# CUBE_LLM_KPI_AUDIT.md — Auditoria à camada Cube, pipeline LLM, KPIs visíveis e módulo profit €

> **Snapshot:** 2026-06-11, branch `feat/decisoes-frescas`, BD `prodplan_one` (read-only, container
> `prodplan-pg-wsl`), Cube v1.3.86 live em `:4000`. **Todas as contagens de BD são deste dia** —
> views live (ex.: `v_of_em_producao`) variam intra-dia. O backend `:8001` **não estava a correr**
> durante a auditoria: os cards foram testados directamente no Cube (`/cubejs-api/v1/load`), não
> end-to-end via `dashboard-dev`.
>
> **Legenda de estados:** `[CÓD]` confirmado-no-código · `[BD]` confirmado-na-BD ·
> `[HIP]` hipótese · `[?]` pergunta ao dono.
>
> Documentos irmãos: [AUDIT.md](AUDIT.md) (achados globais), [DATA_FLOW_MAP.md](DATA_FLOW_MAP.md)
> (origem de cada dado), [DOMAIN_RULES.md](DOMAIN_RULES.md) (definições canónicas),
> [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) (fases de correção),
> [TEST_PLAN.md](TEST_PLAN.md) (cobertura de testes).

---

## 1. Catálogo: Cube live vs contrato Python

### 1.1 Números

| Camada | Onde | Contagem |
|---|---|---|
| Cube live `/meta` | container `prodplan-cube` → `cube/model/*.yml` | **51 cubes / 139 measures** `[BD]` |
| Contrato Python | `src/copilot/cube/measure_contract.py:249` `MEASURE_REGISTRY` | **132 measures** (130 nomes 2-segmentos + 2 workforce 3-segmentos) `[CÓD]` |
| Índice de retrieval | `cube/data/measure_index.npz` (gerado por `scripts/refresh_cube_measure_index.py` a partir do **registry**, não do YAML) | 132 entradas, 1:1 com o registry `[CÓD]` |

O registry é validado à importação (`_validate_registry`, `measure_contract.py:3139`), mas valida
consistência **interna** — não valida contra o `/meta` do Cube nem contra a BD. Daí coexistirem as
três derivas seguintes.

### 1.2 Os 18 cubes mortos — view/tabela em falta (lista completa) `[BD]`

**18 dos 51 cubes** apontam para fontes que **não existem** nesta BD → **51 das 139 measures morrem
em query-time** (provado live: Cube `/load` devolve HTTP 400 `relation does not exist`; o cube de
controlo `producao_ofs_fechadas_dia` devolve 200 com dados — não é problema de infra).

| # | Cube morto | Fonte em falta |
|---|---|---|
| 1 | `ambiental_cura_compliance` | `marts.v_cura_compliance_mes` |
| 2 | `ambiental_cura_horas` | `marts.v_ciclos_cura` |
| 3 | `ambiental_estufa_humidade` | `marts.v_estufa_humidade_mes` |
| 4 | `ambiental_estufa_temp` | `marts.v_estufa_temp_mes` |
| 5 | `ambiental_iot_alarmes` | `factory_raw.iot_sensor_alarm` (única não-marts) |
| 6 | `comercial_facturacao_agente` | `marts.v_facturacao_agente_trim` |
| 7 | `consumo_by_of` | `marts.v_consumo_by_of_dia` |
| 8 | `logistica_docs` | `marts.v_transp_docs_mes` |
| 9 | `logistica_transportes` | `marts.v_transportes_mes` |
| 10 | `moldes_top_uso` | `marts.v_moldes_top_uso` |
| 11 | `operadores_horas` | `marts.v_horas_operador_mes` |
| 12 | `planeamento_reagendamentos` | `marts.v_reagendamentos_mes` |
| 13 | `plataforma_copilot_feedback` | `marts.v_copilot_feedback_mes` (sobre `copilot_request_log` — tabela **inexistente**, ver §4.2) |
| 14 | `plataforma_copilot_latency` | `marts.v_copilot_latency_dia` (idem) |
| 15 | `plataforma_copilot_rag` | `marts.v_copilot_rag_dia` (idem) |
| 16 | `producao_throughput_modelo` | `marts.v_throughput_modelo_sem` |
| 17 | `workforce_colaboradores` | `marts.v_workforce_colaboradores_mes` |
| 18 | `workforce_horas_extra` | `marts.v_workforce_horas_extra_mes` |

**Causa-raiz** `[CÓD]`: as marts são criadas por **49 scripts one-off** `scripts/setup_marts_*.py`;
o Alembic só cria o **schema** (`alembic/versions/063_q93_a_marts_schema.py:32`) e
`bootstrap_dev_full.py` tem **0 referências** a `setup_marts`. Na BD existem 30 views marts; faltam
17 marts + 1 `factory_raw`. Nota da verificação adversarial: vários scripts para as views em falta
**já existem no repo** (ex.: `scripts/setup_marts_workforce_colaboradores_mes.py`,
`setup_marts_transportes_mes.py`, `setup_marts_moldes_top_uso.py`) — nunca foram corridos nesta BD.
A correção provável é **executá-los/orquestrá-los**, não escrever views novas.

