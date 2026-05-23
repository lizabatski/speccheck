# Spec Audit Report — `argmax [under spec]`

Spec clauses: `achieves_max`

**Verdict: UNDER-CONSTRAINED**

## Over-constraint (spec too strict?)

- no over-constraint found in 300 trials.
- (Fuzzing shows the presence of over-constraint, never its absence.)

## Under-constraint (spec too loose?)

- kill rate 86% (6/7 genuinely-broken mutants caught; 0 equivalent mutants discarded); 1 survivor(s)
- **Surviving broken programs the spec accepts:**
    - `cmp#0: Gt -> GtE` — on input `[-47, -44, 33, -17, -23, 33]`, correct output is `2` but this broken version returns `5`, and the spec accepts it.

## Per-clause diagnosis

| Clause | Description | Verdict | Note |
|---|---|---|---|
| `achieves_max` | xs[r] equals the maximum value | **tight** | removing this clause lets 6 previously-caught mutant(s) survive |

---
*Detection + localization only. This audit does not prove the spec correct; it surfaces concrete mismatches. Coverage is bounded by mutant/probe generation.*