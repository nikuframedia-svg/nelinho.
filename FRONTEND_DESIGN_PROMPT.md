# FRONTEND PP1-NELO — PROMPT DE DESIGN

## Para: Claude Code (implementação frontend)
## Stack: React 19 + Vite + TypeScript + shadcn/ui + Tailwind v4 + TanStack Query v5

---

# 1. O QUE É ESTE SOFTWARE

O PP1 é o sistema de scheduling e IA de produção da NELO — a maior fabricante mundial de kayaks de competição, em Vila do Conde, Portugal. Produzem ~14.7 barcos artesanais por dia com 122 operadores, 41 fases de produção, 510 moldes. Meta: €30.000-35.000/dia de valor de produção.

O frontend corre num browser normal (Chrome/Firefox) acedido por vários PCs e tablets da fábrica na rede local. A torre (servidor) hospeda tudo — os PCs não instalam nada.

```
TORRE (servidor) → Caddy → React build (estático) + FastAPI (API)
  ↕ rede local
PC gestor | PC produção | PC CEO | Tablet operador (chão fábrica)
```

---

# 2. REGRAS DE DESIGN ABSOLUTAS

## 2.1 Filosofia

```
REGRA 1: O software EXPLICA SEMPRE. Cada acção mostra consequências ANTES de executar.
REGRA 2: O utilizador pode SEMPRE dizer sim ou não. E pode SEMPRE dizer PORQUÊ.
REGRA 3: TUDO é editável. O sistema NUNCA bloqueia uma edição humana.
REGRA 4: Advisory mode — NUNCA executa sem aprovação. Propõe, explica, o humano decide.
REGRA 5: O "porquê" do utilizador alimenta o sistema de aprendizagem. Cada rejeição com razão é o data point mais valioso do sistema.
```

## 2.2 Chão de fábrica — constraints físicos

```
- Touch targets: MÍNIMO 56×56px (operadores usam luvas)
- Font body: MÍNIMO 18px em tablets, 16px em desktop
- Contraste: WCAG AAA (7:1) — pó, ecrãs com proteção polycarbonato, luz forte
- NUNCA cor sozinha para transmitir informação — ícone + label sempre (8% daltónicos)
- Dark mode DEFAULT (menos reflexo em nave industrial). Light mode disponível.
- Confirmação de acções destrutivas: timeout 5s antes de permitir confirmar
- Tablet operador: botões fullscreen, zero navegação, zero menus
```

## 2.3 Língua

```
- Português de Portugal (NUNCA brasileiro)
- "barcos" não "embarcações" ou "unidades"
- "operador" ou nome próprio ("Paulo Gomes"), NUNCA "recurso" ou "colaborador"
- "molde" não "tooling" ou "ferramenta"
- "retrabalho" não "rework"
- "fase" não "estação" ou "work center"
- Números CONCRETOS: "€2.400" não "valor significativo"
- Tempos CONCRETOS: "4 horas" não "algum tempo"
- Datas CONCRETAS: "terça às 14h" não "nos próximos dias"
- Zero jargão técnico sem explicação
```

## 2.4 Anti-patterns (NUNCA fazer)

```
- NUNCA mais de 8 páginas na navegação principal
- NUNCA gráficos sem acção associada (cada gráfico responde a uma pergunta concreta)
- NUNCA dashboards separados para OEE/WIP/lead time — integrar nas páginas onde fazem sentido
- NUNCA menus com 3+ níveis (barra lateral → página, ponto)
- NUNCA textos longos na UI — se precisa explicar, usa o Copilot (chat)
- NUNCA mostrar só percentagens sem contexto ("72%" não diz nada, "72% — faltam 3 operadores, 5 barcos em risco" diz tudo)
- NUNCA configuração espalhada por múltiplas páginas — TUDO na página Configuração
- NUNCA número sem unidade (€, h, barcos, operadores)
- NUNCA tabela com mais de 8 colunas visíveis (scroll horizontal é proibido)
- NUNCA formulário com mais de 6 campos visíveis (usar steps ou accordion)
```

---

# 3. ARQUITECTURA FRONTEND

## 3.1 Stack

```
React 19 + Vite + TypeScript strict
shadcn/ui + Radix primitives — componentes base
Tailwind v4 — styling (utility-first)
TanStack Query v5 — server state (cache, refetch, mutations)
TanStack Table — tabelas com sort, filter, pagination
TanStack Virtual — virtualização para listas grandes
Zustand + Immer — client state (mínimo, quase tudo é server state)
React Hook Form + Zod — formulários + validação (schemas partilhados via OpenAPI)
Recharts — gráficos simples
Custom SVG — Gantt chart (não usar bibliotecas pesadas)
WebSocket primary / SSE fallback / polling last resort — real-time
react-i18next — i18n (pt-PT, en, de-AT)
openapi-typescript — tipos gerados do backend
Dexie.js + Service Worker (Workbox) — PWA offline para tablet operador
```

## 3.2 Estrutura de ficheiros

