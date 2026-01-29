# CONTRATO 030 — Twin Lite e Sandbox

## Status
**IMPLEMENTADO**

## Objectivo
Motor de cenários tipo "branch/merge" para simular decisões antes de executar:
- Snapshot base (active ingestion)
- Deltas incrementais (patches)
- Solver timeboxed
- Comparação (diff) e reprodutibilidade

**Sem sandbox, o produto limita-se a reporting.**

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                 FACTORY DATA PRODUCT (C10)                       │
│                                                                  │
│     factory_curated.* (active_ingestion_id)                     │
│                                                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ snapshot
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TWIN SANDBOX                                 │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │twin_scenario│───▶│twin_delta   │───▶│twin_result  │         │
│  │             │    │             │    │             │         │
│  │base_ingestion│   │entity_type  │    │kpis_json    │         │
│  │state        │    │patch_json   │    │diff_vs_base │         │
│  │version (OL) │    │idempotency  │    │solver_status│         │
│  └─────────────┘    └─────────────┘    │result_hash  │         │
│                                         └─────────────┘         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ solve (timeboxed)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SOLVER ENGINE                               │
│                                                                  │
│  - Timebox: 5-15s (configurable)                                │
│  - Deterministic mode (seed-based)                              │
│  - Best-effort on timeout                                       │
│  - ExplainedValues output (C20)                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Modelo de Dados

### `twin_scenario`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | uuid | PK |
| `base_active_ingestion_id` | uuid | Snapshot base |
| `state` | enum | draft \| solved \| archived |
| `owner_id` | string | Quem criou |
| `title` | string | Nome descritivo |
| `scenario_version` | int | Optimistic locking |
| `created_at_utc` | timestamp | |
| `updated_at_utc` | timestamp | |

### `twin_scenario_delta`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | uuid | PK |
| `scenario_id` | uuid | FK |
| `delta_idempotency_key` | string | Unique per scenario |
| `entity_type` | enum | CAPACITY \| STANDARD_TIME \| SEQUENCE \| MOLD_POLICY |
| `entity_key` | string | Business key (e.g., "fase:F001") |
| `patch_json` | jsonb | RFC6902 or merge patch |
| `created_at_utc` | timestamp | |

### `twin_scenario_result`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `scenario_id` | uuid | FK |
| `version` | int | Result version |
| `kpis_json` | jsonb | List of ExplainedValues |
| `diff_vs_base_json` | jsonb | Delta comparison |
| `solver_status` | enum | ok \| best_effort \| failed \| timeout |
| `trust_summary_json` | jsonb | Aggregated trust |
| `result_hash` | string | SHA256 for reproducibility |
| `computed_at_utc` | timestamp | |
| `solver_duration_ms` | int | Execution time |

## Deltas Suportados v1

| Delta Type | Descrição | Constraints |
|------------|-----------|-------------|
| `CAPACITY` | Capacidade teórica por fase | ±50% do base |
| `STANDARD_TIME` | Standard time por produto/fase | ±30% do base |
| `SEQUENCE` | Sequenciação teórica de ordens | Heurística simples |
| `MOLD_POLICY` | Políticas de ocupação de molde | Janelas/buffers |

**IMPORTANTE**: Não prometer óptimo global. Apenas simulação what-if.

## Solver Constraints

```python
# Configuration
SOLVER_TIMEOUT_MS_DEFAULT = 10000   # 10s
SOLVER_TIMEOUT_MS_MIN = 5000        # 5s
SOLVER_TIMEOUT_MS_MAX = 30000       # 30s

# Behavior
- Se timeout → solver_status = "best_effort"
- Se falha → solver_status = "failed"
- Deterministic mode: seed fixo → mesmos outputs
```

## APIs

| Endpoint | Method | Descrição |
|----------|--------|-----------|
| `/v1/twin/scenarios` | POST | Criar cenário |
| `/v1/twin/scenarios/{id}` | GET | Obter cenário |
| `/v1/twin/scenarios/{id}/deltas` | POST | Aplicar delta |
| `/v1/twin/scenarios/{id}/solve` | POST | Calcular KPIs |
| `/v1/twin/scenarios/{id}/compare` | GET | Comparar cenários |
| `/v1/twin/scenarios/{id}/merge` | POST | Merge deltas |

## Concurrency

### Optimistic Locking
```
PUT /scenarios/{id}
If-Match: scenario_version=5

Response:
- 200 OK: version updated to 6
- 409 Conflict: {
    "current_version": 7,
    "your_version": 5,
    "diff": {...}
  }
```

### Delta Conflicts
```
POST /scenarios/{id}/deltas

Response on conflict:
- 409 Conflict: {
    "conflict_set": [
      {"existing_delta": {...}, "proposed_delta": {...}}
    ]
  }
```

**NUNCA resolver conflitos silenciosamente.**

## Critérios de Aceitação

- [x] Reprodutibilidade: `result_hash` estável
- [x] Timeboxing: solve nunca bloqueia indefinidamente
- [x] Comparação com ExplainedValue + lineage + trust
- [x] Efeitos confinados ao sandbox (não altera curated/semantic)

## Ficheiros Implementados

```
src/twin/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── scenario.py         # twin_scenario, twin_scenario_delta, twin_scenario_result
│   └── enums.py            # ScenarioState, DeltaType, SolverStatus
├── deltas/
│   ├── __init__.py
│   ├── types.py            # Delta type definitions
│   ├── validator.py        # Patch validation
│   └── applicator.py       # Apply deltas to snapshot
├── solver/
│   ├── __init__.py
│   ├── engine.py           # Main solver with timebox
│   └── deterministic.py    # Seed-based determinism
├── api/
│   ├── __init__.py
│   └── endpoints.py        # /v1/twin/* endpoints
└── tests/
    ├── __init__.py
    ├── test_scenarios.py
    ├── test_solver.py
    └── test_concurrency.py
```

## Testes

- **Unit**: Validação de patches, idempotência de delta
- **Integration**: Criar cenário → aplicar deltas → resolver → comparar
- **Load**: 20 solves concorrentes (graceful degradation)


