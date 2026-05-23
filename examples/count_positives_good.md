# Spec Audit Report — `count_positives [good spec]`

Spec clauses: `nonneg`, `upper_bound`, `exact`

**Verdict: NO DEFECT DETECTED**

## Over-constraint (spec too strict?)

- no over-constraint found in 300 trials.
- (Fuzzing shows the presence of over-constraint, never its absence.)

## Under-constraint (spec too loose?)

- kill rate 100% (8/8 genuinely-broken mutants caught; 0 equivalent mutants discarded); 0 survivor(s)
- No surviving mutants: the spec caught every genuinely-broken program tested.

## Per-clause diagnosis

| Clause | Description | Verdict | Note |
|---|---|---|---|
| `nonneg` | result is non-negative | **vacuous** | removing this clause does not change which mutants are caught |
| `upper_bound` | result does not exceed list length | **vacuous** | removing this clause does not change which mutants are caught |
| `exact` | result equals the true count of positives | **tight** | removing this clause lets 3 previously-caught mutant(s) survive |

---
*Detection + localization only. This audit does not prove the spec correct; it surfaces concrete mismatches. Coverage is bounded by mutant/probe generation.*