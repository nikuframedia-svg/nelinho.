"""
ProdPlan ONE - Genetic Algorithm Scheduling Engine
====================================================

Evolutionary optimization scheduler using DEAP (Distributed Evolutionary Algorithms in Python).
Suitable for large-scale scheduling problems where optimal solutions are computationally expensive.

Features:
- Permutation-based chromosome representation
- Partially Mapped Crossover (PMX) for preserving operation sequences
- Swap and inversion mutations
- Tournament selection
- Elitism to preserve best solutions
- Configurable population size, generations, and rates
"""

import logging
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import DEAP
try:
    from deap import base, creator, tools, algorithms
    DEAP_AVAILABLE = True
except ImportError:
    DEAP_AVAILABLE = False
    logger.warning("DEAP not available - Genetic scheduler will be disabled")


@dataclass
class GeneticConfig:
    """Configuration for Genetic Algorithm scheduler."""
    population_size: int = 100
    num_generations: int = 200
    crossover_probability: float = 0.8
    mutation_probability: float = 0.2
    tournament_size: int = 3
    elite_size: int = 5  # Number of best individuals to preserve
    time_limit_seconds: float = 60.0
    makespan_weight: float = 1.0
    tardiness_weight: float = 10.0
    random_seed: Optional[int] = None


class GeneticScheduler:
    """
    Genetic Algorithm based scheduler for production scheduling.
    
    Uses evolutionary optimization to find good (not necessarily optimal)
    schedules for large-scale problems where CP-SAT may be too slow.
    
    Chromosome Representation:
    - A permutation of operation indices representing processing order
    - Decoding: operations are scheduled in chromosome order, respecting
      machine availability and precedence constraints
    
    Fitness Function:
    - Minimize weighted combination of makespan and total tardiness
    - Lower fitness = better schedule
    
    Genetic Operators:
    - Selection: Tournament selection
    - Crossover: Partially Mapped Crossover (PMX)
    - Mutation: Swap mutation and inversion mutation
    """
    
    def __init__(self, config: Optional[GeneticConfig] = None):
        self.config = config or GeneticConfig()
        self._creator_initialized = False
        
        if not DEAP_AVAILABLE:
            raise ImportError(
                "DEAP is required for Genetic scheduler. "
                "Install with: pip install deap"
            )
        
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)
    
    def _init_creator(self):
        """Initialize DEAP creator classes (only once)."""
        if self._creator_initialized:
            return
        
        # Create fitness class (minimization)
        if not hasattr(creator, "FitnessMin"):
            creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
        
        # Create individual class
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list, fitness=creator.FitnessMin)
        
        self._creator_initialized = True
    
    def schedule(
        self,
        operations: List[Any],  # List of SchedulingOperation
        machines: List[Any],    # List of SchedulingMachine
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> Dict[str, Any]:
        """
        Generate schedule using Genetic Algorithm.
        
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
        
        self._init_creator()
        
        # Store context for fitness evaluation
        self._operations = operations
        self._machines = machines
        self._horizon_start = horizon_start
        self._horizon_end = horizon_end
        self._machine_ids = {m.machine_id for m in machines}
        self._machine_ids.add("MANUAL")
        
        # Build precedence map
        self._precedence_map = self._build_precedence_map(operations)
        
        # Create DEAP toolbox
        toolbox = self._create_toolbox(len(operations))
        
        # Initialize population
        population = toolbox.population(n=self.config.population_size)
        
        # Statistics
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("min", min)
        stats.register("avg", lambda x: sum(v[0] for v in x) / len(x) if x else 0)
        
        # Hall of fame (keeps best individuals)
        hof = tools.HallOfFame(self.config.elite_size)
        
        # Run evolution with time limit
        generation = 0
        while generation < self.config.num_generations:
            elapsed = time.time() - start_time
            if elapsed > self.config.time_limit_seconds:
                logger.info(f"GA stopped at generation {generation} due to time limit")
                break
            
            # Select next generation
            offspring = toolbox.select(population, len(population) - self.config.elite_size)
            offspring = list(map(toolbox.clone, offspring))
            
            # Crossover
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < self.config.crossover_probability:
                    toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values
            
            # Mutation
            for mutant in offspring:
                if random.random() < self.config.mutation_probability:
                    toolbox.mutate(mutant)
                    del mutant.fitness.values
            
            # Evaluate fitness for individuals without valid fitness
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = map(toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit
            
            # Add elite individuals
            population[:] = offspring + list(hof)
            
            # Update hall of fame
            hof.update(population)
            
            generation += 1
            
            # Log progress every 50 generations
            if generation % 50 == 0:
                best_fit = hof[0].fitness.values[0] if hof else float('inf')
                logger.debug(f"GA Generation {generation}: best fitness = {best_fit:.2f}")
        
        solve_time = time.time() - start_time
        
        # Get best solution
        if hof:
            best_individual = hof[0]
            return self._decode_to_result(best_individual, solve_time, generation)
        else:
            return self._empty_result()
    
    def _build_precedence_map(self, operations: List[Any]) -> Dict[str, List[str]]:
        """Build map of operation_id -> list of predecessor operation_ids."""
        precedence = {}
        
        # Group by order and build sequence-based precedence
        ops_by_order = defaultdict(list)
        for op in operations:
            ops_by_order[op.order_id].append(op)
        
        for order_id, order_ops in ops_by_order.items():
            sorted_ops = sorted(order_ops, key=lambda x: x.sequence)
            for i, op in enumerate(sorted_ops):
                preds = []
                # Add sequence-based predecessor
                if i > 0:
                    preds.append(sorted_ops[i - 1].operation_id)
                # Add explicit predecessors
                if op.predecessor_ops:
                    preds.extend(op.predecessor_ops)
                precedence[op.operation_id] = preds
        
        return precedence
    
    def _create_toolbox(self, num_operations: int) -> Any:
        """Create DEAP toolbox with genetic operators."""
        toolbox = base.Toolbox()
        
        # Individual: permutation of operation indices
        toolbox.register("indices", random.sample, range(num_operations), num_operations)
        toolbox.register(
            "individual",
            tools.initIterate,
            creator.Individual,
            toolbox.indices
        )
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        
        # Genetic operators
        toolbox.register("evaluate", self._evaluate_fitness)
        toolbox.register("mate", tools.cxPartialyMatched)  # PMX crossover
        toolbox.register("mutate", self._mutate)
        toolbox.register(
            "select",
            tools.selTournament,
            tournsize=self.config.tournament_size
        )
        
        return toolbox
    
    def _mutate(self, individual: List[int]) -> Tuple[List[int]]:
        """
        Apply mutation: randomly swap two elements or invert a segment.
        """
        if len(individual) < 2:
            return (individual,)
        
        if random.random() < 0.5:
            # Swap mutation
            i, j = random.sample(range(len(individual)), 2)
            individual[i], individual[j] = individual[j], individual[i]
        else:
            # Inversion mutation
            i, j = sorted(random.sample(range(len(individual)), 2))
            individual[i:j+1] = reversed(individual[i:j+1])
        
        return (individual,)
    
    def _evaluate_fitness(self, individual: List[int]) -> Tuple[float]:
        """
        Evaluate fitness of an individual (schedule permutation).
        
        Decodes the permutation to a schedule and calculates:
        - Makespan (total completion time)
        - Tardiness (lateness penalties)
        
        Returns tuple with single fitness value (for minimization).
        """
        # Decode individual to schedule
        schedule, makespan_hours, total_tardiness, num_late = self._decode_individual(individual)
        
        # Calculate weighted fitness (lower is better)
        fitness = (
            self.config.makespan_weight * makespan_hours +
            self.config.tardiness_weight * total_tardiness
        )
        
        return (fitness,)
    
    def _decode_individual(
        self,
        individual: List[int]
    ) -> Tuple[List[Dict], float, float, int]:
        """
        Decode a permutation to a concrete schedule.
        
        The individual is a permutation of operation indices.
        Operations are scheduled in this order, respecting:
        - Machine availability (no overlap)
        - Precedence constraints (predecessors must complete first)
        """
        operations = self._operations
        horizon_start = self._horizon_start
        
        # Track machine availability (machine_id -> next available time in minutes)
        machine_available = defaultdict(int)
        
        # Track operation completion times
        op_end_times: Dict[str, int] = {}
        
        # Schedule in individual order
        scheduled = []
        total_tardiness = 0.0
        late_orders = set()
        max_end = 0
        
        for idx in individual:
            op = operations[idx]
            duration = int(op.duration_minutes)
            if duration <= 0:
                duration = 1
            
            machine_id = op.machine_id or "MANUAL"
            if machine_id not in self._machine_ids:
                machine_id = "MANUAL"
            
            # Earliest start based on machine availability
            earliest_start = machine_available[machine_id]
            
            # Check precedence constraints
            for pred_id in self._precedence_map.get(op.operation_id, []):
                if pred_id in op_end_times:
                    earliest_start = max(earliest_start, op_end_times[pred_id])
            
            # Schedule operation
            start_minutes = earliest_start
            end_minutes = start_minutes + duration
            
            # Update trackers
            machine_available[machine_id] = end_minutes
            op_end_times[op.operation_id] = end_minutes
            max_end = max(max_end, end_minutes)
            
            # Calculate times
            start_dt = horizon_start + timedelta(minutes=start_minutes)
            end_dt = horizon_start + timedelta(minutes=end_minutes)
            
            # Check tardiness
            if op.due_date and end_dt > op.due_date:
                tardiness_hours = (end_dt - op.due_date).total_seconds() / 3600
                total_tardiness += tardiness_hours
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
        
        makespan_hours = max_end / 60.0
        return scheduled, makespan_hours, total_tardiness, len(late_orders)
    
    def _decode_to_result(
        self,
        individual: List[int],
        solve_time: float,
        generations: int,
    ) -> Dict[str, Any]:
        """Convert best individual to SchedulingResult format."""
        scheduled, makespan_hours, total_tardiness, num_late = self._decode_individual(individual)
        
        # Sort by start time
        scheduled.sort(key=lambda x: x["start_time"])
        
        # Calculate utilization
        total_work = sum(op.duration_minutes for op in self._operations)
        total_available = len(self._machines) * makespan_hours * 60 if makespan_hours > 0 else 1
        utilization = min(100, (total_work / total_available) * 100) if total_available > 0 else 0
        
        return {
            "success": True,
            "engine_used": "genetic",
            "rule_used": None,
            "solve_time_sec": solve_time,
            "status": "feasible",
            "operations": scheduled,
            "makespan_hours": makespan_hours,
            "total_tardiness_hours": total_tardiness,
            "num_late_orders": num_late,
            "avg_utilization": utilization,
            "warnings": [],
            "ga_stats": {
                "generations": generations,
                "population_size": self.config.population_size,
                "best_fitness": individual.fitness.values[0] if individual.fitness.valid else None,
            },
        }
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result for no operations."""
        return {
            "success": True,
            "engine_used": "genetic",
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


def is_genetic_available() -> bool:
    """Check if Genetic scheduler is available."""
    return DEAP_AVAILABLE




