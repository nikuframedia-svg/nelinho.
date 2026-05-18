# NELO — Análise da DB + roadmap de oportunidades

> Documento de estratégia. Análise ponta-a-ponta da ERP da NELO (MAR-KAYAKS) e proposta de
> funcionalidades, na perspectiva de director industrial + CEO.
> **Data:** 2026-05-18 · **Âmbito:** chão de fábrica + qualidade + moldes + energia + margem.
> Cada funcionalidade foi **verificada contra o backend `src/`** — as etiquetas de estado
> reflectem o código real, não intenção.

---

## TL;DR

A ERP MAR-KAYAKS tem **284 tabelas, 55 views, ~29M linhas**. O nelinho lê hoje **12 tabelas**.
Há domínios inteiros parados. Mas a descoberta decisiva da análise não foi "falta construir" —
foi o contrário: **a maioria das funcionalidades já está construída no backend** e não corre
porque os dados não fluem (`sqlserver_enabled=False`) ou porque uma peça pronta nunca foi
activada.

Das 13 funcionalidades avaliadas: **1 já está feita, 1 está pronta a ligar, 5 são "completar
um parcial", e só 6 são construção nova de raiz.** O trabalho é mais de *activação* do que de
*invenção*.

---

## Parte A — O que a DB da NELO tem

> Fonte: `nelo_deepscan_2.md`, `nelo_executive_summary.md`, `HANDOFF.md §6`.

A ERP prova que a NELO **não é uma fábrica** — são 5 negócios num só: manufactura de
competição, R&D de performance hidrodinâmica (barcos olímpicos), centro de estágios, aluguer
de barcos para provas, e venda global via agentes. O nelinho hoje só vê o primeiro, e mal.

Este documento foca **produção, qualidade, moldes, energia e margem** (domínios 1-5 + o
segmento de margem do comercial). R&D, centro de estágios e logística ficam mapeados para
referência, fora de âmbito por agora.

| Domínio | Tabelas-chave (linhas) | Em foco aqui? |
|---|---|---|
| Produção | ORDEMFABRICO 441k · OF_FP 2.6M · OFFP_EQ 1.4M · MOVIMENTO 12.4M | ✅ |
| Catálogo / Routing / BOM | PRODUTO 14k · PRODUTO_FASE 42.8k · PRODUTO_COMPONENTE 117.9k · FASES_PRODUCAO 71 | ✅ |
| Qualidade | OF_CHECKLIST 3.0M · OFCH_LOCAL 58k · OFFP_GRAVIDADES 148 · RetornosFuncionario 88k | ✅ |
| Moldes | MOLDES 91 (de ~510) · MOLDES_MOV 3.7k · MOLDES_TIPO 14 | ✅ |
| Energia / Ambiente IoT | IOT_SENSOR_DATA 3.6M · TH 586k · IOT_SENSOR 32 · IOT_SENSOR_ALARM 14 | ✅ |
| Margem (segmento comercial) | ENTIDADE_PHC_FACT 100k · AgenteEncomenda · ENTIDADE 8.9k | ✅ (só F7) |
| Pessoas / calendário | DIAS_TRABALHO 15.6k · FERIAS · ENTIDADE_FASE 1.3k | ✅ |
| KPI / objectivos | KPI 115 · KPI_OBJECTIVO 267 | ✅ |
| R&D / Estágios / Logística | SensoresTeste* · Velocidade 142k · CENTRO_RESERVA* · TRANSP_* | ⏭️ fora de âmbito |

---

## Parte B — O gap nelinho ↔ ERP

- **Lê hoje:** ORDEMFABRICO, OF_FP, OFFP_EQ, PRODUTO, PRODUTO_FASE, PRODUTO_COMPONENTE,
  FASES_PRODUCAO, ENTIDADE, ENTIDADE_FASE, MOLDES, MOVIMENTO, OF_CHECKLIST — **12 de 284**.
- **Bloqueador-mestre:** `settings.sqlserver_enabled=False`. Os 5 mirrors ETL e os jobs
  agendados existem e estão prontos — mas em no-op enquanto a flag estiver desligada.
- **Peças prontas mas inertes:** modelo preditivo de defeito treinado e wired ao CPO, mas o
  job de scoring é um stub; health model de moldes completo, mas sem histórico de uso real.
