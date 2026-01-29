# Factory Data Product — Especificação Técnica

**Versão:** 1.1.0  
**Data:** 2026-01-27  
**Estado:** APROVADO PARA IMPLEMENTAÇÃO  
**Classificação:** Enterprise-Grade / Palantir-Level  
**Base de Dados:** `prodplan_factory` (separada do `prodplan` principal)

---

## 1. Visão Geral e Não-Objetivos

### 1.1 Visão Geral

O **Factory Data Product** é uma camada de dados estruturada que transforma o ficheiro Excel `Folha_IA_extra.xlsx` (dados de produção de kayaks) numa base de dados PostgreSQL auditável, curada e consumível pelo backend **ProdPlan ONE**.

O objectivo central é:
1. **Formalizar** o que já existe implicitamente no backend.
2. **Proteger** o sistema contra afirmações que os dados não suportam.
3. **Criar uma fundação sólida** para evolução futura.

### 1.2 Não-Objectivos (Explicitamente Excluídos)

O Factory Data Product **NÃO** pretende:

| Não-Objectivo | Razão Técnica |
|---------------|---------------|
| Calcular **custo real** por ordem | Não existem horas reais por funcionário no Excel |
| Calcular **produtividade individual** | Tabela `FuncionariosFaseOrdemFabrico` não tem horas trabalhadas |
| Calcular **OEE real** | Não existem dados de paragens de máquina |
| Calcular **capacidade real** | Capacidade no Excel é teórica (NumFuncionarios × 8h) |
| Garantir **OTD oficial** | Não existe campo `due_date` / promessa comercial |
| Fazer **planeamento diário/turno** | `DataPrevista` só existe em 4.8% das fases |

### 1.3 Princípio Fundamental

> **Regra de Ouro:** Todo o output do sistema DEVE distinguir claramente entre:
> - **Teórico** vs **Real**
> - **Observado** vs **Imputado**
> - **Completo** vs **Parcial**

---

## 2. Estado Actual do Backend ProdPlan ONE

### 2.1 Arquitectura Existente

O backend ProdPlan ONE está organizado em módulos:

```
prodplan-one/src/
├── core/           # Dados mestres (produtos, máquinas, funcionários, clientes)
├── plan/           # Planeamento (ordens, schedules, capacidade, MRP)
├── profit/         # Custos (COGS, pricing, cenários)
├── hr/             # Recursos humanos (alocações, produtividade, payroll)
├── supply/         # Inventário (ABC, ROP, forecasting)
├── dqa/            # Data Quality (Trust Index, quality gates, auto-repair)
├── copilot/        # AI Assistant (RAG, guardrails, runbooks)
└── shared/         # Infraestrutura (database, events, auth, metrics)
```

### 2.2 Modelos de Dados Existentes

| Schema | Tabela | Descrição | Estado |
|--------|--------|-----------|--------|
| `plan` | `production_orders` | Ordens de fabrico | IMPLEMENTADO |
| `plan` | `production_schedules` | Schedules de operações | IMPLEMENTADO |
| `core` | `products` | Catálogo de produtos | IMPLEMENTADO |
| `core` | `machines` | Máquinas/recursos | IMPLEMENTADO |
| `core` | `employees` | Funcionários | IMPLEMENTADO |
| `core` | `operations` | Operações/fases | IMPLEMENTADO |
| `profit` | `cost_calculations` | Cálculos COGS | IMPLEMENTADO |
| `hr` | `employee_productivity` | Produtividade | IMPLEMENTADO |
| `hr` | `labor_allocations` | Alocações | IMPLEMENTADO |

### 2.3 Serviços Existentes

| Serviço | Localização | Funcionalidade |
|---------|-------------|----------------|
| `CapacityService` | `src/plan/services/capacity_service.py` | Análise de capacidade por máquina/período |
| `SchedulingService` | `src/plan/services/scheduling_service.py` | Geração de schedules (heurístico/CP-SAT) |
| `CostService` | `src/profit/services/cost_service.py` | Cálculo COGS com breakdown |
| `ProductivityService` | `src/hr/services/productivity_service.py` | Tracking de produtividade |
| `TrustIndexCalculator` | `src/dqa/trust_index.py` | Cálculo de Trust Index (0-1) |

