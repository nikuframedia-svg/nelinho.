# ProdPlan ONE

Sistema completo de gestão e planeamento de produção industrial, desenvolvido para a NELO. Inclui dashboards OEE (Overall Equipment Effectiveness), análise de qualidade, gestão de ordens de produção, alocações de funcionários e muito mais.

## 📦 Sprints Q.1–Q.6 — Plano de Implementação NELO v4

Os 6 sprints abaixo fecham os gaps materiais entre o `PP1_NELO_PLANO_v4.md` e o
HEAD. Plano vivo em [.claude/plans/plano-diz-c-digo-scalable-minsky.md](.claude/plans/plano-diz-c-digo-scalable-minsky.md).
Smoke E2E em [tests/plan/test_sprint_q_e2e_smoke.py](tests/plan/test_sprint_q_e2e_smoke.py).

| Sprint | Entrega | Verificação |
|---|---|---|
| **Q.1** Trust v1→v2 + tooling | `quality_gates.py` migrado para `gate_allows(AUTO_COMMIT)`; `context_builder._calculate_trust_index` agora consome `TrustIndexV2Calculator(scope=factory)` com legacy keys; `trust_index.py` deprecated; frontend ganha `@dnd-kit/core`, `papaparse`, `xlsx` + `dqaApi`/`configApi`/`transportApi` clients; `DQAPage` mostra 7 componentes + 5 gates v2.0. | 213 testes copilot + 164 dqa/plan/governance — 0 regressões |
| **Q.2** Despacho/Expedição (DE01-08) | 7 endpoints REST `src/plan/api/transport.py` (list/create/assign/remove/freeze/dispatch/suggestions); `TransportSuggestionsService` com 5 detectores (advance_boat, delay_boat, swap_between_batches, complete_truck, regroup_by_client) — cada sugestão com `O QUE/PORQUÊ/SE ACEITAR/SE REJEITAR/ALTERNATIVA`; novo `RejectionCategory` enum + migration 027 + validação no endpoint approve_decision; nova `DispatchPage.tsx` com 3-rail layout + `@dnd-kit` drag-drop entre batches + `RejectionDialog` com categoria obrigatória; tab Transporte no Settings. | 633 testes — 0 regressões |
| **Q.3** Colaboradores GC01-GC10 | `EmployeeExtrasService` com `quality_score` (Laplace smoothed), `skill_matrix` (curated + history), `history` (paginated newest-first); 6 endpoints novos sob `/v1/workforce/employees/{id}/...` (quality-score GET/PATCH, skill-matrix GET/PATCH, history GET, soft-delete POST); override de quality_score grava `PreferenceRule(type=WORKFORCE_OVERRIDE)` para Camada 1; `EmployeesPage` ganha tier picker, custo €/h, 3 modais (History, Quality slider+reason, Compare side-by-side com `useQueries`), CSV export via papaparse, soft delete; tab Workforce no Settings. | 633 testes + EmployeeUpdate schema fix (notes field) descoberto e corrigido durante smoke |
| **Q.4** Drag-drop Planeamento | `PreviewDeltaService` (sub-segundo, NUNCA corre GA/CP-SAT) — load latest commit, mutate em memória, recompute fitness, run conflict checks; 2 endpoints `POST /v1/plan/schedule/preview-delta` + `/apply-move` (reason ≥10 chars obrigatório); novo componente `DragDropPlanner` com Layer 1 (colunas por fase) + Layer 2 (swimlanes operador) + painel direito de sugestão com fitness antes/depois e badges de conflito/aviso; tab Drag&drop na SchedulingPage; tab Scheduling no Settings com 9 chaves (6 pesos fitness v2 + budgets + queue). | 912 testes — 0 regressões |
| **Q.5** Timeline + CEO Dashboard | Spike confirmou `CuratedOrder.data_entrega_prevista` + `data_conclusao` existem → OTD% real; `DashboardMetricsService` com OTD%, backlog_by_client, expeditions_next_n_days, first_pass_yield; 5 endpoints novos (`/v1/profit/otd`, `/backlog-by-client`, `/dashboard/active-alerts`, `/v1/quality/first-pass-yield`, `/v1/plan/transport/expeditions/next-n-days`); CEODashboardPage ganha 4 tiles secundários + backlog table + alerts feed + tabela expedições com risk badges; `cpoCommitsApi.decide` e endpoint backend exigem `rejection_category` quando rejected_alt_idxs não vazio (validação 400 com mensagem clara para BANANA / categoria em falta). | 912 testes — 0 regressões |
| **Q.6** Polish + Settings completo | 2 endpoints conveniência (`GET /v1/config/categories`, `POST /v1/config/{cat}/{key}/reset-to-default`) + 6 tabs Settings novas (Cura/Secagem, Moldes, Qualidade, TrustIndex, Sistema, Aprendizagem) via `<ConfigKeysPanel>` genérico com botão reset por linha; LearningSettingsPanel descreve estado das 4 Camadas; novo E2E smoke `tests/plan/test_sprint_q_e2e_smoke.py` (15 testes) que valida o advisory loop ponta-a-ponta. | 927 testes (912 + 15 E2E) — 0 regressões |

