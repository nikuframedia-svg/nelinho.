"""
ProdPlan ONE - Scheduling Adapter
==================================

Adapter for scheduling engines.
Supports multiple scheduling algorithms:
- Heuristic (EDD, SPT, FIFO, WSPT) - Fast dispatch rules
- CP-SAT - Optimal constraint programming (Google OR-Tools)
- Genetic - Evolutionary optimization (DEAP)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SchedulerEngine(str, Enum):
    """Available scheduling engines."""
    HEURISTIC = "heuristic"
    MILP = "milp"  # Legacy - not implemented
    CPSAT = "cpsat"
    GENETIC = "genetic"
    CPO_V4 = "cpo_v4"  # Hyper-heuristic DRCFFS-R (NELO, Sprint E)


class DispatchRule(str, Enum):
    """Dispatch rules for heuristic scheduler."""
    FIFO = "fifo"
    SPT = "spt"
    EDD = "edd"
    WSPT = "wspt"


@dataclass
class SchedulingOperation:
    """Input operation for scheduling.

    Extended for CPO v4 (DRCFFS-R) with dual-resource and mold fields.
    Legacy schedulers (heuristic/CPSAT/genetic) ignore the new fields.
    """
    operation_id: str
    order_id: str
    product_id: str
    sequence: int
    operation_code: str
    duration_minutes: float
    machine_id: Optional[str]
    setup_family: str = ""
    due_date: Optional[datetime] = None
    priority: float = 1.0
    predecessor_ops: List[str] = None

    # CPO v4 — dual-resource + NELO-specific fields (default-safe for legacy callers)
    required_skills: List[str] = None
    alternative_machines: List[str] = None
    mold_id: Optional[str] = None
    mold_required: bool = False
    model_id: str = ""
    team_size: int = 1
    phase_id: Optional[str] = None  # fase_id from NELO curated layer

    # Q.116.B — fase com posição alternativa (OR de predecessores).
    is_flexible: bool = False
    allowed_predecessors: List[str] = None   # phase_ids alternativos

    def __post_init__(self):
        if self.predecessor_ops is None:
            self.predecessor_ops = []
        if self.required_skills is None:
            self.required_skills = []
        if self.alternative_machines is None:
            self.alternative_machines = []
        if self.allowed_predecessors is None:
            self.allowed_predecessors = []


@dataclass
class SchedulingMachine:
    """Input machine for scheduling.

    Extended with NELO cost-center and shift calendar; legacy schedulers
    treat these as metadata only.
    """
    machine_id: str
    name: str
    capacity: int = 1
    speed_factor: float = 1.0
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None

    # CPO v4 — NELO specifics
    centro_custo: str = ""
    shift_calendar: Dict[str, Any] = None  # {"morning": True, "afternoon": False, ...}

    def __post_init__(self):
        if self.shift_calendar is None:
            self.shift_calendar = {"morning": True, "afternoon": False, "night": False}


@dataclass
class ScheduledOperation:
    """Output: a scheduled operation."""
    operation_id: str
    order_id: str
    product_id: str
    operation_code: str
    machine_id: str
    start_time: datetime
    end_time: datetime
    duration_minutes: float
    setup_minutes: float = 0.0


class SchedulingResult(BaseModel):
    """Result of scheduling run."""
    success: bool = True
    engine_used: str = "heuristic"
    rule_used: Optional[str] = None
    solve_time_sec: float = 0.0
    status: str = "optimal"

    operations: List[Dict[str, Any]] = Field(default_factory=list)

    makespan_hours: float = 0.0
    total_tardiness_hours: float = 0.0
    num_late_orders: int = 0
    avg_utilization: float = 0.0

    warnings: List[str] = Field(default_factory=list)

    # FASE 1B.2 (CRIT-14) — set to True when the originally requested
    # engine failed and the adapter fell back to a simpler one (e.g.
    # CPO v4 → heuristic). Callers can surface this in the API
    # response so the frontend can warn the user the schedule is not
    # the best one the system would normally produce.
    degraded: bool = False
    fallback_reason: Optional[str] = None


class SchedulingAdapter:
    """
    Adapter for scheduling engines.
    
    Provides a unified interface for different scheduling algorithms:
    - Heuristic: Fast dispatch rules (EDD, SPT, FIFO, WSPT)
    - CP-SAT: Optimal constraint programming using Google OR-Tools
    - Genetic: Evolutionary optimization using DEAP
    
    Usage:
        adapter = SchedulingAdapter()
        adapter.configure(engine=SchedulerEngine.CPSAT, time_limit_sec=30)
        result = adapter.schedule(operations, machines, horizon_start, horizon_end)
    """
    
    def __init__(self):
        self._engine = SchedulerEngine.HEURISTIC
        self._rule = DispatchRule.EDD
        self._time_limit_sec = 60.0
        
        # Lazy-load advanced schedulers
        self._cpsat_scheduler = None
        self._genetic_scheduler = None
    
    def configure(
        self,
        engine: SchedulerEngine = SchedulerEngine.HEURISTIC,
        rule: DispatchRule = DispatchRule.EDD,
        time_limit_sec: float = 60.0,
    ) -> None:
        """Configure the scheduler."""
        self._engine = engine
        self._rule = rule
        self._time_limit_sec = time_limit_sec
    
    def _get_cpsat_scheduler(self):
        """Lazy-load CP-SAT scheduler."""
        if self._cpsat_scheduler is None:
            try:
                from .cpsat_engine import CPSATScheduler, CPSATConfig, is_cpsat_available
                
                if not is_cpsat_available():
                    raise ImportError("OR-Tools not installed")
                
                config = CPSATConfig(time_limit_seconds=self._time_limit_sec)
                self._cpsat_scheduler = CPSATScheduler(config)
            except ImportError as e:
                logger.warning(f"CP-SAT scheduler unavailable: {e}")
                return None
        return self._cpsat_scheduler
    
    def _get_genetic_scheduler(self):
        """Lazy-load Genetic scheduler."""
        if self._genetic_scheduler is None:
            try:
                from .genetic_engine import GeneticScheduler, GeneticConfig, is_genetic_available
                
                if not is_genetic_available():
                    raise ImportError("DEAP not installed")
                
                config = GeneticConfig(time_limit_seconds=self._time_limit_sec)
                self._genetic_scheduler = GeneticScheduler(config)
            except ImportError as e:
                logger.warning(f"Genetic scheduler unavailable: {e}")
                return None
        return self._genetic_scheduler
    
    def schedule(
        self,
        operations: List[SchedulingOperation],
        machines: List[SchedulingMachine],
        horizon_start: datetime = None,
        horizon_end: datetime = None,
    ) -> SchedulingResult:
        """
        Run scheduling algorithm based on configured engine.
        
        Args:
            operations: List of operations to schedule
            machines: List of available machines
            horizon_start: Start of planning horizon (defaults to now)
            horizon_end: End of planning horizon (defaults to horizon_start + 4 weeks)
            
        Returns:
            SchedulingResult with scheduled operations and KPIs
        """
        horizon_start = horizon_start or datetime.now()
        horizon_end = horizon_end or (horizon_start + timedelta(weeks=4))
        
        # Dispatch to appropriate engine
        if self._engine == SchedulerEngine.CPSAT:
            return self._schedule_cpsat(operations, machines, horizon_start, horizon_end)
        elif self._engine == SchedulerEngine.GENETIC:
            return self._schedule_genetic(operations, machines, horizon_start, horizon_end)
        elif self._engine == SchedulerEngine.CPO_V4:
            return self._schedule_cpo_v4(operations, machines, horizon_start, horizon_end)
        else:
            # Default: heuristic
            return self._schedule_heuristic(operations, machines, horizon_start, horizon_end)

    def _schedule_cpo_v4(
        self,
        operations: List[SchedulingOperation],
        machines: List[SchedulingMachine],
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> SchedulingResult:
        """CPO v4 hyper-heuristic scheduler (NELO DRCFFS-R)."""
        try:
            from src.plan.cpo.engine import CPOConfig, CPOv4Engine
            from src.plan.cpo.state import FactoryState

            # Callers must inject state via configure() in the future;
            # for now, load a lightweight state from the semantic layer.
            state = getattr(self, "_cpo_state", None)
            if state is None:
                # Fallback: empty state (decoder still works, just without
                # skill matrix / mold info / historical durations).
                state = FactoryState(tenant_id=getattr(self, "_tenant_id", None))

            # Sprint Q.9 Onda 1.2 — Camada 2 wire. Adapter is sync, so the
            # async caller (FastAPI handler) is expected to pre-load a
            # `FitnessConfig` via `await FitnessConfig.from_tenant_config(...)`
            # and hand it in via `set_fitness_config`. When absent, the
            # engine constructor falls back to default weights (existing
            # behaviour) plus auto-copies `state.preference_rules` for
            # Camada 1 enforcement.
            engine = CPOv4Engine(
                state=state,
                config=CPOConfig(time_limit_sec=self._time_limit_sec),
                fitness_config=getattr(self, "_fitness_config", None),
            )
            result_dict = engine.schedule(operations, machines, horizon_start, horizon_end)
            return SchedulingResult(**{k: v for k, v in result_dict.items() if k in SchedulingResult.model_fields})
        except Exception as e:
            logger.error(f"CPO v4 scheduling failed: {e}", exc_info=True)
            try:
                from src.shared.metrics import bump_silent_fallback
                bump_silent_fallback(
                    "scheduling_adapter", f"cpo_v4_failed:{type(e).__name__}",
                )
            except Exception:  # noqa: S110  Q.61.06: metrics best-effort
                pass
            fallback = self._schedule_heuristic(operations, machines, horizon_start, horizon_end)
            fallback.warnings.append(f"CPO v4 failed ({e}) - used heuristic fallback")
            fallback.degraded = True
            fallback.fallback_reason = f"cpo_v4_failed: {type(e).__name__}: {str(e)[:200]}"
            return fallback

    def set_cpo_state(self, state) -> None:
        """Inject a pre-loaded FactoryState for the CPO v4 engine."""
        self._cpo_state = state

    def set_fitness_config(self, fitness_config) -> None:
        """Inject a pre-loaded FitnessConfig (typically built via
        `await FitnessConfig.from_tenant_config(...)` so adaptive
        Camada-2 weights are merged in). Sprint Q.9 Onda 1.2."""
        self._fitness_config = fitness_config

    def set_tenant_id(self, tenant_id) -> None:
        self._tenant_id = tenant_id
    
    def _schedule_cpsat(
        self,
        operations: List[SchedulingOperation],
        machines: List[SchedulingMachine],
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> SchedulingResult:
        """Schedule using CP-SAT solver."""
        scheduler = self._get_cpsat_scheduler()
        
        if scheduler is None:
            logger.warning("CP-SAT unavailable, falling back to heuristic")
            result = self._schedule_heuristic(operations, machines, horizon_start, horizon_end)
            result.warnings.append("CP-SAT unavailable - used heuristic fallback")
            result.degraded = True
            result.fallback_reason = "cpsat_unavailable: ortools not installed or scheduler init failed"
            return result

        try:
            result_dict = scheduler.schedule(operations, machines, horizon_start, horizon_end)
            return SchedulingResult(**result_dict)
        except Exception as e:
            logger.error(f"CP-SAT scheduling failed: {e}")
            result = self._schedule_heuristic(operations, machines, horizon_start, horizon_end)
            result.warnings.append(f"CP-SAT failed ({e}) - used heuristic fallback")
            result.degraded = True
            result.fallback_reason = f"cpsat_failed: {type(e).__name__}: {str(e)[:200]}"
            return result
    
    def _schedule_genetic(
        self,
        operations: List[SchedulingOperation],
        machines: List[SchedulingMachine],
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> SchedulingResult:
        """Schedule using Genetic Algorithm."""
        scheduler = self._get_genetic_scheduler()
        
        if scheduler is None:
            logger.warning("Genetic unavailable, falling back to heuristic")
            result = self._schedule_heuristic(operations, machines, horizon_start, horizon_end)
            result.warnings.append("Genetic unavailable - used heuristic fallback")
            result.degraded = True
            result.fallback_reason = "genetic_unavailable: DEAP not installed or scheduler init failed"
            return result

        try:
            result_dict = scheduler.schedule(operations, machines, horizon_start, horizon_end)
            return SchedulingResult(**result_dict)
        except Exception as e:
            logger.error(f"Genetic scheduling failed: {e}")
            result = self._schedule_heuristic(operations, machines, horizon_start, horizon_end)
            result.warnings.append(f"Genetic failed ({e}) - used heuristic fallback")
            result.degraded = True
            result.fallback_reason = f"genetic_failed: {type(e).__name__}: {str(e)[:200]}"
            return result
    
    def _schedule_heuristic(
        self,
        operations: List[SchedulingOperation],
        machines: List[SchedulingMachine],
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> SchedulingResult:
        """
        Schedule using heuristic dispatch rules.
        
        Supported rules:
        - EDD: Earliest Due Date first
        - SPT: Shortest Processing Time first
        - FIFO: First In First Out (by sequence)
        - WSPT: Weighted Shortest Processing Time
        """
        import time
        start_time = time.time()
        
        if not operations:
            return SchedulingResult(
                success=True,
                engine_used="heuristic",
                rule_used=self._rule.value,
                warnings=["No operations to schedule"],
            )
        
        # Sort operations based on dispatch rule
        if self._rule == DispatchRule.EDD:
            sorted_ops = sorted(
                operations,
                key=lambda op: (op.due_date or datetime.max, -op.priority),
            )
        elif self._rule == DispatchRule.SPT:
            sorted_ops = sorted(
                operations,
                key=lambda op: (op.duration_minutes, -op.priority),
            )
        elif self._rule == DispatchRule.WSPT:
            # Weighted SPT: sort by processing_time / priority (lower is better)
            sorted_ops = sorted(
                operations,
                key=lambda op: op.duration_minutes / max(op.priority, 0.1),
            )
        else:  # FIFO
            sorted_ops = sorted(
                operations,
                key=lambda op: (op.sequence, op.order_id),
            )
        
        # Build machine availability map
        machine_next_available: Dict[str, datetime] = {
            m.machine_id: horizon_start for m in machines
        }
        
        scheduled: List[Dict[str, Any]] = []
        total_tardiness = 0.0
        late_orders = set()
        
        for op in sorted_ops:
            # Find machine
            machine_id = op.machine_id
            if not machine_id:
                # Manual operation - use virtual "MANUAL" machine
                machine_id = "MANUAL"
                if machine_id not in machine_next_available:
                    machine_next_available[machine_id] = horizon_start
            
            # Calculate start time
            start_dt = machine_next_available.get(machine_id, horizon_start)
            
            # Calculate end time
            duration = timedelta(minutes=op.duration_minutes)
            end_dt = start_dt + duration
            
            # Update machine availability
            machine_next_available[machine_id] = end_dt
            
            # Check tardiness
            if op.due_date and end_dt > op.due_date:
                tardiness = (end_dt - op.due_date).total_seconds() / 3600
                total_tardiness += tardiness
                late_orders.add(op.order_id)
            
            scheduled.append({
                "operation_id": op.operation_id,
                "order_id": op.order_id,
                "product_id": op.product_id,
                "operation_code": op.operation_code,
                "machine_id": machine_id,
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat(),
                "duration_minutes": op.duration_minutes,
                "setup_minutes": 0.0,
            })
        
        # Calculate KPIs
        makespan = 0.0
        if scheduled:
            all_ends = [
                datetime.fromisoformat(s["end_time"])
                for s in scheduled
            ]
            makespan = (max(all_ends) - horizon_start).total_seconds() / 3600
        
        # Calculate utilization
        total_work_minutes = sum(op.duration_minutes for op in operations)
        total_available_minutes = sum(max(1, m.capacity) for m in machines) * makespan * 60 if makespan > 0 else 1  # Q.168.C — respeita capacity>1 (slots)
        utilization = min(100, (total_work_minutes / total_available_minutes) * 100) if total_available_minutes > 0 else 0
        
        solve_time = time.time() - start_time
        
        return SchedulingResult(
            success=True,
            engine_used="heuristic",
            rule_used=self._rule.value,
            solve_time_sec=solve_time,
            status="optimal",
            operations=scheduled,
            makespan_hours=makespan,
            total_tardiness_hours=total_tardiness,
            num_late_orders=len(late_orders),
            avg_utilization=utilization,
        )
    
    def get_machine_utilization(
        self,
        result: SchedulingResult,
        machines: List[SchedulingMachine],
    ) -> Dict[str, float]:
        """Calculate utilization per machine."""
        utilization: Dict[str, float] = {}
        
        machine_work: Dict[str, float] = {m.machine_id: 0 for m in machines}
        
        for op in result.operations:
            machine_id = op.get("machine_id")
            if machine_id in machine_work:
                machine_work[machine_id] += op.get("duration_minutes", 0)
        
        for m in machines:
            available = m.capacity * result.makespan_hours * 60
            if available > 0:
                utilization[m.machine_id] = min(100, (machine_work[m.machine_id] / available) * 100)
            else:
                utilization[m.machine_id] = 0
        
        return utilization
    
    @staticmethod
    def get_available_engines() -> Dict[str, bool]:
        """Check which scheduling engines are available."""
        available = {
            "heuristic": True,  # Always available
            "milp": False,  # Not implemented
        }
        
        # Check CP-SAT
        try:
            from .cpsat_engine import is_cpsat_available
            available["cpsat"] = is_cpsat_available()
        except ImportError:
            available["cpsat"] = False
        
        # Check Genetic
        try:
            from .genetic_engine import is_genetic_available
            available["genetic"] = is_genetic_available()
        except ImportError:
            available["genetic"] = False
        
        return available
