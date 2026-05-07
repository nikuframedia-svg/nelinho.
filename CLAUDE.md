# CLAUDE.md — nelinho

## What this project is

**ProdPlan ONE / nelinho** — APS+ML+LLM on-premise para a NELO (Mar Kayaks, Vila do Conde). Fábrica
de kayaks de competição (~14.7 barcos/dia, K1/K2/K4 + recreio). 41 fases, 510 moldes, 122 operadores
activos, 61 padrões de routing. Meta: €30-35K/dia.

**Stack:** Python 3.11 + FastAPI + SQLAlchemy 2.0 + asyncpg + Pydantic + React 19 + Vite + TypeScript
strict + TanStack Query + Tailwind + Postgres 16 + Ollama (Gemma na RTX 5060 Ti). Native deploy
(no Docker) + systemd. PCs/tablets da fábrica acedem por browser na rede local.

**Owner:** Luis (luis@nikufra.ai). PT-PT informal, respostas curtas, números concretos.
"€2.400" não "valor significativo"; "4 horas" não "algum tempo"; "Sexta às 14h" não "nos próximos
dias".

## Always-true invariants (no tags — apply everywhere)

These are project-level. Violating any of them is a bug regardless of context.

1. **ZERO MOCKS no frontend** (Luis 2026-05-06) — `frontend/src/` nunca tem `const MOCK_X = [...]`,
   nunca `data ?? [{...}]` placeholder fallbacks. Empty/error states explícitos. Dev e prod
   usam a mesma API; a diferença é o `tenant_id`.
2. **PT-PT, não PT-BR** — utilizador (não usuário), tu (não você), camião (não caminhão), registo
   (não registro), gerir (não gerenciar), fase (não estação).
3. **7 Spelke axioms são imovíveis** — capacity ≥ 0, precedence monotónica, mold exclusivo,
   dual-resource Laminagem (88.5%), skill match, cura/secagem 16 transições, safety_net ≥ baseline.
   Detalhe em [agent_docs/spelke_axioms.md](agent_docs/spelke_axioms.md).
4. **Q.17 rules têm sempre `requires_human_approval=True`** — `kill_switch` é admin-SQL-only.
   LLM nunca opt-out destas duas garantias por design (Pydantic `Literal[True]`).
5. **CoeficienteX é DINHEIRO €**, NUNCA tempo. Usar em `src/profit/`. NUNCA em `decoder/fitness/
   pair_assignment/state`. Confirmado pelo CEO.
6. **Sub-sprint Q.X.Y format** — todo o trabalho >1 ficheiro arruma-se em `Q.<num>.<letra>.<num>`
   (ex: Q.17.B, Q.18.A.3). Um sub-sprint = um logical commit = pytest verde + smoke demo-able.
7. **Audit trail intact** — cada mudança de estado escreve `*_revision` ou `audit_log` na mesma
   transacção. "porque é que o sistema fez X há 3 semanas" tem que ter resposta sem `git blame`.

## How to verify your work

```bash
# Sempre antes de declarar algo "feito"
$env:PYTHONPATH = "c:/Users/User/nelinho"

# Canary (governance suite — 348 tests, ~53s)
.\.venv\Scripts\python.exe -m pytest tests/governance/ -q

# Module-specific durante TDD
.\.venv\Scripts\python.exe -m pytest tests/<module>/ -v

# Full suite (antes de commit grande)
.\.venv\Scripts\python.exe -m pytest tests/ -q   # alvo actual: 1684 passed

# Frontend typecheck
cd frontend && npx tsc -b --noEmit

# DB do zero (quando schema desync)
.\.venv\Scripts\python.exe scripts/bootstrap_dev_full.py
```

## Where to look for context