### Princípios respeitados (Plan v4 §11)

- ✅ **"Explica sempre"** — toda a sugestão tem O QUE/PORQUÊ/SE ACEITAR/SE REJEITAR/ALTERNATIVA
- ✅ **"Porquê obrigatório em rejeições"** — categoria mandatória + texto livre opcional em 3 surfaces (governance, cpo decide, dispatch suggestions)
- ✅ **"Tudo editável via ConfigStore"** — 96 chaves seeded em 13 categorias; cada override grava audit (quem/quando/valor anterior); reset-to-default no UI
- ✅ **"Advisory mode"** — preview-delta NÃO escreve; apply-move e decide criam ScheduleCommit filhos com delta + reason
- ✅ **Camadas de aprendizagem** — Camada 1 (preference_rule + WORKFORCE_OVERRIDE + categoria rejeição) + Camada 2 (adaptive_weights na FitnessConfig.from_tenant_config); Camada 3 DPO + Camada 4 ABLkit já existem

### Pendente para Luis na máquina dev

1. `cd frontend && npm install` (instala `@dnd-kit/core`, `papaparse`, `xlsx`).
2. `npm run build` (confirma 0 erros TypeScript em todas as páginas estendidas).
3. `alembic upgrade head` aplica migration 027.
4. Browser smoke das 6 surfaces: `/plan/dispatch`, `/plan/scheduling` (tab Drag&drop), `/core/employees`, `/admin/settings/*`, `/ceo`, `/plan/timeline`.

### Bug pré-existente identificado (não introduzido pelos sprints Q.*)

`alembic/versions/026_preference_rule_review_notes.py` lista `down_revision = '025a_phase_bonus_payout'` mas a revisão real em `025a` é `025a_phase_bonus`. Bloqueia `alembic upgrade head` em DBs novas. Não corrigido automaticamente — requer decisão de Luis (editar 026 vs criar migration de merge).

---


## 🚀 Características Principais

- **OEE Dashboard**: Análise completa de eficiência de equipamentos (Disponibilidade, Desempenho, Qualidade)
- **Gestão de Ordens**: Sistema completo de ordens de produção com paginação e filtros avançados
- **Análise de Qualidade**: Tracking de erros, FPY (First Pass Yield), análise de defeitos
- **Alocações de Funcionários**: Gestão de recursos humanos e alocações por fase
- **Dashboard Executivo**: Visão geral de KPIs e métricas críticas
- **UI Moderna**: Interface redesenhada com foco em clareza, contraste e usabilidade

## 📋 Tecnologias

### Backend
- **FastAPI** 0.109.0 - Framework web assíncrono
- **SQLite** - Base de dados (desenvolvimento)
- **Pandas** - Processamento de dados Excel
- **Uvicorn** - Servidor ASGI

### Frontend
- **React** 19.2.0 - Biblioteca UI
- **TypeScript** 5.9.3 - Type safety
- **Vite** 7.2.4 - Build tool
- **Tailwind CSS** 4.1.18 - Styling
- **Recharts** 3.6.0 - Gráficos
- **React Router** 7.12.0 - Navegação
- **TanStack Query** 5.90.16 - Data fetching

## 📁 Estrutura do Projeto

```
prodplan-one/
├── backend/              # FastAPI backend (SQLite)
│   ├── main.py          # API principal
│   ├── database.py      # Gestão de base de dados
│   └── requirements.txt  # Dependências Python
├── frontend/            # React frontend
│   ├── src/
│   │   ├── pages/       # Páginas da aplicação
│   │   ├── components/  # Componentes reutilizáveis
│   │   ├── lib/         # Utilitários e API client
│   │   └── data/        # Dados JSON processados
│   └── package.json
├── src/                 # Backend modular (estrutura completa)
│   ├── core/           # Módulo CORE
│   ├── plan/           # Módulo PLAN
│   ├── profit/         # Módulo PROFIT
│   ├── hr/             # Módulo HR
│   └── shared/         # Código partilhado
├── scripts/            # Scripts utilitários
│   ├── convert_excel_to_json.py  # Conversão Excel → JSON
│   └── init-db.sql     # Inicialização PostgreSQL (Docker)
├── alembic/            # Migrations de base de dados
├── docker-compose.yml  # Setup Docker completo
├── Dockerfile          # Container backend
└── Folha_IA.xlsx       # Dados fonte (Excel)
```

## 🛠️ Instalação

### Pré-requisitos

- **Python** 3.11+
- **Node.js** 18+
- **npm** ou **yarn**

### Backend

1. **Instalar dependências**:
```bash
cd backend
pip install -r requirements.txt
```

