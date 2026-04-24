# Learned rules review loop

**Sprint E.2 / E.3 / E.4** close the Camada 1 learning loop.

## How a rule is born

1. Gestor opens `/plan/timeline`, picks an alternative, optionally
   records a reason.
2. The commit persists `rejected_alternatives` with `delta_vs_chosen`
   KPI deltas + `user_preference_signal`.
3. Nightly at 03:00 UTC the `PreferenceRuleDetector` scans the last
   30 days of commits and emits `PreferenceRule` rows with
   `status=detected`.

## Four rule types

| Type | Example | Predicate shape |
|---|---|---|
| `temporal_block` | "Gestor evita Laminagem às sextas" | `{weekday: 5, rejected_count: 6, total_count: 8}` |
| `tradeoff_preference` | "Prefere menos setups a mais throughput" | `{kpi_improved: "setups", kpi_sacrificed: "throughput_eur_day", count: 12}` |
| `operator_affinity` | "Paulo → Laminagem K4" | `{phase_id: "LAMINAGEM", worker_id: "…", sample_count: 11}` |
| `phase_threshold` | "Pintura sempre ≥ 3 workers" | `{phase_id: "PINTURA", min_team_size: 3, sample_count: 9}` |

## Review UI

`/admin/learned-rules` (frontend: `pages/admin/LearnedRulesPage.tsx`):

- Filter by status (detected / confirmed / rejected) + type.
- Each detected row has three actions:
  - **Confirmar** — `POST /v1/governance/preference-rules/{id}/confirm`
    — status flips to `confirmed`; optional notes.
  - **Rejeitar** — `POST /v1/governance/preference-rules/{id}/reject`
    — status flips to `rejected`; reason is **mandatory** for audit.
  - **Editar** — `PATCH /v1/governance/preference-rules/{id}` —
    tweak description / predicate / confidence before confirming.
- Admin role required (`X-User-Role: admin` header until JWT lands).

## Enforcement in the CPO

Confirmed rules flow via `FactoryState.preference_rules` → passed
into `FitnessConfig.preference_rules` → applied per candidate inside
`compute_preference_penalty` (`src/plan/cpo/preference_adapter.py`).

| Type | Penalty shape |
|---|---|
| `temporal_block` | `+50` per op scheduled on the blocked weekday |
| `phase_threshold` | `+100` per op short-staffed in the flagged phase |
| `operator_affinity` | `−15` reward when preferred worker on phase, `+10` when absent |
| `tradeoff_preference` | no-op at fitness level; Camada 2 handles via AdaptiveFitnessWeights |

## Ownership

- **Detector author** owns `src/governance/preference_learning/detector.py`.
- **Gestor** owns the review queue in `/admin/learned-rules`.
- **SRE** owns the nightly cron (`_preference_rule_detector_job`).

## Metrics to watch

- Count of detected rules per nightly scan (healthy: 0-5).
- Confirm/reject ratio (healthy: ≥ 50% of reviewed end up confirmed
  after the first 3 months).
- Fitness penalty contribution — log line in the CPO engine when a
  confirmed rule actually bit a candidate.
