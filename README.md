# speccheck — a spec validation harness

Checks whether a **specification** is right — not whether the code is right.

When an AI writes code *and* a spec, downstream checks only confirm *code matches spec*.
Nobody confirms *spec matches what you meant*. A subtly wrong spec then gets faithfully
satisfied by the code, and every check passes — the **spec itself is the bug**, and it's
invisible because everything trusts it. `speccheck` tests the spec and reports the two
ways it can be wrong, each with a concrete witness.

## The idea: two failures, two opposite probes

| Failure | Meaning | How we catch it |
|---|---|---|
| **Over-constraint** | spec too *strict* — rejects correct behavior | perturb the **input** (property-based fuzzing), trust the code |
| **Under-constraint** | spec too *loose* — accepts broken behavior | perturb the **code** (mutation testing), trust the spec |

Property-based fuzzing alone is **blind to under-constraint**: a too-loose spec is
satisfied by correct code on every input, so no input exposes it. The only way to reach
the gap is to produce a wrong output — i.e. run a *broken* program and see if the spec
notices. That's the mutation half. The contribution is the symmetry, plus that every
finding is a concrete witness with per-clause localization.

This is, honestly, **property-based testing + mutation testing pointed at the spec**.
Neither technique is novel; *what we point them at* and *the symmetry between them* is.

## Quickstart

```bash
pip install -r requirements.txt          # just Hypothesis

# audit one spec
PYTHONPATH=src python -m speccheck.cli --task clamp --spec under

# run the whole benchmark (9 specs, known ground truth)
python benchmark/run_benchmark.py --csv benchmark/results.csv

# run the benchmark + LLM baseline comparison (needs ANTHROPIC_API_KEY + `pip install anthropic`)
python benchmark/run_benchmark.py --baseline

# run the tests
python tests/test_harness.py
```

## What you get

A **Spec Audit Report** (Markdown) with:
- **Over-constraint:** a minimal input where the correct code's output is rejected by the spec.
- **Under-constraint:** a mutation **kill rate** + a list of **surviving broken programs**
  the spec accepts, each with a distinguishing input.
- **Per-clause diagnosis:** each clause tagged **tight / leaky / vacuous**, with witnesses.

Committed examples live in `examples/` (all 9 benchmark specs).

## Layout

```
src/speccheck/
  types.py            shared data types (Spec, Clause, report shapes)
  overconstraint.py   Module 1 — property-based fuzzing (Hypothesis)
  mutation.py         AST mutation generator (operator swaps + constant-return mutants)
  underconstraint.py  Module 2 — mutation testing + equivalence filter
  localizer.py        Module 3 — clause ablation -> tight/leaky/vacuous
  audit.py            orchestrator + Markdown report writer
  cli.py              command-line interface
tasks/tasks.py        benchmark tasks (correct impl + good/under/over specs)
benchmark/            runner + results.csv + LLM baseline
examples/             committed audit reports
tests/                self-checking tests (no pytest needed)
```

## Specs are clauses, not blobs

A spec is a **list of named clauses** ANDed together — not one opaque boolean. The
localizer needs to drop one clause and re-run, so clauses must be individually
addressable. See `tasks/tasks.py` for examples.

```python
from speccheck.types import Clause, Spec
spec = Spec([
    Clause("achieves_max", "xs[r] equals the max value",
           lambda xs, r: 0 <= r < len(xs) and xs[r] == max(xs)),
    Clause("is_first", "no earlier index achieves the max",
           lambda xs, r: all(xs[k] < xs[r] for k in range(r))),
])
```

## Honest limitations

- **Coverage is bounded by mutant/probe generation.** We only catch a defect if we
  generate the input (over) or the mutant (under) that exposes it. Like all testing, we
  show *presence* of defects, not absence. **But our failures are misses, not false
  assurances** — we never certify a broken spec as fine; we only sometimes fail to flag
  one. (See the `clamp` under-constraint case: it's only caught once `return lo`/`return
  hi` mutants are generated — better mutant generation closes the gap.)
- **Equivalent mutants are undecidable in general.** Our behavioral-difference filter
  handles common cases.
- **Single-clause ablation misreads clause interactions.** Two
  jointly-necessary-but-individually-redundant clauses can both read as vacuous. We chose
  linear-cost ablation over exponential subset analysis deliberately.
- **No correctness proof.** The claim is *detection + localization*, never *guarantees
  intent* or *proves correct*.

## No LLM in the trusted core

Detection runs on deterministic code: run `f`, run mutants, run the spec, compare. The
tool works fully offline. An LLM may *optionally* propose extra probes or repairs, but
never judges correctness. **The LLM proposes; execution disposes.**
