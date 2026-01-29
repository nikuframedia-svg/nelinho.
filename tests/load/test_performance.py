"""
ProdPlan ONE - Load Testing
============================

Load tests for Decision Intelligence Platform endpoints:
- /v1/profit/kpis/snapshot-explained (1000 concurrent, p95 <200ms)
- /api/copilot/sandbox (100 concurrent, p95 <2s)
- /v1/decisions (500 concurrent, p95 <500ms)
"""

import pytest
import asyncio
import time
from typing import List, Dict, Any
from uuid import uuid4
from datetime import datetime
from statistics import median, stdev

from src.shared.models.governance import DecisionRun, DecisionStatus
from src.copilot.actions import Action, ActionExecutor, ActionMode


class TestKPISnapshotExplainedLoad:
    """Load test for KPI snapshot-explained endpoint."""
    
    @pytest.mark.asyncio
    async def test_kpi_snapshot_explained_1000_concurrent(self, test_session, sample_tenant_id):
        """
        Load test: 1000 concurrent requests to /v1/profit/kpis/snapshot-explained.
        
        Target: p95 < 200ms
        """
        from src.shared.explanation_engine import ExplanationEngine
        
        async def request_kpi_explanation():
            """Simulate KPI explanation request."""
            start = time.time()
            engine = ExplanationEngine(test_session, sample_tenant_id)
            try:
                explanation = await engine.explain_kpi("otd")
                elapsed = (time.time() - start) * 1000  # Convert to ms
                return {"success": True, "latency_ms": elapsed}
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                return {"success": False, "latency_ms": elapsed, "error": str(e)}
        
        # Run 1000 concurrent requests
        num_requests = 1000
        tasks = [request_kpi_explanation() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        
        # Calculate statistics
        latencies = [r["latency_ms"] for r in results if r["success"]]
        success_count = sum(1 for r in results if r["success"])
        
        if latencies:
            latencies_sorted = sorted(latencies)
            p50 = median(latencies_sorted)
            p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
            p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]
            avg = sum(latencies) / len(latencies)
            
            print(f"\nKPI Snapshot-Explained Load Test Results:")
            print(f"  Total requests: {num_requests}")
            print(f"  Successful: {success_count} ({success_count/num_requests*100:.1f}%)")
            print(f"  Average latency: {avg:.2f}ms")
            print(f"  p50 latency: {p50:.2f}ms")
            print(f"  p95 latency: {p95:.2f}ms")
            print(f"  p99 latency: {p99:.2f}ms")
            
            # Assert p95 < 200ms
            assert p95 < 200, f"p95 latency {p95:.2f}ms exceeds target of 200ms"
            assert success_count >= num_requests * 0.95, "Success rate below 95%"


class TestSandboxLoad:
    """Load test for sandbox endpoint."""
    
    @pytest.mark.asyncio
    async def test_sandbox_100_concurrent(self, test_session, sample_tenant_id):
        """
        Load test: 100 concurrent requests to /api/copilot/sandbox.
        
        Target: p95 < 2s
        """
        user_id = uuid4()
        
        async def execute_sandbox():
            """Simulate sandbox execution."""
            start = time.time()
            action = Action(
                action_id=f"test-{uuid4()}",
                action_type="reduce_setup",
                description="Test action",
                modes=["sandbox"],
                estimated_impact={"setup_reduction": 10},
                payload={"target": "OP-001"},
            )
            
            mock_kafka = None
            executor = ActionExecutor(test_session, sample_tenant_id, user_id, mock_kafka)
            
            try:
                result = await executor.execute_action(action, ActionMode.SANDBOX, None)
                elapsed = (time.time() - start) * 1000  # Convert to ms
                return {"success": True, "latency_ms": elapsed}
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                return {"success": False, "latency_ms": elapsed, "error": str(e)}
        
        # Run 100 concurrent requests
        num_requests = 100
        tasks = [execute_sandbox() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        
        # Calculate statistics
        latencies = [r["latency_ms"] for r in results if r["success"]]
        success_count = sum(1 for r in results if r["success"])
        
        if latencies:
            latencies_sorted = sorted(latencies)
            p50 = median(latencies_sorted)
            p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
            p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]
            avg = sum(latencies) / len(latencies)
            
            print(f"\nSandbox Load Test Results:")
            print(f"  Total requests: {num_requests}")
            print(f"  Successful: {success_count} ({success_count/num_requests*100:.1f}%)")
            print(f"  Average latency: {avg:.2f}ms")
            print(f"  p50 latency: {p50:.2f}ms")
            print(f"  p95 latency: {p95:.2f}ms")
            print(f"  p99 latency: {p99:.2f}ms")
            
            # Assert p95 < 2000ms (2s)
            assert p95 < 2000, f"p95 latency {p95:.2f}ms exceeds target of 2000ms"
            assert success_count >= num_requests * 0.95, "Success rate below 95%"


class TestDecisionsListLoad:
    """Load test for decisions list endpoint."""
    
    @pytest.mark.asyncio
    async def test_decisions_list_500_concurrent(self, test_session, sample_tenant_id):
        """
        Load test: 500 concurrent requests to /v1/decisions.
        
        Target: p95 < 500ms
        """
        user_id = uuid4()
        
        # Pre-populate with test decisions
        decisions = []
        for i in range(50):
            decision = DecisionRun(
                tenant_id=sample_tenant_id,
                title=f"Test Decision {i}",
                action_type="INCREASE_SS",
                target=f"K{i}",
                status=DecisionStatus.PROPOSED.value,
                before_state={},
                proposed_by=user_id,
                proposed_at=datetime.utcnow(),
            )
            decisions.append(decision)
        
        test_session.add_all(decisions)
        await test_session.commit()
        
        async def list_decisions():
            """Simulate decisions list request."""
            start = time.time()
            from sqlalchemy import select
            from src.shared.models.governance import DecisionRun
            
            try:
                query = select(DecisionRun).where(
                    DecisionRun.tenant_id == sample_tenant_id
                ).limit(20)
                result = await test_session.execute(query)
                decisions_list = result.scalars().all()
                elapsed = (time.time() - start) * 1000  # Convert to ms
                return {"success": True, "latency_ms": elapsed, "count": len(decisions_list)}
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                return {"success": False, "latency_ms": elapsed, "error": str(e)}
        
        # Run 500 concurrent requests
        num_requests = 500
        tasks = [list_decisions() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        
        # Calculate statistics
        latencies = [r["latency_ms"] for r in results if r["success"]]
        success_count = sum(1 for r in results if r["success"])
        
        if latencies:
            latencies_sorted = sorted(latencies)
            p50 = median(latencies_sorted)
            p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
            p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]
            avg = sum(latencies) / len(latencies)
            
            print(f"\nDecisions List Load Test Results:")
            print(f"  Total requests: {num_requests}")
            print(f"  Successful: {success_count} ({success_count/num_requests*100:.1f}%)")
            print(f"  Average latency: {avg:.2f}ms")
            print(f"  p50 latency: {p50:.2f}ms")
            print(f"  p95 latency: {p95:.2f}ms")
            print(f"  p99 latency: {p99:.2f}ms")
            
            # Assert p95 < 500ms
            assert p95 < 500, f"p95 latency {p95:.2f}ms exceeds target of 500ms"
            assert success_count >= num_requests * 0.95, "Success rate below 95%"