### 2.4 APIs Existentes

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/capacity/analysis` | POST | Análise de utilização de capacidade |
| `/capacity/machines/{id}/availability` | GET | Disponibilidade de máquina |
| `/schedule/generate` | POST | Geração de schedule |
| `/kpis/snapshot` | GET | Snapshot de KPIs (OEE, availability, etc.) |
| `/cogs/calculate` | POST | Cálculo de COGS |
| `/productivity/record` | POST | Registo de produtividade |

### 2.5 Backend Evidence Inventory (OBRIGATÓRIO)

> **REGRA:** Nenhuma afirmação sobre o backend pode ser feita sem evidência verificada no código.
> Todas as entradas abaixo foram verificadas em `prodplan-one/src/` em 2026-01-27.

#### 2.5.1 Módulos Verificados

| Módulo | Path Real | Verificado | Observação |
|--------|-----------|------------|------------|
| `core/` | `prodplan-one/src/core/` | SIM | Dados mestres (produtos, máquinas, funcionários) |
| `plan/` | `prodplan-one/src/plan/` | SIM | Planeamento (ordens, schedules, capacidade) |
| `profit/` | `prodplan-one/src/profit/` | SIM | Custos (COGS, pricing, cenários) |
| `hr/` | `prodplan-one/src/hr/` | SIM | RH (alocações, produtividade, payroll) |
| `supply/` | `prodplan-one/src/supply/` | SIM | Inventário (ABC, ROP, forecasting) |
| `dqa/` | `prodplan-one/src/dqa/` | SIM | Data Quality (Trust Index, gates, auto-repair) |
| `copilot/` | `prodplan-one/src/copilot/` | SIM | AI Assistant (RAG, guardrails, runbooks) |
| `shared/` | `prodplan-one/src/shared/` | SIM | Infraestrutura (database, events, auth) |

#### 2.5.2 Serviços Verificados

| Serviço | Ficheiro | Linha | Classe | Verificado |
|---------|----------|-------|--------|------------|
| `CapacityService` | `src/plan/services/capacity_service.py` | 74 | `class CapacityService:` | SIM |
| `SchedulingService` | `src/plan/services/scheduling_service.py` | 28 | `class SchedulingService:` | SIM |
| `CostService` | `src/profit/services/cost_service.py` | 23 | `class CostService:` | SIM |
| `ProductivityService` | `src/hr/services/productivity_service.py` | 22 | `class ProductivityService:` | SIM |
| `TrustIndexCalculator` | `src/dqa/trust_index.py` | 27 | `class TrustIndexCalculator:` | SIM |
| `MRPService` | `src/plan/services/mrp_service.py` | 23 | `class MRPService:` | SIM |
| `AllocationService` | `src/hr/services/allocation_service.py` | 28 | `class AllocationService:` | SIM |
| `PricingService` | `src/profit/services/pricing_service.py` | 22 | `class PricingService:` | SIM |
| `PayrollService` | `src/hr/services/payroll_service.py` | 22 | `class PayrollService:` | SIM |
| `CopilotService` | `src/copilot/service.py` | 35 | `class CopilotService:` | SIM |

#### 2.5.3 APIs Verificadas (grep: `@router\.(get|post)`)

| Endpoint | Ficheiro | Método | Verificado |
|----------|----------|--------|------------|
| `/capacity/analysis` | `src/plan/api/capacity.py` | POST | SIM |
| `/schedule/generate` | `src/plan/api/schedule.py` | POST | SIM |
| `/kpis/snapshot` | `src/profit/api/kpis.py` | GET | SIM |
| `/productivity/record` | `src/hr/api/productivity.py` | POST | SIM |
| `/copilot/ask` | `src/copilot/api.py` | POST | SIM |

#### 2.5.4 Entidades NÃO CONFIRMADAS

> **AVISO:** As seguintes afirmações requerem verificação adicional ou não existem:

| Claim | Estado | Acção |
|-------|--------|-------|
| Schema `plan.production_orders` | NÃO CONFIRMADO em DB real | Verificar migrations |
| Tabela `core.employees` com `valor_hora` | NÃO CONFIRMADO | Verificar modelo SQLAlchemy |
| OEE real calculado | NÃO APLICÁVEL | Dados de máquina não existem no Excel |

---

## 3. Funcionalidades Já Existentes e o Seu Grau de Maturidade

### 3.1 Inventário de Funcionalidades

| ID | Funcionalidade | Módulo | Ficheiro | Estado | Dados Consumidos |
|----|----------------|--------|----------|--------|------------------|
| F01 | Gestão de Ordens de Fabrico | plan | `models/order.py` | IMPLEMENTADO | `legacy_id`, `product_id`, `status`, `dates` |
| F02 | Fases Produtivas | plan | `models/schedule.py` | IMPLEMENTADO | `operation_id`, `machine_id`, `duration` |
| F03 | Capacidade por Fase | plan | `services/capacity_service.py` | IMPLEMENTADO | `available_hours_per_day`, `scheduled_duration` |
| F04 | Tempos Reais (Início/Fim) | plan | `models/schedule.py` | PARCIAL | `actual_start`, `actual_end` |
| F05 | Planeamento Teórico | plan | `services/scheduling_service.py` | IMPLEMENTADO | `scheduled_start_date`, `scheduled_duration` |
| F06 | Análise de Gargalos | plan | `services/capacity_service.py` | PARCIAL | `utilization_percent`, `is_over_capacity` |
| F07 | Métricas Operacionais (KPIs) | profit | `api/kpis.py` | IMPLEMENTADO | `OEE`, `availability`, `performance`, `quality` |
| F08 | Cálculo de Custos (COGS) | profit | `services/cost_service.py` | IMPLEMENTADO | `material`, `labor`, `machine`, `overhead` |
| F09 | Produtividade Individual | hr | `services/productivity_service.py` | IMPLEMENTADO | `standard_hours`, `actual_hours`, `efficiency` |
| F10 | Trust Index | dqa | `trust_index.py` | IMPLEMENTADO | `completeness`, `validity`, `consistency`, `timeliness` |

### 3.2 Análise Detalhada por Funcionalidade

#### F01: Gestão de Ordens de Fabrico

**Localização:** `src/plan/models/order.py`

**Dados Consumidos:**
- `legacy_id` (int): ID da ordem no sistema legacy
- `product_id` (int): ID do produto
- `current_phase_id` (int): Fase actual
- `created_date`, `completed_date`, `transport_date` (date)
- `status` (enum): IN_PROGRESS, COMPLETED, CANCELLED

**Pressupostos Implícitos:**
1. Uma ordem está "em aberto" se `completed_date IS NULL`
2. Uma ordem está "concluída" se `status = COMPLETED`
3. O `product_type` é derivado do nome do produto (K1, K2, K4, C1, C2, C4)

**Estado:** USÁVEL AGORA

---

#### F02: Fases Produtivas

**Localização:** `src/plan/models/schedule.py`

**Dados Consumidos:**
- `operation_id` (UUID): ID da operação
- `machine_id` (UUID): Máquina atribuída
- `scheduled_duration_hours` (Decimal): Duração planeada
- `actual_start`, `actual_end` (datetime): Tempos reais

**Pressupostos Implícitos:**
1. Cada operação pertence a uma ordem
2. A duração planeada vem do standard ou do routing
3. Tempos reais só existem se a fase foi iniciada/concluída

**Estado:** USÁVEL COM RESSALVAS (tempos reais parciais)

---

#### F03: Capacidade por Fase

**Localização:** `src/plan/services/capacity_service.py`

**Dados Consumidos:**
- `available_hours_per_day` (float): Horas disponíveis por dia
- `scheduled_duration_hours` (Decimal): Duração alocada
- `period_days` (int): Granularidade do período

**Cálculos:**
```python
utilization_percent = (allocated_minutes / available_minutes) * 100
free_minutes = available_minutes - allocated_minutes
is_over_capacity = allocated_minutes > available_minutes
```

**Pressupostos Implícitos:**
1. Capacidade é teórica (sem paragens, setups, turnos)
2. Assume semana de 5 dias úteis
3. Não considera multitarefa ou sobreposição

**Estado:** USÁVEL COM RESSALVAS (capacidade teórica)

---

#### F04: Tempos Reais (Início/Fim)

**Localização:** `src/plan/models/schedule.py`

**Campos:**
- `actual_start` (datetime): Início real
- `actual_end` (datetime): Fim real
- `actual_quantity` (Decimal): Quantidade real produzida

**Pressupostos Implícitos:**
1. Tempos reais só são preenchidos quando a fase é executada
2. `actual_end - actual_start` representa tempo decorrido, NÃO homem-hora
3. Muitas fases têm duração 0 (marcadores de evento)

**Estado:** USÁVEL COM RESSALVAS (cobertura parcial, semântica ambígua)

---

#### F05: Planeamento Teórico

**Localização:** `src/plan/services/scheduling_service.py`

**Engines Disponíveis:**
- `HEURISTIC`: Regras de despacho (EDD, SPT, etc.)
- `CPSAT`: Constraint Programming (OR-Tools)
- `GENETIC`: Algoritmo genético

**Outputs:**
- `makespan_hours`: Tempo total de execução
- `total_tardiness_hours`: Atraso total
- `num_late_orders`: Ordens atrasadas
- `avg_utilization`: Utilização média

**Pressupostos Implícitos:**
1. Durações vêm do standard ou do routing
2. Não considera restrições de molde
3. Não considera competências de funcionários

**Estado:** USÁVEL COM RESSALVAS (sem restrições de molde/competências)

---

#### F06: Análise de Gargalos

**Localização:** `src/plan/services/capacity_service.py`

**Cálculo:**
```python
severity = "critical" if utilization >= 100 else "warning" if utilization >= 90 else "normal"
```

**Pressupostos Implícitos:**
1. Gargalo = fase com utilização > 100%
2. Capacidade é teórica
3. Não considera sequenciamento ou dependências

**Estado:** USÁVEL COM RESSALVAS (gargalo teórico, não real)

---

#### F07: Métricas Operacionais (KPIs)

**Localização:** `src/profit/api/kpis.py`

**KPIs Calculados:**
- `OEE` = Availability × Performance × Quality
- `Availability` = fases iniciadas / total fases
- `Performance` = tempo padrão / tempo real
- `Quality (FPY)` = ordens sem erros / total ordens

**Pressupostos Implícitos:**
1. OEE é calculado com dados disponíveis (pode ser incompleto)
2. Performance assume que `actual_end - actual_start` é tempo produtivo
3. Quality assume que ordens completadas = ordens sem erros (simplificação)

> **CRÍTICO:** A definição de `Availability` usada (`fases iniciadas / total fases`) 
> **NÃO É** a definição standard de OEE. Em OEE real:
> - Availability = Tempo Disponível / Tempo Planeado (requer dados de paragens de máquina)
> 
> Sem dados de paragens de máquina, **qualquer cálculo de OEE é conceitualmente inválido**.

**Estado:** **NÃO USÁVEL** (não "usável com ressalvas" — conceitualmente inválido sem dados de máquina)

---

#### F08: Cálculo de Custos (COGS)

**Localização:** `src/profit/services/cost_service.py`

**Componentes:**
- Material (BOM)
- Labor (alocações)
- Machine (uso de máquina)
- Setup (preparação)
- Overhead (indirectos)
- Scrap (desperdício)

**Pressupostos Implícitos:**
1. Custos de labor vêm de `ValorHora × horas alocadas`
2. Horas alocadas são teóricas (não reais)
3. Scrap rate é parametrizado (default: 2%)

**Estado:** USÁVEL COM RESSALVAS (custo teórico, não real)

---

#### F09: Produtividade Individual

**Localização:** `src/hr/services/productivity_service.py`

**Cálculos:**
```python
efficiency = (standard_hours / actual_hours) * 100
quality = (good_quantity / actual_quantity) * 100
bonus_eligible = efficiency >= 100 and quality >= 98
```

**Pressupostos Implícitos:**
1. Requer `standard_hours` e `actual_hours` preenchidos
2. Requer `actual_quantity` e `good_quantity` preenchidos
3. Dados do Excel NÃO suportam isto (não há horas reais por funcionário)

**Estado:** NÃO USÁVEL COM DADOS DO EXCEL

---

#### F10: Trust Index

**Localização:** `src/dqa/trust_index.py`

**Componentes (pesos):**
- Completeness (30%): % campos obrigatórios preenchidos
- Validity (30%): % valores dentro de ranges válidos
- Consistency (20%): Conflitos cross-field
- Timeliness (20%): Latência vs SLA

**Cálculo:**
```python
trust_index = completeness * 0.3 + validity * 0.3 + consistency * 0.2 + timeliness * 0.2
```

**Estado:** USÁVEL AGORA

---

## 4. Cruzamento Funcionalidades ↔ Dados do Folha_IA_extra.xlsx

### 4.1 Tabela de Cruzamento Completa

| Funcionalidade | Dados do Excel | Cobertura (%) | Trust Index | Estado | O que PODE afirmar | O que NÃO PODE afirmar | Risco sem Curadoria |
|----------------|----------------|---------------|-------------|--------|-------------------|------------------------|---------------------|
| **Backlog por Fase** | `FasesOrdemFabrico.HorasPrevistas`, `Fases.CapacidadeHorasDia` | 93.8% (após fallback) | 58 | USÁVEL COM AVISOS | "Backlog teórico estimado: X horas" | "Backlog real", "Tempo de espera garantido" | ALTO: Pode subestimar backlog se standards incorrectos |
| **Gargalo Teórico (TOC)** | `FasesOrdemFabrico.HorasPrevistas`, `Fases.CapacidadeHorasDia` | 93.8% | 58 | USÁVEL COM AVISOS | "Gargalo provável: Fase X com Y dias de backlog" | "Gargalo real", "Fase crítica confirmada" | ALTO: Capacidade é teórica, sem paragens |
| **Lead Time Histórico** | `OrdensFabrico.DataCriacao`, `OrdensFabrico.DataAcabamento` | 95.0% | 82 | USÁVEL AGORA | "Lead time médio histórico: X dias" | "Lead time garantido", "Tempo de entrega prometido" | MÉDIO: Não considera variabilidade |
| **Conflitos de Molde** | `FasesOrdemFabrico.MoldeOfId`, `FasesOrdemFabrico.DataPrevista` | 4.8% | 35 | USÁVEL COM AVISOS | "Conflito potencial detectado (assumindo ocupação 12h)" | "Conflito confirmado", "Agenda do molde" | ALTO: Cobertura muito baixa |
| **Qualidade por Fase/Molde** | `OrdemFabricoErros.FaseOfCulpada`, `OrdemFabricoErros.Erro_Descricao` | 58.5% | 67 | USÁVEL COM AVISOS | "Erros mais frequentes: X, Y, Z" | "Fase culpada confirmada", "Root cause" | MÉDIO: 41.5% sem fase culpada |
| **Risco de Competências** | `FuncionariosFasesAptos`, `Funcionarios.Activo` | 100% | 55 | USÁVEL COM AVISOS | "Fases com poucos funcionários aptos: X, Y" | "Risco real de paragem", "Falta de pessoal confirmada" | MÉDIO: Não considera turnos/férias |
| **Custos de Produção** | `Funcionarios.ValorHora`, `FasesOrdemFabrico.HorasPrevistas` | 85.7% (ValorHora válido) | 58 | USÁVEL COM AVISOS | "Custo teórico estimado: €X" | "Custo real", "Custo por ordem confirmado" | ALTO: Sem horas reais por funcionário |
| **Capacidade Diária** | `Fases.CapacidadeHorasDia`, `Fases.NumeroFuncionarios` | 100% | 85 | USÁVEL COM AVISOS | "Capacidade teórica: X horas/dia" | "Capacidade real", "Disponibilidade confirmada" | MÉDIO: Teórica, sem paragens/turnos |
| **OTD / Promessas de Entrega** | N/A | 0% | 0 | NÃO USÁVEL | N/A | "OTD", "Entrega garantida", "Promessa ao cliente" | CRÍTICO: Não existe due_date |
| **Produtividade Individual** | `FuncionariosFaseOrdemFabrico` (sem horas) | 0% | 55 | NÃO USÁVEL | N/A | "Produtividade de X", "Eficiência individual" | CRÍTICO: Não há horas reais |
| **OEE Real** | N/A | 0% | 0 | **NÃO USÁVEL** | N/A | "OEE", "Eficiência global", "Availability" | **CRÍTICO**: Availability ≠ "fases iniciadas/total" (definição errada). OEE requer dados de paragens de máquina que não existem no Excel |

### 4.2 Matriz de Decisão

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MATRIZ DE DECISÃO - FACTORY DATA PRODUCT                  │
├─────────────────────┬───────────────┬───────────────┬───────────────────────┤
│ Trust Index         │ Cobertura     │ Estado        │ Acção                 │
├─────────────────────┼───────────────┼───────────────┼───────────────────────┤
│ ≥ 80                │ ≥ 90%         │ USÁVEL AGORA  │ Usar sem restrições   │
│ 60-79               │ ≥ 70%         │ USÁVEL AVISOS │ Usar com warnings     │
│ 40-59               │ ≥ 50%         │ USÁVEL AVISOS │ Usar com warnings     │
│ < 40                │ < 50%         │ NÃO USÁVEL    │ Bloquear funcionalidade│
└─────────────────────┴───────────────┴───────────────┴───────────────────────┘
```

---

## 5. Arquitectura Proposta do Factory Data Product

### 5.1 Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FACTORY DATA PRODUCT                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   EXCEL      │    │    RAW       │    │   CURATED    │                   │
│  │ Folha_IA_    │───▶│   LAYER      │───▶│    LAYER     │                   │
│  │ extra.xlsx   │    │ (PostgreSQL) │    │ (PostgreSQL) │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│        │                    │                    │                           │
│        │                    │                    │                           │
│        ▼                    ▼                    ▼                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   CLI        │    │    META      │    │   SEMANTIC   │                   │
│  │   Ingest     │    │   LAYER      │    │    LAYER     │                   │
│  │              │    │ (Audit/Hash) │    │   (Views)    │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                                                 │                            │
│                                                 ▼                            │
│                                          ┌──────────────┐                   │
│                                          │  PRODPLAN    │                   │
│                                          │    ONE       │                   │
│                                          │   BACKEND    │                   │
│                                          └──────────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Camadas

