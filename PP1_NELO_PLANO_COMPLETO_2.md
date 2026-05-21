<!-- ============================================================
     ARQUIVADO 2026-05-19 (Q.60.E) — referência histórica.
     Visão original do produto, congelada, não actualizada desde Q.6.
     Fonte de verdade actual: ./CLAUDE.md + ./agent_docs/sprint_history.md.
     ============================================================ -->

# PP1 × NELO — O PLANO COMPLETO

## Sistema de IA Causal que Aprende com a Fábrica

### Scheduling + LLM + Aprendizagem Contínua — On-Premise, Air-Gapped

NIKUFRA.AI — Abril 2026 — CONFIDENCIAL

---

# PARTE I — VISÃO E CONTEXTO

## 1. A Visão em Uma Frase

O PP1 será o primeiro sistema industrial do mundo que mantém um modelo causal persistente da fábrica, simula intervenções e contrafactuais em tempo real, comunica as razões em linguagem natural, e **melhora com cada decisão que o gestor toma** — tudo on-premise, sem cloud, sem consultores, com verificação formal de cada resposta.

O diferenciador final não é o scheduling (qualquer concorrente replica em 2 anos), nem o LLM (qualquer concorrente compra). É o **conhecimento tácito acumulado** — 12 meses de decisões do gestor da Nelo codificadas no sistema. Isto é impossível de copiar, comprar ou replicar. É o Polanyi digitalizado.

## 2. Números-Chave da Nelo

| Métrica | Valor | Confiança | Notas dev |
|---|---|---|---|
| OFs/dia útil (2024) | 14.7 starts, 14.9 completions | ✅ CONFIRMADO | Throughput €/dia é sobre completions |
| Meta diária | €30.000-35.000/dia | ✅ CONFIRMADO CEO | Volume em euros, não unidades |
| Preço médio/barco | ~€2.350 (€35K ÷ 14.9) | CALCULADO | Mix competição + recreio |
| Operações (6 anos) | 529.450 | ✅ DADOS | Mas muitas com duration=0 (registo batch) |
| Registos com erros | 89.836 | ✅ DADOS | ⚠️ CONFIRMAR: gravidade 1 vs 2 = warning vs defeito? |
| OFs com erros | 68,3% (19.075 de 27.911) | ✅ DADOS | ⚠️ Pode ser QC normal, não 68% defeitos reais |
| Retrabalho Lixagem água | 49,2% das ops | ✅ DADOS | Quase metade volta. Planear capacidade 1.5× |
| Retrabalho Pintura Acab. | 42,4% das ops | ✅ DADOS | Idem |
| Retrabalho Lixagem polim. | 41,3% das ops | ✅ DADOS | Idem |
| Workers que trabalharam 2024 | 122 | ✅ DADOS | Flag Activo=True diz 129 mas real são 122 |
| Fases activas | 41 | ✅ DADOS | |
| Padrões routing (por sequência) | 61 | ✅ DADOS | 39 por set de fases, 61 por sequência ordenada |
| Moldes | 510 (397 em produção) | ✅ DADOS | Até 7 poços |
| Lead time — moda | 15 dias | ✅ DADOS | Barco "normal". Média 51 (inflacionada por outliers) |
| Lead time — mediana | 37 dias | ✅ DADOS | Valor intermédio. Barcos complexos demoram mais |
| WIP estimado | 220-540 barcos | ESTIMADO | 14.7/dia × 15-37 dias. ⚠️ CONFIRMAR real com CEO |
| Gap inter-fase — moda | 0h (23,6% imediatos) | ✅ DADOS | Normal = sem espera. Ver constraints cura abaixo |
| Tempos real vs standard | Divergem até 25× | ✅ DADOS | Standard INÚTIL. Usar dados limpos (ver secção 3.7) |
| Laminagem team size | 88,5% = 2 workers | ✅ DADOS | 11,5% com 1 worker — confirmar se possível ou erro |
| Laminagem Infusão team | 58% = 1 worker, 40% = 2 | ✅ DADOS | Processo DIFERENTE da Laminagem standard |
| CoeficienteX | 6.1 na Laminagem | ✅ CONFIRMADO CEO | É DINHEIRO (prémio/bónus €), NÃO tempo. Ver secção 3.9 |
| Turnos | 95% turno único (manhã) | ✅ DADOS | Capacidade = 8h/dia/worker |
| Pintura Acab. — aptos | 40 na skill matrix | ✅ DADOS | Mas só 22 trabalharam em 2024 |
| Pintura Acab. — reais 2024 | 22 | ✅ DADOS | Bottleneck é alocação, não competência |
| Colagem Golas — workers | 13 | ✅ DADOS | Mais restrito |
| Desmolde como QC | 96,4% erros detectados lá | ✅ DADOS | CQ Final detecta 3,6%. Só 2 pontos de detecção |
| Top 2 erros (35% total) | Molde deformações + baço | ✅ DADOS | |
| Threshold manutenção moldes | NÃO EXISTE NOS DADOS | ⚠️ INVENTADO | Zero colunas de manutenção na tabela Moldes |
| Budget CPO | 60s cada 15 min | ⚠️ NÃO VALIDADO | 1 barco novo/32min. Cada hora pode bastar |
| Pesos fitness | makespan 0.20, tard 0.25... | ⚠️ ARBITRÁRIOS | Sistema de aprendizagem deve ajustar |

## 3. Regras de Produção Extraídas dos Dados

### 3.1 Routing Real

61 padrões de routing por sequência (39 por set de fases sem considerar ordem). O CPO usa os 61 porque a ordem importa para scheduling.
- 219 modelos → padrão principal (18 fases com Pintura Acabamento)
- 110 modelos → padrão 2 (16 fases sem Pintura Acabamento)
- 85 modelos → padrão 3 (19 fases com Colagem Barcos)
- 85 modelos → padrão 4 (18 fases com Corte Peças + Colagem Barcos)
- 400 modelos → 46 padrões menores

Exemplo: K1 Vanquish L SCS (18 fases):

```
Não Laminado (1.5h) → Prep.Molde (1.5h) → Pintura gelcoat (1.5h)
→ LAMINAGEM (8h, 2 workers) → Cura (1.5h auto) → Desmolde (0.5h)
→ Corte (0.8h) → Colagem Peças (1.2h) → Acabamento 2 (1.5h)
→ Lixagem polimento (1h) → CQ Montagem (1h) → Montagem (1.5h)
→ CQ Final (1.5h) → Armazém → Embalado → Entregue
```

### 3.2 Cadeia de Erros

| Fase Culpada | Detectada em | Erros | % |
|---|---|---|---|
| Laminagem | Desmolde | 25.111 | 48% |
| Pintura | Desmolde | 15.123 | 29% |
| Prep. Molde | Desmolde | 11.231 | 22% |

**REGRA:** O Desmolde é o ponto QC de facto (96,4% dos erros). CQ Final detecta 3,6%. São os únicos 2 pontos de detecção. Planear buffer DEPOIS do Desmolde.

### 3.3 Retrabalho

| Fase | Retornos | Taxa REAL | Moda retorno | Implicação CPO |
|---|---|---|---|---|
| Lixagem água | 19.149 | **49,2%** | 1× | Quase metade volta. Capacidade = 1.5× |
| Pintura Acabamento | 12.826 | **42,4%** | 1× | Idem |
| Lixagem polimento | 16.221 | **41,3%** | 1× | Idem |
| Montagem | 1.205 | 4,2% | 1× | Baixo |
| Lixagem seco | 5.572 | ~25% | 1× | Significativo |

**REGRA CPO:** NÃO é "buffer 15-20%". É planear com **capacidade 1.5× nestas 3 fases** porque quase metade das operações repete. A moda do retorno é 1× (volta uma vez, não duas).

### 3.4 Skill Matrix

| Fase | Aptos (skill matrix) | Trabalharam 2024 | Nota |
|---|---|---|---|
| Laminagem | 85 | (confirmar) | Standard: 88.5% com 2 workers |
| Laminagem Infusão | (confirmar) | (confirmar) | 58% com 1 worker, 40% com 2 — processo DIFERENTE |
| Pintura Acabamento | **40** (não 22) | **22** | Bottleneck é ALOCAÇÃO, não competência |
| Colagem Golas | 13 | (confirmar) | Mais restrito |
| Desmolde | 16 | (confirmar) | |

⚠️ **CORRECÇÃO:** A skill matrix diz 40 pessoas sabem fazer Pintura Acabamento, mas só 22 trabalharam de facto. O bottleneck pode ser de gestão (não colocam os outros 18 a pintar) e não de skills.

Equipa por operação: 80% = 1 pessoa, max 5. Laminagem standard é excepção (88.5% = 2). Laminagem Infusão é outra excepção (58% = 1 worker — tratar como fase separada).

### 3.5 Moldes Multi-Cavidade

1 poço: 279 | 2: 53 | 3: 19 | 4: 36 | 5: 16 | 6: 64 | 7: 2

**REGRA:** Agrupar ordens do mesmo modelo para maximizar utilização. Molde de 6 poços = 6 barcos em paralelo.

⚠️ **SEM DADOS DE MANUTENÇÃO.** A tabela Moldes tem: MoldeId, MoldeNome, MoldeEstado, MoldeModelo, MoldeNumeroPocosId, MoldeModeloId, MoldeTamanhoId. Zero colunas sobre manutenção, usos, ou última intervenção. Para implementar manutenção preventiva, é preciso CRIAR esta tabela ou recolher dados do CEO.

### 3.6 Transporte e Volume

| Métrica | Moda | Mediana | Média |
|---|---|---|---|
| Barcos/data transporte | **26** | 74 | 82 |

CEO disse 50 barcos = 1 camião. Se moda=26, o normal é meio camião por data.

⚠️ **CONFIRMAR:** a data de transporte no ERP é por camião ou por dia? Se por dia, podem sair múltiplos camiões no mesmo dia (moda=26 pode ser parcial).

### 3.7 Tempos de Referência para o CPO

**Método:** Remover zeros (registo batch) + remover >P95 (outliers) → moda dos dados limpos → fallback mediana dos não-zeros.

