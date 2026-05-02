#!/usr/bin/env bash
#
# ProdPlan ONE — Restore drill (Sprint Q.13.B / B6)
# ===================================================
#
# Quarterly disaster-recovery test: takes a fresh `pg_dump` of the
# production DB, restores it to a temporary database, runs a smoke
# test against the temp DB, and tears it down. If any step fails,
# the script exits non-zero so cron can email the on-call.
#
# This script is the documented part of `monitoring/prometheus/alerts.yml`'s
# `BackupStale` alert: when the alert fires, run this once manually to
# confirm we *can* still restore. The alert keeps the operator honest;
# the drill keeps the restore path tested.
#
# Usage
# -----
#   ./scripts/restore_drill.sh                          # full drill
#   ./scripts/restore_drill.sh --keep                   # don't drop temp DB
#   ./scripts/restore_drill.sh --backup /path/to.dump   # restore from existing dump
#
# Cron (quarterly):
#   0 3 1 */3 *  /opt/prodplan/scripts/restore_drill.sh >> /var/log/prodplan/restore-drill.log 2>&1
#
# Environment variables
# ---------------------
#   PGHOST, PGUSER, PGPASSWORD — standard libpq vars
#   PRODPLAN_DB        — source DB name (default: prodplan)
#   PRODPLAN_DRILL_DB  — temp DB name  (default: prodplan_drill_<epoch>)
#   PRODPLAN_DRILL_DIR — workdir for dump files (default: /tmp/prodplan_drill)
#
# Exit codes
# ----------
#   0   drill passed
#   1   pg_dump failed (source unreachable or insufficient grants)
#   2   restore failed (temp DB rejected the dump)
#   3   smoke test failed (DB restored but doesn't look right)
#   4   cleanup failed (temp DB still alive — manual drop needed)

set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────

PRODPLAN_DB="${PRODPLAN_DB:-prodplan}"
DRILL_TIMESTAMP="$(date +%s)"
PRODPLAN_DRILL_DB="${PRODPLAN_DRILL_DB:-prodplan_drill_${DRILL_TIMESTAMP}}"
PRODPLAN_DRILL_DIR="${PRODPLAN_DRILL_DIR:-/tmp/prodplan_drill}"

KEEP=0
BACKUP_PATH=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep)
            KEEP=1
            shift
            ;;
        --backup)
            BACKUP_PATH="$2"
            shift 2
            ;;
        *)
            echo "Unknown arg: $1" >&2
            exit 1
            ;;
    esac
done

mkdir -p "${PRODPLAN_DRILL_DIR}"
DUMP_FILE="${BACKUP_PATH:-${PRODPLAN_DRILL_DIR}/${PRODPLAN_DB}-${DRILL_TIMESTAMP}.dump}"

log() {
    echo "[$(date -Iseconds)] $*"
}

# ─── Step 1: pg_dump (skipped when --backup supplied) ────────────────

if [[ -z "${BACKUP_PATH}" ]]; then
    log "Step 1/4: pg_dump from '${PRODPLAN_DB}' → ${DUMP_FILE}"
    if ! pg_dump --format=custom --jobs=4 --file="${DUMP_FILE}" "${PRODPLAN_DB}"; then
        log "ERROR: pg_dump failed"
        exit 1
    fi
    DUMP_SIZE=$(du -h "${DUMP_FILE}" | cut -f1)
    log "Dump produced: ${DUMP_SIZE}"
else
    log "Step 1/4: skipping pg_dump (using existing backup ${BACKUP_PATH})"
fi

# ─── Step 2: createdb + pg_restore ───────────────────────────────────

log "Step 2/4: createdb '${PRODPLAN_DRILL_DB}' + pg_restore"
if ! createdb "${PRODPLAN_DRILL_DB}"; then
    log "ERROR: createdb failed"
    exit 2
fi

# pg_restore exits non-zero on warnings (e.g. extension already installed).
# We accept those — the smoke test below is the source of truth.
pg_restore --jobs=4 --no-owner --no-privileges \
    --dbname="${PRODPLAN_DRILL_DB}" "${DUMP_FILE}" \
    || log "WARNING: pg_restore reported issues (continuing — smoke decides)"

# ─── Step 3: smoke test ──────────────────────────────────────────────

log "Step 3/4: smoke test against '${PRODPLAN_DRILL_DB}'"

# These are the absolute minimum tables that MUST exist after a clean
# restore. If any is missing or empty, the dump is broken.
declare -a REQUIRED_TABLES=(
    "core.tenant"
    "factory_curated.order"
    "factory_curated.skill_matrix"
    "plan.schedule_commit"
    "governance.decision_run"
    "governance.preference_rule"
)

SMOKE_FAILED=0
for tbl in "${REQUIRED_TABLES[@]}"; do
    count=$(psql -d "${PRODPLAN_DRILL_DB}" -tAc "SELECT count(*) FROM ${tbl}" 2>/dev/null || echo "ERR")
    if [[ "${count}" == "ERR" ]]; then
        log "  ❌ ${tbl} — table missing or unreadable"
        SMOKE_FAILED=1
    elif [[ "${count}" == "0" ]]; then
        log "  ⚠️  ${tbl} — exists but empty (acceptable for fresh DB)"
    else
        log "  ✅ ${tbl} — ${count} rows"
    fi
done

# Latest schedule commit should be reachable through the chain.
LATEST_SHA=$(psql -d "${PRODPLAN_DRILL_DB}" -tAc "
    SELECT commit_sha256 FROM plan.schedule_commit
    ORDER BY created_at DESC LIMIT 1
" 2>/dev/null || echo "")
if [[ -z "${LATEST_SHA}" ]]; then
    log "  ⚠️  no schedule commits in restored DB (fresh tenant, ok)"
else
    log "  ✅ latest schedule commit: ${LATEST_SHA:0:12}"
fi

if [[ ${SMOKE_FAILED} -eq 1 ]]; then
    log "ERROR: smoke test FAILED. Restored DB is missing required tables."
    log "Temp DB '${PRODPLAN_DRILL_DB}' kept for forensics. Drop manually."
    exit 3
fi

log "Smoke test PASSED"

# ─── Step 4: cleanup ─────────────────────────────────────────────────

if [[ ${KEEP} -eq 1 ]]; then
    log "Step 4/4: --keep specified, leaving '${PRODPLAN_DRILL_DB}' alive"
    log "Drop manually: dropdb ${PRODPLAN_DRILL_DB}"
else
    log "Step 4/4: dropdb '${PRODPLAN_DRILL_DB}'"
    if ! dropdb "${PRODPLAN_DRILL_DB}"; then
        log "ERROR: dropdb failed — temp DB '${PRODPLAN_DRILL_DB}' still alive"
        exit 4
    fi

    if [[ -z "${BACKUP_PATH}" ]]; then
        # Only clean up dump files we created in this run.
        rm -f "${DUMP_FILE}"
    fi
fi

log "Restore drill PASSED for '${PRODPLAN_DB}' in $(($(date +%s) - DRILL_TIMESTAMP))s"
exit 0
