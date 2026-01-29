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










