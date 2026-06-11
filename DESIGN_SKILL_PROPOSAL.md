# DESIGN_SKILL_PROPOSAL — Auditoria de UX/Gantt e proposta de redesenho do planeamento

> **Auditoria multiagente 2026-06-11** (44 agentes, BD real read-only, verificação adversarial).
> Todas as contagens de BD são **snapshot de 2026-06-11** (docker `prodplan-pg-wsl` / `prodplan_one`).
> Classificação de cada afirmação: **confirmado-no-código** / **confirmado-na-BD** / **HIPÓTESE** /
> **pergunta ao dono**.
>
> Documentos irmãos: [AUDIT.md](AUDIT.md) · [DATA_FLOW_MAP.md](DATA_FLOW_MAP.md) ·
> [DOMAIN_RULES.md](DOMAIN_RULES.md) · [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md) ·
> [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md) · [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) ·
> [TEST_PLAN.md](TEST_PLAN.md).
> A skill operacional que materializa estas regras vive em
> `.claude/skills/industrial-ux-design/SKILL.md`.

**Decisões do dono já tomadas (2026-06-11)** — incorporadas neste documento como decisões, não perguntas:

1. **Gate CP-SAT**: tolerância própria + baseline justo (mesmo op-set, sem reparações); guardrails soft isentos quando o makespan melhora >50%; hard axioms intocáveis; configurável por tenant.
2. **Reparações (fases 14/76/77)**: merge-back no **mesmo** plano `/overall` — CP-SAT planeia barcos, reparações agendadas a seguir no mesmo commit, com **filtro/badge próprio**.
3. **"Gama/drop" = tipo/disciplina do produto** (`produto_tipo.TP_ID` / `produto.P_TP_ID_DISCIPLINA`).
4. **Stock mínimo**: importar `P_STOCKMIN` do ERP + override local; lead times de `E_PRAZOENTREGA` (ver [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md)).

---

## 0. Resumo executivo — prioridades

| Prio | Item | Porquê | Secção |
|------|------|--------|--------|
| P0 | Barras de duração reais (deixar de ser grelha de pontos) | é a diferença entre "calendário de post-its" e APS; a infra já suporta | §2.1 |
| P0 | Virtualização + sticky headers | 985 lanes na Por Barco tornam a vista inutilizável | §2.2 |
| P0 | Fim do re-fetch de 2,3 MB/30s | sha imutável; poll só da lista + ETag/GZip | §2.8 |
| P0 | Corrigir wiring partido W1-W5 (OperadorSheet 422, ModeloSheet vazio, filtro-fase morto, "?" morto, `?commit_sha=` ignorado) | funcionalidades anunciadas na UI que falham em silêncio | §1.7 |
| P1 | Filtros 12× (multi-select + URL) | hoje 1/12 completo; gama/modelo/prioridade têm fonte pronta | §3 |
| P1 | Drill em todas as escalas (CountBadge clicável) | semana/mês hoje são leitura cega | §2.3 |
| P1 | Badge/filtro de reparações no mesmo plano | decisão #2 do dono; 76 OFs em reparação live | §3 (#9) |
| P1 | Aba KPIs na FaseSheet (`fila_mediana_h` já calculado) | backend devolve, FE deita fora | §4.1 |
| P2 | Consistência de inputs/badges (DarkBadge, colorScheme, PT-PT) | dívida de design system, baixo risco | §1.5, §4.2 |
| P2 | RiskStrip lazy + remover painel SPOF morto | 4 fetches invisíveis + endpoint apagado | §1.6, W6 |