| Fase | Referência | Método | Confiança |
|---|---|---|---|
| Lixagem polimento | **0.5h** | Moda limpa 52% | ALTA |
| Lixagem seco | **1.0h** | Moda limpa 54% | ALTA |
| Corte | **1.0h** | Moda limpa 44% | ALTA |
| Montagem/Finalização | **0.5h** | Moda limpa 37% | ALTA |
| Prep. Molde | **0.5h** | Moda limpa 17% (61% zeros raw) | ALTA |
| Colagem Golas | **1.0h** | Moda limpa 38% | ALTA |
| Acabamento Enverniz. | **1.0h** | Moda limpa 18% | ALTA |
| CQ Montagem | **0.5h** | Moda limpa 31% | ALTA |
| Lixagem água | **0.5h** | Moda limpa 21% | ALTA (cauda longa retrabalho) |
| Colagem Peças | **3.0h** | Moda limpa 14% | MÉDIA |
| Laminagem standard | **4.0h** | Moda limpa 14% | MÉDIA |
| Colagem Barcos | **2.0h** | Moda limpa 10% | MÉDIA |
| Cura | **0.5h** | Moda limpa 11% | MÉDIA (gap depois é 15h = cura real) |
| Pintura Acabamento | **6.5h** | Mediana ≠0 (moda fraca) | MÉDIA |
| Pintura gelcoat | **1.0h** | Mediana ≠0 (84% zeros raw) | MÉDIA |
| Laminagem Infusão | **24.0h** | Moda limpa 9% | MÉDIA — processo completamente diferente |

**Fallback para modelos novos sem histórico:** Standard × 2.

### 3.8 Constraints de Cura/Secagem (gaps obrigatórios entre fases)

Estes são tempos de processo químico. O CPO modela como `min_gap_hours` — a fase seguinte NÃO PODE começar antes. Não são filas a minimizar.

| Transição | min_gap_hours | n (volume) | Processo |
|---|---|---|---|
| Laminagem → Cura | **15.0h** | 17.012 | Cura na estufa |
| Pintura Acabam. → Lixagem seco | **12.5h** | 20.335 | Secagem tinta |
| Pintura Acabam. → Colagem Peças | **12.5h** | 1.229 | Secagem tinta |
| Pintura Acabam. → Colagem Golas | **15.5h** | 134 | Secagem tinta |
| Colagem Peças → Pintura Acabam. | **19.5h** | 6.912 | Cura cola |
| Colagem Peças → Acabamento 2 | **23.5h** | 2.290 | Cura cola |
| Colagem Peças → Acabamento 3 | **21.5h** | 385 | Cura cola |
| Colagem Peças → Acab. Preparação | **23.5h** | 676 | Cura cola |
| Colagem Barcos → Pintura Acabam. | **19.0h** | 777 | Cura cola |
| Acabamento Enverniz. → Lixagem água | **18.0h** | 3.016 | Secagem verniz |
| Colagem Golas → Acabamento 3 | **24.5h** | 175 | Cura cola |
| Colagem Golas → Acabamento 2 | **24.0h** | 183 | Cura cola |
| Lixagem seco → Acab. Enverniz. | **21.5h** | 474 | Secagem |
| Lixagem seco → Acab. Pintura | **21.5h** | 548 | Secagem |
| Lixagem água → Acabamento 2 | **15.0h** | 999 | Secagem |
| Laminagem Infusão → Cura | **24.0h** | 300 | Cura infusão |

Todas as transições NÃO listadas aqui têm moda ≤ 2h — são filas normais que o CPO deve minimizar para zero.

### 3.9 DESCOBERTA CRÍTICA: CoeficienteX É Dinheiro, Não Tempo

**Confirmado pelo CEO da Nelo:** "Esse campo refere-se ao valor do prémio em cada fase. Quando é gerada uma nova OF, é copiado o que está na folha dos standards."

**O que CoeficienteX realmente é:** O bónus/prémio (€) que o operário ganha por executar aquela fase naquele produto. O valor 6.1 na Laminagem NÃO são 6.1 horas do 2º trabalhador — são €6.10 de prémio.

**O que estava errado no código (3 sítios):**

```
❌ pair_assignment.py:6 — "CoeficienteX > 0 encodes the second worker's time"
❌ state.py:59 — "phase codes that require a 2-person crew (CoeficienteX > 0)"
❌ default_configs.py:113 — "WF11 — Laminagem SEMPRE 2 workers (CoeficienteX > 0)"
```

**O que muda:**

A REGRA está certa, a JUSTIFICAÇÃO é que estava errada:
- ❌ Antes: "se CoeficienteX > 0 → par obrigatório" (euros > 0 não significa pares)
- ✅ Agora: "se a fase historicamente teve ≥80% das operações com 2 workers → par obrigatório"
- A Laminagem continua a precisar de 2 workers em 88.5% dos casos — facto dos dados reais (FuncionariosFaseOrdemFabrico), não do CoeficienteX.

**Onde o CoeficienteX DEVE ser usado:**

No módulo Custos (src/profit/), NÃO no workforce:
- CS01: Custo de mão-de-obra por peça (prémio por fase = custo directo)
- Payroll real por operário (prémios acumulados por operador)
- CS03: Margem por encomenda (custos de prémio + restantes)
- CS05: Throughput em euros reais (€30-35K/dia — agora com custo real)

**Fixes obrigatórios no código:**

```
FIX-CX1: Remover 3 comentários errados (pair_assignment, state, default_configs)
FIX-CX2: Substituir critério "CoeficienteX > 0" por "mediana team_size histórico ≥ 2"
FIX-CX3: Verificar que CoeficienteX não entra em NENHUMA conta de duração/tempo
FIX-CX4: Mover CoeficienteX para src/profit/ como campo de custo
FIX-CX5: Alimentar módulo Custos com prémios reais por fase/modelo
```

**Lição:** Se H1 (CoeficienteX) estava 100% errada, NENHUMA hipótese deve ser tratada como facto sem confirmação. As hipóteses H2-H5 também devem ser confirmadas antes de implementar.

### 3.10 Regra Dual-Resource Corrigida

A Laminagem precisa de 2 workers. Isto é facto. Mas o critério muda:

```python
# ❌ ERRADO (baseado em CoeficienteX — que é prémio em €)
def requires_pair(phase_id):
    return coeficienteX[phase_id] > 0  # euros > 0 não significa pares

# ✅ CORRECTO (baseado em dados históricos reais)
def requires_pair(phase_id):
    historical_team_sizes = get_team_sizes_from_history(phase_id)
    median_team = median(historical_team_sizes)
    pct_pairs = sum(1 for t in historical_team_sizes if t >= 2) / len(historical_team_sizes)
    return pct_pairs >= 0.80  # ≥80% das operações históricas tiveram 2+ workers
```

Fases que requerem par (dados reais):
- Laminagem standard: 88.5% com 2 workers → PAR OBRIGATÓRIO
- Laminagem Infusão: 58% com 1, 40% com 2 → PAR OPCIONAL (tratar como fase separada)

---

# PARTE II — ARQUITECTURA

## 4. Princípios Inalteráveis

1. **"LLM propõe, kernel decide"** — O kernel é determinístico, nunca alucina. O LLM traduz de/para linguagem natural.
2. **Safety net** — O CPO NUNCA devolve pior que baseline. Se o GA produz candidato pior, o baseline ganha.
3. **Advisory mode** — O sistema NUNCA escreve no ERP sem aprovação humana. Cada alteração é uma sugestão na Timeline de Aprovação.
4. **Hyper-heuristic** — Optimiza parâmetros do scheduler, não o problema directamente.
5. **Aprendizagem contínua** — Cada decisão do gestor torna o sistema mais inteligente. Cada rejeição é um data point.

## 5. Stack Técnica (o que está na máquina)

| Componente | Tecnologia | Estado |
|---|---|---|
| Backend | FastAPI + Python 3.11 | ✅ A correr |
| Base dados | PostgreSQL 16 + pgvector | ✅ A correr |
| LLM | Ollama + Gemma 4 E4B | ✅ GPU com drivers |
| Scheduling | CPO v4.0 (Python + OR-Tools) | ✅ Implementado |
| Frontend | React 19 + Vite + shadcn/ui | ✅ 41 páginas |
| Cache | Redis | Opcional em dev |
| Events | Kafka (Redpanda futuro) | Desligado em dev |
| ERP cliente | SQL Server (Nelo) | ❌ Não ligado ainda |
| Deploy actual | Python directo + PostgreSQL local | ✅ Na máquina final |

## 6. Arquitectura de 5 Camadas

```
Layer 1 — RLM (Recursive Language Model)
  Estado da fábrica (220-540 barcos, 41 fases, 510 moldes, 122 operadores)
  carregado como variável num REPL Python. LLM explora via sub-queries
  tipadas, nunca recebe tudo na prompt (~200K tokens impossível).

Layer 2 — POETIQ Loop
  Gerar → Executar (kernel) → Criticar → Refinar. 2-5 iterações.
  Com RLM: iterações informadas (sabe os conflitos antes de propor).

Layer 3 — Kernel CPO v4.0 (Simulador Causal)
  Pipeline 6 fases: Greedy → GA+FRRMAB → MAP-Elites → Surrogate →
  CP-SAT Rolling Horizon → Workforce Optimizer. Budget: ~60s/ciclo.
  Resolve DRCFFS-R. Opera em Rung 2 (intervenção) e Rung 3 (contrafactual).

Layer 4a — RAG Industrial
  pgvector + multilingual-e5-large + HyDE. Conteúdo: Factory Logic
  Contract, 61 routing templates, skill matrix, histórico erros/moldes,
  schedule-as-code commits com explain traces.

Layer 4b — LLM Fine-Tuned Causal
  Gemma 4 E4B + QLoRA + GRPO. Dataset: 2500+ pares causais gerados
  pelo kernel com dados reais da Nelo. Code-first prompting.

Layer 5 — Trust Index + Causal Coherence
  8 componentes. Gates de decisão. Verificação em 5 camadas.
  CC < 0.7 bloqueia resposta do LLM.

LAYER TRANSVERSAL — SISTEMA DE APRENDIZAGEM
  Cada decisão do gestor alimenta 3 camadas de aprendizagem:
  regras explícitas → pesos adaptativos → DPO no LLM.
  O sistema melhora com cada commit aceite ou rejeitado.
```

## 7. Schedule-as-Code — Commits Imutáveis

Cada versão do plano é um commit imutável:

```python
ScheduleCommit:
    commit_id: str           # SHA-256 do estado
    parent_id: str           # hash da versão anterior
    author: str              # humano ou agent
    timestamp: datetime      # UTC
    message: str             # razão da alteração
    delta: dict              # o que mudou vs anterior
    kpis: dict               # snapshot TODOS os KPIs
    operations: list         # plano completo (self-contained)
    alternatives: list       # MAP-Elites representativas
    rejected_alternatives: list  # cenários rejeitados + KPIs + razão
    trust_index: float       # TI no momento
    evidence_refs: list      # dados que alimentaram
    scenarios_tested: int    # quantos o POETIQ avaliou
    user_preference_signal: dict  # Tolman: aceite vs rejeitado
```

