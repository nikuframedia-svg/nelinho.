# AUDIT.md — Documento-mestre da auditoria profunda ao nelinho

**Data:** 2026-06-11 · **Âmbito:** todo o repo `c:/Users/User/nelinho` + BD real (read-only) · **Agentes:** 44

> **Nota sobre números:** todas as contagens de base de dados neste documento são um **snapshot de
> 2026-06-11** (instância docker `prodplan-pg-wsl`, base `prodplan_one`). O ERP sincroniza de 5 em 5
> minutos — os valores absolutos mudam, as ordens de grandeza e os zeros estruturais não.

## Índice dos documentos de entrega

| Documento | Conteúdo |
|---|---|
| **[AUDIT.md](AUDIT.md)** (este) | Documento-mestre: problemas críticos/dados/lógica/UX, funcionalidades em falta, perguntas bloqueantes |
| [DATA_FLOW_MAP.md](DATA_FLOW_MAP.md) | Mapa ERP→espelho→marts→Cube→UI: tabelas, ETLs, views, consumidores |
| [DOMAIN_RULES.md](DOMAIN_RULES.md) | Regras de domínio NELO (reparações, medianas, fases, operador ativo, factor M.O., termos) |
| [DESIGN_SKILL_PROPOSAL.md](DESIGN_SKILL_PROPOSAL.md) | Proposta de skill de design/UX para o frontend |
| [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md) | Plano detalhado de stock mínimo, ruturas, materiais por OF e reparações no plano |
| [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md) | Auditoria detalhada dos 51 cubes / 139 measures / pipeline ask-cube |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Plano de implementação faseado (10 fases) |
| [TEST_PLAN.md](TEST_PLAN.md) | Plano de testes com cenários reais (entidades reais da BD, pré-condições por SELECT) |

---

## 1. Resumo executivo

O nelinho tem o esqueleto certo — espelho ERP vivo (sync 5-min, `of_fp`=972.519 linhas,
`movimento`=2.544.418), zero mocks no frontend, robô de planeamento a gravar DRAFTs de 8.059 ops —
mas **quatro sistemas centrais estão a falhar em silêncio**:

1. **O plano de produção live está 32× pior do que devia.** Desde 2026-06-10 o solver CP-SAT
   (makespan ~690h) é **vetado em todos os replans** pelo guardrail `idle_ratio` (+5pp) e o plano
   servido regrediu para greedy puro com **makespan 22.297h (~2,5 anos)**. A rejeição não é
   persistida em lado nenhum — só aparece em `_arq.err`, que é truncado a cada arranque.
2. **18 dos 51 cubes do Cube apontam para views inexistentes** — 51 das 139 measures morrem em
   query-time (provado live, HTTP 400). O copiloto LLM e a tab KPIs operam sobre um catálogo 35% morto.
3. **A previsão de ruturas de material é 100% inoperante por três camadas independentes:**
   `supply_rop_configs`=0 (shortage-risks devolve `[]` para sempre), `min_stock_qty`=0 em
   **14.110/14.110** materiais (o ERP tem `P_STOCKMIN`>0 em 1.110), lead time placeholder 7d em
   todos, e a única UI (página Materiais) foi **apagada** no commit `2def464`.
4. **A camada ML está congelada desde 2026-05-30** — os 6 retrain jobs falham por construção
   (`TypeError` no arranque de cada job) e o modelo `quality_risk` ativo tem validação degenerada
   (auc=null, ap=0.0).

Transversal a tudo: **203 commits DRAFT vs 3 LIVE** (último LIVE 2026-06-02) — sem aprovação
humana, o loop plan-vs-actual, a calibração e a expiração de overrides nunca acontecem. A higiene
de dados honestos (invariante #8) está globalmente cumprida; as exceções (€12/h hardcoded,
`transport_date` fabricada com fallback `OF_DATA`, pesos inventados no ExplanationEngine) estão
listadas na secção 5. **Durante a auditoria nenhum código foi alterado** (secção 10).

## 2. Metodologia

- **44 agentes** em duas vagas: **9 áreas** (frontend, backend-api, bd-real, cpsat-planeamento,
  regras-config, stock-mrp, kpi-cube-llm, ux-gantt, termos-domínio) + **5 lacunas** identificadas
  pelo crítico e fechadas em segunda vaga (plano de testes, camada ML, verificação adversarial do
  achado CP-SAT, vertical ponta-a-ponta por barco real, profit/€).
- **BD real, estritamente read-only:** `docker exec prodplan-pg-wsl psql` com `SELECT` apenas;
  contagens, viewdefs e amostras citadas datam de 2026-06-11.
- **Verificação adversarial:** cada achado de severidade alta foi re-verificado por um agente
  independente com contexto fresco (marcas `VERIF [REAL]` na matéria-prima). O único achado
  `[critico]` de planeamento foi **re-provado por 4 fontes** (log `_arq.err`, BD, código do gate,
  timeline git) porque a primeira vaga não tinha evidência persistida.
- **Classificação usada em todo o documento:** `confirmado-no-código` / `confirmado-na-BD` /
  `HIPÓTESE` / pergunta ao dono.
- **Inconsistências detetadas entre agentes (resolvidas):**
  - `ml_model_artifact`: um agente reportou 0, a re-verificação encontrou **4** (duration v1/v2 +
    quality_risk v1/v2, criados 2026-05-30) — o valor correto é 4; a conclusão (ML congelado)
    mantém-se.
  - Backend :8001 estava **up** para o agente backend-api (sync às 10:40) e **down** para o agente
    stock-mrp — as verificações live de stock foram substituídas por código+BD.
  - A "contradição" das flags `use_backwards_scheduling/use_hungarian_pair_assignment/use_cpsat_lrho=true`
    nos commits dissolveu-se: são despejo de defaults do dataclass `CPOConfig`
    (`engine.py:581-590`) que **nenhum código lê** — flags=true não implica caminho executado.
  - Para 2026-06-10 a prova do veto CP-SAT é **inferência forte da BD** (não log direto): o
    `serve_demo.ps1:97-98` trunca `_arq.err` a cada arranque.

## 3. Problemas CRÍTICOS

### 3.1 CP-SAT vetado pelo gate `idle_ratio` — plano live regrediu para ~2,5 anos, rejeição não persistida

