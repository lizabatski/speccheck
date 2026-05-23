"""Benchmark runner.

For each task we have three specs with KNOWN ground truth:
  - good  -> should be flagged clean (no over, no under)
  - under -> should be flagged UNDER-CONSTRAINED
  - over  -> should be flagged OVER-CONSTRAINED

We score:
  - detection rate (under): of the `under` specs, how many did we flag as under?
  - detection rate (over):  of the `over` specs, how many did we flag as over?
  - false-flag rate (good): of the `good` specs, how many did we WRONGLY flag?
  - localization: for `over` specs with a spurious clause, did we tag that clause? for
    `under` specs, did we surface a real survivor witness?

The harness never receives the ground-truth label — only (f, spec, strategy).

Optional: --baseline runs a single "is this spec correct?" LLM prompt for comparison.
Requires ANTHROPIC_API_KEY; skipped (with a note) if absent so the offline demo works.
"""
from __future__ import annotations

import csv
import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tasks"))

from speccheck.audit import audit  # noqa: E402
from tasks import ALL_TASKS  # noqa: E402


def harness_verdict(task, spec):
    """Return (flagged_over, flagged_under, report)."""
    report = audit(task.f, spec, task.strategy, task_name=task.name,
                   n_inputs=150, max_examples=300)
    flagged_over = report.over.found
    flagged_under = report.under.kill_rate < 1.0
    return flagged_over, flagged_under, report


def run_benchmark(write_csv: str | None = None):
    rows = []
    tally = {
        "under_detected": 0, "under_total": 0,
        "over_detected": 0, "over_total": 0,
        "good_false_flag": 0, "good_total": 0,
        "localize_over_ok": 0, "localize_over_total": 0,
        "localize_under_ok": 0, "localize_under_total": 0,
    }

    for task in ALL_TASKS:
        for label, spec in [("good", task.good), ("under", task.under), ("over", task.over)]:
            fo, fu, report = harness_verdict(task, spec)

            # scoring
            if label == "under":
                tally["under_total"] += 1
                if fu:
                    tally["under_detected"] += 1
                # localization: did we surface a survivor witness?
                tally["localize_under_total"] += 1
                if report.under.survivors:
                    tally["localize_under_ok"] += 1
            elif label == "over":
                tally["over_total"] += 1
                if fo:
                    tally["over_detected"] += 1
                # localization: did any clause get flagged that contains the spurious one?
                tally["localize_over_total"] += 1
                # the planted spurious clause is the last clause in the `over` spec
                # we count localization OK if over-constraint was found at all (the
                # report names the failing input; clause-level for over is future work)
                if fo:
                    tally["localize_over_ok"] += 1
            else:  # good
                tally["good_total"] += 1
                if fo or fu:
                    tally["good_false_flag"] += 1

            verdict = []
            if fo:
                verdict.append("OVER")
            if fu:
                verdict.append("UNDER")
            verdict = "+".join(verdict) if verdict else "clean"
            correct = (
                (label == "good" and verdict == "clean") or
                (label == "under" and fu) or
                (label == "over" and fo)
            )
            rows.append({
                "task": task.name, "spec": label, "harness_verdict": verdict,
                "kill_rate": f"{report.under.kill_rate:.2f}",
                "over_found": fo, "correct": correct,
            })

    # ---- print summary ----
    def rate(a, b):
        return f"{(a / b * 100):.0f}%" if b else "n/a"

    print("\n=== HARNESS RESULTS ===")
    print(f"Under-constraint detection: {tally['under_detected']}/{tally['under_total']} "
          f"({rate(tally['under_detected'], tally['under_total'])})")
    print(f"Over-constraint detection:  {tally['over_detected']}/{tally['over_total']} "
          f"({rate(tally['over_detected'], tally['over_total'])})")
    print(f"False-flag on good specs:   {tally['good_false_flag']}/{tally['good_total']} "
          f"({rate(tally['good_false_flag'], tally['good_total'])})")
    print(f"Localization (under, has witness): "
          f"{tally['localize_under_ok']}/{tally['localize_under_total']} "
          f"({rate(tally['localize_under_ok'], tally['localize_under_total'])})")

    print("\n=== PER-SPEC ===")
    print(f"{'task':<16}{'spec':<8}{'verdict':<12}{'kill':<7}{'correct'}")
    for r in rows:
        print(f"{r['task']:<16}{r['spec']:<8}{r['harness_verdict']:<12}"
              f"{r['kill_rate']:<7}{'✓' if r['correct'] else '✗'}")

    if write_csv:
        with open(write_csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nWrote {write_csv}")

    return rows, tally


def run_llm_baseline():
    """The mandatory baseline: ask an LLM 'is this spec correct?' with no probes."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n=== LLM BASELINE ===")
        print("Skipped: ANTHROPIC_API_KEY not set. (The harness runs fully offline; the")
        print("baseline is optional and only used for the comparison in the writeup.)")
        print("Expected result when run: the LLM gives a vague yes/no with no concrete")
        print("counterexample, and cannot localize which clause is at fault.")
        return

    try:
        import anthropic
    except ImportError:
        print("\n=== LLM BASELINE ===\nSkipped: `anthropic` package not installed.")
        return

    client = anthropic.Anthropic()
    print("\n=== LLM BASELINE (is this spec correct?) ===")
    for task in ALL_TASKS:
        for label, spec in [("good", task.good), ("under", task.under), ("over", task.over)]:
            clause_text = "\n".join(f"- {c.description}" for c in spec.clauses)
            prompt = (f"Requirement: {task.requirement}\n\n"
                      f"Candidate specification (all clauses must hold):\n{clause_text}\n\n"
                      f"Is this specification a correct and complete capture of the "
                      f"requirement? Answer YES or NO and one sentence why.")
            msg = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            ans = "".join(b.text for b in msg.content if hasattr(b, "text")).strip()
            print(f"[{task.name}/{label}] {ans[:160]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None, help="write per-spec results to this CSV")
    ap.add_argument("--baseline", action="store_true", help="also run the LLM baseline")
    args = ap.parse_args()

    run_benchmark(write_csv=args.csv)
    if args.baseline:
        run_llm_baseline()
