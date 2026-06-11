# STOCK_AND_REPAIRS_PLAN.md — Planeamento por barco + materiais + reparações + ruturas

> **Snapshot:** todas as contagens de BD neste documento são de **2026-06-11** (Postgres `prodplan_one`
> via `docker prodplan-pg-wsl`, read-only). O backend `:8001` esteve em baixo durante parte da
> auditoria de stock — os comportamentos de endpoints foram derivados de **código + BD**, não de
> respostas HTTP live.
>
> **Âmbito:** arquitetura para (A) materiais restantes por OF, (B) motor de previsão de ruturas,
> (C) reparações no plano e na expedição, (D) impacto no Gantt/camiões. Incorpora as **decisões do
> Luis de 2026-06-11** (#2 reparações merge-back no mesmo plano; #4 mínimos = P_STOCKMIN do ERP +
> override local, lead times de E_PRAZOENTREGA).
>
> **Documentos irmãos:** achados completos em [AUDIT.md](AUDIT.md) · fluxos de dados em
> [DATA_FLOW_MAP.md](DATA_FLOW_MAP.md) · semântica de domínio (TPMOV, fases, "em produção") em
> [DOMAIN_RULES.md](DOMAIN_RULES.md) · sequenciação em [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
> · testes em [TEST_PLAN.md](TEST_PLAN.md).

**Legenda de confiança:** ✅ confirmado-no-código · 🗄️ confirmado-na-BD · ❓ HIPÓTESE ·
🙋 pergunta ao dono.

---

## 1. Estado atual (com evidência)

### 1.1 Planeamento por barco — EXISTE e funciona

A pergunta "que fases faltam a este barco e quando estão planeadas?" **tem resposta hoje**:

- **Scope boats-only real** 🗄️ — `factory_raw.v_of_em_producao` = **1.145 OFs** (675 nova produção,
  394 fila, 76 reparação), regra EXATA da NELO (op aberta na fase atual, sem `OF_DATAFIM`), filtrada
  a barcos por `v_of_is_boat`. Loader: `src/plan/cpo/state_loaders.py:965` `_load_open_orders_db`.
- **Rota truncada à fase atual** ✅ — `src/plan/services/routing_resolver.py:52-98`
  `_truncate_route_to_current(rows, current_fase_id, completed_fase_ids)`; fases concluídas vêm de
  `WHERE op."OFFP_DATAFIM" IS NOT NULL` (`state_loaders.py:1116`). O histórico `factory_raw.of_fp`
  tem **972.519** linhas e as fases por fazer já estão pré-criadas (DATAFIM NULL).
- **Verificado em 3 OFs reais** 🗄️ (auditoria vertical, DRAFT `f6a0c873` de 2026-06-11 10:40):

| OF | Produto | Fase atual | Fases restantes (of_fp) | No DRAFT? |
|---|---|---|---|---|
| 902252 | Waterman WWR | 33 Acabamento 2 | 33→42→46(→8) | sim (33 a 02-11-2026; due 19-06-2026!) |
| 900895 | Surf Ski 54 L AIR | 76 Reparação Verniz | 1 op fase 76 | sim (06-07-2026) |
| 8970144 | 400 ENALEIA Blue | 46 Montagem/Final. | 46→8 (0,6 h de trabalho) | sim (… a 2028-10-11) |

**O furo não é o "que falta", é o "quando"**: o DRAFT live é greedy com makespan **22.297 h
(~2,5 anos)** porque o candidato CP-SAT (~**690 h**) está a ser vetado pelo guardrail `idle_ratio`
(detalhe em [AUDIT.md](AUDIT.md)). A decisão #1 do Luis (gate com tolerância própria, baseline justo
sobre o MESMO op-set sem reparações, isenção de guardrails soft quando o makespan melhora >50%)
desbloqueia isto e é pré-condição de tudo o que segue — datas de necessidade de material e datas de
camião só fazem sentido com um plano com datas críveis.

### 1.2 Reparações — meio-existem, e desaparecem no caminho CP-SAT

- ✅ O CPO **planeia** reparações no caminho greedy: bypass em `routing_resolver.py:183-192`
  (`_repair_row`) agenda só a op aberta da fase 14/76/77 com duração mediana real; sem duração →
  unplanned honesto. `state_loaders` ordena-as primeiro (`repair_rank`).
