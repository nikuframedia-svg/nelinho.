"""
ProdPlan ONE — DB-backed training datasets (Q.53.A)
=====================================================

The Sprint H retrain jobs originally read their training rows from the
in-memory curated layer (`SemanticQueriesInMemory`). In the deployed NELO
factory that layer is populated lazily and is empty most of the time, so
`load_active_quality_risk_predictor()` always returned ``None`` and the CPO
ran with no ML.

This module reads the training rows straight from the durable tables that
the ERP sync already fills:

  * ``factory_curated.order_phase`` — ~86k completed phase executions with
    real durations (``horas_reais``), the fase id, the order id and the
    mould id. This is the cleaned `OF_FP` history.
  * ``quality.rework_entry``        — ~100k rework events, each tagged with
    the phase that caused it (``phase_id_causer``) and the hull zone
    (``location_zone``).
  * ``plan.production_orders``      — the kayak model per order, used to
    enrich ``modelo_id`` when the order id is known.

The two history tables do not share an order-id space (the ERP keeps phase
history and checklist rework on different id sequences), so the
``is_error`` label for the quality-risk classifier is built from the
**empirical per-fase rework rate**: for each fase we know how many phase
executions happened and how many rework events were blamed on it; we then
deterministically stratify-label that fraction of the fase's phase rows as
``is_error=1``. That keeps the real, learnable signal — "Laminagem and
Pintura are error-prone, Armazém is not" — without inventing per-row joins
that the data cannot support.

Everything here is best-effort: a missing table or an empty result yields
``[]`` (with a WARN), which the surrounding `RetrainJob.run` turns into an
explicit `EmptyDatasetError` rather than training on nothing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Duration dataset
# ---------------------------------------------------------------------------

async def build_duration_dataset(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 60_000,
) -> List[Dict[str, Any]]:
    """One row per completed phase execution with a positive real duration.

    Feature schema matches `DurationModel` (modelo_id, fase_id, team_size,
    mold_pocket_count, is_rework, queue_depth, horas_reais, timestamp).
    `factory_curated.order_phase` is tenant-agnostic (it is the shared
    curated layer), so `tenant_id` only scopes the production-orders join.
    """
    sql = text(
        """
        SELECT
            op.of_id              AS of_id,
            op.fase_id            AS fase_id,
            op.fase_nome          AS fase_nome,
            op.molde_id           AS molde_id,
            op.horas_reais        AS horas_reais,
            op.data_inicio        AS data_inicio,
            po.product_type       AS product_type
        FROM factory_curated.order_phase op
        LEFT JOIN plan.production_orders po
               ON po.legacy_id::text = op.of_id
              AND po.tenant_id = :tenant_id
        WHERE op.horas_reais IS NOT NULL
          AND op.horas_reais > 0
          AND op.is_quarantined = false
        ORDER BY op.data_inicio
        LIMIT :limit
        """
    )
    try:
        result = await session.execute(
            sql, {"tenant_id": str(tenant_id), "limit": limit}
        )
        raw = result.mappings().all()
    except Exception as exc:  # pragma: no cover — DB outage / missing table
        logger.warning(
            "build_duration_dataset: query failed (%s) — returning empty dataset.",
            exc,
        )
        return []

    if not raw:
        logger.warning(
            "build_duration_dataset: factory_curated.order_phase has no usable "
            "rows — returning empty dataset."
        )
        return []

    # queue_depth proxy: how busy a fase is across the whole window.
    fase_counts: Dict[str, int] = {}
    for r in raw:
        fid = str(r["fase_id"])
        fase_counts[fid] = fase_counts.get(fid, 0) + 1

    rows: List[Dict[str, Any]] = []
    for r in raw:
        fase_id = str(r["fase_id"])
        rows.append(
            {
                "modelo_id": str(r["product_type"] or "desconhecido"),
                "fase_id": fase_id,
                "team_size": 1,  # not tracked on order_phase — neutral default
                "mold_pocket_count": 1,  # order_phase has no pocket count — neutral default
                "is_rework": 0,
                "queue_depth": fase_counts.get(fase_id, 0),
                "horas_reais": float(r["horas_reais"]),
                "timestamp": r["data_inicio"],
            }
        )
    logger.info("build_duration_dataset: %d rows from order_phase", len(rows))
    return rows


# ---------------------------------------------------------------------------
# Quality-risk dataset
# ---------------------------------------------------------------------------

def _normalise_phase_key(value: Any) -> str:
    """Rework `phase_id_causer` is mostly the numeric fase id but a handful
    of rows carry a text label ('Laminagem'). Keep numeric ids verbatim so
    they line up with `order_phase.fase_id`; lower-case the rest.
    """
    s = str(value or "").strip()
    return s if s.isdigit() else s.lower()


async def build_quality_risk_dataset(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 60_000,
) -> List[Dict[str, Any]]:
    """One row per completed phase execution with a binary `is_error` label.

    Label construction (see module docstring): for every fase we compute the
    empirical rework rate ``rework_events / phase_executions`` and then
    deterministically mark the first ``rate × n`` phase rows of that fase
    (ordered by start date) as ``is_error=1``. This reproduces the real
    per-fase error rate, which is exactly the signal the classifier learns
    against the (modelo_id, fase_id, team_size, mold_pocket_count,
    phase_error_rate, queue_depth) features.
    """
    phase_sql = text(
        """
        SELECT
            op.of_id        AS of_id,
            op.fase_id      AS fase_id,
            op.molde_id     AS molde_id,
            op.data_inicio  AS data_inicio,
            po.product_type AS product_type
        FROM factory_curated.order_phase op
        LEFT JOIN plan.production_orders po
               ON po.legacy_id::text = op.of_id
              AND po.tenant_id = :tenant_id
        WHERE op.is_quarantined = false
        ORDER BY op.fase_id, op.data_inicio
        LIMIT :limit
        """
    )
    rework_sql = text(
        """
        SELECT phase_id_causer AS phase, COUNT(*) AS n
        FROM quality.rework_entry
        WHERE tenant_id = :tenant_id
          AND phase_id_causer IS NOT NULL
        GROUP BY phase_id_causer
        """
    )
    try:
        phase_rows = (
            await session.execute(
                phase_sql, {"tenant_id": str(tenant_id), "limit": limit}
            )
        ).mappings().all()
        rework_rows = (
            await session.execute(rework_sql, {"tenant_id": str(tenant_id)})
        ).all()
    except Exception as exc:  # pragma: no cover — DB outage / missing table
        logger.warning(
            "build_quality_risk_dataset: query failed (%s) — returning empty "
            "dataset.",
            exc,
        )
        return []

    if not phase_rows:
        logger.warning(
            "build_quality_risk_dataset: factory_curated.order_phase empty — "
            "returning empty dataset."
        )
        return []

    rework_by_fase: Dict[str, int] = {}
    for phase, n in rework_rows:
        rework_by_fase[_normalise_phase_key(phase)] = (
            rework_by_fase.get(_normalise_phase_key(phase), 0) + int(n or 0)
        )

    # Count phase executions per fase so we can turn the rework count into a
    # rate and cap labelled positives at the number of phase rows we have.
    phase_counts: Dict[str, int] = {}
    for r in phase_rows:
        fid = str(r["fase_id"])
        phase_counts[fid] = phase_counts.get(fid, 0) + 1

    # Empirical per-fase error rate, clamped to [0, 0.95] so no fase is
    # all-positive (the classifier needs both classes).
    fase_error_rate: Dict[str, float] = {}
    for fid, total in phase_counts.items():
        events = rework_by_fase.get(fid, 0)
        rate = events / total if total else 0.0
        fase_error_rate[fid] = min(0.95, max(0.0, rate))

    rows: List[Dict[str, Any]] = []
    seen_per_fase: Dict[str, int] = {}
    for r in phase_rows:
        fase_id = str(r["fase_id"])
        total = phase_counts.get(fase_id, 0)
        rate = fase_error_rate.get(fase_id, 0.0)
        positives_target = round(rate * total)
        idx = seen_per_fase.get(fase_id, 0)
        seen_per_fase[fase_id] = idx + 1
        # phase_rows are ordered by (fase_id, data_inicio); the first
        # `positives_target` rows of the fase are the labelled errors.
        is_error = 1 if idx < positives_target else 0

        rows.append(
            {
                "modelo_id": str(r["product_type"] or "desconhecido"),
                "fase_id": fase_id,
                "team_size": 1,
                "mold_pocket_count": 1,
                "phase_error_rate": round(rate, 4),
                "queue_depth": total,
                "is_error": is_error,
                "timestamp": r["data_inicio"],
            }
        )

    positives = sum(r["is_error"] for r in rows)
    logger.info(
        "build_quality_risk_dataset: %d rows from order_phase ⋈ rework "
        "(%d positives, prior=%.3f)",
        len(rows),
        positives,
        positives / len(rows) if rows else 0.0,
    )
    return rows


# ---------------------------------------------------------------------------
# OTD-risk dataset (Sprint Q.54.F)
# ---------------------------------------------------------------------------

async def build_otd_risk_dataset(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 40_000,
) -> List[Dict[str, Any]]:
    """One row per *completed* production order with a binary `is_late`
    label (1 = the kayak finished after its transport date).

    The label is the real history: `plan.production_orders` carries
    `completed_date` (actual finish) and `transport_date` (the promised
    ship date). An order with both dates and `completed_date >
    transport_date` is late.

    Features are sized from `factory_curated.order_phase` — the number
    of phases and total real hours the order actually consumed — plus
    `slack_days` (transport_date − completed_date; negative = overran)
    and the per-fase rework rate folded into a per-order mean. Feature
    schema matches `OTDRiskModel`.

    `factory_curated.order_phase` is tenant-agnostic (shared curated
    layer); `tenant_id` only scopes `production_orders` and the rework
    table.
    """
    order_sql = text(
        """
        SELECT
            po.legacy_id        AS legacy_id,
            po.product_type     AS product_type,
            po.completed_date   AS completed_date,
            po.transport_date   AS transport_date
        FROM plan.production_orders po
        WHERE po.tenant_id = :tenant_id
          AND po.completed_date IS NOT NULL
          AND po.transport_date IS NOT NULL
        ORDER BY po.completed_date
        LIMIT :limit
        """
    )
    phase_sql = text(
        """
        SELECT
            op.of_id       AS of_id,
            op.fase_id     AS fase_id,
            op.horas_reais AS horas_reais
        FROM factory_curated.order_phase op
        WHERE op.is_quarantined = false
        """
    )
    rework_sql = text(
        """
        SELECT phase_id_causer AS phase, COUNT(*) AS n
        FROM quality.rework_entry
        WHERE tenant_id = :tenant_id
          AND phase_id_causer IS NOT NULL
        GROUP BY phase_id_causer
        """
    )
    try:
        order_rows = (
            await session.execute(
                order_sql, {"tenant_id": str(tenant_id), "limit": limit}
            )
        ).mappings().all()
        phase_rows = (await session.execute(phase_sql)).mappings().all()
        rework_rows = (
            await session.execute(rework_sql, {"tenant_id": str(tenant_id)})
        ).all()
    except Exception as exc:  # pragma: no cover — DB outage / missing table
        logger.warning(
            "build_otd_risk_dataset: query failed (%s) — returning empty "
            "dataset.",
            exc,
        )
        return []

    if not order_rows:
        logger.warning(
            "build_otd_risk_dataset: plan.production_orders has no completed "
            "orders with a transport date — returning empty dataset."
        )
        return []

    # Per-fase phase counts → per-fase rework rate (same construction as
    # the quality-risk builder).
    phase_counts: Dict[str, int] = {}
    for r in phase_rows:
        fid = str(r["fase_id"])
        phase_counts[fid] = phase_counts.get(fid, 0) + 1
    rework_by_fase: Dict[str, int] = {}
    for phase, n in rework_rows:
        key = _normalise_phase_key(phase)
        rework_by_fase[key] = rework_by_fase.get(key, 0) + int(n or 0)
    fase_error_rate: Dict[str, float] = {}
    for fid, total in phase_counts.items():
        events = rework_by_fase.get(fid, 0)
        fase_error_rate[fid] = min(0.95, (events / total) if total else 0.0)

    # Group phase executions per order.
    phases_by_order: Dict[str, List[Dict[str, Any]]] = {}
    for r in phase_rows:
        of_id = str(r["of_id"])
        phases_by_order.setdefault(of_id, []).append(r)

    rows: List[Dict[str, Any]] = []
    for o in order_rows:
        of_id = str(o["legacy_id"])
        completed = o["completed_date"]
        transport = o["transport_date"]
        try:
            is_late = 1 if completed > transport else 0
            slack_days = float((transport - completed).days)
        except (TypeError, AttributeError):
            continue

        order_phases = phases_by_order.get(of_id, [])
        n_phases = len(order_phases)
        total_hours = sum(
            float(p["horas_reais"] or 0)
            for p in order_phases
            if p["horas_reais"]
        )
        error_rates = [
            fase_error_rate.get(str(p["fase_id"]), 0.0) for p in order_phases
        ]
        phase_error_rate_mean = (
            sum(error_rates) / len(error_rates) if error_rates else 0.0
        )

        rows.append(
            {
                "modelo_id": str(o["product_type"] or "desconhecido"),
                "n_phases": n_phases,
                "total_planned_hours": round(total_hours, 2),
                "slack_days": round(slack_days, 2),
                "open_phases": 0,  # training rows are completed orders
                "phase_error_rate_mean": round(phase_error_rate_mean, 4),
                "is_late": is_late,
                "timestamp": completed,
            }
        )

    positives = sum(r["is_late"] for r in rows)
    logger.info(
        "build_otd_risk_dataset: %d completed orders (%d late, prior=%.3f)",
        len(rows),
        positives,
        positives / len(rows) if rows else 0.0,
    )
    return rows
