"""
ProdPlan ONE - Event Contracts
===============================

Event contract definitions and validation.
Interfaces for event contracts (TypeScript-like).
"""

from typing import Dict, Any, Optional
from .event_schemas import EventPayload, EVENT_PAYLOAD_MAP, validate_event_payload


class EventContract:
    """
    Event contract interface (TypeScript-like).
    
    Defines the structure and validation rules for events.
    """
    
    def __init__(
        self,
        event_type: str,
        payload_schema: type[EventPayload],
        required_fields: Optional[Dict[str, type]] = None,
    ):
        self.event_type = event_type
        self.payload_schema = payload_schema
        self.required_fields = required_fields or {}
    
    def validate(self, payload: Dict[str, Any]) -> EventPayload:
        """
        Validate payload against contract.
        
        Args:
            payload: Payload dictionary
            
        Returns:
            Validated EventPayload instance
            
        Raises:
            ValueError: If payload invalid
        """
        return validate_event_payload(self.event_type, payload)


# Event contract registry
EVENT_CONTRACTS: Dict[str, EventContract] = {}

for event_type, payload_class in EVENT_PAYLOAD_MAP.items():
    EVENT_CONTRACTS[event_type] = EventContract(
        event_type=event_type,
        payload_schema=payload_class,
    )


def get_event_contract(event_type: str) -> Optional[EventContract]:
    """Get event contract for event type."""
    return EVENT_CONTRACTS.get(event_type)


def register_event_contract(
    event_type: str,
    payload_schema: type[EventPayload],
    required_fields: Optional[Dict[str, type]] = None,
) -> EventContract:
    """
    Register a new event contract.
    
    Args:
        event_type: Event type string
        payload_schema: Pydantic model for payload
        required_fields: Optional required fields mapping
        
    Returns:
        Registered EventContract
    """
    contract = EventContract(
        event_type=event_type,
        payload_schema=payload_schema,
        required_fields=required_fields,
    )
    EVENT_CONTRACTS[event_type] = contract
    return contract










