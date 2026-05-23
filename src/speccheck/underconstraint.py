"""Module 2 — Under-constraint detector (mutation testing).

Under-constraint = the spec is TOO LOOSE: it accepts outputs that are broken. This is
invisible to input-fuzzing (the correct code never produces the bad output), so we
perturb the *code* instead: break f into mutants, and check whether the spec still
accepts them.

A mutant that PASSES the spec "survived" -> the spec was too weak to catch that bug.

Critical subtlety — equivalent mutants: a mutation that doesn't change behaviour isn't
a fair test of the spec (it survives because it's secretly still correct, not because
the spec is loose). We filter these out by checking the mutant actually differs from f
on the sampled inputs.
"""
from __future__ import annotations

from typing import Callable, Sequence

from hypothesis import strategies as st

from .types import Spec, UnderConstraintResult, Survivor
from .mutation import generate_mutants


def _sample_inputs(strategy: st.SearchStrategy, n: int) -> list[tuple]:
    """Draw a fixed batch of inputs from a Hypothesis strategy, reused across mutants
    so kill rates are comparable. Normalise each to a tuple of args."""
    import warnings
    from hypothesis.errors import NonInteractiveExampleWarning

    raw = []
    seen = set()
    # st.lists/etc. don't expose a clean public sampler; .example() is the pragmatic
    # way to pull concrete values. We over-draw and de-dup. The warning about
    # non-interactive .example() use is expected here (we deliberately sample a fixed
    # batch so kill rates are comparable across mutants).
    attempts = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NonInteractiveExampleWarning)
        while len(raw) < n and attempts < n * 5:
            attempts += 1
            v = strategy.example()
            key = repr(v)
            if key in seen:
                continue
            seen.add(key)
            raw.append(v if isinstance(v, tuple) else (v,))
    return raw


def _safe_call(f: Callable, inputs: tuple):
    try:
        return ("ok", f(*inputs))
    except Exception as e:
        return ("err", type(e).__name__)


def detect_underconstraint(
    f: Callable,
    spec: Spec,
    strategy: st.SearchStrategy,
    n_inputs: int = 200,
    extra_inputs: Sequence[tuple] = (),
) -> UnderConstraintResult:
    """Generate mutants of f, discard equivalent ones, and report which survive the spec.

    `extra_inputs` lets a task inject hand-authored edge cases (already tupled) on top
    of the fuzzed batch — useful for stressing specific clauses.
    """
    inputs = _sample_inputs(strategy, n_inputs)
    inputs.extend(extra_inputs)

    # precompute the correct outputs once
    correct = [_safe_call(f, inp) for inp in inputs]

    total = 0
    equivalent = 0
    killed = 0
    survivors: list[Survivor] = []

    for label, mutant in generate_mutants(f):
        total += 1

        # --- equivalence filter: does the mutant ever differ from f? ---
        differs_at = None
        for inp, corr in zip(inputs, correct):
            mres = _safe_call(mutant, inp)
            if mres != corr:
                differs_at = (inp, corr, mres)
                break
        if differs_at is None:
            equivalent += 1
            continue  # behaviourally identical to f -> not a fair test of the spec

        # --- kill check: does the spec REJECT the mutant somewhere? ---
        # We want the spec to catch this genuinely-broken program.
        spec_caught = False
        for inp, corr in zip(inputs, correct):
            mres = _safe_call(mutant, inp)
            if mres[0] == "err":
                # mutant crashed: spec can't accept a non-output -> counts as caught
                spec_caught = True
                break
            if not spec.holds(inp, mres[1]):
                spec_caught = True
                break

        if spec_caught:
            killed += 1
        else:
            # survived: a broken program the spec accepts everywhere we looked
            inp, corr, mres = differs_at
            survivors.append(Survivor(
                label=label,
                distinguishing_input=inp,
                correct_output=corr[1] if corr[0] == "ok" else f"<{corr[1]}>",
                mutant_output=mres[1] if mres[0] == "ok" else f"<{mres[1]}>",
            ))

    return UnderConstraintResult(
        total_mutants=total,
        equivalent_mutants=equivalent,
        killed=killed,
        survivors=survivors,
    )
