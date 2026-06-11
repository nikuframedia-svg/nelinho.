"""Q.173.AD — contexto de filtros do Gantt (/overall).

Um fetch leve (~dezenas de KB) que dá ao frontend os mapas necessários
para os 12 filtros da Fase 6 sem inchar o payload do plano (2,3MB):

* ``product_names``  — código legacy → nome real (factory_raw.produto);
* ``product_gamas``  — código → disciplina/tipo (decisão Luis #3:
  "gama" = P_TP_ID_DISCIPLINA → produto_tipo.TP_NOME; fallback P_TP_ID);
* ``phase_sectors``  — fase_id → setor (AREA_GROUPS, workforce/levels);
* ``orders_boost``   — order_id → boost efetivo (boost_inputs_snapshot
  do commit — Q.173.S recolhe-o pré-solve);
* ``orders_due``     — order_id → promessa de transporte (honesta:
  ausente quando NULL — Q.173.A);
* ``orders_material_risk`` — order_ids afetados pelo forecast de
  ruturas (Q.173.Z; cache in-process TTL para não correr o motor a
  cada pedido);
* ``repair_phase_ids`` — fases de reparação efetivas (config Q.173.L).

Tudo derivado de dados reais; nada inventado (invariante #8).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/filters-context", tags=["PLAN"])

# Cache in-process do conjunto de ordens com material em risco — o motor
# de ruturas varre o plano inteiro (caro para um GET de contexto).
_RISK_TTL_S = 120.0
_risk_cache: Dict[UUID, Tuple[float, List[str]]] = {}


class FiltersContextOut(BaseModel):
    commit_sha: Optional[str] = Field(None, description="Plano-base do contexto")
    product_names: Dict[str, str] = Field(default_factory=dict)
    order_products: Dict[str, str] = Field(
        default_factory=dict,
        description="order_id → código do produto (OF_P_ID, via ordemfabrico)",
    )
    product_gamas: Dict[str, str] = Field(
        default_factory=dict,
        description="código → disciplina (gama, decisão Luis 2026-06-11)",
    )
    phase_sectors: Dict[str, str] = Field(default_factory=dict)
    orders_boost: Dict[str, int] = Field(default_factory=dict)
    orders_due: Dict[str, str] = Field(
        default_factory=dict,
        description="order_id → promessa de transporte ISO (só quando real)",
    )
    orders_material_risk: List[str] = Field(default_factory=list)
    repair_phase_ids: List[str] = Field(default_factory=list)
    material_risk_stale: bool = Field(
        False, description="true se o conjunto de risco veio da cache TTL",
    )


async def _orders_material_risk(
    session: AsyncSession, tenant_id: UUID,
) -> Tuple[List[str], bool]:
    """Order_ids afetados por ruturas previstas (Q.173.Z), com cache TTL."""
    now = time.monotonic()
    cached = _risk_cache.get(tenant_id)
    if cached is not None and now - cached[0] < _RISK_TTL_S:
        return cached[1], True
    try:
        from src.supply.services.shortage_forecast_service import (
            ShortageForecastService,
        )

        result = await ShortageForecastService(session, tenant_id).forecast()
        orders: set[str] = set()
        for mat in getattr(result, "materiais_em_risco", None) or []:
            for o in getattr(mat, "ordens_afetadas", None) or []:
                orders.add(str(o.order_id))
        out = sorted(orders)
        _risk_cache[tenant_id] = (now, out)
        return out, False
    except (SQLAlchemyError, ImportError, ValueError, TypeError, AttributeError) as exc:
        logger.warning("filters-context: forecast indisponível (%s)", exc)
        # Estado honesto: sem forecast → lista vazia (o filtro mostra 0,
        # não inventa risco). Mantém a cache antiga se existir.
        if cached is not None:
            return cached[1], True
        return [], False


@router.get("", response_model=FiltersContextOut)
async def get_filters_context(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> FiltersContextOut:
    """Mapas de contexto para os filtros do Gantt — 1 fetch, payload leve."""
    from src.plan.cpo.commits import CommitsService
    from src.workforce.levels import area_group_for_phase

    commits = CommitsService(session, tenant_id)
    rows = await commits.list_commits(limit=1, healthy_only=True)
    commit = rows[0] if rows else None

    order_ids: set[str] = set()
    if commit is not None:
        for op in commit.operations or []:
            oid = op.get("order_id")
            if oid is not None:
                order_ids.add(str(oid))

    out = FiltersContextOut(
        commit_sha=getattr(commit, "commit_sha256", None),
    )

    # nomes + gama (disciplina) dos produtos do plano. NOTA: o jsonb do
    # commit NÃO tem product_id (é injetado ao servir a API) — o modelo
    # deriva-se da ordem via factory_raw.ordemfabrico (OF_P_ID), o mesmo
    # caminho do forecast Q.173.Z. Devolve também order→produto para o
    # frontend filtrar por modelo/gama sem 2º fetch.
    numeric_oids_for_products = sorted(
        int(o) for o in order_ids if o.isdigit()
    )
    if numeric_oids_for_products:
        try:
            rows_p = (await session.execute(
                text(
                    'SELECT ofb."OF_ID", p."P_ID", p."P_NOME", '
                    '       COALESCE(td."TP_NOME", t."TP_NOME") AS gama '
                    "FROM factory_raw.ordemfabrico ofb "
                    'JOIN factory_raw.produto p ON p."P_ID" = ofb."OF_P_ID" '
                    'LEFT JOIN factory_raw.produto_tipo td '
                    '       ON td."TP_ID" = p."P_TP_ID_DISCIPLINA" '
                    'LEFT JOIN factory_raw.produto_tipo t '
                    '       ON t."TP_ID" = p."P_TP_ID" '
                    'WHERE ofb."OF_ID" = ANY(:oids)'
                ),
                {"oids": numeric_oids_for_products},
            )).all()
            for oid, pid, nome, gama in rows_p:
                out.order_products[str(oid)] = str(pid)
                if nome:
                    out.product_names[str(pid)] = str(nome)
                if gama:
                    out.product_gamas[str(pid)] = str(gama)
        except SQLAlchemyError as exc:
            logger.warning("filters-context: produto lookup falhou (%s)", exc)

    # setor por fase (AREA_GROUPS por nome da fase)
    try:
        rows_f = (await session.execute(
            text(
                'SELECT "FP_ID", "FP_NOME" FROM factory_raw.fases_producao '
                'WHERE "FP_PRODUCAO" = true'
            )
        )).all()
        for fid, nome in rows_f:
            out.phase_sectors[str(fid)] = area_group_for_phase(
                str(nome or ""), str(fid),
            )
    except SQLAlchemyError as exc:
        logger.warning("filters-context: fases lookup falhou (%s)", exc)

    # boosts do commit (Q.173.S — snapshot pré-solve, no sha)
    snapshot = getattr(commit, "boost_inputs_snapshot", None) or {}
    for oid, comp in snapshot.items():
        try:
            eff = int((comp or {}).get("effective", 0) or 0)
        except (TypeError, ValueError):
            continue
        if eff:
            out.orders_boost[str(oid)] = eff

    # promessa de transporte por ordem (honesta — só quando existe)
    numeric_oids = sorted(int(o) for o in order_ids if o.isdigit())
    if numeric_oids:
        try:
            from src.plan.models.order import ProductionOrder

            rows_o = (await session.execute(
                select(
                    ProductionOrder.legacy_id, ProductionOrder.transport_date,
                ).where(
                    ProductionOrder.tenant_id == tenant_id,
                    ProductionOrder.legacy_id.in_(numeric_oids),
                    ProductionOrder.transport_date.is_not(None),
                )
            )).all()
            for lid, tdate in rows_o:
                out.orders_due[str(lid)] = tdate.isoformat()
        except SQLAlchemyError as exc:
            logger.warning("filters-context: due lookup falhou (%s)", exc)

    out.orders_material_risk, out.material_risk_stale = (
        await _orders_material_risk(session, tenant_id)
    )

    # fases de reparação efetivas (config Q.173.L, default {14,76,77})
    try:
        from src.core.services.tenant_config_service import TenantConfigService
        from src.plan.cpo.state import REPAIR_PHASE_IDS

        planning = await TenantConfigService(session, tenant_id).get_category(
            "planning",
        )
        raw = planning.get("repair.phase_ids")
        if isinstance(raw, (list, tuple)) and raw:
            out.repair_phase_ids = [str(int(x)) for x in raw]
        else:
            out.repair_phase_ids = sorted(REPAIR_PHASE_IDS, key=int)
    except (SQLAlchemyError, ImportError, ValueError, TypeError) as exc:
        logger.debug("filters-context: repair ids default (%s)", exc)
        from src.plan.cpo.state import REPAIR_PHASE_IDS

        out.repair_phase_ids = sorted(REPAIR_PHASE_IDS, key=int)

    return out