- **`.claude/skills/`** — 6 SKILL.md auto-loaded pelo Claude Code:
  - `nelinho-discipline` — pre-flight checklist (Karpathy 4 princípios). **Lê antes de qualquer task.**
  - `nelinho-incremental` — Q.X.Y sub-sprint discipline.
  - `nelinho-tdd` — RED-GREEN-REFACTOR + FakeSession + property tests Spelke.
  - `nelinho-debug` — symptom→cause→recovery table (UndefinedTable, pgvector, Ollama, etc.).
  - `nelinho-frontend` — ZERO MOCKS, dark theme, RegrasPage composition pattern.
  - `nelinho-review` — 9-section pre-merge gate.
- **`agent_docs/`** — reference material, lê on demand:
  - [architecture.md](agent_docs/architecture.md) — module map + deploy topology + 17 módulos
  - [spelke_axioms.md](agent_docs/spelke_axioms.md) — 7 invariants em detalhe
  - [q17_logic_as_data.md](agent_docs/q17_logic_as_data.md) — 12 events × 9 actions × 8 ops + ACTION_WIRING
  - [bootstrap_recovery.md](agent_docs/bootstrap_recovery.md) — DB drop+recreate cycle, pgvector skip
  - [sprint_history.md](agent_docs/sprint_history.md) — Q.X status (substitui CLAUDE_1.md)
  - [domain_glossary.md](agent_docs/domain_glossary.md) — fases, cura/secagem, retrabalho rates, CoeficienteX
- **`.claude/plans/plano-diz-c-digo-scalable-minsky.md`** — plano vivo (audits + Q.13→Q.18 roadmap).
- **`PP1_NELO_PLANO_v4.md`** — visão original do produto (referência histórica, não actualizada).
- **`CLAUDE_1.md`** — stale, anterior a este ficheiro (Q.1-Q.6 only). Não usar.

---

## Conditional gotchas

<important if="touching CPO scheduler, decoder, fitness, safety_net, chromosome, or workforce assignment">
- Os 7 Spelke axioms aplicam-se. Lê [agent_docs/spelke_axioms.md](agent_docs/spelke_axioms.md).
- Property tests vivem em `tests/plan/test_preview_delta_property.py` (4 hypothesis props).
  Adicionar property test para qualquer novo invariant — não basta example tests.
- `CoeficienteX` é DINHEIRO. Se tocares em `pair_assignment.py` ou `fitness.py`, grep
  `coeficiente` antes de submeter — zero matches em src/plan/cpo/.
- Tempos vêm SEMPRE do histórico real (`FaseOf_Inicio→FaseOf_Fim`, limpos: remover zeros →
  remover >P95 → moda dos limpos → fallback mediana ≠0). Nunca usar coeficientes standard
  (divergem até 25× do real).
- Cura/secagem: 16 transições min_gap_hours em `state.py:33` `NELO_CURING_GAPS_SEED`. Não são
  filas — são química.
</important>

<important if="modifying src/governance/yaml_policy/ or frontend RegrasPage.tsx">
- DSL é **closed whitelist**: 12 events × 9 actions × 8 ops × 7 axioms. LLM nunca emite fora dos
  enums (Pydantic `Literal[...]` enforcement).
- `safety.requires_human_approval` é `Literal[True]`. `safety.kill_switch` é `Literal["admin_only"]`.
  LLM não pode opt-out destas duas.
- ACTION_WIRING matrix em `dispatchers.py` é mirrored no frontend `RegrasPage.tsx` `WIRED:` map.
  Quando flipares `wired=False→True` num lado, **flipar no outro também**. Test assertion:
  `test_action_wiring_matrix_has_entry_per_action_type`.
- Dispatcher reportar `status="ok"` quando `wired=False` é o bug Q.17.F.1 risk #5 — o mais
  trust-breaking que tivemos. Usa `_stubbed_or_ok()` helper, nunca string literal.
- Detalhes completos em [agent_docs/q17_logic_as_data.md](agent_docs/q17_logic_as_data.md).
</important>

<important if="editing frontend/src/">
- ZERO MOCKS sweep ANTES de submit:
  ```
  rg --type-add "tsx:*.tsx" --type tsx "const MOCK_" frontend/src/   # zero
  rg "data \|\| \[" frontend/src/pages/                              # zero
  ```
