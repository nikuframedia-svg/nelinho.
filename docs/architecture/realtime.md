# Realtime (SSE) architecture

**Sprint D.1 / D.2 / D.3** wired a single-stream, server-sent-events
bridge between the backend event bus and every browser tab.

## Shape

```
business logic
      │
      ▼
  Kafka topic  (prodplan.plan.schedule_created, …)
      │
      ▼
 RealtimeBridge  (src/shared/realtime/bridge.py)
   • aiokafka consumer
   • per-subscriber asyncio.Queue(maxsize=100) — drop-oldest
   • tenant + channel filter
      │
      ▼
 /v1/realtime/events  (SSE)
   • auth: ?tenant_id=…  (EventSource can't send custom headers)
   • channels: alerts, timeline, dashboard, governance
   • heartbeat every 30 s
      │
      ▼
 useRealtimeEvents  (frontend/src/hooks/useRealtimeEvents.ts)
   • EventSource + exponential backoff reconnect
   • rolling 500-event buffer
      │
      ▼
 RealtimeProvider  (frontend/src/providers/RealtimeProvider.tsx)
   • one connection per tab
   • useRealtime() / useRealtimeType(type, handler)
      │
      ▼
 Consumers: NotificationsPanel, useLiveDashboardRefresh, LiveBadge,
            TimelinePage, OperadorPage
```

## Channels

| Channel | Example event types |
|---|---|
| `alerts` | `MOLD_MAINT_DUE`, `MATERIAL_SHORTAGE_DETECTED`, `MOLD_HEALTH_DEGRADED` |
| `timeline` | `SCHEDULE_CREATED`, `SCHEDULE_UPDATED`, `MRP_CALCULATED`, `DECISION_*` |
| `dashboard` | `SCHEDULE_CREATED`, `COGS_CALCULATED`, `REWORK_ENTRY_CREATED` |
| `governance` | `DECISION_PROPOSED`, `DECISION_APPROVED`, `DECISION_EXECUTED`, `DECISION_ROLLED_BACK` |

Full mapping: `src/shared/realtime/channels.py`.

## Budget

- Heartbeat: 30 s (keeps proxies from dropping the connection).
- Rolling buffer on the client: 500 events (newest first).
- Per-subscriber Kafka queue: 100 events, drop-oldest when full.

## How it degrades

- **Kafka down** → the bridge logs and keeps heartbeats flowing. New
  events don't deliver. Clients see `LiveBadge` stay green (the
  connection is fine) but no activity.
- **Bridge down** → `/v1/realtime/events` returns 503. `LiveBadge`
  flips to "Desligado · a reconectar".
- **Client offline** → `EventSource` reconnects with backoff
  `[1, 2, 4, 8, 15, 30]` s. `LiveBadge` shows attempt count.

## Testing

- Backend: `tests/shared/test_realtime_{bridge,api,channels}.py`
  (27 tests).
- Frontend: no vitest; visual via `npm run dev`. `LiveBadge` is the
  instrumentation surface.