**O campo `rejected_alternatives` é o mais importante de todo o sistema.** Cada alternativa rejeitada com KPIs e razão é um data point para aprendizagem. São as 10 linhas de código mais valiosas do projecto.

## 8. Trust Index — 7+1 Componentes

| Comp. | Nome | Cálculo | Peso |
|---|---|---|---|
| C | Completeness | 1 se dados completos | 0.15 |
| V | Validity | 1 se passa schema/range | 0.20 |
| F | Freshness | exp(-age/τ) | 0.15 |
| K | Consistency | exp(-\|z-score\|/κ) | 0.20 |
| P | Provenance | Tier: sensor > historian > ERP > manual | 0.15 |
| A | Anomaly | 1 - P(anomaly) | 0.10 |
| E | Evidence | 1 se verificável | 0.05 |
| CC | Causal Coherence | LLM response vs DAG | (8º, futuro) |

**Gates:**
- TI < 0.50 → solver em modo sugestão
- TI < 0.60 → usar P90 durations
- TI < 0.70 → reorder automático off
- TI < 0.75 → auto-commit off (aprovação humana)
- TI < 0.80 → disposição qualidade bloqueada

---

# PARTE III — CPO v4.0: O MOTOR DE SCHEDULING

## 9. Classificação do Problema

**DRCFFS-R:** Dual-Resource Constrained Flexible Flow Shop with Re-entrance, Alternative Routing, and Setup-dependent Transitions. NP-hard.

| Dimensão | Incompol (v3) | Nelo (v4) |
|---|---|---|
| Tipo | Single-stage parallel | Multi-stage flexible flow shop |
| Centros | 1 (prensas) | 4+ (laminagem, pintura, colagem, montagem...) |
| Recursos | Máquina só | Máquina + Operador (dual-resource) |
| Routing | Linear | 61 templates + A/B |
| Re-entrance | Não | 4 variantes laminagem |
| Setup | Tool (~30 min) | Mold (1h-1h30) |
| Cromossoma | 7 genes escalares | 1D permutação + decode |
| Workforce | Não | 122 ops, skills, dual-resource |
| Espaço busca | ~10^6-10^8 | ~10^6 (reduzido com decode) |
| Budget | ~15s | ~60s/ciclo |

## 10. Pipeline Greedy — 8 Fases

```
Fase 1: DEMAND AGGREGATION → Net demand (descontando stock, WIP)
Fase 2: BACKWARDS SCHEDULING → Latest-start por fase (puxado transporte)
Fase 3: ROUTING SELECTION → Routing A ou B por barco
Fase 4: SETUP GROUPING → Agrupar modelos por molde
Fase 5: MULTI-CENTER DISPATCH → Schedule por centro + operador (EDD)
Fase 6: WORKFORCE ASSIGNMENT → Hungarian (skill × quality × tier)
Fase 7: BUFFER & JIT → Buffers baseados em variância histórica
Fase 8: SCORING → KPIs (makespan, tardiness, €/dia, quality_risk)
```

Target: < 2s para 50 barcos activos.

## 11. Cromossoma v4.0

```python
ChromosomeV4:
    permutation: list[int]           # ordem de processamento (PRIMARY)
    routing_choices: dict[int, str]  # operation_id → "A" ou "B"
    setup_grouping_gap: int          # dias gap para split groups
    buffer_pct: float                # buffer JIT
    worker_quality_weight: float     # peso qualidade vs velocidade
```

Decode heuristic (1D → 3D): para cada operação na permutação, atribuir máquina (min load), worker (best skill × quality), time slot (earliest available respeitando precedências + transport dates).

## 12. Pipeline CPO — 6 Fases Cascading

| Fase | Tempo | O que faz |
|---|---|---|
| 1. Greedy 8-phase | 2s | Solução viável inicial |
| 2. GA + FRRMAB | 30s | 100 pop × 200 gen, 6 operadores, c=0.2 |
| 3. MAP-Elites 3D | 5s | Grid 10×10×5, 5-10 alternativas |
| 4. Surrogate RF | (embebido) | Pre-screen 80%, threshold=1.2× |
| 5. CP-SAT Rolling Horizon | 15s | L-RHO warm-start, janelas 2 dias |
| 6. Workforce Optimizer | 3s | Hungarian + quality risk |
| **TOTAL** | **~60s** | |

### 6 Operadores de Mutação (FRRMAB c=0.2, window=200):

1. swap_adjacent — swap 2 ops adjacentes
2. swap_random — swap 2 ops aleatórias (respeita precedências)
3. insert_move — remover + inserir noutra posição
4. flip_routing — mudar routing A↔B
5. shift_group — mover grupo mesmo modelo em bloco
6. perturb_params — mutar genes escalares

### MAP-Elites 3D:
- X: Utilização laminagem (0-100%)
- Y: Atraso máximo vs. transporte (0 a +14 dias)
- Z: Operadores idle (0-50%)

### Fitness Multi-Objectivo:

```python
fitness = (
    0.20 × makespan +
    0.25 × tardiness_transporte +      # transport dates are king
    0.15 × idle_operadores +
    0.15 × setup_time_total +
    0.10 × quality_risk_score +
    0.15 × (-throughput_euro_dia)       # €30-35K target
)
# ⚠️ ESTES PESOS SÃO ARBITRÁRIOS. Não há base empírica.
# O sistema de aprendizagem (Camada 2, secção 18) ajusta-os
# com base nas preferências reveladas do gestor.
# Após ~50 commits, os pesos reais substituem estes defaults.
# Se o GA convergir para soluções estranhas nos primeiros dias,
# ajustar manualmente antes da Camada 2 estar activa.
```

## 13. Workforce Optimizer (Hungarian)

```python
# Cost matrix: lower = better
cost[op, worker] = 1 / (skill_score × quality_history × tier_match + 0.01)

# Regras Nelo:
# - Laminagem STANDARD: pares obrigatório (88.5% = 2 workers nos dados históricos)
#   CRITÉRIO: mediana team_size histórico ≥ 2 (NÃO CoeficienteX — que é prémio €)
# - Laminagem INFUSÃO: 1 ou 2 workers (58% = 1 nos dados). Tratar como fase separada.
# - Retrabalho pintura: volta ao causador (campo chefe)
# - Barcos complexos: operadores com mais experiência
# - Zero idle: quando acaba, sistema sugere próxima tarefa
# - CoeficienteX NÃO é usado aqui — é prémio monetário, vai para src/profit/
```

## 14. Quality Risk (Gradient Boosting)

Treinado em 89.836 erros. Features:
- worker.error_rate_phase, worker.error_rate_model, worker.tier
- model.historical_error_rate
- mold.age_days, mold.uses_since_maintenance
- phase.historical_error_rate (Laminagem = 102.5%!)
- current_wip_load, previous_phase_error

Threshold: P(erro) > 0.7 → alerta preventivo.

## 15. Bugs CPO v3.0 a Resolver ANTES

1. Auto-buffer gera 849 dias → cap max(deadline + 30 dias)
2. MachineState.last_tool reset → persistir entre avaliações GA
3. FRRMAB c=0.5 → c=0.2
4. MAP-Elites 2-3 células → grid 10×10×5, injecção periódica
5. Surrogate threshold 1.5× → 1.2×
6. crew_priority ignorado em quick mode
7. Duplicação scripts/cpo/ vs backend/cpo/
8. ~3.185 linhas dead code
9. ortools ausente em requirements.txt
10. Zero testes para stress.py e cpsat_polish.py

---

# PARTE IV — O SISTEMA DE APRENDIZAGEM (o moat real)

## 16. Princípio Central

**Cada decisão do gestor torna o sistema mais inteligente. Cada rejeição é tão valiosa como cada aprovação.**

O scheduling, o LLM, os dashboards — qualquer concorrente replica. O conhecimento tácito acumulado de 12 meses de decisões — ninguém copia. Quando o gestor se reformar, o conhecimento fica no sistema.

O ciclo: CPO gera 5 cenários → gestor vê na Timeline → escolhe cenário B → cenários A,C,D,E ficam rejeitados com KPIs e razão → 4 pares de preferência automáticos → sistema ajusta.

## 17. Camada 1 — Regras Explícitas (funciona hoje, zero ML)

**O que é:** O sistema detecta padrões nas rejeições e cria regras verificáveis.

**Como funciona:**

```python
class PreferenceRuleDetector:
    """Analisa commits rejeitados e detecta padrões.
    Corre diariamente. Sem ML — são contadores."""
    
    def detect_patterns(self, commits: list[ScheduleCommit]) -> list[Rule]:
        rules = []
        
        # Exemplo 1: Rejeição temporal
        # Se gestor rejeita 5+ cenários que mexem na Laminagem à sexta
        friday_laminagem_rejections = [
            c for c in commits
            if c.rejected
            and c.involves_phase("Laminagem")
            and c.proposed_for_weekday == 4  # sexta
        ]
        if len(friday_laminagem_rejections) >= 5:
            rules.append(Rule(
                type="temporal_block",
                description="Não propor alterações na Laminagem à sexta",
                confidence=len(friday_laminagem_rejections) / total_friday_proposals,
                auto_apply=False,  # requer confirmação do gestor
            ))
        
        # Exemplo 2: Preferência de cenário
        # Se gestor sempre escolhe cenário com menos setup
        # quando throughput é semelhante (delta < 5%)
        setup_preference = analyze_tradeoff_preference(
            commits, metric_preferred="setup_time", 
            metric_sacrificed="throughput_euro",
            tolerance=0.05
        )
        if setup_preference.confidence > 0.8:
            rules.append(Rule(
                type="tradeoff_preference",
                description="Gestor prefere menos setup a mais throughput "
                           "quando diferença < 5%",
                confidence=setup_preference.confidence,
                auto_apply=False,
            ))
        
        # Exemplo 3: Operador fixo
        # Se gestor move sempre o operador X para a mesma fase
        operator_patterns = detect_operator_affinity(commits)
        for pattern in operator_patterns:
            if pattern.occurrences >= 3:
                rules.append(Rule(
                    type="operator_affinity",
                    description=f"{pattern.worker_name} preferido para "
                               f"{pattern.phase_name}",
                    confidence=pattern.occurrences / pattern.opportunities,
                    auto_apply=False,
                ))
        
        return rules
    
    def propose_rules(self, rules: list[Rule]) -> None:
        """Mostrar regras detectadas ao gestor para confirmação."""
        for rule in rules:
            notify(
                f"Reparei que {rule.description} "
                f"(confiança: {rule.confidence:.0%}). "
                f"Quero evitar propor isto no futuro. Confirma?"
            )
            # Se gestor confirma → regra activa
            # Se gestor rejeita → padrão descartado
            # Se gestor modifica → regra ajustada
```

