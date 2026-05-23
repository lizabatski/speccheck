# Spec Validation Harness — Project Plan

A tool that checks whether a **specification** is right — not whether the code is right.

---

## 1. The problem, in one paragraph

When you ask an AI to write code, it increasingly also writes a **spec** (a precise
description of what the code should do), and then a checker confirms the code matches the
spec. Everything reports green. But the checker only verifies *code matches spec* — nobody
verifies *spec matches what you actually meant*. So a subtly wrong spec (too permissive, or
missing a requirement) gets faithfully satisfied by the code, and every downstream check
passes, because they all trust the spec. **The spec becomes the bug, and it's invisible**,
because the bug lives in the thing everything else measures against.

Our tool tests the spec itself, and reports the two ways a spec can be wrong, with a
concrete witness for each.

---

## 2. The core idea: two failures, two opposite fixes

A spec is a predicate `P(input, output) -> bool` — it draws a boundary around which outputs
are acceptable. There are exactly two ways that boundary can be wrong:

| Failure | What it means | How we catch it |
|---|---|---|
| **Over-constraint** | Spec is too *strict* — it rejects correct behavior | Perturb the **input**, trust the **code** |
| **Under-constraint** | Spec is too *loose* — it accepts broken behavior | Perturb the **code**, trust the **spec** |

The whole design is this symmetry:

- **Over-constraint** is caught by **property-based fuzzing**: generate many inputs, run the
  *correct* code, and check whether the spec ever rejects the correct output. A rejection
  means the spec forbids something legitimate → too strict.
- **Under-constraint** is caught by **mutation testing**: deliberately *break* the code into
  variants (mutants), then check whether the spec still accepts them. If a *broken* program
  passes the spec → the spec was too weak to catch that bug → too loose.

**Why we need both:** property-based fuzzing alone is *blind to under-constraint*. A
too-loose spec is satisfied by correct code on every input, so no input exposes it — the
flaw is only reachable by producing a wrong output the correct code never would. That's why
the under-constraint side perturbs the *code* instead of the *input*. One technique catches
one failure; we pair them to catch both.

> **The one-line pitch:** Over-constraint = perturb the input and trust the code.
> Under-constraint = perturb the code and trust the spec. A fuzzing harness alone only
> catches the first; we add mutation to catch the second.

---

## 3. What this is honestly built from (say this to judges)

