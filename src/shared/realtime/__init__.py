"""
ProdPlan ONE — Real-time event bus (Sprint D.1)
=================================================

Consumes Kafka topics and fans them out to connected browser clients
via Server-Sent Events. Lets the Gestor see alerts, new commits and
KPI updates appear live — no polling, no page refresh.

Public surface:

    from src.shared.realtime import RealtimeBridge, router, CHANNELS

`RealtimeBridge` is a singleton Kafka consumer + tenant-scoped queue
dispatcher. `router` is the FastAPI APIRouter that exposes the
`GET /v1/realtime/events` SSE endpoint. `CHANNELS` maps channel names
(alerts / timeline / dashboard / governance) to Kafka topics.
"""

from .bridge import RealtimeBridge
from .channels import CHANNELS, resolve_topics
from .api import router

__all__ = ["RealtimeBridge", "CHANNELS", "resolve_topics", "router"]
