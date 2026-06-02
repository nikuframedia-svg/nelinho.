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

  * ``factory_raw.of_fp`` — ~537k real phase executions (one row per
    OFFP), with the start/finish timestamps (``OFFP_DATAINICIO`` /
    ``OFFP_DATAFIM`` → real ``horas_reais``), the fase id (``OFFP_FP_ID``),
    the order id (``OFFP_OF_ID``) and the mould id (``OFFP_OF_ID_MLD``).
    This is the REAL ERP history mirrored from NELO — **not** the static
    Excel snapshot (Q.124: o ML aprende da BD viva, nunca de um ficheiro).
    The kayak product per order is enriched from ``factory_raw.ordemfabrico``
    (``OF_P_ID``).
  * ``quality.rework_entry``        — rework events, each tagged with the
    phase that caused it (``phase_id_causer``, numeric fase id matching
    ``OFFP_FP_ID``) and the hull zone (``location_zone``).
  * ``plan.production_orders``      — completed orders with transport dates,
    the label source for the OTD-risk model.

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
from typing import TYPE_CHECKING, Any, Dict, List
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:  # pandas é import lazy dentro das funções; isto resolve os
    import pandas as pd  # type hints "pd.DataFrame" sem o import eager (Q.120.A).

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
    # Q.124: fonte = factory_raw.of_fp (ERP real espelhado), nao a camada
    # curated/Excel. horas_reais = (OFFP_DATAFIM - OFFP_DATAINICIO) em horas,
    # mesmo padrao de limpeza de setup_marts_lead_time_of (exclui o mesmo
    # segundo / fim < inicio como artefacto).
    sql = text(
        """
        SELECT
            op."OFFP_OF_ID"     AS of_id,
            op."OFFP_FP_ID"     AS fase_id,
            fp."FP_NOME"        AS fase_nome,
            op."OFFP_OF_ID_MLD" AS molde_id,
            EXTRACT(EPOCH FROM (
                CAST(NULLIF(op."OFFP_DATAFIM", '')    AS timestamp)
              - CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp)
            )) / 3600.0         AS horas_reais,
            CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp) AS data_inicio,
            ofb."OF_P_ID"       AS product_type,
            -- Q.156.D (BD-3) — team_size real por execução de fase, vindo de
            -- factory_raw.offp_eq (crew records). Antes hardcoded=1. COALESCE
            -- mantém o default neutro p/ fases sem equipa (ex.: Cura).
            COALESCE(eqc.team_size, 1) AS team_size
        FROM factory_raw.of_fp op
        LEFT JOIN factory_raw.fases_producao fp ON fp."FP_ID" = op."OFFP_FP_ID"
        LEFT JOIN factory_raw.ordemfabrico  ofb ON ofb."OF_ID" = op."OFFP_OF_ID"
        LEFT JOIN (
            SELECT "OFFPEQ_OFFP_ID" AS offp_id, COUNT(*) AS team_size
            FROM factory_raw.offp_eq GROUP BY "OFFPEQ_OFFP_ID"
        ) eqc ON eqc.offp_id = op."OFFP_ID"
        WHERE NULLIF(op."OFFP_DATAINICIO", '') IS NOT NULL
          AND NULLIF(op."OFFP_DATAFIM", '')    IS NOT NULL
          AND CAST(NULLIF(op."OFFP_DATAFIM", '') AS timestamp)
            > CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp)
          -- Q.124 "limpos": teto de 168h (1 semana) exclui fases deixadas
          -- abertas (artefacto de calendario) que envenenavam o WMAPE.
          AND EXTRACT(EPOCH FROM (
                CAST(NULLIF(op."OFFP_DATAFIM", '')    AS timestamp)
              - CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp)
              )) / 3600.0 <= 168.0
        ORDER BY data_inicio
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
                "team_size": int(r.get("team_size") or 1),  # Q.156.D — real, de offp_eq
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
    # Q.124: fonte = factory_raw.of_fp (ERP real). Todas as execucoes de fase
    # (sem filtro de duracao) para construir a taxa empirica de rework por fase.
    phase_sql = text(
        """
        SELECT
            op."OFFP_OF_ID"     AS of_id,
            op."OFFP_FP_ID"     AS fase_id,
            op."OFFP_OF_ID_MLD" AS molde_id,
            CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp) AS data_inicio,
            ofb."OF_P_ID"       AS product_type,
            -- Q.156.D (BD-3) — team_size real de factory_raw.offp_eq.
            COALESCE(eqc.team_size, 1) AS team_size
        FROM factory_raw.of_fp op
        LEFT JOIN factory_raw.ordemfabrico ofb ON ofb."OF_ID" = op."OFFP_OF_ID"
        LEFT JOIN (
            SELECT "OFFPEQ_OFFP_ID" AS offp_id, COUNT(*) AS team_size
            FROM factory_raw.offp_eq GROUP BY "OFFPEQ_OFFP_ID"
        ) eqc ON eqc.offp_id = op."OFFP_ID"
        WHERE NULLIF(op."OFFP_DATAINICIO", '') IS NOT NULL
        ORDER BY op."OFFP_FP_ID", data_inicio
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
                "team_size": int(r.get("team_size") or 1),  # Q.156.D — real, de offp_eq
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
    # Q.124: fonte = factory_raw.of_fp (ERP real). Limitado: o otd_risk so usa
    # fases das ordens completas (plan.production_orders), hoje poucas — o modelo
    # fica fino ate o plano ter ordens reais (Onda 4).
    phase_sql = text(
        """
        SELECT
            op."OFFP_OF_ID" AS of_id,
            op."OFFP_FP_ID" AS fase_id,
            EXTRACT(EPOCH FROM (
                CAST(NULLIF(op."OFFP_DATAFIM", '')    AS timestamp)
              - CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp)
            )) / 3600.0     AS horas_reais
        FROM factory_raw.of_fp op
        WHERE NULLIF(op."OFFP_DATAINICIO", '') IS NOT NULL
          AND NULLIF(op."OFFP_DATAFIM", '')    IS NOT NULL
        LIMIT 200000
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


# ---------------------------------------------------------------------------
# SequenceMining — fases_of_history (Q.115.U)
# ---------------------------------------------------------------------------

async def load_phase_histories(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 100_000,
) -> "pd.DataFrame":
    """
    Retorna DataFrame [of_id, phase_code, phase_order] de plan.fases_of_history.
    Fallback para factory_curated.order_phase se a tabela ainda não existir.
    """
    import pandas as pd

    sql = text(
        """
        SELECT of_id, phase_code, phase_order
        FROM plan.fases_of_history
        WHERE tenant_id = :tenant_id
        ORDER BY of_id, phase_order
        LIMIT :limit
        """
    )
    try:
        rows = (
            await session.execute(sql, {"tenant_id": str(tenant_id), "limit": limit})
        ).mappings().all()
        if rows:
            return pd.DataFrame([dict(r) for r in rows])
    except Exception as exc:
        logger.warning("load_phase_histories: %s — fallback para order_phase", exc)

    # Fallback: order_phase
    fallback_sql = text(
        """
        SELECT of_id::text AS of_id,
               fase_id::text AS phase_code,
               ROW_NUMBER() OVER (PARTITION BY of_id ORDER BY data_inicio) AS phase_order
        FROM factory_curated.order_phase
        WHERE is_quarantined = false
        LIMIT :limit
        """
    )
    try:
        rows = (await session.execute(fallback_sql, {"limit": limit})).mappings().all()
        if rows:
            return pd.DataFrame([dict(r) for r in rows])
    except Exception as exc2:
        logger.warning("load_phase_histories fallback falhou: %s", exc2)

    return pd.DataFrame(columns=["of_id", "phase_code", "phase_order"])


async def load_defects(
    session: AsyncSession,
    tenant_id: UUID,
) -> "pd.DataFrame":
    """
    Retorna DataFrame [of_id] com OFs que tiveram rework confirmado.
    """
    import pandas as pd

    sql = text(
        """
        SELECT DISTINCT of_id::text AS of_id
        FROM quality.rework_entry
        WHERE tenant_id = :tenant_id
          AND of_id IS NOT NULL
        """
    )
    try:
        rows = (
            await session.execute(sql, {"tenant_id": str(tenant_id)})
        ).mappings().all()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame(columns=["of_id"])
    except Exception as exc:
        logger.warning("load_defects: %s", exc)
        return pd.DataFrame(columns=["of_id"])


# ---------------------------------------------------------------------------
# ThroughputForecast — série temporal (Q.115.U)
# ---------------------------------------------------------------------------

async def load_throughput_ts(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 50_000,
) -> "pd.DataFrame":
    """
    Retorna DataFrame [date, boat_id, ops_concluidas] de plan.fases_of_history.
    Fallback para order_phase se a tabela não existir.
    """
    import pandas as pd

    sql = text(
        """
        SELECT
            DATE(completed_at) AS date,
            boat_id::text AS boat_id,
            COUNT(*) AS ops_concluidas
        FROM plan.fases_of_history
        WHERE tenant_id = :tenant_id
          AND completed_at IS NOT NULL
        GROUP BY DATE(completed_at), boat_id
        ORDER BY date, boat_id
        LIMIT :limit
        """
    )
    try:
        rows = (
            await session.execute(sql, {"tenant_id": str(tenant_id), "limit": limit})
        ).mappings().all()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            df["date"] = pd.to_datetime(df["date"])
            return df
    except Exception as exc:
        logger.warning("load_throughput_ts: %s — fallback para order_phase", exc)

    # Fallback: order_phase agregado por dia + fase
    fallback_sql = text(
        """
        SELECT
            DATE(op.data_inicio) AS date,
            COALESCE(po.product_type, 'desconhecido') AS boat_id,
            COUNT(*) AS ops_concluidas
        FROM factory_curated.order_phase op
        LEFT JOIN plan.production_orders po
               ON po.legacy_id::text = op.of_id
              AND po.tenant_id = :tenant_id
        WHERE op.is_quarantined = false
          AND op.data_inicio IS NOT NULL
        GROUP BY DATE(op.data_inicio), COALESCE(po.product_type, 'desconhecido')
        ORDER BY date, boat_id
        LIMIT :limit
        """
    )
    try:
        rows = (
            await session.execute(
                fallback_sql, {"tenant_id": str(tenant_id), "limit": limit}
            )
        ).mappings().all()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            df["date"] = pd.to_datetime(df["date"])
            return df
    except Exception as exc2:
        logger.warning("load_throughput_ts fallback falhou: %s", exc2)

    return pd.DataFrame(columns=["date", "boat_id", "ops_concluidas"])
