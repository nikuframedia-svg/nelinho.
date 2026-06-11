# DOMAIN_RULES.md — Regras de negócio e glossário do nelinho

> **Auditoria multiagente 2026-06-11** (44 agentes, BD real read-only, verificação adversarial).
> Todas as contagens de BD são **snapshot de 2026-06-11** da `prodplan_one` local (espelho do ERP
> MAR-KAYAKS + tabelas nelinho).
>
> **Legenda de confiança** usada em todo o documento:
> - **[CÓDIGO]** — confirmado no código-fonte (file:line citado)
> - **[BD]** — confirmado por query à BD real
> - **[DOCS]** — confirmado em `agent_docs/` ou docs do ERP
> - **[HIPÓTESE]** — plausível mas não provado
> - **[PERGUNTA]** — precisa de resposta do dono (Luis)
>
> Docs irmãos: [AUDIT.md](AUDIT.md) · [DATA_FLOW_MAP.md](DATA_FLOW_MAP.md) ·
> [DESIGN_SKILL_PROPOSAL.md](DESIGN_SKILL_PROPOSAL.md) ·
> [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md) ·
> [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md) ·
> [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) · [TEST_PLAN.md](TEST_PLAN.md)

## Decisões do dono (2026-06-11) — normativas

Incorporadas neste documento como **decisões tomadas**, não como perguntas:

| # | Decisão | Efeito nas regras |
|---|---|---|
| 1 | **Gate CP-SAT**: tolerância própria + baseline justo — baseline recalculado sobre o MESMO op-set (sem reparações); guardrails soft isentos quando o makespan melhora >50%; hard axioms intocáveis; configurável por tenant | Ver [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) |
| 2 | **Reparações (fases 14/76/77)**: merge-back no MESMO plano /overall — CP-SAT planeia barcos, reparações agendadas a seguir **no mesmo commit**, com filtro/badge próprio | Altera a regra R2 abaixo (hoje fluxo separado) |
| 3 | **"Gama"/"drop"** = tipo/disciplina do produto (`produto_tipo.TP_ID` / `P_TP_ID_DISCIPLINA`) | Fecha os termos da secção 2 |
| 4 | **Stock mínimo**: importar `P_STOCKMIN` do ERP + override local no nelinho; lead times de `E_PRAZOENTREGA` | Ver [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md) |

---

## 1. Regras de negócio CONFIRMADAS

### R1 — Barco = PRODUTO_TIPO com raiz Kayak (TP_ID 1)

**[CÓDIGO][BD][DOCS]** O critério de "barco" é a árvore de tipos de produto: um produto é barco
se a raiz de `produto_tipo` for Kayak (`TP_ID=1`). Materializado na view recursiva
`factory_raw.v_of_is_boat`. Validado com **0 diferenças** contra o site de produção real
(`produto_Classes(1)` = 811 barcos, `agent_docs/mar_kayaks_procedures_analysis.md:42-43`).
NÃO usar `P_QTDDECK`/`P_QTDCASCO` (perde C1/Nacra).

> Gotcha de performance **[CÓDIGO]**: `v_of_is_boat` é recursiva — JOIN + ORDER BY DESC LIMIT dá
> timeout; o padrão correto é buscar os boat-ids primeiro e filtrar com `= ANY()` (Q.163).

### R2 — Reparações = fases {14, 76, 77}

**[CÓDIGO]** `REPAIR_PHASE_IDS = frozenset({"14","76","77"})` em `src/plan/cpo/state.py:113`
("A Reparar", "Reparação Verniz", "Reparação"). A fase **13 "Para reparar"** é
`FP_PRODUCAO=false` → NON_PRODUCTION, nunca planeada.

**[BD]** View `factory_raw.v_of_em_producao` define `is_reparacao = OF_FP_ID = ANY(ARRAY[14,76,77])`.
Live 2026-06-11: **76 OFs em reparação** (fase 14→32, fase 77→30, fase 76→14) vs 1.069 não-reparação.
`fases_producao` confirma FP_PRODUCAO=true e FP_SEQUENCIA=31 para as três.

