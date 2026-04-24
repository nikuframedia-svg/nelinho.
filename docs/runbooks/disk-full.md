# Runbook: HostDiskFillingUp / HostDiskCritical

**Alerts:**
- `HostDiskFillingUp` — root `< 20%` free for 10 min (warning).
- `HostDiskCritical` — root `< 10%` free for 5 min (critical).

## Blast radius

Postgres refuses writes once it can't archive WAL. Kafka rotates but
still needs headroom. Ollama model blobs are chunky (≥ 4 GB).

## Diagnose

```bash
df -h
du -sh /var/lib/postgresql /var/lib/pgbackrest /var/lib/kafka \
       /var/lib/prodplan ~ollama/.ollama 2>/dev/null
```

## Mitigate (in order of safety)

1. **Prune pgBackRest** to retain just the last 7 fulls:
   ```bash
   sudo -u postgres pgbackrest --stanza=prodplan \
       --retention-full=7 expire
   ```
2. **Prune old Kafka log segments** (respects topic retention):
   ```bash
   systemctl restart kafka      # kafka rotates on startup
   ```
3. **Drop old app logs**:
   ```bash
   find /var/log/prodplan -name '*.log.*' -mtime +30 -delete
   ```
4. **Drop unused Ollama models** (weight blobs, ~4-8 GB each):
   ```bash
   ollama list
   ollama rm <model-not-in-use>
   ```
5. **Last resort — extend the volume.** Nelo IT owns this. Open a
   ticket; estimate how long current burn rate gives you.

## Verify

`df -h` root shows > 30 % free. Alert clears within 5 min.
