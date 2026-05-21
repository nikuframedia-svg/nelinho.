<!-- ============================================================
     ARQUIVADO 2026-05-19 (Q.60.E) — documento histórico, NÃO usar.
     Versão antiga do CLAUDE.md (cobre só Q.1–Q.6).
     Fonte de verdade actual: ./CLAUDE.md + ./agent_docs/.
     ============================================================ -->

# CLAUDE.md — PP1-Nelo

## Quem és

És o developer sénior do PP1 (ProdPlan ONE) — sistema APS+ML+LLM on-premise para a NELO (Mar Kayaks, Vila do Conde). A equipa é o Luís (produto/cliente) e o João (dev). Estás a desenvolver directamente na máquina de produção final: Ubuntu 24.04, Python 3.11 directo, PostgreSQL 16 local, Ollama + Gemma 4 E4B na RTX 5060 Ti 16GB. Sem Docker. Sem cloud. Deploy nativo + systemd.

## ⚡ Estado actual (commit `2f457cb`, 2026-04-25)

**927 testes PASSED · 323 rotas API · 96 chaves de config seeded em 13 categorias.**

Sprints **Q.1–Q.6 entregues** — fechados os gaps materiais entre `PP1_NELO_PLANO_v4.md` e o HEAD. Ver:
- `README.md` secção "Sprints Q.1–Q.6" (sumário por sprint)
- `.claude/plans/plano-diz-c-digo-scalable-minsky.md` (plano vivo)
- `tests/plan/test_sprint_q_e2e_smoke.py` (15 testes E2E que validam o advisory loop ponta-a-ponta)

Sprints já entregues:
- **Q.1** TrustIndex v1→v2 + tooling frontend
- **Q.2** Despacho/Expedição (DE01-08, 7 endpoints + DispatchPage drag-drop)
- **Q.3** Colaboradores GC01-10 (quality_score Laplace, skill matrix, history, override→Camada 1)
- **Q.4** Drag-drop Planeamento (PreviewDeltaService sub-segundo + Layer 1+2)
- **Q.5** Timeline + CEO Dashboard (OTD, FPY, backlog, expeditions, alerts)
- **Q.6** Polish + 6 tabs Settings (Cura/Moldes/Quality/Trust/Sistema/Aprendizagem) + E2E smoke

## Princípios de código (Karpathy + PP1)

### 1. Pensa antes de codificar

- Antes de implementar, diz as tuas assunções em voz alta. Se não tens a certeza, PERGUNTA.
- Se há várias interpretações, apresenta-as. Nunca escolhas em silêncio.
- Se uma abordagem mais simples existe, diz. Empurra para trás quando justificado.
- Se algo não é claro, PÁRA. Diz o que está confuso.
- **PP1-specific:** Antes de tocar no CPO, decoder ou fitness, verifica se a mudança respeita os Spelke axioms (secção abaixo). Se violares um, PÁRA.

### 2. Simplicidade primeiro

- Código mínimo que resolve o problema. Zero especulação.
- Zero features que não foram pedidas.
- Zero abstracções para código single-use.
- Zero "flexibilidade" ou "configurabilidade" que ninguém pediu.
- Se escreveste 200 linhas e podia ser 50, reescreve.
- **PP1-specific:** Este projecto tem 52K linhas de backend e 17 módulos. NÃO adiciones módulos. NÃO cries novos padrões. Segue os padrões que já existem. Se não existir padrão, pergunta.

### 3. Mudanças cirúrgicas

- Não "melhores" código adjacente, comentários ou formatação.
- Não refactores coisas que não estão partidas.
- Segue o estilo existente, mesmo que fizesses diferente.
- Se notares dead code, menciona — não apagues.
- Se as tuas mudanças criarem imports/variáveis/funções órfãs, remove ESSAS. Não remover pré-existentes.
- **O teste:** Cada linha alterada deve ligar directamente ao pedido.

### 4. Execução orientada a objectivos

- Transforma tarefas em objectivos verificáveis:
  - "Adicionar validação" → "Escrever testes para inputs inválidos, depois fazê-los passar"
  - "Corrigir o bug" → "Escrever teste que reproduz, depois corrigir"
