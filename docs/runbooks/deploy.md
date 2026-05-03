# Deployment runbook

> Sprint Q.13.F F.7 — single-host rolling deploy procedure for the
> NELO production box. Blue-green is out of scope; this is the
> "git pull, restart, watch metrics" recipe.

## Pre-flight

Before pushing to main:

- [ ] All CI checks green on the merge request.
- [ ] No alembic forks in `alembic/versions/` (every revision has a
      single `down_revision` parent — re-confirm with `alembic history`).
- [ ] No new Python deps without entries in `requirements.lock`.
- [ ] Smoke-test locally: `pytest -q tests/plan tests/copilot tests/governance`.

## Deploy sequence

```bash
# 1. Connect to the prod box
ssh prodplan@nelo-prod

# 2. Pull the new code
cd /opt/prodplan
git fetch --tags
git log --oneline HEAD..origin/main         # confirm the diff is what you expect
git checkout origin/main

# 3. Lock dependencies if requirements changed
diff requirements.lock <(git show HEAD:requirements.lock) >/dev/null || \
  /opt/prodplan/.venv/bin/pip install -r requirements.lock

# 4. Run migrations FORWARD-ONLY
/opt/prodplan/.venv/bin/alembic upgrade head

# 5. Reload the systemd unit (drains the outbox in 30s; see B5)
sudo systemctl reload prodplan-api

# 6. Smoke-test the deploy
curl -fsS https://api.prodplan.local/health/ready | jq .
curl -fsS https://api.prodplan.local/v1/diagnostics/audit-board | jq '.modules | length'
```

Step 5 sends `SIGHUP`; the lifespan handler drains the outbox + Kafka
producer + Redis pool over a 30s grace window before the new process
takes traffic. There IS a momentary connection drop — Caddy's retry
covers it for idempotent reads, but **avoid deploys during a CPO
solve** (the long-running endpoint isn't retriable cleanly).

## Rollback

If a deploy breaks:

```bash
# 1. Revert the working tree
cd /opt/prodplan
git checkout <previous-sha>

# 2. Migrations: alembic is FORWARD-ONLY by policy. Don't downgrade
#    unless you've manually verified the down() path works on a clone
#    of prod. In practice: roll forward with a fix.

# 3. Reload
sudo systemctl reload prodplan-api
```

For migration-induced damage, restore from the latest pgBackRest
snapshot (see [backup-stale.md](backup-stale.md) for the inverse
procedure — restore tested quarterly via `scripts/restore_drill.sh`).

## What "alembic upgrade head" actually does

- Acquires an advisory lock so two processes can't migrate at once.
- Runs each revision's `upgrade()` in a transaction. **Postgres
  DDL is transactional** — an exception rolls back cleanly.
- Records the new head in `alembic_version`.

The `IF NOT EXISTS` pattern in Q.13.F migration 042 means re-running
the migration on an already-upgraded DB is a no-op rather than an
error. Newer migrations should follow this pattern.

## Post-deploy verification

In the first 10 minutes after the reload:

- [ ] `/health/ready` stays 200.
- [ ] `prodplan_http_requests_total{status=~"5.."}` rate doesn't spike
      (Grafana → ProdPlan Overview).
- [ ] `prodplan_silent_fallback_total` rate per module flat
      (Grafana → ProdPlan Silent Fallbacks).
- [ ] `prodplan_http_request_duration_seconds_bucket` p99 stays under
      its baseline.
- [ ] Sentry: no new release-tagged errors in the last 5 min
      (only relevant when `SENTRY_DSN` is set).

If any of those breaks: see [incidents.md](incidents.md) and roll
back per the section above.

## Zero-downtime caveats

**This is rolling, not zero-downtime.** Two paths haven't been
covered yet:

1. Schema changes that are NOT backward-compatible with the previous
   app version (e.g. dropping a column the old code still reads).
   For now: stage in two deploys — first add the column, then
   release the code that drops the read, then drop the column in a
   third deploy.
2. Long-running CPO requests (>30s) get cut off. The frontend retries
   on 503 but a CPO solve doesn't resume mid-search. Avoid deploying
   when a solve is in flight.

Blue-green deploy is on the roadmap (Sprint Q.14+); until then,
schedule deploys for the morning quiet window (07:00-09:00) and avoid
production-time pushes.