- **510 moldes** vivem num Excel — só 91 (18%) estão na DB.
- **Domínios 5+** (energia IoT, R&D, estágios, logística) — **0% tocados**.

Legenda de estado usada na Parte C: ✅ já feito · 🟡 parcial · 🔌 construído, falta ligar ·
🆕 novo.

---

## Parte C — As 13 funcionalidades, por estado verificado

### Categoria 1 — Construído, falta LIGAR

#### F1 · Sync ERP a correr em produção — 🔌
**Estado:** os 5 mirrors ETL (master_data, molds, skills, quality, time_mining) estão
**completos**; os jobs APScheduler estão **registados** (`scheduler.py:119-136` — sync leve
nightly 02h UTC, time_mining domingo 01h). Tudo em no-op porque `sqlserver_enabled=False`.
**Falta:** pôr a flag a `True`, credenciais reais (`sqlserver_url`), validar contra o ERP
vivo, e pedir ao IT NELO para aplicar as views `vw_pp1_*`.
**Valor:** base de tudo — sem isto, qualquer painel novo mente. **Esforço:** S (operacional).
**Ficheiros:** `src/adapters/nelo/etl/sync.py`, `src/shared/scheduler.py:119-136`,
`src/shared/config.py`.

#### F2 · OTD honesto — ✅ JÁ FEITO
**Estado:** `GET /v1/profit/otd` calcula `actual <= promised` com
`CuratedOrder.data_entrega_prevista` / `data_conclusao`; existe heatmap produto×semana
(`kpis.py:429-522`). A definição de "ordem aberta" já não depende do `OF_DATAFIM` NULL (71%).
**Falta:** nada de código — só depende de F1 (a camada curada precisa do sync a correr).
**Acção:** nenhuma. Registar como pronto; validar os números quando F1 ligar.

### Categoria 2 — Parcial, falta COMPLETAR

#### F3 · 510 moldes na DB — 🟡
**Estado:** o mirror ERP traz **91** moldes (`etl/molds.py`). O modelo `CuratedMold` e o
transformador Excel `_transform_molds` existem; `config.py` já espera 510.
**Falta:** sync automático dos 510 do Excel (`Folha_IA_extra.xlsx`) para `plan.mold`; ligar
`MOLDES_MOV` (3.7k movimentos) como histórico de uso de molde.
**Valor:** mold exclusivity (Axioma Spelke 3) está hoje 🟡 parcial a 18%. **Esforço:** M.
**Ficheiros:** `src/adapters/nelo/etl/molds.py`, `factory_data_product/ingest/transformer.py`.

#### F4 · Custo do retrabalho em € — 🟡
**Estado:** `ReworkEntry.cost_estimate_eur` existe mas **não é agregado**; o COGS tem linha
de scrap (`cogs_calculator.py:427-464`) mas usa **taxa padrão ~2%** — não lê o rework real.
**Falta:** ligar `ReworkEntry` real → COGS; endpoint "custo total de retrabalho por ordem";
tile de € perdido no painel CEO. Quantificar os 89.836 erros (16.97%) em € concreto.
**Valor:** €, Q — a maior fuga de margem visível. **Esforço:** M.
**Ficheiros:** `src/quality/services/rework_service.py`,
`src/profit/calculators/cogs_calculator.py`.

#### F5 · Modelo preditivo de defeito — 🟡 ★ maior alavanca
**Estado:** `QualityRiskModel` (GradientBoostingClassifier) **existe e treina**
(`ml/models_domain/quality_risk.py`), com RetrainJob aos domingos 02h, e está **wired ao
fitness do CPO** (`fitness.py:58`, peso 0.10). MAS o job `_quality_risk_scoring_job` é um
**stub** (`scheduler.py:353-359` — só faz log).
**Falta:** activar o scoring real; alimentar com dados curados (depende de F1); tornar o
scoring mold-específico.
**Valor:** Q, € ★. **Esforço:** M (activar) → L (mold-específico).
**Ficheiros:** `src/shared/scheduler.py:353-359`, `src/ml/models_domain/quality_risk.py`.