- The **over-constraint detector** *is* a property-based fuzzing harness. We use
  [Hypothesis](https://hypothesis.readthedocs.io/). The twist: the **spec plays the role of
  the property** being fuzzed.
- The **under-constraint detector** is **mutation testing**, pointed at the spec instead of
  at a test suite. Normal mutation testing grades a *test suite* ("do your tests catch
  bugs?"); we grade a *spec* ("is your spec strong enough to reject broken code?").

Neither technique is novel on its own. The contribution is **what we point them at (the
spec, not the code), the symmetry between them, and that every finding is a concrete witness
with clause-level localization.** Do **not** claim property-based testing or mutation
testing is new.

---

## 4. Inputs and output

**Inputs**
- `f` — the implementation (a correct reference function, used for fuzzing and as the base
  to mutate).
- `spec` — the candidate spec, written as a **list of clauses** ANDed together (see §6 on
  why clauses, not one blob).
- `input strategy` — a description of how to generate inputs (a Hypothesis strategy).

**Output: a Spec Audit Report** containing
- **Over-constraint section:** either "none found in N trials" or a *minimal failing input*
  — a concrete input where the correct code's output is rejected by the spec.
- **Under-constraint summary:** a **mutation kill rate** (fraction of genuinely-broken
  mutants the spec caught) plus a list of **survivors** — each a concrete broken program the
  spec wrongly accepts, with the input where it visibly differs from correct.
- **Per-clause verdict table:** each clause tagged **tight / leaky / vacuous**, with a
  witness for each non-clean verdict.

**Principle: every output is a witness, never just a score.** We never merely assert "too
loose" — we exhibit the broken program that proves it. A person can argue with a score; they
can't argue with a wrong program sitting in front of them, passing their spec.

---

## 5. Architecture (three modules)

```
   impl f        spec P (as clauses)      input strategy
      \                 |                      /
       \________________|_____________________/
                        |
        ┌───────────────┴────────────────┐
        |        two independent          |
        |          detectors              |
        |                                 |
   OVER-CONSTRAINT                  UNDER-CONSTRAINT
   fuzz input, run f,               mutate f, check if
   check P(x, f(x))                 broken f still passes P
        |                                 |
   Hypothesis shrinks                drop equivalent mutants
   the failing input                 (keep only behavior-changing)
        |                                 |
   minimal failing input             kill rate + survivors
   (spec too strict here)            (low rate = spec too loose)
        └────────────────┬───────────────┘
                         |
                  LOCALIZER (clause ablation)
                  drop each clause, re-run detectors,
                  label each tight / leaky / vacuous
                         |
                  REPORT (the deliverable)
                  per-clause verdict + a witness for each
```

### Module 1 — Over-constraint detector (property-based fuzzing)
- **Input:** `f`, `spec`, strategy.
- **Does:** uses Hypothesis to search for an input `x` where `P(x, f(x))` is false — i.e.
  the spec rejects the *correct* code's output.
- **Subtlety — shrinking:** Hypothesis automatically reduces a failing input to its minimal
  form (e.g. `[847,-12,9,9]` → `[9,9]`). This is what makes the output legible. We get it
  for free from the library — don't hand-roll a fuzz loop.
- **Honest limit:** "none found in N trials" is *not* proof of no over-constraint. Fuzzing
  shows presence, never absence. Say so in the report.
- **Output:** a minimal failing input, or "none found."

### Module 2 — Under-constraint detector (mutation testing)
- **Input:** `f`, `spec`, strategy.
- **Does, in three steps:**
  1. **Mutate:** parse `f`'s AST and apply small mutation operators (flip `<`→`<=`, `+`→`-`,
     constant `1`→`0`, replace return with a constant, etc.). Each single change = one mutant.
  2. **Filter equivalent mutants** (the critical subtlety, below).
  3. **Test each survivor against the spec:** run `P(x, mutant(x))` over a shared input
     batch. If a *broken* mutant satisfies `P` on every input → it **survived** → the spec
     is too loose there.
- **Subtlety — equivalent mutants:** some mutations don't actually change behavior. Such a
  mutant "survives" not because the spec is loose but because the mutant is secretly still
  correct. **Filter:** run the mutant and the original `f` on the input batch; if they
  *never* differ, the mutant is equivalent → discard it. Only keep mutants that
  demonstrably behave differently from `f` somewhere. This filter is **load-bearing** — an
  unfiltered kill rate is the first thing a sharp judge will attack. (It's undecidable in
  general; the behavioral check handles common cases; name the rest as a limitation.)
- **Output:** kill rate = `killed / (total − equivalent)`, plus the list of surviving broken
  programs with distinguishing inputs.

### Module 3 — Localizer (clause ablation)
- **Input:** `f`, the clause list, strategy. **Calls Modules 1 & 2 as subroutines.**
- **Does:** for each clause `c_i`, build a weakened spec with `c_i` removed and re-run the
  detectors. Compare against the full spec to attribute blame:
  - **Tight** — removing it makes the kill rate *drop* (mutants survive that the full spec
    killed). It does real work. Keep it.
  - **Vacuous** — removing it changes *nothing* (same mutants die). It's redundant /
    decorative. Delete it.
  - **Leaky** — present but too weak: genuinely-broken mutants survive *in this clause's
    domain* even with it in place. Strengthen it.
- **Scope decision:** single-clause ablation only (k runs, linear). We do **not** ablate
  subsets (that's `2^k`, exponential, for a payoff that's mostly redundant). Name the
  limitation: verdicts assume clauses act roughly independently; redundant clause *pairs*
  may both read as vacuous.
- **Output:** the per-clause verdict table — the actionable part ("fix clause 3, here's the
  proof; clause 4 is dead weight").

---

## 6. Key design decisions (locked)

- **Language: Python.** Fastest path to a working, demo-able tool; Hypothesis is
  industrial-grade. (Dafny/Verus would give a stronger over-constraint detector via SMT, but
  cost days and a less legible demo.)
- **Spec format: a list of clause predicates, ANDed.** NOT one opaque boolean. The localizer
  *requires* individually-addressable clauses — it drops one and re-runs. If the spec is one
  blob, Module 3 is impossible. This is not cosmetic; decide it up front.
- **Under-constraint oracle: mutation, NOT a "gold spec".** We detect under-constraint by
  breaking the code and seeing if the spec notices — we do *not* compare against a second
  hand-written "correct" spec. (A correct second spec wouldn't exist in the real situation
  the tool is for; if you could write it, you wouldn't need the tool. Mutation only needs the
  candidate spec + a reference implementation, which is honest to the thesis.)
- **No LLM in the trusted core.** The detection runs on deterministic code: running `f`,
  running mutants, running the spec, comparing. An LLM may *optionally* propose extra probes
  or suggest a clause repair, but it never *judges* correctness. Slogan: **the LLM proposes,
  execution disposes.** The tool runs fully offline.

---

## 7. The demo (90 seconds)

1. **The trap:** show a plausible-looking spec (e.g. password rule
   `len(p) >= 12 and any(c.isdigit() for c in p)`).
2. **Green CI:** the implementation passes tests that match the spec. Everything looks fine.
3. **Run our tool:** `UNDER-CONSTRAINED. Kill rate 40%. Survivor: a program that accepts
   "ninonino12345" (contains the username) — your spec waves it through.`
4. **Punchline:** the code was correct *with respect to the spec*; the spec was the bug, and
   nothing downstream could catch it because everything trusts the spec.
5. **Credibility beat:** contrast with the obvious baseline — asking an LLM "is this spec
   correct?" — which gives a vague yes/no and **no concrete counterexample**.

---

## 8. Benchmark (quick but credible)

We author everything, so the correct diagnosis is known ground truth.

- **~8 tasks**, each with three spec variants: **good / under-constrained / over-constrained**
  (~24 specs). Each task ships a correct reference implementation `f`.
- **Metrics:**
  - detection rate (over-constraint),
  - detection rate (under-constraint),
  - localization accuracy (did we blame the right clause?),
  - **false-flag rate on good specs** (do we wrongly flag correct specs?),
  - counterexample validity (is each reported witness actually a real mismatch?),
  - **and report the miss rate / false-negative rate honestly** — `X%` detection implies
    `(100−X)%` missed; own it.
- **Mandatory baseline:** run the same specs through a single "is this spec correct?" LLM
  prompt and compare. This is what proves the tool does something the obvious approach can't.

---

## 9. Build split (parallelizable)

Modules 1 and 2 are **fully independent** — no shared state, different mechanism. Two people
can build them in parallel on day one. Module 3 just calls 1 and 2, so it's built third.

**Coordinate ONE thing up front:** Modules 1 and 2 each expose a clean entry point with the
same signature, so the localizer can call them repeatedly on synthetic specs:

```python
def run_overconstraint(f, spec, strategy) -> FailingInput | None: ...
def run_underconstraint(f, spec, strategy) -> KillReport:  # kill_rate, survivors
    ...
```

| Owner | Module | Definition of done |
|---|---|---|
| A | Over-constraint (Module 1) | Given `(f, spec, strategy)`, returns a shrunk failing input or "none in N". Wraps Hypothesis. |
| B | Under-constraint (Module 2) | AST mutation generator + equivalence filter + kill-check. Returns kill rate + survivors. |
| C | Localizer + Report (Module 3) | Clause ablation calling A & B; emits the Markdown audit report. Blocked until A & B expose the signatures above. |
| All | Benchmark + baseline | 8 tasks × 3 specs, ground-truth scoring, LLM baseline comparison. |

**Build order for a deadline:** 1 → 2 → 3. Get the `argmax` smoke test (below) working in a
single file *first*, before generalizing.

---

## 10. The smoke test (do this before anything else)

One example that exercises both detectors on one page:

- **Correct `f`:** `argmax` — returns the index of the largest element (first on ties).
- **Over-constrained spec:** `result > 0`. Wrong — fails on a single-element list `[5]`
  (correct answer is index 0). Module 1 should shrink to `[5]` (or `[0]`).
- **Under-constrained spec:** `0 <= result < len(xs)`. True of *any* in-bounds index — a
  mutant that always returns 0 passes it. Module 2 should report that mutant as a survivor.

If you can see Module 1 flag the too-strict spec *and* Module 2 flag the too-loose spec on
this one example, the whole project is real. Generalize from there.

---

## 11. Honest limitations (put these in the writeup — they make us credible)

1. **Coverage is bounded by probe/mutant generation.** We only catch a defect if we generate
   the input (over) or the mutant (under) that exposes it. Like all testing, we show presence
   of defects, not absence. **But our failures are *misses*, not *false assurances*** — we
   never tell you a broken spec is fine, we just sometimes fail to flag it. A miss leaves you
   no worse than before; the dangerous failure (false blessing) is the one we structurally
   avoid.
2. **Equivalent mutants are undecidable in general.** Our behavioral-difference filter handles
   common cases; some equivalents may survive and slightly inflate looseness signals.
3. **Single-clause ablation misreads clause interactions.** Two jointly-necessary-but-
   individually-redundant clauses can both read as vacuous. We chose linear-cost ablation
   over exponential subset analysis deliberately.
4. **We do not prove correctness.** We surface concrete mismatches cheaply. The claim is
   *detection + localization*, never *guarantees intent* or *proves correct*.

---

## 12. What to explicitly NOT build

- No Lean / Dafny / Verus / Coq (Rocq). Python only.
- No auto-repair loop (CEGIS-style). Suggested repairs are advisory text at most.
- No UI before the engine + report work.
- No requirement *elicitation* (that's a different project).
- No cross-model / multi-model LLM disagreement.
- No letting the LLM be the silent final judge.
- No "proves correctness" / "guarantees intent" claims anywhere.

---

## 13. The research claim (modest, measurable)

> On a controlled benchmark of programming tasks where we plant known under- and
> over-constraints into otherwise-plausible specs, a property-based-fuzzing + mutation-testing
> workbench detects **X%** of planted defects and localizes them to the violated clause, with
> a **Y%** false-flag rate on correct specs — outperforming the natural baseline of directly
> asking an LLM "is this spec correct?"

Claims detection + localization. Not correctness.