- Para tarefas multi-step, declara o plano:
  ```
  1. [Passo] → verificar: [check]
  2. [Passo] → verificar: [check]
  3. [Passo] → verificar: [check]
  ```
- Critérios de sucesso fortes permitem loop independente. Critérios fracos ("faz funcionar") requerem clarificação.
- **PP1-specific:** Antes de dizer "feito", corre `pytest tests/` e confirma que TODOS os 927 testes passam. Zero regressões.

---

## Arquitectura do projecto

```
src/
├── core/          # Master data (modelos, routing, moldes, fases)
├── plan/          # Scheduling + CPO v4.0 (o coração)
│   ├── cpo/       # chromosome, decoder, engine, fitness, frrmab,
│   │              # mapelites, surrogate, safety_net, state, workforce, commits
│   ├── api/       # transport.py (Q.2), schedule_preview.py (Q.4), cpo.py, schedule.py, mrp.py
│   └── services/  # transport_batch_service, transport_suggestions (Q.2),
│                  # preview_delta_service (Q.4)
├── profit/        # OEE, custos, qualidade, pricing, CoeficienteX (prémios €)
│                  # Q.5: services/dashboard_metrics_service (OTD/FPY/backlog/expeditions)
├── hr/            # Alocações, turnos, payroll
├── copilot/       # LLM, POETIQ, context builder, guardrails, RAG
├── ml/            # XGBoost tempos, quality risk, surrogate, registry
├── explain/       # Explain traces (4 causas Aristóteles)
├── factory_data_product/  # Ingest, quality, drift
├── governance/    # Decision ledger, approval
├── shared/        # Config, DB, auth, outbox, events, redis, kafka
│   └── api/       # decisions.py (write-gate)
├── twin/          # Digital twin / scenarios
├── sandbox/       # Simulação
├── supply/        # Forecast, inventory, MRP
├── workforce/     # Dashboard workforce
│                  # Q.3: employee_extras_service + employee_extras_api (6 endpoints)
├── dqa/           # Trust Index, quality gates
├── improve/       # Sugestões melhoria (isolado)
└── legacy/        # Código legado
```

Frontend: `frontend/src/` — React 19 + Vite + custom **Dark component system** (`frontend/src/components/dark/`) + Tailwind v4. ~46+ páginas (Q.1-Q.6 adicionou DispatchPage, DragDropPlanner, EmployeesPage modais, 6 tabs Settings novas).

Tests: `tests/` — **927 testes**. TODOS devem passar antes de commit.

Deploy: Nativo. `deploy/prodplan-api.service` (systemd). Sem Docker em produção.

Rede: A torre hospeda TUDO. Os PCs/tablets da fábrica acedem via browser na rede local. Não instalam nada.

```
┌─────────────────────────────────────┐
│          TORRE (servidor)           │
│                                     │
│  PostgreSQL ← dados                 │
│  FastAPI    ← backend/API           │
│  Ollama     ← LLM (GPU)            │
│  Caddy      ← serve frontend +     │
│               reverse proxy +       │
│               HTTPS                 │
│  React build ← ficheiros estáticos  │
│                                     │
│  IP: 192.168.X.X (rede fábrica)    │
│  URL: http://pp1.nelo.local        │
└──────────┬──────────────────────────┘
           │ rede local (Ethernet/Wi-Fi)
     ┌─────┼─────┬──────────┐
     │     │     │          │
  ┌──┴──┐ ┌┴───┐ ┌┴────┐ ┌──┴──────┐
  │ PC  │ │ PC │ │ PC  │ │ Tablet  │
  │escr.│ │prod│ │CEO  │ │operador │
  │     │ │    │ │     │ │chão fáb │
  └─────┘ └────┘ └─────┘ └─────────┘
  browser  browser browser  browser
  (Chrome) (Chrome) (Chrome) (Chrome)
```

Nenhum PC instala nada. Abrem browser → escrevem endereço → PP1 aparece.
O Caddy serve o React build como ficheiros estáticos e faz proxy para o FastAPI.
Cada utilizador vê o seu Umwelt: gestor vê planeamento, operador vê tablet, CEO vê dashboard (RBAC).

