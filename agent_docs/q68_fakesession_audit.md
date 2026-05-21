# Q.68.3.1 — FakeSession audit (40 unique variants)

> **Branch:** `feat/q60-qualidade-agentes` · **Auditoria base:** 5.8/10
> · **Promessa Q.61.02 incumprida:** 1 canónico → 40 cópias distintas.

## Sumário executivo

`grep "class _FakeSession|class FakeSession" tests/` devolve **41 hits** em 40
ficheiros (`test_reichenbach_q15d3.py` declara 3 fakes locais dentro de funções
de teste). Há **2 canónicos paralelos**:

1. `tests/conftest.py:52` — `FakeSession` (queue-based) + `FakeRuleSession`
   (typed-stash, Q.61.02). Surface mais completa (execute, scalars/all,
   scalar_one_or_none, add, delete, flush, commit, rollback, refresh,
   begin_nested).
2. `tests/reports/conftest.py:40` — `FakeSession` (typed-by-table, dispatch
   por substring no SQL compilado). Specializada em `reports.*`.

Tudo o resto (38 ficheiros) é redundante, drift acumulado, e impede que uma
mudança de surface (ex: adicionar `begin_nested`) propague.

---

## Canónico actual — `tests/conftest.py`

### `FakeSession` (queue-based, linha 52-115)

- **Estado interno:** `added: List`, `deleted: List`, `_scalar_queue`,
  `_scalars_queue`, contadores `flush_calls/commit_calls/rollback_calls/refresh_calls`.
- **API pública:** `queue_scalar(v)`, `queue_scalars([v…])`, `add`, `delete`,
  `flush`, `commit`, `rollback`, `refresh`, `begin_nested`, `execute`.
- **Result wrappers:** `_FakeResult` (scalar/scalar_one_or_none/scalars().all()/.first())
  + `_FakeScalars`.
- **Limitações:** ordem dos `execute()` tem de bater certo com a ordem das
  filas; não inspecciona o SQL — testes têm de orquestrar a sequência.

### `FakeRuleSession(FakeSession)` (typed-stash, linha 205-253)

- Extende com colecções tipadas `rules: List`, `revisions: List`.
- `execute()` inspecciona `str(stmt.compile(...))` e dispatch por
  `FROM governance.yaml_policy_rule_revision` / `FROM governance.yaml_policy_rule`.
- Cai para `super().execute()` (queue) em statements desconhecidos.

### Surface coverage matrix (canónico)

| Método             | FakeSession | FakeRuleSession |
|--------------------|:-----------:|:---------------:|
| `add`              | yes         | yes (typed)     |
| `delete`           | yes         |                 |
| `flush`            | yes         | yes (uuid fill) |
| `commit`           | yes         |                 |
| `rollback`         | yes         |                 |
| `refresh`          | yes         |                 |
| `begin_nested`     | yes         |                 |
| `execute` (queue)  | yes         |                 |
| `execute` (typed)  |             | yes (SQL sniff) |
| `scalar`/`scalar_one_or_none` | yes |                 |
| `scalars().all()`  | yes         |                 |
| `scalars().first()`| yes         |                 |
| `get(model, pk)`   | **missing** |                 |

> **Gap conhecido:** `await session.get(Model, pk)` não está no canónico;
> múltiplos variants DOMAIN reintroduzem-no.

---

## Os 40 variants

### Categoria **TRIVIAL — 11 ficheiros**

Apenas dispatch escalar/scalars; sem inspecção de SQL; podem
trocar `class _FakeSession:` por `from tests.conftest import FakeSession`
(com `queue_scalar`/`queue_scalars` ou subclasse 4-linhas).

