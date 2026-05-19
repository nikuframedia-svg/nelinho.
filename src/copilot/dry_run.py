"""
ProdPlan ONE - Copilot DRY_RUN helper
=====================================

Q.37.B — o ramo ``DRY_RUN`` do endpoint ``/api/copilot/action`` deixa de
ser um eco do payload. Passa a correr uma simulação real via o serviço
do Digital Twin (``src/twin/service.py``):

  1. cria um cenário efémero,
  2. aplica o ``twin_delta`` que vem no payload,
  3. simula,
  4. compara contra o baseline,
  5. devolve before/after reais + ``scenario_hash`` para reprodutibilidade.

Honestidade > eco: se o payload não traz um delta mapeável para um
``entity_type`` que o Twin sabe simular, devolve
``{"status": "insufficient_input", ...}`` em vez de fabricar números.

NOTA — invariante 4: DRY_RUN nunca persiste nada fora do próprio
cenário do Twin (que é descartável e auditável). Não toca em ordens,
inventário ou schedule. É uma simulação, não uma execução.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Os entity_type que o `TwinService._apply_delta_to_state` sabe simular.
# Manter sincronizado com esse método — um delta fora desta whitelist
# é aplicado mas não move nenhum KPI, logo a simulação seria um no-op
# silencioso (pior que `insufficient_input` honesto).
TWIN_SUPPORTED_ENTITY_TYPES = frozenset(
    {
        "capacity_adjustment",
        "standard_time",
        "skills_training",
        "quality_improvement",
        "wip_policy",
    }
)


def extract_twin_delta(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extrai um delta do Twin do payload da acção, ou ``None``.

    Forma esperada::

        payload["twin_delta"] = {
            "entity_type": "capacity_adjustment",
            "entity_key": "<id legível>",
            "patch": {"capacity_increase_pct": 10},
            "description": "..."  # opcional
        }

    Devolve ``None`` (→ ``insufficient_input``) quando:
      - não há ``twin_delta``,
      - falta ``entity_type``/``patch``,
      - o ``entity_type`` não é simulável pelo Twin,
      - o ``patch`` está vazio.
    """
    raw = payload.get("twin_delta")
    if not isinstance(raw, dict):
        return None

    entity_type = raw.get("entity_type")
    patch = raw.get("patch")
    if not entity_type or not isinstance(patch, dict) or not patch:
        return None
    if entity_type not in TWIN_SUPPORTED_ENTITY_TYPES:
        return None

    return {
        "entity_type": str(entity_type),
        "entity_key": str(raw.get("entity_key") or entity_type),
        "patch": patch,
        "description": raw.get("description"),
    }


async def run_dry_run(
    payload: Dict[str, Any],
    tenant_id: UUID,
    session: AsyncSession,
    user_id: UUID,
) -> Dict[str, Any]:
    """Corre um DRY_RUN real via o Digital Twin.

    Devolve um dict JSON-safe com ``status`` em
    ``{"simulated", "insufficient_input", "error"}``.
    """
    delta = extract_twin_delta(payload)
    if delta is None:
        return {
            "action_type": "DRY_RUN",
            "status": "insufficient_input",
            "message": (
                "DRY_RUN precisa de payload.twin_delta com entity_type "
                f"simulável ({sorted(TWIN_SUPPORTED_ENTITY_TYPES)}) e um "
                "patch não vazio. Sem isso não há simulação possível — "
                "não foi fabricado nenhum resultado."
            ),
            "supported_entity_types": sorted(TWIN_SUPPORTED_ENTITY_TYPES),
        }

    # Import tardio: o módulo do Twin puxa SQLAlchemy + factory_data_product;
    # mantê-lo fora do import-time da API reduz acoplamento.
    from src.twin.service import TwinService

    twin = TwinService(db=session, tenant_id=tenant_id)
    try:
        scenario = await twin.create_scenario(
            title=f"DRY_RUN copiloto — {delta['entity_type']}",
            description=(
                delta.get("description")
                or "Cenário efémero criado pelo DRY_RUN do copiloto."
            ),
            created_by=str(user_id),
        )
        await twin.apply_delta(
            scenario_id=scenario.id,
            entity_type=delta["entity_type"],
            entity_key=delta["entity_key"],
            patch=delta["patch"],
            description=delta.get("description"),
            applied_by=str(user_id),
        )
        sim = await twin.simulate(scenario.id)
        comparison = await twin.compare(
            scenario_id=scenario.id,
            compared_by=str(user_id),
        )
    except ValueError as exc:
        # Cenário/delta inválido — erro de input, não 500.
        logger.warning("DRY_RUN via Twin rejeitado: %s", exc)
        return {
            "action_type": "DRY_RUN",
            "status": "insufficient_input",
            "message": f"Digital Twin recusou o delta: {exc}",
        }
    except Exception as exc:  # noqa: BLE001 — superfície honesta de erro
        logger.error("DRY_RUN via Twin falhou: %s", exc, exc_info=True)
        return {
            "action_type": "DRY_RUN",
            "status": "error",
            "message": f"Simulação falhou: {exc}",
        }

    return {
        "action_type": "DRY_RUN",
        "status": "simulated",
        "message": "Dry run simulado via Digital Twin (sem persistência de produção).",
        "scenario_id": str(scenario.id),
        "scenario_hash": sim_scenario_hash(scenario),
        "before": sim.get("before", {}),
        "after": sim.get("after", {}),
        "delta_summary": sim.get("delta_summary", {}),
        "comparison": comparison.get("comparison", {}),
        "applied_delta": delta,
    }


def sim_scenario_hash(scenario: Any) -> Optional[str]:
    """Lê o ``scenario_hash`` do cenário simulado (pode ser ``None``)."""
    return getattr(scenario, "scenario_hash", None)