**Estado: confirmado (código + BD + log live).** O guardrail soft do axioma-7 veta sistematicamente
o candidato CP-SAT por **~0,25pp** de idle acima da tolerância, devolvendo a produção ao greedy:

- **Log vivo:** `_arq.err:2326/5961/8300` (2026-06-11 09:48/10:55/11:40): «CP-SAT global REJEITADO
  pelo gate axioma-7: 1 violações: idle_ratio(idle_ratio=0.6805 > baseline=0.6280 + 0.05)».
- **Gate:** `src/plan/cpo/engine.py:160-204` exige **zero** violações nas 9 dimensões;
  tolerância +5pp absoluto em `src/plan/cpo/safety_net.py:83` (desenhada no Q.54.G para ruído da GA,
  aplicada tal-e-qual ao CP-SAT).
- **BD:** último commit com `engine=cpsat_global` é 2026-06-10 16:37 (makespan **689.95h** em
  commit `660752e1`); todos os DRAFTs desde então são «Scheduled (1 generations)» com
  `kpis.makespan_hours=22297.21` e tardiness total 15,6M h. `cpo.use_cpsat_global=true` continua
  ativo em `core.tenant_configuration`.
- **Comparação injusta:** o candidato CP-SAT **exclui** reparações (`cpsat_global.py:72`,
  `REPAIR_PHASE_IDS={14,76,77}`) mas o baseline greedy **inclui-as** (`engine.py:347-361`) — o
  baseline ganha busy extra e idle_ratio artificialmente mais baixo (`decoder_kpis.py:131-148`).
- **Rejeição invisível por construção:** `engine.py:299` grava `cpsat_gate` no result do
  *candidato*; em rejeição `engine.py:300-305` devolve `None` e descarta tudo — o commit GA não leva
  `engine` nem `cpsat_gate` (só 1 commit em toda a tabela tem a chave). Exceções são engolidas em
  `engine.py:293-295` (`except Exception → return None`). Auditar o veto pela BD é impossível.
- **Agravante:** com o CP-SAT vetado, o «fallback GA» é greedy puro — 1 geração em 300s para 8.059
  ops (`generations_run=1`, `baseline_fitness=best_fitness=0.53`).

**Decisão do Luis (2026-06-11), a implementar:** gate com tolerância própria para o CP-SAT +
baseline recalculado sobre o **mesmo op-set** (sem reparações); guardrails *soft* isentos quando o
makespan melhora >50%; axiomas *hard* intocáveis; tudo configurável por tenant. Ver
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

### 3.2 18/51 cubes mortos — 51/139 measures morrem em query-time

**Estado: confirmado live (Cube `/load` → HTTP 400).** Exemplo real:
`{"error":"Error: relation \"marts.v_workforce_colaboradores_mes\" does not exist"}`.
Cross-check `sql_table` × (`pg_views` ∪ `pg_matviews` ∪ `pg_tables`) dá exatamente 18 cubes órfãos:
ambiental×5, comercial_facturacao_agente, consumo_by_of, logistica_docs/transportes,
moldes_top_uso, operadores_horas, planeamento_reagendamentos, plataforma_copilot×3,
producao_throughput_modelo, workforce×2. **Causa raiz:** as marts são criadas por **48 scripts
manuais** `scripts/setup_marts_*.py`; o Alembic só cria o schema (`alembic/versions/063_q93_a_marts_schema.py`)
e o `bootstrap_dev_full.py` não corre os scripts. Agravantes no mesmo pipeline: as 2 measures
workforce do `MEASURE_REGISTRY` usam nomes de 3 segmentos que não existem no Cube
(`measure_contract.py:2291/2318` vs `/meta`), e 9 measures do YAML não estão no registry.
Detalhe completo em [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md).

### 3.3 Previsão de ruturas de material 100% inoperante

**Estado: confirmado-na-BD + código.** Três falhas independentes, qualquer uma fatal:

| # | Falha | Evidência |
|---|---|---|
| 1 | `/v1/factory-map/shortage-risks` devolve `[]` para sempre | `risk_flags.py:98-121` parte de `ROPConfig`; `supply.supply_rop_configs`=**0**. O `ShortageRiskPanel.tsx:32` esconde-se com lista vazia → painel nunca visto |
| 2 | ShortageDetector horário nunca criou um alerta | `min_stock_qty=0` em **14.110/14.110** materiais — o ETL hardcoda `Decimal("0")` (`src/adapters/nelo/etl/material_master.py:56`) apesar de o ERP ter `P_STOCKMIN>0` em **1.110** produtos; `material_service.py:221` nunca dispara; `copilot_alerts LIKE '%MATERIAL%'`=0 |
| 3 | Lead times placeholder | `lead_time_days=7` em 14.110/14.110 (hardcode `material_master.py:55`); ERP tem `E_PRAZOENTREGA`≠0 em 114 entidades e `MOVIMENTO_FORNECEDOR.MOVFOR_ETA` (não espelhada) |

E a única UI (página Materiais, com mínimos/entregas/stockout) foi **apagada** no commit `2def464`
(«lean A1»; rota `/materiais` não existe em `App.tsx:91-110`). O mirror de encomendas a fornecedor
cobre ~2% (138 vs 5.987 movimentos tipo-9/12m) com ETA fictícia +30d (`purchase_orders.py:101`).
**Decisão do Luis:** importar `P_STOCKMIN` + override local; lead times de `E_PRAZOENTREGA`.
Plano completo em [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md).

### 3.4 ML congelado desde 2026-05-30 — retrain partido por construção

**Estado: confirmado-no-código + BD.** Existem 4 artefactos (`ml_model_artifact`=4: duration v1/v2,
quality_risk v1/v2), todos criados pelo seed one-shot `scripts/train_ml_models.py` a 2026-05-30.
Desde então **nunca houve retreino** porque:

- `src/ml/jobs/scheduling.py:98` constrói `SemanticQueriesInMemory()` **sem o argumento `engine`
  obrigatório** (`semantic/__init__.py:51`) → `TypeError` → `semantic=None` →
  `EmptyDatasetError` (`jobs/base.py:147`) em duration/quality_risk/otd_risk, todos os dias.