| # | File:line | Differences vs canónico | Strategy |
|---|---|---|---|
| 1 | `tests/quality/test_mold_quality_q54s.py:28` | `_R().all()` ad-hoc; rows pré-fixadas | `queue_scalars(rows)` |
| 2 | `tests/improve/test_adoption_signal_q13d.py:32` | Inspecciona `whereclause` para filtrar `action_type`/`tenant_id` | Pre-filter em Python + `queue_scalars` |
| 3 | `tests/explain/diagnostics/test_repository_q15d0.py:47` | Queue de `_FakeResult` posicional (não scalar+scalars) | Já idêntico — só renomear |
| 4 | `tests/explain/diagnostics/test_reichenbach_q15d3.py:281,294,305` (3×) | Inline-em-função, `execute` raise/no-op | Inline `MagicMock(spec=...)` |
| 5 | `tests/copilot/test_user_feedback_q31h.py:27` | `add()` + `commit()` apenas | `FakeSession()` directo |
| 6 | `tests/copilot/test_causal_audit.py:45` | Add + queue rows | `FakeSession()` + `queue_scalars` |
| 7 | `tests/copilot/test_causal_audit_endpoint_q13g.py:61` | `add()` + `commit()` | `FakeSession()` |
| 8 | `tests/copilot/test_causal_discovery_persist_q13d.py:39` | Só `add()` | `FakeSession()` |
| 9 | `tests/copilot/test_causal_runtime_q13d.py:56` | `add()` com flag `add_should_raise` | `FakeSession` + monkeypatch `add` |
| 10 | `tests/adapters/nelo/etl/test_runner.py:185` | `add()` + `flush()` apenas | `FakeSession()` |
| 11 | `tests/factory_data_product/test_drift_bridge.py:85` | `add()` + `flush()` | `FakeSession()` |
| 12 | `tests/plan/test_sprint_c_wire_pricing.py:46` | `execute()` devolve tuples (`.all()`) | `queue_scalars(rows)` |
| 13 | `tests/profit/test_kpi_explanations_q22b.py:51` | Empty `_FakeResult` (scalars/scalar) | `FakeSession()` |
| 14 | `tests/profit/test_material_cost_service_q26b.py:35` | Rows tuple-list | `queue_scalars` |
| 15 | `tests/profit/test_labor_cost_service_q26c.py:88` | Rows canned | `queue_scalars` |
| 16 | `tests/governance/test_dpo_dataset_builder.py:80` | Commits via `scalars().all()` | `queue_scalars(commits)` |

> Total TRIVIAL: **15 sites** em 13 ficheiros (`reichenbach` contribui 3).

### Categoria **DOMAIN — 14 ficheiros** (extend canónico)

Adicionam lógica específica que o canónico não cobre (SQL introspection,
multi-batch queues, `get()`, dispatch por entidade ORM).

