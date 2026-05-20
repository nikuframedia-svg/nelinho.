# CLAUDE.md — nelinho

**ProdPlan ONE / nelinho** — APS+ML+LLM on-prem para a NELO (Mar Kayaks, Vila do Conde): ~14.7
barcos/dia, 41 fases, 510 moldes, 122 operadores, 61 padrões de routing. Meta €30-35K/dia.

**Stack:** Python 3.11 + FastAPI + SQLAlchemy 2.0 async + Postgres 16 + React 19 + Vite +
TanStack Query + Tailwind + Ollama. Native deploy (sem Docker) + systemd. LAN access via browser.

**Owner:** Luis (luis@nikufra.ai). PT-PT informal, respostas curtas, números concretos.

## Always-true invariants (apply everywhere)

1. **ZERO MOCKS no frontend** — nunca `const MOCK_X`, nunca `data ?? [{...}]` fallback.
2. **PT-PT, não PT-BR** (utilizador, tu, camião, registo, gerir, fase).
3. **7 axiomas Spelke imovíveis** — ver [agent_docs/spelke_axioms.md](agent_docs/spelke_axioms.md).
4. **Q.17 rules `requires_human_approval=True`** (Pydantic `Literal[True]`); kill_switch admin-SQL-only.
5. **CoeficienteX é DINHEIRO €** — usar em `src/profit/`, NUNCA em `src/plan/cpo/*`.
6. **Sub-sprint Q.X.Y format** — 1 sub-sprint = 1 commit lógico, pytest verde + demo.
7. **Audit trail intact** — cada mudança de estado escreve `audit_log` na mesma tx
   (Q.61.18 `governance/audit_service.audit_change`).

## How to verify

```powershell
pwsh scripts/verify.ps1                   # gate completo (~60s)
pwsh scripts/verify.ps1 -QuickPython      # sem canary (~10s, frontend só)
```

Detalhes: [agent_docs/architecture.md](agent_docs/architecture.md).

## Where to look

- **`.claude/skills/`** — 7 skills auto-loaded (discipline, incremental, tdd, debug, frontend,
  review, invariants).
- **`agent_docs/`** — referência on-demand: `architecture`, `spelke_axioms`, `q17_logic_as_data`,
  `bootstrap_recovery`, `sprint_history`, `domain_glossary`.
- **Planos vivos:** `.claude/plans/trust-index-v1-indexed-token.md` (Q.61).

## Conditional gotchas

<important if="touching CPO scheduler, decoder, fitness, safety_net, chromosome, or workforce assignment">
7 axiomas Spelke aplicam-se. Property tests em `tests/plan/test_preview_delta_property.py`
(adicionar property test para qualquer novo invariant). CoeficienteX NUNCA em `src/plan/cpo/`.
Tempos vêm SEMPRE do histórico real (`FaseOf_Inicio→FaseOf_Fim`, limpos). Cura/secagem: 16
transições em `state.py:NELO_CURING_GAPS_SEED` — química, não filas.
</important>

<important if="modifying src/governance/yaml_policy/ or frontend RegrasPage.tsx">
Closed whitelist: 12 events × 9 actions × 8 ops × 7 axiomas. `safety.requires_human_approval` é
`Literal[True]`, `kill_switch` é `Literal["admin_only"]` — LLM nunca opt-out. `ACTION_WIRING` em
`dispatchers.py` é mirrored em `frontend/src/components/regras/ruleHelpers.ts` (Q.61.04 test
`test_action_wiring_roundtrip_q61_04`). Dispatcher usa `_stubbed_or_ok()`, nunca string literal.
</important>

<important if="editing frontend/src/">
`pwsh scripts/verify.ps1` corre todos os gates. Inputs `<input bg-white>` sempre com
`text-slate-900 placeholder:text-slate-400`. DarkBadge variants:
`success/warning/danger/info/neutral/accent/primary/teal`. Mutations: `queryClient.invalidate
Queries({queryKey: [...]})` após cada POST/PATCH/DELETE. Query-key factories em
`lib/api/keys.ts` (Q.61.27). Lib API: `lib/api/client.ts` injecta tenant + trace_id (Q.61.12).
</important>

<important if="seeing UndefinedTable, DuplicateObject, or InvalidSchemaName errors">
Q.61.16: produção corre `alembic upgrade head` ANTES do uvicorn; `init_db()` só verifica
revision. Para dev/tests: `init_db_create_all()`. Recovery canónica: drop DB + recriar +
`scripts/bootstrap_dev_full.py`. Modelos consolidados em `src/shared/model_registry.py`
(Q.61.14). pgvector skip em dev: `bootstrap_dev_full.py` exclui `copilot_rag_chunk`.
</important>

<important if="writing or modifying tests">
`pytest.ini` tem `asyncio_mode=auto`. Marca async com `@pytest.mark.asyncio`. FakeSession
canónica em `tests/conftest.py` (Q.61.02); subclasse `FakeRuleSession` para yaml_policy.
Property tests Spelke via `hypothesis`. DAMP > DRY — cada teste lê como spec independente.
Zero `@pytest.mark.skip`/`xfail` sem GH issue. `verify_invariants.py` tem AST scan que falha
o CI se um `def test_*: pass` for adicionado (Q.61.01).
</important>

<important if="committing changes">
Title `Q.X.Y` (ou `BUGFIX:`/`DOCS:`/`REFACTOR:`), ≤72 chars; body explica WHY.
Trailer obrigatório: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
1 commit = 1 mudança lógica. Antes do push: `pwsh scripts/verify.ps1`.
</important>

<important if="touching authentication or routing or RBAC">
`X-Tenant-Id` obrigatório (`require_tenant_header`); zero UUID rejeitado (Q.12 Onda 0.1).
Dev tenant `00000000-0000-0000-0000-000000000001`. Frontend `lib/api/client.ts` injecta
tenant + user + `X-Request-Id` (Q.61.12 trace_id). RBAC em
`src/shared/auth/rbac.py:ROUTE_PREFIX_REQUIREMENTS`. SoD em propose+approve (Q.61.09).
</important>

---

*CLAUDE.md é carregado em todas as sessões — cada linha afecta milhares de prompts. Detalhes
em skills + `agent_docs/`. Karpathy: "surface assumptions, prefer the smallest change."*
