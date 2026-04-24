# Learning loop architecture

Blueprint v2.0 §IV stacks four "camadas" of learning on top of the
CPO engine. Sprints C + D.4 + E + I.1 close most of the loop; I.2–I.4
arrive when we have real-data acumulation.

```
          ┌──────────────────────────────────────────────────────┐
          │                  CPO v4 scheduler                    │
          │  (greedy + GA + FRRMAB + MAP-Elites + CP-SAT + WF)   │
          └────────────────────────┬─────────────────────────────┘
                                   │ emits commit with 5-10
                                   ▼ MAP-Elites alternatives
                          ┌────────────────────┐
                          │  ScheduleCommit    │
                          │  + rejected_alts   │ ← /plan/timeline
                          └────────┬───────────┘
                                   │
          ┌────────────────────────┼─────────────────────────────┐
          │              Four camadas of learning                │
          └────────────────────────┼─────────────────────────────┘
                                   ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ Camada 1 — PreferenceRuleDetector (Sprint C)                │
 │  • nightly cron, 30-day window                              │
 │  • emits PreferenceRule rows (status=detected)              │
 │  • /admin/learned-rules confirm/reject/edit                 │
 │  • confirmed rules fed into FactoryState.preference_rules   │
 │    and applied by compute_preference_penalty                │
 └─────────────────────────────────────────────────────────────┘
 ┌─────────────────────────────────────────────────────────────┐
 │ Camada 2 — AdaptiveFitnessWeights (Sprint D.4)              │
 │  • weekly cron, Sunday 02:00 UTC                            │
 │  • pairwise LogisticRegression on delta_vs_chosen           │
 │  • clip(exp(-coef), 0.5, 2.0) × 70/30 blend vs defaults     │
 │  • writes tenant_config.governance.adaptive_fitness_weights │
 │  • FitnessConfig.from_tenant_config reads on GA start       │
 └─────────────────────────────────────────────────────────────┘
 ┌─────────────────────────────────────────────────────────────┐
 │ Camada 3 — DPODatasetBuilder (Sprint I.1 — dataset ready)   │
 │  • JSONL of (prompt, chosen, rejected) triplets             │
 │  • quarterly QLoRA + DPO fine-tune (Sprint S infra)         │
 │  • A/B vs base model before rolling out                     │
 └─────────────────────────────────────────────────────────────┘
 ┌─────────────────────────────────────────────────────────────┐
 │ Camada 4 — ABLkit (deferred, needs I.2 code)                │
 │  • LLM diagnosis vs kernel disagreement → correction pairs  │
 │  • fed into DPO batch                                       │
 └─────────────────────────────────────────────────────────────┘
```

## Feedback into the GA

Both camadas 1 + 2 are applied *inside* the fitness function
(`src/plan/cpo/fitness.py`) so the next solve honours them
automatically. The GA never calls the network inside the hot loop —
everything is pre-computed at engine-construction time:

- `preference_rules` — list copied from `FactoryState`, evaluated per
  candidate by `compute_preference_penalty`.
- Adaptive weights — four scalar weights plugged into the existing
  `w_makespan / w_tardiness / w_setups / w_quality_risk` fields.
- Causal entropy (Sprint I.5) — per-candidate Shannon entropy over
  machine / workers / mould axes, penalty `0.05 × (1 − score)`.

## Fail-soft guarantees

The fitness function wraps every learning hook in `try/except` and
logs at `warning`. A buggy rule or a corrupted tenant_config row
never takes the GA down.

## Tests to anchor the contract

- `tests/governance/test_preference_detector.py` — Camada 1
- `tests/governance/test_adaptive_weights.py` — Camada 2
- `tests/governance/test_dpo_dataset_builder.py` — Camada 3 dataset
- `tests/plan/test_preference_adapter.py` — rule → GA penalty
- `tests/plan/test_causal_entropy.py` — I.5 entropy term
