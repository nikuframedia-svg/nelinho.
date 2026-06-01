"""
ProdPlan ONE - Kafka Client
============================

Async Kafka producer and consumer wrappers.
Event-driven architecture for module communication.

Includes:
- Circuit breaker for resilience
- Retry with exponential backoff
- Idempotency support
- Exactly-once delivery guarantees
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar
from uuid import UUID, uuid4

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError
from pydantic import BaseModel, Field

from .config import settings

logger = logging.getLogger(__name__)


# Event Topics
class Topics:
    """Kafka topic names."""
    
    # CORE events
    MASTER_DATA_LOADED = "prodplan.core.master_data_loaded"
    CONFIG_UPDATED = "prodplan.core.config_updated"
    TENANT_CONFIGURED = "prodplan.core.tenant_configured"
    ORDER_RECEIVED = "prodplan.core.order_received"

    # PLAN events
    SCHEDULE_CREATED = "prodplan.plan.schedule_created"
    SCHEDULE_UPDATED = "prodplan.plan.schedule_updated"
    SCHEDULE_RESCHEDULED = "prodplan.plan.schedule_rescheduled"
    MRP_CALCULATED = "prodplan.plan.mrp_calculated"
    MATERIAL_REQUIREMENT_PLANNED = "prodplan.plan.material_planned"
    PURCHASE_ORDER_CREATED = "prodplan.plan.po_created"
    CAPACITY_CONSTRAINT_DETECTED = "prodplan.plan.capacity_constraint"

    # SUPPLY events (Sprint O)
    STOCK_ADJUSTED = "prodplan.supply.stock_adjusted"
    MATERIAL_SHORTAGE_DETECTED = "prodplan.supply.material_shortage"
    STOCK_RECONCILED = "prodplan.supply.stock_reconciled"

    # QUALITY events (Sprint R)
    REWORK_ENTRY_CREATED = "prodplan.quality.rework_entry_created"
    QUALITY_RISK_SCORED = "prodplan.quality.risk_scored"

    # MOLD events (Sprint R.6)
    MOLD_MAINT_DUE = "prodplan.mold.maint_due"
    MOLD_HEALTH_DEGRADED = "prodplan.mold.health_degraded"
    
    # PROFIT events
    COGS_CALCULATED = "prodplan.profit.cogs_calculated"
    PRICING_RECOMMENDED = "prodplan.profit.pricing_recommended"
    SCENARIO_SIMULATED = "prodplan.profit.scenario_simulated"
    COST_VARIANCE_CALCULATED = "prodplan.profit.cost_variance"

    # GOVERNANCE events (Sprint A WG1)
    DECISION_PROPOSED = "prodplan.governance.decision_proposed"
    DECISION_APPROVED = "prodplan.governance.decision_approved"
    # Q.153 — a rejeição passa a ser um evento de 1ª classe (antes só havia
    # APPROVED). O frontend já escutava `DECISION_REJECTED`
    # (DecisoesPage useRealtimeType) mas nada o publicava — listener morto.
    DECISION_REJECTED = "prodplan.governance.decision_rejected"
    DECISION_EXECUTED = "prodplan.governance.decision_executed"
    DECISION_ROLLED_BACK = "prodplan.governance.decision_rolled_back"

    # GOVERNANCE rule-firing push (Sprint Q.14.B). Synthetic topic name —
    # the source is Postgres LISTEN/NOTIFY, NOT Kafka. The shared topic
    # constant lets the existing realtime channel map fan-out work
    # without a parallel pipeline.
    RULE_FIRING_PROPOSED = "prodplan.governance.rule_firing_proposed"

    # HR events
    EMPLOYEE_ALLOCATED = "prodplan.hr.employee_allocated"
    LABOR_COST_COMMITTED = "prodplan.hr.labor_cost_committed"
    SHIFT_SCHEDULED = "prodplan.hr.shift_scheduled"
    PRODUCTIVITY_RECORDED = "prodplan.hr.productivity_recorded"
    MONTHLY_PAYROLL_CALCULATED = "prodplan.hr.payroll_calculated"
    CERTIFICATION_EXPIRY_ALERT = "prodplan.hr.certification_expiry"
    
    # Dead letter queue
    DLQ = "prodplan.dlq"


class EventBase(BaseModel):
    """Base class for all events."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    tenant_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[UUID] = None
    source_module: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    # Sprint S5 / Π6: explicit sandbox marker. Producers that originate from
    # /v1/sandbox or any what-if path MUST set this to True so consumers can
    # filter business-logic side-effects out of production data.
    sandbox: bool = Field(
        default=False,
        description="True iff this event originated from a sandbox/what-if scenario.",
    )
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class EventEnvelope(BaseModel):
    """Wrapper for event serialization."""

    event_id: str
    event_type: str
    tenant_id: str
    timestamp: str
    correlation_id: Optional[str] = None
    source_module: str
    payload: Dict[str, Any]
    # Sprint S5 / Π6: propagate sandbox flag through the wire envelope so
    # consumers can filter without inspecting payload internals.
    sandbox: bool = False

    @classmethod
    def from_event(cls, event: EventBase) -> "EventEnvelope":
        """Create envelope from event."""
        return cls(
            event_id=str(event.event_id),
            event_type=event.event_type,
            tenant_id=str(event.tenant_id),
            timestamp=event.timestamp.isoformat(),
            correlation_id=str(event.correlation_id) if event.correlation_id else None,
            source_module=event.source_module,
            payload=event.payload,
            sandbox=getattr(event, "sandbox", False),
        )


