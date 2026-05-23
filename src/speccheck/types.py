"""Shared data types for the spec validation harness.

Everything a module produces is one of these. Keeping them in one place means the
localizer and the report writer have a stable contract to depend on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

# A spec clause is a named predicate over (input..., output).
# We keep the name so the report and localizer can refer to clauses by label.
@dataclass
class Clause:
    name: str
    description: str
    predicate: Callable[..., bool]  # called as predicate(*inputs, output)

    def holds(self, inputs: tuple, output: Any) -> bool:
        try:
            return bool(self.predicate(*inputs, output))
        except Exception:
            # A clause that raises on some input is treated as "does not hold"
            # rather than crashing the whole audit.
            return False


@dataclass
class Spec:
    """A spec is a conjunction of named clauses. P(x, y) = all clauses hold."""
    clauses: list[Clause]

    def holds(self, inputs: tuple, output: Any) -> bool:
        return all(c.holds(inputs, output) for c in self.clauses)

    def without(self, clause_name: str) -> "Spec":
        """Return a weakened copy with one clause removed (for ablation)."""
        return Spec([c for c in self.clauses if c.name != clause_name])

    def only(self, clause_name: str) -> "Spec":
        """Return a spec consisting of a single clause (for attribution)."""
        return Spec([c for c in self.clauses if c.name == clause_name])


# ---- detector outputs ----

@dataclass
class OverConstraintResult:
    found: bool
    failing_input: Optional[tuple] = None   # input where correct code's output is rejected
    produced_output: Any = None             # what f produced there
    trials: int = 0

    def summary(self) -> str:
        if not self.found:
            return f"no over-constraint found in {self.trials} trials"
        return (f"spec REJECTS correct output {self.produced_output!r} "
                f"on input {self._fmt(self.failing_input)}")

    @staticmethod
    def _fmt(inp: tuple) -> str:
        return inp[0] if len(inp) == 1 else inp


@dataclass
class Survivor:
    label: str                  # which mutation produced this broken program
    distinguishing_input: tuple # an input where the mutant differs from correct f
    correct_output: Any
    mutant_output: Any


@dataclass
class UnderConstraintResult:
    total_mutants: int
    equivalent_mutants: int
    killed: int
    survivors: list[Survivor] = field(default_factory=list)

    @property
    def tested(self) -> int:
        return self.total_mutants - self.equivalent_mutants

    @property
    def kill_rate(self) -> float:
        if self.tested == 0:
            return 1.0  # nothing genuinely-broken to test against
        return self.killed / self.tested

    def summary(self) -> str:
        return (f"kill rate {self.kill_rate:.0%} "
                f"({self.killed}/{self.tested} genuinely-broken mutants caught; "
                f"{self.equivalent_mutants} equivalent mutants discarded); "
                f"{len(self.survivors)} survivor(s)")


@dataclass
class ClauseVerdict:
    clause: Clause
    verdict: str                # "tight" | "leaky" | "vacuous"
    witness: Optional[Survivor] = None
    note: str = ""


@dataclass
class AuditReport:
    task_name: str
    spec_clause_names: list[str]
    over: OverConstraintResult
    under: UnderConstraintResult
    clause_verdicts: list[ClauseVerdict]
