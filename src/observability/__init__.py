"""Q.66.E.3 — Observability endpoints.

Honeycomb-style traces searchable. Primeiro endpoint:
GET /v1/observability/agent-actions — chamadas do copiloto
(intent, model, latency, outcome, escalated, trace_id).

Modulo separado de `src/shared/observability/` (structlog + middleware
trace_id Q.61.12) para nao misturar plumbing de tracing com endpoints
de leitura. Imports de modelos ficam em src/core/models/.
"""

from src.observability.api import router

__all__ = ["router"]