**Implementação:** ~200 linhas de Python. Sem dependências ML. Contadores sobre commits rejeitados + detecção de padrões simples. Funciona desde o dia 1 de produção.

**Exemplos concretos na Nelo:**

- "O gestor nunca aceita cenários que reduzem operadores na Pintura abaixo de 18" → regra: min_workers_pintura = 18
- "O gestor prefere sempre manutenção preventiva a correctiva quando custo < €500" → regra: manutenção_preventiva_threshold = 500
- "O gestor rejeita cenários com mais de 3 barcos K1 no mesmo dia de Laminagem" → regra: max_k1_laminagem_dia = 3
- "O gestor aceita sempre turno extra quando throughput < €25K/dia" → regra: auto_suggest_turno_extra_below = 25000

## 18. Camada 2 — Pesos Adaptativos da Fitness (precisa de ~50 commits)

**O que é:** Os pesos da fitness function do GA adaptam-se automaticamente às preferências reveladas do gestor.

**Como funciona:**

```python
class AdaptiveFitnessWeights:
    """Ajusta os pesos da fitness com base nas preferências
    reveladas pelos commits aceites vs rejeitados.
    
    Intuição: se o gestor consistentemente escolhe planos com
    menos setup mesmo quando throughput é ligeiramente menor,
    o peso do setup deve subir e o do throughput descer.
    """
    
    DEFAULT_WEIGHTS = {
        "makespan": 0.20,
        "tardiness": 0.25,
        "idle": 0.15,
        "setup": 0.15,
        "quality_risk": 0.10,
        "throughput": 0.15,
    }
    
    def learn_from_commits(
        self,
        commits: list[ScheduleCommit],
        min_pairs: int = 50,
    ) -> dict[str, float]:
        """Extrair pesos implícitos das preferências do gestor.
        
        Método: para cada commit com alternatives rejeitadas,
        temos pares (aceite, rejeitado). Os KPIs de cada par
        revelam que tradeoffs o gestor faz. Regressão logística
        sobre os deltas de KPI → coeficientes = pesos implícitos.
        """
        pairs = []
        for commit in commits:
            if not commit.rejected_alternatives:
                continue
            accepted_kpis = commit.kpis
            for alt in commit.rejected_alternatives:
                rejected_kpis = alt["kpis"]
                # Delta: positivo = aceite é melhor nesta métrica
                delta = {
                    metric: accepted_kpis.get(metric, 0) - rejected_kpis.get(metric, 0)
                    for metric in self.DEFAULT_WEIGHTS
                }
                pairs.append((delta, 1))  # 1 = aceite ganhou
        
        if len(pairs) < min_pairs:
            return self.DEFAULT_WEIGHTS  # dados insuficientes
        
        # Regressão logística: quais deltas predizem a escolha?
        from sklearn.linear_model import LogisticRegression
        X = [list(p[0].values()) for p in pairs]
        y = [p[1] for p in pairs]
        model = LogisticRegression()
        model.fit(X, y)
        
        # Coeficientes = importância relativa de cada métrica
        raw_weights = dict(zip(self.DEFAULT_WEIGHTS.keys(), 
                              abs(model.coef_[0])))
        total = sum(raw_weights.values())
        learned_weights = {k: v/total for k, v in raw_weights.items()}
        
        # Blend com defaults (70% learned, 30% default)
        # para evitar overfitting a padrões temporários
        blended = {}
        for k in self.DEFAULT_WEIGHTS:
            blended[k] = 0.7 * learned_weights[k] + 0.3 * self.DEFAULT_WEIGHTS[k]
        
        return blended
    
    def report_to_user(self, default_w, learned_w) -> str:
        """Mostrar ao gestor como os pesos mudaram."""
        changes = []
        for k in default_w:
            delta = learned_w[k] - default_w[k]
            if abs(delta) > 0.02:
                direction = "↑" if delta > 0 else "↓"
                changes.append(
                    f"{k}: {default_w[k]:.0%} → {learned_w[k]:.0%} {direction}"
                )
        if changes:
            return ("Com base nas suas últimas decisões, ajustei as "
                    "prioridades do planeamento:\n" + "\n".join(changes))
        return "Prioridades mantidas — as suas decisões são consistentes."
```

**Exemplo concreto na Nelo após 3 meses:**

O gestor aprova 80 commits. Ao analisar as preferências reveladas:
- Peso do setup SOBE de 15% para 22% (gestor valoriza muito reduzir mudanças de molde)
- Peso do throughput DESCE de 15% para 10% (gestor aceita menos €/dia se evitar setups)
- Peso do quality_risk SOBE de 10% para 18% (gestor é avesso a risco de qualidade)

O sistema reporta: "Reparei que valoriza mais a redução de setups do que o throughput bruto, e que é especialmente cauteloso com risco de qualidade. Ajustei os pesos do planeamento. Os próximos planos vão reflectir isto."

## 19. Camada 3 — DPO no LLM (precisa de ~500 pares, ~6 meses)

**O que é:** Direct Preference Optimization no Gemma. O modelo aprende não só O QUE o gestor prefere mas COMO pensa e comunica.

**Como funciona:**

```python
class DPODatasetBuilder:
    """Constrói dataset de preferências para DPO a partir dos commits.
    
    Cada commit com rejected_alternatives gera pares:
    - chosen: a explicação/resposta que levou à aprovação
    - rejected: a explicação/resposta de cada alternativa rejeitada
    
    O DPO treina o LLM para gerar respostas mais parecidas com
    as aceites e menos parecidas com as rejeitadas.
    """
    
    def build_pairs(self, commits: list[ScheduleCommit]) -> list[DPOPair]:
        pairs = []
        for commit in commits:
            if not commit.rejected_alternatives:
                continue
            
            # Contexto: estado da fábrica no momento da decisão
            context = {
                "factory_state": commit.evidence_refs,
                "question": commit.message,  # pergunta original
                "trust_index": commit.trust_index,
            }
            
            # Resposta aceite (chosen)
            chosen_response = format_as_copilot_response(
                commit.kpis, commit.delta, commit.message
            )
            
            # Respostas rejeitadas
            for alt in commit.rejected_alternatives:
                rejected_response = format_as_copilot_response(
                    alt["kpis"], alt["delta"], alt.get("reason", "")
                )
                pairs.append(DPOPair(
                    context=context,
                    chosen=chosen_response,
                    rejected=rejected_response,
                ))
        
        return pairs
    
    def finetune_dpo(self, pairs: list[DPOPair], model_path: str):
        """DPO fine-tuning trimestral."""
        if len(pairs) < 500:
            logger.info(f"Apenas {len(pairs)} pares — esperando por 500+")
            return
        
        # QLoRA + DPO via Unsloth (2x mais rápido)
        from unsloth import FastLanguageModel
        model, tokenizer = FastLanguageModel.from_pretrained(model_path)
        # ... DPO training loop ...
        logger.info(f"DPO fine-tuning completo com {len(pairs)} pares")
```

**O que o LLM aprende com DPO:**

- **Estilo de comunicação:** Se o gestor aprova mais quando as respostas têm números concretos e menos texto, o LLM aprende a ser conciso e numérico.
- **Prioridades implícitas:** Se o gestor rejeita cenários agressivos, o LLM aprende a propor cenários conservadores primeiro.
- **Vocabulário:** Se o gestor usa "barcos" em vez de "unidades de produção", o LLM adopta o vocabulário dele.
- **Timing:** Se o gestor rejeita alterações propostas para manhã quando já são 16h, o LLM aprende a não propor mudanças para o dia seguinte ao fim do dia.

## 20. Camada 4 — ABLkit (Abductive Learning Loop)

**O que é:** Quando o LLM erra um diagnóstico, o kernel corrige e o par (erro, correcção) treina o LLM. O sistema melhora especificamente nos erros que comete.

```python
# Loop ABL — corre quando LLM erra
def abductive_learning_cycle(desvio, e4b_prediction, kernel_result):
    if not kernel_result.matches(e4b_prediction):
        # LLM disse "causa é operador ausente"
        # Kernel prova que causa é "molde degradado"
        training_data.append({
            'context': desvio.factory_state,
            'wrong': e4b_prediction,    # DPO negativo
            'correct': kernel_result,    # DPO positivo
        })
        # Re-fine-tune trimestral com erros acumulados
```

## 21. Pipeline Completo de Aprendizagem

```
DIA 1 → Regras default. Pesos default. LLM base.

MÊS 1 (30 commits):
  → Camada 1 activa: primeiras regras detectadas
    "Gestor nunca aceita < 18 pintores"
    "Gestor prefere manutenção preventiva"
  → Camada 2: dados insuficientes (precisa 50+)
  → Camada 3: dados insuficientes (precisa 500+)

MÊS 3 (120 commits):
  → Camada 1: ~15 regras activas, confirmadas pelo gestor
  → Camada 2 activa: pesos da fitness ajustados
    Setup 15% → 22%, quality_risk 10% → 18%
  → Camada 3: ~480 pares acumulados, quase pronto

MÊS 6 (300 commits):
  → Camada 1: ~30 regras, sistema quase não propõe cenários rejeitáveis
  → Camada 2: pesos estabilizados, reflectem o gestor
  → Camada 3 activa: primeiro DPO fine-tuning
    LLM adopta vocabulário e estilo do gestor
  → Camada 4: ~50 erros corrigidos pelo kernel, ABLkit dataset

MÊS 12 (600+ commits):
  → Todas as camadas activas e estabilizadas
  → O sistema É o gestor digitalizado
  → Taxa de rejeição de cenários: < 5% (vs ~40% no mês 1)
  → O gestor reformava-se e o conhecimento ficava no sistema
```

## 22. O Que Tem de Ser Gravado Desde o Dia 1

**CRÍTICO:** Nenhuma das 4 camadas funciona sem dados. Os dados vêm dos commits. Cada commit DEVE incluir:

1. **Estado da fábrica no momento** — snapshot de WIP, carga por centro, operadores disponíveis, moldes em uso
2. **Todos os cenários gerados** — não só o escolhido, TODOS os que o MAP-Elites produziu
3. **KPIs de cada cenário** — makespan, tardiness, throughput €, setup, quality_risk, idle
4. **Qual foi escolhido** — com timestamp e user_id
5. **Quais foram rejeitados** — com KPIs e razão (se o gestor der)
6. **Contexto temporal** — dia da semana, hora, proximidade de expedição

**Sem isto, o sistema nunca aprende.** Cada commit sem `rejected_alternatives` é um data point perdido para sempre.

---

# PARTE V — O LLM: PIPELINE E RACIOCÍNIO CAUSAL