| Camada | Schema | Descrição | Responsabilidade |
|--------|--------|-----------|------------------|
| **RAW** | `factory_raw` | Dados originais do Excel | Preservar dados como estão, auditável |
| **CURATED** | `factory_curated` | Dados normalizados | Validações, flags, campos derivados |
| **META** | `factory_meta` | Metadados de ingestão | Hashes, timestamps, versões |
| **SEMANTIC** | `factory_semantic` | Views de negócio | WIP, backlog, bottlenecks, quality |

---

## 6. Modelo de Dados PostgreSQL (RAW, CURATED, META)

### 6.0 Data Dictionary RAW (Mapeamento Excel → PostgreSQL)

> **OBRIGATÓRIO:** Todo o campo do Excel tem de ser mapeado explicitamente.
> Dados verificados em `Folha_IA_extra.xlsx` em 2026-01-27.

#### 6.0.1 FasesOrdemFabrico (529,450 linhas)

| Coluna Excel | Coluna PostgreSQL | Tipo | Nullability | Regra |
|--------------|-------------------|------|-------------|-------|
| `FaseOf_Id` | `fase_of_id` | VARCHAR(50) | NOT NULL | PK de negócio |
| `FaseOf_OfId` | `fase_of_of_id` | VARCHAR(50) | NOT NULL | FK para OrdensFabrico |
| `FaseOf_Inicio` | `fase_of_inicio` | TIMESTAMP | NULL | Datetime |
| `FaseOf_Fim` | `fase_of_fim` | TIMESTAMP | NULL | Datetime |
| `FaseOf_DataPrevista` | `fase_of_data_prevista` | TIMESTAMP | NULL | Só 4.8% preenchido |
| `FaseOf_Coeficiente` | `fase_of_coeficiente` | NUMERIC(10,4) | NULL | MULTIPLICADOR, não horas |
| `FaseOf_CoeficienteX` | `fase_of_coeficiente_x` | NUMERIC(10,4) | NULL | |
| `FaseOf_FaseId` | `fase_of_fase_id` | VARCHAR(50) | NULL | FK para Fases |
| `FaseOf_Peso` | `fase_of_peso` | NUMERIC(10,4) | NULL | |
| `FaseOf_Retorno` | `fase_of_retorno` | INTEGER | NULL | |
| `FaseOf_Turno` | `fase_of_turno` | VARCHAR(20) | NULL | |
| `FaseOf_Sequencia` | `fase_of_sequencia` | INTEGER | NULL | |
| `MoldeOfId` | `molde_of_id` | VARCHAR(50) | NULL | FK para Moldes |
| `MoldeNome` | `molde_nome` | VARCHAR(255) | NULL | Replicado |
| `MoldeNumeroPocosId` | `molde_numero_pocos_id` | VARCHAR(50) | NULL | Replicado |
| `MoldeModeloId` | `molde_modelo_id` | VARCHAR(50) | NULL | Replicado para validação |
| `MoldeTamanhoId` | `molde_tamanho_id` | VARCHAR(50) | NULL | Replicado para validação |
| **`FaseOf_HorasPrevistas`** | **`fase_of_horas_previstas`** | **NUMERIC(10,4)** | NULL | **CAMPO CRÍTICO - 56.6% zeros** |

#### 6.0.2 OrdensFabrico (27,911 linhas)

| Coluna Excel | Coluna PostgreSQL | Tipo | Nullability | Regra |
|--------------|-------------------|------|-------------|-------|
| `Of_Id` | `of_id` | VARCHAR(50) | NOT NULL | PK de negócio |
| `Of_DataCriacao` | `of_data_criacao` | TIMESTAMP | NULL | |
| `Of_DataAcabamento` | `of_data_acabamento` | TIMESTAMP | NULL | NULL = aberta |
| `Of_ProdutoId` | `of_produto_id` | VARCHAR(50) | NULL | FK para Modelos |
| `Of_FaseId` | `of_fase_id` | VARCHAR(50) | NULL | Fase actual |
| `Of_DataTransporte` | `of_data_transporte` | TIMESTAMP | NULL | |

#### 6.0.3 Funcionarios (301 linhas)

| Coluna Excel | Coluna PostgreSQL | Tipo | Nullability | Regra |
|--------------|-------------------|------|-------------|-------|
| `Funcionario_Id` | `funcionario_id` | VARCHAR(50) | NOT NULL | PK de negócio |
| `Funcionario_Nome` | `funcionario_nome` | VARCHAR(255) | NULL | PII |
| `Funcionario_Activo` | `funcionario_activo` | INTEGER | NULL | 1=activo |
| `FuncionarioValorHora` | `funcionario_valor_hora` | NUMERIC(10,2) | NULL | 0=inválido, PII |

#### 6.0.4 Fases (dimensão, ~30 linhas)

| Coluna Excel | Coluna PostgreSQL | Tipo | Nullability | Regra |
|--------------|-------------------|------|-------------|-------|
| `Fase_Id` | `fase_id` | VARCHAR(50) | NOT NULL | PK de negócio |
| `Fase_Nome` | `fase_nome` | VARCHAR(255) | NULL | |
| `Fase_Sequencia` | `fase_sequencia` | INTEGER | NULL | |
| `Fase_Producao` | `fase_producao` | INTEGER | NULL | 1=produtiva |
| `Fase_Automatica` | `fase_automatica` | INTEGER | NULL | |
| `Fase_NumeroFuncionarios` | `fase_numero_funcionarios` | INTEGER | NULL | |
| `Fase_CapacidadeHorasDia` | `fase_capacidade_horas_dia` | NUMERIC(10,2) | NULL | Teórica |

#### 6.0.5 FasesStandardModelos (standards)

| Coluna Excel | Coluna PostgreSQL | Tipo | Nullability | Regra |
|--------------|-------------------|------|-------------|-------|
| `ProdutoFase_ProdutoId` | `produto_fase_produto_id` | VARCHAR(50) | NOT NULL | Parte da PK composta |
| `ProdutoFase_FaseId` | `produto_fase_fase_id` | VARCHAR(50) | NOT NULL | Parte da PK composta |
| `ProdutoFase_Sequencia` | `produto_fase_sequencia` | INTEGER | NULL | |
| `ProdutoFase_Coeficiente` | `produto_fase_coeficiente` | NUMERIC(10,4) | NULL | |
| `ProdutoFase_CoeficienteX` | `produto_fase_coeficiente_x` | NUMERIC(10,4) | NULL | |
| `ProdutoFase_HorasPrevistas` | `produto_fase_horas_previstas` | NUMERIC(10,4) | NULL | Fallback para derivação |

#### 6.0.6 Moldes (510 linhas)

| Coluna Excel | Coluna PostgreSQL | Tipo | Nullability | Regra |
|--------------|-------------------|------|-------------|-------|
| `MoldeId` | `molde_id` | VARCHAR(50) | NOT NULL | PK de negócio |
| `MoldeNome` | `molde_nome` | VARCHAR(255) | NULL | Pode ter valores mistos |
| `MoldeEstado` | `molde_estado` | VARCHAR(50) | NULL | Sem dicionário |
| `MoldeModelo` | `molde_modelo` | VARCHAR(255) | NULL | |
| `MoldeNumeroPocosId` | `molde_numero_pocos_id` | VARCHAR(50) | NULL | |
| `MoldeModeloId` | `molde_modelo_id` | VARCHAR(50) | NULL | |
| `MoldeTamanhoId` | `molde_tamanho_id` | VARCHAR(50) | NULL | |

#### 6.0.7 OrdemFabricoErros (89,836 linhas)

| Coluna Excel | Coluna PostgreSQL | Tipo | Nullability | Regra |
|--------------|-------------------|------|-------------|-------|
| `Erro_Descricao` | `erro_descricao` | TEXT | NULL | |
| `Erro_OfId` | `erro_of_id` | VARCHAR(50) | NOT NULL | FK para OrdensFabrico |
| `Erro_FaseAvaliacao` | `erro_fase_avaliacao` | VARCHAR(50) | NULL | |
| `OFCH_GRAVIDADE` | `ofch_gravidade` | INTEGER | NULL | |
| `Erro_FaseOfAvaliacao` | `erro_fase_of_avaliacao` | VARCHAR(50) | NULL | |
| `Erro_FaseOfCulpada` | `erro_fase_of_culpada` | VARCHAR(50) | NULL | 41.5% NULL |

### 6.1 Schema RAW

