# Runbook: KafkaDown

**Alert:** `KafkaDown` for 3 min. **Severity:** critical.

## Blast radius

SSE stops receiving events (clients fall back to polling). Outbox
dispatcher accumulates rows — none are lost, but realtime freshness
degrades from <1 s to whatever `SCHEDULE_*` polling cadence callers
use.

## Diagnose

```bash
systemctl status kafka
journalctl -u kafka --since "15 min ago" -n 300

# Is the listener alive?
ss -ltnp | grep 9092

# Broker metadata round-trip:
kafka-topics.sh --bootstrap-server localhost:9092 --list
```

## Mitigate

```bash
systemctl restart kafka
# Wait for the broker to come up (can take ~20 s on first boot).
for i in 1 2 3 4 5; do
    kafka-topics.sh --bootstrap-server localhost:9092 --list && break
    sleep 5
done
```

If the log-segments on disk are corrupted (rare), restore from the
daily kafka tarball — see [disaster-recovery.md §3.3.3](../disaster-recovery.md).

## Verify

- `kafka-topics.sh --list` returns the expected topics.
- `/metrics` on the app shows `prodplan_kafka_producer_success_total`
  incrementing again.
- The `OutboxLagHigh` alert clears within a few minutes (the
  dispatcher flushes the backlog).