```
frontend/src/
├── pages/                    # 8 páginas, uma pasta por página
│   ├── painel/               # Homepage — KPIs + alertas + timeline + chat
│   │   └── PainelPage.tsx
│   ├── producao/             # Mapa da fábrica — barcos por fase
│   │   └── ProducaoPage.tsx
│   ├── planeamento/          # Gantt + atribuição barcos/pessoas
│   │   └── PlaneamentoPage.tsx
│   ├── expedicao/            # Despacho — expedições + sugestões
│   │   └── ExpedicaoPage.tsx
│   ├── equipa/               # CRUD colaboradores
│   │   └── EquipaPage.tsx
│   ├── qualidade/            # Erros + moldes + diagnóstico
│   │   └── QualidadePage.tsx
│   ├── configuracao/         # TUDO configurável — separadores
│   │   └── ConfiguracaoPage.tsx
│   ├── relatorios/           # Gerar relatórios PDF/Excel
│   │   └── RelatoriosPage.tsx
│   └── operador/             # Tablet chão fábrica (fullscreen, sem nav)
│       └── OperadorPage.tsx
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx       # 8 ícones, nada mais
│   │   ├── TopBar.tsx        # Nome do utilizador + role + logout
│   │   └── CopilotPanel.tsx  # Chat lateral (sempre visível em desktop)
│   ├── shared/
│   │   ├── ConsequenceBox.tsx     # "Se aceitar: X. Se rejeitar: Y"
│   │   ├── ApprovalButtons.tsx    # [Aceitar] [Rejeitar] [Porquê?]
│   │   ├── KPICard.tsx            # Número grande + tendência + cor
│   │   ├── AlertCard.tsx          # Frase + acção + botões
│   │   ├── BoatCard.tsx           # Cartão de barco (modelo, cliente, prazo, cor)
│   │   ├── WorkerAvatar.tsx       # Foto/iniciais + score + tier badge
│   │   ├── PhaseColumn.tsx        # Coluna de fase no mapa
│   │   ├── StatusBadge.tsx        # Verde/amarelo/vermelho/azul
│   │   ├── TimelineSuggestion.tsx # Sugestão na timeline com 5-box
│   │   ├── CausalChainCard.tsx    # 5 caixas: pergunta, causa, mecanismo, evidência, recomendação
│   │   ├── GanttChart.tsx         # SVG custom
│   │   ├── GanttBar.tsx           # Barra individual no Gantt
│   │   └── ConfigParam.tsx        # Parâmetro editável com audit trail
│   └── operador/
│       ├── TaskFullscreen.tsx     # Tarefa actual em fullscreen
│       └── BigButton.tsx          # Botão 100×100px para luvas
├── lib/
│   ├── api.ts                # Typed API client (gerado de OpenAPI)
│   ├── realtime.ts           # WebSocket + SSE + fallback
│   ├── auth.ts               # Login + RBAC + role guard
│   ├── i18n.ts               # pt-PT default
│   └── utils.ts              # Formatação €, datas, durações
├── hooks/
│   ├── useOrders.ts          # TanStack Query para ordens
│   ├── useWorkers.ts         # TanStack Query para operadores
│   ├── useMolds.ts           # TanStack Query para moldes
│   ├── useKPIs.ts            # TanStack Query + WebSocket para KPIs
│   ├── useCPO.ts             # Mutação para simular cenários
│   ├── useSuggestions.ts     # Timeline de sugestões pendentes
│   └── useCopilot.ts         # Chat com LLM
└── types/
    └── index.ts              # Gerado de OpenAPI — NÃO editar manualmente
```

## 3.3 RBAC — Quem vê o quê

```
GESTOR DE PRODUÇÃO (role: manager_operations)
  → Vê: TODAS as 8 páginas
  → Pode: Aprovar, rejeitar, editar TUDO, configurar

CEO (role: finance_controller)
  → Vê: Painel (simplificado), Expedição, Relatórios
  → Pode: Ver KPIs, ver expedições, gerar relatórios
  → NÃO vê: Planeamento detalhado, Equipa detalhada, Configuração

OPERADOR (role: operator)
  → Vê: APENAS OperadorPage (fullscreen, sem barra lateral)
  → Pode: Marcar início/fim tarefa, reportar problema
  → NÃO vê: Mais nada

ADMIN (role: admin_platform)
  → Vê: Tudo + Configuração avançada (RBAC, sistema)
```

---

# 4. AS 8 PÁGINAS — ESPECIFICAÇÃO DETALHADA

## 4.1 PAINEL (homepage)

### Layout

```
┌──────────────────────────────────────────────────────────┬──────────────┐
│                        TOP BAR                           │              │
├────────┬─────────────────────────────────────────────────┤              │
│        │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │   COPILOT    │
│        │  │€33.2K│ │ 12   │ │  3   │ │  2   │          │    CHAT      │
│ SIDE   │  │/dia  │ │concl.│ │risco │ │alert │          │              │
│ BAR    │  └──────┘ └──────┘ └──────┘ └──────┘          │  [input___]  │
│        │                                                 │              │
│ 8 ícon │  ┌─ ALERTAS ────────────────────────────────┐  │  Mensagens   │
│        │  │ 🔴 Molde K1 7ML — taxa erro 23%          │  │  do chat     │
│        │  │    [Ver] [Propor manutenção]              │  │  com o LLM   │
│        │  │ 🟡 Expedição sexta — 2 barcos em risco    │  │              │
│        │  │    [Ver detalhe]                          │  │              │
│        │  └──────────────────────────────────────────┘  │              │
│        │                                                 │              │
│        │  ┌─ TIMELINE DE APROVAÇÃO ──────────────────┐  │              │
│        │  │ Sugestão #847 — ALTA                      │  │              │
│        │  │ "Mover 3 K2 de terça para quarta"        │  │              │
│        │  │ Porquê: molde em manutenção               │  │              │
│        │  │ Se aceitar: +1 dia, sem impacto expedição │  │              │
│        │  │ Se rejeitar: 3 barcos parados 8h          │  │              │
│        │  │ [Aceitar] [Rejeitar] [Porquê?]           │  │              │
│        │  │                                           │  │              │
│        │  │ Sugestão #846 — MÉDIA                     │  │              │
│        │  │ ...                                       │  │              │
│        │  └──────────────────────────────────────────┘  │              │
└────────┴─────────────────────────────────────────────────┴──────────────┘
```

### KPI Cards (topo)

4 cartões grandes:

