"""Module 1 — Over-constraint detector (property-based fuzzing).

Over-constraint = the spec is TOO STRICT: it rejects an output the *correct* code
legitimately produces. We find it by fuzzing inputs, running the real f, and checking
whether the spec ever rejects f's output.

The spec plays the role of the property. A counterexample (shrunk by Hypothesis) is a
concrete input where the spec forbids correct behavior.
"""
from __future__ import annotations

from typing import Callable

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from .types import Spec, OverConstraintResult


def detect_overconstraint(
    f: Callable,
    spec: Spec,
    strategy: st.SearchStrategy,
    max_examples: int = 400,
) -> OverConstraintResult:
    """Search for an input x where spec rejects f(x) (f assumed correct).

    `strategy` generates a single input value; if f takes multiple args, the strategy
    should produce a tuple and we splat it. We normalise to a tuple internally.
    """
    found = {"hit": False, "input": None, "output": None, "count": 0}

    @settings(max_examples=max_examples,
              suppress_health_check=[HealthCheck.function_scoped_fixture],
              deadline=None)
    @given(value=strategy)
    def _check(value):
        inputs = value if isinstance(value, tuple) else (value,)
        found["count"] += 1
        output = f(*inputs)
        if not spec.holds(inputs, output):
            # record (Hypothesis will shrink `value` to a minimal failing case
            # before this assertion's failure is finally reported)
            found["hit"] = True
            found["input"] = inputs
            found["output"] = output
            assert False, f"spec rejects correct output {output!r} on {inputs!r}"

    try:
        _check()
    except AssertionError:
        pass  # expected: a counterexample was found (and shrunk)

    return OverConstraintResult(
        found=found["hit"],
        failing_input=found["input"],
        produced_output=found["output"],
        trials=found["count"],
    )
