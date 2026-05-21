"""
ProdPlan ONE - Twin: Scenario CRUD + Baseline construction
===========================================================

Q.67.6.B1 - extraido de `src/twin/service.py` (god-file 1192L). Operacoes
CRUD basicas sobre `Scenario` + `apply_delta` (escrita de um delta a um
cenario existente) + construcao do `baseline_state` (Q.56.B - leitura do
Factory Data Product semantic layer com fallback para tabelas de
governanca).

A construcao do baseline vive aqui (e nao no Simulator) porque e
`create_scenario` quem o consome - simulate/solve recebem o
`baseline_state` ja preparado a partir do `Scenario` persistido.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.factory_data_product.config import (
    BLOCKED_METRICS,
    SEMANTIC_LABELS,
    TRUST_INDEX,
)

from .delta_applier import validate_delta_patch
from .models import Scenario, ScenarioDelta, ScenarioStatus

logger = logging.getLogger(__name__)


class ScenarioCrud:
    """CRUD + delta-application + baseline construction para `Scenario`."""

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def create_scenario(
        self,
        title: str,
        description: Optional[str] = None,
        base_scenario_id: Optional[UUID] = None,
        created_by: Optional[str] = None,
    ) -> Scenario:
        """Create a new scenario."""
        baseline_state = await self.create_baseline_state()

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

    async def apply_delta(
        self,
        scenario_id: UUID,
        entity_type: str,
        entity_key: str,
        patch: Dict[str, Any],
        description: Optional[str] = None,
        applied_by: Optional[str] = None,
    ) -> ScenarioDelta:
        """Apply a delta to a scenario."""
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        if scenario.status not in [ScenarioStatus.DRAFT.value, ScenarioStatus.SIMULATED.value]:
            raise ValueError(f"Cannot apply delta to scenario with status {scenario.status}")

        # Q.54.I - valida o delta ANTES de o persistir.
        validate_delta_patch(entity_type, patch)

        max_sequence = max((d.sequence for d in scenario.deltas), default=-1)

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

        scenario.status = ScenarioStatus.DRAFT.value
        scenario.simulation_result = None
        scenario.scenario_hash = None

        await self.db.commit()
        await self.db.refresh(delta)

        logger.info(f"Applied delta to scenario {scenario_id}: {entity_type}/{entity_key}")
        return delta

    # -------------------------------------------------------------------------
    # Baseline construction (Q.56.B)
    # -------------------------------------------------------------------------

    async def governance_baseline_metrics(self) -> Dict[str, Optional[float]]:
        """Q.56.B - KPIs do baseline computados de tabelas reais.

        Fallback para quando a camada semantica do Factory Data Product
        nao esta disponivel (dev). Cada query e best-effort: uma falha
        numa fonte deixa esse KPI a ``None``, nao derruba o baseline.
        """
        out: Dict[str, Optional[float]] = {
            "wip": None,
            "quality_errors": None,
            "backlog_hours": None,
        }

        try:
            from src.plan.models.order import OrderStatus, ProductionOrder
            from src.plan.services.phase_classification import is_completed_phase

            phases = (await self.db.execute(
                select(ProductionOrder.current_phase_name).where(
                    ProductionOrder.tenant_id == self.tenant_id,
                    ProductionOrder.status == OrderStatus.IN_PROGRESS,
                )
            )).scalars().all()
            out["wip"] = sum(1 for p in phases if not is_completed_phase(p))
        except Exception as exc:  # pragma: no cover - defensivo
            logger.debug("twin baseline: contagem de WIP falhou: %s", exc)

        try:
            from src.quality.models.rework import ReworkEntry

            count = (await self.db.execute(
                select(func.count(ReworkEntry.id)).where(
                    ReworkEntry.tenant_id == self.tenant_id
                )
            )).scalar()
            out["quality_errors"] = int(count or 0)
        except Exception as exc:  # pragma: no cover - defensivo
            logger.debug("twin baseline: contagem de retrabalho falhou: %s", exc)

        try:
            from src.plan.cpo.commits import CommitsService

            commit = await CommitsService(self.db, self.tenant_id).get_latest()
            if commit is not None and commit.kpis:
                makespan = commit.kpis.get("makespan_hours")
                if isinstance(makespan, (int, float)) and makespan > 0:
                    out["backlog_hours"] = float(makespan)
        except Exception as exc:  # pragma: no cover - defensivo
            logger.debug("twin baseline: commit CPO mais recente falhou: %s", exc)

        return out

    async def create_baseline_state(self) -> Dict[str, Any]:
        """Create baseline factory state from FDP semantic layer + governance fallback."""
        sq = None
        try:
            from src.factory_data_product.services.semantic_queries_inmemory import (
                SemanticQueriesInMemory,
            )
            sq = SemanticQueriesInMemory()
        except Exception as exc:
            logger.debug("twin: SemanticQueriesInMemory unavailable: %s", exc)

        def _query_safe(method_name: str) -> Optional[Dict]:
            if sq is None:
                return None
            try:
                result = getattr(sq, method_name)()
                if result and result.get("status") != "BLOCKED":
                    return result
            except Exception as exc:
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

        # Q.56.B - fallback de tabelas reais para os 3 KPIs.
        gov = await self.governance_baseline_metrics()
        wip_source = data_source
        if wip_value is None and gov["wip"] is not None:
            wip_value = gov["wip"]
            wip_source = "governance_tables"
        backlog_source = data_source
        if backlog_value is None and gov["backlog_hours"] is not None:
            backlog_value = gov["backlog_hours"]
            backlog_source = "governance_tables"
        quality_source = data_source
        if quality_value is None and gov["quality_errors"] is not None:
            quality_value = gov["quality_errors"]
            quality_source = "governance_tables"

        any_governance = "governance_tables" in (
            wip_source, backlog_source, quality_source
        )

        return {
            "oee": {
                "value": None, "status": "BLOCKED",
                "reason": BLOCKED_METRICS["oee_real"]["reason"],
            },
            "availability": {
                "value": None, "status": "BLOCKED",
                "reason": BLOCKED_METRICS["availability_oee"]["reason"],
            },
            "otd": {
                "value": None, "status": "BLOCKED",
                "reason": BLOCKED_METRICS["otd_official"]["reason"],
            },
            "wip_theoretical": {
                "value": wip_value, "unit": "orders",
                "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_structure", 80),
                "semantic_label": SEMANTIC_LABELS["wip"],
                "status": "OK" if wip_value is not None else "NO_DATA",
                "source": wip_source,
            },
            "backlog_horas_theoretical": {
                "value": round(backlog_value, 1) if backlog_value is not None else None,
                "unit": "hours",
                "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58),
                "semantic_label": SEMANTIC_LABELS["bottleneck"],
                "status": "WARNING" if backlog_value is not None else "NO_DATA",
                "source": backlog_source,
            },
            "lead_time_days_observed": {
                "value": lead_time_value, "unit": "days",
                "trust_index": TRUST_INDEX.get("OrdensFabrico", 82),
                "semantic_label": SEMANTIC_LABELS["lead_time"],
                "status": "OK" if lead_time_value else "NO_DATA",
                "source": data_source,
            },
            "bottleneck_count": {
                "value": bottleneck_value, "unit": "phases",
                "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58),
                "semantic_label": SEMANTIC_LABELS["bottleneck"],
                "status": "WARNING" if bottleneck_value else "NO_DATA",
                "source": data_source,
            },
            "skills_at_risk_count": {
                "value": skills_value, "unit": "phases",
                "trust_index": TRUST_INDEX.get("FuncionariosFaseOrdemFabrico", 55),
                "semantic_label": SEMANTIC_LABELS["skills"],
                "status": "WARNING" if skills_value else "NO_DATA",
                "source": data_source,
            },
            "quality_errors_total": {
                "value": quality_value, "unit": "errors",
                "trust_index": TRUST_INDEX.get("OrdemFabricoErros", 67),
                "semantic_label": SEMANTIC_LABELS["quality"],
                "status": "WARNING" if quality_value is not None else "NO_DATA",
                "source": quality_source,
            },
            "_metadata": {
                "source": "factory_data_product",
                "data_version": (
                    "semantic_layer" if sq
                    else "governance_tables" if any_governance
                    else "unavailable"
                ),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

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