```typescript
// Throughput
<KPICard
  label="Throughput hoje"
  value={33200}
  unit="€"
  target={30000}
  trend={+2.1}           // vs ontem em %
  status="green"          // green: ≥30K, yellow: 25-30K, red: <25K
  onClick={() => navigate('/producao')}
/>

// Barcos concluídos
<KPICard
  label="Concluídos hoje"
  value={12}
  unit="barcos"
  target={14.7}
  trend={-1.2}
  status="yellow"
  onClick={() => navigate('/producao?filter=completed')}
/>

// Barcos em risco
<KPICard
  label="Em risco"
  value={3}
  unit="barcos"
  description="expedição sexta"   // contexto!
  status={3 > 2 ? "red" : "green"}
  onClick={() => navigate('/expedicao?filter=risk')}
/>

// Alertas
<KPICard
  label="Alertas"
  value={2}
  unit="activos"
  status={2 > 0 ? "yellow" : "green"}
/>
```

### AlertCard

```typescript
interface AlertCardProps {
  severity: "critical" | "high" | "medium" | "low";
  title: string;           // "Molde K1 7 ML (03) — taxa erro a subir"
  detail: string;           // "23% esta semana vs 12% normal"
  cause?: string;           // "847 usos desde manutenção" (do ERRO-TREE)
  actions: {
    label: string;          // "Propor manutenção"
    onClick: () => void;
    variant: "primary" | "secondary";
  }[];
  timestamp: Date;
  source: "auto" | "manual"; // auto = sistema detectou, manual = humano criou
}
```

### TimelineSuggestion

O componente mais importante de toda a aplicação:

```typescript
interface TimelineSuggestionProps {
  id: number;
  priority: "critical" | "high" | "medium" | "low";
  title: string;              // "Mover 3 K2 de terça para quarta"
  what_changed: string;       // Delta — o que muda vs actual
  why: string;                // "Molde K2 7L em manutenção terça"
  if_accept: string;          // "Barcos atrasam 1 dia. Expedição sexta OK."
  if_reject: string;          // "3 barcos parados 8h. 2 operadores idle."
  alternatives?: {
    label: string;
    description: string;
    kpis: KPISnapshot;
  }[];
  onAccept: (reason?: string) => void;
  onReject: (reason?: string) => void;
  onModify: () => void;       // editar sugestão antes de aprovar
}
```

Renderiza:

```
┌─ Sugestão #847 ─────────────────────── ALTA ─┐
│                                               │
│ Mover 3 barcos K2 de terça para quarta       │
│                                               │
│ PORQUÊ: Molde K2 7L em manutenção terça.     │
│ Sem molde, 3 barcos ficam parados.            │
│                                               │
│ SE ACEITAR:                                   │
│ → Barcos atrasam 1 dia (entregues quarta)    │
│ → Expedição sexta sem impacto (margem 2 dias)│
│ → Throughput terça: -€7K, quarta: +€7K      │
│                                               │
│ SE REJEITAR:                                  │
│ → 3 barcos parados terça (sem molde)         │
│ → 2 laminadores idle 8h (custo ~€240)        │
│ → Barcos acabam quarta na mesma              │
│                                               │
│ ALTERNATIVA: Usar molde K2 7L (01) — 2 poços │
│ em vez de 4. +2h, sem atraso. [Ver detalhes] │
│                                               │
│ [✓ Aceitar]  [✗ Rejeitar]  [✎ Modificar]    │
│                                               │
│ Porquê esta decisão? (opcional)              │
│ [________________________________]            │
│                                               │
└───────────────────────────────────────────────┘
```

O campo "Porquê esta decisão?" é SEMPRE visível (não escondido). O texto é gravado no `ScheduleCommit.user_reason`. É o data point mais valioso do sistema.

### Copilot Panel

Chat lateral, SEMPRE visível em desktop (colapsável em mobile/tablet):

```typescript
interface CopilotPanelProps {
  // Mensagens do chat
  messages: {
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
    sources?: string[];       // de onde veio a informação
    confidence?: number;      // 0-1
    causal_chain?: CausalChain; // se resposta é diagnóstico
  }[];
  onSend: (message: string) => void;
  isLoading: boolean;
}
```

Input com placeholder: "Pergunte algo sobre a produção..." e sugestões rápidas:
```
"Quantos barcos na Laminagem?"
"Porque caiu o throughput?"
"E se tirar 2 pintores amanhã?"
```

---

