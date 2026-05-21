# src/sandbox/ — Sandbox (quick-look simulation)

Sandbox para experimentar sugestões `improve` antes de publicar: aplica `estimated_impact`
ao `after_state`, calcula diff vs `before_state`, e permite "publish" para criar um
`SharedDecisionRun` advisory. ~811 LOC.

## Status: **experimental**

Razão: O service confessa-o explicitamente em `service.py:126-129`:

> `simulate()` — Compute the impact diff between `before_state` and `after_state`.
> **Doesn't run the CPO** — the heavy simulation lives in the Twin module; sandbox is
> a quick-look projection.

A UI existe (`SandboxPage.tsx`) mas é uma vista isolada que não fecha o loop com
auto-approval/CPO. Duplica conceptualmente o Twin para o caso "testa esta sugestão
rapidamente".

## ⚠️ Sandbox NÃO computa trust_index

Auto-approval por trust requer **ScheduleCommit do CPO real** (via `/v1/plan/cpo/schedule`
async) ou **Twin** (via `/v1/twin/scenarios/{id}/solve`). O sandbox limita-se a projecção
linear sobre os campos de `estimated_impact` da sugestão.

Decisão Q.67.5.C (default C): documentar o sandbox como quick-look. NÃO ligar a sandbox
ao motor de auto-approval — para isso usa-se Twin ou CPO directos.

## Callers backend

- `src/main.py:35` regista `sandbox_router`.
- `src/shared/model_registry.py:105` carrega `sandbox.models` (SandboxScenario).
- Nenhum outro módulo backend chama o serviço (auto-contido).

## Callers frontend

- `pages/sandbox/SandboxPage.tsx` — lista + criar + simulate + publish + delete.
- `hooks/useSandboxSimulation.ts` — hook para `factoryApi.sandboxApi`.
- Wrappers duplicados: `lib/factoryApi.ts:sandboxApi` E `lib/api/platformApi.ts:sandboxApi`
  (ambos vivos; consolidar Q.68+).

## Endpoints `/v1/sandbox/`

`GET /scenarios`, `POST /scenarios`, `GET /scenarios/{id}`,
`POST /scenarios/{id}/apply-suggestion`, `POST /scenarios/{id}/simulate`,
`GET /scenarios/{id}/exec-pack`, `POST /scenarios/{id}/publish`,
`GET /blocked-metrics`. 8 endpoints.

## Decisão Q.67

**Manter como experimental**, sem investimento extra. Não apagar — o `SandboxPage` é o
único sítio onde um operador pode "carimbar uma sugestão num cenário e ver o diff" sem
abrir o Twin completo. Útil para demo + smoke tests.

Refactor candidato Q.68+: consolidar `sandboxApi` (factoryApi vs platformApi) num só
wrapper. Considerar absorver no Twin se o caso de uso "quick-look" não vingar.

## Notas para futuras edições

- **Ler antes de editar.** `service.py` 328L, `api.py` 366L — o `simulate()` faz CAS via
  `version` column (Q.12 Onda 3.1), não regredir para read-modify-write naïve.
- **BLOCKED_METRICS é sagrado** — endpoint `/blocked-metrics` lista métricas que NUNCA
  são simuladas com valores fake. NÃO inventar valores para preencher dashboards.
- `apply_suggestion` recebe um dict da sugestão `improve` (loose coupling intencional).
- `publish` cria `SharedDecisionRun` advisory (não bloqueante) — não escalar para
  decisão hard sem passar pelo governance write-gate.
- `SandboxStateError` é distinto de `SandboxNotFoundError`; preserva-los nos endpoints.
