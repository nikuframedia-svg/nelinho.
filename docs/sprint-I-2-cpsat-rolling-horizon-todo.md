# Sprint I.2 — CP-SAT Rolling Horizon (L-RHO) — deferred

**Status:** planned, deliberately out-of-scope for the current session.
Sprints I.1 (Workforce Hungarian module), I.3 (quality-risk fitness hook)
and I.4 (mould multi-pocket batching) are complete; this doc captures
what I.2 will do so it can be picked up cleanly.

## Why deferred

The current CP-SAT engine ([src/plan/engines/cpsat_engine.py](../src/plan/engines/cpsat_engine.py))
is single-resource (machine only). A proper L-RHO refactor would:

1. Rewrite the formulation with `IntervalVar` + `NoOverlap` per centro
   **and** per-operator (dual-resource constraints).
2. Add rolling windows of 2 days with 1-day overlap.
3. Wire the Sprint H `QualityRiskModel` to mark "stable" operations and
   fix them as warm-start variables across windows.
4. Respect the 30-second budget per window.

That's a 1-2 week focused effort. Bundling it into the current session
would add significant risk on top of the six already-shipping changes.

## What still needs doing

1. **Refactor variable model**
   - One `IntervalVar` per operation, width = predicted duration.
   - `AddNoOverlap` per machine AND per operator.
   - Mould exclusivity via a second `NoOverlap` over `IntervalVar`s keyed
     by `mold_id` (multi-pocket molds use `AddCumulative(capacity=pocket_count)`).

2. **Sliding window decomposition**
   - Partition the horizon into windows of 2 days, 1 day overlap.
   - Solve each window with the previous window's solution as warm start.
   - Fix operations in the overlap region (their end time ≤ window_end -
     overlap).

3. **Stability prediction hook**
   - Consume `QualityRiskModel` predictions.
   - When `P(disruption) < 0.1`, freeze the op across subsequent
     re-solves to avoid churn.

4. **Observability**
   - Per-window solve time.
   - Warm-start hit rate (fraction of ops transferred from the previous
     window's solution).

## Dependencies

- `ortools>=9.8.3296` (already in [requirements.txt](../requirements.txt)).
- Sprint H `QualityRiskModel` (shipped — `0f5632e` + `211f081`).
- Sprint I.4 mold batching (shipped — this PR) — the CP-SAT solver
  should produce the same batch layout as the greedy decoder.

## References

- L-RHO (2025): *Learning-Guided Rolling Horizon Optimization for FJSP*,
  ICLR 2025.
- Brenndoerfer (2025): *CP-SAT Rostering — Decomposition for workforce
  scheduling*.

## Acceptance criteria

- `CPSATScheduler.schedule_rolling(...)` returns a dict compatible with
  the current `SchedulingResult`.
- Tests on a 50-boat synthetic problem: makespan improves 5-15% vs.
  the single-shot CP-SAT baseline.
- Dual-resource feasibility: no two ops share a worker's time window.
- Mould cumulative respects pocket counts.
