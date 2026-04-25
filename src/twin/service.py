"""
ProdPlan ONE - Digital Twin Service
====================================

Service layer for managing Twin scenarios with database persistence.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Scenario, ScenarioDelta, ScenarioComparison, ScenarioStatus
from src.factory_data_product.config import BLOCKED_METRICS, TRUST_INDEX, SEMANTIC_LABELS

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TwinService:
    """
    Service for managing Digital Twin scenarios.
    
    Provides CRUD operations with database persistence.
    """
    
    def __init__(self, db: AsyncSession, tenant_id: UUID):
        """
        Initialize service.
        
        Args:
            db: AsyncSession for database operations
            tenant_id: Tenant ID for multi-tenancy
        """
        self.db = db
        self.tenant_id = tenant_id
    
    # =========================================================================
    # Scenario CRUD
    # =========================================================================
    
    async def create_scenario(
        self,
        title: str,
        description: Optional[str] = None,
        base_scenario_id: Optional[UUID] = None,
        created_by: Optional[str] = None,
    ) -> Scenario:
        """
        Create a new scenario.
        
        Args:
            title: Scenario title
            description: Optional description
            base_scenario_id: Optional ID of scenario to clone from
            created_by: User creating the scenario
            
        Returns:
            Created Scenario
        """
        # Get baseline state
        baseline_state = self._create_baseline_state()
        
        # Clone deltas from base scenario if specified
        cloned_deltas = []
        if base_scenario_id:
            base_scenario = await self.get_scenario(base_scenario_id)
            if base_scenario:
                for delta in base_scenario.deltas:
                    cloned_deltas.append({
                        "entity_type": delta.entity_type,
                        "entity_key": delta.entity_key,
                        "patch": delta.patch,
                        "description": delta.description,
                    })
        
        # Create scenario
        scenario = Scenario(
            tenant_id=self.tenant_id,
            title=title,
            description=description,
            status=ScenarioStatus.DRAFT.value,
            base_scenario_id=base_scenario_id,
            baseline_state=baseline_state,
            created_by=created_by,
        )
        
        self.db.add(scenario)
        await self.db.flush()
        
        # Add cloned deltas
        for i, delta_data in enumerate(cloned_deltas):
            delta = ScenarioDelta(
                tenant_id=self.tenant_id,
                scenario_id=scenario.id,
                sequence=i,
                entity_type=delta_data["entity_type"],
                entity_key=delta_data["entity_key"],
                patch=delta_data["patch"],
                description=delta_data.get("description"),
                applied_by=created_by,
            )
            self.db.add(delta)
        
        await self.db.commit()
        await self.db.refresh(scenario)
        
        logger.info(f"Created scenario: {scenario.id}")
        return scenario
    
    async def get_scenario(self, scenario_id: UUID) -> Optional[Scenario]:
        """Get a scenario by ID."""
        result = await self.db.execute(
            select(Scenario).where(
                and_(
                    Scenario.id == scenario_id,
                    Scenario.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_scenarios(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Scenario]:
        """List scenarios with optional status filter."""
        query = select(Scenario).where(Scenario.tenant_id == self.tenant_id)
        
        if status:
            query = query.where(Scenario.status == status)
        
        query = query.order_by(Scenario.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def delete_scenario(self, scenario_id: UUID) -> bool:
        """Delete a scenario."""
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            return False
        
        await self.db.delete(scenario)
        await self.db.commit()
        
        logger.info(f"Deleted scenario: {scenario_id}")
        return True
    
    # =========================================================================
    # Delta Operations
    # =========================================================================
    
    async def apply_delta(
        self,
        scenario_id: UUID,
        entity_type: str,
        entity_key: str,
        patch: Dict[str, Any],
        description: Optional[str] = None,
        applied_by: Optional[str] = None,
    ) -> ScenarioDelta:
        """
        Apply a delta to a scenario.
        
        Args:
            scenario_id: ID of the scenario
            entity_type: Type of entity being modified
            entity_key: Identifier of the entity
            patch: Changes to apply
            description: Optional description
            applied_by: User applying the delta
            
        Returns:
            Created ScenarioDelta
        """
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        if scenario.status not in [ScenarioStatus.DRAFT.value, ScenarioStatus.SIMULATED.value]:
            raise ValueError(f"Cannot apply delta to scenario with status {scenario.status}")
        
        # Get next sequence number
        max_sequence = max((d.sequence for d in scenario.deltas), default=-1)
        
        # Create delta
        delta = ScenarioDelta(
            tenant_id=self.tenant_id,
            scenario_id=scenario_id,
            sequence=max_sequence + 1,
            entity_type=entity_type,
            entity_key=entity_key,
            patch=patch,
            description=description,
            applied_by=applied_by,
        )
        
        self.db.add(delta)
        
        # Reset scenario status
        scenario.status = ScenarioStatus.DRAFT.value
        scenario.simulation_result = None
        scenario.scenario_hash = None
        
        await self.db.commit()
        await self.db.refresh(delta)
        
        logger.info(f"Applied delta to scenario {scenario_id}: {entity_type}/{entity_key}")
        return delta
    
    # =========================================================================
    # Simulation
    # =========================================================================
    
    async def simulate(self, scenario_id: UUID) -> Dict[str, Any]:
        """
        Run simulation on a scenario.
        
        Applies all deltas to baseline state and calculates resulting KPIs.
        
        Args:
            scenario_id: ID of the scenario to simulate
            
        Returns:
            Simulation result with before/after KPIs
        """
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        # Mark as simulating
        scenario.status = ScenarioStatus.SIMULATING.value
        await self.db.commit()
        
        try:
            # Start with baseline state
            current_state = scenario.baseline_state.copy()
            
            # Apply all deltas in sequence
            for delta in sorted(scenario.deltas, key=lambda d: d.sequence):
                current_state = self._apply_delta_to_state(current_state, {
                    "entity_type": delta.entity_type,
                    "entity_key": delta.entity_key,
                    "patch": delta.patch,
                })
            
            # Calculate deltas
            delta_summary = self._calculate_kpi_deltas(scenario.baseline_state, current_state)
            
            # Build result
            simulation_result = {
                "before": scenario.baseline_state,
                "after": current_state,
                "delta_summary": delta_summary,
                "simulated_at": datetime.utcnow().isoformat(),
            }
            
            # Calculate scenario hash for reproducibility
            scenario_hash = self._calculate_scenario_hash(scenario)
            
            # Update scenario
            scenario.simulation_result = simulation_result
            scenario.simulated_at = datetime.utcnow()
            scenario.scenario_hash = scenario_hash
            scenario.status = ScenarioStatus.SIMULATED.value
            
            await self.db.commit()
            
            logger.info(f"Simulated scenario {scenario_id}")
            return simulation_result
            
        except Exception as e:
            scenario.status = ScenarioStatus.ERROR.value
            await self.db.commit()
            logger.error(f"Simulation failed for scenario {scenario_id}: {e}")
            raise
    
    async def compare(
        self,
        scenario_id: UUID,
        baseline_scenario_id: Optional[UUID] = None,
        compared_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare a scenario against baseline or another scenario.
        
        Args:
            scenario_id: ID of the scenario to compare
            baseline_scenario_id: Optional ID of baseline scenario (uses factory baseline if None)
            compared_by: User performing comparison
            
        Returns:
            Comparison result with KPI deltas
        """
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        # Get baseline state
        if baseline_scenario_id:
            baseline_scenario = await self.get_scenario(baseline_scenario_id)
            if not baseline_scenario:
                raise ValueError(f"Baseline scenario {baseline_scenario_id} not found")
            baseline_state = baseline_scenario.simulation_result.get("after", baseline_scenario.baseline_state) if baseline_scenario.simulation_result else baseline_scenario.baseline_state
        else:
            baseline_state = scenario.baseline_state
        
        # Get scenario state
        scenario_state = scenario.simulation_result.get("after", scenario.baseline_state) if scenario.simulation_result else scenario.baseline_state
        
        # Calculate comparison
        comparison_result = {}
        kpi_deltas = {}
        
        for key in set(baseline_state.keys()) | set(scenario_state.keys()):
            if key.startswith("_"):
                continue
            
            baseline_val = self._extract_value(baseline_state.get(key))
            scenario_val = self._extract_value(scenario_state.get(key))
            
            if baseline_val is not None and scenario_val is not None:
                delta = scenario_val - baseline_val
                comparison_result[key] = {
                    "baseline": baseline_val,
                    "scenario": scenario_val,
                    "delta": delta,
                    "delta_pct": round(delta / baseline_val * 100, 2) if baseline_val != 0 else None,
                }
                kpi_deltas[key] = delta
        
        # Save comparison
        comparison = ScenarioComparison(
            tenant_id=self.tenant_id,
            scenario_id=scenario_id,
            baseline_scenario_id=baseline_scenario_id,
            comparison_result=comparison_result,
            kpi_deltas=kpi_deltas,
            compared_by=compared_by,
        )
        
        self.db.add(comparison)
        await self.db.commit()
        
        return {
            "scenario_id": str(scenario_id),
            "baseline_id": str(baseline_scenario_id) if baseline_scenario_id else "factory_baseline",
            "comparison": comparison_result,
            "compared_at": datetime.utcnow().isoformat(),
        }
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _create_baseline_state(self) -> Dict[str, Any]:
        """
        Create baseline factory state from the Factory Data Product semantic layer.
        Falls back to None values if the data pipeline has not been run.
        """
        sq = None
        try:
            from src.factory_data_product.services.semantic_queries_inmemory import SemanticQueriesInMemory
            sq = SemanticQueriesInMemory()
        except Exception as exc:
            # Sprint Q.7 Fase 4 — was bare `pass`. SQ unavailable → fall
            # back to None values; log so misconfiguration surfaces.
            logger.debug("twin: SemanticQueriesInMemory unavailable: %s", exc)

        def _query_safe(method_name: str) -> Optional[Dict]:
            if sq is None:
                return None
            try:
                result = getattr(sq, method_name)()
                if result and result.get("status") != "BLOCKED":
                    return result
            except Exception as exc:
                # Sprint Q.7 Fase 4 — was bare `pass`. Best-effort
                # query; log under DEBUG.
                logger.debug("twin _query_safe(%s) failed: %s", method_name, exc)
            return None

        wip_data = _query_safe("wip")
        backlog_data = _query_safe("backlog_by_phase")
        bottleneck_data = _query_safe("bottlenecks")
        skills_data = _query_safe("skills_risk")
        quality_data = _query_safe("quality_analysis")
        lead_time_data = _query_safe("lead_time_analysis")

        wip_value = len(wip_data.get("rows", [])) if wip_data else None
        backlog_value = sum(r.get("backlog_horas", 0) for r in backlog_data.get("rows", [])) if backlog_data else None
        bottleneck_value = len(bottleneck_data.get("rows", [])) if bottleneck_data else None
        skills_value = len(skills_data.get("rows", [])) if skills_data else None
        quality_value = sum(r.get("total_erros", 0) for r in quality_data.get("rows", [])) if quality_data else None
        lead_time_value = None
        if lead_time_data and lead_time_data.get("rows"):
            lt_rows = lead_time_data["rows"]
            lead_time_value = round(sum(r.get("lead_time_days", 0) for r in lt_rows) / max(len(lt_rows), 1), 1)

        data_source = "semantic_layer" if sq else "unavailable"

        return {
            "oee": {
                "value": None,
                "status": "BLOCKED",
                "reason": BLOCKED_METRICS["oee_real"]["reason"],
            },
            "availability": {
                "value": None,
                "status": "BLOCKED",
                "reason": BLOCKED_METRICS["availability_oee"]["reason"],
            },
            "otd": {
                "value": None,
                "status": "BLOCKED",
                "reason": BLOCKED_METRICS["otd_official"]["reason"],
            },
            "wip_theoretical": {
                "value": wip_value,
                "unit": "orders",
                "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_structure", 80),
                "semantic_label": SEMANTIC_LABELS["wip"],
                "status": "OK" if wip_value is not None else "NO_DATA",
                "source": data_source,
            },
            "backlog_horas_theoretical": {
                "value": round(backlog_value, 1) if backlog_value else None,
                "unit": "hours",
                "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58),
                "semantic_label": SEMANTIC_LABELS["bottleneck"],
                "status": "WARNING" if backlog_value else "NO_DATA",
                "source": data_source,
            },
            "lead_time_days_observed": {
                "value": lead_time_value,
                "unit": "days",
                "trust_index": TRUST_INDEX.get("OrdensFabrico", 82),
                "semantic_label": SEMANTIC_LABELS["lead_time"],
                "status": "OK" if lead_time_value else "NO_DATA",
                "source": data_source,
            },
            "bottleneck_count": {
                "value": bottleneck_value,
                "unit": "phases",
                "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58),
                "semantic_label": SEMANTIC_LABELS["bottleneck"],
                "status": "WARNING" if bottleneck_value else "NO_DATA",
                "source": data_source,
            },
            "skills_at_risk_count": {
                "value": skills_value,
                "unit": "phases",
                "trust_index": TRUST_INDEX.get("FuncionariosFaseOrdemFabrico", 55),
                "semantic_label": SEMANTIC_LABELS["skills"],
                "status": "WARNING" if skills_value else "NO_DATA",
                "source": data_source,
            },
            "quality_errors_total": {
                "value": quality_value,
                "unit": "errors",
                "trust_index": TRUST_INDEX.get("OrdemFabricoErros", 67),
                "semantic_label": SEMANTIC_LABELS["quality"],
                "status": "WARNING" if quality_value else "NO_DATA",
                "source": data_source,
            },
            "_metadata": {
                "source": "factory_data_product",
                "data_version": data_source,
                "generated_at": datetime.utcnow().isoformat(),
            },
        }
    
    def _apply_delta_to_state(self, state: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a delta to a state and return new state."""
        new_state = state.copy()
        
        entity_type = delta.get("entity_type", "")
        patch = delta.get("patch", {})
        
        if entity_type == "capacity_adjustment":
            if "capacity_increase_pct" in patch:
                increase = patch["capacity_increase_pct"]
                if "backlog_horas_theoretical" in new_state:
                    current = new_state["backlog_horas_theoretical"]
                    if isinstance(current, dict) and current.get("value"):
                        new_state["backlog_horas_theoretical"]["value"] *= (1 - increase / 100)
        
        elif entity_type == "standard_time":
            if "reduction_pct" in patch:
                reduction = patch["reduction_pct"]
                if "backlog_horas_theoretical" in new_state:
                    current = new_state["backlog_horas_theoretical"]
                    if isinstance(current, dict) and current.get("value"):
                        new_state["backlog_horas_theoretical"]["value"] *= (1 - reduction / 100)
        
        elif entity_type == "skills_training":
            if "phases_trained" in patch:
                trained = patch["phases_trained"]
                if "skills_at_risk_count" in new_state:
                    current = new_state["skills_at_risk_count"]
                    if isinstance(current, dict) and current.get("value"):
                        new_state["skills_at_risk_count"]["value"] = max(0, current["value"] - trained)
        
        elif entity_type == "quality_improvement":
            if "error_reduction_pct" in patch:
                reduction = patch["error_reduction_pct"]
                if "quality_errors_total" in new_state:
                    current = new_state["quality_errors_total"]
                    if isinstance(current, dict) and current.get("value"):
                        new_state["quality_errors_total"]["value"] *= (1 - reduction / 100)
        
        elif entity_type == "wip_policy":
            if "wip_limit" in patch:
                limit = patch["wip_limit"]
                if "wip_theoretical" in new_state:
                    current = new_state["wip_theoretical"]
                    if isinstance(current, dict) and current.get("value"):
                        new_state["wip_theoretical"]["value"] = min(current["value"], limit)
        
        return new_state
    
    def _calculate_kpi_deltas(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate delta summary between two states."""
        deltas = {}
        
        for key in set(before.keys()) | set(after.keys()):
            if key.startswith("_"):
                continue
            
            before_val = self._extract_value(before.get(key))
            after_val = self._extract_value(after.get(key))
            
            if before_val is not None and after_val is not None:
                deltas[f"{key}_change"] = after_val - before_val
        
        return deltas
    
    def _extract_value(self, item: Any) -> Optional[float]:
        """Extract numeric value from a KPI item."""
        if item is None:
            return None
        if isinstance(item, (int, float)):
            return float(item)
        if isinstance(item, dict):
            val = item.get("value")
            if val is not None and item.get("status") != "BLOCKED":
                return float(val)
        return None
    
    def _calculate_scenario_hash(self, scenario: Scenario) -> str:
        """
        Calculate deterministic SHA256 hash for scenario reproducibility.
        
        This hash guarantees that:
        1. Same baseline + same deltas = same hash
        2. Same hash = reproducible simulation result
        3. Any change in baseline or deltas changes the hash
        
        The hash is computed from:
        - baseline_state (sorted JSON)
        - deltas (ordered by sequence, sorted JSON)
        """
        # Calculate baseline hash
        baseline_hash = self._calculate_state_hash(scenario.baseline_state)
        
        # Calculate deltas hash (ordered)
        deltas_data = [
            {
                "sequence": d.sequence,
                "entity_type": d.entity_type,
                "entity_key": d.entity_key,
                "patch": d.patch,
            }
            for d in sorted(scenario.deltas, key=lambda d: d.sequence)
        ]
        deltas_json = json.dumps(deltas_data, sort_keys=True, default=str)
        deltas_hash = hashlib.sha256(deltas_json.encode()).hexdigest()
        
        # Combine hashes
        combined = f"{baseline_hash}|{deltas_hash}"
        scenario_hash = hashlib.sha256(combined.encode()).hexdigest()
        
        return scenario_hash
    
    def _calculate_state_hash(self, state: Dict[str, Any]) -> str:
        """Calculate hash for a state dictionary."""
        # Remove metadata fields that don't affect reproducibility
        clean_state = {
            k: v for k, v in state.items() 
            if not k.startswith("_") and k not in ["generated_at", "computed_at"]
        }
        json_str = json.dumps(clean_state, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def _calculate_result_hash(self, result: Dict[str, Any]) -> str:
        """Calculate hash for simulation result."""
        # Only hash the 'after' state (the result)
        if "after" in result:
            return self._calculate_state_hash(result["after"])
        return ""
    
    # =========================================================================
    # Solver
    # =========================================================================

    async def solve(
        self,
        scenario_id: UUID,
        objective: str = "maximize_oee",
        operations: Optional[List[Dict[str, Any]]] = None,
        machines: Optional[List[Dict[str, Any]]] = None,
        time_limit_sec: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Run optimization on a scenario.

        If `operations` and `machines` are provided, run CP-SAT via SchedulingAdapter
        to produce a real schedule. Otherwise, return the delta-applied projected state
        with status=INSUFFICIENT_DATA (no mock KPIs).
        """
        import asyncio

        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        # Apply deltas deterministically to get projected state
        projected_state = dict(scenario.baseline_state)
        for delta in sorted(scenario.deltas, key=lambda d: d.sequence):
            projected_state = self._apply_delta_to_state(projected_state, {
                "entity_type": delta.entity_type,
                "entity_key": delta.entity_key,
                "patch": delta.patch,
            })

        # Case 1: Real scheduling input → run CP-SAT
        if operations and machines:
            try:
                schedule_result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._run_cpsat, operations, machines, time_limit_sec
                    ),
                    timeout=time_limit_sec + 5.0,
                )
                return {
                    "scenario_id": str(scenario_id),
                    "objective": objective,
                    "status": "SOLVED",
                    "engine_used": "cpsat",
                    "schedule": schedule_result,
                    "projected_kpis": projected_state,
                    "solved_at": datetime.utcnow().isoformat(),
                }
            except asyncio.TimeoutError:
                logger.warning(f"CP-SAT timed out for scenario {scenario_id}")
                return {
                    "scenario_id": str(scenario_id),
                    "objective": objective,
                    "status": "SOLVER_TIMEOUT",
                    "time_limit_sec": time_limit_sec,
                    "projected_kpis": projected_state,
                    "solved_at": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                logger.error(f"Solver error for scenario {scenario_id}: {e}", exc_info=True)
                return {
                    "scenario_id": str(scenario_id),
                    "objective": objective,
                    "status": "SOLVER_ERROR",
                    "error": str(e),
                    "projected_kpis": projected_state,
                    "solved_at": datetime.utcnow().isoformat(),
                }

        # Case 2: No scheduling input → return delta-projection only
        return {
            "scenario_id": str(scenario_id),
            "objective": objective,
            "status": "INSUFFICIENT_DATA",
            "reason": (
                "CP-SAT requires operations[] and machines[] in the request. "
                "The scenario baseline alone is not enough to run scheduling — "
                "supply structured scheduling input or rely on delta-only projection."
            ),
            "projected_kpis": projected_state,
            "solved_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _run_cpsat(
        operations: List[Dict[str, Any]],
        machines: List[Dict[str, Any]],
        time_limit_sec: float,
    ) -> Dict[str, Any]:
        """Run CP-SAT synchronously (invoked via asyncio.to_thread)."""
        from src.plan.engines.scheduling_adapter import (
            SchedulingAdapter,
            SchedulerEngine,
            SchedulingOperation,
            SchedulingMachine,
        )
        from datetime import timedelta

        def _parse_dt(value: Any) -> Optional[datetime]:
            if value is None or isinstance(value, datetime):
                return value if isinstance(value, datetime) else None
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    return None
            return None

        op_objs = [
            SchedulingOperation(
                operation_id=o["operation_id"],
                order_id=o["order_id"],
                product_id=o.get("product_id", ""),
                sequence=o.get("sequence", 0),
                operation_code=o.get("operation_code", ""),
                duration_minutes=float(o["duration_minutes"]),
                machine_id=o.get("machine_id"),
                setup_family=o.get("setup_family", ""),
                due_date=_parse_dt(o.get("due_date")),
                priority=float(o.get("priority", 1.0)),
                predecessor_ops=o.get("predecessor_ops") or [],
            )
            for o in operations
        ]
        machine_objs = [
            SchedulingMachine(
                machine_id=m["machine_id"],
                name=m.get("name", m["machine_id"]),
                capacity=int(m.get("capacity", 1)),
                speed_factor=float(m.get("speed_factor", 1.0)),
            )
            for m in machines
        ]
        horizon_start = datetime.utcnow()
        horizon_end = horizon_start + timedelta(weeks=4)

        adapter = SchedulingAdapter()
        adapter.configure(engine=SchedulerEngine.CPSAT, time_limit_sec=time_limit_sec)
        result = adapter.schedule(op_objs, machine_objs, horizon_start, horizon_end)
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)

    # =========================================================================
    # Serialization
    # =========================================================================

    @staticmethod
    def scenario_to_dict(scenario: Scenario) -> Dict[str, Any]:
        """Serialize a Scenario to a plain dict (for API responses)."""
        return {
            "id": str(scenario.id),
            "tenant_id": str(scenario.tenant_id),
            "title": scenario.title,
            "description": scenario.description,
            "status": scenario.status,
            "base_scenario_id": str(scenario.base_scenario_id) if scenario.base_scenario_id else None,
            "baseline_state": scenario.baseline_state,
            "simulation_result": scenario.simulation_result,
            "scenario_hash": scenario.scenario_hash,
            "created_by": scenario.created_by,
            "created_at": scenario.created_at.isoformat() if scenario.created_at else None,
            "updated_at": scenario.updated_at.isoformat() if scenario.updated_at else None,
            "simulated_at": scenario.simulated_at.isoformat() if scenario.simulated_at else None,
            "deltas": [
                {
                    "id": str(d.id),
                    "sequence": d.sequence,
                    "entity_type": d.entity_type,
                    "entity_key": d.entity_key,
                    "patch": d.patch,
                    "description": d.description,
                    "applied_by": d.applied_by,
                    "applied_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in sorted(scenario.deltas or [], key=lambda x: x.sequence)
            ],
        }

    def get_audit_hashes(self, scenario: Scenario) -> Dict[str, str]:
        """
        Get all hashes for audit/reproducibility.
        
        Returns:
            Dict with baseline_hash, deltas_hash, scenario_hash, result_hash
        """
        baseline_hash = self._calculate_state_hash(scenario.baseline_state)
        
        deltas_data = [
            {
                "sequence": d.sequence,
                "entity_type": d.entity_type,
                "entity_key": d.entity_key,
                "patch": d.patch,
            }
            for d in sorted(scenario.deltas, key=lambda d: d.sequence)
        ]
        deltas_json = json.dumps(deltas_data, sort_keys=True, default=str)
        deltas_hash = hashlib.sha256(deltas_json.encode()).hexdigest()
        
        scenario_hash = scenario.scenario_hash or self._calculate_scenario_hash(scenario)
        
        result_hash = ""
        if scenario.simulation_result:
            result_hash = self._calculate_result_hash(scenario.simulation_result)
        
        return {
            "baseline_hash": baseline_hash[:16],  # Short for display
            "baseline_hash_full": baseline_hash,
            "deltas_hash": deltas_hash[:16],
            "deltas_hash_full": deltas_hash,
            "scenario_hash": scenario_hash[:16],
            "scenario_hash_full": scenario_hash,
            "result_hash": result_hash[:16] if result_hash else None,
            "result_hash_full": result_hash if result_hash else None,
            "is_reproducible": True,
            "algorithm": "sha256",
        }