```sql
-- Schema para dados originais (imutável após ingestão)
CREATE SCHEMA IF NOT EXISTS factory_raw;

-- Ordens de Fabrico
CREATE TABLE factory_raw.ordens_fabrico (
    id SERIAL PRIMARY KEY,
    of_id VARCHAR(50) NOT NULL,
    of_data_criacao TIMESTAMP,
    of_data_acabamento TIMESTAMP,
    of_produto_id VARCHAR(50),
    of_fase_id VARCHAR(50),
    of_data_transporte TIMESTAMP,
    _ingestion_id UUID NOT NULL,
    _ingestion_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    _row_hash VARCHAR(64) NOT NULL
);

CREATE INDEX idx_raw_ordens_of_id ON factory_raw.ordens_fabrico(of_id);
CREATE INDEX idx_raw_ordens_ingestion ON factory_raw.ordens_fabrico(_ingestion_id);

-- Fases de Ordem de Fabrico (COMPLETO conforme Data Dictionary 6.0.1)
CREATE TABLE factory_raw.fases_ordem_fabrico (
    id SERIAL PRIMARY KEY,
    fase_of_id VARCHAR(50) NOT NULL,
    fase_of_of_id VARCHAR(50) NOT NULL,
    fase_of_inicio TIMESTAMP,
    fase_of_fim TIMESTAMP,
    fase_of_data_prevista TIMESTAMP,
    fase_of_coeficiente NUMERIC(10,4),
    fase_of_coeficiente_x NUMERIC(10,4),
    fase_of_fase_id VARCHAR(50),
    fase_of_peso NUMERIC(10,4),
    fase_of_retorno INTEGER,
    fase_of_turno VARCHAR(20),
    fase_of_sequencia INTEGER,
    molde_of_id VARCHAR(50),
    molde_nome VARCHAR(255),
    molde_numero_pocos_id VARCHAR(50),
    molde_modelo_id VARCHAR(50),        -- ADICIONADO: para validação molde↔modelo
    molde_tamanho_id VARCHAR(50),       -- ADICIONADO: para validação molde↔modelo
    fase_of_horas_previstas NUMERIC(10,4),  -- CRÍTICO: campo de horas (56.6% zeros)
    _ingestion_id UUID NOT NULL,
    _ingestion_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    _row_hash VARCHAR(64) NOT NULL
);

CREATE INDEX idx_raw_fases_of_id ON factory_raw.fases_ordem_fabrico(fase_of_id);
CREATE INDEX idx_raw_fases_ordem ON factory_raw.fases_ordem_fabrico(fase_of_of_id);
CREATE INDEX idx_raw_fases_molde ON factory_raw.fases_ordem_fabrico(molde_of_id);

-- Funcionários
CREATE TABLE factory_raw.funcionarios (
    id SERIAL PRIMARY KEY,
    funcionario_id VARCHAR(50) NOT NULL,
    funcionario_nome VARCHAR(255),
    funcionario_activo INTEGER,
    funcionario_valor_hora NUMERIC(10,2),
    _ingestion_id UUID NOT NULL,
    _ingestion_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    _row_hash VARCHAR(64) NOT NULL
);

-- Fases (dimensão)
CREATE TABLE factory_raw.fases (
    id SERIAL PRIMARY KEY,
    fase_id VARCHAR(50) NOT NULL,
    fase_nome VARCHAR(255),
    fase_sequencia INTEGER,
    fase_producao INTEGER,
    fase_automatica INTEGER,
    fase_numero_funcionarios INTEGER,
    fase_capacidade_horas_dia NUMERIC(10,2),
    _ingestion_id UUID NOT NULL,
    _ingestion_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    _row_hash VARCHAR(64) NOT NULL
);

-- Moldes
CREATE TABLE factory_raw.moldes (
    id SERIAL PRIMARY KEY,
    molde_id VARCHAR(50) NOT NULL,
    molde_nome VARCHAR(255),
    molde_estado VARCHAR(50),
    molde_modelo VARCHAR(255),
    molde_numero_pocos_id VARCHAR(50),
    molde_modelo_id VARCHAR(50),
    molde_tamanho_id VARCHAR(50),
    _ingestion_id UUID NOT NULL,
    _ingestion_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    _row_hash VARCHAR(64) NOT NULL
);

-- Modelos (Produtos)
CREATE TABLE factory_raw.modelos (
    id SERIAL PRIMARY KEY,
    produto_id VARCHAR(50) NOT NULL,
    produto_nome VARCHAR(255),
    produto_peso_desmolde NUMERIC(10,4),
    produto_peso_acabamento NUMERIC(10,4),
    produto_qtd_gel_deck NUMERIC(10,4),
    produto_qtd_gel_casco NUMERIC(10,4),
    produto_numero_pocos_id VARCHAR(50),
    produto_modelo_id VARCHAR(50),
    produto_tamanho_id VARCHAR(50),
    _ingestion_id UUID NOT NULL,
    _ingestion_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    _row_hash VARCHAR(64) NOT NULL
);

-- Standards por Produto/Fase
CREATE TABLE factory_raw.fases_standard_modelos (
    id SERIAL PRIMARY KEY,
    produto_fase_produto_id VARCHAR(50) NOT NULL,
    produto_fase_fase_id VARCHAR(50) NOT NULL,
    produto_fase_sequencia INTEGER,
    produto_fase_coeficiente NUMERIC(10,4),
    produto_fase_coeficiente_x NUMERIC(10,4),
    produto_fase_horas_previstas NUMERIC(10,4),
    _ingestion_id UUID NOT NULL,
    _ingestion_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    _row_hash VARCHAR(64) NOT NULL
);

-- Funcionários por Fase de Ordem
CREATE TABLE factory_raw.funcionarios_fase_ordem_fabrico (
    id SERIAL PRIMARY KEY,
    funcionario_fase_of_fase_of_id VARCHAR(50) NOT NULL,
    funcionario_fase_of_funcionario_id VARCHAR(50) NOT NULL,
    funcionario_fase_of_chefe INTEGER,
    _ingestion_id UUID NOT NULL,
    _ingestion_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    _row_hash VARCHAR(64) NOT NULL
);

-- Funcionários Aptos por Fase
CREATE TABLE factory_raw.funcionarios_fases_aptos (
    id SERIAL PRIMARY KEY,
    funcionario_fase_funcionario_id VARCHAR(50) NOT NULL,
    funcionario_fase_fase_id VARCHAR(50) NOT NULL,
    funcionario_fase_inicio TIMESTAMP,
    _ingestion_id UUID NOT NULL,
    _ingestion_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    _row_hash VARCHAR(64) NOT NULL
);

-- Erros de Ordem de Fabrico
CREATE TABLE factory_raw.ordem_fabrico_erros (
    id SERIAL PRIMARY KEY,
    erro_descricao TEXT,
    erro_of_id VARCHAR(50) NOT NULL,
    erro_fase_avaliacao VARCHAR(50),
    ofch_gravidade INTEGER,
    erro_fase_of_avaliacao VARCHAR(50),
    erro_fase_of_culpada VARCHAR(50),
    _ingestion_id UUID NOT NULL,
    _ingestion_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    _row_hash VARCHAR(64) NOT NULL
);
```

### 6.2 Schema CURATED

```sql
-- Schema para dados curados (com validações e campos derivados)
CREATE SCHEMA IF NOT EXISTS factory_curated;

-- Ordens de Fabrico (curadas)
CREATE TABLE factory_curated.ordens_fabrico (
    id SERIAL PRIMARY KEY,
    of_id VARCHAR(50) NOT NULL UNIQUE,
    of_data_criacao TIMESTAMP,
    of_data_acabamento TIMESTAMP,
    of_produto_id VARCHAR(50),
    of_fase_id VARCHAR(50),
    of_data_transporte TIMESTAMP,
    
    -- Campos derivados
    is_open BOOLEAN NOT NULL DEFAULT TRUE,
    lead_time_days NUMERIC(10,2),
    has_valid_dates BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Metadados de curadoria
    _source_ingestion_id UUID NOT NULL,
    _curated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    _trust_index NUMERIC(5,2) NOT NULL DEFAULT 82
);

-- Fases de Ordem de Fabrico (curadas, COMPLETO)
CREATE TABLE factory_curated.fases_ordem_fabrico (
    id SERIAL PRIMARY KEY,
    fase_of_id VARCHAR(50) NOT NULL UNIQUE,
    fase_of_of_id VARCHAR(50) NOT NULL,
    fase_of_inicio TIMESTAMP,
    fase_of_fim TIMESTAMP,
    fase_of_data_prevista TIMESTAMP,
    fase_of_coeficiente NUMERIC(10,4),
    fase_of_fase_id VARCHAR(50),
    molde_of_id VARCHAR(50),
    molde_nome VARCHAR(255),
    molde_modelo_id VARCHAR(50),
    molde_tamanho_id VARCHAR(50),
    fase_of_horas_previstas NUMERIC(10,4),  -- Campo original do Excel
    of_produto_id VARCHAR(50),              -- ADICIONADO: FK derivada de OrdensFabrico para join com standards
    
    -- Campos derivados
    horas_previstas_final NUMERIC(10,4),    -- Derivado: fase_of_horas_previstas OU standard
    horas_previstas_source VARCHAR(20),     -- 'fase', 'standard', NULL
    is_phase_open BOOLEAN NOT NULL DEFAULT TRUE,
    duration_hours NUMERIC(10,4),
    is_event_marker BOOLEAN NOT NULL DEFAULT FALSE,
    is_invalid_timing BOOLEAN NOT NULL DEFAULT FALSE,
    mold_occupancy_start TIMESTAMP,
    mold_occupancy_end TIMESTAMP,
    has_mold_model_mismatch BOOLEAN NOT NULL DEFAULT FALSE,
    standard_has_conflict BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Metadados de curadoria
    _source_ingestion_id UUID NOT NULL,
    _curated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    _trust_index NUMERIC(5,2) NOT NULL DEFAULT 58
);

CREATE INDEX idx_curated_fases_ordem ON factory_curated.fases_ordem_fabrico(fase_of_of_id);
CREATE INDEX idx_curated_fases_fase ON factory_curated.fases_ordem_fabrico(fase_of_fase_id);
CREATE INDEX idx_curated_fases_molde ON factory_curated.fases_ordem_fabrico(molde_of_id);
CREATE INDEX idx_curated_fases_produto ON factory_curated.fases_ordem_fabrico(of_produto_id);

-- Funcionários (curados)
CREATE TABLE factory_curated.funcionarios (
    id SERIAL PRIMARY KEY,
    funcionario_id VARCHAR(50) NOT NULL UNIQUE,
    funcionario_nome VARCHAR(255),
    funcionario_activo INTEGER,
    funcionario_valor_hora NUMERIC(10,2),
    
    -- Campos derivados
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    has_valid_valor_hora BOOLEAN NOT NULL DEFAULT FALSE,
    is_valor_hora_outlier BOOLEAN NOT NULL DEFAULT FALSE,
    valor_hora_p99_threshold NUMERIC(10,2),
    
    -- Metadados de curadoria
    _source_ingestion_id UUID NOT NULL,
    _curated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    _trust_index NUMERIC(5,2) NOT NULL DEFAULT 75
);

-- Fases (curadas)
CREATE TABLE factory_curated.fases (
    id SERIAL PRIMARY KEY,
    fase_id VARCHAR(50) NOT NULL UNIQUE,
    fase_nome VARCHAR(255),
    fase_sequencia INTEGER,
    fase_producao INTEGER,
    fase_automatica INTEGER,
    fase_numero_funcionarios INTEGER,
    fase_capacidade_horas_dia NUMERIC(10,2),
    
    -- Campos derivados
    is_production BOOLEAN NOT NULL DEFAULT FALSE,
    capacity_matches_employees BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Metadados de curadoria
    _source_ingestion_id UUID NOT NULL,
    _curated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    _trust_index NUMERIC(5,2) NOT NULL DEFAULT 85
);

-- Standards (curados, com resolução de duplicados)
CREATE TABLE factory_curated.fases_standard_modelos (
    id SERIAL PRIMARY KEY,
    produto_fase_produto_id VARCHAR(50) NOT NULL,
    produto_fase_fase_id VARCHAR(50) NOT NULL,
    produto_fase_horas_previstas NUMERIC(10,4),
    
    -- Campos derivados
    is_duplicate_key BOOLEAN NOT NULL DEFAULT FALSE,
    has_conflict BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Metadados de curadoria
    _source_ingestion_id UUID NOT NULL,
    _curated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    _trust_index NUMERIC(5,2) NOT NULL DEFAULT 60,
    
    UNIQUE(produto_fase_produto_id, produto_fase_fase_id)
);

-- Erros (curados)
CREATE TABLE factory_curated.ordem_fabrico_erros (
    id SERIAL PRIMARY KEY,
    erro_descricao TEXT,
    erro_of_id VARCHAR(50) NOT NULL,
    erro_fase_avaliacao VARCHAR(50),
    ofch_gravidade INTEGER,
    erro_fase_of_avaliacao VARCHAR(50),
    erro_fase_of_culpada VARCHAR(50),
    
    -- Campos derivados
    has_fase_culpada BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Metadados de curadoria
    _source_ingestion_id UUID NOT NULL,
    _curated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    _trust_index NUMERIC(5,2) NOT NULL DEFAULT 67
);
```

