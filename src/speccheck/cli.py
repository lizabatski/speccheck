"""Command-line interface.

Usage:
    python -m speccheck.cli --task argmax --spec under
    python -m speccheck.cli --task clamp --spec good --out report.md

Loads a task from the benchmark `tasks` module and prints/writes its audit report.
"""
from __future__ import annotations

import argparse
import os
import sys


def _load_tasks():
    here = os.path.dirname(__file__)
    tasks_dir = os.path.join(here, "..", "..", "tasks")
    sys.path.insert(0, tasks_dir)
    import tasks as tasks_mod  # type: ignore
    return {t.name: t for t in tasks_mod.ALL_TASKS}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit a candidate spec for over/under-constraint.")
    ap.add_argument("--task", required=True, help="task name (e.g. argmax, clamp, count_positives)")
    ap.add_argument("--spec", default="under", choices=["good", "under", "over"],
                    help="which planted spec variant to audit")
    ap.add_argument("--out", default=None, help="write the Markdown report to this file")
    ap.add_argument("--n-inputs", type=int, default=200)
    ap.add_argument("--max-examples", type=int, default=400)
    args = ap.parse_args(argv)

    from speccheck.audit import audit, render_markdown

    tasks = _load_tasks()
    if args.task not in tasks:
        ap.error(f"unknown task '{args.task}'. Available: {', '.join(tasks)}")
    task = tasks[args.task]
    spec = {"good": task.good, "under": task.under, "over": task.over}[args.spec]

    report = audit(task.f, spec, task.strategy,
                   task_name=f"{task.name} [{args.spec} spec]",
                   n_inputs=args.n_inputs, max_examples=args.max_examples)
    md = render_markdown(report)

    if args.out:
        with open(args.out, "w") as fh:
            fh.write(md)
        print(f"wrote {args.out}")
    else:
        print(md)


if __name__ == "__main__":
    main()
