# Spec Audit Report — `clamp [under spec]`

Spec clauses: `in_range`

**Verdict: UNDER-CONSTRAINED**

## Over-constraint (spec too strict?)

- no over-constraint found in 300 trials.
- (Fuzzing shows the presence of over-constraint, never its absence.)

## Under-constraint (spec too loose?)

- kill rate 67% (4/6 genuinely-broken mutants caught; 2 equivalent mutants discarded); 2 survivor(s)
- **Surviving broken programs the spec accepts:**
    - `const-return: return lo` — on input `(63, 4, 27)`, correct output is `27` but this broken version returns `4`, and the spec accepts it.
    - `const-return: return hi` — on input `(-51, 6, 37)`, correct output is `6` but this broken version returns `37`, and the spec accepts it.

## Per-clause diagnosis

| Clause | Description | Verdict | Note |
|---|---|---|---|
| `in_range` | result is within [lo, hi] | **tight** | removing this clause lets 4 previously-caught mutant(s) survive |

---
*Detection + localization only. This audit does not prove the spec correct; it surfaces concrete mismatches. Coverage is bounded by mutant/probe generation.*