## 23. POETIQ Loop

```
PROPOSE  → LLM gera cenário (informado por RLM + RAG)
OPTIMIZE → Kernel CPO executa: greedy → GA → MAP-Elites → CP-SAT
EVALUATE → Rubric analítica + comparação MAP-Elites archive
TEST     → Simulação perturbação ("e se máquina X falha?")
ITERATE  → Refinamento dirigido pela critique
QUALIFY  → Colocar no MAP-Elites + commit + gravar preferência
```

Score = kernel_metrics × 0.7 + llm_qual × 0.3

## 24. Code-First Causal Prompting

O E4B foi desenhado para workflows agénticos e code. Cada interacção usa formato código, não texto natural. Vantagem: +10-20% em benchmarks causais.

### DAG da Nelo em código (system prompt)

```python
NELO_DAG = {
    'mold_setup_time': lambda center, mold: (
        0 if center.current_mold == mold.id
        else mold.setup_minutes  # 60-90 min
    ),
    'laminagem_duration': lambda op, workers: (
        op.coeficiente if len(workers) >= 2
        else float('inf')  # impossível com 1 worker
    ),
    'desmolde_qc': lambda op: (
        predict_error_prob(op.model_id, op.mold_id, op.worker_ids)
    ),
    'retrabalho_routing': lambda error: (
        error.causador_id if error.phase == 'Pintura Acabamento'
        else assign_best_available(error.phase)
    ),
    'throughput_euro': lambda schedule, day: (
        sum(model.sale_price for op in schedule.completed_on(day)
            if op.is_final_phase)
    ),
}
```

### Perguntas causais em código

```python
# Intervenção (Rung 2)
do(K1_Vanquish_OF4271.routing = 'B')
query: completion_date, transport_batch.on_time

# Contrafactual (Rung 3)
counterfactual(
    observed: throughput_euro = 22000,
    intervention: remove(transport_batch='2026-05-15'),
    query: throughput_euro
)

# Abdução (Peirce)
observe(retrabalho_lixagem rose from 15% to 23%)
task: identify root_cause using Mill_method_of_difference
```

### Respostas estruturadas

```python
CausalChain(
    root_cause = 'mold_degradation(K1_7_ML_03, uses=847)',
    mechanism = 'deformation → interior enrugado → retrabalho lixagem',
    effect = 'throughput = 22000 (target: 30000)',
    counterfactual = 'if maintenance_now: throughput recovers to 29000',
    recommendation = 'maintenance + reroute 3 boats',
    confidence = 0.91,
    aristotle = {
        'material': 'mold_usage_log, skill_matrix',
        'formal': 'maintenance_threshold = 800 uses',
        'efficient': 'mold K1 7 ML (03) exceeded threshold',
        'final': 'maximize throughput >= 30000 €/dia'
    }
)
```

## 25. Dataset Causal — 7 Tipos de Pares

| # | Tipo | Exemplo Nelo | % |
|---|---|---|---|
| 1 | Estado factual | 'Quantos K2 na Laminagem?' | 15% |
| 2 | Intervenção simples | 'Se routing B para K1 Vanquish?' | 20% |
| 3 | Intervenção composta | 'Se reparar molde E adicionar 2 laminadores?' | 10% |
| 4 | Contrafactual | 'Se expedição de sexta não existisse?' | 15% |
| 5 | Abdução | 'Retrabalho subiu 8pp — porquê?' | 15% |
| 6 | Common cause | 'Laminagem E Pintura Acabamento atrasam — causa comum?' | 10% |
| 7 | Cadeia longa | 'Molde degradado → erro → desmolde → retrabalho → atraso → throughput cai' | 15% |

## 26. Aristóteles — 4 Causas no Explain Trace

| Causa | Significado | Exemplo Nelo |
|---|---|---|
| Material | De que dados vem | Folha_IA, mold_usage_log, skill_matrix |
| Formal | Que regra seguiu | Routing template #1, ATCS dispatch, dual-resource |
| Eficiente | O que provocou | Molde degradado (847 usos, threshold 800) |
| Final | Para que objectivo | Maximizar throughput ≥ €30K/dia |

## 27. Mill's 5 Methods — Templates Diagnóstico

| Método | Template Nelo |
|---|---|
| Diferença | kernel.counterfactual(remove=molde_degradado). Se retrabalho cai, molde é causa. |
| Concordância | Todas as semanas com throughput < €25K — factor comum? |
| Variação concomitante | Correlação usos_molde vs taxa_erro. Se linear = causal. |
| Resíduos | Retrabalho total - explicado por moldes - por operadores = inexplicado (material?) |
| Método conjunto | Molde reparado SEMPRE melhora E degradado SEMPRE piora → confirma |

## 28. DoWhy-GCM — Inferência Causal Formal

```python
# DAG formal com 22 nós, 3 confundidores
dag.add_edges_from([
    ('model_complexity', 'laminagem_duration'),
    ('mold_uses_since_maintenance', 'mold_error_rate'),
    ('operator_skill_laminagem', 'laminagem_error_rate'),
    ('operator_pair_compatibility', 'laminagem_duration'),
    ('desmolde_defect_rate', 'retrabalho_lixagem_rate'),
    ('retrabalho_lixagem_rate', 'throughput_euro_dia'),
    ('ambient_temp_nave', 'cura_time'),         # confundidor
    ('resina_lot', 'laminagem_error_rate'),      # confundidor
    ('turno', 'error_probability'),              # confundidor
    # ... (22 nós total)
])

# Atribuição causal: quanto cada factor contribuiu?
contributions = gcm.intrinsic_causal_influence(
    causal_model, target='throughput_euro_dia'
)
# {'mold_error_rate': 0.38, 'retrabalho_lixagem': 0.27,
#  'transport_tardiness': 0.18, 'operator_skill': 0.11}
```

## 29. PCMCI+ — Descoberta Causal

Após 3-6 meses de dados, corre semanal para descobrir relações ocultas:

**Descobertas prováveis:**
- Molde K1 7 ML (03) piora às segundas (efeito térmico nave)
- Paulo Gomes 20% mais rápido em K4 que K1 (skill-model)
- Resina fornecedor A causa 3% mais bolhas (quality-source)
- Expedições sexta = 15% mais retrabalho (pressão deadline)
- Colagem Golas por operadores < 5 meses = 2× mais defeitos

Cada descoberta → proposta ao gestor → DAG actualizado.

## 30. Verificação em 5 Camadas

| Camada | Verifica | Tempo |
|---|---|---|
| 1. Syntactic | Formato CausalChain válido? | <1ms |
| 2. DAG-consistent | Relações seguem DAG Nelo? | <1ms |
| 3. Direction-check | Direcção correcta? | <1ms |
| 4. NLI-verified | Explicação suportada por factos? | ~200ms |
| 5. Kernel-validated | Resultado numérico correcto? | ~2s |

CC = camada1 × camada2 × camada3 × NLI_score × kernel_match. Threshold: CC ≥ 0.85.

## 31. Entropia Causal na Fitness

```python
def causal_entropy_nelo(schedule):
    """Flexibilidade preservada pelo plano."""
    return (
        0.25 * load_entropy_per_center +
        0.20 * capacity_slack +
        0.15 * molds_ready_diversity +
        0.20 * flexible_workers_available +
        0.20 * healthy_molds_count
    )
# Peso na fitness: 0.05 (efeito suave, não domina)
```

---

# PARTE VI — REQUISITOS FUNCIONAIS (90+ requisitos)

## 32. Advisory Mode — Write-Gate (9 requisitos)

WG01-WG09: Sistema calcula continuamente; cada alteração é sugestão. Timeline de Aprovação com delta view, aprovação individual/bloco, auto-aprovação configurável, anti-fatigue. WG10: MAP-Elites mostra 5-10 alternativas com trade-offs explícitos.

## 33. Factory Map (6 requisitos)

FM01-FM06: Mapa visual com vista por artigo, visão actual/futura, % rutura, KPIs, carga sobre linha.

## 34. MRP (8 requisitos)

MR01-MR08: Config MP, prospeção material, análise erros por fornecedor, alertas falta, stock mínimo, correcção manual, histórico uso, tudo editável.

## 35. Planeamento e Scheduling (24 requisitos)

PL01-PL24: Planeamento 1-1.5 dias, granularidade 15 min, setup optimization, routing 61 templates + A/B, backwards scheduling transporte, tempos históricos NUNCA standard, buffer pós-Desmolde, moldes multi-cavidade, throughput €/dia como objectivo, replaneamento contínuo.

## 36. Workforce (12 requisitos)

WF01-WF12: Auto-reallocation, skill tiers, smart assignment, skill matrix visual, laminagem pares (dados históricos, NÃO CoeficienteX), respeitar bottlenecks (Pintura=40 aptos/22 reais, Colagem Golas=13).

## 37. Qualidade e Retrabalho (11 requisitos)

QA01-QA11: Retrabalho com causador, pintura volta a quem errou, manutenção preventiva moldes (tracking usos, alerta > threshold), ML quality risk, capacidade 1.5× lixagens (49% retrabalho).

## 38. Alertas (8 requisitos)

AL01-AL08: Falta dados, falta material, barcos > X dias, stock negativo, capacidade excedida, gargalo, ordens em risco, molde > threshold manutenção.

## 39. Custos (6 requisitos)

CS01-CS06: Custo por peça/encomenda/SKU, margem, throughput €/dia como KPI principal (€30-35K), valor venda por modelo no scheduler.

## 40. Relatórios, Stock, Config (restantes)

RP01-RP05: Relatório por cliente, produção, qualidade, automáticos, export PDF/Excel.
ST01-ST04: Correcção stock, histórico, reconciliação.
CG01-CG13: Tudo configurável — prioridades, tempos, stocks, routing, calendário, perfis, transporte, threshold moldes, valor venda.

---

# PARTE VII — ECOSSISTEMA: LIGAÇÕES ENTRE MÓDULOS

## 41. Estado Actual (15 ligações em falta)

O software tem 17 módulos mas estão desligados. Ligações que FALTAM:

| Ligação | Impacto |
|---|---|
| plan ← hr | CPO não sabe turnos/ausências |
| plan ← supply | CPO não sabe stock matéria-prima |
| plan ← dqa | Trust Index não gateia scheduler |
| plan ← profit | Fitness sem throughput €/dia |
| explain ← plan | Explicações desligadas do scheduling |
| sandbox ← plan | Simulação sem scheduler |
| workforce ← plan + hr | Dashboard desligado do real |
| improve ← ml + plan | Módulo isolado |

Prioridade de ligação: plan ← profit (throughput €/dia) primeiro, porque é o que o CEO quer ver.

---