### 6.3 Schema META

```sql
-- Schema para metadados de ingestão e auditoria
CREATE SCHEMA IF NOT EXISTS factory_meta;

-- Registo de ingestões
CREATE TABLE factory_meta.ingestion_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_file VARCHAR(500) NOT NULL,
    source_file_hash VARCHAR(64) NOT NULL,
    source_file_size_bytes BIGINT NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING', -- RUNNING, COMPLETED, FAILED
    rows_loaded JSONB, -- {"table": count}
    validation_summary JSONB,
    quality_report JSONB,
    error_message TEXT
);

-- Registo de tabelas por ingestão
CREATE TABLE factory_meta.ingestion_tables (
    id SERIAL PRIMARY KEY,
    ingestion_id UUID NOT NULL REFERENCES factory_meta.ingestion_runs(id),
    table_name VARCHAR(100) NOT NULL,
    schema_name VARCHAR(50) NOT NULL,
    rows_loaded INTEGER NOT NULL,
    rows_validated INTEGER NOT NULL,
    rows_failed INTEGER NOT NULL DEFAULT 0,
    validation_errors JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Registo de hashes por linha (para idempotência)
-- CORRECÇÃO: UNIQUE(table_name, row_hash) bloquearia reimportações.
-- O correcto é UNIQUE(ingestion_id, table_name, row_hash) para permitir
-- o mesmo row aparecer em runs diferentes (reimportações do mesmo ficheiro).
CREATE TABLE factory_meta.row_hashes (
    id SERIAL PRIMARY KEY,
    ingestion_id UUID NOT NULL REFERENCES factory_meta.ingestion_runs(id),
    table_name VARCHAR(100) NOT NULL,
    row_hash VARCHAR(64) NOT NULL,
    source_row_number INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(ingestion_id, table_name, row_hash)  -- CORRIGIDO: inclui ingestion_id
);

CREATE INDEX idx_row_hashes_table ON factory_meta.row_hashes(table_name);
CREATE INDEX idx_row_hashes_hash ON factory_meta.row_hashes(row_hash);
CREATE INDEX idx_row_hashes_ingestion ON factory_meta.row_hashes(ingestion_id);

-- Quality gates
CREATE TABLE factory_meta.quality_gates (
    id SERIAL PRIMARY KEY,
    ingestion_id UUID NOT NULL REFERENCES factory_meta.ingestion_runs(id),
    gate_name VARCHAR(100) NOT NULL,
    gate_type VARCHAR(50) NOT NULL, -- BLOCKING, WARNING, INFO
    passed BOOLEAN NOT NULL,
    threshold NUMERIC(10,4),
    actual_value NUMERIC(10,4),
    message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Active run (singleton para controlo lógico de versão activa)
-- CRÍTICO: RAW é append-only, rollback é lógico via esta tabela
CREATE TABLE factory_meta.active_run (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- Singleton
    active_ingestion_id UUID NOT NULL REFERENCES factory_meta.ingestion_runs(id),
    activated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    activated_by VARCHAR(100),
    previous_ingestion_id UUID  -- Para histórico de rollbacks
);

-- Histórico de activações (auditoria de rollbacks)
CREATE TABLE factory_meta.activation_history (
    id SERIAL PRIMARY KEY,
    ingestion_id UUID NOT NULL REFERENCES factory_meta.ingestion_runs(id),
    action VARCHAR(20) NOT NULL,  -- ACTIVATED, ROLLED_BACK
    performed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    performed_by VARCHAR(100),
    reason TEXT
);
```

---

## 7. Pipeline de Ingestão (CLI) — Descrição Técnica Completa

### 7.1 Fluxo de Ingestão

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE DE INGESTÃO                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. HASH CHECK                                                               │
│     └─▶ Calcular SHA-256 do ficheiro                                        │
│     └─▶ Verificar se já foi ingerido (idempotência)                         │
│     └─▶ Se igual: SKIP (exit 0)                                             │
│                                                                              │
│  2. LOAD RAW                                                                 │
│     └─▶ Ler cada sheet do Excel                                             │
│     └─▶ Preservar tipos originais (IDs como string)                         │
│     └─▶ Calcular hash por linha                                             │
│     └─▶ Inserir em factory_raw.* com _ingestion_id                          │
│                                                                              │
│  3. VALIDATE                                                                 │
│     └─▶ Verificar volumetria (±10% do esperado)                             │
│     └─▶ Verificar integridade referencial                                   │
│     └─▶ Verificar ranges de valores                                         │
│     └─▶ Registar erros em factory_meta.quality_gates                        │
│                                                                              │
│  4. CURATE                                                                   │
│     └─▶ Aplicar transformações (campos derivados)                           │
│     └─▶ Resolver duplicados (standards)                                     │
│     └─▶ Calcular Trust Index por tabela                                     │
│     └─▶ Inserir em factory_curated.* com _trust_index                       │
│                                                                              │
│  5. QUALITY GATES                                                            │
│     └─▶ Executar gates BLOCKING                                             │
│     └─▶ Se falhar: ROLLBACK + exit 1                                        │
│     └─▶ Executar gates WARNING                                              │
│     └─▶ Registar em factory_meta.quality_gates                              │
│                                                                              │
│  6. FINALIZE                                                                 │
│     └─▶ Actualizar factory_meta.ingestion_runs                              │
│     └─▶ Gerar quality_report.json                                           │
│     └─▶ exit 0                                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Comandos CLI

> **IMPORTANTE:** A base de dados é `prodplan_factory`, **SEPARADA** de `prodplan`.
> O schema principal de `prodplan` **NÃO** deve ter credenciais de escrita em `prodplan_factory`.

```bash
# Ingestão completa
python -m factory_data_product.cli ingest \
    --source /path/to/Folha_IA_extra.xlsx \
    --database postgresql://factory_user:pass@host:5432/prodplan_factory

# Apenas validação (dry-run)
python -m factory_data_product.cli validate \
    --source /path/to/Folha_IA_extra.xlsx

# Ver relatório de qualidade
python -m factory_data_product.cli report \
    --ingestion-id <uuid> \
    --database postgresql://factory_user:pass@host:5432/prodplan_factory

# Rollback lógico (ver secção 13.3)
python -m factory_data_product.cli rollback \
    --reason "Erro detectado" \
    --database postgresql://factory_user:pass@host:5432/prodplan_factory
```

#### Separação de Credenciais

| Role | Base de Dados | Permissões |
|------|---------------|------------|
| `factory_ingest` | `prodplan_factory` | SELECT, INSERT, UPDATE em `raw`, `curated`, `meta` |
| `factory_api` | `prodplan_factory` | SELECT ONLY em `curated`, `semantic` |
| `prodplan_app` | `prodplan` | SEM ACESSO a `prodplan_factory` |

```sql
-- Criar roles com separação de privilégios
CREATE ROLE factory_ingest WITH LOGIN PASSWORD '${FACTORY_INGEST_PASSWORD}';
CREATE ROLE factory_api WITH LOGIN PASSWORD '${FACTORY_API_PASSWORD}';

-- factory_ingest: acesso total ao factory data product
GRANT USAGE ON SCHEMA factory_raw, factory_curated, factory_meta TO factory_ingest;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA factory_raw TO factory_ingest;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA factory_curated TO factory_ingest;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA factory_meta TO factory_ingest;

-- factory_api: APENAS leitura de curated/semantic
GRANT USAGE ON SCHEMA factory_curated, factory_semantic TO factory_api;
GRANT SELECT ON ALL TABLES IN SCHEMA factory_curated TO factory_api;
GRANT SELECT ON ALL TABLES IN SCHEMA factory_semantic TO factory_api;

-- PROIBIR factory_api de aceder a RAW (data contract)
REVOKE ALL ON SCHEMA factory_raw FROM factory_api;
```

### 7.3 Pseudo-código do Pipeline

```python
def ingest(source_file: Path, database_url: str) -> int:
    """
    Pipeline de ingestão completo.
    
    Returns:
        0 se sucesso, 1 se falha
    """
    # 1. Hash check
    file_hash = calculate_sha256(source_file)
    if is_already_ingested(file_hash):
        logger.info(f"File already ingested: {file_hash}")
        return 0
    
    ingestion_id = uuid4()
    
    try:
        # 2. Load RAW
        with transaction():
            raw_data = load_excel_sheets(source_file)
            for table_name, df in raw_data.items():
                df["_ingestion_id"] = ingestion_id
                df["_row_hash"] = df.apply(calculate_row_hash, axis=1)
                insert_raw(table_name, df)
        
        # 3. Validate
        validation_results = validate_all(raw_data)
        if has_blocking_errors(validation_results):
            raise ValidationError(validation_results)
        
        # 4. Curate
        with transaction():
            curated_data = transform_all(raw_data)
            for table_name, df in curated_data.items():
                df["_trust_index"] = calculate_trust_index(table_name, df)
                insert_curated(table_name, df)
        
        # 5. Quality Gates
        gates = execute_quality_gates(curated_data)
        if has_blocking_gates(gates):
            raise QualityGateError(gates)
        
        # 6. Finalize
        update_ingestion_run(ingestion_id, status="COMPLETED")
        generate_quality_report(ingestion_id)
        
        return 0
        
    except Exception as e:
        rollback_ingestion(ingestion_id)
        update_ingestion_run(ingestion_id, status="FAILED", error=str(e))
        return 1
```

---

## 8. Regras de Curadoria e Semântica dos Dados

### 8.1 Regra: Semântica do "0"

| Campo | Valor 0 Significa | Tratamento |
|-------|-------------------|------------|
| `FaseOf_HorasPrevistas` | UNKNOWN/NOT_SET | Fallback para standard |
| `ProdutoFase_HorasPrevistas` | Fase não existe para produto | NULL |
| `FuncionarioValorHora` | Não parametrizado | Marcar como inválido |
| `Fase_CapacidadeHorasDia` | Fase não produtiva | Excluir de cálculos |

### 8.2 Regra: HorasPrevistas_Final

> **CRÍTICO:** O campo `FaseOf_Coeficiente` é um **multiplicador** (valores 1.0, 1.5, 2.0), 
> **NÃO** são horas previstas. O campo correcto é `FaseOf_HorasPrevistas`.

**Evidência dos dados reais:**
- `FaseOf_HorasPrevistas`: 229,984 valores > 0 (43.4%), valores típicos: 0.67, 1.33, 5.33
- `FaseOf_Coeficiente`: 496,809 valores > 0 (93.8%), valores típicos: 1.0, 1.5, 2.0

```sql
-- Lógica de derivação CORRECTA
-- NOTA: Usa fase_of_horas_previstas, NÃO fase_of_coeficiente
UPDATE factory_curated.fases_ordem_fabrico f
SET 
    horas_previstas_final = CASE
        WHEN f.fase_of_horas_previstas > 0 THEN f.fase_of_horas_previstas
        WHEN s.produto_fase_horas_previstas > 0 THEN s.produto_fase_horas_previstas
        ELSE NULL
    END,
    horas_previstas_source = CASE
        WHEN f.fase_of_horas_previstas > 0 THEN 'fase'
        WHEN s.produto_fase_horas_previstas > 0 THEN 'standard'
        ELSE NULL
    END
FROM factory_curated.fases_standard_modelos s
WHERE f.fase_of_fase_id = s.produto_fase_fase_id
  AND f.of_produto_id = s.produto_fase_produto_id;
```