---

## O domínio: fábrica de kayaks

A NELO produz ~14.7 kayaks/dia de competição (K1, K2, K4) e recreio. 41 fases de produção, 510 moldes, 122 operadores activos, 61 padrões de routing. Meta: €30-35K/dia de produção em valor.

### Fases mais importantes

- **Laminagem** — fibra carbono/kevlar. 4h (moda). 88.5% com 2 workers. Fase mais crítica.
- **Laminagem Infusão** — processo diferente. 24h (moda). 58% com 1 worker. TRATAR SEPARADAMENTE.
- **Desmolde** — ponto QC. 96.4% dos erros detectados aqui.
- **Lixagem água** — 49.2% retrabalho. Quase metade repete.
- **Pintura Acabamento** — 42.4% retrabalho. 40 aptos na skill matrix mas só 22 trabalharam em 2024.

### Constraints de cura/secagem (min_gap_hours)

O decoder DEVE respeitar estes tempos entre fases. Não são filas — são química.

```
Laminagem → Cura:                    15.0h
Pintura Acabam. → Lixagem seco:      12.5h
Colagem Peças → Pintura Acabam.:     19.5h
Colagem Peças → Acabamento 2:        23.5h
Acabamento Enverniz. → Lixagem água: 18.0h
Colagem Barcos → Pintura Acabam.:    19.0h
Colagem Golas → Acabamento 3:        24.5h
Laminagem Infusão → Cura:            24.0h
```

### CoeficienteX — ATENÇÃO

**CoeficienteX é DINHEIRO (prémio/bónus €), NÃO tempo.** Confirmado pelo CEO. O valor 6.1 na Laminagem são €6.10 de prémio, não 6.1 horas.

NUNCA usar CoeficienteX em:
- Cálculos de duração
- Lógica de workforce/pares
- Fitness function tempos

USAR CoeficienteX em:
- src/profit/ — custos, payroll, margem

O critério para pares na Laminagem é: mediana team_size histórico ≥ 2 (dados reais), NÃO CoeficienteX > 0.

### Tempos — NUNCA usar standard

Os coeficientes standard (FasesStandardModelos) divergem até 25× do real. O CPO usa SEMPRE tempos históricos reais (FaseOf_Inicio → FaseOf_Fim), limpos com o pipeline: remover zeros → remover >P95 → moda dos limpos → fallback mediana ≠0.

---

## Bugs P0 — todos fixos antes ou durante Q.1-Q.6 ✅

Estes bugs já estão resolvidos. Se encontrares regressão num deles, **PARA imediatamente** —
os testes Q.* deviam ter apanhado. Não tentes "corrigir de novo".

| ID | Estado | Onde foi fixo |
|---|---|---|
| **D1** Setup counter sempre zero | ✅ FIXED | `decoder.py:47` (setup_family) + `:497` (setups++) + `:860` (`_last_on_machine_has_different_family`) |
| **D2** Sem cura/secagem | ✅ FIXED | `state.py:33` `NELO_CURING_GAPS_SEED` (16 transições) + migration 023 |
| **F1** Sem throughput €/dia | ✅ FIXED | `fitness.py` `w_v2_throughput_eur_day=0.15` + `cpo.py:354` `ProductPricing` import |
| **WG1** Aprovação não executa | ✅ FIXED | `ActionExecutor` + `governance/api.py` `/decisions/{id}/execute` |
| **CO1** Sem rejected_alternatives | ✅ FIXED | `ScheduleCommit.rejected_alternatives` + `user_preference_signal` (migration 022) |
| **C1** Sem routing_choices | ✅ FIXED | `chromosome.py:54` `routing_choices` + `flip_variant` |
| **CX1-3** CoeficienteX | ✅ FIXED | `pair_assignment.py` historical 88.5%; CoeficienteX migrado para `src/profit/services/bonus_payout_service.py` |

## Bugs P1 — todos fixos durante Sprints A-P + Q.1-Q.6 ✅