- ✅🗄️ Mas `src/plan/engines/cpsat_global.py:72` exclui as fases de reparação
  (`main_ops = [o for o in operations if str(o.phase_id) not in REPAIR_PHASE_IDS]`) **e o result só
  contém `main_ops`**: o último commit `cpsat_global` tem **0 ops** nas fases 14/76/77 vs **190** no
  greedy (14:56, 76:79, 77:55). Não existe nenhum runner separado — quando o CP-SAT ganha, as **76
  OFs em reparação** desaparecem do plano.
- 🗄️ **74/76 reparações estão fora de `plan.production_orders`** (9.607 linhas): o mirror filtra
  `WHERE NULLIF(OF_DATAFIM,'') IS NULL` (`scripts/q131_setup_production_orders_mirror.py:61`) e uma
  reparação reentrada tem `OF_DATAFIM` da produção original preenchido (ex.: OF 900895,
  OF_DATAFIM=2024-10-09). Consequência: `/expedicao` by-date e camiões **nunca as veem**.
- 🗄️ **Due de reparação é mentirosa**: o COALESCE das 3 colunas (`state_loaders.py:1138-1140`)
  devolve a promessa da **venda original** — 900895 → 2024-10-11, no passado.
- 🗄️ **Reparação sem rasto de materiais**: 900895 tem 96 consumos TPMOV=11, todos de 2024; **zero**
  movimentos desde a reentrada (Armazém 2025-03-21). Coerente com a auditoria ERP de 2026-06-02
  ("retrabalho nunca registado") e com os **5.908** registos de rework com `mold_id` NULL.

### 1.3 Materiais NÃO entram no plano — o gate CTP é um proxy

- ✅ `src/plan/services/ctp_service.py:175-199` `_materials_gate`: *"we don't expand the full BOM…
  We check the finished product's own stock figure"* — verifica o stock do **produto acabado** como
  proxy, e sem dados de stock devolve `True` ("don't block on absence"). O `CTPTab.tsx:534-539`
  mostra "materiais OK" com base nisto.
- ✅🗄️ O MRP é caller-fed: `src/plan/services/mrp_service.py:101-106` só explode BOM "if provided"
  no payload; nunca lê `core.bom_items` (86.438 linhas espelhadas). `plan.material_requirements` =
  **0** — nunca correu. O frontend `planApi.ts:60-69` chama rotas (`/mrp/runs`) que nem existem.
- ✅ No CPO: `grep mrp|stock|material|shortage` em `src/plan/cpo` só devolve comentários;
  `greedy_pipeline.py:197-201` admite que o `demand_net` não subtrai stock. Nenhuma constraint de
  material no decoder, no CP-SAT, nem no state.
- ✅ Os únicos leitores de `factory_raw.movimento`/`produto_componente` em `src/` são o
  `boat_complexity_job.py:97,159` (ICB — conta peças e kg de tinta).

### 1.4 Deteção de ruturas — 100% inoperante, por 3 causas independentes

| # | Causa | Evidência |
|---|---|---|
| 1 | `/v1/factory-map/shortage-risks` itera `supply_rop_configs` que tem **0 linhas** → `items=[]` sempre | 🗄️ `supply.supply_rop_configs=0`; ✅ `risk_flags.py:98-121`; o único consumidor `ShortageRiskPanel.tsx:32` faz `return null` com lista vazia → painel **permanentemente invisível** no /overall |
| 2 | ShortageDetector horário varre 14.110 materiais mas **todos têm `min_stock_qty=0`** (hardcoded no ETL) → 0 alertas alguma vez criados | 🗄️ `min_stock_qty=0` em **14.110/14.110**; `copilot_alerts LIKE '%MATERIAL%'` → 0; ✅ `material_service.py:221` `below_min = projected < effective_min` com min=0; hardcode em `etl/material_master.py:56`. **Agravante** ✅: `min_stock_qty` está nos `update_fields` do upsert (`material_master.py:86`) — cada sync repõe 0 e **destrói overrides manuais** do PATCH `/materials/{sku}/min-stock` |
| 3 | A única UI de mínimos/POs/stockout — página Materiais — foi **apagada** no commit `2def464` (lean A1, 2026-06-02; já estava órfã da navegação desde Q.115) | ✅ git; `App.tsx:91-110` sem rota /materiais; endpoints `from-bom`, `purchase-orders`, PATCH min-stock vivos no backend **sem consumidor** |

E mesmo que 1-3 se resolvessem, os inputs estão podres:

- 🗄️ **Lead time = 7 dias placeholder em 14.110/14.110** (`material_master.py:55`); `core.suppliers`
  = 0 linhas; `E_PRAZOENTREGA` nunca lido em lado nenhum de `src/` (grep).
