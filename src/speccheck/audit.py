"""The top-level audit: run all three modules and emit a Markdown Spec Audit Report.

Every finding is a concrete witness, never just a score:
  - over-constraint -> a minimal input where the spec rejects correct output
  - under-constraint -> a broken program the spec accepts, with a distinguishing input
  - per-clause verdict -> tight / leaky / vacuous, with a witness where relevant
"""
from __future__ import annotations

from typing import Callable, Sequence

from hypothesis import strategies as st

from .types import Spec, AuditReport
from .overconstraint import detect_overconstraint
from .underconstraint import detect_underconstraint
from .localizer import localize


def audit(
    f: Callable,
    spec: Spec,
    strategy: st.SearchStrategy,
    task_name: str = "task",
    n_inputs: int = 200,
    max_examples: int = 400,
    extra_inputs: Sequence[tuple] = (),
) -> AuditReport:
    over = detect_overconstraint(f, spec, strategy, max_examples=max_examples)
    under = detect_underconstraint(f, spec, strategy, n_inputs, extra_inputs)
    verdicts = localize(f, spec, strategy, n_inputs, extra_inputs)
    return AuditReport(
        task_name=task_name,
        spec_clause_names=[c.name for c in spec.clauses],
        over=over,
        under=under,
        clause_verdicts=verdicts,
    )


def _fmt_input(inp):
    if isinstance(inp, tuple):
        return inp[0] if len(inp) == 1 else inp
    return inp


def render_markdown(report: AuditReport) -> str:
    lines: list[str] = []
    L = lines.append

    L(f"# Spec Audit Report — `{report.task_name}`")
    L("")
    L(f"Spec clauses: {', '.join(f'`{n}`' for n in report.spec_clause_names)}")
    L("")

    # ---- overall verdict line ----
    issues = []
    if report.over.found:
        issues.append("OVER-CONSTRAINED")
    if report.under.kill_rate < 1.0:
        issues.append("UNDER-CONSTRAINED")
    headline = " + ".join(issues) if issues else "NO DEFECT DETECTED"
    L(f"**Verdict: {headline}**")
    L("")

    # ---- over-constraint ----
    L("## Over-constraint (spec too strict?)")
    L("")
    if report.over.found:
        L(f"- **Too strict.** {report.over.summary()}")
        L(f"- Witness input: `{_fmt_input(report.over.failing_input)}` — the correct "
          f"implementation returns `{report.over.produced_output}`, which the spec rejects.")
    else:
        L(f"- {report.over.summary()}.")
        L("- (Fuzzing shows the presence of over-constraint, never its absence.)")
    L("")

    # ---- under-constraint ----
    L("## Under-constraint (spec too loose?)")
    L("")
    L(f"- {report.under.summary()}")
    if report.under.survivors:
        L("- **Surviving broken programs the spec accepts:**")
        for s in report.under.survivors:
            L(f"    - `{s.label}` — on input `{_fmt_input((s.distinguishing_input,))[0] if False else _fmt_input(s.distinguishing_input)}`, "
              f"correct output is `{s.correct_output}` but this broken version returns "
              f"`{s.mutant_output}`, and the spec accepts it.")
    else:
        L("- No surviving mutants: the spec caught every genuinely-broken program tested.")
    L("")

    # ---- per-clause localization ----
    L("## Per-clause diagnosis")
    L("")
    L("| Clause | Description | Verdict | Note |")
    L("|---|---|---|---|")
    for v in report.clause_verdicts:
        L(f"| `{v.clause.name}` | {v.clause.description} | **{v.verdict}** | {v.note} |")
    L("")

    # witnesses for leaky clauses
    leaky = [v for v in report.clause_verdicts if v.verdict == "leaky" and v.witness]
    if leaky:
        L("### Witnesses for leaky clauses")
        L("")
        for v in leaky:
            s = v.witness
            L(f"- `{v.clause.name}`: the broken program `{s.label}` returns "
              f"`{s.mutant_output}` on `{_fmt_input(s.distinguishing_input)}` "
              f"(correct: `{s.correct_output}`) and this clause does not reject it.")
        L("")

    L("---")
    L("*Detection + localization only. This audit does not prove the spec correct; "
      "it surfaces concrete mismatches. Coverage is bounded by mutant/probe generation.*")
    return "\n".join(lines)