| ID | Estado |
|---|---|
| **D3** quality_weight não usado | ✅ FIXED — `decoder.py:402` propaga para `workforce.py:810` (`skill_score×qw + availability×(1-qw)`) |
| **D4** Sem backwards scheduling | ✅ FIXED — opt-in via `CPOConfig.use_backwards_scheduling` |
| **D5** Worker selection ignora skill | ✅ FIXED — `workforce.py:23` `skill_penalty=INF` se não está no skill pool |
| **F2** Sem idle operadores | ✅ FIXED — `w_v2_idle_operators=0.15` |
| **F4** quality_risk OFF | ✅ FIXED — `w_v2_quality_risk=0.10` por default |
| **E1** Generations 50 | ✅ FIXED — default agora 200 (`engine.py:54`) |
| **ME1** Eixos MAP-Elites | ✅ FIXED — bins em `default_configs` (lam_utilization, tardiness_transport, idle_pct) |
| **ST1** FactoryState sem cura | ✅ FIXED — `NELO_CURING_GAPS_SEED` |
| **TI1** Trust Index 4 de 7 | ✅ FIXED — Q.1: `src/dqa/trust_v2.py` com 7 componentes; v1 deprecated |
| **WG2** Rollback não funciona | ✅ FIXED — `governance/api.py:445` `rollback_decision` com `reason min_length=10` |

---

## Spelke axioms (invariantes NUNCA violáveis)

Antes de qualquer mudança no scheduler/decoder/fitness, verifica:

1. **Capacidade ≥ 0** — nenhum centro de trabalho pode ter carga negativa
2. **Precedência monotónica** — Cura SEMPRE depois de Laminagem. Desmolde SEMPRE depois de Cura. BOM inviolável.
3. **Molde exclusivo** — molde de 1 poço NUNCA atribuído a 2 barcos ao mesmo tempo
4. **Dual-resource Laminagem** — Laminagem standard SEMPRE 2 operadores (88.5% histórico)
5. **Skill match** — operador só pode ser atribuído a fase se está em FuncionariosFasesAptos
6. **Cura/secagem** — operação seguinte NÃO PODE começar antes do min_gap_hours
7. **Safety net** — CPO NUNCA devolve pior que baseline

Se o teu código viola qualquer um destes, PÁRA e pergunta.

---

## Padrão ConfigStore (zero hardcoded)

NUNCA hardcoded:
```python
# ❌ ERRADO
MIN_WORKERS_PINTURA = 18
FRRMAB_C = 0.2
SURROGATE_THRESHOLD = 1.2

# ✅ CORRECTO
config.get("min_workers_pintura", default=18, editable=True)
config.get("frrmab_c", default=0.2, editable=True)
config.get("surrogate_threshold", default=1.2, editable=True)
```

Cada parâmetro vem da DB com: default, override, quem mudou, quando, porquê.
O utilizador SEMPRE pode mudar qualquer valor na página de configuração.

---

## Padrão de commits (schedule-as-code)

Cada alteração de plano é um ScheduleCommit com:
- `commit_id` (SHA-256), `parent_id`, `author`, `timestamp`
- `delta` — o que mudou
- `kpis` — snapshot de TODOS os KPIs
- `alternatives` — MAP-Elites representativas
- **`rejected_alternatives`** — cenários rejeitados + KPIs + razão (CRÍTICO para aprendizagem)
- **`user_reason`** — porquê o gestor aceitou/rejeitou (campo livre, MAIS VALIOSO)

Se criares ou modificares ScheduleCommit, NUNCA remover `rejected_alternatives` nem `user_reason`.

---

## Convenções de código

- Python 3.11, type hints obrigatórios
- FastAPI para API, Pydantic para schemas
- SQLAlchemy 2.0 para DB, Alembic para migrations
- pytest para testes, Hypothesis para property-based
- Imports relativos dentro do módulo, absolutos entre módulos: `from src.plan.cpo.decoder import decode`
- Docstrings em inglês, Google style
- Comentários em código em inglês
- Nomes de variáveis em inglês, termos de domínio em inglês (phase, mold, worker, boat)
- Mensagens ao utilizador em português (frontend, copilot)
- Linha < 120 caracteres
- Sem `print()` — usar `logging.getLogger(__name__)`
- Sem `import *`
- Sem variáveis globais mutáveis

