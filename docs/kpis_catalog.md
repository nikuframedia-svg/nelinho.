# KPI Catalog — ProdPlan ONE
**Gerado automaticamente:** 2026-01-27 18:01
**Versão:** 1.0.0

---
## Índice
1. [Resumo](#resumo)
2. [KPIs por Domínio](#kpis-por-domínio)
   - [Plan](#plan)
   - [Profit](#profit)
   - [Hr](#hr)
   - [Dqa](#dqa)
   - [Factory](#factory)
   - [Supply](#supply)
   - [Quality](#quality)
3. [KPIs Bloqueados](#kpis-bloqueados)
4. [Trust Index Guide](#trust-index-guide)

---
## Resumo
| Métrica | Valor |
|---------|-------|
| Total KPIs | 14 |
| KPIs Usáveis | 10 |
| KPIs Bloqueados | 4 |

## KPIs por Domínio

### PROFIT
<a name="profit"></a>

#### `real_cost_per_order` — Custo Real por Ordem
**Status:** 🚫 BLOQUEADO

**Descrição:** Custo real de mão-de-obra e materiais por ordem

**Fórmula:**
```
N/A
```

**Unidade:** `EUR`

**Fontes de Dados:**

**Trust Segments:**

**Trust Mínimo:** 90

**Limitações:**
- ⚠️ Não existem dados de horas reais trabalhadas
- ⚠️ Não existem dados de consumo real de materiais

**Claims Proibidas:**
- 🚫 "custo real"
- 🚫 "custo efectivo"
- 🚫 "custo actual"

**Razão do Bloqueio:**
> Real cost requires actual hours worked and actual material consumption, neither of which are available in current data.

---

### HR
<a name="hr"></a>

#### `skill_risk_phases` — Fases em Risco de Competências
**Status:** ✅ USÁVEL

**Descrição:** Número de fases com menos de 3 funcionários aptos activos

**Fórmula:**
```
COUNT(fases) WHERE funcionarios_aptos_activos < 3
```

**SQL:**
```sql
SELECT COUNT(*)
            FROM (
                SELECT fas.fase_id,
                       COUNT(DISTINCT fa.func_apto_funcionario_id) FILTER (WHERE f.is_active = true) as active_capable
                FROM factory_curated.fases fas
                LEFT JOIN factory_curated.funcionarios_fases_aptos fa ON fas.fase_id = fa.func_apto_fase_id
                LEFT JOIN factory_curated.funcionarios f ON fa.func_apto_funcionario_id = f.funcionario_id
                WHERE fas.is_production = true
                GROUP BY fas.fase_id
                HAVING COUNT(DISTINCT fa.func_apto_funcionario_id) FILTER (WHERE f.is_active = true) < 3
            ) sub
```

**Unidade:** `pcs`

**Thresholds:**
- Warning: 3.0 (above)
- Block: 5.0 (above)

**Fontes de Dados:**
- `factory_curated.fases`
- `factory_curated.funcionarios_fases_aptos`
- `factory_curated.funcionarios`

**Trust Segments:**
- `fases_dimensao`
- `funcionarios_fase_ponte`
- `funcionarios_dimensao`

**Trust Mínimo:** 50

**Qualificadores:** count, risk

**Limitações:**
- ⚠️ Não considera nível de proficiência
- ⚠️ Não considera disponibilidade actual

---

#### `theoretical_labor_cost` — Custo Teórico de Mão-de-Obra
**Status:** ✅ USÁVEL

**Descrição:** Custo teórico baseado em horas previstas e valor/hora médio

**Fórmula:**
```
SUM(horas_previstas_final × valor_hora_medio)
```

**SQL:**
```sql
SELECT COALESCE(
                SUM(f.horas_previstas_final * COALESCE(func.avg_valor_hora, 15.0)),
                0
            )
            FROM factory_curated.fases_ordem_fabrico f
            CROSS JOIN (
                SELECT AVG(funcionario_valor_hora) FILTER (WHERE valor_hora_valid = true) as avg_valor_hora
                FROM factory_curated.funcionarios
            ) func
            WHERE f.is_phase_open = true
```

**Unidade:** `EUR`

**Fontes de Dados:**
- `factory_curated.fases_ordem_fabrico`
- `factory_curated.funcionarios`

**Trust Segments:**
- `fases_ordem_fabrico_horas`
- `funcionarios_dimensao`

**Trust Mínimo:** 50

**Qualificadores:** theoretical, estimated

**Limitações:**
- ⚠️ Custo é TEÓRICO (não real)
- ⚠️ Baseado em horas previstas, não trabalhadas
- ⚠️ Valor/hora é média, pode não reflectir funcionários reais

**Claims Proibidas:**
- 🚫 "custo real"
- 🚫 "custo efectivo"
- 🚫 "custo actual"

---

#### `productivity_individual` — Produtividade Individual
**Status:** 🚫 BLOQUEADO

**Descrição:** Produtividade por funcionário

**Fórmula:**
```
N/A
```

**Unidade:** `pct`

**Fontes de Dados:**

**Trust Segments:**

**Trust Mínimo:** 90

**Limitações:**
- ⚠️ FuncionariosFaseOrdemFabrico apenas indica associação, não horas trabalhadas
- ⚠️ Não existem dados de clock-in/clock-out por tarefa

**Claims Proibidas:**
- 🚫 "produtividade real"
- 🚫 "eficiência individual"
- 🚫 "desempenho individual"

**Razão do Bloqueio:**
> Individual productivity requires actual hours worked per employee per task. FuncionariosFaseOrdemFabrico only indicates 'who was associated', not actual hours.

---

### FACTORY
<a name="factory"></a>

#### `wip_orders` — WIP (Orders)
**Status:** ✅ USÁVEL

**Descrição:** Número de ordens de fabrico em aberto (não concluídas)

**Fórmula:**
```
COUNT(ordens) WHERE data_acabamento IS NULL
```

**SQL:**
```sql
SELECT COUNT(*) 
            FROM factory_curated.ordens_fabrico 
            WHERE of_data_acabamento IS NULL
```

**Unidade:** `pcs`

**Fontes de Dados:**
- `factory_curated.ordens_fabrico`

**Trust Segments:**
- `ordens_fabrico`

**Trust Mínimo:** 50

**Qualificadores:** count

**Limitações:**
- ⚠️ Conta apenas ordens sem data de acabamento
- ⚠️ Não distingue entre ordens pausadas e em progresso

---

#### `wip_hours` — WIP (Horas)
**Status:** ✅ USÁVEL

**Descrição:** Total de horas previstas em fases abertas de ordens abertas

**Fórmula:**
```
SUM(horas_previstas_final) WHERE fase em aberto AND ordem em aberto
```

**SQL:**
```sql
SELECT COALESCE(SUM(horas_previstas_final), 0)
            FROM factory_curated.fases_ordem_fabrico f
            JOIN factory_curated.ordens_fabrico o ON f.fase_of_of_id = o.of_id
            WHERE f.is_phase_open = true AND o.is_open = true
```

**Unidade:** `hours`

**Thresholds:**
- Warning: 10000.0 (any)

**Fontes de Dados:**
- `factory_curated.fases_ordem_fabrico`
- `factory_curated.ordens_fabrico`

**Trust Segments:**
- `fases_ordem_fabrico_horas`

**Trust Mínimo:** 50

**Qualificadores:** theoretical, estimated

**Limitações:**
- ⚠️ Horas são TEÓRICAS (não reais)
- ⚠️ 56.6% das horas imputadas por standard
- ⚠️ Não considera multitarefa

---

#### `backlog_hours` — Backlog Total (Horas)
**Status:** ✅ USÁVEL

**Descrição:** Total de horas previstas de trabalho pendente

**Fórmula:**
```
SUM(horas_previstas_final) WHERE fase em aberto
```

**SQL:**
```sql
SELECT COALESCE(SUM(horas_previstas_final), 0)
            FROM factory_curated.fases_ordem_fabrico
            WHERE is_phase_open = true
```

**Unidade:** `hours`

**Fontes de Dados:**
- `factory_curated.fases_ordem_fabrico`

**Trust Segments:**
- `fases_ordem_fabrico_horas`
- `standards_produto_fase`

**Trust Mínimo:** 50

**Qualificadores:** theoretical

**Limitações:**
- ⚠️ Backlog TEÓRICO sem calendário real
- ⚠️ Horas podem ser imputadas por standard
- ⚠️ Não considera setups ou paragens

---

#### `backlog_days_max` — Backlog Máximo (Dias)
**Status:** ✅ USÁVEL

**Descrição:** Máximo de dias de backlog teórico na fase mais carregada

**Fórmula:**
```
MAX(backlog_hours / capacity_hours_day) por fase produtiva
```

**SQL:**
```sql
SELECT MAX(backlog_hours / NULLIF(capacity_hours_day, 0))
            FROM (
                SELECT fase_of_fase_id, 
                       SUM(horas_previstas_final) as backlog_hours,
                       MAX(fase_capacidade_horas_dia) as capacity_hours_day
                FROM factory_curated.fases_ordem_fabrico f
                JOIN factory_curated.fases fas ON f.fase_of_fase_id = fas.fase_id
                WHERE f.is_phase_open = true AND fas.is_production = true
                GROUP BY fase_of_fase_id
            ) sub
```

**Unidade:** `days`

**Thresholds:**
- Warning: 10.0 (above)
- Block: 30.0 (above)

**Fontes de Dados:**
- `factory_curated.fases_ordem_fabrico`
- `factory_curated.fases`

**Trust Segments:**
- `fases_ordem_fabrico_horas`
- `fases_dimensao`

**Trust Mínimo:** 50

**Qualificadores:** theoretical, maximum

**Limitações:**
- ⚠️ Dias são TEÓRICOS (capacidade teórica)
- ⚠️ Não considera turnos ou paragens
- ⚠️ Fase com maior backlog relativo

---

#### `lead_time_avg` — Lead Time Médio (Dias)
**Status:** ✅ USÁVEL

**Descrição:** Tempo médio desde criação até conclusão de ordens

**Fórmula:**
```
AVG(data_acabamento - data_criacao) para ordens concluídas
```

**SQL:**
```sql
SELECT AVG(EXTRACT(EPOCH FROM (of_data_acabamento - of_data_criacao)) / 86400)
            FROM factory_curated.ordens_fabrico
            WHERE of_data_acabamento IS NOT NULL
```

**Unidade:** `days`

**Fontes de Dados:**
- `factory_curated.ordens_fabrico`

**Trust Segments:**
- `ordens_fabrico`

**Trust Mínimo:** 70

**Qualificadores:** historical, average

**Limitações:**
- ⚠️ Baseado em ordens concluídas
- ⚠️ Inclui tempo de espera e não apenas trabalho

---

#### `oee` — OEE
**Status:** 🚫 BLOQUEADO

**Descrição:** Overall Equipment Effectiveness

**Fórmula:**
```
Availability × Performance × Quality
```

**Unidade:** `pct`

**Fontes de Dados:**

**Trust Segments:**

**Trust Mínimo:** 90

**Limitações:**
- ⚠️ OEE requer dados de máquina não disponíveis
- ⚠️ Availability actual (fases_started/total) não é OEE Availability
- ⚠️ Necessários: machine downtime, planned production time

**Claims Proibidas:**
- 🚫 "OEE real"
- 🚫 "eficiência real"
- 🚫 "disponibilidade real"

**Razão do Bloqueio:**
> OEE requires machine downtime data. Current 'Availability' definition (phases_started/total) is conceptually incorrect for OEE. OEE Availability = (Run Time / Planned Production Time).

---

#### `otd` — On-Time Delivery
**Status:** 🚫 BLOQUEADO

**Descrição:** Percentagem de ordens entregues dentro do prazo

**Fórmula:**
```
(ordens_on_time / total_ordens) × 100
```

**Unidade:** `pct`

**Fontes de Dados:**

**Trust Segments:**

**Trust Mínimo:** 90

**Limitações:**
- ⚠️ Não existe due_date/data prometida nos dados
- ⚠️ Impossível calcular OTD sem data de entrega prometida

**Claims Proibidas:**
- 🚫 "OTD real"
- 🚫 "pontualidade real"

**Razão do Bloqueio:**
> OTD (On-Time Delivery) requires customer due dates which are not available. OrdensFabrico does not have 'due_date' or 'promised_delivery_date' fields.

---

#### `mold_conflicts` — Conflitos de Molde
**Status:** ✅ USÁVEL

**Descrição:** Número de potenciais conflitos de molde (sobreposição de ocupação)

**Fórmula:**
```
COUNT(sobreposições) WHERE molde_occupancy se sobrepõe
```

**SQL:**
```sql
WITH mold_windows AS (
                SELECT molde_of_id, mold_occupancy_start, mold_occupancy_end, fase_of_id
                FROM factory_curated.fases_ordem_fabrico
                WHERE molde_of_id IS NOT NULL AND mold_occupancy_start IS NOT NULL
            )
            SELECT COUNT(*)
            FROM mold_windows a
            JOIN mold_windows b ON a.molde_of_id = b.molde_of_id 
                AND a.fase_of_id < b.fase_of_id
                AND a.mold_occupancy_start < b.mold_occupancy_end
                AND a.mold_occupancy_end > b.mold_occupancy_start
```

**Unidade:** `pcs`

**Fontes de Dados:**
- `factory_curated.fases_ordem_fabrico`

**Trust Segments:**
- `fases_ordem_fabrico_data_prevista`
- `moldes_dimensao`

**Trust Mínimo:** 30

**Qualificadores:** potential, heuristic

**Limitações:**
- ⚠️ Conflitos são POTENCIAIS (heurística de 12h ocupação)
- ⚠️ DataPrevista só existe para ~4.8% das fases
- ⚠️ Não considera calendário real do molde

---

### QUALITY
<a name="quality"></a>

#### `quality_fpy` — First Pass Yield
**Status:** ✅ USÁVEL

**Descrição:** Percentagem de ordens sem erros na primeira passagem

**Fórmula:**
```
(ordens_sem_erro / total_ordens) × 100
```

**SQL:**
```sql
SELECT (
                COUNT(DISTINCT o.of_id) FILTER (WHERE e.erro_of_id IS NULL)::float /
                NULLIF(COUNT(DISTINCT o.of_id), 0) * 100
            )
            FROM factory_curated.ordens_fabrico o
            LEFT JOIN factory_curated.ordem_fabrico_erros e ON o.of_id = e.erro_of_id
```

**Unidade:** `pct`

**Thresholds:**
- Warning: 90.0 (below)
- Block: 70.0 (below)

**Fontes de Dados:**
- `factory_curated.ordens_fabrico`
- `factory_curated.ordem_fabrico_erros`

**Trust Segments:**
- `ordens_fabrico`
- `qualidade_transacional`

**Trust Mínimo:** 60

**Qualificadores:** partial

**Limitações:**
- ⚠️ 41.5% dos erros não têm fase culpada identificada
- ⚠️ Não distingue gravidade dos erros

---

#### `error_rate` — Taxa de Erros
**Status:** ✅ USÁVEL

**Descrição:** Número de erros por ordem

**Fórmula:**
```
total_erros / total_ordens
```

**SQL:**
```sql
SELECT COUNT(e.*)::float / NULLIF(COUNT(DISTINCT o.of_id), 0)
            FROM factory_curated.ordens_fabrico o
            LEFT JOIN factory_curated.ordem_fabrico_erros e ON o.of_id = e.erro_of_id
```

**Unidade:** `errors/order`

**Fontes de Dados:**
- `factory_curated.ordem_fabrico_erros`
- `factory_curated.ordens_fabrico`

**Trust Segments:**
- `qualidade_transacional`
- `ordens_fabrico`

**Trust Mínimo:** 60

**Qualificadores:** ratio

**Limitações:**
- ⚠️ Inclui todos os erros registados
- ⚠️ Não pondera por gravidade

---

## KPIs Bloqueados
<a name="kpis-bloqueados"></a>

Os seguintes KPIs **NÃO PODEM** ser calculados com os dados actuais:

| KPI | Domínio | Razão | Dados Necessários |
|-----|---------|-------|-------------------|
| `oee` | factory | OEE requires machine downtime data. Current 'Availability' d... | — |
| `otd` | factory | OTD (On-Time Delivery) requires customer due dates which are... | — |
| `productivity_individual` | hr | Individual productivity requires actual hours worked per emp... | — |
| `real_cost_per_order` | profit | Real cost requires actual hours worked and actual material c... | — |

### Como Desbloquear

#### `oee` — OEE

**Dados Necessários:**
- `machine_downtime`
- `planned_production_time`

**Como Desbloquear:**
> Integrar dados MES/SCADA com estados de máquina e tempos de paragem.

#### `otd` — On-Time Delivery

**Dados Necessários:**
- `customer_due_date`
- `promised_delivery_date`

**Como Desbloquear:**
> Adicionar campo due_date às ordens via integração ERP/CRM.

#### `productivity_individual` — Produtividade Individual

**Dados Necessários:**
- `employee_time_tracking`
- `actual_hours_per_task`

**Como Desbloquear:**
> Integrar sistema de registo de tempo ou MES com clock-in/out individual.

#### `real_cost_per_order` — Custo Real por Ordem

**Dados Necessários:**
- `actual_labor_hours`
- `actual_material_consumption`

**Como Desbloquear:**
> Integrar com sistema de recolha de dados do chão de fábrica.


## Trust Index Guide
<a name="trust-index-guide"></a>

O Trust Index indica a confiança nos dados usados para calcular um KPI.

| Score | Nível | Descrição | Acção |
|-------|-------|-----------|-------|
| 90-100 | HIGHLY_RELIABLE | Dados altamente fiáveis | Usar com confiança |
| 75-89 | RELIABLE_WITH_VALIDATION | Dados fiáveis com ressalvas | Validar em casos críticos |
| 55-74 | USEFUL_FOR_TRENDS | Útil para tendências | Não usar para promessas |
| <55 | HEURISTIC_ONLY | Apenas heurística | Usar só como indicador |

### Trust por Segmento

| Segmento | Score | Justificação |
|----------|-------|---------------|
| `erros_catalogo` | 🟢 92 | Semântica estável |
| `fases_dimensao` | 🟢 85 | Estrutura sólida |
| `ordens_fabrico` | 🟢 82 | Boa base para WIP |
| `funcionarios_dimensao` | 🟢 75 | ValorHora com zeros |
| `moldes_dimensao` | 🟡 70 | Estados sem dicionário |
| `qualidade_transacional` | 🟡 67 | 41.5% sem fase culpada |
| `fases_ordem_fabrico_tempos` | 🟡 62 | Muitas durações 0 |
| `standards_produto_fase` | 🟡 60 | Duplicados por chave |
| `fases_ordem_fabrico_horas` | 🟡 58 | 56.6% zeros |
| `funcionarios_fase_ponte` | 🟡 55 | Não dá horas reais |
| `fases_ordem_fabrico_data_prevista` | 🔴 35 | Só 4.8% preenchido |

---

*Gerado por `scripts/generate_kpi_catalog.py` em 2026-01-27T18:01:09.646103*
