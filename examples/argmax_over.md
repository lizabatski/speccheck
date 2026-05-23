# Spec Audit Report — `argmax [over spec]`

Spec clauses: `achieves_max`, `is_first`, `positive`

**Verdict: OVER-CONSTRAINED**

## Over-constraint (spec too strict?)

- **Too strict.** spec REJECTS correct output 0 on input [0]
- Witness input: `[0]` — the correct implementation returns `0`, which the spec rejects.

## Under-constraint (spec too loose?)

- kill rate 100% (7/7 genuinely-broken mutants caught; 0 equivalent mutants discarded); 0 survivor(s)
- No surviving mutants: the spec caught every genuinely-broken program tested.

## Per-clause diagnosis

| Clause | Description | Verdict | Note |
|---|---|---|---|
| `achieves_max` | xs[r] equals the maximum value | **vacuous** | removing this clause does not change which mutants are caught |
| `is_first` | no earlier index achieves the max | **vacuous** | removing this clause does not change which mutants are caught |
| `positive` | result is strictly positive (SPURIOUS) | **vacuous** | removing this clause does not change which mutants are caught |

---
*Detection + localization only. This audit does not prove the spec correct; it surfaces concrete mismatches. Coverage is bounded by mutant/probe generation.*