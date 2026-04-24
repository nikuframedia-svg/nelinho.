# Adaptive Fitness Weights (Camada 2)

**Sprint D.4** — weekly retrain of the GA's cost weights from the
operator's accept/reject history.

## Math

Four legacy scalar weights participate (`w_makespan`, `w_tardiness`,
`w_setups`, `w_quality_risk`):

1. Collect `delta_vs_chosen` from every rejected alternative in the
   past 30 days.
2. Build a pairwise dataset: for each delta vector `d`, emit two
   rows — `(−d, label=1)` for "chosen was preferred" and `(+d,
   label=0)` for "rejected was not preferred".
3. Standardise features (`StandardScaler`) so heterogeneous KPI
   scales don't dominate.
4. Fit `sklearn.linear_model.LogisticRegression(fit_intercept=False,
   class_weight='balanced')`.
5. For each weight *w*: `multiplier = clip(exp(−coef), 0.5, 2.0)`,
   then `w_blended = 0.70 × w_learned + 0.30 × w_default` (Blueprint
   §5.5).

## Guardrails

- **< 50 pairs in the window** → skip retrain, keep defaults. Noise
  is worse than no adaptation.
- **Multiplier clamp `[0.5, 2.0]`** → a single noisy week can't flip
  the GA upside-down.
- **70/30 blend** → even with a strong signal, defaults keep a 30 %
  anchor.
- **Write-through `TenantConfigService`** → every retrain is
  history-preserving, audit-visible in `tenant_config` table.

## Cron

`_preference_weights_retrain_job` in `src/shared/scheduler.py`:
`CronTrigger(day_of_week=6, hour=2, minute=0, timezone="UTC")` —
Sunday 02:00 UTC so Monday morning starts with fresh weights.

## Reading the weights at GA start

`FitnessConfig.from_tenant_config(session, tenant_id)` — async
factory that:

1. Loads adaptive weights via `load_adaptive_weights`.
2. Falls back to defaults if no row exists / retrain was skipped.
3. Returns a regular `FitnessConfig`, usable anywhere one is expected.

Existing callers that use `FitnessConfig()` keep hardcoded defaults —
adaptive weights are opt-in.

## Observability

- `RetrainResult.status`: `trained` / `skipped` / `error`.
- `RetrainResult.pairs_used`: fed count.
- `RetrainResult.coefficients`: z-scored LR coef per weight — useful
  for "why did w_setups move that much?"

Log line every run (INFO level):
```
adaptive_fitness_weights: tenant=… commits=… pairs=… weights={…}
```

## Tests

`tests/governance/test_adaptive_weights.py` — insufficient-data
fallback, direction-of-learning (60 synthetic commits preferring low
setup → `w_setups` rises), multiplier clamp, blend ratio,
`load_adaptive_weights` partial-fallback.
