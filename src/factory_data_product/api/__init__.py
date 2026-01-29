"""
Factory Data Product API
========================

Read-only API for semantic data access.
Includes blocked metrics enforcement.
"""

from src.factory_data_product.api.endpoints import router
from src.factory_data_product.api.blocked_metrics import (
    check_metric_blocked,
    is_metric_blocked,
    get_blocked_reason,
    is_metric_allowed,
    enforce_blocked_metrics,
    MetricBlockedError,
)

__all__ = [
    "router",
    "check_metric_blocked",
    "is_metric_blocked",
    "get_blocked_reason",
    "is_metric_allowed",
    "enforce_blocked_metrics",
    "MetricBlockedError",
]


