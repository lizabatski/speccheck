"""Module 3 — Localizer (clause ablation).

Turns a global verdict ("spec too loose") into a per-clause diagnosis ("clause 3 is
leaky; clause 4 is vacuous"). Mechanism: remove one clause at a time and re-run the
under-constraint detector, comparing the kill rate to the full spec.

  - tight   : removing the clause DROPS the kill rate (it was catching real bugs)
  - vacuous : removing the clause changes NOTHING (redundant / decorative)
  - leaky   : full spec still has survivors that this clause is the natural home for

Scope: single-clause ablation only (linear cost). We do not analyse clause subsets
(exponential); the known limitation is that two jointly-necessary-but-individually-
redundant clauses can both read as vacuous.
"""
from __future__ import annotations

from typing import Callable, Sequence

from hypothesis import strategies as st

from .types import Spec, ClauseVerdict, Survivor
from .underconstraint import detect_underconstraint


def localize(
    f: Callable,
    spec: Spec,
    strategy: st.SearchStrategy,
    n_inputs: int = 200,
    extra_inputs: Sequence[tuple] = (),
) -> list[ClauseVerdict]:
    full = detect_underconstraint(f, spec, strategy, n_inputs, extra_inputs)
    full_killed = full.killed

    verdicts: list[ClauseVerdict] = []

    for clause in spec.clauses:
        weakened = spec.without(clause.name)
        ablated = detect_underconstraint(f, weakened, strategy, n_inputs, extra_inputs)

        # How many mutants did this clause uniquely account for?
        # (kill count drops when we remove a load-bearing clause)
        delta = full_killed - ablated.killed

        if delta > 0:
            # removing it lets previously-killed mutants survive -> it does real work
            verdict = "tight"
            note = (f"removing this clause lets {delta} previously-caught "
                    f"mutant(s) survive")
            witness = None
        else:
            # removing it changed nothing about what got caught. Two sub-cases:
            #   - if the clause is redundant (some OTHER clause already rejects
            #     everything this one would) -> VACUOUS
            #   - otherwise the spec still has survivors this clause is the natural
            #     home for but fails to catch -> LEAKY
            if not full.survivors:
                # no survivors at all and this clause caught nothing unique -> vacuous
                verdict = "vacuous"
                note = "removing this clause does not change which mutants are caught"
                witness = None
            elif _is_redundant(clause, spec, f, strategy, n_inputs, extra_inputs):
                verdict = "vacuous"
                note = ("redundant: other clauses already reject everything this one "
                        "would; removing it changes nothing")
                witness = None
            else:
                verdict = "leaky"
                note = ("clause present but full spec still accepts broken programs; "
                        "this clause does not constrain them")
                witness = _best_witness_for(clause, f, full.survivors)

        verdicts.append(ClauseVerdict(clause=clause, verdict=verdict,
                                      witness=witness, note=note))

    return verdicts


def _is_redundant(clause, spec, f, strategy, n_inputs, extra_inputs) -> bool:
    """A clause is redundant if, on the survivor-distinguishing inputs, it never
    rejects anything the other clauses don't already reject. Operationally: does this
    clause ever single-handedly reject a mutant output that the rest of the spec
    accepts? If it never does, removing it is a no-op -> vacuous.

    We test against the actual mutants: for each mutant output the full spec accepts,
    check whether this clause alone would have rejected it. If never, it's redundant.
    """
    from .mutation import generate_mutants
    rest = spec.without(clause.name)
    single = Spec([clause])

    inputs = _gather_inputs(strategy, n_inputs, extra_inputs)
    for _, mutant in generate_mutants(f):
        for inp in inputs:
            try:
                y = mutant(*inp)
            except Exception:
                continue
            # the clause does real work iff it rejects something `rest` accepts
            if rest.holds(inp, y) and not single.holds(inp, y):
                return False  # this clause uniquely rejects -> NOT redundant
    return True


def _gather_inputs(strategy, n_inputs, extra_inputs):
    import warnings
    from hypothesis.errors import NonInteractiveExampleWarning
    seen, out = set(), []
    attempts = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NonInteractiveExampleWarning)
        while len(out) < n_inputs and attempts < n_inputs * 5:
            attempts += 1
            v = strategy.example()
            key = repr(v)
            if key in seen:
                continue
            seen.add(key)
            out.append(v if isinstance(v, tuple) else (v,))
    out.extend(extra_inputs)
    return out



    """Pick a survivor to attach to a leaky clause: prefer one whose distinguishing
    input the clause itself fails to reject (i.e. the clause is silent on it)."""
    for s in survivors:
        inp = s.distinguishing_input
        # if the single-clause spec accepts the mutant's output here, this clause is
        # demonstrably not the thing catching it
        single = Spec([clause])
        if s.mutant_output is not None and not isinstance(s.mutant_output, str):
            if single.holds(inp, s.mutant_output):
                return s
    return survivors[0] if survivors else None
