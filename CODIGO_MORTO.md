# CÓDIGO MORTO — nelinho

> Análise de quanto código pode ser apagado e quanto o código vivo pode encolher, para o projeto
> ficar lean mantendo-se hiperfuncional. Base: **91 subagents, 5 workflows, ~9M tokens**.
> Verificação determinística (reachability BFS direto+reverso, grafo AST de imports) + ronda
> **adversarial** (cada candidato atacado: "prova que está vivo"). Data: 2026-06-02.
> **Documento de análise — nenhum código foi alterado.**

## Sumário

| | LOC | % |
|---|---:|---:|
| **Total hoje** | 438.025 | 100% |
| Código MORTO (apagável com segurança) | **~141.000** | ~32% |
| Melhoria do código vivo (dedup/genericizar, sem perder features) | ~22.600 | ~5% |
| **Alvo realista escolhido (todas as features intactas)** | **~274.000** | ~63% |

100k no total **não é alcançável** sem cortar o copiloto (o mínimo viável CPO+copiloto+fundação ≈ 155k).
O alvo saudável = apagar o morto + consolidar o vivo, mantendo tudo.

---

## 🔒 SISTEMAS PROTEGIDOS — NUNCA APAGAR

Tracei a espinha dorsal viva. **Nada no inventário de morto lhe toca.** Guard-rail: commit que mexa = STOP.

| Sistema | Onde | Prova de vida |
|---|---|---|
| **nelo_dag / stack causal** | `src/copilot/causal/*` (nelo_dag, attribution, chain, discovery, world_model, ablkit, audit, runtime) | 2 jobs do scheduler (`core.py:558 _causal_discovery_job`, `core.py:526 _abl_feedback_job`) + RLM (`rlm/agent.py`, `rlm/factory_state_query.py`) |
| **Cube ↔ BD real** | `src/copilot/cube/{client,query,interpret,narrate,measure_contract,schema_compiler}.py` | `CubeClient` ← `routers/ask_cube.py` montado; queries contra `marts.v_*` |
| **Marts** | `scripts/setup_marts_*.py` (58) + `cube/model/*.yml` (48) | DDL das views vivas; cube models glob-loaded (`load_all_cube_yamls`). **NÃO vestigiais** |
| **Ligação ERP / BD real** | `src/adapters/nelo/*` | ETL `__import__` dinâmico; sync ERP→BD real |
| **RLM do copiloto** | `src/copilot/rlm/*`, `fact_pack_builder.py` | resposta diagnóstica do copiloto |
| **CPO engine (Spelke)** | `src/plan/cpo/*` (decoder, fitness, chromosome, safety_net, mapelites, frrmab, state, pair_assignment) | engine.py/scheduler_run.py + property-tests |

---

## Inventário do código morto (~141.000 LOC)

### A. Frontend (~113.000 LOC) — herança da consolidação Q.115
| Bloco | LOC | Prova |
|---|---:|---|
| `lib/api/generated/` (Orval, 689 fich) + `orvalMutator.ts` | 55.385 | 0 importadores; 1344 símbolos gerados, 0 usados; app usa `client.ts` manual |
| Páginas/componentes mortos (`pages/*`, `components/*` fora das rotas vivas) | ~54.600 | reachability direto+reverso de `main.tsx` (236 fich); 404 confirma "removida na consolidação Q.115" |
| Dead-symbols em ficheiros vivos + `lib/factoryApi.ts` antigo | ~3.000 | grep zero-caller |

**Rotas VIVAS (preservar):** `pages/{decisoes,overall,llm,configuracoes,login,operadores,search,
copilot,expedicao}` + `admin/RegrasPage`. Tudo o resto sob `pages/`/`components/` é morto.

### B. Backend (~17.000 LOC) — routers sem cliente + órfãos puros
- **Routers montados mas sem cliente vivo** (apagáveis ao desmontar de `routers_registry.py`):
  `src/reports/` (1.014), `src/profit/{pricing,cogs,scenarios,dashboard,oee,bonus}` (~5.800),
  `src/ml/api.py` (389), `src/hr/{payroll,productivity,allocations}` (~2.460), `src/supply/*` exceto o
  service do shortage-job (~2.480).
- **Órfãos puros** (grafo AST, 558/636 módulos alcançáveis de entradas vivas):
  `cpsat_lrho.py` (396), `ml/features/`+`feature_engineering/` (478), `copilot/tools/{schema_introspection,
  sql_runner,diagnostic_tools}` (805), `dqa/auto_repair.py` (195)+`consistency_rules.py` (83),
  `factory_data_product/cli/` (319), `shared/events/handlers.py` (281), `ml/llm/*` (~520),
  `fact_packs/schedule_fact_pack.py` (211), `guardrails_tier1/2` (282), `cpo/workforce.py` Hungarian
  (176, opt-in nunca ligado), `replan_hook.py` (138), `infrastructure/erp/sqlserver/` (386, adapter ERP
  **antigo** auto-deprecado — NÃO é a ligação viva, que é `adapters/nelo/*`).

