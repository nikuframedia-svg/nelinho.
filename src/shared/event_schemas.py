"""
ProdPlan ONE - Event Schemas
=============================

Pydantic models for event payloads and envelopes.
Event schema registry for type-safe event publishing.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class EventPayload(BaseModel):
    """Base class for all event payloads."""
    pass


class PlanScheduleCommittedPayload(EventPayload):
    """Payload for plan.schedule.committed event."""
    plan_id: str = Field(..., description="Plan/schedule identifier")
    makespan_minutes: int = Field(..., description="Total makespan in minutes")
    cost_eur: float = Field(..., description="Total cost in EUR")
    oee_percent: float = Field(..., ge=0.0, le=100.0, description="OEE percentage")


class InventoryMovementPayload(EventPayload):
    """Payload for inventory.movement event."""
    sku_id: str = Field(..., description="SKU identifier")
    qty_change: float = Field(..., description="Quantity change (positive for receipts, negative for consumption)")
    transaction_type: str = Field(..., description="Type: 'consume', 'receive', or 'adjust'")
    reference_id: str = Field(..., description="Reference ID (operation_id or po_id)")


class QualityGatePassedPayload(EventPayload):
    """Payload for quality.gate.passed event."""
    entity_id: str = Field(..., description="Entity identifier")
    entity_type: str = Field(..., description="Entity type (e.g., 'order', 'operation')")
    trust_index: float = Field(..., ge=0.0, le=1.0, description="TrustIndex score (0-1)")
    components: Dict[str, float] = Field(
        ..., 
        description="Component scores: {completeness, validity, consistency, timeliness}"
    )


class CopilotActionExecutedPayload(EventPayload):
    """Payload for copilot.action.executed event."""
    action_type: str = Field(..., description="Action type (e.g., 'reduce_setup', 'expedite_purchase')")
    transaction_id: str = Field(..., description="Transaction ID")
    plan_id: Optional[str] = Field(None, description="Plan ID if applicable")
    result: Dict[str, Any] = Field(..., description="Action execution result")


class Event(BaseModel):
    """
    Complete event envelope for Kafka.
    
    Includes message ID for idempotency, event type, aggregate ID for partitioning,
    tenant ID, payload, and timestamp.
    """
    message_id: str = Field(..., description="Unique message ID for idempotency")
    event_type: str = Field(..., description="Event type (e.g., 'plan.schedule.committed')")
    aggregate_id: str = Field(..., description="Aggregate ID for partitioning (ensures ordering)")
    tenant_id: str = Field(..., description="Tenant identifier")
    payload: Dict[str, Any] = Field(..., description="Event payload")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg_123",
                "event_type": "plan.schedule.committed",
                "aggregate_id": "plan_456",
                "tenant_id": "nelo",
                "payload": {
                    "plan_id": "plan_456",
                    "makespan_minutes": 1200,
                    "cost_eur": 5000,
                    "oee_percent": 85.5,
                },
                "timestamp": "2026-01-18T15:49:00Z",
            }
        }


# Event type to payload class mapping
EVENT_PAYLOAD_MAP: Dict[str, type[EventPayload]] = {
    "plan.schedule.committed": PlanScheduleCommittedPayload,
    "inventory.movement": InventoryMovementPayload,
    "quality.gate.passed": QualityGatePassedPayload,
    "copilot.action.executed": CopilotActionExecutedPayload,
}


def validate_event_payload(event_type: str, payload: Dict[str, Any]) -> EventPayload:
    """
    Validate event payload against schema.
    
    Args:
        event_type: Event type string
        payload: Payload dictionary
        
    Returns:
        Validated EventPayload instance
        
    Raises:
        ValueError: If event_type not found or payload invalid
    """
    payload_class = EVENT_PAYLOAD_MAP.get(event_type)
    if not payload_class:
        # Allow unknown event types but validate as generic EventPayload
        return EventPayload(**payload)
    
    return payload_class(**payload)










