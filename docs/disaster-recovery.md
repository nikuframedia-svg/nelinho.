# Disaster Recovery Runbook (Sprint J.2)

> **Goal**: restore the Nelo on-prem deployment from a full-box loss
> within the RTO of 2 h (see `docs/sla.md` §3). This file is the
> single canonical recipe — don't redo restores from memory.

## 1. What's backed up, where

| Asset | Method | Frequency | Stored at | Encrypted |
|---|---|---|---|---|
| Postgres cluster | pgBackRest (full + WAL archive) | full daily 02:00, WAL every 5 min | `/var/lib/pgbackrest/` + off-site via rsync to `nelo-backup.local` | yes (aes-256-cbc) |
| Kafka broker state | tarball of `$KAFKA_DATA_DIR` | daily 03:00 | same | yes |
| Object-store files (commit artefacts, RAG) | rsync snapshot | daily 03:30 | same | yes |
| App configuration | git + `/etc/prodplan/*` snapshot | on change + daily | `nelo-backup.local:/backup/config` | yes |
| Ollama models | rsync | weekly (slow-changing) | same | no (public weights) |

RPO contract: at most **1 hour of WAL** is lost if the primary fails
catastrophically. RTO contract: **2 hours** from incident declaration
to a fully functional system.

## 2. Pre-flight checks (do this weekly)

```bash
# On the primary box, run as postgres user:
sudo -u postgres pgbackrest --stanza=prodplan check
sudo -u postgres pgbackrest --stanza=prodplan info

# On the backup box, verify the latest full + WAL chain:
rsync -av --dry-run nelo-primary.local:/var/lib/pgbackrest/ /backup/prodplan/

# Smoke test the metrics endpoint so we know alerts will fire:
curl -sf http://localhost:8000/metrics | grep prodplan_ | wc -l   # expect > 10
```

Alerts `BackupStale` and `PostgresReplicationLagHigh` cover the
automated side; this manual pre-flight catches silent rsync
failures.

## 3. Scenarios

### 3.1 Postgres only is down (data intact)

1. `systemctl status postgresql` — capture the failure mode.
2. `journalctl -u postgresql --since "1 hour ago"` — copy the
   relevant lines into the incident ticket.
3. `systemctl start postgresql`. If it doesn't start:
   - Fill-disk failure: free space (Kafka log segments, Postgres
     WAL archives under `/var/lib/pgbackrest/archive`), `systemctl
     start postgresql`.
   - Corrupted cluster: skip to §3.3.
4. After start, verify: `sudo -u postgres psql -c 'SELECT now()'`.
5. Unpause APScheduler: `systemctl restart prodplan-api`.

**Expected RTO**: 15 min.

### 3.2 Box is alive, app is dead

Common suspects: OOM kill (Ollama pulled all memory), Python
exception on startup, port conflict.

```bash
systemctl status prodplan-api
journalctl -u prodplan-api --since "30 minutes ago" -n 200
curl -sf http://localhost:8000/v1/ping || echo "down"
curl -sf http://localhost:11434/api/tags || echo "ollama down"
```

Mitigation:

```bash
# Force a clean restart, preserving in-flight Kafka outbox rows:
systemctl restart prodplan-api
# If Ollama is OOM-killing, switch to the lighter model:
# (TenantConfig update, requires admin role)
curl -X PATCH http://localhost:8000/v1/core/tenant-config/... \
  -H 'X-Tenant-Id: ...' \
  -d '{"category":"copilot","key":"llm_model","value":"gemma3:4b"}'
```

**Expected RTO**: 10 min.

### 3.3 Full-box loss (restore from backups)

The 2 h RTO budget breaks down like this:

| Step | Budget |
|---|---|
| Provision a new box (OS + deps) | 30 min |
| Restore Postgres via pgBackRest | 45 min |
| Replay WAL + PITR to last consistent point | 15 min |
| Restore Kafka / Ollama / app config | 20 min |
| Smoke tests + open for traffic | 10 min |
| **Total** | **2 h** |

#### 3.3.1 Provision

On a fresh Ubuntu 24.04 box:

```bash
# Base deps:
apt-get update
apt-get install -y postgresql-16 pgbackrest kafka ollama caddy nginx \
  python3.11 python3.11-venv python3.11-dev build-essential

# ProdPlan source:
git clone https://github.com/nikuframedia-svg/nelinho.git /opt/prodplan
cd /opt/prodplan
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

# systemd units:
cp deploy/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
```

#### 3.3.2 Restore Postgres

