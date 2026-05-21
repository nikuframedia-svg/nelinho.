# Q.67.3.B — Mutation-aware test design for decoder & fitness

## Why not just run mutmut?

`scripts/mutation_test.ps1 -Module cpo` runs ~30min on Luis' laptop and
generates a survivor list that we then have to *read* and *act on*. The
Q.66.C.3 baseline already documented the target (<100 survivors in
`src/plan/cpo/{decoder,fitness}.py`) and the survivor pattern is
predictable: comparison flips, magic-number tweaks, sign inversions,
default-value removals.

This sub-sprint took the **inverse approach**: instead of running mutmut
and chasing survivors, we wrote tests that *pre-emptively kill* the
mutant classes mutmut is known to generate. The two new files

- `tests/plan/test_decoder_mutation_pin_q67.py` (44 tests)
- `tests/plan/test_fitness_mutation_pin_q67.py` (50 tests)

each target the smallest, most boundary-heavy helpers in their module
and pin every operator / constant / default that mutmut hammers.

## Mutant classes covered

| Mutmut operator             | Example mutation                | Test pattern that kills it                            |
| --------------------------- | ------------------------------- | ----------------------------------------------------- |
| Comparison flip             | `>` → `>=`, `==` → `!=`         | Boundary value at `threshold` AND `threshold ± 1`      |
| Constant 1/0                | `max(1, x)` → `max(0, x)`       | Input where the floor matters (`pocket_count=-3 → 1`) |
| Magic-number tweak          | `100.0` → `101.0` (cap)         | Input that exceeds the cap (over-capacity → 100.0)    |
| Sign flip                   | `- norm_throughput` → `+`       | Schedule with throughput > 0 vs zero (must DECREASE)  |
| `or default` removal        | `... or 1` → `...`              | Falsy input that must collapse to the default         |
| Branch constant True/False  | `if use_v2_weights: ...`        | Test BOTH legacy and v2 mode at the same input        |
| Tuple/list constant emptied | `REWORK_BUFFER_PHASE_KEYWORDS`  | Assert seed dict keeps all 3 buckets                  |

## Pinned functions

### `decoder.py`
- `_pocket_count` — `max(1, int(... or 1))` guard
- `classify_rework_phase` — substring containment, `.lower()`, seed dict
- `_is_desmolde` — `startswith` vs `==` vs `endswith(".desmolde")`
- `_last_on_machine_has_different_family` — `batch_size` tail-skip, empty-family
- `_estimate_utilization` — `min(100.0, ...)` cap, `max(1.0, span)` divisor
- `_empty_result` — every zero/empty field, `warnings` copy semantics
- `compute_mold_batches` — `pocket_count <= 1`, singleton URGENCY_DAYS=3 window

### `fitness.py`
- `compute_fitness` — dispatch on `use_v2_weights`, safety penalty in both modes
- `_legacy_fitness` — each of the 4 weights (1.0, 10.0, 0.5, 0.10)
- `_v2_fitness` — sum-to-one constraint, normalisation refs, throughput sign
- `_rework_penalty_hours` — `<=1.0` short-circuit, threshold inclusion
- `build_op_features_for_risk` — `or 1` workers fallback, every `or` chain
- Truck consolidation `> 0` guard

## How this maps to mutmut survivors

When Luis (or CI) runs `pwsh scripts/mutation_test.ps1 -Module cpo` in
a nocturnal CI slot, the survivor count for these two files should
drop substantially vs the Q.66.C.3 baseline: most of the killed
mutations live in arithmetic and boundary lines that these 94 new
tests now nail to exact values.

Survivors that remain will mostly be *equivalent mutations* (different
syntax, same semantics — e.g. `x + 0` ↔ `x`) and *logging strings*
that don't affect schedule output. Those are tolerated.

## Maintenance rule

If a future PR changes any constant in `decoder.py` or `fitness.py`
(a weight, a threshold, a normalisation reference), it MUST update
the matching pin-test in this campaign. The test failures are the
audit trail — never silence them with `pytest.skip`.
