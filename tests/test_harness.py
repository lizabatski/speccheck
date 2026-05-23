"""Self-checking tests (run directly: `python tests/test_harness.py`).

No pytest dependency — each check asserts and prints. Exits non-zero on failure.
Validates the harness against the known ground truth in the benchmark tasks.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tasks"))

from hypothesis import strategies as st  # noqa: E402
from speccheck.types import Clause, Spec  # noqa: E402
from speccheck.overconstraint import detect_overconstraint  # noqa: E402
from speccheck.underconstraint import detect_underconstraint  # noqa: E402
from speccheck.audit import audit  # noqa: E402
from tasks import ALL_TASKS  # noqa: E402

FAILURES = []


def check(name, cond):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}")
    if not cond:
        FAILURES.append(name)


def test_overconstraint_basic():
    print("test: over-constraint detects a too-strict spec")
    def argmax(xs):
        best = 0
        for i in range(1, len(xs)):
            if xs[i] > xs[best]:
                best = i
        return best
    strat = st.lists(st.integers(-50, 50), min_size=1, max_size=6)
    strict = Spec([Clause("pos", "r>0", lambda xs, r: r > 0)])
    res = detect_overconstraint(argmax, strict, strat)
    check("flags too-strict spec", res.found)
    check("witness is a single-element list", res.found and len(res.failing_input[0]) == 1)


def test_underconstraint_basic():
    print("test: under-constraint detects a too-loose spec")
    def argmax(xs):
        best = 0
        for i in range(1, len(xs)):
            if xs[i] > xs[best]:
                best = i
        return best
    strat = st.lists(st.integers(-50, 50), min_size=1, max_size=6)
    loose = Spec([Clause("inb", "0<=r<len", lambda xs, r: 0 <= r < len(xs))])
    res = detect_underconstraint(argmax, loose, strat)
    check("loose spec has kill rate < 1", res.kill_rate < 1.0)
    check("loose spec has at least one survivor", len(res.survivors) >= 1)


def test_kill_rate_monotonic():
    print("test: kill rate increases as spec tightens")
    def argmax(xs):
        best = 0
        for i in range(1, len(xs)):
            if xs[i] > xs[best]:
                best = i
        return best
    strat = st.lists(st.integers(-50, 50), min_size=1, max_size=6)
    loose = Spec([Clause("inb", "0<=r<len", lambda xs, r: 0 <= r < len(xs))])
    tight = Spec([Clause("first", "first max",
                         lambda xs, r: 0 <= r < len(xs)
                         and all(xs[k] <= xs[r] for k in range(len(xs)))
                         and all(xs[k] < xs[r] for k in range(r)))])
    kl = detect_underconstraint(argmax, loose, strat).kill_rate
    kt = detect_underconstraint(argmax, tight, strat).kill_rate
    check(f"tight ({kt:.0%}) >= loose ({kl:.0%})", kt >= kl)
    check("tight spec kills everything", kt == 1.0)


def test_benchmark_ground_truth():
    print("test: harness matches ground truth on all benchmark specs")
    for task in ALL_TASKS:
        # good -> clean
        r = audit(task.f, task.good, task.strategy, n_inputs=120, max_examples=250)
        check(f"{task.name}/good is clean",
              not r.over.found and r.under.kill_rate == 1.0)
        # under -> flagged under
        r = audit(task.f, task.under, task.strategy, n_inputs=120, max_examples=250)
        check(f"{task.name}/under flagged", r.under.kill_rate < 1.0)
        # over -> flagged over
        r = audit(task.f, task.over, task.strategy, n_inputs=120, max_examples=250)
        check(f"{task.name}/over flagged", r.over.found)


if __name__ == "__main__":
    test_overconstraint_basic()
    test_underconstraint_basic()
    test_kill_rate_monotonic()
    test_benchmark_ground_truth()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        sys.exit(1)
    print("ALL TESTS PASSED")