#### F6 · Manutenção preditiva de moldes — 🟡 (núcleo ✅)
**Estado:** o health model está **completo** — `mold_health_calculator.py` (4 sinais
ponderados), thresholds RED/YELLOW/GREEN, `/molds/health-report`, `/molds/calendar`,
`propose_preventive_schedule()`, job diário de scan. O threshold de ciclos está a **0
(desactivado de propósito** — a NELO vai por inspecção visual, decisão do CEO 2026-04-26).
**Falta:** alimentar com uso real (`MOLDES_MOV` — depende de F3); decidir com o Luis se o
threshold de ciclos passa a estar activo (substituir o "800 usos" inventado, ver `HANDOFF` H2).
**Valor:** €, Q. **Esforço:** S (depende de F3).
**Ficheiros:** `src/plan/services/mold_health_calculator.py`,
`src/plan/services/mold_service.py:46-51`.

#### F7 · Margem por cliente / agente / país — 🟡
**Estado:** margem **por ordem** existe (`/v1/profit/orders/margins`); backlog e OTD "por
cliente" existem mas o cliente é **proxied por `produto_nome`** — não é o cliente real. Sem
agente, sem país, sem leitura de `ENTIDADE_PHC_FACT`.
**Falta:** cliente real (de `ENTIDADE` / `ENTIDADE_PHC_FACT`); segmentação por agente
comercial e por país; histograma de margem por segmento.
**Valor:** € ★ — responde "quem dá lucro vs quem dá só volume". **Esforço:** M.
**Ficheiros:** `src/profit/services/dashboard_metrics_service.py`,
`src/profit/services/margin_calculator.py`.

### Categoria 3 — Construir NOVO

#### F8 · Custo de energia REAL por barco/fase — 🆕 (linha standard ✅)
**Estado:** o COGS já tem linha de energia, mas **standard** —
`MachineRate.energy_cost_per_hour` × horas. Não lê sensores. `IOT_SENSOR_DATA` (3.6M, potência
trifásica) nunca foi tocado.
**Falta:** ingerir `IOT_SENSOR_DATA` → kWh real por fase/dia → € real; comparar real vs
standard. Não há mirror IoT — é ingestão nova.
**Valor:** € — energia real vs orçada. **Esforço:** M-L.
**Ficheiros:** novo mirror em `src/adapters/nelo/etl/`,
`src/profit/calculators/cogs_calculator.py`.

#### F9 · KPI objectivo vs realizado no painel CEO — 🆕
**Estado:** os snapshots de KPI existem (OEE / Availability / Performance / FPY / Rework —
`kpis.py:311-334`), mas **não há conceito de objectivo**. A NELO já definiu **267 objectivos**
na ERP (`KPI_OBJECTIVO`) que ninguém lê.
**Falta:** modelo de objectivos; ler `KPI` / `KPI_OBJECTIVO` da ERP; mostrar actual-vs-meta na
DirecaoPage.
**Valor:** €, OTD ★ — os alvos do CEO já existem, só não estão à vista. **Esforço:** M.
**Ficheiros:** `src/profit/api/kpis.py`, novo modelo de objectivos, `DirecaoPage`.

#### F10 · Calendário de capacidade real — 🆕
**Estado:** **não existe**. O `FactoryState` carrega a skill matrix mas **não** dias de
trabalho, férias ou turnos — a disponibilidade do operador é idealizada (8h/dia fixo).
`Employee.status` tem `ON_LEAVE` mas nunca entra no decoder.
**Falta:** ingerir `DIAS_TRABALHO` (15.6k) + `FERIAS`; modelo de disponibilidade; constraint
no decoder que respeite a indisponibilidade.
**Valor:** OTD, € — um plano que ignora férias é um plano que falha. **Esforço:** M.
**Ficheiros:** `src/plan/cpo/state.py`, `src/plan/cpo/decoder.py`, novo modelo de calendário.

#### F11 · Mapa de defeitos do barco (por zona) — 🆕
**Estado:** **não existe**. O root-cause analisa por worker / model / mold / phase, mas nunca
por **zona do casco**. `OFCH_LOCAL` (58k — onde no barco está o defeito) não é lido; nem
`ReworkEntry` nem `MoldDefectLog` têm campo de localização.
**Falta:** campo `location_zone`; ingerir `OFCH_LOCAL`; heatmap + Pareto por zona.
**Valor:** Q — diz *onde* a fábrica falha, não só *quanto*. **Esforço:** M.
**Ficheiros:** `src/quality/models/rework.py`, `src/quality/services/root_cause_analyzer.py`.