# PARTE VIII — ROADMAP HONESTO (24 semanas)

## 42. Princípio: Valor primeiro, sofisticação depois

O gestor da Nelo não quer teoria — quer ver €/dia no dashboard. O LLM não precisa de fine-tuning para ser útil — precisa de dados reais. A aprendizagem contínua não precisa de DPO — precisa de commits com rejected_alternatives gravados.

## 43. Fase 0 — Bugs + Fundação (Semanas 1-3)

- **PRIMEIRO:** Fixes CoeficienteX (CX1-CX5) — remover lógica errada, mover para Custos
- **SEGUNDO:** Confirmar H3, H4, H5 com CEO da Nelo (10 minutos de conversa)
- Resolver 10 bugs CPO v3.0
- Adicionar 16 constraints de cura/secagem ao decoder (secção 3.8)
- Ligar plan ← profit (throughput €/dia na fitness)
- Implementar rejected_alternatives no ScheduleCommit (CO1)
- Garantir que cada commit grava estado da fábrica + alternativas + razão
- Ligar máquina à rede Nelo → acesso SQL Server

**Entregável: CPO sem bugs, CoeficienteX corrigido, cura/secagem implementada, commits com dados de aprendizagem, acesso ao ERP**

## 44. Fase 1 — Copilot que Funciona (Semanas 4-6)

- LLM (Gemma E4B) responde perguntas sobre a fábrica com dados reais do PostgreSQL
- Testar 100 perguntas reais ("quantos barcos K1 na Laminagem?")
- Se accuracy < 70% → resolver com prompt engineering
- RAG populado com 61 routing templates, skill matrix, histórico erros
- Camada 1 de aprendizagem activa: contadores sobre commits

**Entregável: Copilot funcional com dados reais + primeiras regras aprendidas**

## 45. Fase 2 — CPO Greedy + Timeline (Semanas 7-9)

- Pipeline greedy 8-fases funcional com dados Nelo
- Timeline de Aprovação com 5-10 alternativas do MAP-Elites
- Gestor vê cenários, escolhe um, rejeita os outros → dados gravados
- Backwards scheduling com datas transporte reais
- Alertas moldes > threshold manutenção

**Entregável: Scheduling funcional com Timeline + dados de preferência a acumular**

## 46. Fase 3 — CPO Optimizado + Copilot Integrado (Semanas 10-13)

- GA+FRRMAB + MAP-Elites 3D + Surrogate RF
- Copilot chama CPO via POETIQ one-shot ("e se adicionar 2 pintores?")
- CP-SAT Rolling Horizon
- Workforce Optimizer (Hungarian)
- Camada 2 de aprendizagem activa: pesos adaptativos (50+ commits)

**Entregável: CPO completo + Copilot integrado + pesos a adaptar-se**

## 47. Fase 4 — ML + Qualidade + Trust (Semanas 14-17)

- Quality risk model (XGBoost treinado em 89K erros)
- Mold maintenance model (RF treinado em 510 moldes)
- Trust Index completo (7 componentes + gates)
- Explain traces com 4 causas (Aristóteles)
- Ligar módulos em falta (hr, supply, dqa)

**Entregável: ML funcional + Trust Index + ecossistema ligado**

## 48. Fase 5 — Fine-tuning + Aprendizagem Profunda (Semanas 18-21)

- Fine-tuning QLoRA se necessário (1000+ pares causais)
- Code-first causal prompting
- POETIQ loop iterativo (não só one-shot)
- Camada 3 pronta se 500+ pares de preferência
- DoWhy-GCM se dados suficientes

**Entregável: LLM fine-tuned (se necessário) + aprendizagem profunda activa**

## 49. Fase 6 — Polish + Produção (Semanas 22-24)

- 3 Umwelts: Gestor (scheduling + explain) / Operador (tablet) / CEO (dashboard €/dia)
- Stress test com dados reais
- PCMCI+ causal discovery (se 3+ meses de dados)
- Primeiro DPO batch (se 500+ pares)
- Documentação + SLA

**Entregável: Sistema em produção + a aprender continuamente**

---

# PARTE IX — 12 INSIGHTS ANCESTRAIS

| # | Insight | Origem | Aplicação Nelo |
|---|---|---|---|
| 1 | Diagnóstico abdutivo | Peirce | Throughput cai → hipóteses → contrafactual kernel |
| 2 | Latent learning / DPO | Tolman | Cenários rejeitados = sinais negativos automáticos |
| 3 | Affordances UI | Gibson | 'Laminagem pode aceitar 3 barcos' não 'utilização 72%' |
| 4 | Core knowledge axioms | Spelke | Dual-resource, molde exclusivo, precedência BOM |
| 5 | Curriculum treino | Piaget | sensorimotor → concreto → formal |
| 6 | Entropia scheduling | Wissner-Gross | Preferir planos com flexibilidade futura |
| 7 | Três Umwelts | Uexküll | Gestor / Operador / CEO |
| 8 | Causal discovery | Reichenbach | PCMCI+ descobre relações ocultas nos dados |
| 9 | Common cause | Reichenbach | Quando 3+ centros desviam, verificar recurso partilhado |
| 10 | Active inference | Friston | Sistema pede dados quando Trust Index cai |
| 11 | Prehension enrichment | Whitehead | Commits com cenários testados + rejeitados |
| 12 | Economy explanation | Mach | Explain trace em 3-5 passos |

---

# PARTE X — MOAT COMPETITIVO

## 50. 5 Barreiras

1. **Kernel DRCFFS-R** — 18-24 meses para replicar
2. **Dataset causal proprietário** — só existe porque o kernel + Nelo existem
3. **Conhecimento tácito acumulado** — 12 meses de decisões impossível de comprar
4. **Compounding 12 insights** — copiar 3 de 12 ≠ 25% do valor
5. **Causal discovery contínuo** — PCMCI+ descobre relações específicas à Nelo

## 51. Comparação

| Capacidade | PP1 | SAP Joule | Siemens Copilot | EthonAI |
|---|---|---|---|---|
| Rung 2 (intervenção) | Sim (kernel) | Não | Parcial | Sim |
| Rung 3 (contrafactual) | Sim (kernel) | Não | Não | Parcial |
| Aprendizagem contínua | 4 camadas | Não | Não | Não |
| Dual-resource scheduling | Sim | Parcial | Não | Não |
| On-premise air-gapped | Sim | Não | Parcial | Cloud |
| Trust Index verificado | 8 componentes | Não | Parcial | Não |
| Preço PME | <€500/mês | ≫ | ≫ | ≫ |

---

# PARTE XI — FÓRMULA DE ANÁLISE DE DADOS HISTÓRICOS

## 52. O Método (para TODAS as métricas do CPO)

Qualquer valor de referência da Nelo (duração de fase, gap entre fases, team size, lead time, batch transporte) passa por este pipeline antes de ser usado no código.

```python
def valor_referencia(dados_raw: Series, nome: str) -> dict:
    """
    Pipeline de limpeza + valor de referência para o CPO.
    
    Passo 1: Remover zeros (registo batch / instantâneo falso)
    Passo 2: Remover > P95 (outliers — barcos parados semanas)
    Passo 3: Moda dos dados limpos (arredondada a 0.5h)
    Passo 4: Se moda fraca (<8% dos dados), fallback para mediana ≠0
    Passo 5: Cruzar com bom senso + coeficiente standard
    
    Retorna: valor de referência + método + confiança
    """
    
    # PASSO 1 — Remover zeros
    # Ninguém lamina um barco em 0h. Ninguém prepara molde em 0h.
    # Zeros = registo batch (início e fim ao mesmo tempo) ou erro.
    # EXCEPÇÃO: fases pass-through (Desmolde, CQ) podem ser 0 legítimo.
    n_total = len(dados_raw)
    n_zeros = (dados_raw.abs() < 0.05).sum()
    pct_zeros = n_zeros / n_total * 100
    
    nao_zeros = dados_raw[dados_raw > 0.05]
    
    if len(nao_zeros) < 20:
        # Quase tudo é zero — fase pass-through (ex: Desmolde, CQ)
        return {
            'referencia': 0.0,
            'metodo': 'fase instantânea (pass-through)',
            'confianca': 'ALTA',
            'pct_zeros': pct_zeros,
            'n_limpo': 0,
        }
    
    # PASSO 2 — Remover outliers acima do P95
    # P95 corta barcos que ficaram parados por razões excepcionais
    # (fim de semana, falta material, máquina avariada).
    # Não representam o tempo de trabalho normal.
    p95 = nao_zeros.quantile(0.95)
    limpos = nao_zeros[nao_zeros <= p95]
    
    if len(limpos) < 20:
        return {
            'referencia': round(nao_zeros.median() * 2) / 2,
            'metodo': 'mediana ≠0 (poucos dados limpos)',
            'confianca': 'BAIXA',
            'pct_zeros': pct_zeros,
            'n_limpo': len(limpos),
        }
    
    # PASSO 3 — Moda dos dados limpos
    # Arredondar a 0.5h para agrupar valores próximos.
    # A moda é o valor que MAIS ACONTECE — é o "normal" da fábrica.
    limpos_arredondados = (limpos * 2).round() / 2
    moda = limpos_arredondados.mode().iloc[0]
    moda_pct = (limpos_arredondados == moda).sum() / len(limpos_arredondados) * 100
    
    # PASSO 4 — Moda forte (≥8%) ou fallback mediana
    if moda > 0 and moda_pct >= 8:
        # Moda é um pico real — usar como referência
        metodo = f'moda limpa ({moda_pct:.0f}%)'
        confianca = 'ALTA' if moda_pct > 15 else 'MÉDIA'
        referencia = moda
    else:
        # Moda fraca — usar mediana dos não-zeros
        metodo = 'mediana ≠0 (moda fraca)'
        confianca = 'MÉDIA'
        referencia = round(nao_zeros.median() * 2) / 2
    
    # PASSO 5 — Cruzar com bom senso
    # Se referência > 5× o coeficiente standard → suspeitar
    # Se referência < 0.1× o standard → suspeitar
    # NOTA: standard é inútil para scheduling mas útil como sanity check
    
    return {
        'referencia': referencia,
        'metodo': metodo,
        'confianca': confianca,
        'moda': moda,
        'moda_pct': moda_pct,
        'mediana_nao_zeros': round(nao_zeros.median(), 1),
        'media': round(dados_raw.mean(), 1),
        'pct_zeros': round(pct_zeros, 1),
        'n_limpo': len(limpos),
        'p95': round(p95, 1),
    }
```

### 52.1 Quando usar o quê