**Verificação de integridade (pós-curadoria):**

```sql
-- Verificar cobertura de horas_previstas_final
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN horas_previstas_final IS NOT NULL THEN 1 ELSE 0 END) as com_horas,
    ROUND(100.0 * SUM(CASE WHEN horas_previstas_final IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as cobertura_pct,
    COUNT(DISTINCT horas_previstas_source) as fontes_usadas
FROM factory_curated.fases_ordem_fabrico;
-- Esperado: cobertura_pct entre 85% e 95% (após fallback para standard)
```

### 8.3 Regra: Resolução de Standards Duplicados

```python
def resolve_standard_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resolver duplicados em FasesStandardModelos.
    
    Regra:
    - Se valores iguais: manter um
    - Se valores diferentes: usar max(non_zero), marcar conflito
    - NUNCA somar (pode inflacionar tempos)
    """
    grouped = df.groupby(["produto_fase_produto_id", "produto_fase_fase_id"]).agg({
        "produto_fase_horas_previstas": lambda x: x[x > 0].max() if (x > 0).any() else 0,
        "_has_conflict": lambda x: x.nunique() > 1,
    })
    return grouped
```

### 8.4 Regra: Validação de Tempos

```python
def validate_timing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validar tempos Inicio/Fim.
    """
    # Fim < Inicio = inválido
    df["is_invalid_timing"] = (
        df["fase_of_fim"].notna() & 
        df["fase_of_inicio"].notna() & 
        (df["fase_of_fim"] < df["fase_of_inicio"])
    )
    
    # Fim == Inicio = marcador de evento
    df["is_event_marker"] = (
        df["fase_of_fim"].notna() & 
        df["fase_of_inicio"].notna() & 
        (df["fase_of_fim"] == df["fase_of_inicio"])
    )
    
    return df
```

### 8.5 Regra: Conflitos de Molde

```python
MOLD_OCCUPANCY_HOURS = 12  # Parametrizável

def detect_mold_conflicts(df: pd.DataFrame) -> List[Dict]:
    """
    Detectar conflitos de molde usando heurística de 12h.
    
    Só aplicável quando:
    - MoldeOfId NOT NULL
    - FaseOf_DataPrevista NOT NULL
    """
    conflicts = []
    
    for mold_id, group in df.groupby("molde_of_id"):
        if len(group) < 2:
            continue
        
        sorted_group = group.sort_values("fase_of_data_prevista")
        
        for i in range(len(sorted_group) - 1):
            current = sorted_group.iloc[i]
            next_phase = sorted_group.iloc[i + 1]
            
            occupancy_end = current["fase_of_data_prevista"] + timedelta(hours=MOLD_OCCUPANCY_HOURS)
            
            if next_phase["fase_of_data_prevista"] < occupancy_end:
                conflicts.append({
                    "mold_id": mold_id,
                    "phase_1": current["fase_of_id"],
                    "phase_2": next_phase["fase_of_id"],
                    "overlap_hours": (occupancy_end - next_phase["fase_of_data_prevista"]).total_seconds() / 3600,
                })
    
    return conflicts
```

---

## 9. Catálogo de Problemas Reais do Excel (com Severidade)

### 9.1 Tabela de Problemas

| ID | Problema | Tabela | Severidade | Impacto | Mitigação |
|----|----------|--------|------------|---------|-----------|
| P01 | HorasPrevistas = 0 em 56.6% das fases | FasesOrdemFabrico | ALTA | Backlog subestimado | Fallback para standard |
| P02 | DataPrevista só em 4.8% das fases | FasesOrdemFabrico | ALTA | Conflitos de molde incompletos | Warning explícito |
| P03 | Erros sem FaseOfCulpada (41.5%) | OrdemFabricoErros | MÉDIA | Qualidade por fase incompleta | Flag "sem atribuição" |
| P04 | Standards duplicados (217 chaves) | FasesStandardModelos | MÉDIA | Tempos inconsistentes | Resolução por max(non_zero) |
| P05 | Standards com conflito (105 chaves) | FasesStandardModelos | MÉDIA | Tempos ambíguos | Flag "conflito" |
| P06 | ValorHora = 0 em 14.3% funcionários | Funcionarios | MÉDIA | Custos incompletos | Excluir de cálculos |
| P07 | ValorHora outliers | Funcionarios | BAIXA | Custos distorcidos | Usar mediana |
| P08 | Tempos Inicio == Fim (marcadores) | FasesOrdemFabrico | BAIXA | Duração 0 | Flag "event_marker" |
| P09 | Tempos Fim < Inicio | FasesOrdemFabrico | BAIXA | Dados inválidos | Flag "invalid_timing" |
| P10 | Estados de molde sem legenda | Moldes | BAIXA | Semântica incompleta | Não inferir disponibilidade |

### 9.2 Matriz de Severidade

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MATRIZ DE SEVERIDADE                                      │
├─────────────────────┬───────────────┬───────────────────────────────────────┤
│ Severidade          │ Critério      │ Acção                                 │
├─────────────────────┼───────────────┼───────────────────────────────────────┤
│ CRÍTICA             │ Bloqueia uso  │ GATE BLOCKING - Ingestão falha        │
│ ALTA                │ Degrada muito │ GATE WARNING + Trust Index < 60       │
│ MÉDIA               │ Degrada       │ Flag + Warning no output              │
│ BAIXA               │ Informativo   │ Log + Documentação                    │
└─────────────────────┴───────────────┴───────────────────────────────────────┘
```

---

## 10. Trust Index por Segmento e Impacto Funcional

### 10.1 Tabela de Trust Index

| Segmento | Trust Index | Justificação | Impacto Funcional |
|----------|-------------|--------------|-------------------|
| **Erros (catálogo)** | 92 | Semântica estável, boa para BI | Qualidade: USÁVEL AGORA |
| **Fases (dimensão)** | 85 | Estrutura sólida, capacidade teórica | Capacidade: USÁVEL COM AVISOS |
| **OrdensFabrico** | 82 | Boa base para WIP/lead time | WIP: USÁVEL AGORA |
| **FasesOrdemFabrico (estrutura)** | 80 | Boa malha relacional | Backlog: USÁVEL COM AVISOS |
| **Funcionários** | 75 | ValorHora com zeros/outliers | Custos: USÁVEL COM AVISOS |
| **Moldes** | 70 | Estados sem dicionário | Conflitos: USÁVEL COM AVISOS |
| **OrdemFabricoErros** | 67 | 41.5% sem fase culpada | Qualidade: USÁVEL COM AVISOS |
| **Tempos Inicio/Fim** | 62 | Muitas durações 0 | Lead time: USÁVEL COM AVISOS |
| **Standards** | 60 | Duplicados, zeros | Backlog: USÁVEL COM AVISOS |
| **HorasPrevistas** | 58 | 56.6% zeros | Backlog: USÁVEL COM AVISOS |
| **Funcionário↔Fase** | 55 | Sem horas reais | Produtividade: NÃO USÁVEL |
| **DataPrevista** | 35 | Só 4.8% cobertura | Conflitos molde: USÁVEL COM AVISOS |

### 10.2 Fórmula de Trust Index

```python
def calculate_trust_index(
    base_trust: int,
    coverage_pct: float,
    sample_size: int,
    min_sample: int = 10,
) -> float:
    """
    Calcular Trust Index ajustado.
    
    Trust Index = Base × Coverage Factor × Sample Factor
    
    Args:
        base_trust: Trust Index base do segmento (0-100)
        coverage_pct: Cobertura de campos críticos (0-100)
        sample_size: Número de registos
        min_sample: Mínimo para confiança total
    
    Returns:
        Trust Index ajustado (0-100)
    """
    coverage_factor = min(1.0, coverage_pct / 100)
    sample_factor = min(1.0, sample_size / min_sample)
    
    return round(base_trust * coverage_factor * sample_factor, 1)
```

### 10.3 Degradação de Funcionalidades

| Trust Index | Estado | Acção no Sistema |
|-------------|--------|------------------|
| ≥ 80 | VERDE | Usar sem restrições |
| 60-79 | AMARELO | Usar com warning no output |
| 40-59 | LARANJA | Usar com warning + disclaimer |
| < 40 | VERMELHO | Bloquear funcionalidade |

---

## 11. Data Quality Gates e Políticas de Bloqueio

### 11.1 Gates BLOCKING (Falha = Rollback)

> **CRÍTICO:** O gate `PK_UNIQUENESS` original estava errado porque testava `id SERIAL PRIMARY KEY`,
> que por definição nunca duplica. O correcto é testar **chaves de negócio**.

| Gate | Condição | Threshold | Acção se Falhar |
|------|----------|-----------|-----------------|
| `VOLUMETRY_ORDERS` | `abs(count - 27911) / 27911 > threshold` | 20% | ROLLBACK |
| `VOLUMETRY_PHASES` | `abs(count - 529450) / 529450 > threshold` | 20% | ROLLBACK |
| `BUSINESS_KEY_ORDERS` | `of_id duplicates > 0` | 0 | ROLLBACK |
| `BUSINESS_KEY_PHASES` | `fase_of_id duplicates > 0` | 0 | ROLLBACK |
| `BUSINESS_KEY_EMPLOYEES` | `funcionario_id duplicates > 0` | 0 | ROLLBACK |
| `FK_INTEGRITY_PHASES` | `fase_of_of_id orphans > threshold` | 1% | ROLLBACK |
| `FK_INTEGRITY_ERRORS` | `erro_of_id orphans > threshold` | 1% | ROLLBACK |

### 11.2 Gates WARNING (Falha = Log + Continua)

| Gate | Condição | Threshold | Acção se Falhar |
|------|----------|-----------|-----------------|
| `HORAS_PREVISTAS_COVERAGE` | `coverage < threshold` | 50% | WARNING |
| `DATA_PREVISTA_COVERAGE` | `coverage < threshold` | 10% | WARNING |
| `FASE_CULPADA_COVERAGE` | `coverage < threshold` | 60% | WARNING |
| `VALOR_HORA_VALID` | `valid_count / total < threshold` | 80% | WARNING |
| `STANDARD_DUPLICATES` | `duplicates > threshold` | 100 | WARNING |
| `TIMING_INVALID` | `invalid > threshold` | 1% | WARNING |

### 11.3 Implementação de Gates

```python
@dataclass
class QualityGate:
    name: str
    gate_type: str  # BLOCKING, WARNING
    threshold: float
    table: str  # Tabela alvo
    check_fn: Callable[[pd.DataFrame], Tuple[bool, float, str]]