Dependências externas ao redesenho: a ativação do CP-SAT ([AUDIT.md](AUDIT.md), decisão #1) encolhe
o horizonte de 22.297h (~2,5 anos) para ~690h (~1 mês) — sem isso, qualquer Gantt mostra um plano
fisicamente ilegível; o filtro de materiais depende do [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md)
(decisão #4); os filtros setor e pessoa-de-expedição dependem de resposta do dono (§6).

---

## 1. Auditoria do design atual

### 1.1 Organização e navegação

Confirmado-no-código:

- 5 páginas no menu (`/decisoes`, `/overall`, `/expedicao`, `/llm`, `/configuracoes`) + standalone `/login`, `/operador` — `frontend/src/App.tsx:89-111`; sidebar com 5 itens em `frontend/src/components/layout/Sidebar.tsx:52-58`; raiz redireciona para `/decisoes` (`App.tsx:97`).
- Shell: Sidebar fixa 220px + TopBar 52px — `frontend/src/components/layout/Layout.tsx:33-41`.
- **God-files**: `frontend/src/pages/overall/OverallPage.tsx` ~1.190 linhas; `frontend/src/pages/configuracoes/ConfiguracoesPage.tsx` 1.105 linhas / 50 KB. Qualquer alteração à `/overall` mexe num monólito.
- A vista única "Agrupar por" (Q.146.A) existe e funciona: `GroupBy = 'fase' | 'barco' | 'pessoa' | 'expedicao'` (`OverallPage.tsx:54-60`), chips com contagens (`OverallPage.tsx:985-1012`). Boa fundação — mantém-se na proposta.
- Pesquisa global manda hits de barco/molde/erro para `/overall` **sem contexto** — `SearchResultsPage.tsx:57-66` descarta o `hit.id` para 3 dos 4 tipos (só `operador` abre sheet).

### 1.2 A `/overall` NÃO é um Gantt (achado alto, confirmado-no-código)

- É uma **grelha lane×slot**: 1 célula = 1 dia/semana/mês; todas as vistas empurram items com `spanSlots: 1` **fixo** — `PorFaseView.tsx:228-233`, `PorBarcoView.tsx:211`, `PorPessoaView.tsx:244`. O posicionamento usa só `op.start` (`dateToSlotIndex`, `Timeline.tsx:92-105`); `end`/`duration_min` existem no tipo (`components/overall/types.ts:15-16`) mas **nunca são desenhados**. Sem barras de duração, sem dependências, sem resize.
- **Nuance importante** (verificação adversarial): a primitiva `TimelineLanes.tsx:183` **já suporta** barras multi-slot (`width: it.spanSlots * slotWidth`) — a limitação está nos *callers*, não na infra de render.
- Existem **2 componentes Gantt verdadeiros órfãos**: `components/charts/GanttChart.tsx` e `components/dark/GanttChart.tsx` (Gantt SVG completo com `GanttBar` work/curing/wait) — 0 imports fora dos barrels.
- Drill-down existente e bom: heatmap de densidade (`DENSITY_THRESHOLD = 3`, `DensityCell.tsx:13`, intensidade log em `:26`) → `CellOpsSheet` (`CellOpsSheet.tsx:13-75`).

### 1.3 Densidade e legibilidade

- OpCards de **10px** com truncate + tooltip `title` — `OpCard.tsx:100-105`. Abaixo do mínimo legível para chão de fábrica.
- Lane da Por Barco mistura 3 identidades num label mono truncado a 140px: `[order_id, product_id, cliente].join(' · ')` onde `product_id` é o **OF_P_ID numérico cru** (`PorBarcoView.tsx:155-161`; injetado em `cpo_commit_orders.py:341`) — o operador vê "902252 · 20155 · Fed. X" em vez do nome do modelo.
- Escalas **semana/mês são leitura cega**: células viram `CountBadge` sem `onClick` nem drag (`PorFaseView.tsx:77-83`; `CountBadge.tsx:11-28` não recebe handler) — inspecionar/editar exige voltar à escala dia.
- Janela default hoje−7d → hoje+15d (`DAYS_PAST/DAYS_FUTURE`, `OverallPage.tsx:45-46`) — mas o plano greedy live tem makespan **22.297h (~2,5 anos)**; com CP-SAT (~690h ≈ 1 mês) o plano inteiro passa a caber numa janela navegável. O redesenho do Gantt e a ativação do CP-SAT ([AUDIT.md](AUDIT.md)) reforçam-se mutuamente.

### 1.4 Filtros — 1 completo em 12 desejados (achado alto)

Confirmado-no-código + confirmado-na-BD: o único filtro da grelha é texto-livre sobre `[order_id, operator_name, phase_name, cliente]` (`OverallPage.tsx:492-495` — **nem `product_id`/modelo entra**) + toggle "Só barcos" (`:489`, `is_boat !== false`) + `PeriodSelector` (datas, completo). BD: **0 colunas** gama/drop/sector/seccao em `factory_raw` (information_schema); `TransportBatch` sem responsável em 3 camadas (FE `views/PorExpedicaoView.tsx:22-34`, API `src/plan/api/transport.py:70-83`, ORM `src/plan/models/transport.py:37-59`). Estado detalhado e proposta: ver §3.

### 1.5 Estados, badges e legendas

- Badges "Rascunho · não aprovado" (`status !== 'LIVE'`, `OverallPage.tsx:917-925`) e "Plano degradado" (`safety_net_triggered`, `:926-934`) são **spans inline**, não `DarkBadge` — inconsistente com o design system. Relevância real: a BD tem **203 commits DRAFT vs 3 LIVE**, logo o badge "Rascunho" está praticamente sempre visível.
- Badge **★ afinidade nunca acende** (médio, confirmado): `api_affinities.py:111` devolve `operator_id` UUID (`Employee.id`), as lanes usam `employee_code` ("20365") — `PorPessoaView.tsx:184,196`: `topAffinity.get(id)` UUID-vs-code nunca casa.
- Badge **⚡ Acelerada (boost) morto** (médio, confirmado): `OpCard.tsx:75` testa `(op.effective_boost ?? 0) > 50`, mas o mapeamento do plano (`OverallPage.tsx:382-416`) nunca atribui `effective_boost`; `commits.py:117-138` só injeta `is_boat`/`product_id`; `types.ts:18-19` admite «ainda não no /schedule (Q.116.G)».
- Legenda Realizado/Planeado (`OverallPage.tsx:936-951`) é só visual — **não filtra**.
- `StatusBadge` do design system tem labels EN ('Active','Pending','Completed') — `DarkBadge.tsx:73-81`; hoje só usado em testes, mas é export público: risco PT-PT latente.

### 1.6 Performance (achado alto, confirmado-na-BD)

- Último commit DRAFT: **8.059 ops, payload `operations` = 2.319 kB**, re-fetched **a cada 30s** com `include_operations: true` (`OverallPage.tsx:160-169`, `refetchInterval: 30_000`). O backend FastAPI **não tem GZip/ETag** (0 matches em `src/`) — re-download integral apesar de o `commit_sha256` ser imutável. (Na demo o Caddy comprime no fio, mas serialização no backend + parse no browser mantêm-se na íntegra.)
- **985 lanes** na vista Por Barco **sem virtualização** (`lanes.map(...items.filter(...))` = O(lanes×items), `TimelineLanes.tsx:122-123`; zero react-window em `pages/overall`) e **sem `position: sticky`** no header de datas nem na coluna de labels (`TimelineLanes.tsx:86-119`). Nota: a vista por defeito é `groupBy='fase'` (~41 lanes, `OverallPage.tsx:94`) — o problema explode ao agrupar Por Barco.
- ~11 queries no load (commits, detail 2,3 MB, actuals, catalog, employees×2, alerts, decisions, excluded, snapshot, +4 do RiskStrip); polling 30s em 4 delas. `QualityRiskBadge` já é lazy via IntersectionObserver (Q.144.E, `QualityRiskBadge.tsx:30-49`) — padrão a replicar.
- `RiskStrip` monta os **4 painéis de risco mesmo colapsado** («sempre montados, visibilidade controlada por CSS», `RiskStrip.tsx:45-51`, `expanded=false` por defeito `:16`) → 4 fetches por visita que ninguém vê (ex. `OtdRiskPanel.tsx:22-28`).

### 1.7 Wiring partido (mapa)

| # | Sintoma | Causa (file:line) | Severidade | Estado |
|---|---------|-------------------|------------|--------|
| W1 | Clicar num operador na Por Pessoa → **422/SheetError** | `PorPessoaView.tsx:206-208` passa `employee_code` ("20365"); endpoint exige `employee_id: UUID` (`entity_summary.py:1193`). Adversarial: mesmo com UUID dava 404 — o endpoint procura `Employee.id` (`entity_summary.py:1209-1213`) e a vista nunca tem esse UUID | alto | confirmado-no-código |
| W2 | ModeloSheet abre **meio-vazio com título numérico** | `OverallPage.tsx:704` passa `OF_P_ID` (`cpo_commit_orders.py:340-344`); `entity_summary.py:626-646` indexa por `ProductionOrder.product_name`. BD: 9.607 `production_orders`, **0** `product_name` numéricos → tabs Encomendas/Em produção sempre vazias; só a tab Fases resolve (`model_routing_assignment` 4.737/4.737 numéricos) | alto | confirmado-na-BD |
| W3 | "Filtrar por fase" no label da lane **morto** | `PorFaseView.tsx:191-200`: o `<Clickable kind="fase">` interno faz `e.stopPropagation()` (`Clickable.tsx:34-37`) e engole o clique; kinds `boat/operator/cliente` de `selection.ts:12` nunca são emitidos por nenhuma vista | médio | confirmado-no-código |
| W4 | Botão "?" de ajuda (Q.56, pedido explícito do Luis) **morto em 4/5 páginas** | chaves `PAGE_HELP` são rotas antigas ('planeamento','copilot','configuracao','inbox') — `pageHelp.ts:14-34,57-61`; `PageHeader.tsx:39` fica `undefined`. Só `/expedicao` tem `helpId` explícito (`ExpedicaoPage.tsx:68`); a tab Regras tem "?" interno via `RegrasPage.tsx:143` | alto | confirmado-no-código |
| W5 | `?commit_sha=` **ignorado** — "Ver plano" das decisões abre sempre o último plano | `DecisionHubActions.tsx:78` gera o link; `OverallPage.tsx` não tem `useSearchParams` (0 ocorrências); query fixa `cpoCommitsApi.list({limit:1, excludeDegenerate:true})` (`OverallPage.tsx:151`) | alto | confirmado-no-código |
| W6 | Painel SPOF do RiskStrip **nunca aparece** | `SpofRiskPanel.tsx:25` chama `/v1/workforce/risks/spof`, endpoint **apagado** no saneamento (`src/workforce/__init__.py`); `RiskStrip.tsx:40` continua a anunciar "SPOF" | médio | confirmado-no-código |
| W7 | Drag-drop da Por Expedição **inativo** + ignora a escala | `views/PorExpedicaoView.tsx:5-7`: «inactivo enquanto `POST /v1/plan/transport/assign` não existir» (rota não existe); `:109` `eachDayOfInterval` sempre por dia | médio | confirmado-no-código |
| W8 | Dedupe realizado→plano **esconde repetições futuras** de fases repetíveis | `OverallPage.tsx:443-448`: `doneKeys = Set(order__phase)` filtra todo o plano; fases com `FP_PODE_REPETIR=true` (coluna real de `factory_raw.fases_producao`) perdem a passagem futura planeada. Impacto em barcos concretos não medido | médio | confirmado-no-código (mecanismo) |
| W9 | Em modo Editar, o alvo de clique para o editor é **minúsculo** | `OpCard.tsx:87-90` ignora cliques em `a, button[data-clickable]`; `:109-117` o label inteiro está dentro de `<Clickable kind="encomenda">` → clicar no texto abre a EncomendaSheet; só o resto do cartão de 10px seleciona a op | baixo | confirmado-no-código |
| W10 | Inputs inconsistentes claro/escuro entre sheets | `FaseSheet.tsx:488,509,531` `bg-white text-slate-900` (correto p/ regra) vs `OperationEditSheet.tsx:23-33` fieldStyle dark; `PeriodSelector.tsx:84-108` date-inputs **sem `colorScheme: dark`** → ícone do calendário escuro-sobre-escuro no Chrome/Windows | baixo | confirmado-no-código |
| W11 | Query keys inline fora de `keys.ts` → invalidação cruzada falha | `views/PorExpedicaoView.tsx:64` `['plan','transport','batches',…]` vs `transportKeys.batches` (`keys.ts:420-423`) usado pela ExpedicaoPage — sincronizar camiões em `/expedicao` não invalida a Por Expedição. Também `OverallPage.tsx:301,533`; `OtdRiskPanel.tsx:23`; `Sidebar.tsx:65` | baixo | confirmado-no-código |
| W12 | ExpedicaoPage é a única página com tabs fora do URL | `ExpedicaoPage.tsx:27` `useState` local, sem `?tab=` — refresh/deep-link perdem a aba | baixo | confirmado-no-código |

---

## 2. Proposta: Gantt escalável

Princípio: **evoluir a fundação existente** (TimelineLanes + GroupBy + DensityCell + CellOpsSheet), não reescrever. A primitiva já suporta barras multi-slot; os Gantt órfãos servem de referência visual (GanttBar work/curing/wait) e devem ser absorvidos ou apagados — não manter 3 implementações.

### 2.1 Barras de duração reais

- Cada op desenha `startSlot..endSlot`: `spanSlots = max(1, slotsBetween(op.start, op.end ?? op.start + duration_min))`. Os campos já chegam ao FE (`types.ts:15-16`); a mudança é nos 3 callers (`PorFaseView.tsx:228-233`, `PorBarcoView.tsx:211`, `PorPessoaView.tsx:244`) + clamp à janela visível.
- Distinguir **tempo de trabalho vs cura/espera** dentro da barra (padrão do GanttChart órfão: segmentos work/curing/wait). Fonte: `cpo_meta` do commit + `NELO_CURING_GAPS_SEED` (cura é química, não fila — [DOMAIN_RULES.md](DOMAIN_RULES.md)).
- Ops realizadas (of_fp) mantêm verde sólido; planeadas tracejado — semântica atual preservada.

### 2.2 Virtualização e sticky (obrigatório, não opcional)

- Virtualizar lanes acima de **~60** (TanStack Virtual; já há precedente de lazy-load no QualityRiskBadge). Indexar items por lane **uma vez** (`Map<laneId, items[]>`) em vez de `items.filter` por lane (mata o O(lanes×items) de `TimelineLanes.tsx:122-123`).
- `position: sticky` no header de datas (top) e na coluna de labels (left) — hoje ausentes (`TimelineLanes.tsx:86-119`). Com 985 lanes × janela de 22 dias, sem sticky o utilizador perde a referência ao 2.º ecrã de scroll.

### 2.3 Zoom dia/semana/mês com drill em TODAS as escalas

- Manter `buildDaySlots/buildWeekSlots/buildMonthSlots` (`Timeline.tsx:51-86`).
- `CountBadge` passa a receber `onClick` → abre `CellOpsSheet` com o intervalo da célula (semana/mês), tal como o `DensityCell` já faz na escala dia. Editar a partir do drill (selecionar op → OperationEditSheet) em qualquer escala.
- A Por Expedição passa a respeitar a escala (hoje `eachDayOfInterval` fixo, `views/PorExpedicaoView.tsx:109`).

### 2.4 Agrupamento

- Manter os 4 grupos (fase/barco/pessoa/expedição) + acrescentar **setor/disciplina** quando a decisão #3 estiver materializada no payload (ver §3, filtro gama).
- Por Fase continua ordenada por `FP_SEQUENCIA` (`/v1/plan/phases/catalog`, `phase_preferred_operators.py:82`) — correto, preservar.
- Por Barco: label passa a `order_id · nome do modelo · cliente` (resolver `OF_P_ID → produto.P_DESIGN` no backend, mesmo fix do W2).

### 2.5 Cap de densidade com drill-down

- Manter `DENSITY_THRESHOLD=3` → DensityCell → CellOpsSheet; manter cap de 6 cartões/célula (Q.146). Com barras de duração, a densidade por célula desce naturalmente (ops longas deixam de empilhar no slot do início).

### 2.6 Dependências visuais

- **Só em contexto focado** (lane de 1 barco selecionado ou CellOpsSheet), nunca nas 985 lanes: linha fase n→n+1 da rota do barco, com gap de cura anotado. Desenhar dependências globais num plano de 8.059 ops é ruído, não informação.

### 2.7 Edição inline

- Manter o fluxo drag → preview-delta → MoveBoatConfirm (motivo ≥10 chars) → `POST /v1/plan/operations/reorder` (`reorder.py:57`; `OverallPage.tsx:520-560`).
- Corrigir W9: grip de drag/editar com **alvo ≥40px**, label clicável separado do corpo do cartão.
- `OperationEditSheet`: deixar de fixar a hora a T08:00; considerar multi-operador (o campo real é `workers[]` — lição Q.148).

### 2.8 Performance do payload

- O `commit_sha256` é imutável → o detail com `include_operations:true` deve ter `staleTime: Infinity` por sha; o polling de 30s passa a só **listar** commits (resposta pequena) e refazer o detail apenas quando o sha muda.
- Backend: GZip middleware + `ETag` no GET do commit; opcionalmente `?window=de..até` para servir só as ops da janela visível (2,3 MB → dezenas de kB no caso típico).
- RiskStrip: montar painéis **lazy on-expand** (corrige o W6 parcialmente por arrasto: 4 fetches deixam de correr escondidos).

### 2.9 Deep-link e URL como estado

- `?commit_sha=` lido com `useSearchParams` (corrige W5; pergunta ao dono: navegação por histórico de planos é desejada ou o "último saudável" é regra fixa do Q.162?).
- `?groupBy=`, `?escala=`, filtros e período no URL — partilhável entre chefes de secção; corrige também a pesquisa global (hit de barco → `/overall?barco=902252`).

---

## 3. Filtros propostos (12)

Padrão de UI: barra de filtros multi-select com chips removíveis + contagem de resultados, persistida no URL. Para cada filtro: **fonte de dados real** e disponibilidade **hoje** (snapshot 2026-06-11).

| # | Filtro | Fonte de dados real | Disponível hoje? | Trabalho necessário |
|---|--------|---------------------|------------------|---------------------|
| 1 | **Barco** (OF) | `order_id` no payload do commit; `v_of_em_producao` = 1.145 live | PARCIAL — texto-livre + toggle "Só barcos" (`OverallPage.tsx:484-496`) | multi-select com typeahead sobre os order_id do plano |
| 2 | **Modelo** | `product_id` = `OF_P_ID` já no payload (`commits.py:117-138`); nome em `factory_raw.produto` | NÃO — `filterText` não inclui `product_id` (`OverallPage.tsx:492-495`) | injetar `product_name` no commit (join `produto`) + multi-select; resolve W2 e o label do §2.4 |
| 3 | **Fase** | `phase_id/phase_name` no payload; catálogo `/v1/plan/phases/catalog` (FP_SEQUENCIA) | PARCIAL — texto-livre + agrupar Por Fase; seleção por label morta (W3) | multi-select alimentado pelo catálogo; corrigir W3 |
| 4 | **Operador** | `workers[]` (employee_code = E_ID); `/v1/core/employees` + `v_active_operators` (106 ativos) | PARCIAL — texto-livre + agrupar Por Pessoa | multi-select com nomes reais (hook `useEmployeeNamesByCode`, Q.154) |
| 5 | **Setor** | sem coluna `sector/seccao` em `factory_raw` (confirmado-na-BD, 0 hits); existe setor DERIVADO em `src/workforce/sector_preference_service.py` (Q.140 pessoa×sector) | NÃO | **pergunta ao dono** (mantém-se): setor = disciplina do produto, secção física (grupo de fases FP) ou sectores Q.140? Construível a partir do derivado se for a 3.ª |
| 6 | **Expedição** (camião/data) | `/v1/plan/transport/batches` (`transport.py:235`) + `actuals.expeditions` (transp_of) | PARCIAL — só via vista Por Expedição | filtro "com camião atribuído / data de expedição em X" na grelha |
| — | **Pessoa de expedição** | **SEM FONTE** — nenhum campo de responsável/condutor em `transp_of`, `transporte` nem `TransportBatch` (3 camadas verificadas: `views/PorExpedicaoView.tsx:22-34`, `transport.py:70-83`, `models/transport.py:37-59`) | NÃO | documentado como sem fonte; **pergunta ao dono**: onde vive este dado no ERP? Sem resposta, o filtro não nasce |
| 7 | **Gama** (= tipo/disciplina, decisão #3) | `produto_tipo.TP_ID` / `produto.P_TP_ID_DISCIPLINA` — existem em `factory_raw` (é o critério de barco: TP_ID raiz=Kayak) | NÃO na UI; dados SIM na BD | injetar disciplina no payload do commit (mesmo mecanismo de `is_boat`) + multi-select; reaproveitar nas vistas agrupadas |
| 8 | **Materiais em risco** | hoje `ShortageRiskPanel` lê `supply.*` maioritariamente vazias (`supply_rop_configs=0`; `min_stock_qty=0` em 14.110 materiais; `P_STOCKMIN>0` em 1.110; lead_time 7d placeholder) | NÃO — painel só informativo | depende da decisão #4 ([STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md)): com `P_STOCKMIN` importado + BOM (`produto_componente` 111.339 ativas), realçar/filtrar barcos cujo material está abaixo do mínimo |
| 9 | **Reparações** | fases {14, 76, 77}; `setup_family "Reparação (fase 14)"` já nas ops do commit; **76 OFs em reparação** live | PARCIAL — só KPI `emProducao.reparacao` no banner (`OverallPage.tsx:764-771`) | decisão #2: reparações no MESMO plano com **badge próprio** no OpCard + filtro mostrar/ocultar/só-reparações |
| 10 | **Prioridade** (boost) | `effective_boost` 0-100 existe no backend (order/boat/client boost) mas nunca é mapeado (`types.ts:18-19`, Q.116.G) | NÃO — badge ⚡ morto (§1.5) | mapear `effective_boost` no commit→payload→OpCard; filtro "aceleradas (>50)". **Pergunta ao dono** mantém-se: prioridade = boost, prioridade do cliente, ou outra? |
| 11 | **Datas** | `PeriodSelector` (6 atalhos + de/até custom, `PeriodSelector.tsx:36-43,83-109`) | **SIM — completo** | só persistir no URL |
| 12 | **Estado** (realizado/planeado/atrasado/em-risco) | `kind` realizado-vs-planeado já distinguido no merge (`OverallPage.tsx:443-449`); "atrasado" precisa de `due_date` (cobertura 0→79% pós Q.168-F1); "em-risco" do QualityRiskBadge | PARCIAL — só legenda visual (`OverallPage.tsx:936-951`) | chips de estado client-side; "atrasado" = `end > due_date`. **Pergunta ao dono**: que estados exatos quer filtráveis? |

Resumo: **1/12 completo hoje (datas)**; 5 parciais (barco, fase, operador, expedição, reparações, estado); 5 inexistentes mas com fonte conhecida (modelo, gama, materiais, prioridade); 2 dependem de resposta do dono (setor, pessoa-de-expedição — esta última **sem fonte** no ERP espelhado).

---

## 4. Subtabs e sheets — o que corrigir

### 4.1 FaseSheet (`frontend/src/components/entitySheets/sheets/FaseSheet.tsx`)

- Hoje: 4 abas Operadores · Barcos exigentes · Cura · Configuração (`FaseSheet.tsx:31-36`). A Configuração lê/escreve `/v1/plan/phases/{id}/config` (`phase_config_admin.py:260,284`) — **funciona**.
- **Aba KPIs nova**: o backend já devolve `fila_mediana_h` (`entity_summary.py:905-917`, Q.160 — mediana real de fila por fase de `of_fp`) e o FE **não tipa nem mostra** (`entityApi.ts:117-124`). Conteúdo proposto: `fila_mediana_h`, duração p50 da fase (histórico of_fp), nº de ops planeadas vs realizadas na janela, aderência plano-vs-real. **Pergunta ao dono** (mantém-se): confirmar a lista exata de KPIs desejados.
- Inputs `bg-white text-slate-900` (`FaseSheet.tsx:488,509,531`) estão corretos pela regra do projeto — é o `OperationEditSheet` que diverge (ver 4.2).

### 4.2 OperationEditSheet (`frontend/src/components/overall/OperationEditSheet.tsx`)

- Funciona (operador com nomes reais Q.159 / fase / data → reorder, `OperationEditSheet.tsx:96-129`), mas: data fixa **T08:00**; **1 só operador** quando o modelo real é `workers[]` (Q.148); `fieldStyle` dark (`:23-33`) inconsistente com a regra de inputs do projeto — unificar (regra: claro `bg-white text-slate-900 placeholder:text-slate-400`).

### 4.3 CellOpsSheet (`CellOpsSheet.tsx:13-75`)

- Funciona; mas em modo Ver, "ver ou editar" só destaca — o editor exige modo Editar (`OverallPage.tsx:1127-1136,499-503`). Proposta: CTA explícita "Editar" no item que comuta o modo, em vez de falhar silenciosamente.
- Passa a ser o drill-down universal das escalas semana/mês (§2.3).

### 4.4 Sheets de entidade

- **OperadorSheet**: corrigir W1 — o endpoint deve aceitar `employee_code` (resolver `employee_code == E_ID → Employee.id` no backend) em vez de obrigar o FE a ter UUIDs que nunca tem.
- **ModeloSheet**: corrigir W2 — indexar por id de produto (OF_P_ID) com join a `factory_raw.produto` para nome humano; tabs Encomendas/Em produção passam a encher; título deixa de ser numérico (`ModeloSheet.tsx:97`).
- **EncomendaSheet**: OK (`entity_summary.py:1024`) — manter; resolver a ambiguidade do clique (**pergunta ao dono**: clicar num barco na grelha abre a ENCOMENDA — comportamento atual do cartão — ou o MODELO?).
- Deep-link `?sheet=&id=` (`EntitySheetProvider.tsx:28-67`) — manter e usar na pesquisa global.

### 4.5 Transversal

- Botão "?" de ajuda: corrigir W4 (atualizar chaves `PAGE_HELP` para as rotas atuais + conteúdo das 5 páginas) — pedido explícito do Luis em Q.56.
- Query keys: migrar os inline (W11) para as factories de `lib/api/keys.ts` (Q.61.27).
- Badges de estado do plano migram para `DarkBadge` (variantes existentes) e `StatusBadge` ganha labels PT-PT antes de qualquer uso em produção.

---

## 5. Como a skill será usada (fases 6-7 do plano)

A skill `.claude/skills/industrial-ux-design/SKILL.md` (ficheiro B desta entrega) é o **gate de revisão de UI** das fases 6-7 do [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — as fases que tocam o frontend de planeamento (Gantt escalável + filtros, e sheets/polimento):

1. **Antes de tocar UI**: o agente carrega a skill e percorre a checklist (densidade, cor-só-para-estado, virtualização, sticky, estados honestos, inputs, PT-PT, URL-como-estado).
2. **Durante**: as decisões de layout citam a regra da skill que as justifica (ex.: "barra multi-slot porque R2; virtualizado porque 985 lanes > N").
3. **No fim de cada sub-sprint Q.X.Y**: a secção "Anti-padrões observados" da skill funciona como lista de regressão — nenhum dos W1-W12 do §1.7 pode reaparecer; o reviewer (skill `nelinho-review`) recebe a checklist como critério de aprovação.
4. **Testes**: os casos de UI correspondentes vivem no [TEST_PLAN.md](TEST_PLAN.md) (ex.: lane > N → virtualizado; CountBadge clicável em semana/mês; OperadorSheet abre com employee_code).

A skill é viva: cada anti-padrão novo encontrado em revisão é acrescentado com file:line.

---

## 6. Perguntas em aberto ao dono

(As decisões #1-#4 de 2026-06-11 já estão incorporadas; restam estas.)

1. **Setor**: disciplina do produto (`P_TP_ID_DISCIPLINA`), secção física da fábrica (grupo de fases FP), ou sectores Q.140 (pessoa×sector)?
2. **Pessoa de expedição**: é o responsável/condutor do camião? Onde vive no ERP? (Nenhum campo encontrado em `transp_of`/`transporte`/`TransportBatch`.)
3. **Prioridade**: o boost 0-100 existente, a prioridade do cliente, ou outra coisa?
4. **Estado**: que estados exatos queres filtráveis (realizado/planeado/atrasado/em-risco)?
5. **Aba KPIs da FaseSheet**: fila mediana + p50 durações + aderência chegam, ou queres mais?
6. **Clique num barco**: abre a ficha da ENCOMENDA (atual) ou do MODELO?
7. **Histórico de planos**: o `/overall` deve aceitar `?commit_sha=` (deep-link navegável a planos antigos) ou "mostrar só o último saudável" (Q.162) é regra fixa?

---

*Gerado pela auditoria multiagente de 2026-06-11. Contagens de BD = snapshot dessa data.*
