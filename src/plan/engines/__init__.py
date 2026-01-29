# ProdPlan ONE - PLAN Engines
"""
Scheduling and MRP engines for production planning.

Available Scheduling Engines:
- Heuristic: Fast dispatch rules (EDD, SPT, FIFO, WSPT)
- CP-SAT: Optimal constraint programming using Google OR-Tools
- Genetic: Evolutionary optimization using DEAP

Usage:
    from src.plan.engines import SchedulingAdapter, SchedulerEngine
    
    adapter = SchedulingAdapter()
    adapter.configure(engine=SchedulerEngine.CPSAT, time_limit_sec=30)
    result = adapter.schedule(operations, machines, horizon_start, horizon_end)
"""

from .scheduling_adapter import (
    SchedulingAdapter,
    SchedulerEngine,
    DispatchRule,
    SchedulingOperation,
    SchedulingMachine,
    ScheduledOperation,
    SchedulingResult,
)
from .mrp_adapter import MRPAdapter
from .bom_adapter import BOMAdapter

# Optional: Import advanced schedulers if available
try:
    from .cpsat_engine import CPSATScheduler, CPSATConfig, is_cpsat_available
    _CPSAT_AVAILABLE = True
except ImportError:
    _CPSAT_AVAILABLE = False
    CPSATScheduler = None
    CPSATConfig = None
    is_cpsat_available = lambda: False

try:
    from .genetic_engine import GeneticScheduler, GeneticConfig, is_genetic_available
    _GENETIC_AVAILABLE = True
except ImportError:
    _GENETIC_AVAILABLE = False
    GeneticScheduler = None
    GeneticConfig = None
    is_genetic_available = lambda: False


def get_available_engines():
    """
    Get dictionary of available scheduling engines.
    
    Returns:
        Dict[str, bool]: Engine name -> availability
    """
    return {
        "heuristic": True,
        "cpsat": _CPSAT_AVAILABLE and is_cpsat_available(),
        "genetic": _GENETIC_AVAILABLE and is_genetic_available(),
        "milp": False,  # Not implemented
    }


__all__ = [
    # Main adapter
    "SchedulingAdapter",
    # Enums
    "SchedulerEngine",
    "DispatchRule",
    # Data classes
    "SchedulingOperation",
    "SchedulingMachine",
    "ScheduledOperation",
    "SchedulingResult",
    # Advanced schedulers
    "CPSATScheduler",
    "CPSATConfig",
    "GeneticScheduler",
    "GeneticConfig",
    # Utility functions
    "is_cpsat_available",
    "is_genetic_available",
    "get_available_engines",
    # Other adapters
    "MRPAdapter",
    "BOMAdapter",
]
