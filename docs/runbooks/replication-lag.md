# Runbook: PostgresReplicationLagHigh

**Alert:** `pg_replication_lag > 60s` for 5 min. **Severity:** critical.

## Why it matters

The SLA commits to RPO ≤ 1 h (`docs/sla.md` §3). Replication lag is
the leading indicator — this alert fires well before the RPO budget
is spent, giving you time to intervene.

## Diagnose

```bash
sudo -u postgres psql -c "SELECT client_addr, state, sync_state,
    pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replay_lag
    FROM pg_stat_replication;"
```

Common causes:

1. **Network saturation** — the replica can't keep up with WAL
   streaming. Check `iftop -i eth0`.
2. **Replica disk I/O bottleneck** — `iostat 2 5` on the replica.
3. **Long-running query holding a replication slot** — `pg_stat_activity`
   on the replica.
4. **Replica stopped** — `systemctl status postgresql` on the replica.

## Mitigate

- If the replica is stuck on a long query, kill it:
  ```bash
  sudo -u postgres psql -c "SELECT pg_cancel_backend(<pid>);"
  ```
- If networking is saturated, throttle `wal_sender_timeout` or pause
  the replica's heavy OLAP jobs.
- If the replica is unrecoverable, re-bootstrap from the pgBackRest
  base backup (see [disaster-recovery.md §3.3.2](../disaster-recovery.md)).

## Verify

`pg_stat_replication` shows `replay_lag` in the < 2 s range. Alert
clears after the 5 min window.