## 4.2 PRODUÇÃO (mapa da fábrica)

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ [Filtros: Cliente ▾ | Modelo ▾ | Urgência ▾ | Operador ▾]     │
├──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬────────┤
│Prep. │Paint │LAMIN │ Cura │Desm. │Corte │Colag │Paint │ Lixa-  │
│Molde │gelc. │AGEM  │      │      │      │Peças │Acab. │ gens   │
│      │      │      │      │      │      │      │      │        │
│ 3🟢  │ 5🟡  │14🟡  │ 8⏳  │ 4🔴  │ 6🟢  │ 9🟢  │11🟡  │ 22🔴   │
│      │      │      │      │      │      │      │      │        │
│┌────┐│┌────┐│┌────┐│┌────┐│┌────┐│┌────┐│┌────┐│┌────┐│┌────┐ │
││K1  ││││K2  ││││K1  ││││K4  ││││K1  ││││K2  ││││K1  ││││K4  ││││K2  ││ │
││Fed.││││Pri.││││Fed.││││Clu.││││Fed.││││Pri.││││Swe.││││Clu.││││Nor.││ │
││FR 🟢│││DE 🟡│││PT 🟡│││PT ⏳│││FR 🔴│││DE 🟢│││SE 🟢│││PT 🟡│││NO 🔴│ │
│└────┘│└────┘│└────┘│└────┘│└────┘│└────┘│└────┘│└────┘│└────┘ │
│      │      │┌────┐│      │      │      │      │      │        │
│      │      ││K2  ││      │      │      │      │      │        │
│      │      ││Fed.││      │      │      │      │      │        │
│      │      ││IT 🟢││      │      │      │      │      │        │
│      │      │└────┘│      │      │      │      │      │        │
├──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴────────┤
│ Montag │ CQ Mont │ CQ Final │ Armazém │ Embalado │ Entregue   │
│  5🟢   │   3🟢   │   2🟢    │  12🟢   │   8🟢    │   4🟢      │
└────────────────────────────────────────────────────────────────┘
```

### BoatCard

```typescript
interface BoatCardProps {
  order_id: number;
  model: string;                // "K1 Vanquish L SCS"
  model_short: string;          // "K1"
  client: string;               // "Federação Francesa"
  client_code: string;          // "FR"
  phase: string;                // "Laminagem"
  status: "on_time" | "at_risk" | "late" | "curing" | "completed";
  days_in_phase: number;
  transport_date?: Date;
  workers?: string[];           // ["Paulo Gomes", "Maria Silva"]
  mold?: string;                // "K1 7 ML (03)"
  quality_risk?: number;        // 0-1
  onClick: () => void;          // abre detalhe
  draggable: boolean;
}
```

Cores:
- 🟢 Verde: no prazo
- 🟡 Amarelo: em risco (< 3 dias de margem)
- 🔴 Vermelho: atrasado (passou data ou fase muito lenta)
- ⏳ Cinza: em cura/secagem (não é atraso — é processo)
- 🔵 Azul: concluído / pronto para expedição

Clicar num BoatCard abre modal com detalhe completo:

```
┌─ K1 Vanquish L SCS #4271 ─────────────────────────────┐
│                                                         │
│ Cliente: Federação Francesa                            │
│ Expedição: Sexta, 16 Maio 2026                         │
│ Routing: Padrão #1 (18 fases) — routing A              │
│ Fase actual: Laminagem (há 2.5h)                       │
│ Operadores: Paulo Gomes + Maria Silva                   │
│ Molde: K1 7 ML (02) — 340 usos                        │
│ Risco qualidade: 8% (baixo)                            │
│                                                         │
│ HISTÓRICO DE FASES:                                    │
│ ✅ Prep. Molde    0.5h  João Costa        08:00-08:30  │
│ ✅ Pintura gelc.  1.0h  Ana Reis          08:45-09:45  │
│ 🔄 Laminagem     2.5h  Paulo + Maria     10:00-...    │
│ ⬜ Cura          (est. 15h)                            │
│ ⬜ Desmolde      (est. 0.5h)                           │
│ ⬜ ... (12 fases restantes)                            │
│                                                         │
│ ERROS NESTE BARCO: 0                                   │
│                                                         │
│ [Reagendar]  [Mudar operador]  [Mudar routing A→B]    │
└─────────────────────────────────────────────────────────┘
```

### PhaseColumn

```typescript
interface PhaseColumnProps {
  phase_id: number;
  phase_name: string;
  boats: BoatCardProps[];
  capacity: number;           // max barcos simultâneos
  current_load: number;       // barcos actuais
  workers_allocated: number;
  workers_available: number;
  is_bottleneck: boolean;     // load > 80% capacity
  curing_hours?: number;      // se fase tem cura obrigatória
  rework_rate?: number;       // taxa retrabalho (49.2% Lixagem água)
  onDropBoat: (boat_id: number) => void; // drag-and-drop
}
```

Cabeçalho da coluna:
```
┌────────────────────────┐
│ LAMINAGEM        14 🟡 │  ← nome + contagem + cor
│ 14/16 carga  │ 8/10 op │  ← carga/capacidade | operadores
│ ████████████░░ 87%     │  ← barra de utilização
│ Retrabalho: 15%        │  ← se >20% fica amarelo
└────────────────────────┘
```

---

## 4.3 PLANEAMENTO (Gantt + atribuição)

### Duas vistas (toggle)

**Vista Gantt:**

```
                  Seg 12    Ter 13    Qua 14    Qui 15    Sex 16
                  08 12 16  08 12 16  08 12 16  08 12 16  08 12 16
K1 #4271 FR  Lam ████████
             Cura          ░░░░░░░░░░░░░░░░    (15h, cinza = cura)
             Desm                     ██
             Corte                      ███
K2 #5103 DE  Lam   ████████
             Cura            ░░░░░░░░░░░░░░░░
             ...
K1 #4272 PT  Prep ██
             Pint   ███
             Lam      ████████
             ...

Legenda: ████ = trabalho  ░░░░ = cura/secagem  ┊┊┊┊ = espera (fila)
         🟢 no prazo  🟡 em risco  🔴 atrasado
