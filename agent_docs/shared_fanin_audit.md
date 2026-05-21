# `src/shared/` fan-in audit (Q.67.6.C1)

Audit: 21 ficheiros `.py` em `src/shared/` + subdirs (`api/`, `auth/`, `events/`,
`models/`, `realtime/`). Métrica: `from src.shared.<modulo> import` em qualquer
ficheiro fora de `src/shared/` (callers em `src/<dominio>/` + `tests/`).

Baseline antes desta passagem: ~300 imports `from src.shared.*` em 154
ficheiros (`src/` exclusivo, sem `tests/`). Subset apenas-`src/`.

## Top 20 módulos `src/shared/` por fan-in (callers `src/` apenas)

| Rank | Módulo                          | Callers src/ | Notas                                    |
|------|---------------------------------|--------------|------------------------------------------|
| 1    | `database`                      | 109          | base — não tocar                         |
| 2    | `kafka_client`                  | 30           | core infra — não tocar                   |
| 3    | `config`                        | 36           | core infra — não tocar                   |
| 4    | `pagination`                    | 7            | 5 core_api + 2 modules — não single-use  |
| 5    | `observability`                 | 5            | infra — não tocar                        |
| 6    | `decorators`                    | 5            | 5 callers + 2 tests — multi-use          |
| 7    | `tracing`                       | 1            | só `app/startup.py` — infra app          |
| 8    | `outbox_models`                 | 3            | router + executor — multi-use            |
| 9    | `scheduler` (shim)              | ~4           | shim Q.66.A.4 — manter                   |
| 10   | `model_registry`                | (wildcard)   | Q.61.14 — agrega Base.metadata           |
| 11   | `event_schemas`                 | 1 (+2 sh.)   | usado por 2 outros shared/ — NÃO mover   |
| 12   | `outbox_dispatcher`             | 1            | só `app/startup.py` — infra app          |
| 13   | `error_reporting`               | 1            | só `app/startup.py` — infra app          |
| 14   | `event_contracts`               | 0            | só `shared/events/handlers.py` — interno |
| 15   | `secret_manager`                | 0            | só tests — manter                        |
| 16   | `http_metrics_middleware`       | 1            | só `app/middleware_registry.py` — infra  |
| 17   | `redis_client`                  | 7            | multi-use                                |
| 18   | `scheduler_lock` ✓ MOVIDO       | 2            | ambos em `src/scheduling/jobs/`          |
| 19   | `explanation_engine` ✓ MOVIDO   | 1            | só `src/profit/api/kpis.py`              |
| 20   | `auth/middleware`, `auth/*`     | múltiplos    | core infra auth — não tocar              |

Subdirs `src/shared/api/`, `src/shared/realtime/`, `src/shared/events/`,
`src/shared/models/`, `src/shared/auth/` ficam intactos — todos são API
agregadora, infra realtime, modelos partilhados (User, governance), ou auth core.

## Single-use movidos nesta passagem

| De                                  | Para                                    | Razão                                                                                                                  |
|-------------------------------------|-----------------------------------------|------------------------------------------------------------------------------------------------------------------------|
| `src/shared/explanation_engine.py`  | `src/profit/explanation_engine.py`      | Único caller em `src/profit/api/kpis.py` (local import). Já importa `src.plan.models.schedule` (cross-domain ok no profit). |
| `src/shared/scheduler_lock.py`      | `src/scheduling/scheduler_lock.py`      | 2 callers, ambos em `src/scheduling/jobs/` (preference_learning + causal). Tight cohesion: lock só faz sentido para os jobs do scheduling. |

### Mudanças auxiliares

- `tests/shared/test_explanation_engine_q67_1d.py` — import actualizado.
- `tests/shared/test_explanation_engine_kpis.py` — import actualizado.
- `pyproject.toml` — removida regra `ignore_imports` `"src.shared.explanation_engine -> src.plan.models.schedule"` (já não aplicável; profit→plan não é forbidden).

## Candidatos para Q.68 (complexos, não tocados)

1. **`src/shared/decorators.py`** (5 callers): `governance.ab_framework` + `governance.models` — semântica de governance. Candidato a mover para `src/governance/decorators.py` mas tem 5 callers de domínios diferentes (explain, copilot, improve). Avaliar tracking real.
2. **`src/shared/pagination.py`** (7 callers, todos sob `core/api/` + `sandbox/api.py` + `improve/api.py`): poderia subir para `src/shared/api/pagination.py` (já que é util de routers FastAPI) mas não reduz fan-in — só reorganiza.
3. **`src/shared/event_schemas.py`** (1 caller externo, 2 internal shared): pendente até que `event_contracts.py` e `outbox_dispatcher.py` sejam refactorizados — circular dep impede move directo.
4. **`src/shared/error_reporting.py`**, **`tracing.py`**, **`outbox_dispatcher.py`**, **`http_metrics_middleware.py`**: cada um tem 1 caller (`src/app/*.py`). São infra app-level — mover para `src/app/` seria coerente (afinal startup.py orquestra-os), mas é re-arrangement, não reduzir fan-in real. Avaliar Q.68 se Luis quiser consolidar app infra.

## Counts antes/depois

```
ANTES: from src.shared.* (callers src/, excluindo src/shared/) = 300
       de 154 ficheiros, em 19 módulos shared/*.py
DEPOIS: 300 - 3 = 297 (-3 imports)
       2 módulos movidos, 2 testes ajustados
```

Redução modesta (~1%) — passagem conservadora alinhada com a TOUCH MAP (max 10 ficheiros movidos, "só o que é claramente single-use"). Q.68 pode fazer rearranjos maiores (app infra) se justificado.