- 🗄️ **POs: cobertura ~2%** — `supply.purchase_orders` = 138 vs ~5.987 movimentos tipo 9 nos últimos
  12 meses; **ETA fictícia `ordered_at+30d` em 138/138**, `qty_received=0` em 138/138, todas OPEN.
  Causa ✅: `etl/purchase_orders.py:147` lê o ERP **live** com limit 5000 movimentos recentes (todos
  os tipos) e filtra tipo 9 em Python — nos 5.000 mais recentes só ~2 são tipo 9 — ignorando o
  espelho local `factory_raw.movimento` já sincronizado.
- 🗄️ **Ledger só tem 14 dias** (34.076 linhas, 2026-05-29→06-11): `inventory_ledger.py:116` lê o ERP
  live com limit 5000/noite em vez do espelho de 24 meses. O StockoutPredictor precisa de ≥30 dias
  para confidence high e o `recompute_rop_configs` (que existe, `rop_calculator.py:66`, mas **nunca
  correu nem está agendado**) usa lookback 90d — ambos à fome.

### 1.5 A matéria-prima EXISTE — dados ricos já espelhados e não usados

| Fonte 🗄️ | Linhas (2026-06-11) | O que dá |
|---|---|---|
| `factory_raw.movimento` | **2.544.418** (~24 meses) | movimentos de stock; 1,61M com `MOV_OF_ID` |
| — tipo 11 (consumo p/ OF) | **1.468.924** | 1,24M ligados a OF → modelo via `ordemfabrico.OF_P_ID`; 2.225 materiais distintos |
| — tipo 4 (Reserva) | ~137 K | criadas na criação da OF, com `MOV_FP_ID` (fase de consumo) e `MOV_SATISFEITO` |
| — tipo 9 (pedidos a fornecedor) | 12,7 K | encomendas reais (vs 138 espelhadas) |
| `factory_raw.produto_componente` (BOM) | **111.339 ativas** | `COMP_QUANTIDADE` + **`COMP_FP_ID` = fase de consumo** → timing por fase do plano |
| `factory_raw.produto` | 14.110 | **`P_STOCKMIN` > 0 em 1.110 produtos** — nunca importado |
| `factory_raw.entidade` | 9.031 | **`E_PRAZOENTREGA` ≠ 0 em 114 entidades** (lead time fornecedor) — nunca importado |
| `marts.v_consumo_material_dia` | 80.316 | dia×material: qty + custo, já filtrado a TPMOV=11 |
| `supply.warehouse_stock` | 8.069 | stock atual real, sync 5-min (fresco: 2026-06-11 10:45) |

**Semântica TPMOV** (❓ confirmada em doc, não em tabela oficial): `routes/_GLOSSARIO_BURACOS.md:14-31`
(cópia da tabela ERP `MOVIMENTO_TIPO`): **1=Entrada, 2=Saída, 4=Reserva, 5=Reparação, 9=Pedidos a
fornecedor, 11=Saída como componente (consumo de OF), 12=Pedidos internos**. Corroborada por SPs do
ERP (`agent_docs/mar_kayaks_procedures.md:9746-9752`: stock=Σtp1−Σtp2; necessidades=tp4). A tabela
**não está espelhada** em `factory_raw` — ver §8.

---

## 2. Arquitetura alvo A — materiais restantes por OF

**Objetivo:** responder "que materiais faltam consumir a este barco, em que fase, e há stock?".

### 2.1 Fonte primária: reservas abertas (TPMOV=4, `MOV_SATISFEITO=false`)

O ERP **já materializa o "por consumir"** — caso real verificado 🗄️:

- OF **902252**: 85 reservas TPMOV=4 (criadas na criação da OF, 2026-05-12, com `MOV_FP_ID` = fase
  de consumo), **78 não satisfeitas = 351,58 unid** por consumir, vs 7 consumos TPMOV=11 já feitos.
- OF 8970144: 30 reservas, 0 consumos. OF 900895 (reparação): **0 reservas** — ver §4.5.

### 2.2 Fonte secundária (validação): explosão BOM multi-nível × consumos TPMOV=11

A BOM nível-1 **não chega** 🗄️: os 7 consumos reais da 902252 (epoxy, carbono…) não estão na BOM
nível-1 do produto (34 linhas, que inclui pseudo-componentes "Mão de Obra de…") — estão na BOM do
componente laminado 27658 "K2 WWR (6) L100". A conta exige **CTE recursiva** sobre `core.bom_items`
(86.438 linhas), excluindo pseudo-componentes (❓ heurística: designação `Mão de Obra%`; 🙋 confirmar
critério oficial — há flag no ERP?).