```bash
# Install pgBackRest config the backup box expects:
cp deploy/pgbackrest/pgbackrest.conf /etc/pgbackrest.conf

# Pull the backup store down:
rsync -av nelo-backup.local:/backup/prodplan/pgbackrest/ /var/lib/pgbackrest/

# Restore to the Postgres data dir:
sudo -u postgres pgbackrest --stanza=prodplan --type=default \
  --target-time="2026-04-24 14:00:00+00" restore

sudo -u postgres systemctl start postgresql

# Confirm the cluster is healthy and our tenant data is present:
sudo -u postgres psql -d prodplan \
  -c "SELECT count(*) FROM plan.schedule_commits;"
```

`--target-time` should be set to "right before the incident began".
Omit it to restore to the latest archived WAL.

#### 3.3.3 Restore Kafka + object-store

```bash
# Kafka:
rsync -av nelo-backup.local:/backup/prodplan/kafka/ /var/lib/kafka/
systemctl start kafka

# Artefact store (RAG PDFs, commit snapshots, DPO datasets):
rsync -av nelo-backup.local:/backup/prodplan/files/ /var/lib/prodplan/files/

# Ollama models:
rsync -av nelo-backup.local:/backup/prodplan/ollama/ ~ollama/.ollama/
systemctl start ollama
```

#### 3.3.4 Bring the app up

```bash
systemctl start prodplan-api
curl -f http://localhost:8000/v1/ping
# Expected: {"status": "ok", "version": "..."}
```

Run the smoke checklist:

1. `curl http://localhost:8000/v1/realtime/health` returns `ok`.
2. The Grafana dashboard loads and shows fresh metrics.
3. One of the `SCHEDULE_CREATED` test events round-trips through SSE.

## 4. DR drill procedure

Every 3 months Luis (or the delegated operator) runs this drill on a
dedicated staging box:

1. Shut down the staging app stack.
2. Wipe the staging Postgres data dir + Kafka data dir.
3. Run §3.3.2 + §3.3.3 start-to-finish, timing each step.
4. Restart the staging app stack.
5. Run the automated smoke checks (`./scripts/smoke.sh`, see below).
6. Record the observed RTO in `docs/dr-drill-log.md`.

If the observed RTO exceeds 2 h by more than 15 %, open a ticket
(`infra-2026-Q…`) to cut the slow step.

## 5. Scripts

### `scripts/dr-smoke.sh`

Quick post-restore verification; exits non-zero on any failure.

```bash
#!/usr/bin/env bash
set -euo pipefail

check() { printf "%-40s" "$1"; shift; "$@" && echo "OK" || { echo "FAIL"; exit 1; }; }

check "API /v1/ping"          curl -sf http://localhost:8000/v1/ping >/dev/null
check "Realtime health"       curl -sf http://localhost:8000/v1/realtime/health >/dev/null
check "Metrics endpoint"      curl -sf http://localhost:8000/metrics >/dev/null
check "Postgres connect"      sudo -u postgres psql -c 'SELECT 1' >/dev/null
check "Kafka topics"          sudo -u kafka kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null
check "Ollama generate"       curl -sf http://localhost:11434/api/tags >/dev/null

echo "---"
echo "ALL SMOKE CHECKS PASSED"
```

Save to `scripts/dr-smoke.sh`, `chmod +x`, and link from the DR
drill runbook.

### `scripts/dr-backup-prune.sh`

Nightly job — keeps backup volume under control:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Prune pgBackRest older than 14 days.
sudo -u postgres pgbackrest --stanza=prodplan --retention-full=7 expire

# Prune Kafka data (handled by Kafka retention, but the tarball
# snapshots accumulate on the backup box).
find /backup/prodplan/kafka -name '*.tar.gz' -mtime +14 -delete

# Keep only the last 90 days of app logs.
find /var/log/prodplan -name '*.log.*' -mtime +90 -delete
```

## 6. Responsibility matrix

| Who | What |
|---|---|
| **Luis** | Owns the DR contract, runs the quarterly drill, signs off on RTO regressions. |
| **Nelo IT** | Owns the backup box (network, disk, rsync credentials). |
| **Oncall rotation** (future) | Executes §3.1/§3.2/§3.3 during incidents. |

## 7. Change log

| Date | What changed | Reviewed by |
|---|---|---|
| 2026-04-24 | First draft (Sprint J.2) | Luis |

---

*Keep this file short + executable. A 40-page DR plan is a
liability; a 1-page checklist gets rehearsed.*
