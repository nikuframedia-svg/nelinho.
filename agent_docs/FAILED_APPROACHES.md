# FAILED APPROACHES

Things we tried that DIDN'T work. Save future-self (and future maintainer)
the hours of repeating them.

Format per entry:
- **Approach:** what we tried.
- **When:** Q.X.Y or date.
- **Why it failed:** root cause.
- **What works instead:** the right pattern.

---

## 1. Sub-agent worktrees for parallel work

**Approach:** Spawn Agent with `isolation: "worktree"` to parallelize work on isolated branch copies.

**When:** explored across Q.61 + Q.62 sessions.

**Why it failed:** worktree gives sub-agents a stale base — modifications made in the main checkout during the agent's run don't reflect, and the agent commits against an outdated tree. Memory: `agent_worktree_unreliable.md`.

**What works instead:** run sub-agents sequentially in the main checkout. For true parallelism use single-message multi-Agent calls with **pre-verified disjoint touch maps** (Q.65 lesson — 5 agents in ~6 min wall-clock, zero file collisions, vs ~9h sequential).

---

## 2. Alembic + create_all hybrid in production

**Approach:** `init_db()` ran `Base.metadata.create_all()` on startup, in parallel with Alembic migrations. Models added without a migration would still get tables.

**When:** until Q.61.16.

**Why it failed:** new models without migrations were silently created in dev; production via `alembic upgrade head` left them orphaned. ~21 tables drifted between `env.py` import list and what `create_all()` actually built. Memory: `project_alembic_create_all_legacy.md`.

**What works instead:** Q.61.14 introduced `src/shared/model_registry.py` as single source of truth (used by both `alembic/env.py` and `bootstrap_dev_full.py`). Q.61.16 made `init_db()` verify there is a current Alembic revision and crash early on schema desync. `init_db_create_all()` is reserved for tests/dev fixtures only. Q.61.17 added a CI job that runs `alembic upgrade head` + `alembic check` to fail builds when a model is added without a migration.

---

## 3. pgvector in scoop Postgres 18 dev

**Approach:** assume pgvector is available by default; let migration 008 (`copilot_rag_chunk` with `vector(...)` column) just run.

**When:** initial Q.18.BOOTSTRAP attempts.

**Why it failed:** scoop Postgres 18 doesn't ship pgvector. Migration 008 crashed with `extension "vector" is not available`.

**What works instead:** `bootstrap_dev_full.py` skips `copilot_rag_chunk`; migration 008 has a graceful skip via `pg_available_extensions`. RAG features are disabled in dev. Production installs pgvector explicitly. See `agent_docs/bootstrap_recovery.md`.

---

## 4. Surgical schema fixes on a broken dev DB

**Approach:** when a migration failed mid-way (DuplicateObject, UndefinedTable, ENUM type already exists), patch the DB by hand with ad-hoc SQL or edit the failed migration.

**When:** several times during Q.18 and Q.61.15.

**Why it failed:** non-reproducible. Editing migration history breaks `alembic upgrade head` for the next dev. Hand-patched dev DBs have state nobody else can recreate.

**What works instead:** **drop database + recreate + `bootstrap_dev_full.py`** (5 min, idempotent). Canonical recovery in `agent_docs/bootstrap_recovery.md`. If a migration is wrong, fix the model and generate a new migration on top — never edit history.

---

## 5. Mega-consolidate Alembic migration via autogenerate

**Approach:** drop dev DB + `alembic upgrade head` + `alembic check` to identify drift between `Base.metadata` and migrations, then let autogenerate emit a consolidate migration.

**When:** Q.61.15 attempted in a single session.

**Why it failed:** (a) the migration chain broke at 027 because earlier nodes (governance.approval, factory_meta.*) only existed via `create_all()`, skipped by Alembic. (b) `alembic check` after `stamp head` reported 95 tables + 249 indexes + 3 columns of drift — autogenerate emitted `drop_table` for all of them (catastrophic if applied). (c) Migrations 015 and 018b had latent bugs (missing `CREATE SCHEMA plan`, `sa.Enum` vs `postgresql.ENUM`).

**What works instead:** Q.62.A.1/A.2/A.3 broke the work into 3 sub-sprints: 028a (governance orphan tables), 028b (factory_meta tables), 055a (13 remaining orphans using `Base.metadata.tables[k].create(checkfirst=True)` — idempotent, single source of truth). Plus inline fixes to 015/018b/036/040. Result: `alembic upgrade head` on a fresh DB reaches HEAD with 106 tables. Estimated 1-2 dedicated sessions, not 2h.

---

## 6. Synchronous Kafka publish inside request transactions

**Approach:** `propose_decision()` called `await publish_event(...)` synchronously inside the request handler.

**When:** until Q.61.11.

**Why it failed:** if the Kafka broker was down or slow, the request blocked for ~30s before timing out. Tail latency was unbounded by an external system.

**What works instead:** Q.61.11 switched to the outbox pattern. `propose_decision` writes an `EventOutbox` row in the same transaction as the state change (preserving audit invariant 7). A background dispatcher (`outbox_dispatcher.py`) drains the outbox with retry + DLQ + `SKIP LOCKED`. Q.61.34 added `GET /v1/outbox/status` for observability (`oldest_pending_age_seconds` alarm).

---

## 7. Dispatcher reporting `status="ok"` when wired=False

**Approach:** generic dispatch helper returned `"ok"` as a literal string whether the action was wired or not.

**When:** discovered Q.17.F.1; pinned by property test in Q.61.03.

**Why it failed:** the most trust-breaking bug we had — rules appeared to fire successfully but did nothing. Hard to detect via tests because the API contract still looked healthy.

**What works instead:** `_stubbed_or_ok()` helper that returns `"ok"` only when both `wired=True` AND a callback was registered. Property test `test_dispatcher_wired_property_q61_03.py` pins the invariant across all 9 actions × 4 combinations × 100+ Hypothesis examples. Backend/frontend ACTION_WIRING matrices have a roundtrip test (Q.61.04).

---

## 8. Mass `# noqa: BLE001` to silence ruff

**Approach:** when ruff added `BLE001` (blind-except) and we had 370 sites, add `# noqa` to every site in one sweep.

**When:** considered in Q.61.06.

**Why it failed:** orthogonal damage. Mass `# noqa` hides legitimate future regressions and adds churn unrelated to any feature.

**What works instead:** `scripts/lint_drift_gate.py` with a baseline in `scripts/lint_baseline.json` — CI fails if the BLE001 count rises above baseline. Existing 370 sites grandfathered; touched-file pays the reduction. Same pattern for `Q61_07_no_direct_fetch` (50 baseline), `Q61_28_any_annotation` (272 baseline).

---

## 9. Trusting overnight audit reports without verification

**Approach:** when an automated overnight audit flagged "dashboard/LiveBadge is a duplicate of dark/LiveBadge" or "aprendizagem/ folder is dead", just delete or refactor based on the report.

**When:** several Q.61.23–Q.61.33 sub-sprints reported as "no-fix" after investigation.

**Why it failed:** audits used grep-level heuristics that missed semantic differences (LiveBadge — one is a `RealtimeProvider` status indicator, the other a static pill). Folder names typed wrong (`aprendizagem` vs `aprendi`). 4 of 5 "suspicious satellites" were live (routers mounted in main.py).

**What works instead:** every audit finding gets a manual `rg` for importers + a read of the actual code before any delete. Sub-sprints document `(no-fix)` outcomes in `sprint_history.md` with the reason, so we don't re-investigate next quarter.