| # | File:line | Domain-specific behaviour | Strategy |
|---|---|---|---|
| 1 | `tests/governance/test_preference_rules_api.py:68` | Inspecciona `stmt.compile().params` para detectar `rule_id` vs lista; "ghost id" detection | Subclasse `FakeRuleSession` com `_extract_id` mixin |
| 2 | `tests/governance/test_rule_firing_endpoint_q14a.py:51` | Walk `whereclause` (operator.eq/ge/lt) + filter rows + ordering | Promover `_flatten_clauses` para `tests/_fake_session_filters.py` |
| 3 | `tests/governance/test_preference_detector.py:67` | Dispatch por `entity` em `column_descriptions[0]` (commits vs rules) | Adicionar `register_entity(cls, rows)` ao canónico |
| 4 | `tests/governance/test_learning_metrics.py:40` | Queue de **batches** (lista de listas) | Adicionar `queue_batch(batches)` ao canónico |
| 5 | `tests/governance/test_adaptive_weights.py:45` | Always-returns-same set; `add`/`flush` | Já cobrível por canónico |
| 6 | `tests/governance/test_ab_framework_q14c.py:263` | `execute` retorna `_FakeResult(None)`; `commit` flag | Já cobrível |
| 7 | `tests/plan/test_worker_operations_endpoint.py:76` | Params introspection (UUIDs + dates) + sort | Promover utilitário `params_introspect()` |
| 8 | `tests/plan/test_operation_complete_endpoint.py:61` | Params introspection + `flush`/`commit` | Idem |
| 9 | `tests/plan/test_cpo_commit_orders_q54d.py:247` | **Multi-call sequence:** 1º execute=commit, 2º=orders, 3º=employees | `queue_scalars` triplo já cobre |
| 10 | `tests/plan/test_order_status_q54b.py:127` | Orders + `add` audit + `commit` | Cobrível |
| 11 | `tests/plan/test_mold_maintenance_list_q31b.py:21` | Apenas rows fixos via scalars().all() | TRIVIAL na verdade |
| 12 | `tests/plan/test_co1_decision_recording.py:52` | **`get(model, pk)`** + `flush_calls` | Adicionar `get()` ao canónico (gap!) |
| 13 | `tests/search/test_global_search_q31f.py:26` | Dispatch por `column_descriptions[0]["entity"]` | Promover `register_entity` |
| 14 | `tests/shared/test_auth_me_q22a.py:49` | Single-row + cross-tenant filter check | Subclasse 5 linhas |
| 15 | `tests/shared/test_auth_login_q31g.py:39` | Params introspection (uuids+strs) | Promover utilitário |
| 16 | `tests/copilot/test_copilot_api_characterization_q66_d.py:105` | **Surface mais larga do projecto:** `stub_get`/`stub_execute`, id auto-fill, `created_at` auto, rollback flag | Manter como subclasse `FakeCharacterizationSession` |
| 17 | `tests/shared/test_record_rule_firing_q14a.py:50` | `existing_for_dedupe`, `_patch_session` (monkeypatch `get_session_context`) | Cobrível com `queue_scalar` + helper |
| 18 | `tests/ml/test_quality_risk_job_q68_5b.py:37` | Apenas commits/rollbacks counter — sem execute | TRIVIAL |
| 19 | `tests/shared/test_outbox_backoff_q66_e.py:69` | Capture `stmt` para asserts + `add`/commit | Cobrível |
| 20 | `tests/profit/test_bonus_payout_service_q13e.py:52` | Walk where clauses + sort por `valid_from desc` + limit 1 | Promover utilitário |
| 21 | `tests/workforce/test_recency_filter_q13e.py:38` | `raise_on_execute` flag + `executed` counter | Cobrível com helper |

> Total DOMAIN: **~21 sites**; **~9** podem ser TRIVIAL com 1 helper (`queue_scalars`,
> `register_entity`).

### Categoria **PROTOCOL — 0 ficheiros**

Nenhum dos 40 usa um protocolo não-SQLA (Redis-backed, gRPC). Todos
estão dentro do mesmo paradigma `AsyncSession`.

### Categoria **LEGACY — 2 ficheiros (canónico paralelo)**

| File | Why | Action |
|---|---|---|
| `tests/reports/conftest.py:40` (`FakeSession`) | Pre-Q.61.02 — typed-by-table dispatch específico de `reports.*` | Mover lógica `gen_rows[fragment]` para utilitário; promover a subclasse `FakeReportsSession(FakeSession)` |

---

## Plano de migração (4 fases sequenciais)

### Fase A — Q.68.3.2 (Promover canónico)

**Touch:** `tests/conftest.py` (+~120 LOC).

Adições ao canónico:

1. `async def get(self, model, pk)` — devolve `_get_stash.get((model, pk))`
   (resolve o gap usado por `test_co1_decision_recording.py` e
   `test_copilot_api_characterization_q66_d.py`).
2. `register_entity(cls, rows: List)` + dispatch em `execute()` por
   `stmt.column_descriptions[0]["entity"]` (resolve 4 variants).
3. `queue_batch(batches: List[List])` — multi-call sequência (resolve
   `learning_metrics`, `cpo_commit_orders`).
4. `add_should_raise: bool` + `raise_on_execute: bool` flags
   (resolve 3 variants).
5. Promover utilitários para `tests/_fake_session_helpers.py`:
   - `extract_uuid_params(stmt)`
   - `flatten_where_clauses(stmt)`
   - `inspect_compile_params(stmt)`