```

Barras arrastáveis (com constraints: não pode violar precedências nem cura). Quando arrasta, ghost preview + ConsequenceBox:

```
"Se mover K1 #4271 Laminagem para quarta:
→ Cura acaba sexta às 10h (em vez de quinta às 2h)
→ Expedição de sexta: RISCO (margem reduz de 2 dias para 4h)
→ Operadores Paulo+Maria ficam livres terça (podem fazer K2 #5103)
Continuar?"
```

**Vista Atribuição (tabela):**

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PLANO DE AMANHÃ — Terça, 13 Maio 2026                                 │
├─────────────┬───────────┬──────────┬──────────────────┬───────┬────────┤
│ Barco       │ Fase      │ Molde    │ Operador(es)     │ Início│ Estado │
├─────────────┼───────────┼──────────┼──────────────────┼───────┼────────┤
│ K1 #4271 FR │ Laminagem │ K1 7ML02 │ Paulo G. + Maria │ 08:00 │ 🟢    │
│             │           │          │ [Trocar ▾]       │       │        │
│ K2 #5103 DE │ Colagem P.│ —        │ João Costa       │ 08:30 │ 🟢    │
│             │           │          │ [Trocar ▾]       │       │        │
│ K1 #4272 PT │ Pintura AC│ —        │ Ana Reis         │ 09:00 │ 🟡    │
│             │           │          │ [Trocar ▾]       │       │ risco  │
│ ...         │           │          │                  │       │        │
├─────────────┴───────────┴──────────┴──────────────────┴───────┴────────┤
│ SUGESTÃO CPO: Trocar Ana Reis por Carlos (score 8.1 vs 6.2 em Pint.)  │
│ Impacto: risco erro desce de 18% para 5%. +30min estimados.           │
│ [Aceitar sugestão] [Manter Ana] [Porquê?]                             │
└───────────────────────────────────────────────────────────────────────────┘
```

O dropdown [Trocar ▾] mostra APENAS operadores qualificados para aquela fase, ordenados por score:

```
┌─────────────────────────────────────┐
│ Paulo Gomes     ★8.9  erro 3%  🟢  │
│ Maria Silva     ★8.2  erro 5%  🟢  │
│ Carlos Santos   ★8.1  erro 4%  🟡  │  ← disponível às 10h
│ João Costa      ★7.2  erro 8%  🟢  │
│ António Pereira ★4.2  erro 22% ⚠️  │  ← tier <5 meses
└─────────────────────────────────────┘
```

Quando troca, ConsequenceBox aparece:

```
"Se trocar Ana Reis (★6.2) por Carlos Santos (★8.1):
→ Risco erro desce de 18% para 4%
→ Tempo estimado: +30min (Carlos é mais metódico)
→ Expedição: sem impacto (margem 2 dias)
→ Ana fica livre — pode ir para Lixagem (3 barcos em espera)
Confirmar troca?"
```

---

## 4.4 EXPEDIÇÃO (despacho)

```
┌─────────────────────────────────────────────────────────────────┐
│ SUGESTÕES DO SISTEMA                                            │
│ 💡 3 barcos prontos sem expedição — juntar a quarta poupa €800 │
│    [Aceitar] [Ignorar]                                          │
│ 💡 K1 #4271 pronto 3 dias antes — antecipar para sexta?        │
│    [Antecipar] [Manter] [Porquê?]                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ 📦 Sexta, 16 Maio — Fed. Francesa + Fed. Portuguesa            │
│    48/50 barcos  ████████████████████████████████████████░░ 96% │
│    🟢 42 prontos  🟡 4 em produção (prazo)  🔴 2 em risco     │
│    [Ver barcos] [Gerir]                                         │
│                                                                  │
│ 📦 Terça, 20 Maio — Cliente privado Alemanha                   │
│    18/50 barcos  ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░ 36%   │
│    🟢 18 prontos  💡 +4 barcos prontos sem expedição            │
│    [Ver barcos] [Completar camião]                              │
│                                                                  │
│ 📦 Quinta, 22 Maio — Fed. Italiana + Equipa Sueca              │
│    31/50 barcos  ██████████████████████░░░░░░░░░░░░░░░░ 62%    │
│    🟢 22 prontos  🟡 7 em produção  🔴 2 em risco              │
│    [Ver barcos] [Gerir]                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Dentro de cada expedição (clica [Ver barcos]):

```
┌─────────────────────────────────────────────────────────────────┐
│ 📦 Sexta, 16 Maio — 48 barcos                                  │
├──────────────┬─────────┬───────────┬───────────┬───────────────┤
│ Barco        │ Cliente │ Fase act. │ Estado    │ Acção         │
├──────────────┼─────────┼───────────┼───────────┼───────────────┤
│ K1 #4271     │ Fed. FR │ Armazém   │ 🟢 Pronto │ [Mover ▾]    │
│ K1 #4273     │ Fed. FR │ Montagem  │ 🟡 Prazo  │ [Mover ▾]    │
│ K1 #4275     │ Fed. PT │ Lixagem   │ 🔴 Risco  │ [Mover ▾]    │
│              │         │           │ retrab.23%│ [Atrasar]     │
│ ...          │         │           │           │               │
├──────────────┴─────────┴───────────┴───────────┴───────────────┤
│ [+ Adicionar barco] [Reagrupar por cliente] [Sugestões CPO]   │
└─────────────────────────────────────────────────────────────────┘
```

Drag-and-drop entre expedições. Cada move mostra ConsequenceBox.

---

## 4.5 EQUIPA (colaboradores)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [+ Adicionar] [Importar CSV] [Exportar]                                │
│ Filtros: [Fase ▾] [Disponibilidade ▾] [Score ▾] [Pesquisar nome___]  │
├────────┬─────────────────┬────────┬───────┬────────┬───────┬──────────┤
│ Foto   │ Nome            │ Fase   │ Score │ Erro   │ Tier  │ Estado   │
│        │                 │ princ. │       │        │       │          │
├────────┼─────────────────┼────────┼───────┼────────┼───────┼──────────┤
│ [PG]   │ Paulo Gomes     │ Lamin. │ ★8.9 │ 3.1%  │ >12m  │ 🟢 Activo│
│ [MS]   │ Maria Silva     │ Lamin. │ ★8.2 │ 4.8%  │ >12m  │ 🟢 Activo│
│ [JC]   │ João Costa      │ Colag. │ ★7.2 │ 7.9%  │ >12m  │ 🟡 Férias│
│ [AP]   │ António Pereira │ Lamin. │ ★4.2 │ 22.1% │ <5m   │ 🟢 Activo│
│ ...    │                 │        │       │        │       │          │
└────────┴─────────────────┴────────┴───────┴────────┴───────┴──────────┘
```

Clicar abre perfil editável:

```
┌─ Paulo Gomes ─────────────────────────────────────────────────┐
│                                                                │
│ ┌─ INFORMAÇÃO ──────────────────────────────────────────────┐ │
│ │ Nome: [Paulo Gomes Faria        ]                         │ │
│ │ Custo/hora: [€12.50         ]                             │ │
│ │ Tier: [>12 meses ▾]                                       │ │
│ │ Data entrada: 14/03/2014                                  │ │
│ └───────────────────────────────────────────────────────────┘ │
│                                                                │
│ ┌─ QUALIDADE ───────────────────────────────────────────────┐ │
│ │ Score ML: 8.7    Score Manual (override): [8.9    ]       │ │
│ │ Taxa erro global: 3.1%                                    │ │
│ │ Taxa erro Laminagem: 2.8% (melhor que média 4.5%)        │ │
│ │ Taxa erro K1: 3.2%  K2: 2.1%  K4: 4.0%                  │ │
│ │ Operações totais: 14.195                                  │ │
│ └───────────────────────────────────────────────────────────┘ │
│                                                                │
│ ┌─ SKILLS ──────────────────────────────────────────────────┐ │
│ │ ☑ Laminagem        ☑ Colagem Peças    ☑ Corte           │ │
│ │ ☑ Laminagem Infusão ☑ Colagem Barcos  ☐ Pintura gelcoat │ │
│ │ ☐ Pintura Acabam.   ☑ Desmolde        ☐ Montagem        │ │
│ │ ☑ Reparação         ☐ CQ Final        ☐ Acabamento 2    │ │
│ │ [Adicionar skill] [Remover skill]                        │ │
│ └───────────────────────────────────────────────────────────┘ │
│                                                                │
│ ┌─ CALENDÁRIO ──────────────────────────────────────────────┐ │
│ │ Seg: 08-16 | Ter: 08-16 | Qua: 08-16 | Qui: 08-16       │ │
│ │ Sex: 08-16 | Sab: — | Dom: —                             │ │
│ │ Férias: 15-30 Agosto 2026                                │ │
│ │ [Editar horário] [Marcar ausência]                       │ │
│ └───────────────────────────────────────────────────────────┘ │
│                                                                │
│ [Guardar] [Cancelar] [Desactivar colaborador]                │
│                                                                │
│ ┌─ HISTÓRICO RECENTE ───────────────────────────────────────┐ │
│ │ Hoje:  K1 #4271 Laminagem 4.0h ✅                        │ │
│ │ Ontem: K2 #5103 Laminagem 3.5h ✅                        │ │
│ │ Ontem: K4 #6001 Colagem Peças 2.8h ✅                    │ │
│ │ Seg:   K1 #4270 Laminagem 4.2h ⚠️ (erro: bolha interior)│ │
│ │ [Ver histórico completo]                                  │ │
│ └───────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

Quando o gestor edita o score manual ou adiciona/remove skill, ConsequenceBox:

```
"Se subir o score do Paulo de 8.7 para 8.9:
→ Paulo fica elegível para barcos K1 premium (threshold 8.8)
→ 2 barcos K1 actualmente em espera por operador qualificado ficam desbloqueados
Guardar?"
```

---

## 4.6 QUALIDADE

```
┌─────────────────────────────────────────────────────────────────┐
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                           │
│ │ 81%  │ │ 49%  │ │ 42%  │ │  2   │                           │
│ │1ªpass│ │retr. │ │retr. │ │moldes│                           │
│ │ 🟡   │ │Lixa 🔴│ │Pint 🔴│ │alerta│                           │
│ └──────┘ └──────┘ └──────┘ └──────┘                           │
├───────────────────────────────────────────────────────────────┤
│ ┌─ DIAGNÓSTICO AUTOMÁTICO ─────────────────────────────────┐ │
│ │ 🔴 Throughput caiu para €24K                              │ │
│ │                                                           │ │
│ │ CAUSA RAIZ (confiança 91%):                              │ │
│ │ Molde K1 7 ML (03) degradado — 847 usos                  │ │
│ │                                                           │ │
│ │ CADEIA: Molde degradado → defeitos Laminagem              │ │
│ │ → detectados Desmolde → retrabalho Lixagem                │ │
│ │ → throughput cai €11K/dia                                 │ │
│ │                                                           │ │
│ │ [Propor manutenção] [Ver alternativas] [Porquê?]         │ │
│ └──────────────────────────────────────────────────────────┘ │
├───────────────────────────────────────────────────────────────┤
│ ┌─ MOLDES ─────────────────────────────────────────────────┐ │
│ │ Molde           │ Erros semana │ Normal │ Estado         │ │
│ │ K1 7 ML (03)    │ 23%   🔴     │ 12%   │ [Manutenção]  │ │
│ │ K2 7 L (02)     │ 14%   🟡     │ 10%   │ [Monitorizar] │ │
│ │ K4 7 L (01)     │ 8%    🟢     │ 9%    │ OK            │ │
│ └──────────────────────────────────────────────────────────┘ │
├───────────────────────────────────────────────────────────────┤
│ ┌─ ERROS RECENTES ────────────────────────────────────────┐  │
│ │ K1 #4270 │ Interior enrugado │ Laminagem │ Paulo G. │ 🔴│  │
│ │ K2 #5098 │ Pintura com fios  │ Pintura   │ Ana R.   │ 🟡│  │
│ │ [Ver todos] [Filtrar por fase ▾] [Filtrar por operador ▾]│ │
│ └──────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

## 4.7 CONFIGURAÇÃO

Separadores horizontais em cima:

```
[Scheduling] [Routing] [Cura/Secagem] [Moldes] [Workforce] 
[Qualidade] [Custos] [Alertas] [Aprendizagem] [Sistema]
```

Cada separador tem lista de parâmetros editáveis:

```typescript
interface ConfigParamProps {
  key: string;                    // "scheduling.fitness.w_tardiness"
  label: string;                  // "Peso do atraso de transporte"
  description: string;            // "Quanto o sistema penaliza barcos atrasados"
  value: number | string | boolean;
  default_value: number | string | boolean;
  type: "number" | "text" | "boolean" | "select";
  range?: { min: number; max: number; step: number };
  options?: string[];
  editable: boolean;
  last_changed_by?: string;       // "gestor" ou "sistema (regra aprendida #12)"
  last_changed_at?: Date;
  source: "default" | "manual" | "learned_rule";
  onSave: (value: any, reason: string) => void;
  onReset: () => void;
}
```

Renderiza:

```
┌─────────────────────────────────────────────────────────────┐
│ Peso do atraso de transporte                                │
│ Quanto o sistema penaliza barcos atrasados na fitness.      │
│                                                             │
│ Valor: [===●==========] 0.25                                │
│ Default: 0.25  │  Actual: 0.30 (gestor, há 3 dias)         │
│ Regra aprendida: "Gestor valoriza pontualidade 20% acima    │
│ do default" (confiança 82%)                                │
│                                                             │
│ [Reset para default] [Aceitar regra aprendida]             │
└─────────────────────────────────────────────────────────────┘
```

Separador **Aprendizagem** — o mais importante:

```
┌─ REGRAS APRENDIDAS ─────────────────────────────────────────┐
│                                                              │
│ 🟢 Regra #1 (activa, confiança 92%)                        │
│ "Nunca propor alterações na Laminagem à sexta-feira"        │
│ Baseada em: 7 rejeições consecutivas                        │
│ [Desactivar] [Editar] [Eliminar]                            │
│                                                              │
│ 🟢 Regra #2 (activa, confiança 85%)                        │
│ "Preferir menos setups a mais throughput (delta < 5%)"      │
│ Baseada em: 23 escolhas consistentes                        │
│ [Desactivar] [Editar] [Eliminar]                            │
│                                                              │
│ 🟡 Regra #3 (sugerida, confiança 68% — abaixo threshold)   │
│ "Operadores tier <5m não devem fazer K1 competição"         │
│ Baseada em: 4 overrides manuais                             │
│ [Activar] [Ignorar] [Editar]                                │
│                                                              │
│ PESOS FITNESS APRENDIDOS vs DEFAULT                         │
│ makespan:    default 0.20 → aprendido 0.18 (↓)             │
│ tardiness:   default 0.25 → aprendido 0.30 (↑) ★           │
│ setup:       default 0.15 → aprendido 0.22 (↑) ★           │
│ quality:     default 0.10 → aprendido 0.18 (↑) ★           │
│ throughput:  default 0.15 → aprendido 0.08 (↓)             │
│ idle:        default 0.15 → aprendido 0.04 (↓)             │
│ [Aceitar pesos aprendidos] [Manter defaults] [Reset]        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 4.8 RELATÓRIOS

```
┌─────────────────────────────────────────────────────────────┐
│ GERAR RELATÓRIO                                             │
│                                                             │
│ Tipo: [Produção mensal ▾]                                   │
│ Período: [01/04/2026] a [30/04/2026]                       │
│ Cliente: [Todos ▾]                                          │
│ Formato: [PDF ▾]                                            │
│                                                             │
│ [Gerar]                                                     │
│                                                             │
│ RELATÓRIOS RECENTES                                        │
│ 📄 Produção Abril 2026         Gerado há 2 dias  [Abrir]  │
│ 📄 Fed. Portuguesa Q1 2026    Gerado há 1 semana [Abrir]  │
│ 📄 Qualidade Semana 18        Gerado há 3 dias  [Abrir]   │
└─────────────────────────────────────────────────────────────┘
```

---

## 4.9 OPERADOR (tablet — fullscreen)

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│                    PAULO GOMES                               │
│                    Terça, 13 Maio                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                                                        │  │
│  │   PRÓXIMO BARCO                                       │  │
│  │                                                        │  │
│  │   K1 Vanquish L SCS  #4271                            │  │
│  │   Federação Francesa                                  │  │
│  │                                                        │  │
│  │   Fase: LAMINAGEM                                     │  │
│  │   Molde: K1 7 ML (02)                                 │  │
│  │   Parceiro: Maria Silva                               │  │
│  │   Tempo estimado: 4 horas                             │  │
│  │                                                        │  │
│  │   Instrução: Layup standard carbono 200g              │  │
│  │              Reforço extra na quilha (modelo racing)   │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────┐    ┌────────────────────┐           │
│  │                    │    │                    │           │
│  │     COMECEI        │    │    PROBLEMA        │           │
│  │                    │    │                    │           │
│  │   (100×100px       │    │   (100×100px       │           │
│  │    verde)          │    │    vermelho)        │           │
│  │                    │    │                    │           │
│  └────────────────────┘    └────────────────────┘           │
│                                                              │
│  Hoje: 2 barcos feitos (K2 #5098 ✅ 3.2h, K4 #6001 ✅ 2.8h)│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Após clicar COMECEI → ecrã muda para timer + botão ACABEI:

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│   K1 Vanquish #4271 — LAMINAGEM                            │
│   Com: Maria Silva                                          │
│                                                              │
│                  02:34:17                                    │
│                  (de ~4h estimadas)                          │
│                                                              │
│  ┌────────────────────┐    ┌────────────────────┐           │
│  │                    │    │                    │           │
│  │     ACABEI         │    │    PROBLEMA        │           │
│  │                    │    │                    │           │
│  └────────────────────┘    └────────────────────┘           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Após ACABEI → próxima tarefa automática. Após PROBLEMA → formulário simples:

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│   QUE PROBLEMA?                                             │
│                                                              │
│   ┌──────────────────┐  ┌──────────────────┐               │
│   │ DEFEITO NO BARCO │  │ MOLDE DANIFICADO │               │
│   └──────────────────┘  └──────────────────┘               │
│   ┌──────────────────┐  ┌──────────────────┐               │
│   │ FALTA MATERIAL   │  │    OUTRO         │               │
│   └──────────────────┘  └──────────────────┘               │
│                                                              │
│   Nota (opcional): [_______________________]                │
│                                                              │
│   [ENVIAR]                                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Botões 100×100px. Zero menus. Zero navegação. Só a tarefa.

---

# 5. COMPONENTES PARTILHADOS CRÍTICOS

## 5.1 ConsequenceBox

SEMPRE aparece antes de qualquer acção. Mostra impacto.

```typescript
interface ConsequenceBoxProps {
  if_accept: string | string[];    // consequências de aceitar
  if_reject: string | string[];    // consequências de rejeitar
  alternatives?: {
    label: string;
    consequences: string[];
  }[];
  onAccept: (reason?: string) => void;
  onReject: (reason?: string) => void;
  onAlternative?: (index: number, reason?: string) => void;
  showReasonField: boolean;        // true = campo "porquê" visível
}
```

## 5.2 ApprovalButtons

```typescript
// SEMPRE com campo "porquê"
<ApprovalButtons
  onAccept={(reason) => approve(id, reason)}
  onReject={(reason) => reject(id, reason)}
  onModify={() => openEditor(id)}
  requireReason="on_reject"    // "always" | "on_reject" | "never"
  reasonPlaceholder="Porquê esta decisão? (ajuda o sistema a aprender)"
/>
```

## 5.3 CausalChainCard

Para diagnósticos do ERRO-TREE/Reichenbach/Mill:

```typescript
interface CausalChainCardProps {
  question: string;          // "Porque caiu o throughput?"
  root_cause: string;        // "Molde K1 7 ML (03) degradado"
  confidence: number;        // 0.91
  mechanism: string[];       // ["Defeitos na Laminagem", "Detectados no Desmolde", ...]
  evidence: string[];        // ["847 usos", "Taxa deformação 23% vs 12% normal"]
  recommendation: string;    // "Manutenção molde + rerouting 3 barcos"
  alternatives?: string[];
  onAcceptRecommendation: (reason?: string) => void;
  onReject: (reason?: string) => void;
}
```

---

# 6. PALETA DE CORES

```css
/* Dark mode (default) */
--bg-primary: #0A0A0A;          /* fundo principal */
--bg-secondary: #141414;        /* cards, painéis */
--bg-tertiary: #1E1E1E;         /* inputs, hover */
--text-primary: #FAFAFA;        /* texto principal */
--text-secondary: #A1A1AA;      /* texto secundário */
--border: #27272A;              /* bordas */

/* Status */
--green: #22C55E;               /* no prazo, OK */
--yellow: #EAB308;              /* em risco, atenção */
--red: #EF4444;                 /* atrasado, problema */
--blue: #3B82F6;                /* concluído, informação */
--gray: #6B7280;                /* cura/secagem, inactivo */
--orange: #F97316;              /* alerta alto */

/* Accent */
--accent: #3B82F6;              /* botões primários, links */
--accent-hover: #2563EB;

/* Industrial — alto contraste */
/* Cada cor de status tem ícone + label (nunca cor sozinha) */
/* Fundo escuro = menos reflexo na nave industrial */
```

---

# 7. REAL-TIME

```typescript
// WebSocket primary
const ws = new WebSocket('ws://pp1.nelo.local/ws');

// Eventos que o frontend recebe:
ws.onmessage = (event) => {
  const { type, data } = JSON.parse(event.data);
  
  switch(type) {
    case 'kpi_update':        // KPIs mudaram → refrescar PainelPage
    case 'new_suggestion':    // Nova sugestão CPO → toast + timeline
    case 'order_update':      // Barco mudou fase → refrescar ProducaoPage
    case 'alert':             // Novo alerta → toast + painel
    case 'rule_firing':       // Regra diagnóstico disparou → toast
    case 'worker_status':     // Operador começou/acabou → refrescar
  }
};

// Fallback SSE se WebSocket falhar
// Fallback polling cada 30s se SSE falhar
```

---

# 8. DADOS DE TESTE PARA DESENVOLVIMENTO

Usar estes dados para popular o frontend durante desenvolvimento:

```typescript
const MOCK_BOATS = [
  { id: 4271, model: "K1 Vanquish L SCS", model_short: "K1", client: "Federação Francesa", client_code: "FR", phase: "Laminagem", status: "on_time", transport_date: "2026-05-16", workers: ["Paulo Gomes", "Maria Silva"], mold: "K1 7 ML (02)" },
  { id: 5103, model: "K2 Hybrid", model_short: "K2", client: "Cliente Privado DE", client_code: "DE", phase: "Colagem Peças", status: "on_time", transport_date: "2026-05-20", workers: ["João Costa"] },
  { id: 4272, model: "K1 Quattro L SCS", model_short: "K1", client: "Federação Portuguesa", client_code: "PT", phase: "Pintura Acabamento", status: "at_risk", transport_date: "2026-05-16", workers: ["Ana Reis"] },
  { id: 6001, model: "K4 Multisport", model_short: "K4", client: "Clube Coimbra", client_code: "PT", phase: "Cura", status: "curing" },
  { id: 4275, model: "K1 Vanquish M", model_short: "K1", client: "Federação Portuguesa", client_code: "PT", phase: "Lixagem água", status: "late", transport_date: "2026-05-16" },
];

const MOCK_WORKERS = [
  { id: 1, name: "Paulo Gomes", score: 8.9, error_rate: 0.031, tier: ">12m", status: "active", skills: ["Laminagem", "Colagem Peças", "Desmolde", "Corte", "Reparação"] },
  { id: 2, name: "Maria Silva", score: 8.2, error_rate: 0.048, tier: ">12m", status: "active", skills: ["Laminagem", "Laminagem Infusão", "Colagem Barcos"] },
  { id: 3, name: "João Costa", score: 7.2, error_rate: 0.079, tier: ">12m", status: "vacation", skills: ["Colagem Peças", "Corte", "Montagem"] },
  { id: 4, name: "Ana Reis", score: 6.2, error_rate: 0.15, tier: "<12m", status: "active", skills: ["Pintura Acabamento", "Pintura gelcoat"] },
  { id: 5, name: "António Pereira", score: 4.2, error_rate: 0.221, tier: "<5m", status: "active", skills: ["Laminagem"] },
];

const MOCK_KPIS = {
  throughput_euro: 33200,
  throughput_target: 30000,
  completed_today: 12,
  at_risk: 3,
  alerts: 2,
  first_pass_quality: 0.81,
  rework_lixagem: 0.492,
  rework_pintura: 0.424,
};
```

---

*PP1-NELO Frontend Design Prompt v1*
*8 páginas. 237 checkpoints de verificação. Zero jargão. TUDO editável. TUDO explicado.*
