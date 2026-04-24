# Runbook: PostgresDown

**Alert:** `PostgresDown` for 1 min. **Severity:** critical.

## Diagnose

```bash
systemctl status postgresql
journalctl -u postgresql --since "15 min ago" -n 300
sudo -u postgres psql -c 'SELECT 1'
df -h  # disk full is the #1 cause
```

## Mitigate

1. **Disk full** → free space: drop old Kafka segments + archived WAL:
   ```bash
   sudo -u postgres pgbackrest --stanza=prodplan expire
   ```
2. **Clean restart** → `systemctl restart postgresql`.
3. **Corrupted cluster** → follow
   [disaster-recovery.md §3.3](../disaster-recovery.md) to restore.

## Verify

`sudo -u postgres psql -c 'SELECT now()'` → returns current time.
`curl http://localhost:8000/v1/ping` → 200 (app reconnects).