- `DriftDetectionJob`: `scheduling.py:135-141` chama `job.run(...)` com kwargs que a assinatura
  (`drift.py:220`) não aceita → `TypeError` todos os domingos; e mesmo sem isso o corpo é scaffold
  confesso (`drift.py:234-251`) — `ml.drift_event`=0 garantido.
- `sequence_mining`/`throughput_forecast` treinam e **deitam fora** o modelo (sem `registry.save`;
  Prophet nem está instalado no venv).
- Os modelos ativos são fracos: duration WMAPE=0.85 treinado nos 60.000 registos **mais antigos**
  (`training_data.py:113-114`, `ORDER BY data_inicio LIMIT` ASC de 408k) e o CPO vivo nem o usa;
  quality_risk com auc=null/ap=0.0 (labels sintéticos + split temporal degenerado,
  `training_data.py:269-278` + `quality_risk.py:89-105`).
- Training-serving skew: o risk-preview lê `factory_curated.order_phase` (**0 linhas**) →
  `phase_error_rate=0` sempre → QualityRiskBadge praticamente nunca acende
  (`defect_risk_service.py:124-143`).

## 4. Problemas de DADOS

| Problema | Evidência | Estado |
|---|---|---|
| **203 DRAFT vs 3 LIVE** — último LIVE 2026-06-02; `plan_execution_observed`=0; loop plan-vs-actual e calibração nunca alimentados | `capture_plan_execution.py:207-217` só lê `status='LIVE'`; `plan_schedule_commits` na BD | confirmado-na-BD |
| ETLs `phase_history` e `worker_assignment` falham **permanentemente** (9/9 error) — consultam `dbo.FasesOf`/`dbo.WorkerAssignment`, nomes do fake-ERP que não existem no ERP NELO | `src/adapters/nelo/services.py:828/863`; `core.etl_run` erro 42S02; destinos a 0; **nenhum leitor de `etl_run.status='error'` alarma** | confirmado |
| `rework_entry.mold_id` 100% NULL em **5.908** entradas → mart `v_rework_por_molde_mes` devolve 0 | query live; viewdef filtra `mold_id IS NOT NULL` | confirmado-na-BD |
| `transport_date` fabricada: fallback `OF_DATA` (data de criação!) dá «data de expedição» a 100% das ordens (**9.607** production_orders) | `scripts/q131_setup_production_orders_mirror.py:54-57` (COALESCE … OF_DATA) — roça o invariante #8 | confirmado |
| `production_orders.completed_date` NULL em 100% (todas IN_PROGRESS) → modelo OTD-risk nunca treinável | BD; `training_data.py:374-392` | confirmado-na-BD |
| Reparações invisíveis na expedição: **74 das 76** OFs em reparação têm `OF_DATAFIM` preenchido (da produção original) e ficam fora de `plan.production_orders` | filtro `WHERE NULLIF(OF_DATAFIM,'') IS NULL` em `q131_setup_production_orders_mirror.py:61` | confirmado |
| Camiões com assignments obsoletos nunca limpos: SHP-2026-06-19 tem 50 assignments mas só 5 ordens ainda são desse dia; barco do próprio dia (OF 902252) fica de fora | `transport_batch_service.py:256-261` («nunca reatribui», não remove stale) | confirmado-na-BD |
| `factory_curated.*` 100% vazia (10 tabelas a 0) — «mundo paralelo» nunca ingerido; routers `/v1/factory/*` e o serving do defect-risk leem daqui | `semantic.py`, `quality.py`, `defect_risk_service.py:124-143` | confirmado-na-BD |
| Metade do schema `supply` a zero: `supply_rop_configs`=0, forecasts=0, in_transit=0, reconciliation=0; ledger só tem **14 dias** (lê ERP live limit-5000 em vez do espelho de 24 meses) | `inventory_ledger.py:116`; `factory_raw.movimento`=2.544.418 não usado | confirmado |
| HR 6/8 tabelas a zero; MRP morto (`material_requirements`=0, não lê `core.bom_items`=86.438); `plan.production_schedules`=0 (endpoint zombie) | `productivity.py:48-60`, `mrp_service.py:101-102`, `schedule.py:57-110` | confirmado-na-BD |
| Configuração manual com adoção zero: `yaml_policy_rule`=0, `phase_config`=0, `plan_exclusion`=0, `order_boost/boat_boost`=0, `preference_rule`=0, `phase_transition_gap`=0 (cura vive do seed em código), `daily_revenue_target`=0 (meta €30-35K nunca semeada) | queries live; `state.py:33` NELO_CURING_GAPS_SEED | confirmado-na-BD |
| CoeficienteX: espelho tem 22.002 linhas com `PRODF_COEFICIENTE_X`>0 mas `profit.phase_bonus_payout`=0 — não há ETL, só endpoint REST nunca chamado | `api/bonus_payouts.py:55-63` | confirmado |
| Cadeia COGS→margem nunca executada: `cost_calculations`=0, `order_revenue`=0, `overhead_rates`=0 — apesar de BOM (86.438) e `labor_rates` (4.244, média 5,41€/h) reais | `cost_service.py:175-217` | confirmado-na-BD |
| `factory_raw.apontamento_trabalho` definida no mirror mas inexistente na BD — horas reais de M.O. indisponíveis; ETL time_mining stale 106,8h | `scripts/q75_setup_raw_mirror.py:118` | confirmado |
| Espelho parcial por construção: `of_fp`=972.519 de ~2,6M; `movimento`=2.544.418 de ~12,4M (janela 2 anos + keep-open) — análises >2 anos ficam fora | `q75_setup_raw_mirror.py:101-106` | confirmado |
| Duas definições de «OFs em curso» visíveis: Cube 8.510 (`FP_SEQUENCIA<30`) vs critério NELO **1.145** (`v_of_em_producao`) — números 7× diferentes com o mesmo nome | `producao_ofs_em_curso.yml` vs viewdef | confirmado-na-BD |
| 93/105 `decision_runs` são ADOPT_PLAN REJECTED (~89%) — provável auto-expire Q.161, mecanismo não confirmado | query live | HIPÓTESE |
| `boat_potential`=0 com o job a correr há meses (irmãos `boat_phase_score`=68.645 e `boat_complexity`=1.604 funcionam) | `core.py:514-523` | HIPÓTESE (causa) |
| Histórico copiloto/DQA/reports a zero: `copilot_conversation`=0, feedback=0, `trust_index_snapshots`=0, `report_run`=0; `copilot_request_log` nem existe como tabela | queries live | confirmado-na-BD |
| Tabela `MOVIMENTO_TIPO` (15 valores) não espelhada — semântica TPMOV vive só em `routes/_GLOSSARIO_BURACOS.md:14-31` (1=Entrada, 2=Saída, 4=Reserva, 11=consumo p/ OF, 12=pedidos internos) | confirmado em docs ERP; tipos 7/8/14 por confirmar | parcialmente confirmado |
| Anchors numéricos obsoletos nos YAML do Cube enviesam o LLM (ex.: «4.233 OFs em curso» vs 8.510 live; moldes 91 vs 510) | `producao_ofs_em_curso.yml:1810`, `moldes.yml:1246` | confirmado |

