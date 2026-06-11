"""
ProdPlan ONE - DQA API (Sprint AA.4)
=====================================

Public endpoint for the v2.0 Trust Index:

    GET /v1/dqa/trust-index?scope=factory&scope_id=...

Returns the 7+1 component breakdown, composite score, the five gate
`effective_mode` map, and the current weights snapshot. Also emits the
Prometheus gauge `prodplan_trust_index_score` so dashboards pick up the value
without a pull-side integration.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.dqa.trust_gates import effective_mode, load_gate_config
from src.dqa.trust_signals import curated_signals_provider
from src.dqa.trust_v2 import (
    SCOPE_FACTORY,
    TrustIndexV2Calculator,
)
from src.shared.database import get_session
from src.shared.metrics import trust_index_score
from src.shared.auth.headers import require_tenant_header

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/dqa", tags=["DQA"])


get_tenant_id = require_tenant_header


class TrustIndexResponse(BaseModel):
    scope: str
    scope_id: Optional[str]
    composite: float
    components: dict[str, Any]
    weights: dict[str, float]
    effective_gates: dict[str, bool]


# F4.E — formato dos business keys do ERP (of_id/fase_id): alfanumérico +
# separadores comuns. Não é defesa anti-SQLi (o ORM parametriza) — é
# validação de formato HTTP: input fora disto → 422 em vez de query inútil.
_BUSINESS_KEY_PATTERN = r"^[A-Za-z0-9 _./-]{1,64}$"


@router.get("/trust-index", response_model=TrustIndexResponse)
async def get_trust_index(
    # F4.E — Literal substitui o runtime-check manual (400→422 automático,
    # consistente com ask_cube.period). ALLOWED_SCOPES continua a guardar
    # o compute_for_scope interno em trust_v2.py.
    scope: Literal["factory", "order", "phase"] = Query(
        SCOPE_FACTORY, description="factory | order | phase",
    ),
    scope_id: Optional[UUID] = Query(None, description="UUID for order/phase scope"),
    order_id: Optional[str] = Query(
        None,
        description="Business key (of_id) when scope=order",
        pattern=_BUSINESS_KEY_PATTERN,
    ),
    phase_id: Optional[str] = Query(
        None,
        description="Business key (fase_id) when scope=phase",
        pattern=_BUSINESS_KEY_PATTERN,
    ),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> TrustIndexResponse:
    """Compute the Blueprint v2.0 §4.5 Trust Index for the requested scope.

    Parameters
    ----------
    scope : factory | order | phase
    scope_id : optional UUID for order/phase scope (display only)
    order_id, phase_id : optional business keys — used when the curated
        tables' business keys differ from the entity UUIDs
    """
    async def provider_with_keys(sess, tid, sc, sid):
        # Closure that forwards the business keys the API caller passed in.
        # The calculator's SignalsProvider protocol has a fixed signature, so
        # we can't thread kwargs through it directly.
        return await curated_signals_provider(
            sess, tid, sc, sid,
            order_id_str=order_id,
            phase_id_str=phase_id,
        )

    calc = TrustIndexV2Calculator(
        session, tenant_id, signals_provider=provider_with_keys,
    )
    result = await calc.compute_for_scope(scope, scope_id=scope_id)

    gate_cfg = await load_gate_config(session, tenant_id)
    gates = effective_mode(result.composite, gate_cfg)

    # Emit the Prometheus gauge — labels are fixed to (entity_type, entity_id)
    # per the existing declaration in src.shared.metrics; we reuse scope /
    # scope_id for those, defaulting to "global" when scope is factory-wide.
    try:
        trust_index_score.labels(
            entity_type=scope,
            entity_id=str(scope_id) if scope_id else "global",
        ).set(result.composite)
    except Exception as exc:  # pragma: no cover — metrics best-effort
        # Onda 2.1 — observability must not silently degrade. Dashboards
        # depending on this gauge would otherwise show stale values without
        # any signal that emission is broken (mis-labelled metric, registry
        # collision, etc.).
        logger.error(
            "Failed to emit trust_index_score gauge (scope=%s scope_id=%s): %s",
            scope, scope_id, exc, exc_info=True,
        )

    payload = result.to_dict()
    payload["effective_gates"] = gates
    return TrustIndexResponse(**payload)
