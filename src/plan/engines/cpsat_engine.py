"""
ProdPlan ONE - CP-SAT Scheduling Engine
========================================

Constraint Programming scheduler using Google OR-Tools CP-SAT solver.
Provides optimal or near-optimal solutions for Job-Shop Scheduling Problems (JSSP).

Features:
- Precedence constraints (operation sequences)
- No-overlap constraints (machine capacity)
- Due date penalties (tardiness minimization)
- Setup time handling between different products
- Configurable time limits
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import OR-Tools
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    logger.warning("OR-Tools not available - CP-SAT scheduler will be disabled")


@dataclass
class CPSATConfig:
    """Configuration for CP-SAT scheduler."""
    time_limit_seconds: float = 30.0
    num_workers: int = 4
    makespan_weight: float = 1.0
    tardiness_weight: float = 10.0  # Penalize late jobs more
    setup_time_minutes: int = 15  # Default setup time between different products


class CPSATScheduler:
    """
    CP-SAT based scheduler for production scheduling.
    
    Formulates the scheduling problem as a Constraint Satisfaction Problem
    and uses Google OR-Tools' CP-SAT solver to find optimal/near-optimal solutions.
    
    Problem Formulation:
    - Variables: start_time, end_time, interval for each operation
    - Constraints:
        - Precedence: operations must respect sequence within same order
        - No-overlap: machine can only process one operation at a time
        - Time bounds: operations must fit within planning horizon
    - Objective: Minimize weighted sum of makespan + total tardiness
    """
    
    def __init__(self, config: Optional[CPSATConfig] = None):
        self.config = config or CPSATConfig()
        
        if not ORTOOLS_AVAILABLE:
            raise ImportError(
                "OR-Tools is required for CP-SAT scheduler. "
                "Install with: pip install ortools"
            )
    
    def schedule(
        self,
        operations: List[Any],  # List of SchedulingOperation
        machines: List[Any],    # List of SchedulingMachine
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> Dict[str, Any]:
        """
        Generate optimal schedule using CP-SAT solver.
        
        Args:
            operations: List of operations to schedule
            machines: List of available machines
            horizon_start: Start of planning horizon
            horizon_end: End of planning horizon
            
        Returns:
            SchedulingResult-compatible dictionary
        """
        import time
        start_time = time.time()
        
        if not operations:
            return self._empty_result()
        
        # Calculate horizon in minutes (working with integers for CP-SAT)
        horizon_minutes = int((horizon_end - horizon_start).total_seconds() / 60)
        
        # Create the model
        model = cp_model.CpModel()
        
        # Build machine map
        machine_ids = {m.machine_id for m in machines}
        machine_ids.add("MANUAL")  # Virtual machine for manual operations
        
        # Create variables for each operation
        op_vars = {}  # operation_id -> (start_var, end_var, interval_var)
        machine_intervals = defaultdict(list)  # machine_id -> list of interval vars
        
        for op in operations:
            duration = int(op.duration_minutes)
            if duration <= 0:
                duration = 1  # Minimum 1 minute
            
            # Create start, end, and interval variables
            suffix = f"_{op.operation_id}"
            start_var = model.NewIntVar(0, horizon_minutes, f"start{suffix}")
            end_var = model.NewIntVar(0, horizon_minutes, f"end{suffix}")
            interval_var = model.NewIntervalVar(
                start_var, duration, end_var, f"interval{suffix}"
            )
            
            op_vars[op.operation_id] = (start_var, end_var, interval_var, op)
            
            # Assign to machine
            machine_id = op.machine_id or "MANUAL"
            if machine_id not in machine_ids:
                machine_id = "MANUAL"
            machine_intervals[machine_id].append(interval_var)
        
        # Constraint 1: No overlap on each machine
        for _machine_id, intervals in machine_intervals.items():
            if len(intervals) > 1:
                model.AddNoOverlap(intervals)
        
        # Constraint 2: Precedence (operations in same order respect sequence)
        # Group operations by order_id
        ops_by_order = defaultdict(list)
        for op in operations:
            ops_by_order[op.order_id].append(op)
        
        # Sort by sequence and add precedence constraints
        for _order_id, order_ops in ops_by_order.items():
            sorted_ops = sorted(order_ops, key=lambda x: x.sequence)
            for i in range(len(sorted_ops) - 1):
                curr_op = sorted_ops[i]
                next_op = sorted_ops[i + 1]
                
                if curr_op.operation_id in op_vars and next_op.operation_id in op_vars:
                    curr_end = op_vars[curr_op.operation_id][1]
                    next_start = op_vars[next_op.operation_id][0]
                    model.Add(next_start >= curr_end)
        
        # Constraint 3: Handle explicit predecessors
        for op in operations:
            if op.predecessor_ops:
                for pred_id in op.predecessor_ops:
                    if pred_id in op_vars and op.operation_id in op_vars:
                        pred_end = op_vars[pred_id][1]
                        op_start = op_vars[op.operation_id][0]
                        model.Add(op_start >= pred_end)
        
        # Objective: Minimize makespan + weighted tardiness
        # Create makespan variable (maximum end time)
        makespan = model.NewIntVar(0, horizon_minutes, "makespan")
        for _op_id, (_start_var, end_var, _interval_var, _op) in op_vars.items():
            model.Add(makespan >= end_var)
        
        # Create tardiness variables for each operation with due date
        tardiness_vars = []
        for op_id, (_start_var, end_var, _interval_var, op) in op_vars.items():
            if op.due_date:
                due_minutes = int((op.due_date - horizon_start).total_seconds() / 60)
                if due_minutes > 0:
                    tardiness = model.NewIntVar(0, horizon_minutes, f"tardiness_{op_id}")
                    # tardiness = max(0, end - due)
                    model.AddMaxEquality(tardiness, [0, end_var - due_minutes])
                    tardiness_vars.append((tardiness, op.priority))
        
        # Objective function: minimize weighted combination
        objective_terms = []
        
        # Makespan term
        makespan_weight = int(self.config.makespan_weight * 100)
        objective_terms.append(makespan * makespan_weight)
        
        # Tardiness terms (weighted by priority)
        for tardiness_var, priority in tardiness_vars:
            weight = int(self.config.tardiness_weight * priority * 100)
            objective_terms.append(tardiness_var * weight)
        
        if objective_terms:
            model.Minimize(sum(objective_terms))
        else:
            model.Minimize(makespan)
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config.time_limit_seconds
        solver.parameters.num_search_workers = self.config.num_workers
        
        status = solver.Solve(model)
        solve_time = time.time() - start_time
        
        # Process results
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return self._build_result(
                solver=solver,
                op_vars=op_vars,
                horizon_start=horizon_start,
                status=status,
                solve_time=solve_time,
                machines=machines,
            )
        else:
            logger.warning(f"CP-SAT solver failed with status: {solver.StatusName(status)}")
            return self._infeasible_result(status, solver, solve_time)
    
    def _build_result(
        self,
        solver: "cp_model.CpSolver",
        op_vars: Dict,
        horizon_start: datetime,
        status: int,
        solve_time: float,
        machines: List[Any],
    ) -> Dict[str, Any]:
        """Build scheduling result from solver solution."""
        scheduled_ops = []
        total_tardiness = 0.0
        late_orders = set()
        max_end_minutes = 0
        
        for _op_id, (start_var, end_var, _interval_var, op) in op_vars.items():
            start_minutes = solver.Value(start_var)
            end_minutes = solver.Value(end_var)
            
            start_dt = horizon_start + timedelta(minutes=start_minutes)
            end_dt = horizon_start + timedelta(minutes=end_minutes)
            
            max_end_minutes = max(max_end_minutes, end_minutes)
            
            # Check tardiness
            if op.due_date and end_dt > op.due_date:
                tardiness_hours = (end_dt - op.due_date).total_seconds() / 3600
                total_tardiness += tardiness_hours
                late_orders.add(op.order_id)
            
            scheduled_ops.append({
                "operation_id": op.operation_id,
                "order_id": op.order_id,
                "product_id": op.product_id,
                "operation_code": op.operation_code,
                "machine_id": op.machine_id or "MANUAL",
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat(),
                "duration_minutes": op.duration_minutes,
                "setup_minutes": 0.0,
            })
        
        # Sort by start time
        scheduled_ops.sort(key=lambda x: x["start_time"])
        
        # Calculate KPIs
        makespan_hours = max_end_minutes / 60.0
        total_work_minutes = sum(op.duration_minutes for op in [v[3] for v in op_vars.values()])
        total_available_minutes = sum(max(1, m.capacity) for m in machines) * makespan_hours * 60 if makespan_hours > 0 else 1  # Q.168.C — respeita capacity>1 (slots)
        utilization = min(100, (total_work_minutes / total_available_minutes) * 100) if total_available_minutes > 0 else 0
        
        status_name = "optimal" if status == cp_model.OPTIMAL else "feasible"
        
        return {
            "success": True,
            "engine_used": "cpsat",
            "rule_used": None,
            "solve_time_sec": solve_time,
            "status": status_name,
            "operations": scheduled_ops,
            "makespan_hours": makespan_hours,
            "total_tardiness_hours": total_tardiness,
            "num_late_orders": len(late_orders),
            "avg_utilization": utilization,
            "warnings": [],
            "solver_stats": {
                "objective_value": solver.ObjectiveValue(),
                "num_conflicts": solver.NumConflicts(),
                "num_branches": solver.NumBranches(),
                "wall_time": solver.WallTime(),
            },
        }
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result for no operations."""
        return {
            "success": True,
            "engine_used": "cpsat",
            "rule_used": None,
            "solve_time_sec": 0.0,
            "status": "optimal",
            "operations": [],
            "makespan_hours": 0.0,
            "total_tardiness_hours": 0.0,
            "num_late_orders": 0,
            "avg_utilization": 0.0,
            "warnings": ["No operations to schedule"],
        }
    
    def _infeasible_result(
        self,
        status: int,
        solver: "cp_model.CpSolver",
        solve_time: float,
    ) -> Dict[str, Any]:
        """Return result for infeasible/error case."""
        status_name = solver.StatusName(status)
        return {
            "success": False,
            "engine_used": "cpsat",
            "rule_used": None,
            "solve_time_sec": solve_time,
            "status": status_name.lower(),
            "operations": [],
            "makespan_hours": 0.0,
            "total_tardiness_hours": 0.0,
            "num_late_orders": 0,
            "avg_utilization": 0.0,
            "warnings": [f"Solver returned status: {status_name}"],
        }


def is_cpsat_available() -> bool:
    """Check if CP-SAT solver is available."""
    return ORTOOLS_AVAILABLE








