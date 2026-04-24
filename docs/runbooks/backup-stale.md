# Runbook: BackupStale

**Alert:** `time() - pg_backup_last_successful_seconds > 26 h` for 10 min.
**Severity:** critical.

## Why it matters

RPO ≤ 1 h is the contract. Without a recent full + streaming WAL,
RPO degrades to "time since the last successful backup". A stale
backup is a silent SLA violation.

## Diagnose

```bash
sudo -u postgres pgbackrest --stanza=prodplan info
journalctl -u pgbackrest@prodplan --since "30 hours ago" -n 300
df -h  # full pgbackrest repo is the usual cause
```

## Mitigate

1. **Disk full on the backup store**:
   ```bash
   sudo -u postgres pgbackrest --stanza=prodplan \
       --retention-full=5 expire
   ```
2. **Kick a manual backup** once space is free:
   ```bash
   sudo -u postgres pgbackrest --stanza=prodplan --type=full backup
   ```
3. **Off-site rsync failed** (alert fires even if local is fine):
   ```bash
   rsync -av /var/lib/pgbackrest/ nelo-backup.local:/backup/prodplan/pgbackrest/
   ```

## Verify

`pgbackrest info` shows a full or incremental newer than 24 h ago.
Alert clears within 10 min.