---

## Testes

- Antes de commit: `pytest tests/` — 527+ testes, TODOS verdes
- Novo código no CPO → adicionar property-based test com Hypothesis
- 4 invariantes property-based do scheduler:
  1. Nunca double-book (centro + operador)
  2. Respeitar capacidade
  3. Respeitar precedências (BOM + routing)
  4. Respeitar calendário + skills
- Coverage mínimo para novos ficheiros: 70%

---

## Módulos linkagem — estado actual (Q.1-Q.6)

✅ **Já ligados (não regredir):**
- `plan ← profit` — `cpo.py:354` importa `ProductPricing`; `transport.py` importa `DashboardMetricsService` (Q.5); fitness usa `throughput_eur_day`
- `plan ← dqa` — `cpo.py:325` importa `TrustIndexV2Calculator` para `_compute_trust_index_for_schedule` (gateia `ScheduleCommit.trust_index`)
- `plan ← workforce` — partilham `Employee` model; `EmployeeExtrasService` usa `ProductionSchedule` para history
- `explain ← plan` — `explain/api.py:723` importa `CommitsService` (lazy)

⏳ **Ainda em aberto (verificar prioridade com Luis antes de tocar):**
- `plan ← hr` (turnos / ausências) — zero imports
- `plan ← supply` (stock matéria-prima) — zero imports
- `sandbox ← plan` — simulação não corre o scheduler real
- `improve` — isolado, módulo dead-code funcional

---

## Hipóteses não confirmadas — CUIDADO

Se o teu código depende de alguma destas, documenta como hipótese:

| Hipótese | Status |
|---|---|
| H1: CoeficienteX = tempo 2º worker | ❌ ERRADO — é prémio € |
| H2: Threshold manutenção = 800 usos | ⚠️ INVENTADO — sem dados |
| H3: Gravidade 1 = warning, 2 = defeito | ⚠️ NÃO CONFIRMADO |
| H4: Laminagem 1 worker = erro registo | ⚠️ NÃO CONFIRMADO |
| H5: Data transporte = por dia | ⚠️ NÃO CONFIRMADO |

---

## Bug alembic conhecido (não introduzido por Q.*, mas afecta deploys novos)

`alembic/versions/026_preference_rule_review_notes.py` lista
`down_revision = '025a_phase_bonus_payout'` mas a revisão real em `025a` é
`'025a_phase_bonus'`. Bloqueia `alembic upgrade head` em DBs novas. Pre-existe
ao Q.1 (commit `52821d6`). Decisão pendente Luis: editar 026 vs migration de
merge 028. **NÃO mexer sem confirmação.**

---

## Quando estás perdido

1. Lê este ficheiro
2. Lê o plano de visão: `PP1_NELO_PLANO_v4.md` (anotado com status Q.1-Q.6 no topo)
3. Lê o plano de execução: `.claude/plans/plano-diz-c-digo-scalable-minsky.md`
4. Vê o que Q.1-Q.6 entregou: `README.md` secção "Sprints Q.1–Q.6"
5. Corre os testes: `pytest tests/ -x` (927 testes; smoke do advisory loop em `tests/plan/test_sprint_q_e2e_smoke.py`)
6. Se o problema é no CPO: `src/plan/cpo/engine.py` (entry point) ou `src/plan/services/preview_delta_service.py` (Q.4 what-if sub-segundo)
7. Se o problema é no Despacho: `src/plan/api/transport.py` + `src/plan/services/transport_suggestions.py`
8. Se o problema é no CEO Dashboard: `src/profit/services/dashboard_metrics_service.py`
9. Se o problema é em Colaboradores: `src/workforce/employee_extras_service.py`
10. Se o problema é no Copilot: `src/copilot/service.py`
11. Se não tens a certeza de NADA: pergunta ao Luís antes de implementar

---

*Estas guidelines funcionam se: os diffs têm menos mudanças desnecessárias, há menos reescrituras por over-engineering, e as perguntas de clarificação vêm ANTES da implementação e não depois dos erros.*