**Risco:** 0 mudança comportamental — só novos features opt-in.

### Fase B — Q.68.3.3 (Migrar TRIVIAL = 13 ficheiros)

**Touch:** ~13 ficheiros tests; LOC tocadas **~−320 LOC** (cada variant
remove ~25 LOC de boilerplate; +1 linha `from tests.conftest import FakeSession`).

Comando-template por ficheiro:
```python
# antes
class _FakeSession:
    async def execute(self, _stmt): return _R(...)
# depois
from tests.conftest import FakeSession
session = FakeSession(); session.queue_scalars(rows)
```

**Risco:** Baixo — execute() shape idêntico. Verificar com `pytest tests/<file>` por ficheiro.

### Fase C — Q.68.3.4 (Migrar DOMAIN = 14 ficheiros)

**Touch:** ~14 ficheiros tests; LOC tocadas **~−600 LOC** (extends mais
substanciais). Cada variant vira ≤10 linhas de subclasse local.

Padrão-template:
```python
from tests.conftest import FakeSession
from tests._fake_session_helpers import flatten_where_clauses

class _LocalSession(FakeSession):
    def __init__(self, rules):
        super().__init__()
        self.register_entity(PreferenceRule, rules)
```

**Risco:** Médio — `test_preference_rules_api.py` (`_extract_rule_id_from_stmt`)
e `test_rule_firing_endpoint_q14a.py` (operator.eq/ge/lt) têm lógica
intrincada. Migrar último e validar com `pytest -k governance` antes de
commit.

### Fase D — Q.68.3.5 (Drift gate)

**Touch:** `scripts/verify_invariants.py` (+15 LOC).

Adicionar AST scan:
```python
INVARIANT["Q68_3_fakesession_local_definitions"] = {
    "baseline": 1,   # apenas conftest.py + reports/conftest.py
    "pattern": r"class\s+(_)?FakeSession\b",
    "scope": "tests/**/*.py",
    "excludes": ["tests/conftest.py", "tests/reports/conftest.py",
                 "tests/_fake_session_helpers.py"],
}
```

**Risco:** 0 — gate apenas trava regressão.

---

## LOC tocadas estimadas (totais)

| Fase | Ficheiros | LOC added | LOC removed | Net |
|---|---|---|---|---|
| A — promover canónico | 2 | +180 | 0 | +180 |
| B — TRIVIAL | 13 | +30 | −320 | −290 |
| C — DOMAIN | 14 | +110 | −600 | −490 |
| D — drift gate | 1 | +15 | 0 | +15 |
| **Total** | **30** | **+335** | **−920** | **−585** |

---

## Risco identificado

1. **`test_preference_rules_api.py`** tem 80 linhas de SQL introspection
   muito específica (ghost-id detection). Migração pode quebrar 8 tests
   da governance. **Mitigação:** manter helpers `_extract_rule_id_from_stmt`
   e `_stmt_has_ghost_id` como módulo-privado do test, só extrair `FakeSession` base.

2. **`tests/reports/conftest.py`** é canónico paralelo com 67 testes a
   depender dele. **Mitigação:** Fase A mantém-no intacto; Fase C considera
   refactor opcional para subclasse.

3. **`test_copilot_api_characterization_q66_d.py`** tem a surface mais
   larga (Q.66 D acabou de o decompor — characterization test). **Mitigação:**
   manter como subclasse `FakeCharacterizationSession` documentada,
   sem inline.

4. **3 `_FakeSession` inline em `test_reichenbach_q15d3.py`** (linhas 281/294/305)
   são minúsculos (1-2 linhas execute()) — substituir por `MagicMock(spec=AsyncSession)`
   é mais barato do que subclassear.

---

*Audit gerado: Q.68.3.1. Próximo: Q.68.3.2 — promover canónico (touch
`tests/conftest.py` + `tests/_fake_session_helpers.py`).*
