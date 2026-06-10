"""Q.67.6.B2 — shared dependencies + helpers for CPO sub-routers.

Estes símbolos viviam todos em `src/plan/api/cpo.py` (god-file 1104L) e
são partilhados por múltiplos sub-routers (schedule, commits, timeline,
operations). Centralizar aqui mantém o agregador `cpo.py` fino e evita
import circular.

Os helpers `_compute_trust_index_for_schedule`, `_load_product_prices`
e `_extract_mapelites_representatives` continuam a ser re-exportados pelo
agregador para preservar imports legados (`from src.plan.api.cpo import
_compute_trust_index_for_schedule`).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.cpo.commits import CommitsService, ScheduleCommit
from src.plan.cpo.engine import CPOv4Engine
from src.shared.auth.headers import require_tenant_header
from src.shared.time import local_today

logger = logging.getLogger(__name__)

# Tenant dependency alias preserved from cpo.py.
_tenant_id = require_tenant_header


# =============================================================================
# Commit resolution helper
# =============================================================================

async def _resolve_commit_or_404(
    service: CommitsService,
    sha_or_prefix: str,
) -> ScheduleCommit:
    """Resolve a commit by full SHA-256 or short prefix, raising 404 if not found."""
    commit = await service.get_by_sha(sha_or_prefix)
    if commit is None:
        commit = await service.get_by_sha_prefix(sha_or_prefix)
    if commit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"commit {sha_or_prefix!r} not found",
        )
    return commit


# =============================================================================
# MAP-Elites representative extractor (Sprint K)
# =============================================================================

def _extract_mapelites_representatives(
    engine: CPOv4Engine, top_n: int = 10
) -> List[Dict[str, Any]]:
    """Serialise the best-N MAP-Elites elites into commit-storable dicts."""
    archive = getattr(engine, "_mapelites", None)
    if archive is None or archive.is_empty():
        return []
    reps = archive.representatives(top_n)
    out: List[Dict[str, Any]] = []
    for rank, elite in enumerate(reps):
        out.append({
            "rank": rank,
            "fitness": round(float(elite.fitness), 4),
            "generation": int(elite.generation),
            "behavioral": dict(elite.behavioral),
            "chromosome": {
                "permutation": list(elite.chromosome.permutation),
                "edd_gap": int(elite.chromosome.edd_gap),
                "buffer_pct": float(elite.chromosome.buffer_pct),
                "quality_weight": float(elite.chromosome.quality_weight),
            },
        })
    return out


# =============================================================================
# Trust Index (Sprint C 1.2)
# =============================================================================

async def _compute_trust_index_for_schedule(
    db: AsyncSession,
    tenant_id: UUID,
) -> float:
    """Sprint C 1.2 — compute the Trust Index for this schedule commit.

    Uses `TrustIndexV2Calculator` in factory scope (the only scope that
    makes sense for a full-horizon schedule). No signals provider is
    wired yet — the calculator falls back to neutral components
    (everything 1.0), which still exercises the v2 weights path so the
    composite isn't hardcoded to 0. Once Sprint AA.3 attaches a real
    `SignalsProvider`, this call lights up automatically.

    Returns a float in [0, 1]. On any DQA failure we log and return
    0.0 so the rest of the pipeline stays up — the approval gate then
    forces human review, which is the safer default.
    """
    try:
        from src.dqa.trust_v2 import SCOPE_FACTORY, TrustIndexV2Calculator

        calc = TrustIndexV2Calculator(db, tenant_id)
        result = await calc.compute_for_scope(SCOPE_FACTORY)
        return float(result.composite)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Trust Index computation failed: %s", exc)
        return 0.0


# =============================================================================
# Product pricing loader (Sprint C 1.1)
# =============================================================================

async def _load_product_prices(
    db: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, float]:
    """Sprint C 1.1 + Q.138.H — current sale prices per product (€).

    Pulls the latest-valid `ProductPricing` row per product for this
    tenant. Used by the CPO decoder to compute `throughput_eur_day`
    (F1 final wire — without this the fitness term stays at 0 and the
    €30–35K/day CEO target cannot be optimised).

    Q.138.H FIX — chave do mapa é `core.products.product_code` (string
    numérica, ex: "20205") em vez do UUID de `core.products.id`.
    Razão: `plan.production_orders.product_id` é o INTEGER ERP (P_ID)
    e o decoder procura `price_lookup.get(str(op.product_id))`.
    Sem o JOIN, as chaves eram UUIDs e o casamento falhava → throughput=0.

    Returns `{product_code: sale_value_default_eur}` strings → floats.
    An empty dict is returned when no rows exist — decoder then falls
    back to `throughput_eur_day=0.0` (no-op, backwards compatible).
    """
    from datetime import date as _date
    from sqlalchemy import and_, or_, select

    from src.core.models.product import Product
    from src.profit.models.pricing import ProductPricing

    today = local_today()
    # Q.138.H: JOIN com core.products para obter product_code = str(P_ID)
    # que é o mesmo identificador usado em plan.production_orders.product_id.
    stmt = (
        select(
            Product.product_code,
            ProductPricing.sale_value_default_eur,
            ProductPricing.valid_from,
        )
        .join(Product, Product.id == ProductPricing.product_id)
        .where(
            and_(
                ProductPricing.tenant_id == tenant_id,
                ProductPricing.active.is_(True),
                ProductPricing.valid_from <= today,
                or_(
                    ProductPricing.valid_to.is_(None),
                    ProductPricing.valid_to >= today,
                ),
            )
        )
        .order_by(Product.product_code, ProductPricing.valid_from.desc())
    )
    try:
        rows = (await db.execute(stmt)).all()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("product_pricing lookup failed, using empty map: %s", exc)
        return {}

    # Latest-valid per product_code (rows ordered DESC by valid_from — keep first).
    prices: Dict[str, float] = {}
    for product_code, price, _valid_from in rows:
        key = str(product_code)
        if key not in prices:
            prices[key] = float(price)
    return prices


# =============================================================================
# Narrative helpers for alternatives endpoint (Sprint M.7 — WG10)
# =============================================================================

def _relative_delta(a: Any, b: Any) -> Optional[float]:
    """(b-a)/|a| as a fraction. Returns None when either value is non-numeric
    or `a` is zero (undefined %)."""
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    if a == 0:
        return None
    return (float(b) - float(a)) / abs(float(a))


def _format_delta_pct(delta: Optional[float]) -> Optional[str]:
    if delta is None:
        return None
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta * 100:.1f}%"


def _build_narrative(vs_primary: Dict[str, Optional[str]]) -> str:
    """Template-based trade-off summary. Picks the two most salient dimensions
    (largest |delta|) and describes them in PT-PT."""
    labels = {
        "avg_utilization": "utilização média",
        "total_tardiness_hours": "atraso total",
        "num_late_orders": "ordens em atraso",
    }
    parts: List[tuple[float, str]] = []
    for key, fmt in vs_primary.items():
        if fmt is None:
            continue
        try:
            # "+5.2%" → 5.2
            magnitude = abs(float(fmt.rstrip("%")))
        except ValueError:
            continue
        parts.append((magnitude, f"{labels.get(key, key)}: {fmt}"))
    if not parts:
        return "Trade-off indisponível (KPIs não comparáveis)."
    parts.sort(reverse=True)
    return "Trade-offs principais — " + "; ".join(p[1] for p in parts[:3]) + "."


async def _attach_effective_boost(
    db: AsyncSession,
    tenant_id: UUID,
    operations: List[Dict[str, Any]],
) -> None:
    """Q.116.G — enriquece cada op com `effective_boost` (in-place).

    Cada op no payload do schedule tem `order_id` (string do `of_id` =
    `ProductionOrder.legacy_id`). Calculamos batch:
      * OrderBoost por legacy_id
      * BoatBoost por product_name (lookup ProductionOrder)
      * ClientPriority por customer_name → Customer → priority

    Defesa em profundidade: cada lookup tem try/except — se uma tabela
    ainda não existe (DB sem migrar) o campo cai para 0 sem derrubar
    o schedule. Performance: TODO Q.117 caso schedules >500 ops causem
    latência preocupante (3 batch queries + N para production_order).
    """
    if not operations:
        return

    from sqlalchemy import and_, select

    from src.core.models.client_priority import ClientPriority
    from src.core.models.partner import Customer
    from src.plan.models.order import ProductionOrder
    from src.plan.services.boost_service import compute_effective_boost

    # 1. Recolhe legacy_ids únicos (strings → ints onde possível).
    legacy_ids: List[int] = []
    for op in operations:
        raw = op.get("order_id")
        if raw is None:
            continue
        try:
            legacy_ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    legacy_ids = list(set(legacy_ids))
    if not legacy_ids:
        return

    # 2. Carrega ProductionOrders (legacy_id → row) para obter
    # product_name + customer_name.
    order_by_lid: Dict[int, Any] = {}
    try:
        po_stmt = select(ProductionOrder).where(
            and_(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.legacy_id.in_(legacy_ids),
            )
        )
        for row in (await db.execute(po_stmt)).scalars().all():
            order_by_lid[int(row.legacy_id)] = row
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("ProductionOrder batch skipped (%s)", exc)

    # 3. OrderBoost batch.
    order_boost_map: Dict[int, int] = {}
    try:
        from src.plan.models.order_boost import OrderBoost

        ob_stmt = select(OrderBoost).where(
            and_(
                OrderBoost.tenant_id == tenant_id,
                OrderBoost.work_order_id.in_(legacy_ids),
            )
        )
        for row in (await db.execute(ob_stmt)).scalars().all():
            order_boost_map[int(row.work_order_id)] = int(row.boost)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("OrderBoost batch skipped (%s)", exc)

    # 4. BoatBoost batch — chaveado por product_name.
    product_names = list({
        o.product_name for o in order_by_lid.values() if getattr(o, "product_name", None)
    })
    boat_boost_map: Dict[str, int] = {}
    if product_names:
        try:
            from src.plan.models.boat_boost import BoatBoost

            bb_stmt = select(BoatBoost).where(
                and_(
                    BoatBoost.tenant_id == tenant_id,
                    BoatBoost.boat_id.in_(product_names),
                )
            )
            for row in (await db.execute(bb_stmt)).scalars().all():
                boat_boost_map[str(row.boat_id)] = int(row.boost)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("BoatBoost batch skipped (%s)", exc)

    # 5. ClientPriority via Customer.customer_name → id → priority.
    customer_names = list({
        getattr(o, "customer_name", None)
        for o in order_by_lid.values()
        if getattr(o, "customer_name", None)
    })
    priority_by_customer: Dict[str, int] = {}
    if customer_names:
        try:
            cust_stmt = select(Customer).where(
                and_(
                    Customer.tenant_id == tenant_id,
                    Customer.customer_name.in_(customer_names),
                )
            )
            customers = list((await db.execute(cust_stmt)).scalars().all())
            cust_id_to_name = {c.id: c.customer_name for c in customers}
            if cust_id_to_name:
                cp_stmt = select(ClientPriority).where(
                    and_(
                        ClientPriority.tenant_id == tenant_id,
                        ClientPriority.client_id.in_(list(cust_id_to_name.keys())),
                    )
                )
                for cp_row in (await db.execute(cp_stmt)).scalars().all():
                    name = cust_id_to_name.get(cp_row.client_id)
                    if name is not None:
                        priority_by_customer[name] = int(cp_row.priority)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("ClientPriority batch skipped (%s)", exc)

    # 6. Constrói boost por legacy_id e injecta em cada op.
    boost_by_lid: Dict[int, int] = {}
    for lid, order in order_by_lid.items():
        ob = order_boost_map.get(lid, 0)
        bb = boat_boost_map.get(getattr(order, "product_name", ""), 0)
        customer = getattr(order, "customer_name", None)
        priority = priority_by_customer.get(customer) if customer else None
        boost_by_lid[lid] = int(
            compute_effective_boost(
                client_priority=priority,
                order_boost=ob,
                boat_boost=bb,
            )
        )

    for op in operations:
        raw = op.get("order_id")
        try:
            lid = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            lid = None
        op["effective_boost"] = boost_by_lid.get(lid, 0) if lid is not None else 0


__all__ = [
    "_tenant_id",
    "_resolve_commit_or_404",
    "_extract_mapelites_representatives",
    "_compute_trust_index_for_schedule",
    "_load_product_prices",
    "_relative_delta",
    "_format_delta_pct",
    "_build_narrative",
    "_attach_effective_boost",
]