As duas fontes divergem por construção: **usar reservas como verdade operacional** (refletem o que o
armazém alocou) **e a explosão BOM como verificação de completude** (reserva em falta = OF criada sem
picking completo → flag própria, não silêncio).

### 2.3 Desenho

- **Serviço novo** `src/supply/services/material_remaining_service.py`:
  `remaining_for_order(of_id)` → lê `supply.material_reservations` (mirror novo, §6) + consumos
  TPMOV=11 do espelho local; devolve por material: `qty_reservada`, `qty_consumida`, `qty_restante`,
  `fase_consumo` (MOV_FP_ID), `stock_disponivel` (warehouse_stock), `em_risco`.
- **Endpoint** `GET /v1/plan/orders/{order_id}/materials-remaining` (router supply ou plan; tenant
  via `require_tenant_header` como sempre).
- **Estado-vazio honesto** (invariante #8): reparações e OFs sem reservas devolvem
  `{"materials_known": false, "reason": "sem reservas registadas no ERP"}` — nunca lista vazia
  disfarçada de "tudo OK".
- **Substituir o proxy do CTP**: `_materials_gate` (`ctp_service.py:175-199`) passa a chamar este
  serviço em vez do stock do produto acabado. A docstring do módulo (que promete "every BOM material…
  is in stock") deixa de mentir.

---

## 3. Arquitetura alvo B — motor de previsão de ruturas

**Objetivo:** por material, projetar o saldo dia-a-dia no horizonte do plano e gritar ANTES da rutura
— e antes de o plano ser confirmado.

### 3.1 Fórmula de projeção (por material *m*, dia *t*)

```
saldo(m, t) = stock_atual(m)                                  [warehouse_stock, sync 5-min]
            + Σ encomendas pendentes com ETA ≤ t              [POs reais; ver 3.2-ETA]
            − Σ reservas abertas com necessidade ≤ t          [TPMOV=4 não satisfeitas; data = start
                                                               planeado da fase MOV_FP_ID no plano]
            − consumo previsto do plano ≤ t                   [ops planeadas × BOM, timing COMP_FP_ID,
                                                               SÓ para procura sem reserva — ver nota]
            − consumo base ≤ t                                [mediana E moda diárias por modelo, de
                                                               movimento tipo 11 (24 meses)]
```

**Nota anti-dupla-contagem (desenho, não opcional):** uma OF que está no plano *e* tem reservas
abertas entra **só pelas reservas** (mais precisas — qty alocada real); a componente plano×BOM cobre
ops planeadas de OFs **sem** reserva para esse material; o consumo base cobre procura **fora do
plano** (OFs futuras ainda não criadas). Cada componente etiqueta a sua origem no output.

**Consumo base por modelo:** mediana **e** moda diárias por (material × modelo) calculadas de
`factory_raw.movimento` tipo 11 via `MOV_OF_ID→ordemfabrico.OF_P_ID`; hierarquia de fallback quando
o par é raro: material×modelo → material×**disciplina** (`P_TP_ID_DISCIPLINA` — decisão #3 do Luis:
"gama/drop" = tipo/disciplina do produto) → material global (`marts.v_consumo_material_dia`).

### 3.2 Inputs e o seu estado

| Input | Fonte | Estado hoje | Pré-requisito (fase IMPL) |
|---|---|---|---|
| Stock atual | `supply.warehouse_stock` (8.069) | ✅ fresco | — |
| Mínimos | `P_STOCKMIN` ERP (1.110 >0) + override local | 🗄️ tudo 0 hoje | importar + fix clobber (§6, Fase 1) |
| Lead times | `E_PRAZOENTREGA` (114 entidades) | 🗄️ 7d placeholder | importar (§6, Fase 1) |
| POs + ETA | tipo 9 do espelho local; ETA real em `MOVIMENTO_FORNECEDOR.MOVFOR_ETA` | 🗄️ 138/~5.987 (2%), ETA +30d fictícia | backfill do espelho; ETA: bloqueada (§8) → interim `eta_source` + override manual |
| Reservas | TPMOV=4 do espelho | existem na raw, sem mirror estruturado | mirror novo (§6, Fase 1) |
| Plano com datas | ScheduleCommit | greedy 22.297 h (inútil p/ timing) | gate CP-SAT (decisão #1, Fase do CP-SAT) |
| Consumo histórico | movimento tipo 11 (1.468.924) | ✅ espelhado, não usado | job de agregação (§6) |

### 3.3 Saída

`plan.material_risk_run` (1 por execução, FK `schedule_commit_id`) + `plan.material_risk_item`:

| Campo | Conteúdo |
|---|---|
| `material_id`, `sku`, `designacao` | material em risco |
| `data_rutura_provavel` | primeiro dia com saldo projetado < mínimo efetivo (ou < 0) |
| `qty_necessaria` vs `qty_disponivel` | no dia da rutura |
| `ofs_afetadas[]`, `modelos[]` | OFs/barcos cuja fase de consumo cai depois da rutura |
| `impacto_plano` | nº ops e horas planeadas que ficam sem material |
| `sugestao` | `comprar` (lead time chega? → data-limite de encomenda) / `transferir` (stock noutro armazém em `warehouse_stock`) / `replanear` (empurrar as ops afetadas) |
| `confianca` | degrada quando ETA é placeholder, reserva ausente, ou consumo base com n baixo |

### 3.4 Quando corre — ANTES de confirmar o plano

- **Hook no preview/approve**: o fluxo de aprovação (SoD Q.61.09) passa a anexar o `material_risk_run`
  do commit ao payload do preview — quem aprova vê as ruturas que o plano implica. **Soft gate**:
  avisa, não bloqueia (materiais não são axioma Spelke; bloquear seria mentir sobre a precisão atual
  dos inputs). 🙋 promover a hard gate por tenant quando os inputs amadurecerem?
- **Pós-commit do robô**: com **203 DRAFT vs 3 LIVE**, esperar pelo approve seria nunca correr.
  O worker Arq corre o motor logo a seguir a cada DRAFT saudável (mesmo job, depois do
  `ScheduleCommit`), para o /overall mostrar badges sem depender de aprovação.
- **Horário**: o `ShortageDetector` existente (`scheduling/core.py:426-435`, hourly — vivo mas
  inerte) passa a comparar contra mínimos efetivos reais; mantém-se como rede de segurança
  independente do plano.

---

## 4. Arquitetura alvo C — reparações (decisão #2: merge-back no MESMO plano)

### 4.1 Decisão tomada (Luis, 2026-06-11)

> CP-SAT planeia barcos; reparações são agendadas **a seguir, no mesmo commit**, com filtro/badge
> próprio no /overall. Não há agenda separada.

### 4.2 Repair pass — desenho

1. `run_cpsat_global` (`cpsat_global.py:57`) continua a excluir `REPAIR_PHASE_IDS` (14/76/77) — o
   solver global não as modela (fase 14 é dual molde+barco; durações de reparação são erráticas).
2. **Gate axioma-7 primeiro, com baseline justo** (decisão #1): o baseline greedy é recalculado
   sobre o **mesmo op-set sem reparações** — hoje o gate compara CP-SAT (sem reparações) contra
   greedy (com 190 ops de reparação), o que é estruturalmente injusto.
3. **Depois de o gate aceitar**, um passo novo `schedule_repairs(result, state)` (greedy
   earliest-feasible, reaproveitando `_repair_row` do `routing_resolver.py:183-192` e o
   load-balancing de `_pick_workers`) agenda as ops de reparação **sobre a capacidade residual** do
   plano CP-SAT — mesmos pools de operadores (gate `Entidade_Fase`, filtro `v_active_operators` =
   **106 ativos**), mesmas estações — e **anexa-as ao mesmo result dict** antes do `ScheduleCommit`.
4. Cada op leva `is_repair=true`; `cpo_meta.repair_pass = {count, unplanned, engine:"greedy_repair"}`.
   Sem duração mediana → unplanned honesto (comportamento atual preservado).
5. `validate_schedule` (`commits.py:255`) corre sobre o conjunto completo — double-booking entre
   plano CP-SAT e repair pass é apanhado estruturalmente.

Ordem deliberada (reparações depois dos barcos): evita que 190 ops de reparação roubem capacidade ao
plano otimizado. 🙋 confirmar com a fábrica — há reparações com cliente à espera que devam furar a
fila? Se sim: `repair_rank` já existe como mecanismo de prioridade.

### 4.3 Reparações na expedição — corrigir o mirror

- Alterar o filtro do mirror (`q131_setup_production_orders_mirror.py:61`): além de
  `OF_DATAFIM IS NULL`, incluir OFs presentes em `v_of_em_producao` com fase atual ∈ {14, 76, 77}
  (cobre as **74/76** hoje excluídas), com coluna nova `is_repair`.
- Com isto, `/expedicao` by-date (`src/plan/api/transport.py:591-662`) e o `refresh_from_orders`
  dos camiões passam a vê-las sem mais código.

### 4.4 Due honesta de reparação

- 🗄️ A due derivada devolve a promessa da venda original (900895 → 2024). **Não usar.**
- Interim: para `is_repair`, due no passado >N meses → `due_date=NULL` (sem prazo conhecido) +
  prioridade via `repair_rank`. Estado-vazio honesto no frontend ("sem prazo registado").
- 🙋 **Pergunta ao dono:** existe promessa NOVA de reparação no ERP (ENCOMENDA nova? `transp_of`/
  `transp_datas`? campo na reabertura?) que devamos espelhar como due real?

### 4.5 Reparações × materiais — limite honesto

🗄️ Reparações **não têm** reservas nem consumos desde a reentrada (900895: 0 reservas, 96 consumos
todos de 2024; coerente com "retrabalho nunca registado" e os **5.908** rework com `mold_id` NULL).
O motor de ruturas (§3) **não consegue** prever consumo de reparações — declarar
`materials_known=false` nessas ops, nunca estimar em silêncio. 🙋 a NELO quer passar a registar
consumo de reparação no ERP (movimento tipo 5/11 contra a OF reaberta)? Sem isso este furo é
permanente.

---

## 5. Impacto no Gantt (/overall) e na expedição

### 5.1 Gantt

- **Badge "falta material"** no OpCard quando a fase da op consome um material com
  `data_rutura_provavel` ≤ start planeado (join op×`material_risk_item` via fase de consumo).
  **Obrigatório lazy-load** via IntersectionObserver + endpoint batch por janela visível — lição
  Q.144: o QualityRiskBadge eager fez ~9.896 fetches e abriu o circuit-breaker global.
- **Filtro/badge reparações** (decisão #2): chip "Reparações (N)" + cor própria nas ops
  `is_repair`; o filtro/foco existente do /overall ganha a dimensão reparação.
- O painel `ShortageRiskPanel.tsx` (hoje permanentemente invisível, §1.4) passa a alimentar-se do
  `material_risk_run` do commit mostrado — deixa de depender de `supply_rop_configs`.

### 5.2 Expedição

- **Camiões largam assignments obsoletos** 🗄️: hoje `refresh_from_orders`
  (`transport_batch_service.py:256-261`) "nunca reatribui uma ordem já colocada" e nunca limpa stale
  — o camião SHP-2026-06-19 tem 50 assignments mas só **5** ordens ainda são desse dia (42 mudaram
  para 03-07, 2 no passado, 1 órfã), e a OF 902252 (due 19-06!) ficou de fora por o camião estar
  "cheio" de fantasmas. Fix: no refresh, remover assignments cuja `transport_date` atual da ordem
  diverge da data do batch (e re-sentar os despejados). 🙋 capacidade real por camião/destino? — o
  default 50 é hardcoded (`transport_batch_service.py:220`).
- **`transport_date` honesta** ✅🗄️: o mirror usa `COALESCE(OF_TR_DATA_PREVISTA, OF_DATA)` — fallback
  à **data de criação** (`q131_setup_production_orders_mirror.py:54-57`) → **9.607/9.607** ordens
  "têm" data, parte fabricada (8970144 ficou com 2026-05-15 = OF_DATA). Roça o invariante #8.
  Fix: alinhar com a derivação do due (`state_loaders.py:1138-1140`) e deixar NULL quando não há
  promessa.
- **Ligação plano→camião** (hoje **inexistente** ✅: `fitness.py:100`
  `truck_consolidation_weight=0.0`, `compute_truck_consolidation_penalty_h` só chamado em testes,
  by-date classifica pela fase ATUAL e não pelo DRAFT): primeiro passo barato — o by-date passa a
  ler o end planeado da última fase produtiva do commit saudável mais recente e a sinalizar
  `risco=atraso` quando end > data do camião. A penalidade no fitness fica para depois de o CP-SAT
  estar live (senão otimiza contra datas fabricadas).

---

## 6. Modelo de dados e jobs

### 6.1 Tabelas/colunas

| Objeto | Mudança | Porquê |
|---|---|---|
| `supply.supply_material_master` | + `min_stock_qty_erp` (import P_STOCKMIN); `min_stock_qty` passa a **override local nullable**; mínimo efetivo = `COALESCE(override, erp, 0)`. **Tirar ambos + `lead_time_days` dos `update_fields`** do upsert (`material_master.py:86`) — fix do clobber. + `lead_time_days_erp` | decisão #4; §1.4 |
| `supply.material_reservations` **(nova)** | mirror TPMOV=4: `mov_id` (chave idempotente), `of_id`, `material_id`, `fase_id` (MOV_FP_ID), `qty`, `satisfeito` (MOV_SATISFEITO), `created_at_erp` | §2.1 |
| `core.suppliers` | seed de `factory_raw.entidade` (fornecedores) com `lead_time_days` = E_PRAZOENTREGA (114 com valor) | hoje 0 linhas; FK alvo já existente |
| `supply.purchase_orders` | backfill do **espelho local** tipo 9 (12,7 K) em vez do ERP live limit-5000; + `eta_source` (`placeholder`/`movfor`/`manual`) + ETA editável | §1.4; §8 |
| `plan.production_orders` (mirror) | incluir reparações (filtro §4.3) + `is_repair`; `transport_date` sem fallback OF_DATA (nullable) | §4.3, §5.2 |
| `plan.material_risk_run` / `plan.material_risk_item` **(novas)** | output do motor (§3.3), FK `schedule_commit_id` | §3 |
| ScheduleCommit `cpo_meta` | + `repair_pass` | §4.2 |
| ops do plano | + `is_repair` no contrato do result dict (decoder e cpsat partilham contrato — `build_result_dict`) | §4.2, §5.1 |
| `marts.v_consumo_by_of_dia` | **recriar** sobre `factory_raw.movimento` (MOV_OF_ID) — o script Q.108.G atual referencia `inventory_ledger_entries.work_order_id` que **não existe** e nunca foi aplicado | §1.4 |

### 6.2 Jobs/ETL

| Job | Mudança | Cadência |
|---|---|---|
| `etl/material_master.py` | mapear P_STOCKMIN→`min_stock_qty_erp`; não clobberar overrides | nightly (atual) |
| `etl/inventory_ledger.py` | **repontar para `factory_raw.movimento`** (espelho local, 24 meses) com backfill — destrava StockoutPredictor (≥30 dias) e ROP (90d) | nightly |
| mirror reservas **(novo)** | TPMOV=4 incremental por MOV_ID/data | juntar aos `_INCREMENTAL_MIRRORS` 5-min (`scheduling/jobs/nelo_erp.py:56`) |
| `etl/purchase_orders.py` | ler tipo 9 do espelho local; `eta_source` | nightly |
| `recompute_rop_configs` | **agendar** (existe e nunca correu — `rop_calculator.py:66`); só depois de mínimos+lead reais, senão cimenta o placeholder 7d | nightly, após ledger |
| agregação consumo base **(novo)** | mediana+moda por material×modelo (+disciplina) de tipo 11 | nightly |
| motor de ruturas **(novo)** | pós-commit do robô + hook preview/approve + hourly | §3.4 |
| `refresh_from_orders` (camiões) | largar/re-sentar assignments stale | no sync 5-min atual |

Tudo dentro das regras da casa: migrações Alembic (nunca create_all em prod), `audit_log` na mesma tx
para mudanças de estado (invariante #7), estados vazios honestos (invariante #8).

---

## 7. Mapeamento para o [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

Este documento alimenta as fases 1, 3, 4 e 5 (e o filtro/badge de reparações na fase 6); a
dependência do gate CP-SAT (decisão #1) vive na fase 3 e é pré-condição do timing fino de §3/§5.

| Fase IMPL | Entregas deste plano | Itens |
|---|---|---|
| **Fase 1 — fundações de dados** | tudo o que é import/mirror/honestidade, sem lógica nova de planeamento | P_STOCKMIN + override (§6.1); E_PRAZOENTREGA→suppliers; mirror reservas TPMOV=4; ledger do espelho local; backfill POs tipo 9 + `eta_source`; mirror reparações em `production_orders` + `is_repair`; `transport_date` sem OF_DATA; recriar `v_consumo_by_of_dia`; espelhar `MOVIMENTO_TIPO` (§8) |
| **Fase 3 — CP-SAT (decisões #1/#2)** | merge-back das reparações no solver | repair pass no mesmo commit + `cpo_meta.repair_pass` (§4.2); baseline do gate sem reparações (mesmo op-set, decisão #1) |
| **Fase 4 — vertical por barco (materiais + reparações/expedição)** | materiais por OF + camiões honestos | `material_remaining_service` + endpoint (§2); CTP gate real (BOM, não proxy); due honesta de reparação (§4.4); limpeza de assignments stale + capacidade real de camião; by-date a ler o plano (§5.2) |
| **Fase 5 — ruturas de stock** | motor de ruturas + UI de materiais | motor de ruturas + `material_risk_*` + hooks preview/approve/pós-DRAFT (§3); `recompute_rop_configs` agendado; badge falta-material lazy no Gantt (§5.1); ressuscitar UI de materiais (🙋 página própria ou abas no /overall+/expedicao — a antiga foi apagada por ser órfã, não por ser má) |
| **Fase 6 — Gantt** | reparações visíveis no plano | filtro/badge reparações no Gantt (decisão #2, lado visual) |

Critérios de aceitação e cobertura de teste por fase: [TEST_PLAN.md](TEST_PLAN.md).

---

## 8. Riscos e perguntas abertas

| # | Risco / pergunta | Tipo | Mitigação interim |
|---|---|---|---|
| 1 | **Semântica TPMOV não confirmada oficialmente** — 11 (consumo) e 9 (pedidos) corroborados por código+marts+SPs; **2 (~568 K), 12 (232 K), 4 (137 K), 1 (112 K)** vivem só no glossário markdown; tipo 14 aparece como "xx"; 7/8 ("Entrada/Saída Em produção") nunca usados | ❓→🙋 | espelhar `dbo.MOVIMENTO_TIPO` para `factory_raw` (15 linhas) e pedir confirmação à NELO antes da Fase 4 |
| 2 | **`MOVIMENTO_FORNECEDOR` não acessível** (issue Q.68.A, `purchase_orders.py:31-33`) — sem `MOVFOR_ETA` não há ETA real nem receções (`qty_received`) | bloqueio externo | `eta_source` explícito + ETA manual editável; pedir acesso de leitura à tabela no SQL Server da NELO |
| 3 | **Reservas = picking real?** As TPMOV=4 são criadas na criação da OF — refletem alocação teórica ou picking físico? Quando é que `MOV_SATISFEITO` vira true (no consumo? na separação?) | 🙋 | confirmar com o armazém; até lá, tratar reservas como *necessidade* e consumos tipo 11 como *verdade* |
| 4 | **`E_PRAZOENTREGA`**: está em dias? cobre só 114/9.031 entidades (1,3%) — é fonte parcial, não substituto; e qual o link produto→fornecedor preferencial para atribuir lead time a um material? | 🙋 | fallback honesto: material sem fornecedor/lead conhecido fica `lead_time_days=NULL` (não 7) e baixa a `confianca` da sugestão de compra |
| 5 | **Explosão BOM multi-nível**: pseudo-componentes "Mão de Obra" e profundidade desconhecida da árvore (6.216 pais × 3.650 componentes) podem inflacionar a procura prevista | ❓ | reservas como fonte primária (§2.1); explosão só como verificação, com exclusão heurística auditável |
| 6 | **Reparações sem promessa nem consumo no ERP** — due honesta (§4.4) e materiais (§4.5) dependem de prática nova na fábrica | 🙋 | due=NULL + `materials_known=false`; levar as duas perguntas à NELO |
| 7 | **Dupla contagem reservas×plano×consumo-base** na fórmula de §3.1 | desenho | regra anti-dupla-contagem explícita + origem etiquetada por componente; property test no [TEST_PLAN.md](TEST_PLAN.md) |
| 8 | **Timing do plano só presta com CP-SAT live** — com o greedy (22.297 h) as datas de necessidade/rutura ficam todas "daqui a anos" | dependência | sequenciar: gate CP-SAT (decisão #1) antes da Fase 4; motor de ruturas degrada `confianca` quando o commit fonte é greedy |
| 9 | **Capacidade de camião 50 hardcoded** e sem destino/rota | 🙋 | pedir tabela real de camiões/destinos; até lá, manter 50 mas configurável por tenant |
| 10 | **Verificação live em falta** — o backend esteve em baixo na auditoria de stock; os endpoints supply nunca foram exercitados ao vivo neste ciclo | dívida | smoke live dos endpoints supply na Fase 1 (ver [TEST_PLAN.md](TEST_PLAN.md)) |

---

*Escrito a partir da auditoria multiagente de 2026-06-11 (44 agentes, BD real read-only, verificação
adversarial). Achados integrais: [AUDIT.md](AUDIT.md). Última revisão: 2026-06-11.*
