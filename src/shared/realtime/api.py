"""
ProdPlan ONE — Real-time SSE endpoint (Sprint D.1)
====================================================

Exposes `GET /v1/realtime/events` as a Server-Sent Events stream.

Auth: per the Sprint D decision, tenant_id arrives via query string
(`?tenant_id=<UUID>`). This matches the rest of the codebase (header
`X-Tenant-ID` + query fallback) and sidesteps the `EventSource` API's
limitation that it cannot send custom headers natively. For production
hardening a JWT cookie layer is a drop-in swap inside `_resolve_tenant`.

Channels subscribed via CSV: `?channels=alerts,timeline`.

SSE format produced:

    event: MOLD_MAINT_DUE
    id: <event_id>
    data: {"tenant_id": "...", "payload": {...}, "_topic": "prodplan..."}

The `event` name is the envelope's `event_type` so the frontend hook
can `addEventListener(type, cb)` to dispatch by type.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sse_starlette.sse import EventSourceResponse

from src.shared.realtime.bridge import RealtimeBridge
from src.shared.realtime.channels import CHANNELS, resolve_topics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/realtime", tags=["Realtime"])


# Heartbeat cadence — Caddy default idle timeout is 2 min, Cloudflare
# proxy buffers can kill silent SSE streams around 90s. 30s keeps every
# hop happy without burning bandwidth.
HEARTBEAT_EVERY_SECONDS = 30.0


@router.get("/events")
async def stream_events(
    tenant_id: UUID = Query(...),
    channels: str = Query(
        ...,
        description="Comma-separated channel names (alerts,timeline,dashboard,governance)",
        examples=["alerts,timeline"],
    ),
):
    """Subscribe to real-time events for this tenant + channels.

    Returns an SSE stream. The client uses `EventSource` and
    `addEventListener(event_type, handler)` to route each event by its
    type name.
    """
    channel_list = _parse_channels(channels)
    # Validate channels up-front so the client gets a clean 400 rather
    # than an empty stream it'll stare at forever.
    try:
        resolve_topics(channel_list)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    bridge = RealtimeBridge.instance()
    # Q.59.A — an unhealthy bridge (Kafka unreachable) used to answer 503.
    # But `EventSource` cannot read an HTTP status, so the browser just
    # reconnects forever — a single backend log showed 982 such 503s. We
    # now always serve the stream; when degraded it carries only
    # heartbeats and the frontend falls back to TanStack Query polling.
    # `/v1/realtime/health` still reports the real bridge state.
    degraded = not bridge.healthy

    sub_id, queue = bridge.subscribe(tenant_id, channels=channel_list)

    async def _event_stream() -> AsyncGenerator[dict, None]:
        try:
            # Initial handshake — lets the browser know the stream is
            # live and tells it which subscription id we're using
            # (useful when debugging a missing event with journalctl).
            # `degraded=True` means no live event source (Kafka down);
            # the client should lean on polling for data.
            yield {
                "event": "connected",
                "data": json.dumps({
                    "subscription_id": sub_id,
                    "tenant_id": str(tenant_id),
                    "channels": channel_list,
                    "degraded": degraded,
                }),
            }

            while True:
                try:
                    envelope = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_EVERY_SECONDS,
                    )
                except asyncio.TimeoutError:
                    # Send a heartbeat comment so the connection stays
                    # live even when the factory is quiet.
                    yield {"event": "heartbeat", "data": "ping"}
                    continue

                if envelope is None:
                    # Bridge is shutting down — close the stream.
                    break

                yield {
                    "event": envelope.get("event_type", "message"),
                    "id": envelope.get("event_id", ""),
                    "data": json.dumps(envelope, default=str),
                }
        finally:
            bridge.unsubscribe(sub_id)

    return EventSourceResponse(_event_stream())


@router.get("/channels")
async def list_channels() -> dict:
    """Enumerate the channels the frontend can subscribe to, plus which
    Kafka topics each one covers. Useful for debugging + doc pages.
    """
    return {
        name: sorted(topics) for name, topics in sorted(CHANNELS.items())
    }


@router.get("/health")
async def bridge_health() -> dict:
    """Expose bridge status so `/health` dashboards can light up green."""
    return RealtimeBridge.instance().snapshot()


# ─── Helpers ────────────────────────────────────────────────────────


def _parse_channels(raw: str) -> List[str]:
    """Trim + lower + dedupe, keep submission order."""
    seen: set = set()
    out: List[str] = []
    for piece in raw.split(","):
        clean = piece.strip().lower()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    if not out:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="channels query must list at least one channel",
        )
    return out