- `<input bg-white>` sem text color = bug Q.18.UX_FIX (texto branco em fundo branco). Sempre
  `text-slate-900 placeholder:text-slate-400`.
- DarkBadge variants permitidos: `success/warning/danger/info/neutral/accent/primary/teal`.
  NÃO `green/yellow/red/blue/gray` (TS error).
- Lazy-load todas as pages em App.tsx: `const Page = lazy(() => import(...))` + `<Suspense>`.
- Mutations invalidam queries: `queryClient.invalidateQueries({ queryKey: [...] })` após cada
  POST/PATCH/DELETE.
- RegrasPage.tsx é a referência de composição (split-pane + diff modal). Reutiliza para qualquer
  admin page nova.
</important>

<important if="seeing UndefinedTable, DuplicateObject, or InvalidSchemaName errors">
- O `init_db()` em `src/shared/database.py:198` faz `Base.metadata.create_all` — só cria tabelas
  para modelos que foram **importados no momento**. Modelos não importados nunca criam tabelas.
- Recovery canónica: drop DB + recriar + `bootstrap_dev_full.py`. Detalhes em
  [agent_docs/bootstrap_recovery.md](agent_docs/bootstrap_recovery.md). Não tentar surgical
  schema fixes — não são reproduzíveis.
- pgvector NÃO está disponível no scoop postgres 18 por default. Migration 008 tem graceful skip
  via `pg_available_extensions`. O `bootstrap_dev_full.py` exclui a tabela `copilot_rag_chunk`.
</important>

<important if="writing or modifying tests">
- `pytest.ini` tem `asyncio_mode=auto`. Marca tests async com `@pytest.mark.asyncio`.
- Models governance usam Postgres-only (JSONB, schemas) → SQLite não serve. Reutiliza
  `_FakeSession` de `tests/governance/test_yaml_rule_service_q17c.py`.
- Tests para Spelke invariants → usar `hypothesis`, não example tests. 4 props em
  `tests/plan/test_preview_delta_property.py`.
- DAMP > DRY em testes. Cada teste lê como spec independente. Não extrair helpers só para
  poupar 5 linhas.
- `Ollama / Kafka / CPO real` mocked por `AsyncMock` em unit tests; integration tests usam
  fixtures Excel-derivadas.
- Zero `@pytest.mark.skip` ou `xfail` sem GH issue linkada. Testes desligados rotam.
</important>

<important if="committing changes">
- Title prefix: `Q.X.Y` (ou `BUGFIX:`, `DOCS:`, `REFACTOR:`).
- Title ≤ 72 chars; body explica WHY, diff já mostra WHAT.
- Trailer obrigatório: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- Single logical change. Refactor + feature no mesmo commit = split.
- ANTES de commit corre o gate `nelinho-review` (9 secções). Se algo é "no", não está feito.
</important>

<important if="touching authentication or routing or RBAC">
- Tenant header `X-Tenant-Id` é obrigatório em quase todos os endpoints (`require_tenant_header`).
  Zero UUID (`00000000-0000-0000-0000-000000000000`) é **rejeitado por design** (Q.12 Onda 0.1).
  Dev tenant é `00000000-0000-0000-0000-000000000001`.
- Frontend `lib/api.ts:128` + `CapabilitiesProvider.tsx:121` usam `…001` por default.
- RBAC matrix em `src/shared/auth/rbac.py:ROUTE_PREFIX_REQUIREMENTS`. Quando adicionares route
  com write semantics, pensar se precisa role-guard.
</important>

---

*This file is intentionally short. Boris (Anthropic): "every line in CLAUDE.md affects 1000 future
prompts — write fewer, better lines." Karpathy: "surface assumptions, prefer the smallest change."
HumanLayer: "progressive disclosure beats monolithic config." When in doubt, link to a skill or
to `agent_docs/`. Don't repeat content here.*
