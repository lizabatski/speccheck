# Spec Audit Report — `argmax [good spec]`

Spec clauses: `achieves_max`, `is_first`

**Verdict: NO DEFECT DETECTED**

## Over-constraint (spec too strict?)

- no over-constraint found in 300 trials.
- (Fuzzing shows the presence of over-constraint, never its absence.)

## Under-constraint (spec too loose?)

- kill rate 100% (7/7 genuinely-broken mutants caught; 0 equivalent mutants discarded); 0 survivor(s)
- No surviving mutants: the spec caught every genuinely-broken program tested.

## Per-clause diagnosis

| Clause | Description | Verdict | Note |
|---|---|---|---|
| `achieves_max` | xs[r] equals the maximum value | **tight** | removing this clause lets 2 previously-caught mutant(s) survive |
| `is_first` | no earlier index achieves the max | **vacuous** | removing this clause does not change which mutants are caught |

---
*Detection + localization only. This audit does not prove the spec correct; it surfaces concrete mismatches. Coverage is bounded by mutant/probe generation.*