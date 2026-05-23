# Spec Audit Report — `count_positives [under spec]`

Spec clauses: `nonneg`, `upper_bound`

**Verdict: UNDER-CONSTRAINED**

## Over-constraint (spec too strict?)

- no over-constraint found in 300 trials.
- (Fuzzing shows the presence of over-constraint, never its absence.)

## Under-constraint (spec too loose?)

- kill rate 62% (5/8 genuinely-broken mutants caught; 0 equivalent mutants discarded); 3 survivor(s)
- **Surviving broken programs the spec accepts:**
    - `cmp#0: Gt -> GtE` — on input `[0]`, correct output is `0` but this broken version returns `1`, and the spec accepts it.
    - `const#1: 0 -> 1` — on input `[-5, -4, 7, 6, 1, 1, -4, 3]`, correct output is `5` but this broken version returns `3`, and the spec accepts it.
    - `const-return: return 0` — on input `[-3, 4]`, correct output is `1` but this broken version returns `0`, and the spec accepts it.

## Per-clause diagnosis

| Clause | Description | Verdict | Note |
|---|---|---|---|
| `nonneg` | result is non-negative | **tight** | removing this clause lets 1 previously-caught mutant(s) survive |
| `upper_bound` | result does not exceed list length | **tight** | removing this clause lets 3 previously-caught mutant(s) survive |

---
*Detection + localization only. This audit does not prove the spec correct; it surfaces concrete mismatches. Coverage is bounded by mutant/probe generation.*