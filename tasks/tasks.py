"""Benchmark tasks. Each task ships:
  - a correct reference implementation `f`
  - an input `strategy`
  - three specs: `good`, `under` (planted under-constraint), `over` (planted over-constraint)

We author everything, so the correct diagnosis is known ground truth. The harness is
scored against these labels; the harness never sees the label, only (f, spec, strategy).

Clauses are written to be cleanly separable (non-overlapping) so per-clause localization
is unambiguous in the demo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from hypothesis import strategies as st

from speccheck.types import Clause, Spec


@dataclass
class Task:
    name: str
    f: Callable
    strategy: st.SearchStrategy
    good: Spec
    under: Spec   # planted: too loose
    over: Spec    # planted: too strict
    requirement: str


# ───────────────────────── Task 1: argmax (first index of max) ─────────────────────────
def argmax(xs):
    best = 0
    for i in range(1, len(xs)):
        if xs[i] > xs[best]:
            best = i
    return best

_argmax_strat = st.lists(st.integers(min_value=-50, max_value=50), min_size=1, max_size=6)

argmax_task = Task(
    name="argmax",
    f=argmax,
    strategy=_argmax_strat,
    requirement="Return the index of the largest element; on ties, the FIRST such index.",
    good=Spec([
        Clause("achieves_max", "xs[r] equals the maximum value",
               lambda xs, r: 0 <= r < len(xs) and xs[r] == max(xs)),
        Clause("is_first", "no earlier index achieves the max",
               lambda xs, r: all(xs[k] < xs[r] for k in range(r))),
    ]),
    # UNDER: drops the "is_first" clause -> accepts ANY max index (ties unhandled)
    under=Spec([
        Clause("achieves_max", "xs[r] equals the maximum value",
               lambda xs, r: 0 <= r < len(xs) and xs[r] == max(xs)),
    ]),
    # OVER: adds a spurious "result must be > 0" -> rejects correct index 0
    over=Spec([
        Clause("achieves_max", "xs[r] equals the maximum value",
               lambda xs, r: 0 <= r < len(xs) and xs[r] == max(xs)),
        Clause("is_first", "no earlier index achieves the max",
               lambda xs, r: all(xs[k] < xs[r] for k in range(r))),
        Clause("positive", "result is strictly positive (SPURIOUS)",
               lambda xs, r: r > 0),
    ]),
)


# ───────────────────────── Task 2: clamp value into [lo, hi] ─────────────────────────
def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x

_clamp_strat = st.tuples(
    st.integers(min_value=-100, max_value=100),
    st.integers(min_value=-20, max_value=20),
    st.integers(min_value=21, max_value=60),
)

clamp_task = Task(
    name="clamp",
    f=clamp,
    strategy=_clamp_strat,
    requirement="Clamp x into [lo, hi]: return lo if x<lo, hi if x>hi, else x.",
    good=Spec([
        Clause("in_range", "result is within [lo, hi]",
               lambda x, lo, hi, r: lo <= r <= hi),
        Clause("preserves_interior", "if x already in range, result is x",
               lambda x, lo, hi, r: not (lo <= x <= hi) or r == x),
        Clause("saturates", "if x out of range, result is the nearest bound",
               lambda x, lo, hi, r: (lo <= x <= hi) or r == (lo if x < lo else hi)),
    ]),
    # UNDER: only checks the result is in range -> accepts always-return-lo
    under=Spec([
        Clause("in_range", "result is within [lo, hi]",
               lambda x, lo, hi, r: lo <= r <= hi),
    ]),
    # OVER: demands result strictly less than hi -> rejects correct clamp-to-hi
    over=Spec([
        Clause("in_range", "result is within [lo, hi]",
               lambda x, lo, hi, r: lo <= r <= hi),
        Clause("preserves_interior", "if x already in range, result is x",
               lambda x, lo, hi, r: not (lo <= x <= hi) or r == x),
        Clause("strict_hi", "result strictly below hi (TOO STRICT)",
               lambda x, lo, hi, r: r < hi),
    ]),
)


# ───────────────────────── Task 3: count_positives ─────────────────────────
def count_positives(xs):
    c = 0
    for v in xs:
        if v > 0:
            c += 1
    return c

_cp_strat = st.lists(st.integers(min_value=-10, max_value=10), min_size=0, max_size=8)

count_pos_task = Task(
    name="count_positives",
    f=count_positives,
    strategy=_cp_strat,
    requirement="Return how many elements are strictly greater than zero.",
    good=Spec([
        Clause("nonneg", "result is non-negative",
               lambda xs, r: r >= 0),
        Clause("upper_bound", "result does not exceed list length",
               lambda xs, r: r <= len(xs)),
        Clause("exact", "result equals the true count of positives",
               lambda xs, r: r == sum(1 for v in xs if v > 0)),
    ]),
    # UNDER: drops exactness -> accepts any count in [0, len]
    under=Spec([
        Clause("nonneg", "result is non-negative",
               lambda xs, r: r >= 0),
        Clause("upper_bound", "result does not exceed list length",
               lambda xs, r: r <= len(xs)),
    ]),
    # OVER: demands result >= 1 -> rejects the correct 0 for all-negative lists
    over=Spec([
        Clause("exact", "result equals the true count of positives",
               lambda xs, r: r == sum(1 for v in xs if v > 0)),
        Clause("at_least_one", "result is at least 1 (TOO STRICT)",
               lambda xs, r: r >= 1),
    ]),
)


ALL_TASKS = [argmax_task, clamp_task, count_pos_task]
