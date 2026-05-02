"""
ProdPlan ONE - Prometheus Metrics
==================================

Prometheus metrics for SLO monitoring and observability.
Exposes /metrics endpoint for Prometheus scraping.
"""

import logging
from typing import Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from prometheus_client.core import CollectorRegistry

logger = logging.getLogger(__name__)

# Create a custom registry (optional - can use default)
registry = CollectorRegistry()

# ═══════════════════════════════════════════════════════════════════════════════
# Outbox Dispatcher Metrics (LACUNA 1)
# ═══════════════════════════════════════════════════════════════════════════════

outbox_dispatcher_latency_seconds = Histogram(
    "prodplan_outbox_dispatcher_latency_seconds",
    "Outbox dispatcher latency in seconds (fetch + publish)",
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
    registry=registry,
)

outbox_events_dispatched_total = Counter(
    "prodplan_outbox_events_dispatched_total",
    "Total number of events dispatched from outbox",
    ["status"],  # status: published, failed
    registry=registry,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Kafka Producer Metrics (LACUNA 1)
# ═══════════════════════════════════════════════════════════════════════════════

kafka_producer_success_total = Counter(
    "prodplan_kafka_producer_success_total",
    "Total number of successful Kafka publishes",
    ["topic"],
    registry=registry,
)

kafka_producer_failure_total = Counter(
    "prodplan_kafka_producer_failure_total",
    "Total number of failed Kafka publishes",
    ["topic", "error_type"],
    registry=registry,
)

kafka_producer_latency_seconds = Histogram(
    "prodplan_kafka_producer_latency_seconds",
    "Kafka producer latency in seconds",
    ["topic"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
    registry=registry,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Data Quality Metrics (LACUNA 2)
# ═══════════════════════════════════════════════════════════════════════════════

trust_index_score = Gauge(
    "prodplan_trust_index_score",
    "TrustIndex score (0-1 scale) for data quality",
    ["entity_type", "entity_id"],
    registry=registry,
)

data_quality_issues_total = Counter(
    "prodplan_data_quality_issues_total",
    "Total number of data quality issues detected",
    ["issue_type"],  # missing_field, out_of_range, latency
    registry=registry,
)

auto_repair_actions_total = Counter(
    "prodplan_auto_repair_actions_total",
    "Total number of auto-repair actions applied",
    ["repair_type"],  # forward_fill, mean_impute, outlier_clamp
    registry=registry,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Copilot Action Metrics (LACUNA 3)
# ═══════════════════════════════════════════════════════════════════════════════

copilot_action_execution_time_seconds = Histogram(
    "prodplan_copilot_action_execution_time_seconds",
    "Copilot action execution time in seconds",
    ["action_type", "mode"],  # mode: preview, sandbox, execute
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry,
)

copilot_actions_total = Counter(
    "prodplan_copilot_actions_total",
    "Total number of Copilot actions executed",
    ["action_type", "mode", "status"],  # status: success, failed
    registry=registry,
)

copilot_action_rollbacks_total = Counter(
    "prodplan_copilot_action_rollbacks_total",
    "Total number of action rollbacks",
    ["action_type"],
    registry=registry,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Supply Chain Metrics (LACUNA 4)
# ═══════════════════════════════════════════════════════════════════════════════

supply_forecast_quality = Gauge(
    "prodplan_supply_forecast_quality",
    "Forecast quality metric (WMAPE)",
    ["sku_id", "quality"],  # quality: good, fair, poor
    registry=registry,
)

inventory_movements_total = Counter(
    "prodplan_inventory_movements_total",
    "Total number of inventory movements",
    ["transaction_type"],  # consume, receive, adjust
    registry=registry,
)

# ═══════════════════════════════════════════════════════════════════════════════
# HTTP Request Metrics (Sprint J follow-up — surfaces in alerts.yml)
# ═══════════════════════════════════════════════════════════════════════════════
#
# The alert file references `prodplan_http_requests_total` +
# `prodplan_http_request_duration_seconds`; these instruments feed them.
# Emitted by the middleware in `src/shared/http_metrics_middleware.py`
# — ONE place to edit if the label cardinality needs trimming on a
# busy tenant.

http_requests_total = Counter(
    "prodplan_http_requests_total",
    "Total number of HTTP requests handled by the FastAPI app.",
    ["method", "path_template", "status"],
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "prodplan_http_request_duration_seconds",
    "HTTP request handler latency, split by method/path/status.",
    ["method", "path_template", "status"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry,
)

http_requests_in_flight = Gauge(
    "prodplan_http_requests_in_flight",
    "Current number of HTTP requests being processed.",
    registry=registry,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Silent Fallbacks (FASE 4.1 — auditoria PLANO Decide)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Every "best-effort" path in the codebase that swallows an error and
# returns a default (empty list, fallback constant, baseline schedule)
# bumps this counter. Operators can alert on rate>0 to surface paths
# that are silently degrading without raising. Labels:
#   * module — coarse area (cpo, routing_resolver, factory_state, ml...)
#   * reason — short tag identifying which fallback path fired
#
# Example call sites:
#   silent_fallback_total.labels(module="routing_resolver", reason="engine_unavailable").inc()
#   silent_fallback_total.labels(module="cpo.fitness", reason="quality_risk_predictor_none").inc()

silent_fallback_total = Counter(
    "prodplan_silent_fallback_total",
    "Number of times a silent fallback path was taken (best-effort defaults instead of raising).",
    ["module", "reason"],
    registry=registry,
)


def bump_silent_fallback(module: str, reason: str) -> None:
    """Increment ``silent_fallback_total`` from any caller.

    Defensive: callers in modules that get unit-tested without
    prometheus_client installed shouldn't crash. We swallow any
    increment error and log at debug.
    """
    try:
        silent_fallback_total.labels(module=module, reason=reason).inc()
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("bump_silent_fallback(%s, %s) failed: %s", module, reason, exc)


# ═══════════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_metrics_response() -> bytes:
    """
    Generate Prometheus metrics response.
    
    Returns:
        Bytes of Prometheus metrics in text format
    """
    return generate_latest(registry)


def get_metrics_content_type() -> str:
    """
    Get content type for Prometheus metrics endpoint.
    
    Returns:
        Content type string
    """
    return CONTENT_TYPE_LATEST