`[?]` As 18 marts em falta são esperadas neste ambiente, ou isto É a BD de referência? Os
`setup_marts_*.py` deviam ser corridos pelo bootstrap/deploy (ou migrados para Alembic)?

### 1.3 As 9 measures do YAML fora do MEASURE_REGISTRY `[CÓD]`

Diff YAML(139) × registry(132). Invisíveis ao picker (`list_measure_catalog`,
`measure_contract.py:2423`) e ao retrieval (`measure_index.npz` só lê o registry):

1. `ambiental_estufa_humidade.min`
2. `ambiental_estufa_humidade.max`
3. `comercial_facturacao_agente.n_declaracoes`
4. `logistica_docs.tratados_total`
5. `qualidade.defeitos_intermedios` (a `taxa_intermedia` ESTÁ registada, mas o numerador não)
6. `workforce_colaboradores.total`
7. `workforce_colaboradores.n_eventos`
8. `workforce_horas_extra.total`
9. `workforce_horas_extra.n_eventos`

### 1.4 As 2 measures workforce com nomes inválidos `[CÓD]` + `[BD]`

O registry declara nomes de **3 segmentos** que **não existem** no Cube:

- `measure_contract.py:2291` → `"workforce.colaboradores_activos.total"`
- `measure_contract.py:2318` → `"workforce.horas_extra.total"`