**[DOCS]** Nuance ERP — a **fase 14 é DUAL** (`mar_kayaks_procedures_analysis.md:18-22,47-51`):
serve moldes (OFs 70000-79999, P_TP_ID=82, 23 live) E barcos (32 live). Em scope boats a
`v_of_is_boat` exclui os moldes, por isso incluir a 14 é correto.

**Comportamento no planeador [CÓDIGO]:**
- Prioridade 0 **hardcoded** no SQL de carga (`state_loaders.py:1132`).
- Rota de reparação = bypass: planeia SÓ a op aberta da fase 14/76/77 com duração mediana real;
  sem mediana → unplanned honesto (`routing_resolver.py:183-192`, `_repair_row`).
- O CP-SAT global **exclui-as** do solver (`src/plan/engines/cpsat_global.py:72`) — hoje é fluxo
  separado. **Decisão #2 do dono muda isto**: merge-back no mesmo commit /overall, com badge próprio.

**[PERGUNTA] Divergência vs canónico ERP**: a SP `of_EmReparacao` (barcos) = {76,77} **+ colagem (53)**;
`getMoldesAReparar` (moldes) = fase 14 (`mar_kayaks_procedures_analysis.md:49`). O nosso
`REPAIR_PHASE_IDS` não inclui a 53 — não está confirmado se foi decisão deliberada (a 53 é
colagem normal na maioria dos casos) ou omissão. **Confirmar com o dono** se barcos devolvidos
em fase 53 devem ser `is_reparacao`.

### R3 — "Em produção" = op aberta na fase atual (view `v_of_em_producao`)

**[BD][CÓDIGO]** Regra exata (Q.158): uma OF está "em produção" se tem operação aberta
(`OFFP_DATAFIM IS NULL`) na sua fase atual (`OF_FP_ID`) e a OF não está fechada
(`OF_DATAFIM IS NULL`). View única `factory_raw.v_of_em_producao` partilhada por scope do CPO,
display e watermark do robô. Live 2026-06-11: **1.145 OFs** (675 nova produção, 394 fila,
76 reparação). Bate com o alvo da NELO (verificado contra producao.nelo.eu na Q.158).

### R4 — Operador ativo = E_ACTIVO + atividade nos últimos 2 meses

**[BD][CÓDIGO]** View `factory_raw.v_active_operators` = `E_ACTIVO=true` AND
`OFFP_DATAINICIO >= now() - 60 days` → **106 operadores ativos** (Q.159). Fonte única para:
`/v1/core/employees?active_only`, `/v1/workforce/operators/summary` e o filtro do pool do CPO
(`state.py:548-568`, input-only com fallback não-vazio). Desativação manual =
`MasterDataTab.tsx:533` → `cancel_service.py:313` (status=TERMINATED, **permanente** — não é
ausência datada; ver secção 3, "disponibilidade").

### R5 — 7 sectores de fábrica (AREA_GROUPS)

**[CÓDIGO]** `src/workforce/levels.py:57-65`:
**Laminagem, Pintura, Acabamento, Montagem, Cura/Moldes, Estrutura, Transversal**.
Mapeamento fase→sector por substring no nome (`_FASE_SUBSTRING_TO_GROUP`, levels.py:67;
fallback Transversal). Servem níveis por (pessoa×sector) (Q.140) e UI — **não** existe
capacidade agregada por sector (ver secção 3).

### R6 — Fila inter-fase = mediana REAL por fase de destino (Q.160)