### C. Testes de código morto (~9.000 LOC)
`tests/profit+supply+hr` (5.108), `tests/{dqa,explain,improve,…}` (1.950), `tests/copilot` (1.435 — de
schema_introspection/sql_runner/ontology/guardrails_tier/ml-llm), `tests/quality+twin+sandbox` (646)…

### D. Scripts / config / routes (~1.800 LOC)
`routes/*.yml` golden-SQL engine (554, loader já removido do branch), seeds de config de features mortas
em `default_configs.py` (627), 8 scripts órfãos (626).

### E. Duplicação consolidável (~1.500 LOC líquidos)
`lib/factoryApi.ts`/`workforceApi.ts` antigos vs `lib/api/*`, `_safe_float`×6→1, 8 routers CRUD
`core/api/*` genericizáveis via `BaseCRUDService` (que já existe, morto).

---

## ⚠️ HOLD — adjacentes ao Cube/nelo_dag, verificar 1-a-1 antes de tocar
- `copilot/cube/yaml_validator.py` (171) — 0 importadores, mas é validador dos cube/model (dev-tool).
- `copilot/ontology/entities.py` (186) — referencia nelo_dag; confirmar que a RLM não o carrega.
- `explain/routers/diagnostics.py`+`mill_diff.py`+`correlation.py` — causal-adjacentes; confirmar.

## 🟡 Dependente de política (~7.900 LOC) — fora do alvo (mantém-se)
O copiloto invoca **dinamicamente** GETs `/v1/explain` e `/v1/quality` (allowlist do `tool_registry`).
Apagáveis **só se** aceitares que o copiloto perde essas análises. No alvo ~274k **mantêm-se**.

## 🛑 RESGATADOS — parecem mortos mas são VIVOS (NÃO apagar — partiria a app)
A ronda adversarial impediu 3+ enganos:
- **Os 2 sistemas de decisão NÃO são redundantes** — `governance/*` tem kill-switch, hash-chain de
  auditoria, SoD, yaml-policy, e é chamado pelo job de ML-retrain + sandbox + profit dashboard.
- **`explain/` reichenbach+erro_tree+multivariate** — vivos via jobs do scheduler.
- **Semantic-queries (2 impls)** — ambas vivas.
- **profit `/preview`+`/kpis`+throughput**, **supply shortage-job**, **quality runbook/rework/risk/molds**,
  **HR LegacyAllocation** — vivos.

---

## Melhoria do código VIVO (~22.600 LOC) — Fase B, sem perder funcionalidade
- **Genericizar CRUD** (~1.050): 8 routers `core/api/*` + `MasterDataService` (~620 repetidos x7) → `BaseCRUDService`.
- **Reduzir redundância de testes** (~2.850–8.650): characterization obsoletos, sobre-testagem, fixtures duplicadas.
- **explain/learning/search/resto** (~3.100): boilerplate de routers/jobs.
- **copilot vivo** (~800–1.700): dev-twins (`routers/ask.py`), error-envelope factory (`response_renderer.py:346..432`), `@degrade_to`.
- **plan** (~370): 8× `get_tenant_id`→`require_tenant_header`; `get_or_404()`.
- **governance** (~185): `_get_decision_run`×5→1.
- **frontend lib/api+hooks** (~1.350): wrappers repetidos por endpoint.

---

## Metodologia / confiança
- Frontend: reachability BFS de `main.tsx` (estático + `import()` + alias `@/`), validado direto+reverso;
  sem `import.meta.glob`/auto-route → estático autoritativo.
- Backend: grafo AST de imports (resolve relativos + `__import__` dinâmico), seeded de entradas VIVAS
  (rotas vivas + 43 jobs do scheduler + allowlist copiloto + ETL + Arq worker + model_registry).
- Adversarial: cada candidato refutado por caller (frontend vivo / job / copiloto / ETL / externo).
- Nota: um total bruto intermédio (206.961) tinha um double-count (um agente etiquetou o frontend morto
  inteiro como "novo") — corrigido para ~141k.

## Plano de execução
Ver `.claude/plans/quero-que-analises-de-binary-harbor.md` — Fase A (apagar morto, A0→A3) + Fase B
(melhorar vivo), 1 commit por bloco, `verify.ps1`/`npm run build`/vitest verdes a cada passo.
