# Spec Audit Report — `clamp [over spec]`

Spec clauses: `in_range`, `preserves_interior`, `strict_hi`

**Verdict: OVER-CONSTRAINED**

## Over-constraint (spec too strict?)

- **Too strict.** spec REJECTS correct output 21 on input (21, 0, 21)
- Witness input: `(21, 0, 21)` — the correct implementation returns `21`, which the spec rejects.

## Under-constraint (spec too loose?)

- kill rate 100% (6/6 genuinely-broken mutants caught; 2 equivalent mutants discarded); 0 survivor(s)
- No surviving mutants: the spec caught every genuinely-broken program tested.

## Per-clause diagnosis

| Clause | Description | Verdict | Note |
|---|---|---|---|
| `in_range` | result is within [lo, hi] | **vacuous** | removing this clause does not change which mutants are caught |
| `preserves_interior` | if x already in range, result is x | **tight** | removing this clause lets 1 previously-caught mutant(s) survive |
| `strict_hi` | result strictly below hi (TOO STRICT) | **vacuous** | removing this clause does not change which mutants are caught |

---
*Detection + localization only. This audit does not prove the spec correct; it surfaces concrete mismatches. Coverage is bounded by mutant/probe generation.*