O Cube `/meta` live só expõe `workforce_colaboradores.{total,n_eventos}` e
`workforce_horas_extra.{total,n_eventos}` — não existe cube `workforce`. A deriva é **conhecida e
whitelistada** desde Q.108 (`tests/copilot/test_cube_meta_alignment.py:64-69`, "Pre-Q108 drift
conhecida (Q.106)") mas continua por corrigir. Efeitos:

- **Picker**: `_coerce_card_specs` (`ask_cube.py:536`) aceita-as do registry → `_run_card`
  (`ask_cube.py:381`) deriva a dim `workforce.data` inexistente; a própria measure 3-segmentos é
  membro inválido no Cube → o card dá **sempre** `status="error"`, mesmo com `period="none"`.
- **Ask-cube**: `measure_retrieval.py:195-197` devolve chaves do registry →
  `candidate_cubes={"workforce"}` (`interpret.py:568`) não casa os blocos curados
  `workforce_colaboradores`/`workforce_horas_extra` (`cube_interpret.md:355/376`); a intersecção do
  enum com o `/meta` fica vazia (`schema_compiler.py:54-61`) e o constrained decoding **degrada para
  todas as measures**. Mitigação parcial Q.157.D: gera-se um bloco auto do registry — o prompt não
  fica vazio, mas anuncia ao LLM os nomes 3-segmentos errados que o enum degradado já não corrige.

`[?]` Corrigir os nomes do registry para `workforce_colaboradores.*`/`workforce_horas_extra.*`
(alinhar com o Cube) e reconstruir o `measure_index`, ou renomear os cubes YAML?

---

## 2. KPIs visíveis (`/llm?tab=kpis` → `frontend/src/pages/llm/KPIsTab.tsx`)

### 2.1 Os 8 cards "Destaques" — `_CARD_SPECS` (`src/copilot/routers/ask_cube.py:289-298`), servidos por GET `/api/copilot/cube/dashboard-dev` (`ask_cube.py:433`)

| Card | Measure | Fórmula SQL | Tabela origem | Filtros | Período | ⚠ |
|---|---|---|---|---|---|---|
| OFs produzidas hoje | `producao_ofs_fechadas_dia.total` | COUNT de OFs com `OF_DATAFIM` no dia | `marts.v_ofs_fechadas_dia` ← `factory_raw.of` | — | hoje | — |
| OFs em curso | `producao_ofs_em_curso.total` | `SUM(n_ofs)` (snapshot por fase) | `marts.v_ofs_em_curso_snapshot` ← `of_fp` | fase `FP_SEQUENCIA<30` | snapshot | **⚠ definição** (ver §3.1): live **8.510** vs critério NELO 1.14x |
| Taxa de defeitos | `qualidade.taxa_defeitos` | `SUM(defeitos)::float/NULLIF(SUM(total_checks),0)` (`qualidade_taxa_defeitos.yml:2361`) | `marts.v_taxa_defeitos_dia` ← `OF_CHECKLIST` | gravidade ≥1 | **`period="none"` = ALL-TIME** | **⚠ sem rótulo de período** — parece taxa actual |
| Faturação (mês) | `comercial_facturacao.total` | `SUM(facturado_eur)`; notas de crédito subtraem | `marts.v_facturacao_mes` ← `factory_raw.entidade_phc_fact.EPHCF_FACTURADO` | — | mês anterior completo | `[HIP]` base sem IVA — YAML marca "pendente confirmação CFO" (`comercial_facturacao.yml:460-462`); total all-time live €125.778.749,59 |
| Consumo material € (mês) | `consumo_material.custo` | `SUM(MOV_QUANTIDADE × P_PRECOCUSTO)`; NULL para material sem preço (nunca inventa €0) (`consumo_material.yml:941-954`) | `marts.v_consumo_material_dia` ← `movimento` | — | mês anterior | — |
| Backlog | `planeamento_backlog.total` | SUM diário | `marts.v_backlog_dia` | — | snapshot/dia | — |
| Lead time P50 | `producao_lead_time_of.lead_time_p50` | percentil 50 do lead time de OF | `marts.v_lead_time_of_*` ← `of_fp` | — | **`period="none"` = ALL-TIME** | **⚠ sem rótulo de período** |
| OFs expedidas (mês) | `logistica_ofs_expedidas.total` | COUNT mensal | `marts.v_ofs_expedidas_mes` | — | mês anterior | — |

Todos os 8 cards usam cubes **saudáveis** (nenhum dos 18 mortos). Detalhe cosmético `[CÓD]`: o
código e o frontend dizem "7 cards" (`ask_cube.py:466` "dashboard CURADO (7 cards fixos)",
`KPIsTab.tsx:8` "Destaques — 7 cards curados") mas `_CARD_SPECS` tem **8** entradas desde que
Q.152 acrescentou `ofs_produzidas_hoje` — comentários stale.

Há ainda 4 gráficos curados em `_CHART_SPECS` (`ask_cube.py:301-310`), incl. `facturacao_mensal`.

### 2.2 OtdHeatmap (na mesma tab, FORA do Cube)

GET `/v1/profit/kpis/otd-heatmap` (`OtdHeatmap.tsx:5/:34` → `src/profit/api/kpis.py:421-514`):
% on-time por produto×semana agrupando `ProductionSchedule`. **`plan.production_schedules` = 0
linhas** `[BD]` → matriz **sempre vazia** (estado honesto, feature morta). A query key está inline,
não em `lib/api/keys.ts`. É o único KPI do módulo profit visível na UI — ver §6.

### 2.3 Picker "Os meus indicadores"

- GET `/cube/measures-dev` (`ask_cube.py:505` → `list_measure_catalog()`,
  `measure_contract.py:2423` — 132 entradas) + POST `/cube/measure-cards-dev` (`ask_cube.py:563`;
  lista fechada, 422 fora do registry, máx. 60 cards).
- Selecção em `localStorage` `kpis.cube.selection` (`KPIsTab.tsx:44`) com self-heal contra
  measures removidas (`KPIsTab.tsx:114-120`).
- **Problema**: ~45 das 132 measures do picker caem em cubes com fonte inexistente (§1.2) + as 2
  workforce inválidas (§1.4) → **~1/3 do menu devolve card "error" sempre**. O estado de erro é
  honesto, mas o utilizador escolhe de um catálogo onde um terço está morto.

### 2.4 Endpoints `*-dev` — 404 em production `[CÓD]`

`dev_only` (`src/shared/auth/headers.py:313-326`) levanta 404 se
`settings.environment=="production"` (valor que `.env.production.example:28` define). Dependem
dele: `/ask-dev-cube` (`ask_cube.py:250-254`), `/cube/dashboard-dev` (:434-437),
`/cube/measures-dev` (:506-509), `/cube/measure-cards-dev` (:564-567). **Só `/ask-cube` tem versão
autenticada** (:236-246). O chat chama SEMPRE `/ask-dev-cube` com `DEV_TENANT` hardcoded
(`copilotApi.ts:19, :97-99`); em `!response.ok` devolve `null` → **fallback silencioso** para
`/ask` (comentário literal "Cube indisponível → fallback silencioso", `copilotApi.ts:108`) — em
production o caminho Cube do chat desaparece sem aviso. Na tab KPIs (`cubeApi.ts:92/112/116`) a
falha NÃO é silenciosa (página mostra erro), mas também só usa os `-dev`.

`[?]` Produção vai correr com `environment != "production"` (como a demo) ou criam-se endpoints
autenticados antes do go-live?

---

## 3. Definições ambíguas ou erradas

### 3.1 "OFs em curso": 8.510 vs 1.144 — dois critérios com o mesmo nome `[BD]`

| Fonte | Critério | Live 2026-06-11 | Quem usa |
|---|---|---|---|
| `marts.v_ofs_em_curso_snapshot` (cube `producao_ofs_em_curso`) | OF com fase `FP_SEQUENCIA<30` | `SUM(n_ofs)` = **8.510** | card "OFs em curso" do `/llm`, picker, chat |
| `factory_raw.v_of_em_producao` (critério NELO Q.158: op aberta na fase atual, sem `OF_DATAFIM`) | regra EXATA da fábrica | **1.144** nesta medição (a âncora canónica do dia regista **1.145** — view live, varia intra-dia; alvo NELO ~1.211) | CPO scope, página produção, watermark do robô |

O utilizador vê números **7× diferentes** para conceitos com o mesmo nome, e o card não explica o
critério. **Proposta — 2 nomes distintos** (alinhar com [DOMAIN_RULES.md](DOMAIN_RULES.md)):

- **"OFs abertas (ERP)"** — mantém `producao_ofs_em_curso` (renomear `title`/descrições), critério
  `FP_SEQUENCIA<30`, útil como volume bruto de carteira aberta.
- **"Barcos em produção (critério NELO)"** — measure nova sobre `factory_raw.v_of_em_producao`
  (a view canónica já partilhada pelo CPO), que é o número que a fábrica reconhece.

### 3.2 Agregações default duvidosas `[CÓD]`

| Measure | Problema | Evidência |
|---|---|---|
| `comercial_arpu.clientes_activos` | `type: sum` sobre **COUNT DISTINCT pré-computado** — somar entre meses/disciplinas conta a mesma identidade várias vezes (o cube irmão `comercial_facturacao` usa `countDistinct` e avisa) | `comercial_arpu.yml:397-401` |
| `operadores_horas.n_ofs_distintas` | `type: sum` com aviso textual "NÃO somar entre meses" — mas o type executa SUM por default (cube actualmente morto, §1.2; o erro persiste quando a view voltar) | `operadores_horas.yml:1406-1411` |
| Família `*_avg`/`*_p50` | `type: avg` sobre médias mensais = **média de médias não ponderada** (limitação reconhecida nas descrições, mas executada na mesma) | `aprovacoes_q17.yml`, `lead_time_*`, `phase_transition` |

### 3.3 `moldes_top_uso.moldes_count` — filtro prometido que não existe `[CÓD]`

`moldes_top_uso.yml:1360-1364`: a descrição diz "COUNT moldes activos com counter > 0" mas a
fórmula é `sql: n_utilizacoes` com `type: count` — conta valores **não-NULL, incluindo 0**. Três
measures do cube usam a MESMA coluna `n_utilizacoes` com types diferentes (sum/max/count). Cube
actualmente morto (view em falta), mas o erro fica armado para quando a view voltar.

### 3.4 Anchors numéricos obsoletos nas descrições YAML `[BD]`

- `producao_ofs_em_curso.yml:1810`: "Anchor … 4.233 OFs em curso" vs live **8.510**.
- `moldes.yml:1246`: documenta espelho com 91 moldes vs 510 reais do ERP
  (`factory_raw.moldes`=91 `[BD]`).

Estes anchors entram nos blocos do prompt do interpret. A narração está protegida pelo
`guard_numbers` (payload-only), mas descrições desactualizadas podem enviesar a escolha de
measure/filtros e confundem quem audita.

### 3.5 Duplicações por desenho — risco de dupla contagem delegado à disciplina do LLM `[CÓD]`

- `marts.v_facturacao_mes` alimenta **3 cubes** (`comercial_facturacao`, `_disciplina`,
  `_top_clientes`) com a mesma `SUM(facturado_eur)`.
- `producao_ofs_em_curso.total` ≡ `producao_ofs_por_fase.total` (mesma contagem, 2 cubes).
- **4 variantes de "OFs fechadas"**: `producao_ofs_fechadas_dia` (dia/header),
  `producao_lead_time_of.ofs_fechadas` (mês/envelope of_fp), `producao_throughput_modelo`
  (semana — morto), `producao_disciplina_mes` (mês×disciplina).

Os YAMLs avisam "NUNCA somar entre si", mas a única defesa em runtime é o texto do prompt:
`can_sum_measures` (`measure_contract.py:2456`) só compara **unidades canónicas** — não deteta a
mesma facturação em cubes distintos.

---

## 4. Pipeline LLM (ask-cube)

### 4.1 Arquitectura — o que está bem `[CÓD]`

`routers/ask_cube.py:94 _process` → `cube/interpret.py:457 interpret` (gemma4:e4b, **constrained
decoding** via `schema_compiler.py:132`) → `CubeClient /load` → `cube/narrate.py:572
narrate_with_guard` (qwen3.5:9b, 1 retry). Estados honestos:
`ok|abstain|no_data|guard_failed|ambiguous` (>20 linhas = vago, `ask_cube.py:54`).

- **Retrieval**: materiais FAISS+BM25 (`material_retrieval.py`); measures top-5 com threshold 0.02
  (`interpret.py:79-80`; abaixo → abstain pré-LLM, `:555-567`).
- **Guards de narração**: `guard_numbers` (`narrate.py:491`, tolerância 1%, payload-only) +
  `guard_context` (`:177` — mês/ano vs dateRange, material, unidade, fração>100%).
- **Datas determinísticas**: `resolve_question_period` + override do `period_label` + remoção de
  filtros LLM sobre dims de tempo (`interpret.py:626-735`) — "LLM propõe, código decide".
- **Fidelity-guard "produção" → material "custos de produção": JÁ CORRIGIDO (Q.167.I)** `[CÓD]`:
  `_MATERIAL_GENERIC_TOKENS` (`measure_contract.py:2920-2925`) exclui
  produção/custos/efeitos/…, `_discriminative_material_tokens` (`:2928`) filtra-os, o match exige
  word-boundary (`:2996`); Q.172.B relaxou ainda o guard para sinónimos do catálogo
  (`:3029-3057`). Ressalva operacional: o backend não estava a correr — quando arrancar tem de ser
  **com este código** (gotcha conhecido de processo stale, ver memória `reference_backend_no_reload`).

### 4.2 Gaps

| Gap | Detalhe | Evidência |
|---|---|---|
| **Prompt curado só para 16/51 cubes** | `cube_interpret.md` (1.195 linhas) tem blocos manuais nas linhas 39-401 para: consumo_material, qualidade, producao_ofs_em_curso, producao_ofs_fechadas_dia, producao_disciplina_mes, producao_pecas_laminadas, producao_ofs_por_fase, comercial_facturacao, comercial_top_clientes, comercial_facturacao_disciplina, logistica_ofs_expedidas, logistica_atrasos_culpa, ambiental_cura_horas, workforce_colaboradores, workforce_horas_extra, capacidade_fase. O fallback auto-gerado (`render_catalog_block`, `measure_contract.py:3202`) só dispara quando **NENHUMA** candidata tem bloco curado (`interpret.py:354-369`) — se o top-5 mistura curado + não-curado, o segundo fica **sem descrição** no prompt (decisão deliberada Q.157.D, mas mantém o gap "measure nova sem bloco" parcialmente aberto; cf. memória `feedback_llm_picker_needs_prompt_block`) | `[CÓD]` |
| **Loop feedback→prompt inexistente** | POST `/feedback/user` grava `copilot_user_feedback` (`routers/suggestions.py:64`) — **0 rows na BD** e **nenhum leitor** em `src/` (só models + writer). `copilot_request_log` **não existe como tabela** (`SELECT` → `relation does not exist`) — mata também os 3 cubes `plataforma_copilot_*` (§1.2 #13-15). Sem `PromptVersion`/prompt versioning em BD (Q.111 fase 2 não implementada). O que existe: `jobs/daily_feedback.py` (sinais diários) e `jobs/abl_feedback.py` (triplets DPO → JSONL) | `[BD]`+`[CÓD]` |
| **Endpoints todos `*-dev`** | Ver §2.4 — em production o caminho Cube do chat cai silenciosamente para `/ask` e a tab KPIs dá erro | `[CÓD]` |
| **Sem golden-SQL suite NL→CubeQuery** | `tests/copilot/test_golden_traces_q66_e.py` = 10 traces shape-only com Ollama **mockado** (testa a forma do `/ask`, não a correctude das queries Cube); `data/learning/golden/` é dataset DPO de governance (`scripts/dpo_eval.py`); verificação live depende do manual `scripts/e2e_llm_smoke.py` (23 cenários). Regressões semânticas (como o caso workforce §1.4) não são apanhadas pelo CI — ver [TEST_PLAN.md](TEST_PLAN.md) | `[CÓD]` |

`[?]` O loop feedback→prompt (Q.32/Q.111) é para reactivar? Hoje o 👍/👎 grava numa tabela que
ninguém lê, e o `copilot_request_log` que alimentaria os KPIs do próprio copiloto não existe.

---

## 5. Explicabilidade — o número chega, a fonte não

### 5.1 Estado actual `[CÓD]`

**O backend já devolve a query exacta**: `AskCubeResponse.query` (measures, filters, dateRange) +
`annotation` do Cube (`ask_cube.py:212-218`), `abstain_reason` e `warnings` detalhados, período
canónico forçado na narração (`narrate.py:525-529`). **Mas o frontend descarta tudo isso**:
`cubeToCopilotResponse` (`frontend/src/lib/api/copilotApi.ts:36-92`) usa só `narration` + data
preview, com citação genérica fixa `{ref:'cube', label:'Cube · camada semântica'}`; `r.query`
**nunca é renderizado**. E a fórmula SQL + `sql_table` vivem só em `cube/model/*.yml`: o
`MeasureSpec` não tem campo de fórmula e `list_measure_catalog` (`measure_contract.py:2423`) só
devolve name/label/unit/domain/dims. `cube_narrate.md` (80 linhas) não pede citação de fonte.
Resultado: o utilizador vê o número, o período e os avisos — **nunca a tabela, o campo nem a
fórmula**.

### 5.2 Desenho da correção (→ fase 8 do [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md))

1. **FE renderiza a query** — bloco expansível "Como foi calculado" no cartão de resposta do chat:
   measures pedidas, filtros aplicados, `dateRange`/`period_label`. Tudo já vem em `r.query`; é só
   parar de o descartar em `copilotApi.ts:36-92` e substituir a citação genérica por uma citação
   estruturada por measure.
2. **Catálogo devolve `sql` + `sql_table`** — acrescentar os 2 campos ao `MeasureSpec` (ou
   extraí-los do YAML no build do `measure_index`, fonte única `cube/model/*.yml`) e expô-los em
   `list_measure_catalog`/`measures-dev` e `measure-cards-dev`. O picker passa a mostrar fórmula +
   tabela origem em tooltip/detalhe de cada card; o chat anexa-os à citação.
3. **Narração cita a fonte** — `cube_narrate.md` passa a exigir 1 linha final
   "Fonte: `marts.v_x` · `SUM(...)` · período Y"; `guard_context` valida que a fonte citada bate
   com a query (mesma filosofia payload-only do `guard_numbers`).
4. **Cards "Destaques" ganham rótulo de período** — `taxa_defeitos` e `lead_time_p50` com
   `period="none"` passam a mostrar "todo o histórico" no subtítulo (fix de 1 linha por card em
   `_CARD_SPECS`/`KPIsTab.tsx`).

---

## 6. Módulo profit € — fórmulas honestas, quase tudo morto

Das ~20 rotas `/v1/profit/*`, **só 2 têm consumidor no frontend** (`OtdHeatmap.tsx:34` e
`marginPreviewApi` em `DecisionHubActions.tsx:53`/`SimulacoesTab.tsx:53`/`AutoProposeOverlay.tsx:33`)
— e ambas mostram vazio hoje. Os € que o utilizador VÊ (cards do `/llm`) vêm do **Cube**, não do
profit. App.tsx:91-110 só tem 7 rotas; não existe página de Direção/Custos/Pricing.

### 6.1 Cadeia morta por dados `[BD]`

| Componente | Fórmula (honesta) | Bloqueio | Evidência BD |
|---|---|---|---|
| COGS 6 componentes | material+M.O.+máquina+setup+overhead+scrap (`cogs_calculator.py:63-71`; pipeline real `cost_service.py:175-217` sobre BOM real + horas OF_FP × `labor_rates.loaded_rate`) | **nunca executado** — exposto em POST `/cogs/orders/{id}/calculate` (`api/cogs.py:81`) mas ninguém o corre | `profit.cost_calculations=0`; inputs prontos: `core.bom_items=86.438`, `core.labor_rates=4.244` (3.204 com taxa, média 5,41 €/h) |
| Margem por barco | `revenue − total_cogs` (`api/dashboard.py:376-385 _margin_row`) | sem COGS nem receita | `profit.order_revenue=0` → tudo `calculated=false`, margens null |
| Overhead | componente do COGS | sem taxa configurada (0€ honesto) | `core.overhead_rates=0` |
| **CoeficienteX (bónus €)** | `Σ(bonus_eur − duração×cost_rate)` (`margin_preview.py:74-96`); casa canónica `bonus_payout_service.py` | **sem ETL** — única escrita é o REST `bulk_upsert` (`api/bonus_payouts.py:55-63`), nenhum job o chama; `_load_bonus` (`margin_preview.py:159-196`) devolve sempre 0€ | `profit.phase_bonus_payout=0` apesar de `factory_raw.produto_fase`=43.510 com **22.002 linhas `PRODF_COEFICIENTE_X>0`** (média 1,32) |
| Meta diária € | `baseline = target_eur × (commit_hours/8h)` (`margin_preview.py:275-313`); CPO lê em `src/plan/cpo/fitness.py:229-244` | **`core.daily_revenue_target=0`** → baseline=None → delta €=null → `DecisionHubActions.tsx:85` esconde a pill €; revenue_alignment do CPO neutro. UI de escrita JÁ existe (Configurações › custos → POST `/v1/config/revenue-target`, `q115_config.py:127`) mas nunca foi usada | 0 linhas |
| OTD heatmap | % on-time produto×semana (`api/kpis.py:421-514`) | lê `plan.production_schedules` | **0 linhas** → matriz vazia (§2.2) |
| Métricas CEO (OTD/backlog/FPY) | `dashboard_metrics_service.py:137-200,308-353` | lê `factory_curated."order"` | **0 linhas** |
| Cenários what-if | multiplicadores sobre `CostCalculation` base (`cost_service.py:306-352`) | `cost_service.py:315-317` → `ValueError("No calculation found")` sempre | `profit.profit_scenarios=0` |
| Rework € | `Σ cost_estimate_eur` (`quality/services/impact_service.py:72` — soma honesta) | quase sem dados | `quality.rework_entry=5.909` entradas, **só 4 com custo (610€ total)** |
| Incoerência interna | `/v1/profit/dashboard`: faturação repontada ao ERP real (Q.138.A, `throughput_service.py:189-197`) mas `top_skus` (`:112-150`) lê `OrderRevenue` (0 linhas) → sempre `[]`; o payload declara `"source": "factory_raw.entidade_phc_fact"` (`:179`) para um bloco misto real+morto | rota órfã | — |

### 6.2 Violações (e quase-violações) do invariante #8 — números autorais `[CÓD]`

| Onde | O que está fabricado | Evidência |
|---|---|---|
| `margin_preview.py:34-36, :91` | **`_DEFAULT_COST_RATE_EUR_H = 12.00` hardcoded** ("Valor NELO provisório — substituir por core.labor_rates quando disponível") — mas `core.labor_rates` JÁ tem 4.244 taxas reais (média 5,41 €/h). Agravante: `:242` inventa **1h por operação** como último recurso. Com `phase_bonus_payout=0`, `predicted_margin = −duração×12€` (sempre negativa) | alto |
| `src/explain/diagnostics/erro_tree.py:518-526` | `_recommend_action` devolve `"cost_estimate_eur": 400, "downtime_hours": 4` **hardcoded** para mold_degradation — € inventado em recomendação ao operador | médio |
| `src/profit/explanation_engine.py:273-289, :221-242` | pesos "Direct labour 55% / Rework 25% / Overtime 20%" e impactos "+5%", "+8%" inventados; exposto via `/kpis/snapshot-explained` (`api/kpis.py:399-412`) — sem consumidor UI actual (comentário `LLMPage.tsx:12` é stale), mitigado por `advisory_mode:True` | médio (latente) |
| `dashboard_metrics_service.py:40, :238` | backlog € = `count × 2.350€/barco` (`BACKLOG_DEFAULT_VALUE_EUR`, TenantConfig `cost.target.unit_value_eur=2350` `[BD]`) — proxy autoral em vez de `P_PRECOVENDA` real (`profit.product_pricing=3.714` produtos já sincronizados, seed marcado "confirmar com CFO") | médio (órfão) |
| `cogs_calculator.py:161-162, :193` | scrap defaults autorais: recovery 50%, rework factor 10%, scrap rate 2% — parametrizáveis mas sem origem ERP | baixo |
| `pricing_engine.py:112-113, :28-31, :203` | markup 40%, target margin 30%, factores dinâmicos 1.0, floor COGS×1.01 — tudo autoral; `pricing_recommendations=0`, sem UI | baixo (órfão) |
| `kpi_history.py:27-33` + `api/kpis.py:531` | job diário escreve 5 KPIs (nenhum em €) que ninguém lê — `profit.kpi_snapshot=60` linhas, `orders_completed` sempre NULL; KPIsTab migrou para o Cube | baixo |

### 6.3 Os 2 positivos

1. **Invariante #5 (CoeficienteX) cumprido, com gate automático** `[CÓD]`: grep em `src/plan/cpo`
   dá 13 matches, **todos comentários proibitivos** (`state.py:392` "monetary bonus (€), NOT a…",
   `pair_assignment.py:9`, `state_loaders.py:301-302` "NUNCA usa FP_HORA_COEF nem os
   COEFICIENTE_X") — zero uso funcional. Gate CX1 em `scripts/verify_invariants.py:46-75` (regex +
   2 âncoras de comentário). E o **factor M.O. 1.065 é legítimo** (não é violação #8):
   `material_cost_service.py:44-45` só guarda identificadores ERP (`VAR_ID=2`, `P_TP_ID=90`); o
   VALOR vem de `core.erp_variables` (`var_id=2='1.065'` `[BD]`), aplicado só se `P_TP_ID=90`
   (`:168-179`), com fallback honesto 1.0 (`:150-165`) — paridade Q.167.F com a fórmula canónica
   do ERP.
2. **Faturação coerente entre as 2 fontes €** `[BD]`: o Cube (`marts.v_facturacao_mes` =
   `SUM(factory_raw.entidade_phc_fact."EPHCF_FACTURADO")` por mês, confirmado em `pg_views`) e o
   profit (`throughput_service.py:189-197 _sum_revenue`, mesma coluna por dia) leem a **MESMA
   coluna** do espelho PHC (100.872 linhas; último dia 2026-06-09 = 100.240€). Sem risco de
   divergência de fonte; e como o dashboard profit é UI-órfão, nunca há dois números diferentes no
   mesmo ecrã. A diferença de janela (mês completo vs hoje/MTD) é intencional.

---

## 7. Correções propostas — mapa para o [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

| # | Correção | Ficheiros/alvo | Fase |
|---|---|---|---|
| 1 | Remover €12/h hardcoded → ler `core.labor_rates` (regra a decidir: média real, taxa do operador planeado, ou taxa por fase) | `margin_preview.py:34-36,:91,:242` | **Fase 1** (€ hardcoded) |
| 2 | Remover €400/4h fabricados na recomendação de molde | `erro_tree.py:518-526` | **Fase 1** |
| 3 | ExplanationEngine: remover/derivar os pesos 55/25/20 e impactos "+5%" (ou desligar a rota órfã) | `explanation_engine.py:273-289,:221-242` | **Fase 1** |
| 4 | Backlog €: trocar proxy 2.350€ por `P_PRECOVENDA` (`profit.product_pricing`) — pendente CFO | `dashboard_metrics_service.py:40,:238` | **Fase 1** |
| 5 | Configurar `core.daily_revenue_target` (UI já existe: Configurações › custos) — desbloqueia pill € em /decisoes + revenue_alignment do CPO | acção de configuração, `q115_config.py:127` | **Fase 1** |
| 6 | Correr/orquestrar os `setup_marts_*.py` em falta (17 marts + decidir `iot_sensor_alarm`) e integrá-los no bootstrap/deploy ou Alembic | `scripts/setup_marts_*.py`, `bootstrap_dev_full.py` | **Fase 8** |
| 7 | Workforce: alinhar nomes do `MEASURE_REGISTRY` com o Cube + rebuild `measure_index.npz` + retirar a whitelist do teste | `measure_contract.py:2291,:2318`, `test_cube_meta_alignment.py:64-69` | **Fase 8** |
| 8 | Registar as 9 measures YAML em falta no registry (ou removê-las do YAML) | `measure_contract.py` | **Fase 8** |
| 9 | "OFs em curso" → 2 nomes distintos: "OFs abertas (ERP)" + "Barcos em produção (critério NELO)" sobre `v_of_em_producao` | `producao_ofs_em_curso.yml`, cube novo, `_CARD_SPECS` | **Fase 8** |
| 10 | Agregações: `comercial_arpu.clientes_activos`→countDistinct na view; `n_ofs_distintas` sem sum default; rotular avg-de-médias | `comercial_arpu.yml:397-401`, `operadores_horas.yml:1406-1411` | **Fase 8** |
| 11 | `moldes_count` com o filtro `counter>0` prometido | `moldes_top_uso.yml:1360-1364` | **Fase 8** |
| 12 | Refresh dos anchors obsoletos (4.233→8.510; moldes 91) | `producao_ofs_em_curso.yml:1810`, `moldes.yml:1246` | **Fase 8** |
| 13 | Endpoints autenticados para dashboard/measures/measure-cards/ask-cube no FE (matar dependência `*-dev` + DEV_TENANT hardcoded) | `ask_cube.py`, `copilotApi.ts:19,:97-108`, `cubeApi.ts` | **Fase 8** |
| 14 | Explicabilidade: FE renderiza `r.query`; catálogo devolve `sql`+`sql_table`; narração cita fonte; rótulo de período nos cards all-time (desenho em §5.2) | `copilotApi.ts:36-92`, `measure_contract.py:2423`, `cube_narrate.md`, `_CARD_SPECS` | **Fase 8** |
| 15 | Loop feedback→prompt: leitor de `copilot_user_feedback` + criar `copilot_request_log` (revive os 3 cubes `plataforma_copilot_*`) — pendente decisão | `suggestions.py`, migração nova | **Fase 8** |
| 16 | Golden-SQL suite NL→CubeQuery no CI (casos: workforce, períodos, materiais) — ver [TEST_PLAN.md](TEST_PLAN.md) | `tests/copilot/` | **Fase 8** |
| 17 | ETL CoeficienteX (`produto_fase`/`of_fp` → `profit.phase_bonus_payout`) — pendente semântica (§8) | job novo + `bonus_payout_service.bulk_upsert` | **Fase 10** (item 3 do plano) |
| 18 | Job batch COGS (`calculate_cogs_from_sources` sobre OFs) OU declarar a família margem-por-barco morta e remover — decisão do dono | `cost_service.py:175-217` | **Fase 8** |
| 19 | Blocos curados de prompt para cubes ressuscitados pelo #6 (regra: measure nova ⇒ bloco no `cube_interpret.md`) | `prompts/cube_interpret.md` | **Fase 8** |

---

## 8. Perguntas ao dono `[?]`

1. **Marts em falta**: as 18 fontes ausentes são esperadas neste ambiente ou esta É a BD de
   referência? Política: `setup_marts_*.py` no bootstrap/deploy ou migrar para Alembic?
2. **Faturação €125,8M**: confirma-se base **sem IVA**? (HIPÓTESE no YAML desde Q.102, "pendente
   confirmação CFO".)
3. **"Não Laminado"** deve continuar a contar em `producao_pecas_laminadas.total`
   (`ILIKE '%lamin%'`)? Excluir mudaria o anchor de 2.393 para 2.202 (Abril 2026).
4. **Workforce**: corrigir o registry (preferido) ou renomear os cubes YAML?
5. **Go-live**: endpoints autenticados antes de produção, ou produção corre com
   `environment != "production"`?
6. **Meta €30-35K/dia**: oficializar agora em `core.daily_revenue_target`? Valor exacto e
   `effective_from` (30.000 / 32.500 / outro)?
7. **Custo/h para margem de operações futuras**: média real de `labor_rates`, taxa do operador
   planeado, ou taxa por fase?
8. **Semântica do `PRODF_COEFICIENTE_X`** (média 1,32): é o bónus € pago por unidade de
   fase×produto, ou precisa de transformação (×quantidade, ×horas) antes do ETL?
9. **Backlog €**: o proxy 2.350€/barco mantém-se ou passa a `P_PRECOVENDA` real (3.714 produtos)?
10. **COGS**: ganhar job batch sobre as OFs, ou declarar a família margem-por-barco fora do scope
    do menu actual e removê-la?
11. **Overhead**: existe taxa oficial €/h de gastos gerais para `core.overhead_rates`, ou fica 0
    de propósito?
12. **Scrap defaults** (recovery 50%, rework 10%, scrap 2%): têm base real NELO ou derivam-se do
    histórico (`rework_entry`/`of_fp`)?
13. **Loop feedback→prompt** (Q.32/Q.111): reactivar?