## 5. Problemas de LÓGICA

| Problema | Evidência | Estado |
|---|---|---|
| **Backwards scheduling morto** — nenhum código ativa `schedule_direction='backward'`; due dates só entram via tardiness | `decoder.py:132`; config `scheduler.direction=backward` (`default_configs.py:106`) lida por ninguém; crossover/mutate nunca tocam o campo | confirmado |
| **Boosts/prioridade de cliente não influenciam o plano** — `boost_inputs` recolhidos PÓS-solve, só badge | `scheduler_run.py:636-644`; `engine.py:355/440` chamam `decode` sem boost_inputs | confirmado |
| **Truck-consolidation é código morto** — config seeded 2.0, default do fitness 0.0, função só chamada em testes; **não existe nenhuma ligação plano→camião** | `fitness.py:100`, `transport_batch_service.py:322` (caller único: `tests/plan/test_sprint_p.py`) | confirmado |
| Override manual fantasma («op 110532::77 de 77 para 77», resíduo do E2E Q.172.C) re-aplicado a cada replan → pares de commits DRAFT de 8k ops; só um commit LIVE fecha a janela e nunca há LIVE | `commits.py:404-409`, `manual_reorder.py:558`, `worker.py:144-147`; 6 pares <3s a 2026-06-11 | confirmado |
| Motor /regras (Q.17) duplamente inerte: 0 regras **e** só 1 dos 12 eventos do DSL é emitido (`SCHEDULE_PROPOSE`, `scheduler_run.py:597`) — regras sobre os outros 11 eventos nunca disparariam | grep `on_event(` em src/ | confirmado |
| 84/184 chaves de config seeded mortas; categoria `alertas.*` inteira ignorada — o motor de alertas usa constantes hardcoded (`DELIVERY_RISK_WINDOW_DAYS`) | `agent_docs/config_keys_audit.md`; `copilot/alerts/engine.py:254` | confirmado |
| RBAC: router real `/v1/config` vs matriz `/v1/core/config` → mutações de config **fora do middleware**; `/api/copilot` inteiro fora da matriz (todas as 38 entradas são `/v1/*`); fall-through fail-open; entrada `/v1/operador` sem router | `rbac.py:202/233-234`, `tenant_config.py:34`, `middleware.py:154-158`; teste anula o gate (`test_q115_b_config_endpoints.py:135-142`) | confirmado |
| Gate de materiais do CTP é proxy: verifica stock do produto **acabado**, não explode a BOM (docstring promete o contrário); sem dados → «não bloqueia» | `ctp_service.py:176-194` | confirmado |
| `€12,00/h` hardcoded no margin_preview com `core.labor_rates` reais (4.244 linhas) disponíveis; +1h inventada por operação como último recurso → margem prevista sempre negativa | `margin_preview.py:34-36/91/242` | confirmado |
| Números autorais no backend (invariante #8): pesos 55%/25%/20% e impactos «+5%» no ExplanationEngine (`explanation_engine.py:273-289`, órfão+advisory); €400/4h fabricados em `erro_tree.py:518-526`; proxy 2.350€/barco no backlog (`dashboard_metrics_service.py:40`); telemetria fabricada `core_elapsed/4` (`greedy_pipeline.py:169`) | file:line citados | confirmado |
| `otd_risk` re-tenta treinar a **cada visita** ao /overall — scan de 200k linhas de `of_fp` antes de descobrir 0 ordens treináveis | `otd_risk_service.py:97`, `training_data.py:374-392` | confirmado |
| Fila inter-fase (mediana Q.160) não modelada no caminho CP-SAT — assimetria estrutural com o greedy no gate (pode ser one-piece-flow intencional, não documentado) | `cpsat_scheduler.py:132-158` vs `decoder_resources.py:130-142` | confirmado (intenção: pergunta) |
| Moldes multi-poço não first-class no CP-SAT (cap = nº moldes, `pocket_count` ignorado; post-pass serializa 1 barco/molde) — conservador, perde capacidade | `cpsat_scheduler.py:215-224`, `cpsat_postpass.py:160-179` | confirmado |
| Horizonte fixo 150 dias 24/7 no CP-SAT — se a carga exceder, INFEASIBLE e cai silenciosamente no greedy; `cpsat_lrho` morto com flag ligada na BD | `cpsat_scheduler.py:48`, `cpsat_lrho.py` | confirmado |
| Capacidade por fase é proxy auto-referencial: p95 da concorrência histórica em `of_fp` (congestão histórica vira «capacidade») | `phase_workcenters.py:79` | confirmado |
| Agregações Cube duvidosas: `type:sum` sobre COUNT DISTINCT pré-computado (`comercial_arpu.yml:397-401`), média-de-médias não ponderada na família p50/avg; dupla contagem delegada à disciplina do LLM | YAMLs citados; `can_sum_measures` só compara unidades | confirmado |
| Endpoints KPIs/Cube do chat são todos `*-dev` → **404 em production**; o chat cai silenciosamente para `/ask` e o caminho Cube desaparece | `headers.py:313-326`, `ask_cube.py:254/437/509/567`, `copilotApi.ts:97-99` | confirmado |
| Dedupe realizado→plano por `(order_id, phase_id)` esconde ops planeadas de fases repetíveis (`FP_PODE_REPETIR=true`) | `OverallPage.tsx:443-448` | confirmado (impacto não medido) |
| Jobs cron in-process sem catch-up nem jobstore persistente — máquina desligada à hora do job = dia perdido (consistente com `plan_execution_observed`=0) | `scheduling/core.py:122` | HIPÓTESE (uptime real não confirmado) |
| Divergência reparações vs ERP canónico: `of_EmReparacao`={76,77}+colagem(53); nelinho usa {14,76,77} sem a 53 — deliberado? | `mar_kayaks_procedures_analysis.md:49` vs `state.py:113` | HIPÓTESE |
| Hungarian pair-assignment morto (0 call-sites) mas `spelke_axioms.md:51` cita-o como enforcer do axioma 4 — doc desatualizada | `workforce.py:72` | confirmado |
| Loop feedback→prompt do copiloto não existe: `copilot_user_feedback` é write-only (0 rows, nenhum leitor); QLoRA é código morto (unsloth ausente, adapter config write-only) | `suggestions.py:64`, `qlora_trainer.py:9-12` | confirmado |

## 6. Problemas VISUAIS / UX

| Problema | Evidência | Estado |
|---|---|---|
| **/overall não é Gantt:** grelha lane×slot com `spanSlots` fixo=1 — duração/end nunca desenhados, sem dependências; 2 componentes GanttChart órfãos no bundle | `PorFaseView.tsx:228-233`, `Timeline.tsx:92-105`, `components/dark/GanttChart.tsx` (0 usos) | confirmado |
| Clicar num operador (vista Por Pessoa) → **422**: lanes usam `employee_code` («20365») mas `/v1/entity/operador/{id}` exige UUID | `PorPessoaView.tsx:206-208`, `entity_summary.py:1191-1193` | confirmado |
| ModeloSheet aberto do /overall recebe `OF_P_ID` numérico mas o endpoint indexa por `product_name` → tabs encomendas/produção **sempre vazias** | `cpo_commit_orders.py:340-343`, `entity_summary.py:626-646` | confirmado |
| Filtros: dos 12 pedidos pelo dono só **datas** está completo; setor/pessoa-expedição/modelo/gama-drop/materiais/prioridade/estado **não existem**; único filtro é texto-livre que nem inclui o modelo | `OverallPage.tsx:484-496` | confirmado |
| Botão de ajuda «?» (pedido explícito, Q.56) morto em **4 das 5 páginas** — chaves `PAGE_HELP` são rotas antigas (`planeamento`/`copilot` vs `overall`/`llm`) | `pageHelp.ts:14-34/57-61` | confirmado |
| Performance: payload do plano **2,3 MB** (8.059 ops) re-fetched a cada 30s sem GZip/ETag; 985 lanes sem virtualização nem headers sticky | `OverallPage.tsx:160-169`, `TimelineLanes.tsx:86-123` | confirmado |
| «Ver plano» das decisões passa `?commit_sha=` que o /overall **ignora** (mostra sempre o último plano) | `DecisionHubActions.tsx:78` vs `OverallPage.tsx:151/158` | confirmado |
| Badges mortos: ★ afinidade nunca acende (UUID vs employee_code, `api_affinities.py:111` vs `PorPessoaView.tsx:184-196`); ⚡ boost nunca renderiza (`effective_boost` nunca mapeado, `OpCard.tsx:75`) | file:line | confirmado |
| «Filtrar por fase» no label da lane engolido pelo `Clickable` (stopPropagation) — nunca dispara | `PorFaseView.tsx:191-200`, `Clickable.tsx:34-37` | confirmado |
| Escalas semana/mês só leitura cega (CountBadge sem drill-down nem drag); vista Por Expedição com drag-drop inativo e ignora a escala | `CountBadge.tsx:11-28`, `PorExpedicaoView.tsx:5-7/109` | confirmado |
| FaseSheet sem aba KPIs; `fila_mediana_h` que o backend devolve (Q.160) nunca é mostrada | `FaseSheet.tsx:31-36`, `entityApi.ts:117-124` | confirmado |
| SpofRiskPanel chama endpoint **apagado** no saneamento — painel nunca aparece, mas o RiskStrip anuncia «SPOF»; RiskStrip monta 4 painéis colapsados = 4 fetches invisíveis | `SpofRiskPanel.tsx:25`, `RiskStrip.tsx:40-51` | confirmado |
| Pesquisa global: hits de barco/molde/erro navegam para /overall **sem contexto** (id descartado) | `SearchResultsPage.tsx:57-66` | confirmado |
| Capacidade do camião inconsistente na mesma página: 50 lugares (header/CTP) vs 26 («moda real», ProntosTab) | `ExpedicaoPage.tsx:67`, `ProntosTab.tsx:20` | confirmado |
| Tablet do operador: mapeamento problema→error_code semanticamente trocado («Falta peça»→COLAGEM_FAIL, «Erro molde»→DIMENSION_OFF) — RCA contaminado | `operadorTabletBits.tsx:13-17` | HIPÓTESE (intenção) |
| Cenários de crise com €/dias/cascatas hand-authored (€4.500 Fed. Francesa, barco #4274) — único bloco autoral do frontend, rotulado «cenário de referência» | `crisisScenarios.ts:124-150` | confirmado |
| Miudezas: tabs da Expedição fora do URL (refresh perde aba); sidebar engole erros (backend down = «0 pendentes»); histórico de decisões corta a 100/105 sem paginação; inputs claros vs escuros inconsistentes entre sheets; lane Por Barco mostra modelo como número cru; StatusBadge em inglês; query keys inline fora das factories (invalidação cruzada falha); `request<any>` em APIs; cluster órfão palantir (8 componentes + 8 hooks) | file:line nos extratos por área | confirmado |

## 7. Funcionalidades INEXISTENTES que têm de ser criadas

1. **Materiais restantes por OF** — não existe em lado nenhum do produto. A conta é possível hoje:
   reservas abertas TPMOV=4 não satisfeitas vs consumos TPMOV=11 (verificado live: OF 902252 tem 78
   reservas/351,6 unid por satisfazer) e/ou explosão BOM (`produto_componente`=**111.339** ativas,
   com fase de consumo `COMP_FP_ID`).
2. **Consumo previsto do plano (CPO×BOM)** — peça central da previsão de ruturas: nenhum código
   cruza as operações planeadas (`ScheduleCommit`) com `core.bom_items` para projetar consumo
   futuro com timing por fase.
3. **Motor de ruturas real** — ROP configurado (recompute existe em `rop_calculator.py:66` mas
   nunca correu nem está agendado), mínimos importados do ERP, lead times reais, alertas que
   disparam, ledger alimentado do espelho local (24 meses) em vez do ERP live (14 dias).
4. **Ausências/férias/turnos de operadores** — zero modelo (grep `absence|ferias|vacation`
   = 0 funcionalidades); o CPO assume os **106** operadores ativos disponíveis todos os dias; o
   evento `WORKER_ABSENT` do DSL existe mas nunca é emitido.
5. **Capacidade por setor** — só existem estações paralelas por fase (`phase_config.num_stations_override`,
   0 rows) com fallback p95 auto-referencial; não há cap agregado «Laminagem ≤ N barcos/dia».
6. **Página Materiais** — apagada no commit `2def464`; endpoints from-bom/purchase-orders/min-stock
   continuam vivos no backend sem consumidor.
7. **Gantt verdadeiro** — barras com duração real, dependências, drill-down nas escalas
   semana/mês; os 2 componentes GanttChart existentes estão órfãos.
8. **Explicabilidade LLM no frontend** — o backend devolve a query Cube exata
   (measures/filtros/período, `ask_cube.py:212-218`) mas `copilotApi.ts:36-92` descarta-a; fórmula
   SQL e tabela de origem nunca chegam ao utilizador.

Adjacentes (decididos ou derivados): merge-back de reparações no mesmo plano /overall (decisão do
Luis), ligação plano→camião, limpeza automática de assignments obsoletos, UI de configuração de
tenant (removida no Q.172.E), UI de calendário (sábados/paragens) e de cura (PATCH existe, UI não).

## 8. Plano faseado (resumo)

Detalhe, dependências e critérios de aceitação em [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md);
cenários de validação em [TEST_PLAN.md](TEST_PLAN.md). As 10 fases, por ordem:

| Fase | Objetivo | Ancora |
|---|---|---|
| F1 | **Fontes de dados honestas**: `transport_date` sem fallback `OF_DATA`, ETLs mortos (`dbo.FasesOf`) desligados/repontados + alarme sobre `etl_run.status='error'`, importar `P_STOCKMIN` (1.110) + `E_PRAZOENTREGA`, POs do tipo 9, ledger do espelho (24 meses), `mold_id` do rework, €12/h e números autorais removidos | min_stock 0→real |
| F2 | **Regras configuráveis persistidas E usadas**: RBAC `/v1/config`, UI de configuração do planeador, `alertas.*` ligados ao motor, cura DB-first, `use_queue_time`+`REPAIR_PHASE_IDS` em config; primeiros eventos reais no motor /regras (Q.17) | 8 cadeias vazias ganham leitor |
| F3 | **Destrancar o CP-SAT** (decisões #1/#2): baseline no mesmo op-set, tolerância própria, isenção de guardrails soft quando makespan melhora >50%, hard axioms intocáveis, configurável por tenant; persistir `cpsat_gate` em TODOS os commits (aceite e rejeitado); **merge-back das reparações 14/76/77 no mesmo commit**; fim do override fantasma + logs com rotação | 22.297h → ~690h; 76 OFs deixam de desaparecer |
| F4 | **Vertical por barco**: materiais restantes por OF (TPMOV 4/11 vs BOM), reparações visíveis na expedição (74/76 fora do mirror), camiões largam assignments obsoletos, CTP com BOM real | OF 902252: 78 reservas visíveis |
| F5 | **Motor de ruturas** (decisão #4): recompute ROP agendado, consumo previsto plano×BOM (`COMP_FP_ID`), página Materiais nova, ShortageDetector vivo | shortage-risks ≠ `[]` |
| F6 | **Gantt operacional** (decisão #3): barras de duração, virtualização, 12 filtros (gama=tipo/disciplina TP_ID/P_TP_ID_DISCIPLINA, estado, prioridade, reparações com filtro/badge) | 12/12 filtros |
| F7 | **Subtabs ligadas à lógica real**: fixes de wiring (422 operador, ModeloSheet, `?commit_sha=`, badges ★/⚡, help «?», pesquisa global) | wiring W1-W12 fechado |
| F8 | **KPIs, Cube e LLM corretos**: criar as 18 marts em falta (bootstrap/Alembic), corrigir registry workforce + 9 measures, agregações, explicabilidade ponta-a-ponta (query Cube/fonte no FE), endpoints autenticados (fim dos `*-dev`), golden-SQL | 51/139 measures revivem |
| F9 | **Validação completa**: verify + pytest + e2e smokes + cenários reais (OF 902252/900895/17226, camião SHP-2026-06-19) | suite verde live |
| F10 | **Erros restantes**: ML descongelado (retrain DB-backed, quality_risk com labels reais OF_CHECKLIST, drift real ou remoção honesta), alarme LIVE-stale (203 DRAFT vs 3 LIVE), ETL CoeficienteX, limpeza + DELETION_LOG | retrain > 2026-05-30 |

## 9. PERGUNTAS BLOQUEANTES consolidadas

> **Já decidido pelo Luis (2026-06-11) — NÃO voltar a perguntar:** (1) gate CP-SAT com tolerância
> própria + baseline justo no mesmo op-set, soft isentos quando makespan melhora >50%, hard axioms
> intocáveis, configurável por tenant; (2) reparações 14/76/77 em merge-back no MESMO plano
> /overall, agendadas a seguir no mesmo commit, com filtro/badge próprio; (3) «gama/drop» = tipo/
> disciplina do produto (`produto_tipo.TP_ID` / `P_TP_ID_DISCIPLINA`); (4) stock mínimo importado
> de `P_STOCKMIN` + override local; lead times de `E_PRAZOENTREGA`.

### 9.1 Planeamento / CPO
1. Backward scheduling (PL14, `scheduler.direction=backward`) — religar, ou o objetivo tardiness
   do CP-SAT (Q.169.D) substitui-o de vez? Hoje está morto em produção.
2. A fila inter-fase mediana (Q.160) deve entrar no modelo CP-SAT, ou one-piece-flow (fila=
   desperdício) é a política para o plano otimizado?
3. Materiais/stock devem condicionar o arranque de fases no plano? Hoje não entram de todo no modelo.
4. As prioridades de cliente/boosts devem alterar a ORDEM do plano do robô? Hoje só badge pós-solve.
5. Override manual no-op («de 77 para 77», resíduo do E2E) — autorizas limpar + bloquear reorders
   no-op na origem? Que política de expiração de overrides quando não há LIVE?
6. As fases de reparação {14,76,77} são estáveis na NELO ou pode aparecer outra? (hoje hardcoded em
   `state.py:113`). E o canónico ERP inclui colagem (53) em `of_EmReparacao` — incluí-la ou foi
   deliberado excluir?
7. Qual o prazo de entrega real de uma reparação? A due derivada devolve a data da venda original
   (ex.: 2024) — existe promessa nova no ERP (ENCOMENDA/transp_datas)?
8. Barcos sem prazo nenhum (ex.: projeto ENALEIA) — FIFO como hoje, ou há data contratual em
   tabela nunca espelhada (ENCOMENDA)?

### 9.2 Processo e operação
9. Qual a cadência esperada de aprovação DRAFT→LIVE? Com 203 DRAFT vs 3 LIVE o loop plan-vs-actual
   nunca aprende — é gap de processo (hábito) ou de produto (falta UI/notificação)?
10. Quando o CP-SAT cai/é vetado, o robô deve gravar `cpo_meta.cpsat_gate`/`cpsat_error` no commit
    (falha ruidosa) ou apenas alarmar no painel? (Persistir a decisão parece obrigatório — confirmar formato.)
11. Logs do worker/backend: passar a append+rotate em vez do truncate do `Start-Process`?
12. Os 93 ADOPT_PLAN REJECTED em `shared.decision_runs` são auto-expire (Q.161) ou rejeições
    humanas? O mecanismo não foi confirmado.
13. Porta/topologia canónica de produção para o `dr-smoke.sh` (8000 vs 8001, Postgres docker vs nativo)?

### 9.3 Dados ERP / espelho
14. ETLs `phase_history` e `worker_assignment` (apontam a tabelas do fake-ERP): desligar
    definitivamente ou repontar para OF_FP/OFFP_EQ como nas afinidades (Q.150)?
15. `APONTAMENTO_TRABALHO` existe mesmo no ERP da NELO? O mirror define-a mas a tabela nunca foi
    criada nesta BD.
16. Rework-por-molde: o `mold_id` deve vir de OF_CHECKLIST/`OF_OF_ID_MLD` no ETL? Qual a regra de
    negócio para atribuir molde a um retrabalho? (5.908/5.908 NULL hoje.)
17. A camada `factory_curated` (10 tabelas a 0, morta desde Q.34) — popular (Fase B) ou remover o
    schema? Nota: o serving do defect-risk depende dela hoje.
18. O espelho de 2 anos (`of_fp` 972.519 de 2,6M; `movimento` 2.544.418 de 12,4M) chega para todos
    os consumidores (ML, calibração, afinidades) ou há análises que precisam do histórico completo?
19. Confirmar a semântica TPMOV com a NELO e espelhar `dbo.MOVIMENTO_TIPO`: 11=consumo p/ OF
    (glossário interno confirma), mas 2/12/4/1 carecem de confirmação oficial e 7/8/14 são desconhecidos.
20. Há acesso de leitura a `dbo.MOVIMENTO_FORNECEDOR` (ETA real + receções)? O placeholder
    eta=+30d e `qty_received=0` só se resolve com ela. E `E_PRAZOENTREGA` está em dias?

### 9.4 Stock, materiais e expedição
21. Materiais restantes por OF: fonte preferida — reservas abertas (TPMOV=4, com `MOV_FP_ID`) ou
    explosão BOM × consumos TPMOV=11? Divergem (BOM nível-1 inclui pseudo-componentes «Mão de Obra»).
22. A previsão de ruturas deve usar o consumo PREVISTO do plano CPO (BOM×operações, timing por
    `COMP_FP_ID`) ou chega EWMA/mediana do consumo histórico?
23. Reconstruir a página Materiais ou integrar ruturas/encomendas no /overall e /expedicao?
24. Existe conceito de reserva/kitting de material a uma OF a modelar, ou o consumo só se regista
    no movimento tipo 11?
25. Capacidade real do camião: 50 lugares (header/CTP/refresh hardcoded) ou 26 («moda real»)? Por
    camião/destino?
26. Assignments obsoletos: quando a `transport_date` muda, o camião antigo deve largar a ordem
    automaticamente? (Hoje nunca larga — 45/50 do camião de 19-06 já não são desse dia.)
27. «Pessoa de expedição» — é um responsável interno por embalar/carregar (fases 10/37)? Onde vive
    no ERP? (Só há transportadoras-empresa, 84; `TR_OPERADOR_CODIGO` tem 3% cobertura.)

### 9.5 KPIs / Cube / LLM
28. As 18 marts em falta são esperadas neste ambiente, ou esta É a BD de referência? Os
    `setup_marts_*.py` devem passar para bootstrap/Alembic — qual a política?
29. Definição canónica de «OFs em curso» para KPIs visíveis: Cube 8.510 (`FP_SEQUENCIA<30`) ou
    critério NELO 1.145 (`v_of_em_producao`)? Nomes distintos para os dois?
30. Faturação `comercial_facturacao.total` (€125,8M live) é base SEM IVA? «HIPÓTESE FORTE, pendente
    CFO» desde Q.102.
31. «Não Laminado» deve continuar a contar em `producao_pecas_laminadas.total`? (pendente decisão
    de negócio desde o YAML).
32. Measures workforce: corrigir o `MEASURE_REGISTRY` para os nomes do Cube
    (`workforce_colaboradores.*`) e reconstruir o índice, ou renomear os cubes YAML?
33. Produção vai correr com `environment!='production'` (como a demo) ou é preciso criar endpoints
    autenticados antes do go-live? (Tab KPIs + caminho Cube do chat são todos `*-dev` → 404.)
34. Loop feedback→prompt (Q.32/Q.111) é para reativar? O 👍/👎 grava numa tabela que ninguém lê e
    o `copilot_request_log` não existe.

### 9.6 ML
35. DurationModel: manter ligado ao CPO (o caminho vivo já usa medianas reais; o modelo ativo tem
    WMAPE 0.85), retreinar com dados recentes, ou remover da wiring?
36. quality_risk com labels sintéticos tem valor para a NELO, ou reconstruir com labels reais de
    retrabalho (OF_CHECKLIST RCA, Q.167)?
37. Retreino agendado: confirmar a correção (repontar os RetrainJobs para o caminho DB-backed
    `training_service`) antes de gastar uma campanha?
38. `sequence_mining`/`throughput_forecast`: religar a sério (persistir+endpoint+UI) ou apagar e
    registar no DELETION_LOG (invariante #8)?
39. Pipeline QLoRA (fine-tune do LLM local): visão a curto prazo ou declarar morto até haver
    GPU+unsloth no deployment da NELO?
40. OTD-risk: preencher `completed_date` no sync ERP (ex.: de `OF_DATAFIM`) para tornar o modelo
    treinável?

### 9.7 Regras, configuração e segurança
41. /regras (Q.17): qual o primeiro caso de uso real como regra YAML, e qual dos 11 eventos mortos
    ligar primeiro? (Ligar eventos é trabalho por evento.)
42. Recriar UI de configuração de tenant (scope, CP-SAT, caps do robô, buffers transporte —
    removida no Q.172.E) ou fica admin-via-API?
43. Das 84 chaves de config mortas (`alertas.*`, `dispatch.*`, `kpi_targets.*`…): apagar do seed ou
    ligar aos consumidores? Em particular os thresholds de alertas hardcoded.
44. `/api/copilot` fora da matriz RBAC em produção é aceitável (defesa só por tenant-header) ou
    ganha entrada própria? E remover a entrada morta `/v1/operador`?
45. Capacidade por setor: limite agregado por área («Laminagem ≤ N barcos/dia») ou chegam as
    estações paralelas por fase já existentes (e por preencher)?
46. Tempos por modelo/fase: confirmar o invariante atual (durações SÓ do histórico real) ou poder
    definir tempos-alvo? Mudar isto contraria um invariante Spelke.
47. Ausências/férias: vêm do ERP (existe lá tabela de ausências?) ou geridas no nelinho?
48. Calendário: precisa de UI para sábados de trabalho/paragens/horas extra, ou o gerado
    (seg-sex + feriados PT) chega?
49. HR (produtividade/alocações/payroll) e MRP: roadmap para ligar ao ERP, ou remover do menu/API
    à la DELETION_LOG?

### 9.8 UX / frontend
50. «Ver plano» de uma decisão deve abrir o commit específico no /overall (deep-link por
    `commit_sha`), ou é aceitável mostrar sempre o último plano saudável?
51. Filtro «setor» no planeamento: disciplina do produto (`P_TP_ID_DISCIPLINA`), secção física
    (grupo de fases), ou os sectores Q.140 (pessoa×sector)?
52. Filtro «prioridade» = boost 0-100 existente, prioridade do cliente, ou outra coisa?
53. Filtro «estado» = realizado/planeado/atrasado/em-risco?
54. Filtro «materiais» deve esconder/realçar barcos com falta de material — fonte é o
    shortage-risk (a reconstruir) ou outra?
55. Clicar num barco na grelha: ficha da ENCOMENDA (cartão atual) ou do MODELO (label da lane,
    hoje meio-vazio pelo id numérico)?
56. FaseSheet: que conteúdo na aba KPIs em falta — fila mediana (já no backend), durações p50,
    aderência por fase?
57. Pesquisa global: abrir ficha/sheet para barcos e moldes (como já faz para operadores)?
58. Painel SPOF: remover do frontend (endpoint apagado) ou reimplementar com dados reais?
59. Tablet do operador: que error_codes reais deve cada botão registar? «Falta peça»→COLAGEM_FAIL
    e «Erro molde»→DIMENSION_OFF parecem trocados.
60. Cenários de crise hand-authored (€4.500 Fed. Francesa…): manter como «cenário de referência»
    ou remover/recalcular com dados reais?
61. Meta OTD 95% no KPI da Expedição: meta oficial ou placeholder a passar para configuração?

### 9.9 € / profit
62. Oficializar a meta €30-35K/dia em `core.daily_revenue_target` agora? Valor exato e
    `effective_from`?
63. Custo/h para margem prevista de operações futuras: média de `core.labor_rates`, taxa do
    operador planeado, ou taxa por fase? (Hoje €12/h hardcoded.)
64. `PRODF_COEFICIENTE_X` (média 1,32) é o bónus € por unidade fase×produto, ou precisa de
    transformação (×quantidade, ×horas) antes de carregar `phase_bonus_payout`?
65. Proxy 2.350€/barco do backlog: mantém-se, ou passa a `P_PRECOVENDA` real
    (`profit.product_pricing`, 3.714 produtos)?
66. Família COGS/margem-por-barco/cost-ledger: criar job batch que corra
    `calculate_cogs_from_sources` sobre as OFs, ou declarar morta/remover (fora do menu de 5 páginas)?
67. Existe taxa oficial de overhead (€/h) para `core.overhead_rates`, ou fica 0 de propósito?
68. Defaults de scrap do COGS (recovery 50%, rework factor 10%, scrap 2%): base real da NELO ou
    derivar do histórico de retrabalho?

### 9.10 Termos de domínio
69. «deana» — confirmar que é «mediana» (percentile_cont 0.5)? Zero vestígios em código, BD e git.
70. Promover os termos só-em-código ao `agent_docs/domain_glossary.md` (REPAIR_PHASE_IDS, 7
    sectores, operador ativo=2 meses, fila mediana por fase, factor M.O. 1.065, markers terminais)?
    Ver [DOMAIN_RULES.md](DOMAIN_RULES.md).

## 10. Confirmação de não-alteração

**Durante a fase de auditoria (2026-06-11) NENHUM código, teste, configuração, migração ou dado foi
alterado.** Todo o acesso à BD foi `SELECT`-only (psql via docker, sem DML/DDL); toda a análise de
código foi por leitura (grep/read); os únicos artefactos produzidos são os 8 documentos listados no
índice, escritos na raiz do repo. As correções propostas vivem exclusivamente em
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) e aguardam decisão.