| Situação | Valor a usar | Razão |
|---|---|---|
| Moda > 0 e representa ≥15% dos dados | **MODA** | Pico claro — é o "normal" |
| Moda > 0 e representa 8-15% dos dados | **MODA** (com cautela) | Pico existe mas dispersão alta |
| Moda = 0 ou < 8% | **MEDIANA dos não-zeros** | Moda é artefacto de registo |
| >90% dos valores são 0 | **0 (pass-through)** | Fase instantânea legítima (CQ, Desmolde) |
| < 20 dados não-zero | **NÃO USAR** | Dados insuficientes — confirmar com CEO |

### 52.2 Erros a NUNCA cometer

1. **Nunca usar a média.** A média de tempos de produção está SEMPRE inflacionada por outliers (barcos parados dias/semanas). A média do lead time é 51 dias, a moda é 15. A média mente.

2. **Nunca usar a mediana sem filtrar zeros.** Se 61% dos dados são zero (Prep. Molde), a mediana é zero. Mas ninguém prepara um molde em 0h — são registos mal feitos.

3. **Nunca aceitar moda=0 para fases com trabalho real.** Prep. Molde, Pintura, Laminagem, Montagem — todas têm trabalho real. Moda=0 nestas fases é erro de dados, não realidade. Usar mediana dos não-zeros.

4. **Nunca misturar tempos de trabalho com tempos de espera.** A duração de "Acabamento 2" tem mediana 27h — inclui tempo de espera entre camadas. O tempo de TRABALHO real é diferente do tempo total registado. Os dados da Nelo não distinguem — o CPO deve usar o total (inclui espera) porque é isso que ocupa o recurso.

5. **Nunca confundir gap inter-fase com fila.** Gap entre Colagem Peças e Pintura Acabamento = 19.5h (moda). NÃO é fila — é cura da cola. O CPO modela como constraint, não como ineficiência a eliminar. Gaps com moda 0-2h SÃO filas minimizáveis.

### 52.3 O pipeline aplicado na Nelo (exemplo)

```
Laminagem standard:
  Raw: 22.580 registos, 22% zeros, média 6.9h, mediana 3.7h
  Passo 1: remover 5.018 zeros → 17.562 não-zeros
  Passo 2: P95 = 15.2h → remover 878 outliers → 16.684 limpos
  Passo 3: arredondar a 0.5h → moda = 4.0h (14%)
  Passo 4: 14% ≥ 8% → moda é válida
  Passo 5: standard = 7.9h, ratio = 0.5× → razoável (real < standard)
  → REFERÊNCIA: 4.0h | MÉTODO: moda limpa 14% | CONFIANÇA: MÉDIA

Pintura Acabamento:
  Raw: 29.532 registos, 8.5% zeros, média 12.7h, mediana 5.7h
  Passo 1: remover 2.510 zeros → 27.022 não-zeros
  Passo 2: P95 = 47.8h → remover 1.351 → 25.671 limpos
  Passo 3: arredondar → moda = 8.0h (6.9%)
  Passo 4: 6.9% < 8% → moda FRACA → fallback mediana ≠0 = 6.5h
  Passo 5: standard = 1.7h, ratio = 3.8× → standard é claramente errado
  → REFERÊNCIA: 6.5h | MÉTODO: mediana ≠0 | CONFIANÇA: MÉDIA

Gap Laminagem→Cura:
  Raw: 23.060 registos, 27% zeros, média 11.7h
  Passo 1: remover zeros → 16.834 não-zeros
  Passo 2: P95 = 24.3h → 15.993 limpos
  Passo 3: moda = 15.0h (concordância com tempo de estufa)
  Passo 5: 15h de cura na estufa é fisicamente plausível
  → CONSTRAINT: min_gap_hours = 15.0h | TIPO: cura obrigatória
```

---

# PARTE XII — AUDITORIA DE CÓDIGO (29 problemas lógicos)

## 53. Decoder (decoder.py) — 7 problemas

**D1. CRÍTICO — Setup counter sempre zero.**
`_last_on_machine_has_different_family()` retorna SEMPRE `False`. O campo `setups` no resultado é sempre 0. O termo `w_setups × setups` na fitness é inútil. O GA NÃO optimiza setups.
```
FIX: Implementar comparação real de setup_family entre última op na máquina e op actual.
```

**D2. CRÍTICO — Sem constraints de cura/secagem.**
O decoder agenda operações seguidas sem gap obrigatório. Na Nelo, Colagem→Pintura precisa 19.5h de cura. Laminagem→Cura precisa 15h. O decoder ignora — agenda tudo back-to-back, fisicamente impossível.
```
FIX: Adicionar min_gap_hours ao FactoryState (carregar da tabela de constraints).
     No decoder, ao calcular earliest_start, adicionar:
     earliest = max(earliest, pred_end + min_gap[pred_phase][current_phase])
```

**D3. ALTO — quality_weight do cromossoma não é usado.**
O GA muta `quality_weight` mas o decoder nunca o lê. `_pick_workers` é first-fit por disponibilidade. A qualidade dos workers não entra na selecção.
```
FIX: No _pick_workers, ordenar por (quality_score × quality_weight + availability × (1-quality_weight))
     usando dados do FactoryState.
```

**D4. ALTO — Sem backwards scheduling.**
O decoder agenda para a frente (forward). Lê `due_date` só para calcular tardiness no fim. Na Nelo, o scheduling deveria partir da data de transporte e subtrair tempos.
```
FIX: Pré-calcular latest_start_date por operação antes do decode.
     latest_start = due_date - sum(durations das fases seguintes) - sum(curing gaps)
     Usar no cálculo de earliest_start: max(earliest, latest_start - buffer).
```

**D5. ALTO — Worker selection ignora skills/qualidade.**
`_pick_workers` ordena apenas por `worker_free_at`. Dois laminadores com 20 anos e dois com 2 meses são idênticos para o decoder.
```
FIX: Ordenar por (skill_score × quality_weight_from_chromosome, worker_free_at, worker_id).
```

**D6. MÉDIO — Mold batch threshold rígido.**
Se `len(members) < 2: continue` — molde de 6 poços com 1 operação elegível não faz batch. Não há lógica para decidir se é melhor esperar por mais operações ou avançar com poços vazios.
```
FIX: Decisão depende de urgência. Se a operação tem tardiness > 0, avançar. Se não, esperar N horas.
```

**D7. MÉDIO — Soft horizon pode gerar planos impossíveis.**
Operações que excedem `horizon_end` são marcadas como `infeasible` MAS são agendadas na mesma. O resultado tem `success: True` com operações para lá do horizonte.
```
FIX: Separar claramente: ou não agenda (hard horizon) ou agenda e marca como warning (soft).
     Nunca ter success=True com ops infeasible agendadas.
```

## 54. Fitness (fitness.py) — 5 problemas

**F1. CRÍTICO — Sem throughput €/dia.**
A meta €30-35K/dia confirmada pelo CEO está ausente da fitness. O GA optimiza makespan e tardiness mas ignora valor de produção.
```
FIX: Adicionar w_throughput_euro e calcular:
     throughput = sum(model.sale_price for op in schedule if op.is_final_phase and op.end <= target_date)
     fitness += w_throughput * (target_throughput - throughput) / target_throughput
```

**F2. ALTO — Sem idle operadores.**
O spec define peso 0.15 para operadores idle. A fitness não tem este objectivo. Planos com 30% operadores parados não são penalizados.
```
FIX: Calcular idle_ratio = 1 - (total_busy_minutes / (n_workers × horizon_minutes))
     fitness += w_idle * idle_ratio
```

**F3. MÉDIO — Pesos não normalizados.**
w_makespan=1.0, w_tardiness=10.0, w_setups=0.5 — são multiplicadores sobre unidades diferentes. 1h de tardiness vale 10, 1h de makespan vale 1. Pode ser intencional mas não está justificado.
```
FIX: Normalizar cada objectivo para [0,1] antes de multiplicar pelo peso.
     Ou documentar que a escala actual é intencional e porquê.
```

**F4. ALTO — quality_risk OFF por defeito.**
`w_quality_risk = 0.0`. Com 89.836 erros e retrabalho de 49% nas lixagens, quality risk devia estar ON.
```
FIX: Default w_quality_risk = 0.10. Ligar automaticamente quando quality_risk_predictor está disponível.
```

**F5. CRÍTICO (cascata D1) — setups sempre 0.**
O input é zero porque o decoder não conta setups. Mesmo com w_setups=0.5, o termo é 0×0.5=0.
```
FIX: Resolver D1 primeiro. Depois este resolve-se sozinho.
```

## 55. Cromossoma (chromosome.py) — 3 problemas

**C1. CRÍTICO — Sem routing_choices.**
O spec define routing A/B por operação. O cromossoma não tem `dict[int, str]` de routing. O GA não optimiza escolhas de routing.
```
FIX: Adicionar routing_choices: Dict[int, str] = field(default_factory=dict)
     Adaptar crossover (uniform para routing), mutação (flip A↔B).
```

**C2. BAIXO — quality_weight range inconsistente.**
Docstring diz 0.0-1.0, `random()` gera até 0.8. E o decoder não usa o valor (D3).
```
FIX: Alinhar range. Implementar D3 primeiro, depois este faz sentido.
```

**C3. BAIXO — Sem setup_grouping_gap.**
O spec define este gene para controlar agrupamento por molde.
```
FIX: Adicionar setup_grouping_gap: int = 5 (dias). Usar no mold batching do decoder.
```

## 56. FRRMAB (frrmab.py) — 2 problemas

**FR1. ALTO — op_flip_routing NÃO é flip routing.**
O nome diz "flip routing A↔B" mas o código faz 2-opt reverse na permutação. É um operador válido mas não implementa routing alternativo (que nem existe no cromossoma — ver C1).
```
FIX: Renomear para op_reverse_subsequence. Quando C1 for implementado,
     criar op_flip_routing real que muda routing_choices[op_id] de A para B.
```

**FR2. MÉDIO — Decay recalcula toda a história.**
Em `record()`, aplica `decay` multiplicando TODOS os valores do deque. Com window=200, são 200 multiplicações por chamada. Ineficiente.
```
FIX: Usar weighted average com decaimento implícito:
     running_avg = decay × running_avg + (1-decay) × new_reward
```

## 57. MAP-Elites (mapelites.py) — 2 problemas

**ME1. ALTO — Eixos não correspondem ao spec.**
Spec: X=Utilização laminagem, Y=Atraso transporte, Z=Operadores idle.
Código: X=avg_utilization (global), Y=total_tardiness_hours, Z=num_late_orders (count, não %).
```
FIX: Mudar Z para idle_operator_ratio. Mudar X para laminagem_utilization
     quando o decoder expor métricas per-centro. Y está aproximadamente correcto.
```

