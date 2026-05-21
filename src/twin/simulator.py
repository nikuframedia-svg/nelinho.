"""
ProdPlan ONE - Twin: Simulator / Solver / Compare
==================================================

Q.67.6.B1 - extraido de `src/twin/service.py` (god-file 1192L). Caminho
pesado de simulacao: aplica deltas ao baseline, opcionalmente corre
CP-SAT, computa comparacoes e persiste resultados.

`_run_cpsat` continua a viver no `TwinService` como `@staticmethod` -
ha testes (Q.53.C) que fazem `monkeypatch.setattr(TwinService, "_run_cpsat", ...)`.
Por isso o `Simulator` invoca-o sempre via referencia ao servico
(`self._service._run_cpsat`), nao localmente.

Tambem aqui: `_create_baseline_state` e `_governance_baseline_metrics`
vivem no servico por dependerem de modulos externos (Factory Data
Product, Plan, Quality). Cobertos por `test_baseline_real_q56b.py`.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from .delta_applier import (
    TwinValidationError,
    apply_delta_to_state,
    validate_delta_patch,
)
from .hash_audit import (
    calculate_kpi_deltas,
    calculate_scenario_hash,
    extract_value,
)
from .models import Scenario, ScenarioComparison, ScenarioStatus

if TYPE_CHECKING:  # avoid cyclic import at runtime
    from .service import TwinService

logger = logging.getLogger(__name__)


class Simulator:
    """Executa simulacao, solver CP-SAT e comparacao de cenarios.

    Recebe a instancia do `TwinService` para poder chamar
    `_run_cpsat`/`get_scenario` atraves dela - isto preserva os
    monkeypatches que os testes Q.53.C fazem sobre a classe.
    """

    def __init__(self, service: "TwinService"):
        self._service = service

    @property
    def db(self):
        return self._service.db

    @property
    def tenant_id(self) -> UUID:
        return self._service.tenant_id

    # =========================================================================
    # simulate
    # =========================================================================

    async def simulate(self, scenario_id: UUID) -> Dict[str, Any]:
        """Run simulation on a scenario."""
        scenario = await self._service.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        scenario.status = ScenarioStatus.SIMULATING.value
        await self.db.commit()

        try:
            # Q.54.I - deep copy do estado-base. Shallow copy partilha
            # dicts aninhados (cada KPI e `{"value": ...}`) e contaminava
            # o baseline original.
            current_state = copy.deepcopy(scenario.baseline_state)
            baseline_snapshot = copy.deepcopy(scenario.baseline_state)

            # Aplica deltas em sequencia. Cada delta e validado outra vez
            # aqui (Q.54.I) - deltas clonados de outro cenario entram pelo
            # construtor e nao passam por `apply_delta`.
            for delta in sorted(scenario.deltas, key=lambda d: d.sequence):
                validate_delta_patch(delta.entity_type, delta.patch or {})
                current_state = apply_delta_to_state(current_state, {
                    "entity_type": delta.entity_type,
                    "entity_key": delta.entity_key,
                    "patch": delta.patch,
                })

            delta_summary = calculate_kpi_deltas(baseline_snapshot, current_state)

            simulation_result = {
                "before": baseline_snapshot,
                "after": current_state,
                "delta_summary": delta_summary,
                "mode": "projecao_linear",
                "mode_reason": (
                    "Os KPIs foram projectados linearmente a partir dos "
                    "deltas. Não correu o solver — o cenário não traz input "
                    "de scheduling (operations[]+machines[])."
                ),
                "simulated_at": datetime.now(timezone.utc).isoformat(),
            }

            # Auto-solve when the scenario carries scheduling input.
            sched_input = self.extract_scheduling_input(scenario)
            if sched_input is not None:
                operations, machines = sched_input
                try:
                    schedule_result = await asyncio.wait_for(
                        asyncio.to_thread(
                            # Invocar via classe -> respeita monkeypatch dos testes.
                            type(self._service)._run_cpsat,
                            operations, machines, 30.0,
                        ),
                        timeout=35.0,
                    )
                    simulation_result["mode"] = "solver_cpsat"
                    simulation_result["mode_reason"] = (
                        "O cenário traz input de scheduling — correu o "
                        "solver CP-SAT automaticamente."
                    )
                    simulation_result["solver"] = {
                        "engine": "cpsat",
                        "status": "SOLVED",
                        "schedule": schedule_result,
                    }
                except asyncio.TimeoutError:
                    logger.warning(
                        "CP-SAT auto-solve timed out for scenario %s",
                        scenario_id,
                    )
                    simulation_result["solver"] = {
                        "engine": "cpsat",
                        "status": "SOLVER_TIMEOUT",
                    }
                except Exception as exc:  # pragma: no cover — defensive
                    logger.error(
                        "CP-SAT auto-solve error for scenario %s: %s",
                        scenario_id, exc, exc_info=True,
                    )
                    simulation_result["solver"] = {
                        "engine": "cpsat",
                        "status": "SOLVER_ERROR",
                        "error": str(exc),
                    }

            scenario_hash = calculate_scenario_hash(scenario)

            scenario.simulation_result = simulation_result
            scenario.simulated_at = datetime.now(timezone.utc)
            scenario.scenario_hash = scenario_hash
            scenario.status = ScenarioStatus.SIMULATED.value

            await self.db.commit()

            logger.info(f"Simulated scenario {scenario_id}")
            return simulation_result

        except TwinValidationError as e:
            # Q.54.I - erro de INPUT (delta invalido), nao falha de execucao.
            # Volta a DRAFT para o utilizador poder corrigir o delta.
            scenario.status = ScenarioStatus.DRAFT.value
            await self.db.commit()
            logger.warning(f"Simulation rejected for scenario {scenario_id}: {e}")
            raise

        except Exception as e:
            scenario.status = ScenarioStatus.ERROR.value
            await self.db.commit()
            logger.error(f"Simulation failed for scenario {scenario_id}: {e}")
            raise

    # =========================================================================
    # solve
    # =========================================================================

    async def solve(
        self,
        scenario_id: UUID,
        objective: str = "maximize_oee",
        operations: Optional[List[Dict[str, Any]]] = None,
        machines: Optional[List[Dict[str, Any]]] = None,
        time_limit_sec: float = 30.0,
    ) -> Dict[str, Any]:
        """Run optimization on a scenario via CP-SAT (or projection-only)."""
        scenario = await self._service.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        # Apply deltas deterministically to get projected state.
        projected_state = copy.deepcopy(scenario.baseline_state)
        for delta in sorted(scenario.deltas, key=lambda d: d.sequence):
            validate_delta_patch(delta.entity_type, delta.patch or {})
            projected_state = apply_delta_to_state(projected_state, {
                "entity_type": delta.entity_type,
                "entity_key": delta.entity_key,
                "patch": delta.patch,
            })

        input_source = "request"
        if not (operations and machines):
            sched_input = self.extract_scheduling_input(scenario)
            if sched_input is not None:
                operations, machines = sched_input
                input_source = "scenario_delta"

        # Case 1: Real scheduling input -> run CP-SAT
        if operations and machines:
            try:
                schedule_result = await asyncio.wait_for(
                    asyncio.to_thread(
                        type(self._service)._run_cpsat,
                        operations, machines, time_limit_sec,
                    ),
                    timeout=time_limit_sec + 5.0,
                )
                return {
                    "scenario_id": str(scenario_id),
                    "objective": objective,
                    "status": "SOLVED",
                    "engine_used": "cpsat",
                    "input_source": input_source,
                    "schedule": schedule_result,
                    "projected_kpis": projected_state,
                    "solved_at": datetime.now(timezone.utc).isoformat(),
                }
            except asyncio.TimeoutError:
                logger.warning(f"CP-SAT timed out for scenario {scenario_id}")
                return {
                    "scenario_id": str(scenario_id),
                    "objective": objective,
                    "status": "SOLVER_TIMEOUT",
                    "time_limit_sec": time_limit_sec,
                    "projected_kpis": projected_state,
                    "solved_at": datetime.now(timezone.utc).isoformat(),
                }
            except Exception as e:
                logger.error(f"Solver error for scenario {scenario_id}: {e}", exc_info=True)
                return {
                    "scenario_id": str(scenario_id),
                    "objective": objective,
                    "status": "SOLVER_ERROR",
                    "error": str(e),
                    "projected_kpis": projected_state,
                    "solved_at": datetime.now(timezone.utc).isoformat(),
                }

        # Case 2: No scheduling input -> projection only.
        return {
            "scenario_id": str(scenario_id),
            "objective": objective,
            "status": "INSUFFICIENT_DATA",
            "mode": "projecao_linear",
            "reason": (
                "CP-SAT requires operations[] and machines[]. Supply them in "
                "the request, or add a delta with entity_type='scheduling_input' "
                "carrying operations[]+machines[] so the solver runs "
                "automatically. The scenario baseline alone is not enough — "
                "the result below is a delta-only linear projection."
            ),
            "projected_kpis": projected_state,
            "solved_at": datetime.now(timezone.utc).isoformat(),
        }

    # =========================================================================
    # compare
    # =========================================================================

    async def compare(
        self,
        scenario_id: UUID,
        baseline_scenario_id: Optional[UUID] = None,
        compared_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compare a scenario against baseline or another scenario."""
        scenario = await self._service.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        if baseline_scenario_id:
            baseline_scenario = await self._service.get_scenario(baseline_scenario_id)
            if not baseline_scenario:
                raise ValueError(f"Baseline scenario {baseline_scenario_id} not found")
            baseline_state = (
                baseline_scenario.simulation_result.get("after", baseline_scenario.baseline_state)
                if baseline_scenario.simulation_result
                else baseline_scenario.baseline_state
            )
        else:
            baseline_state = scenario.baseline_state

        scenario_state = (
            scenario.simulation_result.get("after", scenario.baseline_state)
            if scenario.simulation_result
            else scenario.baseline_state
        )

        comparison_result: Dict[str, Any] = {}
        kpi_deltas: Dict[str, Any] = {}

        for key in set(baseline_state.keys()) | set(scenario_state.keys()):
            if key.startswith("_"):
                continue

            baseline_val = extract_value(baseline_state.get(key))
            scenario_val = extract_value(scenario_state.get(key))

            if baseline_val is not None and scenario_val is not None:
                delta = scenario_val - baseline_val
                comparison_result[key] = {
                    "baseline": baseline_val,
                    "scenario": scenario_val,
                    "delta": delta,
                    "delta_pct": round(delta / baseline_val * 100, 2) if baseline_val != 0 else None,
                }
                kpi_deltas[key] = delta

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
            "compared_at": datetime.now(timezone.utc).isoformat(),
        }

    # =========================================================================
    # scheduling-input extraction
    # =========================================================================

    @staticmethod
    def extract_scheduling_input(
        scenario: Scenario,
    ) -> Optional[tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
        """Pull CP-SAT scheduling input carried by the scenario's deltas.

        A scenario "has sufficient data" for a real solver run when one of
        its deltas is of ``entity_type="scheduling_input"`` and its ``patch``
        carries non-empty ``operations[]`` and ``machines[]`` lists. The
        last such delta wins (later deltas override earlier ones).

        Returns ``(operations, machines)`` when present, else ``None``.
        """
        found: Optional[tuple[List[Dict[str, Any]], List[Dict[str, Any]]]] = None
        for delta in sorted(scenario.deltas or [], key=lambda d: d.sequence):
            if delta.entity_type != "scheduling_input":
                continue
            patch = delta.patch or {}
            operations = patch.get("operations")
            machines = patch.get("machines")
            if operations and machines:
                found = (list(operations), list(machines))
        return found


def run_cpsat(
    operations: List[Dict[str, Any]],
    machines: List[Dict[str, Any]],
    time_limit_sec: float,
) -> Dict[str, Any]:
    """Run CP-SAT synchronously (invoked via asyncio.to_thread)."""
    from src.plan.engines.scheduling_adapter import (
        SchedulerEngine,
        SchedulingAdapter,
        SchedulingMachine,
        SchedulingOperation,
    )

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
    horizon_start = datetime.now(timezone.utc)
    horizon_end = horizon_start + timedelta(weeks=4)

    adapter = SchedulingAdapter()
    adapter.configure(engine=SchedulerEngine.CPSAT, time_limit_sec=time_limit_sec)
    result = adapter.schedule(op_objs, machine_objs, horizon_start, horizon_end)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)
