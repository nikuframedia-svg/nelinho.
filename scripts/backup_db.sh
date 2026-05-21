#!/usr/bin/env bash
# Q.68.2.C — nelinho daily Postgres backup (pg_dump custom format).
#
# Production single-server backup. Runs via systemd timer
# (`deploy/systemd/nelinho-backup.timer`, 03:00 UTC daily). Idempotent
# — re-runs in the same minute produce a second dump with a fresh
# timestamp, never overwriting.
#
# Restore path: see `agent_docs/bootstrap_recovery.md` §3.2.
#
# Environment (all optional; sensible defaults for the NELO box):
#   NELINHO_BACKUP_DIR            target dir (default /var/backups/nelinho)
#   POSTGRES_DB                   source DB (default prodplan_one)
#   POSTGRES_USER                 role with read access (default prodplan)
#   POSTGRES_HOST                 default localhost
#   POSTGRES_PASSWORD             passed to libpq via PGPASSWORD
#   NELINHO_BACKUP_RETENTION_DAYS keep window (default 30)
#   NELINHO_BACKUP_OFFSITE        optional rsync target (e.g. nelo-backup:/srv/nelinho/)
#
# Exit codes:
#   0   dump produced, integrity verified, prune ok
#   1   pg_dump failed
#   2   integrity check failed (corrupt dump removed)
#   3   offsite copy failed (local dump kept)

set -euo pipefail

BACKUP_DIR="${NELINHO_BACKUP_DIR:-/var/backups/nelinho}"
DB_NAME="${POSTGRES_DB:-prodplan_one}"
DB_USER="${POSTGRES_USER:-prodplan}"
DB_HOST="${POSTGRES_HOST:-localhost}"
RETENTION_DAYS="${NELINHO_BACKUP_RETENTION_DAYS:-30}"
OFFSITE="${NELINHO_BACKUP_OFFSITE:-}"

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_FILE="$BACKUP_DIR/nelinho_${TIMESTAMP}.dump"

log() {
    echo "[$(date -Iseconds)] $*"
}

log "pg_dump '$DB_NAME' (host=$DB_HOST user=$DB_USER) -> $BACKUP_FILE"

# pg_dump custom format (-Fc): compressed, supports parallel restore,
# and is the only format `pg_restore --list` can inspect for integrity.
if ! PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump \
        -h "$DB_HOST" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -Fc \
        --no-owner \
        --no-privileges \
        -f "$BACKUP_FILE"; then
    log "ERROR: pg_dump failed"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Integrity check: `pg_restore --list` parses the TOC. A corrupt dump
# fails here even though pg_dump returned 0.
if ! pg_restore --list "$BACKUP_FILE" >/dev/null 2>&1; then
    log "ERROR: integrity check failed; removing $BACKUP_FILE"
    rm -f "$BACKUP_FILE"
    exit 2
fi

DUMP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Backup OK: $BACKUP_FILE ($DUMP_SIZE)"

# Retention: keep the last N days only.
PRUNED=$(find "$BACKUP_DIR" -maxdepth 1 -name 'nelinho_*.dump' \
            -mtime "+$RETENTION_DAYS" -print -delete 2>/dev/null | wc -l)
log "Retention: pruned $PRUNED dump(s) older than $RETENTION_DAYS days"

# Offsite copy (best-effort): a second copy on the NELO backup box.
# Falls back to a non-fatal warning so the local dump survives even
# when the network/box is down.
if [[ -n "$OFFSITE" ]]; then
    log "Offsite copy -> $OFFSITE"
    if ! rsync -a --partial "$BACKUP_FILE" "$OFFSITE/"; then
        log "WARN: offsite rsync failed (local copy kept)"
        exit 3
    fi
fi

exit 0