T = TypeVar("T", bound=EventBase)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Blocking requests after failures
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for Kafka resilience.
    
    Prevents cascading failures by opening the circuit after a threshold
    of failures, then attempting to close it after a timeout period.
    
    Args:
        failure_threshold: Number of failures before opening circuit (default: 5)
        timeout_seconds: Time to wait before attempting reset (default: 60)
    """
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Raises:
            Exception: If circuit is OPEN and timeout not elapsed
        """
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                raise Exception(
                    f"Circuit breaker OPEN. Retry after {self.timeout_seconds - int(elapsed)}s"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise
    
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Async version of call() for async functions."""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                if self.last_failure_time:
                    elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                    raise Exception(
                        f"Circuit breaker OPEN. Retry after {self.timeout_seconds - int(elapsed)}s"
                    )
                raise Exception(f"Circuit breaker OPEN. Retry after {self.timeout_seconds}s")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return False
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout_seconds
    
    def _on_success(self):
        """Reset failure count and close circuit on success."""
        self.failure_count = 0
        if self.state != CircuitBreakerState.CLOSED:
            logger.info(f"Circuit breaker transitioning to CLOSED (was {self.state})")
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self):
        """Increment failure count and open circuit if threshold reached."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitBreakerState.OPEN:
                logger.warning(
                    f"Circuit breaker opening after {self.failure_count} failures. "
                    f"Will retry after {self.timeout_seconds}s"
                )
            self.state = CircuitBreakerState.OPEN


class KafkaProducerClient:
    """
    Async Kafka producer for publishing events.
    
    Usage:
        producer = KafkaProducerClient()
        await producer.start()
        await producer.publish(Topics.SCHEDULE_CREATED, event)
        await producer.stop()
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self._producer: Optional[AIOKafkaProducer] = None
        self._started = False
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
    
    async def start(self) -> None:
        """Start the producer."""
        if self._started:
            return
        
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
            max_batch_size=16384,
            linger_ms=10,
        )
        
        await self._producer.start()
        self._started = True
        logger.info("Kafka producer started")
    
    async def stop(self) -> None:
        """Stop the producer."""
        if self._producer and self._started:
            await self._producer.stop()
            self._started = False
            logger.info("Kafka producer stopped")
    
    async def publish(
        self,
        topic: str,
        event: EventBase,
        key: Optional[str] = None,
        aggregate_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Publish an event to a topic with retry and circuit breaker.
        
        Args:
            topic: Kafka topic name
            event: Event to publish
            key: Optional partition key (defaults to tenant_id or aggregate_id)
            aggregate_id: Aggregate ID for partitioning (ensures ordering per aggregate)
            idempotency_key: Optional idempotency key for deduplication
        
        Returns:
            Dict with status, message_id, and metadata
            
        Raises:
            Exception: If all retries fail or circuit breaker is open
        """
        if not self._started:
            await self.start()
        
        envelope = EventEnvelope.from_event(event)
        # Use aggregate_id for partitioning to ensure ordering per aggregate
        partition_key = key or aggregate_id or str(event.tenant_id)
        message_id = idempotency_key or str(event.event_id)
        
        # Add message_id to envelope for idempotency tracking
        envelope_dict = envelope.model_dump()
        envelope_dict["message_id"] = message_id
        
        # Retry with exponential backoff
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                # Use circuit breaker
                result = await self.circuit_breaker.call_async(
                    self._producer.send_and_wait,
                    topic,
                    value=envelope_dict,
                    key=partition_key.encode("utf-8") if partition_key else None,
                )
                
                # Get record metadata
                record_metadata = result
                
                logger.info(
                    f"Published event {event.event_id} to {topic} "
                    f"(offset={record_metadata.offset}, partition={record_metadata.partition}, "
                    f"attempt={attempt + 1})"
                )
                
                return {
                    "status": "published",
                    "message_id": message_id,
                    "kafka_offset": record_metadata.offset,
                    "partition": record_metadata.partition,
                    "topic": topic,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            
            except (KafkaError, Exception) as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    # Sprint S5: exponential backoff capped at 60s. Without
                    # the cap, attempt 10 with backoff_factor=2 burned 17
                    # minutes per retry.
                    wait_time = min(self.backoff_factor ** attempt, 60.0)
                    logger.warning(
                        f"Publish attempt {attempt + 1}/{self.max_retries + 1} failed for "
                        f"event {event.event_id}: {e}. Retrying in {wait_time:.2f}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to publish event {event.event_id} after "
                        f"{self.max_retries + 1} attempts: {e}"
                    )
        
        # All retries exhausted
        raise Exception(f"Failed to publish event after {self.max_retries + 1} attempts") from last_exception
    
    async def publish_batch(
        self,
        topic: str,
        events: List[EventBase],
        aggregate_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Publish multiple events to a topic.
        
        Args:
            topic: Kafka topic name
            events: List of events to publish
            aggregate_id: Optional aggregate ID for partitioning (if all events belong to same aggregate)
        
        Returns:
            List of publish results (one per event)
        """
        if not self._started:
            await self.start()
        
        results = []
        for event in events:
            try:
                result = await self.publish(
                    topic=topic,
                    event=event,
                    aggregate_id=aggregate_id or str(event.tenant_id),
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to publish event {event.event_id} in batch: {e}")
                results.append({
                    "status": "failed",
                    "event_id": str(event.event_id),
                    "error": str(e),
                })
        
        return results


EventHandler = Callable[[EventEnvelope], Any]


class KafkaConsumerClient:
    """
    Async Kafka consumer for subscribing to events.
    
    Usage:
        consumer = KafkaConsumerClient([Topics.SCHEDULE_CREATED])
        consumer.register_handler(Topics.SCHEDULE_CREATED, my_handler)
        await consumer.start()
        await consumer.consume()  # Blocking
    """
    
    def __init__(
        self,
        topics: List[str],
        group_id: Optional[str] = None,
    ):
        self._topics = topics
        self._group_id = group_id or settings.kafka_consumer_group
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._started = False
        self._running = False
    
    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def start(self) -> None:
        """Start the consumer."""
        if self._started:
            return
        
        self._consumer = AIOKafkaConsumer(
            *self._topics,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=self._group_id,
            auto_offset_reset=settings.kafka_auto_offset_reset,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=True,
            auto_commit_interval_ms=5000,
        )
        
        await self._consumer.start()
        self._started = True
        logger.info(f"Kafka consumer started for topics: {self._topics}")
    
    async def stop(self) -> None:
        """Stop the consumer."""
        self._running = False
        if self._consumer and self._started:
            await self._consumer.stop()
            self._started = False
            logger.info("Kafka consumer stopped")
    
    async def consume(self) -> None:
        """
        Start consuming messages.
        
        This is a blocking operation. Call stop() from another task to stop.
        """
        if not self._started:
            await self.start()
        
        self._running = True
        
        try:
            async for message in self._consumer:
                if not self._running:
                    break
                
                try:
                    envelope = EventEnvelope(**message.value)
                    await self._dispatch(envelope)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await self._send_to_dlq(message.value, str(e))
        
        except Exception as e:
            logger.error(f"Consumer error: {e}")
            raise
    
    async def _dispatch(self, envelope: EventEnvelope) -> None:
        """Dispatch event to registered handlers."""
        handlers = self._handlers.get(envelope.event_type, [])
        
        if not handlers:
            logger.warning(f"No handlers for event type: {envelope.event_type}")
            return
        
        for handler in handlers:
            try:
                result = handler(envelope)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Handler error for {envelope.event_type}: {e}")
    
    async def _send_to_dlq(self, message: Dict, error: str) -> None:
        """Send failed message to the DLQ topic.

        Sprint S5: was a logger-only stub. Now publishes to ``Topics.DLQ``
        with the original message embedded in the payload so an operator
        (or a re-drive job) can inspect or replay it.
        """
        try:
            producer = await get_producer()
            await producer._producer.send_and_wait(
                Topics.DLQ,
                value={
                    "original_message": message,
                    "error": error,
                    "dlq_timestamp": datetime.utcnow().isoformat(),
                },
            )
            logger.error(
                "DLQ published (event_id=%s error=%s)",
                message.get("event_id"), error,
            )
        except Exception as exc:  # pragma: no cover — DLQ failure is logged
            logger.exception(
                "DLQ publish failed (event_id=%s error=%s dlq_error=%s)",
                message.get("event_id"), error, exc,
            )


# Global instances
_producer: Optional[KafkaProducerClient] = None
_consumers: Dict[str, KafkaConsumerClient] = {}


async def get_producer() -> KafkaProducerClient:
    """Get or create the global producer."""
    global _producer
    if _producer is None:
        _producer = KafkaProducerClient()
        await _producer.start()
    return _producer


async def publish_event(topic: str, event: EventBase) -> bool:
    """Convenience function to publish an event."""
    producer = await get_producer()
    return await producer.publish(topic, event)


async def shutdown_kafka() -> None:
    """Shutdown all Kafka clients."""
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None
    
    for consumer in _consumers.values():
        await consumer.stop()
    _consumers.clear()


# Health check
async def check_kafka_health() -> bool:
    """Check Kafka connectivity."""
    try:
        producer = await get_producer()
        return producer._started
    except Exception:
        return False

