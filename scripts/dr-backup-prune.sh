#!/usr/bin/env bash
# ProdPlan ONE — nightly backup pruning (Sprint J.2)
#
# Cron: 04:30 daily on the backup box. See docs/disaster-recovery.md §5.
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/backup/prodplan}"
LOG_ROOT="${LOG_ROOT:-/var/log/prodplan}"

echo "[$(date --iso-8601=seconds)] pruning pgBackRest (keep 7 full)"
sudo -u postgres pgbackrest --stanza=prodplan --retention-full=7 expire || true

echo "[$(date --iso-8601=seconds)] pruning kafka snapshots > 14 days"
find "$BACKUP_ROOT/kafka" -type f -name '*.tar.gz' -mtime +14 -print -delete || true

echo "[$(date --iso-8601=seconds)] pruning app logs > 90 days"
find "$LOG_ROOT" -type f -name '*.log.*' -mtime +90 -print -delete || true

echo "[$(date --iso-8601=seconds)] done"
