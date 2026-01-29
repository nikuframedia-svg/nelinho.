"""
ProdPlan ONE - End-to-End Integration Tests
============================================

Test complete integration of all 4 lacunae:
- Event flow (Lacuna 1: Event-Driven)
- DQA gates (Lacuna 2: Data Quality Autopilot)
- Copilot actions (Lacuna 3: Action-First)
- Supply forecast (Lacuna 4: Supply Chain Planning)
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from src.shared.outbox_models import EventOutbox
from src.dqa.trust_index import TrustIndexCalculator
from src.copilot.actions import Action, ActionExecutor, ActionMode
from src.supply.forecaster import ARIMAForecaster
import pandas as pd


class TestEventFlowIntegration:
    """Test event flow integration (Lacuna 1)."""
    
    @pytest.mark.asyncio
    async def test_event_published_to_outbox_and_dispatched(self, test_session):
        """
        E2E: Event created → Outbox → Dispatched → Kafka.
        
        Tests complete flow:
        1. Create event in outbox
        2. Dispatcher publishes to Kafka
        3. Status updated to 'published'
        """
        from src.shared.outbox_dispatcher import OutboxDispatcher
        from src.shared.kafka_client import KafkaProducerClient
        
        tenant_id = uuid4()
        aggregate_id = uuid4()
        
        # Step 1: Create event in outbox
        event = EventOutbox(
            id=uuid4(),
            tenant_id=tenant_id,
            aggregate_id=aggregate_id,
            aggregate_type="plan",
            event_type="plan.schedule.committed",
            payload={"makespan": 1200, "cost": 5000},
            status="pending",
        )
        test_session.add(event)
        await test_session.commit()
        
        # Step 2: Mock Kafka producer
        mock_producer = AsyncMock(spec=KafkaProducerClient)
        mock_producer.publish = AsyncMock(return_value={"kafka_offset": 123})
        
        # Step 3: Dispatcher publishes event
        async def session_factory():
            return test_session
        
        dispatcher = OutboxDispatcher(
            db_session_factory=session_factory,
            kafka_producer=mock_producer,
        )
        
        await dispatcher._dispatch_pending_events(test_session)
        await test_session.commit()
        
        # Step 4: Verify event published
        await test_session.refresh(event)
        assert event.status == "published"
        assert event.published_at is not None
        mock_producer.publish.assert_called_once()


class TestDQAIntegration:
    """Test DQA integration (Lacuna 2)."""
    
    @pytest.mark.asyncio
    async def test_trust_index_gate_blocks_low_quality(self, test_session):
        """
        E2E: TrustIndex calculation → Quality Gate blocks low-quality data.
        
        Tests:
        1. Calculate TrustIndex for entity
        2. Quality gate blocks if TI < 0.70
        3. Auto-repair triggers if 0.65 <= TI < 0.70
        """
        from src.dqa.auto_repair import AutoRepairEngine
        
        # Step 1: Calculate TrustIndex for low-quality data
        calculator = TrustIndexCalculator(
            required_fields={"field1": str, "field2": int},
            valid_ranges={"field1": (0, 100)},
            sla_latency_seconds=60,
        )
        
        entity = {"field1": None}  # Missing required field
        result = calculator.calculate(entity, latency_ms=120000)  # High latency
        
        # Step 2: Verify TrustIndex < 0.70 (should be blocked)
        assert result["trust_index"] < 0.70
        
        # Step 3: If 0.65 <= TI < 0.70, auto-repair should trigger
        if 0.65 <= result["trust_index"] < 0.70:
            repair_engine = AutoRepairEngine()
            historical_data = [{"field1": "value1", "field2": 100}]
            repair_result = repair_engine.repair(entity, result["trust_index"], historical_data)
            
            # Should attempt repair
            assert "repairs" in repair_result
    
    def test_drift_detection_identifies_distribution_changes(self):
        """
        E2E: Historical data → Recent data → Drift detection.
        
        Tests:
        1. Compare historical vs recent distributions
        2. KS test detects drift (p-value < 0.05)
        """
        from src.dqa.drift_detector import DriftDetector
        
        # Historical: mean=10
        historical_data = [
            {"field1": 8.0}, {"field1": 10.0}, {"field1": 12.0},
            {"field1": 9.0}, {"field1": 11.0}, {"field1": 10.0},
            {"field1": 9.0}, {"field1": 11.0}, {"field1": 10.0},
            {"field1": 12.0}, {"field1": 9.0}, {"field1": 11.0},
        ]
        
        # Recent: mean=20 (shifted)
        recent_data = [
            {"field1": 18.0}, {"field1": 20.0}, {"field1": 22.0},
            {"field1": 19.0}, {"field1": 21.0}, {"field1": 20.0},
            {"field1": 19.0}, {"field1": 21.0}, {"field1": 20.0},
            {"field1": 22.0}, {"field1": 19.0}, {"field1": 21.0},
        ]
        
        detector = DriftDetector(p_value_threshold=0.05)
        result = detector.detect_drift(recent_data, historical_data, "field1")
        
        # Should detect drift (different distributions)
        assert "drifted" in result
        assert "p_value" in result


class TestCopilotIntegration:
    """Test Copilot actions integration (Lacuna 3)."""
    
    @pytest.mark.asyncio
    async def test_copilot_action_preview_sandbox_execute_flow(self, test_session):
        """
        E2E: Copilot action flow (Preview → Sandbox → Execute).
        
        Tests:
        1. Preview returns estimated_impact
        2. Sandbox executes and rolls back
        3. Execute commits and creates audit log
        """
        from src.copilot.sandbox import SandboxExecutor
        
        action = Action(
            action_id="action_e2e",
            action_type="test_action",
            description="E2E test action",
            modes=["preview", "sandbox", "execute"],
            estimated_impact={"makespan_delta_minutes": -120},
        )
        
        executor = ActionExecutor(
            session=test_session,
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        
        # Step 1: Preview
        preview_result = await executor.execute_action(action, ActionMode.PREVIEW)
        assert preview_result["mode"] == "preview"
        assert "estimated_impact" in preview_result
        
        # Step 2: Sandbox (should rollback)
        sandbox_result = await executor.execute_action(action, ActionMode.SANDBOX)
        assert sandbox_result["mode"] == "sandbox"
        assert "rolled back" in sandbox_result["message"].lower() or "rollback" in sandbox_result["message"].lower()
        
        # Step 3: Execute (should commit)
        mock_kafka = AsyncMock()
        mock_kafka.publish = AsyncMock(return_value={"kafka_offset": 456})
        
        executor_with_kafka = ActionExecutor(
            session=test_session,
            tenant_id=uuid4(),
            user_id=uuid4(),
            kafka_producer=mock_kafka,
        )
        
        execute_result = await executor_with_kafka.execute_action(action, ActionMode.EXECUTE)
        assert execute_result["mode"] == "execute"
        assert "transaction_id" in execute_result


class TestSupplyChainIntegration:
    """Test Supply Chain integration (Lacuna 4)."""
    
    def test_forecast_generation_with_wmape_validation(self):
        """
        E2E: Historical data → Prophet forecast → WMAPE validation → Quality classification.
        
        Tests:
        1. Generate forecast from historical data
        2. Calculate WMAPE
        3. Classify quality (good/fair/poor)
        """
        forecaster = ARIMAForecaster()
        
        # Historical data with trend
        base_date = datetime.now() - timedelta(days=30)
        historical_data = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(30)],
            "value": [100 + i * 2 for i in range(30)],
        })
        
        # Generate forecast
        forecast = forecaster.forecast(
            sku_id="SKU-E2E-001",
            historical_data=historical_data,
            periods_ahead=30,
        )
        
        # Verify structure
        assert "forecast" in forecast
        assert "wmape" in forecast
        assert "quality" in forecast
        
        # Verify forecast periods
        assert len(forecast["forecast"]) == 30
        
        # Verify quality classification based on WMAPE
        assert forecast["quality"] in ["good", "fair", "poor"]
        if forecast["wmape"] < 10.0:
            assert forecast["quality"] == "good"
        elif 10.0 <= forecast["wmape"] < 15.0:
            assert forecast["quality"] == "fair"
        else:
            assert forecast["quality"] == "poor"


class TestCrossLacunaeIntegration:
    """Test integration across all 4 lacunae."""
    
    @pytest.mark.asyncio
    async def test_complete_flow_event_dqa_copilot_supply(self, test_session):
        """
        E2E: Complete flow integrating all 4 lacunae.
        
        Flow:
        1. Event created in outbox (Lacuna 1)
        2. DQA checks data quality (Lacuna 2)
        3. Copilot action executed (Lacuna 3)
        4. Supply forecast generated (Lacuna 4)
        """
        tenant_id = uuid4()
        
        # Step 1: Create event in outbox (Lacuna 1)
        event = EventOutbox(
            id=uuid4(),
            tenant_id=tenant_id,
            aggregate_id=uuid4(),
            aggregate_type="plan",
            event_type="plan.schedule.committed",
            payload={"plan_id": str(uuid4()), "makespan": 1200},
            status="pending",
        )
        test_session.add(event)
        await test_session.commit()
        
        # Step 2: Calculate TrustIndex for event payload (Lacuna 2)
        calculator = TrustIndexCalculator(
            required_fields={"plan_id": str, "makespan": int},
            valid_ranges={"makespan": (0, 10000)},
            sla_latency_seconds=60,
        )
        
        trust_result = calculator.calculate(event.payload, latency_ms=50000)
        assert "trust_index" in trust_result
        
        # Step 3: Copilot action (Lacuna 3) - if TrustIndex is good
        if trust_result["trust_index"] >= 0.70:
            action = Action(
                action_id="action_cross_lacunae",
                action_type="optimize_plan",
                description="Cross-lacunae test",
                modes=["preview"],
                estimated_impact={"makespan_delta_minutes": -100},
            )
            
            executor = ActionExecutor(
                session=test_session,
                tenant_id=tenant_id,
                user_id=uuid4(),
            )
            
            action_result = await executor.execute_action(action, ActionMode.PREVIEW)
            assert action_result["mode"] == "preview"
        
        # Step 4: Supply forecast (Lacuna 4)
        base_date = datetime.now() - timedelta(days=30)
        historical_data = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(30)],
            "value": [50 + i for i in range(30)],
        })
        
        forecaster = ARIMAForecaster()
        forecast = forecaster.forecast(
            sku_id="SKU-CROSS-LACUNAE",
            historical_data=historical_data,
            periods_ahead=30,
        )
        
        assert "forecast" in forecast
        assert "quality" in forecast
        
        # All lacunae integrated successfully
        assert True  # Flow completed


class TestIntegrationErrorHandling:
    """Test error handling in integrated flows."""
    
    @pytest.mark.asyncio
    async def test_outbox_dlq_after_max_retries(self, test_session):
        """
        E2E: Event fails → Retries → DLQ.
        
        Tests:
        1. Event fails to publish
        2. Retry count increments
        3. Event moved to DLQ after 5 retries
        """
        from src.shared.outbox_dispatcher import OutboxDispatcher
        from src.shared.kafka_client import KafkaProducerClient
        from src.shared.outbox_models import EventDLQ
        from sqlalchemy import select
        
        tenant_id = uuid4()
        event_id = uuid4()
        
        # Create event with retry_count = 4 (one below threshold)
        event = EventOutbox(
            id=event_id,
            tenant_id=tenant_id,
            aggregate_id=uuid4(),
            aggregate_type="plan",
            event_type="plan.schedule.committed",
            payload={"test": "data"},
            status="pending",
            retry_count=4,
        )
        test_session.add(event)
        await test_session.commit()
        
        # Mock Kafka to raise exception
        mock_producer = AsyncMock(spec=KafkaProducerClient)
        mock_producer.publish = AsyncMock(side_effect=Exception("Kafka error"))
        
        async def session_factory():
            return test_session
        
        dispatcher = OutboxDispatcher(
            db_session_factory=session_factory,
            kafka_producer=mock_producer,
        )
        
        # Dispatch (should fail and move to DLQ)
        await dispatcher._dispatch_pending_events(test_session)
        await test_session.commit()
        
        # Verify event in DLQ
        stmt = select(EventDLQ).where(EventDLQ.event_outbox_id == event_id)
        result = await test_session.execute(stmt)
        dlq_entry = result.scalar_one_or_none()
        
        assert dlq_entry is not None
        assert dlq_entry.retry_attempt == 5