QUALITY_GATES = [
    # --- BLOCKING GATES (Chaves de Negócio) ---
    QualityGate(
        name="VOLUMETRY_ORDERS",
        gate_type="BLOCKING",
        threshold=0.20,
        table="ordens_fabrico",
        check_fn=lambda df: (
            abs(len(df) - 27911) / 27911 <= 0.20,
            len(df),
            f"Expected ~27911, got {len(df)}"
        ),
    ),
    QualityGate(
        name="BUSINESS_KEY_ORDERS",
        gate_type="BLOCKING",
        threshold=0,
        table="ordens_fabrico",
        check_fn=lambda df: (
            df["of_id"].is_unique,
            df["of_id"].duplicated().sum(),
            f"Duplicate business keys (of_id): {df['of_id'].duplicated().sum()}"
        ),
    ),
    QualityGate(
        name="BUSINESS_KEY_PHASES",
        gate_type="BLOCKING",
        threshold=0,
        table="fases_ordem_fabrico",
        check_fn=lambda df: (
            df["fase_of_id"].is_unique,
            df["fase_of_id"].duplicated().sum(),
            f"Duplicate business keys (fase_of_id): {df['fase_of_id'].duplicated().sum()}"
        ),
    ),
    QualityGate(
        name="BUSINESS_KEY_EMPLOYEES",
        gate_type="BLOCKING",
        threshold=0,
        table="funcionarios",
        check_fn=lambda df: (
            df["funcionario_id"].is_unique,
            df["funcionario_id"].duplicated().sum(),
            f"Duplicate business keys (funcionario_id): {df['funcionario_id'].duplicated().sum()}"
        ),
    ),
    QualityGate(
        name="FK_INTEGRITY_PHASES",
        gate_type="BLOCKING",
        threshold=0.01,
        table="fases_ordem_fabrico",
        check_fn=lambda df, orders: (
            df["fase_of_of_id"].isin(orders["of_id"]).mean() >= 0.99,
            1 - df["fase_of_of_id"].isin(orders["of_id"]).mean(),
            f"Orphan phases: {(~df['fase_of_of_id'].isin(orders['of_id'])).sum()}"
        ),
    ),
    
    # --- WARNING GATES ---
    QualityGate(
        name="HORAS_PREVISTAS_COVERAGE",
        gate_type="WARNING",
        threshold=0.50,
        table="fases_ordem_fabrico",
        check_fn=lambda df: (
            df["horas_previstas_final"].notna().mean() >= 0.50,
            df["horas_previstas_final"].notna().mean(),
            f"Coverage: {df['horas_previstas_final'].notna().mean():.1%}"
        ),
    ),
]

def execute_quality_gates(data: Dict[str, pd.DataFrame]) -> List[Dict]:
    """
    Executar todos os quality gates.
    
    NOTA: Gates BLOCKING falham a ingestão inteira.
          Gates WARNING apenas registam e continuam.
    """
    results = []
    blocking_failed = False
    
    for gate in QUALITY_GATES:
        if gate.table not in data:
            continue
        
        df = data[gate.table]
        
        # Alguns gates precisam de múltiplas tabelas
        if "FK_INTEGRITY" in gate.name and "orders" in gate.check_fn.__code__.co_varnames:
            passed, actual, message = gate.check_fn(df, data.get("ordens_fabrico", pd.DataFrame()))
        else:
            passed, actual, message = gate.check_fn(df)
        
        results.append({
            "gate": gate.name,
            "type": gate.gate_type,
            "passed": passed,
            "threshold": gate.threshold,
            "actual": actual,
            "message": message,
        })
        
        if not passed and gate.gate_type == "BLOCKING":
            blocking_failed = True
            logger.error(f"BLOCKING gate failed: {gate.name} - {message}")
        elif not passed:
            logger.warning(f"WARNING gate failed: {gate.name} - {message}")
    
    if blocking_failed:
        raise QualityGateError("One or more BLOCKING gates failed", results)
    
    return results
```

---

## 12. Testes Obrigatórios (Unit, Integration, Data Quality)

### 12.1 Testes de Parsing e Tipagem

```python
class TestParsing:
    """Testes de parsing do Excel."""
    
    def test_ids_are_strings(self, raw_data):
        """IDs devem ser strings, não floats."""
        for table in ["ordens_fabrico", "fases_ordem_fabrico", "funcionarios"]:
            id_col = f"{table.split('_')[0]}_id"
            assert raw_data[table][id_col].dtype == object
            assert not raw_data[table][id_col].str.contains(r"\.0$").any()
    
    def test_dates_are_datetime(self, raw_data):
        """Datas devem ser datetime."""
        date_cols = {
            "ordens_fabrico": ["of_data_criacao", "of_data_acabamento"],
            "fases_ordem_fabrico": ["fase_of_inicio", "fase_of_fim"],
        }
        for table, cols in date_cols.items():
            for col in cols:
                assert pd.api.types.is_datetime64_any_dtype(raw_data[table][col])
    
    def test_numeric_columns(self, raw_data):
        """Colunas numéricas devem ser numéricas."""
        numeric_cols = {
            "fases_ordem_fabrico": ["fase_of_coeficiente"],
            "funcionarios": ["funcionario_valor_hora"],
        }
        for table, cols in numeric_cols.items():
            for col in cols:
                assert pd.api.types.is_numeric_dtype(raw_data[table][col])
```

### 12.2 Testes de Idempotência

```python
class TestIdempotency:
    """Testes de idempotência do pipeline."""
    
    def test_same_file_same_hash(self, source_file):
        """Mesmo ficheiro deve ter mesmo hash."""
        hash1 = calculate_sha256(source_file)
        hash2 = calculate_sha256(source_file)
        assert hash1 == hash2
    
    def test_duplicate_ingestion_skipped(self, pipeline, source_file):
        """Segunda ingestão do mesmo ficheiro deve ser skipped."""
        result1 = pipeline.ingest(source_file)
        result2 = pipeline.ingest(source_file)
        
        assert result1.status == "COMPLETED"
        assert result2.status == "SKIPPED"
        assert result2.message == "File already ingested"
    
    def test_row_hashes_unique(self, curated_data):
        """Hashes de linha devem ser únicos por tabela."""
        for table, df in curated_data.items():
            assert df["_row_hash"].is_unique
```

### 12.3 Testes de Invariantes

> **NOTA:** Alguns invariantes são **soft checks** (warnings) porque dependem de
> pressupostos de negócio que podem variar (ex: turnos, horas por dia).

```python
# Parâmetros configuráveis (podem variar por fábrica)
HOURS_PER_SHIFT = 8  # Parametrizável: pode ser 7h, 7.5h, etc.
SHIFTS_PER_DAY = 1   # Parametrizável: pode haver 2 turnos

class TestInvariants:
    """Testes de invariantes de negócio."""
    
    def test_capacity_matches_employees_soft(self, curated_fases):
        """
        SOFT CHECK: Capacidade deve ser ~consistente com NumFuncionarios × 8h.
        
        AVISO: Este é um soft check porque:
        - A fábrica pode ter turnos de 7h ou 7.5h
        - Pode haver 2 turnos
        - A capacidade pode incluir ajustes manuais
        
        Falha gera WARNING, não bloqueia ingestão.
        """
        mismatches = []
        for _, row in curated_fases.iterrows():
            if row["fase_producao"] == 1 and row["fase_numero_funcionarios"] > 0:
                expected = row["fase_numero_funcionarios"] * HOURS_PER_SHIFT * SHIFTS_PER_DAY
                actual = row["fase_capacidade_horas_dia"]
                if actual and abs(actual - expected) / expected > 0.2:  # 20% tolerância
                    mismatches.append({
                        "fase_id": row["fase_id"],
                        "expected": expected,
                        "actual": actual,
                        "diff_pct": abs(actual - expected) / expected * 100
                    })
        
        if mismatches:
            # WARNING, não assertion
            logger.warning(
                f"Capacity mismatch in {len(mismatches)} phases (soft check)",
                extra={"mismatches": mismatches[:5]}  # Log primeiros 5
            )
        
        # NÃO falha o teste, apenas regista
        return len(mismatches)
    
    def test_production_phases_have_capacity(self, curated_fases):
        """Fases de produção devem ter capacidade > 0."""
        production = curated_fases[curated_fases["fase_producao"] == 1]
        assert (production["fase_capacidade_horas_dia"] > 0).all()
    
    def test_open_orders_no_completed_date(self, curated_ordens):
        """Ordens abertas não devem ter data de acabamento."""
        open_orders = curated_ordens[curated_ordens["is_open"] == True]
        assert open_orders["of_data_acabamento"].isna().all()
```

### 12.4 Testes de Flags de Inconsistência

```python
class TestInconsistencyFlags:
    """Testes de flags de inconsistência."""
    
    def test_invalid_timing_flagged(self, curated_fases):
        """Fases com Fim < Inicio devem estar flagged."""
        invalid = curated_fases[
            curated_fases["fase_of_fim"].notna() &
            curated_fases["fase_of_inicio"].notna() &
            (curated_fases["fase_of_fim"] < curated_fases["fase_of_inicio"])
        ]
        assert (invalid["is_invalid_timing"] == True).all()
    
    def test_event_markers_flagged(self, curated_fases):
        """Fases com Fim == Inicio devem estar flagged."""
        markers = curated_fases[
            curated_fases["fase_of_fim"].notna() &
            curated_fases["fase_of_inicio"].notna() &
            (curated_fases["fase_of_fim"] == curated_fases["fase_of_inicio"])
        ]
        assert (markers["is_event_marker"] == True).all()
    
    def test_standard_conflicts_flagged(self, curated_standards):
        """Standards com conflito devem estar flagged."""
        conflicts = curated_standards[curated_standards["has_conflict"] == True]
        # Verificar que há pelo menos os 105 conflitos esperados
        assert len(conflicts) >= 100
```

### 12.5 Testes de Regressão de Qualidade

```python
class TestQualityRegression:
    """Testes de regressão de qualidade."""
    
    def test_trust_index_within_bounds(self, quality_report):
        """Trust Index deve estar dentro dos bounds esperados."""
        expected = {
            "Fases": (80, 90),
            "OrdensFabrico": (78, 86),
            "FasesOrdemFabrico": (35, 65),
            "Funcionarios": (70, 80),
        }
        for table, (min_ti, max_ti) in expected.items():
            actual = quality_report["tables"][table]["adjusted_trust_index"]
            assert min_ti <= actual <= max_ti, \
                f"{table}: expected [{min_ti}, {max_ti}], got {actual}"
    
    def test_coverage_not_degraded(self, quality_report, baseline):
        """Cobertura não deve degradar vs baseline."""
        for table, metrics in quality_report["tables"].items():
            if table in baseline:
                for field, coverage in metrics["critical_coverage"].items():
                    baseline_coverage = baseline[table].get(field, 0)
                    assert coverage >= baseline_coverage * 0.95, \
                        f"{table}.{field}: coverage degraded from {baseline_coverage} to {coverage}"
