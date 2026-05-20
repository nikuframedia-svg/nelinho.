# SUCCESSION

Single-owner project (Luis Nuno Santos, luis@nikufra.ai). Bus factor reality: 96% of commits are the owner's. If Luis disappears for 90+ days, this file is how the project continues.

## Entry point — first thing a successor does

1. `cd C:\Users\User\nelinho` (Windows dev box) or clone the repo wherever.
2. `git log --oneline -20` to see recent state.
3. Read `agent_docs/sprint_history.md` — 1-pager roadmap covering Q.1 through Q.65.
4. Read `CLAUDE.md` (94 lines) for project DNA + invariants + verify commands.
5. `pwsh scripts/verify.ps1` — one-command gate: ruff + canary pytest + invariants + lint drift + tsc + vitest + lint:mocks. Backend-only ~5s, full ~60s.
6. `ls .claude/skills/` — 7 skills auto-loaded by Claude Code (discipline, incremental, tdd, debug, frontend, review, invariants). These ARE the project's tribal knowledge.

If `scripts/verify.ps1` is green, the codebase is in a known-good state. If not, see `agent_docs/bootstrap_recovery.md` for the drop+recreate+bootstrap cycle.

## Brain externalization

Claude Code acts as a **secondary owner** of this project. It is useful because:
- `CLAUDE.md` root has invariants + where-to-look + verify commands.
- `.claude/skills/` (7 SKILL.md files) cover TDD, debug, frontend, review, invariants, discipline, incremental sub-sprints — each loaded automatically when relevant.
- `agent_docs/*.md` (architecture, spelke_axioms, q17_logic_as_data, bootstrap_recovery, domain_glossary, sprint_history, mar_kayaks_schema_discovery, nelo_executive_summary, mutmut_target, FAILED_APPROACHES, SUCCESSION) are reference material loaded on demand.
- Q.X.Y commit discipline means `git log --oneline` reads as a roadmap. Each commit's body explains WHY.
- Memory in `~/.claude/projects/C--Users-User-nelinho/memory/MEMORY.md` keeps cross-session context (project goals, decisions, lessons).

A new maintainer who reads `CLAUDE.md` + `sprint_history.md` + runs `verify.ps1` has 80% of what they need in under 30 minutes.

## The 7 Spelke axioms — permanent invariants

These never move. Touching the CPO scheduler, decoder, fitness, safety_net, chromosome, or workforce assignment requires preserving all 7. Property tests in `tests/plan/test_preview_delta_property.py`.

1. **Capacity ≥ 0** — no workcenter overload.
2. **Precedence monotonic** — BOM phase order (Cura always after Laminagem, never inverted).
3. **Mold exclusivity** — one 1-pocket mold ≠ two boats at the same slot.
4. **Dual-resource Laminagem** — pair preferred 88.5% (real history). Laminagem Infusão is a different process.
5. **Skill match** — operator must be in `FuncionariosFasesAptos`. No "learn on the job" in the scheduler.
6. **Curing/drying min_gap_hours** — 16 chemical transitions in `NELO_CURING_GAPS_SEED`. Not queues — real chemistry.
7. **Safety net** — CPO never returns a schedule worse than the heuristic baseline.

Full detail in `agent_docs/spelke_axioms.md`. Verify with `pwsh scripts/verify.ps1` or `pytest tests/plan/test_preview_delta_property.py -v`.

## Critical domain

**NELO** = Mar Kayaks, Vila do Conde. Competition kayaks (K1/K2/K4 + recreation). Production target: ~14.7 boats/day, €30-35K/day. Plant: 41 phases, 510 molds, 122 active operators, 61 routing patterns. PCs/tablets on the factory floor browse the local network deployment.

- `agent_docs/domain_glossary.md` — phases, curing/drying, rework rates, CoeficienteX (**€, not time**).
- `agent_docs/mar_kayaks_schema_discovery.md` — ERP schema (284 tables, 55 views, 29M rows).
- `agent_docs/nelo_executive_summary.md` — business context.
- `agent_docs/architecture.md` — 17 modules + deploy topology.

## "If I disappear for 90 days, do this"

1. **Don't touch production** (NELO factory deploy) without first: fresh clone, `alembic upgrade head`, full canary green, smoke the 4 health endpoints (`/health`, `/health/ready`, `/health/live`, `/metrics`).
2. **Pending PR for `main`** — branch `feat/q60-qualidade-agentes` is ~183 commits ahead at Q.65 close. PR description in `agent_docs/pr_descriptions/q60_q61_q62.md`. Merge if comfortable, otherwise leave the branch alive — it is the live work.
3. **Open decisions** — top of `agent_docs/sprint_history.md` + `.claude/plans/` lists what's blocked on owner input (ERP credentials, NELO HTTP API, customer_name NULLs, defect_rate semantics).
4. **Don't rewrite from scratch** (Spolsky's law). Refactor in place + 1 sub-sprint Q.X.Y at a time + pytest green gate.
5. **Don't merge ZERO MOCKS regressions**. The factory floor sees the same API as dev — only the `X-Tenant-Id` header differs. `npm run lint:mocks` enforces this.
6. **Don't skip the 7 Spelke axioms**. If a property test fails, fix the code, not the test.
7. **Owner contact:** luis@nikufra.ai (Luis Nuno Santos). Co-author trailer in commits is `Claude Opus 4.7 (1M context) <noreply@anthropic.com>` — Claude Code is the secondary owner of record.

## What this project is NOT

- Not a microservice mesh. Single FastAPI process + Postgres + optional Kafka/Redis. Native systemd deploy. No Docker, no k8s, by design.
- Not a SaaS. On-premise per-factory. Tenant header exists but only one tenant runs in prod (NELO).
- Not OpenAI-hosted. LLM is Ollama (Gemma on RTX 5060 Ti) for data sovereignty.
- Not a research playground. Every change ends in pytest green + a demo-able sub-sprint.

## Read these in order if you have 1 hour

1. `CLAUDE.md` (5 min) — DNA.
2. `agent_docs/sprint_history.md` (15 min) — roadmap + history.
3. `agent_docs/spelke_axioms.md` (10 min) — the 7 invariants.
4. `agent_docs/bootstrap_recovery.md` (10 min) — when DB breaks.
5. `agent_docs/FAILED_APPROACHES.md` (10 min) — what NOT to try.
6. `pwsh scripts/verify.ps1` (5 min) — confirm green.

That gets you operational. Everything else is loaded on demand by Claude Code from `.claude/skills/` and `agent_docs/`.