**[CÓDIGO]** `src/plan/cpo/state_loaders.py:486-511` (`_load_phase_queue_medians_db`):
`percentile_cont(0.5)` sobre gaps LAG em `factory_raw.of_fp`; exige n_obs≥5; descarta <0 e
>1 semana; **NUNCA média** (cauda assimétrica: mediana ~5,2h vs p90 ~69h).
Precedência: mediana da fase → mediana global → fallback 5,2h
(seed `planning.queue_time.median_h`, `default_configs.py:113-114`; `state.py:266,731-738`).
Exposta na UI como `FaseSummary.fila_mediana_h` (`entity_summary_schemas.py:118`).
Separação concetual: **fila = desperdício** (mediana, removível) vs **cura = física** (R8, fixa).
One-piece-flow simulável com `use_queue_time=False` — só em código, não configurável (secção 3).

### R7 — Durações vêm SEMPRE do histórico real (invariante Spelke)

**[CÓDIGO][DOCS]** Tempos de fase = histórico limpo de `FaseOf_Inicio→FaseOf_Fim`
(`factory_raw.of_fp` = **972.519 linhas**). Pipeline de limpeza
(`src/adapters/nelo/etl/time_mining.py:13,70-96`): zeros removidos → >P95 removidos →
**p50 = moda da amostra limpa** (`statistics.multimode`), fallback mediana dos não-zero.
Durações de rota do CPO = mediana real por fase; fases sem mediana são **saltadas**, nunca
fabricadas (`routing_resolver.py:181,270,314,338-343`).
`FasesStandardModelos` do ERP é **proibido** como fonte (até 25× errado,
`domain_glossary.md:47-57`). Override manual de duração é proibido **por desenho**
(`src/plan/models/phase_config.py:4-5`). Sentinelas `1900-01-01` anuladas na carga
(`state_loaders.py:1124-1125`).

### R8 — Cura/secagem = 16 transições químicas (NELO_CURING_GAPS_SEED)

**[CÓDIGO]** `src/plan/cpo/state.py:33` `NELO_CURING_GAPS_SEED` — 16 transições com gap mínimo
químico entre fases (química, **não filas**; não removível por otimização). Validação anti-drag
em `manual_reorder.py:223-245`; alias por phase_id Q.169.F (`state.py:636-640`).
**[BD]** Tabela editável `plan.phase_transition_gap` = **0 rows** → o seed é a única fonte viva.
A API PATCH `/v1/plan/phase-gaps` existe (`phase_gaps.py:161`) mas nenhum componente FE a usa
(secção 3).

### R9 — Factor de mão-de-obra 1.065 (ERP VARIAVEIS VAR_ID=2)

**[CÓDIGO][BD]** `src/profit/services/material_cost_service.py:39-44,151-157`
(`_ERP_LABOR_FACTOR_VAR_ID = 2`): o factor de correcção das mãos-de-obra (`@fInflacao` no ERP,
valor live `1.065`) aplica-se às linhas de mão-de-obra (P_TP_ID=90) e é lido **sempre** do
espelho `core.erp_variables` (VAR_ID=2), nunca de literal no código (Q.167.F).

### R10 — CoeficienteX é DINHEIRO (€), nunca tempo

**[CÓDIGO][DOCS]** Invariante #5 do CLAUDE.md + `domain_glossary.md:59-85`: CoeficienteX usa-se
em `src/profit/` e **NUNCA** em `src/plan/cpo/*`. Confundi-lo com tempo corrompe o fitness do
planeador.

### R11 — TPMOV: semântica dos tipos de movimento de stock

**[DOCS]** Fonte canónica: `routes/_GLOSSARIO_BURACOS.md:14-31` — cópia integral da tabela ERP
`MOVIMENTO_TIPO`, que **NÃO está espelhada** em `factory_raw` (0 tabelas `%tpmov%`; a única
parecida, `ent_mov_tipo`, é RH). Corroborado por `mar_kayaks_schema_discovery.md:4488-4492` e
pelas SPs (`mar_kayaks_procedures.md:9746-9752`: stock = Σtp1 − Σtp2; necessidades = tp4 + tp12).