**ME2. BAIXO — Representantes sem explicação de trade-offs.**
`representatives()` devolve cromossomas mas não gera texto explicativo para a Timeline.
```
FIX: Adicionar método explain_representative(elite) que gera:
     "Este plano usa laminagem a 85% com 0 atrasos mas 15% operadores idle."
```

## 58. Engine (engine.py) — 3 problemas

**E1. ALTO — Generations default 50, spec diz 200.**
Com 50 gerações e c=0.2, o FRRMAB mal converge. O GA tem pouca oportunidade de explorar.
```
FIX: Mudar default para 200. Ou parametrizar por tempo (time_limit_sec já existe a 30s).
```

**E2. MÉDIO — Surrogate OFF por defeito.**
`use_surrogate = False`. O spec diz que filtra 80% dos candidatos.
```
FIX: Mudar para True quando min_samples_to_train (20) for atingido. Auto-ligar, não manual.
```

**E3. MÉDIO — FRRMAB reward perdido quando child morre na selecção.**
A child mutada recebe `_frrmab_op` mas o reward só é calculado quando aparece em `scored` na geração seguinte. Se a child é eliminada no tournament, o operador que a gerou nunca recebe feedback.
```
FIX: Calcular reward IMEDIATAMENTE após decode da child (não na geração seguinte).
     reward = max(0, parent_fit - child_fit) / (parent_fit + 1e-6)
     frrmab.record(op_name, reward)
```

## 59. Safety Net (safety_net.py) — 1 problema

**SN1. MÉDIO — Não compara makespan nem throughput.**
Um candidato que duplica o makespan mas mantém zero tardiness passa o safety net. O plano é 2× mais lento mas "não é pior".
```
FIX: Adicionar: if cand_makespan > base_makespan * 1.5: return True (50% degradação)
```

## 60. Write-Gate (decisions.py) — 2 problemas

**WG1. CRÍTICO — Aprovação não executa acção.**
Linha 368: `# TODO: Execute actual action`. O gestor aprova e nada acontece.
```
FIX: Implementar ActionExecutor que aplica o plano ao FactoryState e persiste.
```

**WG2. ALTO — Rollback não funciona.**
Linha 422: `# TODO: Revert state using before_state snapshot`.
```
FIX: Implementar revert usando o parent commit do schedule-as-code.
```

## 61. Trust Index (trust_index.py) — 2 problemas

**TI1. ALTO — Só 4 de 7+1 componentes.**
Completeness 30%, Validity 30%, Consistency 20%, Timeliness 20%. Faltam Provenance, Anomaly, Evidence, Causal Coherence. Pesos somam 100% — redistribuir ao adicionar.
```
FIX: Implementar os 3 em falta com pesos do spec (P=0.15, A=0.10, E=0.05).
     Redistribuir C=0.15, V=0.20, K=0.20, F=0.15.
```

**TI2. BAIXO — Consistency sem lógica.**
`# TODO: Implement specific consistency rules` — retorna valor neutro.
```
FIX: Implementar z-score check entre valores actuais e históricos.
```

## 62. Commits (commits.py) — 1 problema

**CO1. CRÍTICO — Sem campo rejected_alternatives.**
O modelo tem `alternatives` (MAP-Elites) mas não `rejected_alternatives` com KPIs e razão. Sem isto, as 4 camadas de aprendizagem não funcionam.
```
FIX: Adicionar ao modelo:
     rejected_alternatives: Mapped[List[Dict]] = mapped_column(JSONB, default=list)
     user_preference_signal: Mapped[Dict] = mapped_column(JSONB, default=dict)
     Migration Alembic para adicionar colunas.
```

## 63. State (state.py) — 1 problema

**ST1. ALTO — Sem dados de cura/secagem.**
FactoryState carrega centros, workers, moldes, skills. Não carrega `min_gap_hours` entre fases.
```
FIX: Adicionar phase_transition_gaps: Dict[Tuple[str,str], float] ao FactoryState.
     Carregar da DB (tabela nova) ou hardcode os 16 constraints da secção 3.8.
```

## 64. Resumo — 29 problemas + 5 fixes CoeficienteX por prioridade

| Prioridade | # | IDs | Impacto |
|---|---|---|---|
| **P0 — Fix antes de demo** | 11 | D1, D2, F1, WG1, CO1, C1, CX1, CX2, CX3, CX4, CX5 | Output errado ou feature core em falta |
| **P1 — Fix para CPO funcional** | 10 | D3, D4, D5, F2, F4, E1, ME1, ST1, TI1, WG2 | Feature importante em falta |
| **P2 — Fix para qualidade** | 8 | D6, D7, F3, FR1, FR2, E2, E3, SN1 | Lógica suspeita ou ineficiente |
| **P3 — Nice to have** | 5 | C2, C3, ME2, TI2, F5(cascata) | Stubs, naming, polish |

### Fixes CoeficienteX (P0 — fazer ANTES de tudo o resto):

| ID | Fix | Ficheiros | Esforço |
|---|---|---|---|
| CX1 | Remover 3 comentários errados sobre CoeficienteX = tempo | pair_assignment.py, state.py, default_configs.py | 15 min |
| CX2 | Substituir critério "CoeficienteX > 0" por "mediana team_size ≥ 2" | pair_assignment.py, state.py | 1h |
| CX3 | Auditar que CoeficienteX não entra em contas de duração/tempo | decoder.py, fitness.py, engine.py | 2h |
| CX4 | Mover CoeficienteX para src/profit/ como campo de custo | profit/models.py, profit/service.py | 2h |
| CX5 | Alimentar módulo Custos com prémios reais por fase/modelo | profit/service.py, factory_data_product/ | 4h |

---

# PARTE XIII — PRESSUPOSTOS vs CONFIRMADOS

## 66. O que está confirmado (pode implementar)

- Meta €30-35K/dia em valor ✅
- 61 padrões de routing por sequência ✅
- Laminagem standard 88.5% com 2 workers ✅
- Desmolde detecta 96.4% dos erros ✅
- Retrabalho Lixagem água 49.2%, Pintura Acab. 42.4%, Lixagem polim. 41.3% ✅
- 122 workers trabalharam em 2024 ✅
- 40 aptos para Pintura Acabamento mas só 22 trabalharam ✅
- Tempos de referência (secção 3.7) — método limpo ✅
- Constraints de cura/secagem (secção 3.8) — 16 transições com min_gap ✅
- Lead time moda 15 dias, mediana 37 ✅
- Transporte moda 26 barcos/data ✅

## 67. O que é hipótese (confirmar antes de implementar)

| # | Pressuposto | Status | Onde se usa | Risco |
|---|---|---|---|---|
| H1 | CoeficienteX = tempo do 2º worker | ❌ **CONFIRMADO ERRADO** — é prémio/bónus (€) | Workforce, decoder, fitness | CORRIGIDO — ver secção 3.9. Código tem 3 sítios errados |
| H2 | Threshold manutenção moldes = 800 usos | ⚠️ INVENTADO — sem dados | Alertas, quality risk, CPO | Alto — número ficção. Confirmar com CEO |
| H3 | Gravidade 1 = warning, gravidade 2 = defeito | ⚠️ NÃO CONFIRMADO | Quality risk model | Médio — 68% pode ser inspecção normal |
| H4 | Laminagem com 1 worker (11.5%) é erro de registo | ⚠️ NÃO CONFIRMADO | Workforce rules | Médio — pode ser barcos simples que 1 faz |
| H5 | Data transporte = por dia (não por camião) | ⚠️ NÃO CONFIRMADO | Backwards scheduling | Médio — muda o batch size |
| H6 | Replaneamento cada 15 min | Implementável | Budget CPO, arquitectura | Baixo — cada hora pode bastar, ajustável |
| H7 | Pesos fitness (0.20, 0.25, 0.15...) | Implementável | GA do CPO | Baixo — aprendizagem ajusta |
| H8 | WIP ~220-540 barcos | Estimado | Dimensionamento scheduler | Baixo — confirmar com contagem real |

**LIÇÃO DO H1:** O CoeficienteX estava a ser usado como horas em 3 ficheiros de código, e o valor real são euros. Se a hipótese mais importante estava 100% errada, as outras H2-H5 devem ser confirmadas com o CEO antes de implementar. Custo de confirmar: 10 minutos de conversa. Custo de construir sobre erro: semanas de retrabalho.

**IMPLEMENTAR SEM CONFIRMAR:** H6, H7, H8 (ajustáveis ou de baixo risco).

**IMPLEMENTAR COM DEFAULT + OVERRIDE:** H2 (default configurável pelo gestor, sem hardcode de 800).

**CONFIRMAR COM CEO (10 minutos):** H3, H4, H5 — enviar lista antes de implementar.

**CORRIGIDO:** H1 — 5 fixes obrigatórios listados na secção 3.9 (FIX-CX1 a FIX-CX5).

---

# PARTE XIV — REFERÊNCIAS

## Académicas
- Mlekusch & Hartl (2025). DRCFFS with hybrid GA. IJPR 63(5).
- Li et al. (2025). FJSP-MW with GALS. IJPR 63(19).
- L-RHO (2025). Learning-Guided RHO for FJSP. ICLR.
- Lu et al. (2018). Concise chromosome for DFJS. J. Intell. Manuf.
- MAP-Elites MEHH for RCPSP (2022). arXiv:2204.11162.
- Fan et al. (2025). IGA for DRCFJSP. Expert Systems.
- CP-SAT Rostering (Brenndoerfer 2025).
- CARE Duke (2025). Causal reasoning benchmarks.
- MIT Press (2025). Code prompts improve causal reasoning.
- DoWhy-GCM (JMLR 2024). Formal causal inference.
- PCMCI+ (Tigramite). Causal discovery time series.
- Mouret & Clune (2015). MAP-Elites.
- Xu et al. (ICML 2018). Semantic Loss Functions.
- ABLkit (Zhou, 2019). Abductive Learning.

## Dados Nelo
- Folha_IA_Extra.xlsx: 57MB, 529.450 operações, 89.836 erros, 2020-2026
- 10 tabelas: OrdensFabrico (27.911), FasesOrdemFabrico (529.450), FuncionariosFaseOrdemFabrico (423.769), OrdemFabricoErros (89.836), Funcionarios (301), FuncionariosFasesAptos (902), Fases (71), Moldes (510), Modelos (899), FasesStandardModelos (15.445)

---

*PP1 × NELO — O Plano Completo (v3 — com CoeficienteX corrigido)*

*NIKUFRA.AI — Abril 2026 — Confidencial*

*14 partes • 67 secções • 34 bugs de código • 8 hipóteses (1 confirmada errada) • Sistema que aprende.*
