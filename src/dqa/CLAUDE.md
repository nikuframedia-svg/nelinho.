# src/dqa/ — Data Quality Autopilot

Calcula o **Trust Index v2** (7+1 componentes), expõe quality gates contextuais
(`effective_mode`), e detecta drift de distribuições. ~1653 LOC. Núcleo: `trust_v2.py`,
`trust_signals.py`, `trust_gates.py`, `consistency_rules.py`, `distribution_drift_detector.py`.

## Status: **vivo**

Razão: Trust Index v2 está integrado em CPO (`plan/api/cpo.py:455`), diagnostics, copilot
context_builder, e factory_map_service. UI activa em 3 páginas (DQAPage, TrustTab, hook
`useTrustHeatmap`). Trust v1 já foi apagada (Q.61.29) — esta é a única implementação viva.

## O que sobreviveu à limpeza Q.61.29

- `trust_v2.py` — calculator 7-component v2 (canónico, em uso).
- `trust_gates.py` — `effective_mode()` lê config dos 5 gates (block/warn/allow).
- `trust_signals.py` — `curated_signals_provider` agrega sinais do FDP curated.
- `consistency_rules.py` — regras de consistência cross-table (sem v1).
- `distribution_drift_detector.py` — detecta drift estatístico (PSI/KL); usado por
  `explain/diagnostics/multivariate_monitor.py`.
- `quality_gates.py` — middleware FastAPI (`QualityGateMiddleware` em `main.py:61`).
- `auto_repair.py` — repair determinista de inconsistências detectadas.

## Callers backend

- `src/main.py:61` regista `QualityGateMiddleware`; `src/main.py:602` regista `dqa_router`.
- `src/plan/api/cpo.py:455` — CPO consulta TrustIndex antes de propor schedule.
- `src/diagnostics/service.py:339-341` — diagnostics inclui trust.
- `src/copilot/context_builder.py:16-17` — copilot mete trust no contexto LLM.
- `src/factory_data_product/services/factory_map_service.py:948-950` — factory_map inclui
  trust no payload.
- `src/explain/diagnostics/multivariate_monitor.py:37` — usa `DriftDetector`.
- `src/shared/model_registry.py:52` — carrega `dqa.models` (TrustComponentSnapshot,
  TrustComponentWeight, ToolTrustSnapshot, etc.).

## Callers frontend

- `pages/admin/DQAPage.tsx` — dashboard principal trust.
- `pages/configuracao/tabs/TrustTab.tsx` — config de pesos/gates.
- `hooks/useTrustHeatmap.ts` — projecta 7 componentes em heatmap.
- Wrapper: `lib/api/qualityApi.ts:dqaApi`.

## Endpoints `/v1/dqa/`

Apenas `GET /trust-index?scope=factory|order|phase&scope_id=...`. Devolve composite + 7
componentes + pesos + effective_gates.

## Decisão Q.67

**Manter.** Trust v1 já foi apagada (Q.61.29); o que resta é o mínimo coerente em uso.

Não inflar: NÃO adicionar endpoints novos sem caso de uso real. O DQA cresce por consumo
externo (mais sinais, mais regras de consistência), não por API surface.

## Notas para futuras edições

- **Ler antes de editar.** `trust_v2.py` (376L) e `trust_signals.py` (308L) têm lógica
  matemática delicada (composite weights, scope dispatch).
- `SCOPE_FACTORY` / `SCOPE_ORDER` / `SCOPE_PHASE` — não criar scopes novos sem actualizar
  `ALLOWED_SCOPES` em `trust_v2.py`.
- Trust v2 escreve `TrustComponentSnapshot` para histórico — não fazer dropping de tabelas
  sem migrar.
- Não reintroduzir "TrustIndex v1" — foi removida intencionalmente em Q.61.29.
- `effective_gates` retorna **dict de booleanos** (gate ON/OFF efectivo); UI espera isso.
- `prodplan_trust_index_score` (Prometheus) é emitido no endpoint — não remover sem
  actualizar dashboards.
