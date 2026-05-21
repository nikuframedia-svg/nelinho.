# src/twin/ — Digital Twin

Cenários "what-if" persistidos (deltas + simulação CP-SAT opcional + diff vs baseline). É o
caminho **pesado** de simulação: corre solver CP-SAT real quando o utilizador chama `/solve`;
`/simulate` faz projecção linear quando não há solver. ~1872 LOC.

## Status: **vivo**

Razão: UI usa-o em duas páginas (`TwinPage`, `SimulacoesPage`) + tab (`TwinSandboxTab`) +
componentes (`TwinPanels`, `DeltaWizard`). Frontend tem **2 wrappers paralelos** para Twin
(`lib/api/twinApi.ts` mais limpo, e `lib/api/copilotApi.ts:twinApi` legacy) — ambos vivos.

## Callers backend

- `src/main.py:34` regista `twin_router`.
- `src/shared/model_registry.py:119` importa `twin.models` (Scenario, ScenarioDelta,
  ScenarioComparison) para metadata.create_all.
- Nenhum outro módulo backend chama o serviço Twin directamente (auto-contido).

## Callers frontend

- `pages/twin/TwinPage.tsx` — CRUD + simulate + delete.
- `pages/simulacoes/SimulacoesPage.tsx` — leitura para baseline-vs-simulação.
- `components/twin/TwinPanels.tsx` + `DeltaWizard.tsx` — wizard manual de deltas (chama
  `fetch` directo, não `twinApi`).
- `components/aprendi/tabs/TwinSandboxTab.tsx` — criação rápida a partir de aprendizagem.
- Wrappers: `lib/api/twinApi.ts` (canónico) e `lib/api/copilotApi.ts:twinApi` (legacy).

## Endpoints `/v1/twin/`

`GET /baseline`, `GET /scenarios`, `POST /scenarios`, `GET /scenarios/{id}`,
`DELETE /scenarios/{id}`, `POST /scenarios/{id}/apply-delta`,
`POST /scenarios/{id}/simulate`, `POST /scenarios/{id}/solve` (CP-SAT),
`GET /scenarios/{id}/compare`, `GET /scenarios/{id}/hashes`,
`POST /scenarios/{id}/verify` (audit hash chain). 11 endpoints.

## Decisão Q.67

**Manter como está.** O módulo é o motor canónico para auto-approval por trust no fluxo
"Twin → CPO real" (decisão Q.67.5.C — quando o utilizador quer trust_index sobre um
cenário, é o Twin que o computa, não o Sandbox).

Possível refactor Q.68+: consolidar os dois wrappers frontend (`twinApi.ts` canónico vs
`copilotApi.ts:twinApi` legacy) num único. `TwinPanels` ainda usa `fetch` directo —
migrar para `twinApi` quando se mexer naquele componente.

## Notas para futuras edições

- **Ler antes de editar.** Ficheiros são longos (`service.py` 1192L, `api.py` 423L);
  procura por símbolo antes de tocar.
- `TwinValidationError` é subclasse de `ValueError` para o endpoint devolver 422 em vez de
  400/404 — não alargar a hierarquia sem perceber isto.
- Mensagens de erro **em PT-PT** (regra do módulo).
- `simulate()` tem dois modos: `projecao_linear` (default) e `solver_cpsat`. O `mode_reason`
  é honest — não esconder INSUFFICIENT_DATA com fake KPIs.
- BLOCKED metrics (OEE/Availability/Performance/Quality/OTD) vêm de
  `create_baseline_state()` no service — sem dados reais, ficam BLOCKED, **não simular**.
- Hash chain (`scenario_hash` + endpoint `/verify`) é audit-grade — não regenerar hashes
  sem perceber a cadeia.