```

### 12.6 Testes de Performance

```python
class TestPerformance:
    """Testes de performance com budgets explícitos."""
    
    BUDGETS = {
        "load_excel": 300,  # segundos
        "validate": 60,
        "curate": 120,
        "save_postgres": 60,
        "total_pipeline": 600,
    }
    
    def test_load_excel_performance(self, source_file):
        """Load Excel deve completar em < 300s."""
        start = time.time()
        load_excel_sheets(source_file)
        elapsed = time.time() - start
        assert elapsed < self.BUDGETS["load_excel"], \
            f"Load Excel took {elapsed:.1f}s, budget is {self.BUDGETS['load_excel']}s"
    
    def test_total_pipeline_performance(self, pipeline, source_file):
        """Pipeline total deve completar em < 600s."""
        start = time.time()
        pipeline.ingest(source_file)
        elapsed = time.time() - start
        assert elapsed < self.BUDGETS["total_pipeline"], \
            f"Pipeline took {elapsed:.1f}s, budget is {self.BUDGETS['total_pipeline']}s"
```

---

## 13. Observabilidade, Auditoria, Rollback e Segurança

### 13.1 Observabilidade

#### Métricas Prometheus

```python
# Métricas de ingestão
INGESTION_DURATION = Histogram(
    "factory_ingestion_duration_seconds",
    "Duration of ingestion pipeline",
    ["phase"],  # load, validate, curate, save
)

INGESTION_ROWS = Counter(
    "factory_ingestion_rows_total",
    "Total rows ingested",
    ["table", "status"],  # status: success, failed
)

QUALITY_GATE_RESULTS = Counter(
    "factory_quality_gate_results_total",
    "Quality gate results",
    ["gate", "type", "result"],  # result: passed, failed
)

TRUST_INDEX = Gauge(
    "factory_trust_index",
    "Trust Index by table",
    ["table"],
)
```

#### Logs Estruturados

```python
logger.info(
    "Ingestion phase completed",
    extra={
        "ingestion_id": str(ingestion_id),
        "phase": "curate",
        "table": "fases_ordem_fabrico",
        "rows_processed": 529450,
        "duration_seconds": 45.2,
        "trust_index": 58,
    }
)
```

### 13.2 Auditoria

Toda a ingestão é auditável através de:

1. **`factory_meta.ingestion_runs`**: Registo de cada execução
2. **`factory_meta.ingestion_tables`**: Detalhes por tabela
3. **`factory_meta.row_hashes`**: Hash de cada linha (idempotência)
4. **`factory_meta.quality_gates`**: Resultados de gates

```sql
-- Query de auditoria: últimas ingestões
SELECT 
    id,
    source_file,
    started_at,
    completed_at,
    status,
    rows_loaded->>'total' as total_rows,
    quality_report->>'overall_confidence' as confidence
FROM factory_meta.ingestion_runs
ORDER BY started_at DESC
LIMIT 10;
```

### 13.3 Rollback

> **PRINCÍPIO FUNDAMENTAL:** RAW é **append-only** e **NUNCA se apaga**.
> O rollback é **lógico**, não físico. Consiste em trocar o `active_ingestion_id`.

#### 13.3.1 Rollback Lógico (Implementação Correcta)

```python
def rollback_to_previous(current_user: str, reason: str) -> bool:
    """
    Rollback lógico para a ingestão anterior.
    
    CRÍTICO: RAW NUNCA é apagado. O rollback apenas:
    1. Troca o active_ingestion_id para a versão anterior
    2. Marca CURATED como inactivo (soft delete)
    3. Regista na auditoria
    """
    with transaction():
        # 1. Obter ingestão activa actual
        current = execute(
            "SELECT active_ingestion_id, previous_ingestion_id FROM factory_meta.active_run WHERE id = 1"
        ).fetchone()
        
        if not current or not current.previous_ingestion_id:
            raise ValueError("Não existe ingestão anterior para rollback")
        
        previous_id = current.previous_ingestion_id
        rolled_back_id = current.active_ingestion_id
        
        # 2. Swap do active_run (ROLLBACK LÓGICO)
        execute("""
            UPDATE factory_meta.active_run 
            SET 
                active_ingestion_id = %s,
                previous_ingestion_id = %s,
                activated_at = NOW(),
                activated_by = %s
            WHERE id = 1
        """, previous_id, rolled_back_id, current_user)
        
        # 3. Marcar ingestão como ROLLED_BACK (não apagar)
        execute("""
            UPDATE factory_meta.ingestion_runs 
            SET status = 'ROLLED_BACK'
            WHERE id = %s
        """, rolled_back_id)
        
        # 4. Registar na auditoria
        execute("""
            INSERT INTO factory_meta.activation_history 
            (ingestion_id, action, performed_by, reason)
            VALUES (%s, 'ROLLED_BACK', %s, %s)
        """, rolled_back_id, current_user, reason)
    
    logger.info(f"Rollback completed: {rolled_back_id} -> {previous_id}")
    return True


def get_active_data() -> Dict[str, pd.DataFrame]:
    """
    Obter dados da ingestão activa.
    
    CURATED é sempre filtrado pelo active_ingestion_id.
    """
    active_id = execute(
        "SELECT active_ingestion_id FROM factory_meta.active_run WHERE id = 1"
    ).scalar()
    
    result = {}
    for table in CURATED_TABLES:
        result[table] = pd.read_sql(
            f"SELECT * FROM factory_curated.{table} WHERE _source_ingestion_id = %s",
            conn, params=[active_id]
        )
    
    return result
```

#### 13.3.2 Limpeza Física (Política de Retenção)

> A limpeza física de RAW só ocorre via **políticas de retenção**, nunca por rollback.

```sql
-- Política de retenção: Apagar RAW com mais de 90 dias (execução manual/cron)
-- NUNCA executar durante rollback normal
DELETE FROM factory_raw.ordens_fabrico 
WHERE _ingestion_timestamp < NOW() - INTERVAL '90 days'
  AND _ingestion_id NOT IN (
      SELECT active_ingestion_id FROM factory_meta.active_run
  );
```

#### 13.3.3 CLI de Rollback

```bash
# Rollback para ingestão anterior
python -m factory_data_product.cli rollback \
    --reason "Erro detectado na ingestão"

# Listar ingestões disponíveis
python -m factory_data_product.cli list-ingestions

# Activar ingestão específica (avançado)
python -m factory_data_product.cli activate \
    --ingestion-id <uuid> \
    --reason "Restauro manual"
```

### 13.4 Segurança

| Aspecto | Implementação |
|---------|---------------|
| **Autenticação** | JWT via ProdPlan ONE |
| **Autorização** | RBAC: `factory:read`, `factory:write`, `factory:admin` |
| **Encriptação** | TLS em trânsito, AES-256 em repouso |
| **Auditoria** | Logs de todas as operações com user_id |
| **Dados Sensíveis** | `FuncionarioNome` e `ValorHora` são PII - acesso restrito |

---

## 14. Critérios de Aceitação (Definition of Done)

### 14.1 Checklist de Aceitação

| # | Critério | Verificação |
|---|----------|-------------|
| 1 | Pipeline de ingestão executa sem erros | `exit code = 0` |
| 2 | Todos os gates BLOCKING passam | `quality_gates.blocking_failed = 0` |
| 3 | Trust Index por tabela dentro dos bounds | Ver secção 10.1 |
| 4 | Testes unitários passam | `pytest tests/unit -v` |
| 5 | Testes de integração passam | `pytest tests/integration -v` |
| 6 | Testes de qualidade passam | `pytest tests/quality -v` |
| 7 | Performance dentro do budget | Ver secção 12.6 |
| 8 | Documentação actualizada | Este documento |
| 9 | Rollback testado | `cli rollback --ingestion-id <uuid>` |
| 10 | Métricas Prometheus expostas | `/metrics` endpoint |

### 14.2 Critérios de Rejeição

A implementação é REJEITADA se:

1. Qualquer gate BLOCKING falhar
2. Trust Index de qualquer tabela crítica < 40
3. Testes unitários falharem
4. Performance exceder budget em > 50%
5. Rollback não funcionar
6. Dados PII expostos sem autorização

---

## 15. Apêndice: Glossário, Convenções e Limites do Sistema

### 15.1 Glossário

| Termo | Definição |
|-------|-----------|
| **Backlog** | Soma de HorasPrevistas_Final para fases em aberto |
| **Gargalo** | Fase com backlog_dias > capacidade disponível |
| **Lead Time** | Tempo entre DataCriacao e DataAcabamento |
| **Trust Index** | Pontuação de confiança dos dados (0-100) |
| **Curadoria** | Processo de normalização e validação de dados |
| **Gate** | Verificação de qualidade com threshold |
| **Idempotência** | Mesma entrada produz mesmo resultado |

### 15.2 Convenções de Nomenclatura

| Tipo | Convenção | Exemplo |
|------|-----------|---------|
| Schema | `factory_{layer}` | `factory_raw`, `factory_curated` |
| Tabela | `snake_case` | `ordens_fabrico` |
| Coluna original | `snake_case` do Excel | `of_data_criacao` |
| Coluna derivada | `snake_case` descritivo | `horas_previstas_final` |
| Flag | `is_*` ou `has_*` | `is_open`, `has_conflict` |
| Metadado | `_prefixo` | `_ingestion_id`, `_trust_index` |

### 15.3 Limites do Sistema

| Limite | Valor | Justificação |
|--------|-------|--------------|
| Tamanho máximo Excel | 100 MB | Performance de parsing |
| Linhas por tabela | 10M | Performance de queries |
| Ingestões por dia | 10 | Evitar sobrecarga |
| Retenção de RAW | 90 dias | Compliance |
| Retenção de META | 365 dias | Auditoria |

### 15.4 Afirmações Proibidas

O sistema **NUNCA** pode afirmar:

1. "Custo real da ordem X é €Y"
2. "Produtividade do funcionário X é Y%"
3. "OEE da fábrica é X%" — **Razão técnica:** OEE requer Availability = Tempo Disponível / Tempo Planeado, que exige dados de paragens de máquina. A fórmula "fases iniciadas / total fases" **NÃO É** Availability no sentido OEE.
4. "Capacidade real da fase X é Y horas"
5. "Entrega garantida para dia X"
6. "Gargalo confirmado na fase X"
7. "Availability da fase X é Y%" — **Razão:** Sem dados de paragens reais, qualquer "availability" calculada é uma métrica diferente (ex: "taxa de início").

### 15.5 Afirmações Permitidas (com Qualificação)

O sistema **PODE** afirmar:

1. "Custo **teórico estimado** da ordem X é €Y (Trust Index: Z)"
2. "Backlog **teórico** da fase X é Y horas (cobertura: Z%)"
3. "Gargalo **provável** na fase X (TOC com dados disponíveis)"
4. "Conflito **potencial** de molde (assumindo ocupação de 12h)"
5. "Lead time **histórico médio**: X dias"

---

## Assinaturas

| Papel | Nome | Data | Assinatura |
|-------|------|------|------------|
| Arquitecto | [A preencher] | [A preencher] | __________ |
| Tech Lead | [A preencher] | [A preencher] | __________ |
| Product Owner | [A preencher] | [A preencher] | __________ |
| CTO | [A preencher] | [A preencher] | __________ |

---

**FIM DO DOCUMENTO**

*Versão: 1.0.0 | Data: 2026-01-27 | Classificação: Enterprise-Grade*

