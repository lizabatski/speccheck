# Spec Audit Report — `count_positives [over spec]`

Spec clauses: `exact`, `at_least_one`

**Verdict: OVER-CONSTRAINED**

## Over-constraint (spec too strict?)

- **Too strict.** spec REJECTS correct output 0 on input []
- Witness input: `[]` — the correct implementation returns `0`, which the spec rejects.

## Under-constraint (spec too loose?)

- kill rate 100% (8/8 genuinely-broken mutants caught; 0 equivalent mutants discarded); 0 survivor(s)
- No surviving mutants: the spec caught every genuinely-broken program tested.

## Per-clause diagnosis

| Clause | Description | Verdict | Note |
|---|---|---|---|
| `exact` | result equals the true count of positives | **tight** | removing this clause lets 2 previously-caught mutant(s) survive |
| `at_least_one` | result is at least 1 (TOO STRICT) | **vacuous** | removing this clause does not change which mutants are caught |

---
*Detection + localization only. This audit does not prove the spec correct; it surfaces concrete mismatches. Coverage is bounded by mutant/probe generation.*