"""
ProdPlan ONE - Digital Twin Service (facade)
=============================================

Q.67.6.B1 - este ficheiro era um god-file de 1192 linhas. Foi decomposto
em 4 sub-modulos:

* `delta_applier`  - validacao + aplicacao de deltas (whitelist Q.54.I).
* `hash_audit`     - extraccao de KPIs + hashes deterministicos.
* `scenario_crud`  - CRUD + `apply_delta` + construcao do baseline_state.
* `simulator`      - simulate + solve + compare + CP-SAT runner.

`TwinService` continua a ser a API publica - delega para os sub-modulos.
Os metodos `_private` que os characterization tests Q.67.A1 invocam
directamente (`svc._apply_delta_to_state(...)`, `svc._extract_value(...)`,
etc.) sao mantidos como thin wrappers para preservar a safety-net.

Re-exports: `SUPPORTED_DELTA_ENTITY_TYPES`, `TwinValidationError`,
`validate_delta_patch`, `_is_finite_number`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from . import hash_audit
from .delta_applier import (
    SUPPORTED_DELTA_ENTITY_TYPES,
    TwinValidationError,
    apply_delta_to_state,
    is_finite_number,
    validate_delta_patch,
)
from .models import Scenario
from .scenario_crud import ScenarioCrud
from .simulator import Simulator, run_cpsat

logger = logging.getLogger(__name__)

# Backwards-compat re-export — tests Q.54.I + Q.67.A1 importam isto daqui.
_is_finite_number = is_finite_number

__all__ = [
    "SUPPORTED_DELTA_ENTITY_TYPES",
    "TwinService",
    "TwinValidationError",
    "validate_delta_patch",
    "_is_finite_number",
]


class TwinService:
    """Service for managing Digital Twin scenarios (facade Q.67.6.B1)."""

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self._crud = ScenarioCrud(db, tenant_id)
        self._sim = Simulator(self)

    # -------- Scenario CRUD ---------------------------------------------------

    async def create_scenario(self, *args, **kwargs) -> Scenario:
        return await self._crud.create_scenario(*args, **kwargs)

    async def get_scenario(self, scenario_id: UUID) -> Optional[Scenario]:
        return await self._crud.get_scenario(scenario_id)

    async def list_scenarios(self, *args, **kwargs) -> List[Scenario]:
        return await self._crud.list_scenarios(*args, **kwargs)

    async def delete_scenario(self, scenario_id: UUID) -> bool:
        return await self._crud.delete_scenario(scenario_id)

    async def apply_delta(self, *args, **kwargs):
        return await self._crud.apply_delta(*args, **kwargs)

    # -------- Simulation / Solver / Compare -----------------------------------

    async def simulate(self, scenario_id: UUID) -> Dict[str, Any]:
        return await self._sim.simulate(scenario_id)

    async def solve(self, *args, **kwargs) -> Dict[str, Any]:
        return await self._sim.solve(*args, **kwargs)

    async def compare(self, *args, **kwargs) -> Dict[str, Any]:
        return await self._sim.compare(*args, **kwargs)

    # -------- Baseline state — tests Q.56.B/test_api.py patcham aqui ----------

    async def _governance_baseline_metrics(self) -> Dict[str, Optional[float]]:
        return await self._crud.governance_baseline_metrics()

    async def _create_baseline_state(self) -> Dict[str, Any]:
        return await self._crud.create_baseline_state()

    # -------- Thin wrappers — chamados pelos tests Q.67.A1 + Q.54.I -----------
    # NAO podem ser removidos sem partir a safety-net.

    def _apply_delta_to_state(
        self, state: Dict[str, Any], delta: Dict[str, Any]
    ) -> Dict[str, Any]:
        return apply_delta_to_state(state, delta)

    def _calculate_kpi_deltas(
        self, before: Dict[str, Any], after: Dict[str, Any]
    ) -> Dict[str, Any]:
        return hash_audit.calculate_kpi_deltas(before, after)

    def _extract_value(self, item: Any) -> Optional[float]:
        return hash_audit.extract_value(item)

    def _calculate_scenario_hash(self, scenario: Scenario) -> str:
        return hash_audit.calculate_scenario_hash(scenario)

    def _calculate_state_hash(self, state: Dict[str, Any]) -> str:
        return hash_audit.calculate_state_hash(state)

    def _calculate_result_hash(self, result: Dict[str, Any]) -> str:
        return hash_audit.calculate_result_hash(result)

    def get_audit_hashes(self, scenario: Scenario) -> Dict[str, str]:
        return hash_audit.get_audit_hashes(scenario)

    # -------- Static helpers — monkeypatch Q.53.C: `TwinService._run_cpsat` ---

    @staticmethod
    def _extract_scheduling_input(scenario: Scenario):
        return Simulator.extract_scheduling_input(scenario)

    @staticmethod
    def _run_cpsat(
        operations: List[Dict[str, Any]],
        machines: List[Dict[str, Any]],
        time_limit_sec: float,
    ) -> Dict[str, Any]:
        """Run CP-SAT synchronously (invoked via asyncio.to_thread)."""
        return run_cpsat(operations, machines, time_limit_sec)

    @staticmethod
    def scenario_to_dict(scenario: Scenario) -> Dict[str, Any]:
        return ScenarioCrud.scenario_to_dict(scenario)