| TPMOV | Significado | Volume no espelho (`factory_raw.movimento` = **2.544.418**) |
|---|---|---|
| 1 | Entrada | 112K |
| 2 | Saída | 568K |
| 4 | Reserva (criada na criação da OF, com `MOV_FP_ID` = fase de consumo) | 137K |
| 5 | Reparação | (residual) |
| 9 | Pedido a fornecedor | 12,7K |
| 11 | **Saída como componente = consumo de OF** | **1.468.924** |
| 12 | Pedidos internos | 232K |

Usos no código **[CÓDIGO]**: consumo=11 em `measure_contract.py:306` e
`boat_complexity_job.py:159-165` (kg tinta p/ ICB); tp9 em `etl/purchase_orders.py:9`.
"Materiais restantes por OF" (BOM ativa `produto_componente` = **111.339 linhas** × reservas
tp4 não satisfeitas vs consumos tp11) é computável mas **não existe como feature** — ver
[STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md).

### R12 — Camião: capacity 50 (CEO) vs moda real 26 barcos/viagem

**[CÓDIGO][DOCS]** `default_configs.py:360-369`: `truck.capacity=50` (baseline CEO) e
`truck.capacity_moda=26` (moda histórica real). O detetor de camião-completo usa a **moda**
(`transport_suggestions.py:48-51,105-111`); A/B framework moda26 vs ceiling50
(`ab_framework.py:11,92`); documentado em `domain_glossary.md:101-107`.
Os lotes `SHP-{date}` derivados das **9.607 production_orders** usam cap default 50
(`transport_batch_service.py:216-286`) — e nunca reatribuem nem limpam stale (ver
[STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md)).

### R13 — due_date = COALESCE de 3 colunas do ERP

**[CÓDIGO]** `src/plan/cpo/state_loaders.py:1138-1140`:
`COALESCE(NULLIF(OF_DATAENTREGA,''), NULLIF(OF_TR_DATA_PREVISTA,''), NULLIF(OF_PLANO_DATA_PREVISTA,''))`,
com sentinela 1900 anulada (`:1124-1125`); viaja como due do backward-scheduling (`:1227-1232`).
⚠️ **Inconsistência confirmada**: o espelho de `production_orders` usa OUTRA fórmula para
`transport_date` — `COALESCE(OF_TR_DATA_PREVISTA, OF_DATA)`
(`scripts/q131_setup_production_orders_mirror.py:54-57`), com fallback à data de **criação**
da OF → datas de transporte fabricadas no passado. Detalhe em
[DATA_FLOW_MAP.md](DATA_FLOW_MAP.md).

### R14 — Meta económica: €30-35K/dia

**[DOCS]** Vive só no cabeçalho do CLAUDE.md (~14,7 barcos/dia, meta €30-35K/dia). **Nunca foi
semeada** como config operacional — a categoria `kpi_targets.*` está nas 84 keys mortas
(secção 3). Hoje nenhuma página nem alerta compara contra esta meta.

### R15 — Números estruturais da fábrica

**[DOCS]** `agent_docs/domain_glossary.md`: 122 operadores (catálogo; **ativos = 106**, R4),
41 fases, 510 moldes, 61 padrões de routing, ~14,7 barcos/dia. Fases 1-77 no ERP
(`FP_SEQUENCIA` ordena; catálogo em `/phases/catalog`, Q.163).

---

## 2. Termos que NÃO existem no sistema

