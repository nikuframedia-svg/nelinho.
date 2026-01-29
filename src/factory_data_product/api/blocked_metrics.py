"""
Blocked Metrics Enforcement for Factory Data Product API.

Implements automatic blocking of metrics that cannot be calculated
due to missing data in Folha_IA_extra.xlsx.

Usage:
    @router.get("/metric/{metric_id}")
    async def get_metric(metric_id: str):
        check_metric_blocked(metric_id)  # Raises HTTPException if blocked
        # ... rest of endpoint
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, Optional, Dict, Any

from fastapi import HTTPException, status

from ..config import BLOCKED_METRICS, ALLOWED_METRICS


class MetricBlockedError(HTTPException):
    """
    Exception raised when a blocked metric is requested.
    
    Returns 422 Unprocessable Entity with detailed reason.
    """
    
    def __init__(self, metric_id: str, reason: str, required_data: list):
        detail = {
            "error": "metric_blocked",
            "metric_id": metric_id,
            "reason": reason,
            "required_data": required_data,
            "message": f"Métrica '{metric_id}' está BLOQUEADA: {reason}",
            "how_to_unblock": f"Para desbloquear esta métrica, é necessário adicionar os seguintes dados: {', '.join(required_data)}",
            "status": "BLOCKED",
        }
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


def check_metric_blocked(metric_id: str) -> None:
    """
    Check if a metric is blocked and raise HTTPException if so.
    
    Args:
        metric_id: The metric identifier to check
        
    Raises:
        MetricBlockedError: If the metric is blocked
    """
    blocked_info = BLOCKED_METRICS.get(metric_id)
    
    if blocked_info:
        raise MetricBlockedError(
            metric_id=metric_id,
            reason=blocked_info["reason"],
            required_data=blocked_info["required_data"],
        )


def is_metric_blocked(metric_id: str) -> bool:
    """
    Check if a metric is blocked without raising an exception.
    
    Args:
        metric_id: The metric identifier to check
        
    Returns:
        True if blocked, False otherwise
    """
    return metric_id in BLOCKED_METRICS


def get_blocked_reason(metric_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the reason why a metric is blocked.
    
    Args:
        metric_id: The metric identifier
        
    Returns:
        Dict with reason and required_data, or None if not blocked
    """
    return BLOCKED_METRICS.get(metric_id)


def is_metric_allowed(metric_id: str) -> bool:
    """
    Check if a metric is in the allowed list.
    
    Args:
        metric_id: The metric identifier
        
    Returns:
        True if allowed, False otherwise
    """
    return metric_id in ALLOWED_METRICS


def enforce_blocked_metrics(func: Callable) -> Callable:
    """
    Decorator to enforce blocked metrics check on endpoints.
    
    Expects the first argument after self/cls to be metric_id.
    
    Usage:
        @router.get("/metric/{metric_id}")
        @enforce_blocked_metrics
        async def get_metric(metric_id: str):
            # This will only execute if metric is not blocked
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Try to get metric_id from kwargs or args
        metric_id = kwargs.get("metric_id")
        if metric_id is None and len(args) > 0:
            metric_id = args[0]
        
        if metric_id:
            check_metric_blocked(metric_id)
        
        return await func(*args, **kwargs)
    
    return wrapper


# Mapping of common metric aliases to canonical blocked metric IDs
METRIC_ALIASES = {
    # OEE variants
    "oee": "oee_real",
    "oee_global": "oee_real",
    "oee_real": "oee_real",
    "overall_equipment_effectiveness": "oee_real",
    
    # Availability variants
    "availability": "availability_oee",
    "availability_oee": "availability_oee",
    "disponibilidade": "availability_oee",
    
    # OTD variants
    "otd": "otd_official",
    "otd_official": "otd_official",
    "on_time_delivery": "otd_official",
    "entrega_prazo": "otd_official",
    
    # Productivity variants
    "productivity_individual": "productivity_individual_real",
    "productivity_individual_real": "productivity_individual_real",
    "produtividade_individual": "productivity_individual_real",
    
    # Cost variants
    "cost_real": "cost_real_per_order",
    "cost_real_per_order": "cost_real_per_order",
    "custo_real": "cost_real_per_order",
    
    # Capacity variants
    "capacity_real": "capacity_real_per_day",
    "capacity_real_per_day": "capacity_real_per_day",
    "capacidade_real": "capacity_real_per_day",
    
    # Mold conflict variants
    "mold_conflict": "mold_conflict_confirmed",
    "mold_conflict_confirmed": "mold_conflict_confirmed",
    "conflito_molde": "mold_conflict_confirmed",
}


def normalize_metric_id(metric_id: str) -> str:
    """
    Normalize a metric ID to its canonical form.
    
    Args:
        metric_id: The metric identifier (may be an alias)
        
    Returns:
        Canonical metric ID
    """
    return METRIC_ALIASES.get(metric_id.lower(), metric_id)


def check_metric_blocked_with_aliases(metric_id: str) -> None:
    """
    Check if a metric is blocked, considering aliases.
    
    Args:
        metric_id: The metric identifier (may be an alias)
        
    Raises:
        MetricBlockedError: If the metric (or its canonical form) is blocked
    """
    canonical_id = normalize_metric_id(metric_id)
    check_metric_blocked(canonical_id)