2. **Configurar variáveis de ambiente** (criar `.env` a partir de `.env.example`):
```bash
cp .env.example .env
# Editar .env com as configurações necessárias
```

3. **Inicializar base de dados**:
A base de dados SQLite será criada automaticamente na primeira execução, importando dados do `Folha_IA.xlsx`.

4. **Executar servidor**:
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

O backend estará disponível em `http://localhost:8000`

### Frontend

1. **Instalar dependências**:
```bash
cd frontend
npm install
```

2. **Configurar variáveis de ambiente**:
Criar `frontend/.env.local`:
```env
VITE_API_URL=http://localhost:8000
```

3. **Executar servidor de desenvolvimento**:
```bash
npm run dev
```

O frontend estará disponível em `http://localhost:5173`

## 🐳 Docker (Opcional)

Para executar com Docker Compose (inclui PostgreSQL, Redis, Kafka):

```bash
docker-compose up -d
```

O backend estará disponível em `http://localhost:8000`

## 📡 API Endpoints

### Orders (Ordens de Produção)
- `GET /api/orders` - Lista paginada de ordens
- `GET /api/orders/stats` - Estatísticas agregadas
- `GET /api/orders/{order_id}` - Detalhes de uma ordem

**Parâmetros de query**:
- `page` (int): Número da página
- `pageSize` (int): Itens por página (máx 100)
- `status` (string): `ALL`, `IN_PROGRESS`, `COMPLETED`
- `search` (string): Pesquisa em nome, ID ou fase
- `productType` (string): `K1`, `K2`, `K4`, `C1`, `C2`, `C4`, `Other`
- `sortBy` (string): Campo de ordenação
- `sortOrder` (string): `asc` ou `desc`

### Errors (Erros de Qualidade)
- `GET /api/errors` - Lista paginada de erros
- `GET /api/errors/stats` - Estatísticas de erros

**Parâmetros de query**:
- `page`, `pageSize`
- `severity` (int): `1` (Minor), `2` (Major), `3` (Critical)
- `phase` (string): Filtro por fase
- `search` (string): Pesquisa em descrição ou ID

### Allocations (Alocações de Funcionários)
- `GET /api/allocations` - Lista paginada de alocações
- `GET /api/allocations/stats` - Estatísticas de alocações

**Parâmetros de query**:
- `page`, `pageSize`
- `employeeId` (string): Filtro por funcionário
- `phaseId` (string): Filtro por fase
- `search` (string): Pesquisa em nome, fase ou ordem

## 📊 Dados

O sistema utiliza dados do ficheiro `Folha_IA.xlsx` que contém:

- **OrdensFabrico**: 27,380 ordens de produção
- **FasesOrdemFabrico**: 519,079 execuções de fases
- **OrdemFabricoErros**: 89,836 erros registados
- **FuncionariosFaseOrdemFabrico**: 346,832 alocações
- **Modelos**: 894 produtos/kayaks
- **Fases**: 71 fases de produção
- **Funcionarios**: 137 funcionários ativos

Os dados são processados pelo script `scripts/convert_excel_to_json.py` e importados para SQLite na primeira execução.

## 🎨 UI/UX

A interface foi redesenhada com foco em:
- **Contraste elevado**: Texto legível, hierarquia clara
- **Design moderno**: Cards premium, sombras suaves, animações subtis
- **Responsividade**: Funciona em diferentes resoluções
- **Acessibilidade**: Suporte a `prefers-reduced-motion`, contraste WCAG AA

## 📝 Documentação Adicional

- `DATA_REQUIREMENTS.md`: Requisitos de dados e funcionalidades em falta
- `frontend/README.md`: Documentação específica do frontend

## 🔧 Desenvolvimento

### Scripts Disponíveis

**Backend**:
```bash
# Executar servidor com reload
python -m uvicorn backend.main:app --reload

# Converter Excel para JSON
python scripts/convert_excel_to_json.py
```

**Frontend**:
```bash
# Desenvolvimento
npm run dev

# Build de produção
npm run build

# Preview de produção
npm run preview

# Lint
npm run lint
```

## 🚨 Troubleshooting

### Backend não inicia
- Verificar se `Folha_IA.xlsx` está na raiz do projeto
- Verificar permissões de escrita para criar `backend/prodplan.db`
- Verificar se todas as dependências estão instaladas

### Frontend não conecta ao backend
- Verificar se `VITE_API_URL` está correto em `.env.local`
- Verificar se o backend está a correr na porta 8000
- Verificar CORS no backend (já configurado para localhost:5173)

### Dados não aparecem
- Verificar se a base de dados foi inicializada (primeira execução)
- Verificar se `Folha_IA.xlsx` está presente
- Verificar logs do backend para erros de importação

## 📄 Licença

Este projeto é propriedade da NELO.

## 👥 Contribuidores

Desenvolvido para NELO - Sistema de Gestão de Produção Industrial

---

**Versão**: 2.0.0  
**Última atualização**: Janeiro 2026










