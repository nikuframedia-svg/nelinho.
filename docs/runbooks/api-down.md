# Runbook: APIDown

**Alert:** `APIDown` — `up{job="prodplan-api"} == 0` for 2 min.

**Severity:** critical (pages oncall).

## Blast radius

The FastAPI process is down. SSE disconnects, every REST write
returns 5xx, the CPO scheduler is unreachable. Ops Inbox + Timeline +
Learned Rules UI all go blank.

## Diagnose (≤ 2 min)

```bash
systemctl status prodplan-api
journalctl -u prodplan-api --since "10 min ago" -n 200
curl -sf http://localhost:8000/v1/ping || echo "confirmed down"
```

Common root causes (in rough frequency order):

1. **OOM kill** — Ollama or a runaway python worker stole the
   memory. Check `dmesg | tail -20` for `Out of memory: Killed process`.
2. **Postgres unreachable** — the app startup probe failed. See
   [Postgres down](postgres-down.md).
3. **Port conflict** — something else bound 8000. `ss -ltnp | grep 8000`.
4. **Recent deploy regressed startup** — see `/var/log/prodplan/deploy.log`.

## Mitigate

```bash
# Clean restart, preserves in-flight Kafka outbox rows.
systemctl restart prodplan-api

# Verify it's back:
sleep 10
curl -sf http://localhost:8000/v1/ping
```

If the restart loops:

```bash
# Stop the systemd unit while you investigate.
systemctl stop prodplan-api

# Run the app in foreground with the same env to see the trace.
cd /opt/prodplan
.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

When Ollama is the OOM culprit, switch to the lighter model:

```bash
# Requires admin X-User-Role on the tenant-config PATCH.
curl -X PATCH http://localhost:8000/v1/core/tenant-config/.../copilot/llm_model \
  -H 'X-Tenant-Id: <tenant>' \
  -H 'X-User-Role: admin' \
  -d '"gemma3:4b"'
```

## Verify resolution

1. `curl http://localhost:8000/v1/ping` → 200.
2. Grafana "API up" panel flips green.
3. Re-open the frontend — LiveBadge turns "Ao vivo".

## After the fact

1. Copy the failing log into the incident ticket.
2. File a follow-up if the same root cause fires twice in a week.
3. Update this runbook if the mitigation changed.