#### F12 · Validação ambiental da cura — 🆕
**Estado:** os 16 gaps de cura são um **seed validado** + override por tenant (completo,
`state.py:33`). Mas **não há validação contra sensores reais** — `TH` (586k) e
`OFFP_TEMPERATURA` / `OFFP_HUMIDADE` nunca foram sincronizados.
**Falta:** ingerir `TH` / IoT; constraint "não desmoldar se temp/humidade fora de range";
alerta ambiental no copiloto via `IOT_SENSOR_ALARM`.
**Valor:** Q ★ — a cura é química; hoje confia-se no relógio, não no sensor. **Esforço:** M.
**Ficheiros:** `src/plan/cpo/state.py`, novo `curing_environment`, novo mirror IoT.

#### F13 · Aderência ao plano (plano vs realizado) — 🆕
**Estado:** o plano digital **já existe** — `ScheduleCommit` persiste-o (imutável,
hash-chained, com KPIs e alternativas) e materializa-o em `ProductionSchedule`. O ERP é
read-only, logo não há (nem deve haver) write-back para `PLANEAMENTO_DIARIO`.
**Falta:** o gap real não é gerar o plano — é **medir se foi cumprido**. Comparar o
`ScheduleCommit` com o que o `OF_FP` regista que aconteceu de facto → % de aderência, desvios
por fase, deriva.
**Valor:** OTD ★ — fecha o ciclo "planeei → aconteceu → aprendi". **Esforço:** M.
**Ficheiros:** `src/plan/cpo/commits.py`, `src/adapters/nelo/services.py` (`list_operations`).

---

## Parte D — Sequência recomendada

| # | Funcionalidade | Estado | Categoria |
|---|---|---|---|
| F1 | Sync ERP em produção | 🔌 | Ligar |
| F2 | OTD honesto | ✅ | Feito |
| F3 | 510 moldes na DB | 🟡 | Completar |
| F4 | Custo do retrabalho em € | 🟡 | Completar |
| F5 | Modelo preditivo de defeito | 🟡 | Completar ★ |
| F6 | Manutenção preditiva de moldes | 🟡 | Completar |
| F7 | Margem por cliente/agente/país | 🟡 | Completar |
| F8 | Energia real por barco/fase | 🆕 | Novo |
| F9 | KPI objectivo vs realizado | 🆕 | Novo |
| F10 | Calendário de capacidade real | 🆕 | Novo |
| F11 | Mapa de defeitos por zona | 🆕 | Novo |
| F12 | Validação ambiental da cura | 🆕 | Novo |
| F13 | Aderência ao plano | 🆕 | Novo |

**Ordem proposta:**
1. **F1 primeiro, sempre.** Sem o sync ligado, F2 não tem dados e F5/F8/F12 não têm o que
   ingerir. É esforço operacional, não código — o desbloqueio mais barato e mais alto.
2. **F2 valida-se sozinho** logo a seguir — já está feito; é a primeira prova de que os
   dados fluem.
3. **Categoria 2** (F3, F4, F6, F7, F5) — completar peças parciais rende rápido porque o
   esqueleto já existe. F4 (custo do retrabalho) dá ao CEO um número que dói já.
4. **Categoria 3 por lente:** qualidade → F11, F12; € → F8, F9; OTD → F10, F13.

**Maior alavanca:** F5 — o modelo de defeito está treinado e ligado ao CPO; só falta activar
o job de scoring. 16.97% de retrabalho × 14.7 barcos/dia × ~€2.350 é a maior fuga de margem
da casa, e o preditor está a um stub de distância de funcionar.

**Lição da análise:** o nelinho está mais perto do que parece. De 13 funcionalidades, 1 já
está feita, 1 está pronta a ligar, 5 são "completar parcial", e só 6 são construção nova de
raiz. A próxima fase é mais de *activação* do que de *invenção*.

---

*Documento gerado por exploração read-only do código (`src/`) e dos relatórios de scan da DB
(`nelo_deepscan_2.md`, `nelo_executive_summary.md`). Owner: Luis (luis@nikufra.ai).*
