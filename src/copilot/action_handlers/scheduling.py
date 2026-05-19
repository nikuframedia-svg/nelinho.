"""
Q.37.D — handlers de scheduling: `reschedule_order`, `optimize_capacity`,
`reduce_setup`.

SEGURANÇA (risco do plano Q.37): este módulo NUNCA importa de
`src/plan/cpo/decoder|fitness|pair_assignment|state|chromosome`. Toca o
scheduler apenas pela API pública `POST /v1/plan/cpo/schedule` — a
função `schedule_cpo`, que constrói o `CPOv4Engine`, corre os 7 axiomas
Spelke, o safety_net e o hook `yaml_policy`. Reaproveitar essa porta é
exactamente o que o plano pede ("HTTP in-process, reaproveita os
guardrails do CPO").

Dois modos (lidos de `executor.current_mode`):
  * SANDBOX — projecção via Digital Twin (`TwinService`), sem correr o
    GA caro e sem persistir nada de produção;
  * EXECUTE — chamada real a `schedule_cpo`, que persiste um commit
    Schedule-as-Code (auditável).

Os três handlers diferem apenas no delta que enviam ao Twin / nos
parâmetros do pedido CPO.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class SchedulingActionRejected(ValueError):
    """Acção de scheduling recusada por input inválido."""


# entity_type do Twin por acção — casa com `TwinService._apply_delta_to_state`.
_TWIN_DELTA_BY_ACTION = {
    "reschedule_order": ("capacity_adjustment", "capacity_increase_pct"),
    "optimize_capacity": ("capacity_adjustment", "capacity_increase_pct"),
    "reduce_setup": ("standard_time", "reduction_pct"),
}


async def _sandbox_via_twin(
    executor: "Any",
    action: "Any",
    plan_id: Optional[UUID],
) -> Dict[str, Any]:
    """Projecção SANDBOX via Digital Twin — sem correr o GA, sem persistir."""
    from src.twin.service import TwinService

    entity_type, patch_key = _TWIN_DELTA_BY_ACTION[action.type]
    payload = action.payload or {}
    # Magnitude do efeito; default conservador de 5% se não vier no payload.
    magnitude = payload.get("magnitude_pct", payload.get(patch_key, 5))

    twin = TwinService(db=executor.session, tenant_id=executor.tenant_id)
    scenario = await twin.create_scenario(
        title=f"SANDBOX copiloto — {action.type}",
        description=f"Projecção da acção {action.type} via Digital Twin.",
        created_by=str(executor.user_id),
    )
    await twin.apply_delta(
        scenario_id=scenario.id,
        entity_type=entity_type,
        entity_key=str(payload.get("target") or action.type),
        patch={patch_key: magnitude},
        description=f"Delta de {action.type}",
        applied_by=str(executor.user_id),
    )
    sim = await twin.simulate(scenario.id)

    return {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "action_type": action.type,
        "plan_id": str(plan_id) if plan_id else None,
        "mode": "sandbox_twin",
        "scenario_id": str(scenario.id),
        "scenario_hash": getattr(scenario, "scenario_hash", None),
        "before": sim.get("before", {}),
        "after": sim.get("after", {}),
        "delta_summary": sim.get("delta_summary", {}),
    }


async def _execute_via_cpo(
    executor: "Any",
    action: "Any",
    plan_id: Optional[UUID],
) -> Dict[str, Any]:
    """EXECUTE real: corre `POST /v1/plan/cpo/schedule` in-process.

    Importa a função do router CPO (camada API), NUNCA os módulos
    internos do scheduler. Todos os guardrails do `CPOv4Engine` correm
    dentro dessa chamada.
    """
    from src.plan.api.cpo import CPOScheduleRequest, schedule_cpo

    payload = action.payload or {}
    request = CPOScheduleRequest(
        orders=payload.get("orders"),
        horizon_days=int(payload.get("horizon_days", 30)),
        time_limit_sec=float(payload.get("time_limit_sec", 30.0)),
        author=f"copilot:{executor.user_id}",
        message=payload.get("message")
        or f"Copiloto {action.type} (acção {action.id})",
    )

    response = await schedule_cpo(
        request=request,
        tenant_id=executor.tenant_id,
        db=executor.session,
    )
    # `schedule_cpo` devolve um CPOScheduleResponse (pydantic).
    resp = response.model_dump() if hasattr(response, "model_dump") else dict(response)

    return {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "action_type": action.type,
        "plan_id": str(plan_id) if plan_id else None,
        "mode": "execute_cpo",
        "commit_sha256": resp.get("commit_sha256"),
        "engine_used": resp.get("engine_used"),
        "status": resp.get("status"),
        "makespan_hours": resp.get("makespan_hours"),
        "num_late_orders": resp.get("num_late_orders"),
        "safety_net_triggered": resp.get("safety_net_triggered"),
        "degraded": resp.get("degraded"),
    }


async def _scheduling_handler(
    executor: "Any",
    action: "Any",
    plan_id: Optional[UUID],
) -> Dict[str, Any]:
    """Dispatcher comum: SANDBOX → Twin, EXECUTE → CPO."""
    from src.copilot.actions import ActionMode

    mode = getattr(executor, "current_mode", None)
    if mode == ActionMode.SANDBOX:
        return await _sandbox_via_twin(executor, action, plan_id)
    # EXECUTE (e qualquer outro caso por defeito) → CPO real.
    return await _execute_via_cpo(executor, action, plan_id)


async def reschedule_order(executor, action, plan_id):
    """Re-agenda ordens. SANDBOX projecta no Twin; EXECUTE corre o CPO."""
    return await _scheduling_handler(executor, action, plan_id)


async def optimize_capacity(executor, action, plan_id):
    """Optimiza capacidade. SANDBOX projecta no Twin; EXECUTE corre o CPO."""
    return await _scheduling_handler(executor, action, plan_id)


async def reduce_setup(executor, action, plan_id):
    """Reduz tempos de setup. SANDBOX projecta no Twin; EXECUTE corre o CPO."""
    return await _scheduling_handler(executor, action, plan_id)
