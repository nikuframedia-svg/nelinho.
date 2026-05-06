"""
ProdPlan ONE - Event Contracts
===============================

Event contract definitions and validation. Single source of truth for
``event_type → topic`` mapping (closes Sprint S4 / Φ1).

Convention (Sprint S4):
    * **event_type** is the short UPPERCASE name (e.g. ``SCHEDULE_CREATED``)
      stamped by publishers and matched by consumer handler registration.
    * **topic** is the dot-notation Kafka topic (e.g.
      ``prodplan.plan.schedule_created``) defined in
      :class:`src.shared.kafka_client.Topics`.

Before S4, three layers used three different conventions and events never
reached handlers. ``resolve_topic`` is the chokepoint that aligns them.
"""

from typing import Any, Dict, Optional

from .event_schemas import (
    EventPayload,
    EVENT_PAYLOAD_MAP,
    validate_event_payload,
)


# --- event_type → topic mapping ---------------------------------------------

def _build_topic_map() -> Dict[str, str]:
    """Derive the canonical mapping from the ``Topics`` class.

    Uses ``Topics.SCHEDULE_CREATED = "prodplan.plan.schedule_created"`` as the
    source of truth — the attribute *name* becomes the event_type and the
    attribute *value* becomes the topic.
    """
    # Imported here to avoid an import cycle with the Kafka client at startup.
    from .kafka_client import Topics

    mapping: Dict[str, str] = {}
    for attr in dir(Topics):
        if attr.startswith("_"):
            continue
        value = getattr(Topics, attr)
        if isinstance(value, str) and value.startswith("prodplan."):
            mapping[attr] = value
    return mapping


_TOPIC_BY_EVENT_TYPE: Optional[Dict[str, str]] = None


def event_type_to_topic_map() -> Dict[str, str]:
    """Return (and lazily build) the ``event_type → topic`` mapping."""
    global _TOPIC_BY_EVENT_TYPE
    if _TOPIC_BY_EVENT_TYPE is None:
        _TOPIC_BY_EVENT_TYPE = _build_topic_map()
    return _TOPIC_BY_EVENT_TYPE


def resolve_topic(event_type: str) -> str:
    """Return the Kafka topic for ``event_type``.

    Two paths:
    * UPPERCASE short names → looked up in :class:`Topics` enum.
    * Already-canonical dot-notation (``copilot.action.executed``) → prefixed
      with ``prodplan.`` for backward compatibility with legacy emitters.

    Raises ``ValueError`` when neither path applies, so a typo or an unmapped
    new event_type fails loudly at publish time instead of routing into the
    void.
    """
    if not isinstance(event_type, str) or not event_type:
        raise ValueError(f"event_type must be a non-empty string, got {event_type!r}")

    mapping = event_type_to_topic_map()
    if event_type in mapping:
        return mapping[event_type]

    if "." in event_type:
        return f"prodplan.{event_type}"

    raise ValueError(
        f"Unknown event_type {event_type!r}: not in Topics enum and not "
        f"dot-notation. Add it to src.shared.kafka_client.Topics or rename "
        f"the publisher."
    )


# --- contract registry -------------------------------------------------------


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