| Termo | Veredicto | Evidência | Resolução |
|---|---|---|---|
| **"deana"** | INEXISTENTE | grep -i a todo o repo → 0 ficheiros; `git log --all -S deana -i` → 0 commits; `information_schema` ILIKE '%deana%' → 0 | Quase de certeza é **"mediana"** (`percentile_cont(0.5)`, omnipresente — R6, R7). **[PERGUNTA]** confirmar com o dono o contexto onde apareceu |
| **"gama"** | INEXISTENTE como conceito | Únicos usos = "fora de gama" (range genérico) em `twin/api.py:241` e `twin/delta_applier.py:79`; 0 colunas/tabelas `%gama%` na BD; 0 hits no schema do ERP | **DECIDIDO (decisão #3)**: gama = **tipo/disciplina do produto** → `produto_tipo.TP_ID` / `P_TP_ID_DISCIPLINA` |
| **"drop"** | INEXISTENTE como conceito | Só SQL `DROP`, drag-drop UI (`OverallPage.tsx:6`, `ListaTab.tsx:235`) e CSS drop-shadow; 0 colunas na BD | **DECIDIDO (decisão #3)**: idem — tipo/disciplina do produto |
| **"pessoa de expedição"** | INEXISTENTE como entidade | O que há: **84 transportadoras-empresa** (`entidade.E_TRANSPORTADOR=true`: Lassen, Kuhne+Nagel, Cevalogistics…, mapeadas `is_carrier` em `adapters/nelo/models.py:116`); `TR_OPERADOR_CODIGO` com **3% de cobertura** ("buraco residual Q.82, não inventar", `measure_contract.py:843-845`); `plan.transport_batch` não tem coluna de responsável | **[PERGUNTA]** é um role interno (fases 10 Embalado / 37 Logística-Embalagem)? Modelar como responsável do `transport_batch`? |

Termos que **existem** e por vezes se confundem: **"mediana"** (R6/R7 — fila, durações, baselines
de custo, ~10 measures P50 no Cube) e **"moda"** (2 usos: p50 dos tempos de fase limpos em
`time_mining.py:70` e carga modal do camião = 26, R12).

---

## 3. Estado das regras configuráveis

Infraestrutura construída e bem ligada ao planeador, mas **quase toda vazia na BD**.

### 3.1 Mapa regra → edição → persistência → leitor → estado

| Regra | Onde se edita | Onde persiste | Quem lê | Estado |
|---|---|---|---|---|
| Regras YAML Q.17 (/regras) | `RegrasPage.tsx` (tab de /configuracoes) + wizard | `governance.yaml_policy_rule` = **0** | `RuleEngine` (`runtime.py:157`); único emissor real: `scheduler_run.py:597` | **MORTA** (0 regras + 11/12 eventos sem emissor) |
| Config de tenant (scope, CP-SAT, caps robô, buffers) | **SEM UI** (binding removido Q.172.E, `platformApi.ts:252-255`) — só API `/v1/config` ou SQL | `core.tenant_configuration` = 186 rows (43 keys `planning`; só 2 manuais: `planning.scope=boats_and_molds`, `cpo.use_cpsat_global=true`) | `_build_cpo_config` (`scheduler_run.py:191-270`), `state.py:591-630`, robô (`auto_cpo_replan_job.py:145-159`), fitness | **EXISTENTE sem UI** + gap RBAC (abaixo) |
| Override de fase (equipa/estações/whitelist) Q.135 | FaseSheet tab "Configuração" (`FaseSheet.tsx:315-384`) | `plan.phase_config` = **0** | `state.py:651,745-765,924-945` (interseção whitelist, team_size, estações) | **cadeia completa, VAZIA** |
| Níveis por sector (pessoa×sector) Q.140 | `EquipaNiveisTab.tsx:88` | `governance.preference_rule` = **0** (derivado on-the-fly de `offp_eq⋈of_fp` em uso) | `state.py:573-576` → `preference_score_for` (reordena pool, nunca alarga) | **cadeia completa, VAZIA** (só derivado vivo) |
| Melhores por fase Q.155 | `MelhoresPorFaseTab.tsx` | `governance.phase_preferred_operator` = **2** (fase 40) | bónus aditivo no `_pick_workers` (`state.py:585-588`) | **existente**, adoção mínima |
| Routing: sequência + fases flexíveis | editor PATCH `/sequence` + `/flexible` (`routing_template_admin.py:112,153`, RBAC ROUTING_EDIT aberto a todos os roles) | `plan.routing_template`=142 / `_phase`=1.433; `is_flexible=true` = **0** | `state_loaders.py:562-589` (+ fallback rota canónica Q.164) | rotas **existentes**; flexível = **cadeia completa, VAZIA** |
| Cura/secagem editável | API PATCH `/v1/plan/phase-gaps` (`phase_gaps.py:161`); `phaseGapsApi` existe (`governanceApi.ts:392-420`) mas **0 componentes .tsx** o importam | `plan.phase_transition_gap` = **0** → seed R8 é a fonte | `state.py:636-640` | **parcial (só-API)** |
| Calendário de fábrica | **nenhum write-path** (só GET `/v1/plan/dates/calendar`, `dates.py:57`) | `plan.factory_calendar_day` = 583 (gerado por `etl/calendar.py:99-165`: seg-sex + feriados PT; labels com mojibake) | `state.py:672-677` + CP-SAT (Q.166.C) | **parcial (só leitura)** — sem sábados de trabalho/paragens |
| Prioridade de cliente Q.115/116 | tab "Custos & Objectivos" (`ConfiguracoesPage.tsx:87-160`) | `core.client_priority` = **1** | `boost_service.py:20-51` → decoder reordena por `-effective_boost` | **existente**, adoção quase nula |
| Boost de encomenda/barco | `EncomendaSheet.tsx` + PATCH `/v1/plan/order-boost/{id}` (`order_writes.py:117`) | `plan.order_boost` = **0** / `plan.boat_boost` = **0** | idem boost_service; snapshot no commit (Q.168.C) | **cadeias completas, VAZIAS** |
| Excluir barco do plano Q.153.C1 | UI "tirar barco" no /overall | `plan.plan_exclusion` = **0** | `state.py:656-667` (em cada load) | **cadeia completa, VAZIA** |
| Bloqueios automáticos (pause_writes 423 / block 409) | dependem de regras YAML | `yaml_policy_rule` = 0 | `middleware_registry.py:161`; `scheduler_run.py:603-619` | **mortos por arrasto** (0 regras) |
| Stock mínimo / ROP | **nenhuma UI**; recompute só via POST manual `/rop-configs/recompute` (`routers/rop.py:135`), sem job agendado | `supply.supply_rop_configs` = **0**; `min_stock_qty=0` em **14.110 materiais** | `rop_calculator.py:66`; `safety_multiplier=1.0` multiplica zero → sem efeito | **EM-FALTA** → **decisão #4**: importar `P_STOCKMIN` do ERP (**>0 em 1.110 produtos**) + override local; lead times de `E_PRAZOENTREGA` (hoje placeholder 7d). Plano: [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md) |
| Disponibilidade de operadores (ausências/férias/turnos) | **inexistente** (desativar = TERMINATED permanente) | — (`hr.shift_schedules` = 0 rows, 0 consumidores) | CPO assume todos os ativos disponíveis todos os dias; evento `WORKER_ABSENT` do DSL nunca emitido | **EM-FALTA** (ausências históricas do ERP existem em `ent_mov` MET_MET_ID=2 como KPI read-only, Q.167.C — não alimentam o CPO) |
| Capacidade agregada por SECTOR | **inexistente** | — | só estações paralelas por fase (`num_stations_override`, fallback p95 `state.py:942-945`) | **EM-FALTA** — os 7 AREA_GROUPS são só níveis/UI |
| Tempos-alvo por modelo/fase | **proibido por desenho** | — | R7 (invariante Spelke) | **em-falta POR DESENHO** — mudar isto é decisão de produto contra invariante |
| `use_queue_time` (one-piece-flow) | só em código | `CPOConfig` default True (`engine.py:104`) | `engine.py:337` | **não-configurável** (nem tenant nem request) |
| Fases de reparação | hardcoded | `state.py:113` frozenset | R2 | **não-configurável** — fase nova exige deploy |
| Expedição (transporte.*) | sem UI (idem config tenant) | `truck.capacity=50`/`capacity_moda=26`/`buffer=2d` em config | fitness + transport_suggestions | **parcial**; categoria `dispatch.*` inteira **morta** |

### 3.2 As 8 cadeias completas (UI+API+tabela+leitor CPO) com 0 rows

`yaml_policy_rule`, `phase_config`, `plan_exclusion`, `order_boost`, `boat_boost`,
`preference_rule` (overrides), `phase_transition_gap`, `routing_template_phase.is_flexible`.
As cadeias **funcionam** (ex.: `workers_for` respeita whitelist, `state.py:754-765`) — o problema
é adoção zero, não código. Só `phase_preferred_operator` (2) e `client_priority` (1) foram tocadas.

### 3.3 Motor Q.17 (/regras) — duplamente inerte **[CÓDIGO][BD]**

1. **0 regras** em `governance.yaml_policy_rule` (e 0 em `yaml_policy_rule_revision` — nunca
   existiu regra alguma). A página /regras mostra vazio **honesto**, não está partida.
2. **1/12 eventos com emissor**: só `SCHEDULE_PROPOSE` (`scheduler_run.py:597`; block→409 em
   `:603-619`). Os outros 11 (worker_absent, quality_event_logged, kpi_threshold_crossed…)
   nunca são emitidos — uma regra criada sobre eles nunca dispararia.
3. Emissor fantasma quebrado: `drift.py:194` chama `GovernanceService.on_event` que **não existe**
   (AttributeError engolido em `drift.py:205`).
4. **4 mecanismos de regra distintos, só 1 com UI**: yaml_policy (0 regras), motor de alertas do
   copiloto (`copilot/alerts/engine.py:122-254` — escreveu as 6.328 `rule_firing` com thresholds
   **hardcoded**), `preference_rule` (learning) e `GovernanceService.on_event`.

### 3.4 Keys de configuração mortas e gaps de governação **[CÓDIGO][DOCS]**

- **84/184 keys seeded UNUSED** (`agent_docs/config_keys_audit.md`): `alertas.*`, `dispatch.*`,
  `kpi_targets.*`, `rbac.*`, `notifications.*`, `reports.*`, `ml.*`, `learning_rules.*`,
  `routing.phases.requires_mold`, `llm.ollama.*`… Caso flagrante: `alertas.delivery_risk.window_days`
  existe na BD mas o motor usa `DELIVERY_RISK_WINDOW_DAYS=3` constante
  (`copilot/alerts/engine.py:55,252-254`) — **mudar o knob não muda nada**.
- **Gap RBAC**: o router real é `/v1/config` (`tenant_config.py:34`) mas a matriz protege
  `/v1/core/config` (`rbac.py:233-234`) → `requirements_for_route` devolve None → fall-through
  do middleware. Em produção (rbac_strict), mutações de config passam **sem** `CONFIG_WRITE`.
- **Drift de documentação no DSL**: CLAUDE.md diz "12 eventos × 9 ações" e "11 YAMLs"; o código
  tem **10 ações** (`rule_schema.py:74-100`, `execute_runbook` adicionado Q.115.H) e **2 YAMLs**
  em `config/yaml/`.
- Estado live ≠ defaults documentados: `planning.scope=boats_and_molds` (não boats_only) e
  CP-SAT global **ON** — únicas keys `source=manual`.

---

## 4. Hipóteses e perguntas ao dono

**[HIPÓTESE]** (plausíveis, não provadas):
- H1. A exclusão da fase 53 (colagem) de `REPAIR_PHASE_IDS` foi deliberada (53 é colagem normal
  a maioria das vezes) — não há registo da decisão.
- H2. As 2 keys manuais da config de tenant foram postas via API (inferido de `source='manual'`
  + `last_modified_by`; pode ter sido SQL direto — irrelevante para a conclusão).
- H3. `P_L_ID` (FK sem alvo óbvio, `mar_kayaks_schema_discovery.md:1341`) pode ser o vestígio de
  uma classificação de "linha/gama" antiga no ERP.

**[PERGUNTA]** (precisam de resposta do Luis):
1. **"deana"** — confirmas que é "mediana"? Se não, em que contexto apareceu o termo?
2. **Fase 53 (colagem)** — marcar `is_reparacao` para barcos devolvidos em fase 53, como no
   canónico ERP `of_EmReparacao`?
3. **Fases de reparação** — {14,76,77} são estáveis na NELO ou pode aparecer outra? (hoje
   hardcoded; fase nova exige deploy)
4. **"Pessoa de expedição"** — é um role interno (embalar+carregar, fases 10/37)? Modelar como
   responsável do `transport_batch`?
5. **Capacidade por sector** — queres limite agregado (ex.: "Laminagem ≤ N barcos/dia") ou
   chegam as estações por fase (`phase_config`, nunca preenchido)?
6. **Tempos por modelo/fase** — confirmas o invariante (durações SÓ do histórico) ou queres
   tempos-alvo manuais? (contraria invariante Spelke)
7. **Disponibilidade de operadores** — ausências/férias vêm do ERP (`ent_mov` MET_MET_ID=2 já
   tem faltas/baixas/férias) ou geridas no nelinho? Hoje o CPO assume toda a gente disponível.
8. **Calendário** — precisas de UI para sábados de trabalho/paragens/horas extra, ou o gerado
   (seg-sex + feriados PT) chega?
9. **/regras (Q.17)** — qual o primeiro caso de uso real como regra YAML? Ligar emissores é
   trabalho por evento — qual priorizar?
10. **Config de tenant sem UI** (removida Q.172.E) — recriar página de Configuração do planeador
    (scope, CP-SAT, caps do robô, buffers de transporte) ou fica admin-via-API?
11. **84 keys mortas** — apagar do seed ou ligar aos consumidores? Em particular os thresholds
    de alertas, hoje constantes no código.

---

## 5. Gap de documentação — regras só-em-código a promover ao glossário

`agent_docs/domain_glossary.md` documenta bem: 7 axiomas Spelke, CoeficienteX=€, pipeline de
tempos, truck moda 26, retrabalho rates, fase 14 dual, whitelist Q.17, hipóteses H1-H5. Mas
~10 regras de negócio vivem **só em código/views da BD**:

| # | Regra | Onde vive |
|---|---|---|
| 1 | `REPAIR_PHASE_IDS` {14,76,77} | `src/plan/cpo/state.py:113` |
| 2 | `STATUS_PHASE_IDS` {11,32} (duração ~0) | `src/plan/cpo/state.py:123` |
| 3 | `NON_PRODUCTION_PHASE_IDS` (9 Armazém, 10 Embalado, 12 Entregue…) | `src/plan/cpo/state.py:75` |
| 4 | Markers de fase terminal ("entregue/armazem/embalado") e por-começar ("pendente/nao laminado") | `src/plan/services/phase_classification.py:53-84` |
| 5 | 7 sectores AREA_GROUPS | `src/workforce/levels.py:57-65` |
| 6 | Fila inter-fase = mediana por fase (Q.160) | `src/plan/cpo/state_loaders.py:486-511` |
| 7 | "Em produção" = op aberta na fase atual | view `factory_raw.v_of_em_producao` |
| 8 | Operador ativo = E_ACTIVO + 2 meses | view `factory_raw.v_active_operators` |
| 9 | Factor M.O. 1.065 = `core.erp_variables` VAR_ID=2 | `src/profit/services/material_cost_service.py:39-44` |
| 10 | Critério barco = raiz Kayak TP_ID 1 via `v_of_is_boat` | view + `mar_kayaks_procedures_analysis.md:42-43` |
| 11 | TPMOV (tabela MOVIMENTO_TIPO não espelhada) | `routes/_GLOSSARIO_BURACOS.md:14-31` |

E **um item desatualizado perigoso**: `domain_glossary.md:144-148` ainda aponta os números para
`Folha_IA_extra.xlsx` ("Where these numbers come from") — contraria a regra vigente **"ML treina
da BD real"** (desde Q.124 o pipeline treina de `factory_raw.of_fp`). Risco: um agente futuro
volta ao Excel. Corrigir junto com a promoção das regras acima (proposta de execução em
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)).
