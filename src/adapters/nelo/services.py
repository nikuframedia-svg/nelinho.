"""Async read-only services for the NELO MAR-KAYAKS adapter.

Each function returns Pydantic schemas from `src.adapters.nelo.schemas`.
Queries inline the body of the corresponding `vw_pp1_*` view defined in
`agent_docs/views_pp1.sql` — switch to `SELECT * FROM dbo.vw_pp1_*` once
Nelo IT applies that file on the SQL Server (current user `nikufra` has
DataReader rights only and cannot CREATE VIEW).

Connection
----------
Reads `settings.sqlserver_url` (mssql+aioodbc) and builds an async engine
lazily. NEVER use this engine to write — there is no write path here, and
the source DB is the factory's live ERP.

Usage
-----
    from src.adapters.nelo.services import (
        count_open_orders,
        list_open_orders,
        get_routing,
        ...
    )

    n = await count_open_orders()
    orders = await list_open_orders(limit=20)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.shared.config import settings

logger = logging.getLogger(__name__)

from datetime import date

from .schemas import (
    BomRow,
    ChecklistIncidentRow,
    EntityPhaseRow,
    EntityRow,
    ErpVariableRow,
    FasesOfHistoryRow,
    HealthCheckResult,
    MoldRow,
    MovementRow,
    OperationRow,
    OrderLaborRow,
    OrderRow,
    PhaseRow,
    ProductOrderCount,
    ProductRow,
    ProductStockRow,
    RoutingRow,
    ScheduleRow,
    WarehouseStockRow,
    WorkerAssignmentRow,
)

# ─── Engine ─────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Lazy async engine. One per process, cached."""
    if not settings.sqlserver_enabled or not settings.sqlserver_url:
        raise RuntimeError(
            "sqlserver_enabled=False or sqlserver_url=None. "
            "Configure SQLSERVER_URL in .env before calling NELO services."
        )
    engine = create_async_engine(
        settings.sqlserver_url,
        pool_size=settings.sqlserver_pool_size,
        pool_pre_ping=True,
        future=True,
        # Login/connect timeout (seconds). aioodbc forwards `timeout` to
        # pyodbc.connect() as the login timeout. Without it, an unreachable
        # ERP host blocks on TCP connect for the OS default (~20s+) and
        # hangs every NELO-backed request instead of failing fast so the
        # caller can degrade (e.g. /v1/profit/oee -> erp_available:false).
        connect_args={"timeout": settings.sqlserver_connect_timeout_s},
    )

    # Query timeout: pyodbc's Connection.timeout cancels a statement that runs
    # longer than N seconds (raises OperationalError). `sqlserver_query_timeout_s`
    # existed but was never wired — a heavy OF_FP read (2.6 M rows) could block a
    # request for >90s and tie up a pool slot indefinitely. Now every pooled
    # connection enforces the timeout server-side, so slow reads surface as a
    # SQLAlchemyError the callers already handle (degrade, not hang).
    @event.listens_for(engine.sync_engine, "connect")
    def _set_query_timeout(dbapi_connection, _record):
        # The pyodbc Connection exposes a writable `.timeout` (maps to
        # SQL_ATTR_QUERY_TIMEOUT — seconds). SQLAlchemy's async stack nests it:
        #   AsyncAdapt_aioodbc_connection._connection  -> aioodbc Connection
        #     (whose own `.timeout` is a read-only proxy)
        #     ._conn                                   -> pyodbc Connection
        # Try the deepest layer first, then walk outward.
        candidates = []
        aioodbc_conn = getattr(dbapi_connection, "_connection", None)
        if aioodbc_conn is not None:
            candidates.append(getattr(aioodbc_conn, "_conn", None))
        candidates.append(dbapi_connection)
        for target in candidates:
            if target is None:
                continue
            try:
                target.timeout = settings.sqlserver_query_timeout_s
                break
            except (AttributeError, TypeError):
                # read-only proxy / wrong layer — try the next nesting level
                continue
        else:  # pragma: no cover - driver may not support it
            logger.warning("NELO engine: could not set query timeout on any layer")

    return engine


async def close_engine() -> None:
    """Dispose the cached engine. Call on app shutdown."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_engine.cache_clear()


# ─── Inline view bodies ─────────────────────────────────────────────────
# Each constant matches the corresponding CREATE VIEW body in
# agent_docs/views_pp1.sql. When IT Nelo applies the .sql, replace each
# "(_VW_*_SQL)" subquery with "dbo.vw_pp1_*" in the queries below.

_VW_ORDERS_SQL = """
SELECT
    of_.OF_ID                 AS work_order_id,
    of_.OF_DATA               AS ordered_at,
    of_.OF_DATATRANSPORTE     AS transport_date,
    of_.OF_DATAENTREGA        AS delivery_date,
    of_.OF_DATAINICIO         AS start_date,
    of_.OF_DATAFIM            AS end_date,
    of_.OF_NOME               AS customer_name,
    of_.OF_REFERENCIA         AS reference,
    of_.OF_PRECOCUSTO         AS cost_price,
    of_.OF_PRECOVENDA         AS sale_price,
    of_.OF_DESCONTO           AS discount,
    of_.OF_VALORPAGO          AS paid_amount,
    of_.OF_COEFICIENTE        AS coefficient_eur,
    of_.OF_PAGO               AS is_paid,
    of_.OF_SUPERVISAO         AS supervised,
    of_.OF_SEQUENCIA          AS sequence,
    of_.OF_P_ID               AS product_id,
    of_.OF_E_ID               AS customer_entity_id,
    of_.OF_FP_ID              AS current_phase_id,
    of_.OF_ARM_ID             AS warehouse_id,
    of_.OF_ENC_ID             AS encomenda_id,
    est.EE_NOME               AS encomenda_state,
    cust.E_NOME               AS customer_full_name,
    cust.E_PAIS               AS customer_country
FROM        dbo.ORDEMFABRICO     of_   WITH (NOLOCK)
LEFT JOIN   dbo.ENCOMENDA        enc   WITH (NOLOCK) ON enc.ENC_ID  = of_.OF_ENC_ID
LEFT JOIN   dbo.ENCOMENDA_ESTADO est   WITH (NOLOCK) ON est.EE_ID   = enc.ENC_EE_ID
LEFT JOIN   dbo.ENTIDADE         cust  WITH (NOLOCK) ON cust.E_ID   = of_.OF_E_ID
WHERE of_.OF_DATA > '1900-01-02'
"""

_VW_ROUTINGS_SQL = """
SELECT
    pf.PRODF_ID               AS routing_id,
    pf.PRODF_P_ID             AS product_id,
    pf.PRODF_FP_ID            AS phase_id,
    fp.FP_NOME                AS phase_name,
    fp.FP_DESCRICAO           AS phase_description,
    pf.PRODF_DESCRICAO        AS routing_description,
    pf.PRODF_SEQUENCIA        AS sequence,
    pf.PRODF_TEMPO            AS time_hours,
    fp.FP_HORA_COEF           AS phase_hour_coefficient,
    fp.FP_VALOR_REF_K1        AS k1_reference_hours,
    fp.FP_VALOR_REF_K2        AS k2_reference_hours,
    fp.FP_VALOR_REF_K4        AS k4_reference_hours,
    fp.FP_PRODUCAO            AS phase_is_production,
    fp.FP_AUTOMATICA          AS phase_is_automatic,
    fp.FP_PODE_REPETIR        AS phase_can_repeat,
    pf.PRODF_FABRICO          AS routing_in_production,
    pf.PRODF_COEFICIENTE      AS routing_coefficient,
    pf.PRODF_COEFICIENTE_X    AS routing_coefficient_x,
    pf.PRODF_TPCAM_ID         AS layer_type_id,
    pf.PRODF_DATA             AS created_at,
    pf.PRODF_DATAACTUALIZACAO AS updated_at
FROM        dbo.PRODUTO_FASE   pf  WITH (NOLOCK)
INNER JOIN  dbo.FASES_PRODUCAO fp  WITH (NOLOCK) ON fp.FP_ID = pf.PRODF_FP_ID
WHERE pf.PRODF_DATA_ELIMINADO IS NULL
"""

_VW_BOM_SQL = """
SELECT
    c.COMP_ID                AS bom_id,
    c.COMP_P_ID              AS parent_product_id,
    pp.P_NOME                AS parent_product_name,
    pp.P_NOME_EN             AS parent_product_name_en,
    c.COMP_P_P_ID            AS component_product_id,
    cp.P_NOME                AS component_product_name,
    cp.P_NOME_EN             AS component_product_name_en,
    cp.P_UNI_ID              AS component_unit_id,
    cp.P_STOCK               AS component_stock,
    cp.P_STOCKMIN            AS component_stock_min,
    cp.P_PRECOCUSTO          AS component_cost_price,
    c.COMP_QUANTIDADE        AS quantity,
    c.COMP_TPCOMP_ID         AS component_type_id,
    c.COMP_FP_ID             AS consumption_phase_id,
    c.COMP_FASE_FINAL        AS is_final_phase,
    c.COMP_CONFIGURAVEL      AS configurable,
    c.COMP_UNICO             AS is_unique,
    c.COMP_L_ID              AS list_id,
    c.COMP_OBS               AS observations,
    c.COMP_DATA_ALT          AS changed_at
FROM        dbo.PRODUTO_COMPONENTE c   WITH (NOLOCK)
LEFT JOIN   dbo.PRODUTO            pp  WITH (NOLOCK) ON pp.P_ID = c.COMP_P_ID
INNER JOIN  dbo.PRODUTO            cp  WITH (NOLOCK) ON cp.P_ID = c.COMP_P_P_ID
WHERE c.COMP_ELIMINADO IS NULL
"""

_VW_SCHEDULE_SQL = """
SELECT
    p.PlaneamentoDiarioId    AS schedule_id,
    p.Dia                    AS day,
    p.HoraInicio             AS start_hour,
    p.HoraFim                AS end_hour,
    p.NumeroFuncionarios     AS headcount,
    p.TransporteId           AS transport_id,
    CAST(p.HoraFim - p.HoraInicio AS int) AS shift_hours
FROM dbo.PLANEAMENTO_DIARIO p WITH (NOLOCK)
"""

_VW_OPERATIONS_SQL = """
SELECT
    offp.OFFP_ID                AS operation_id,
    offp.OFFP_OF_ID             AS work_order_id,
    offp.OFFP_FP_ID             AS phase_id,
    fp.FP_NOME                  AS phase_name,
    offp.OFFP_DATAINICIO        AS start_at,
    offp.OFFP_DATAFIM           AS end_at,
    offp.OFFP_DATA_PREVISTA     AS expected_at,
    COALESCE(pf.PRODF_TEMPO, fp.FP_VALOR_REF_K1, 0) AS standard_time_hours,
    offp.OFFP_TEMPERATURA       AS temperature,
    offp.OFFP_HUMIDADE          AS humidity,
    offp.OFFP_PROBS_GOLA        AS problem_neck,
    offp.OFFP_PROBS_INTERIOR    AS problem_interior_id,
    offp.OFFP_PROBS_PINTURA     AS problem_paint_id,
    offp.OFFP_PROBS_MOLDE       AS problem_mold_id,
    offp.OFFP_PROBS_LAMINAGEM   AS problem_lamination_id,
    offp.OFFP_PROBS_DATA        AS problem_logged_at,
    offp.OFFP_RETURN            AS is_return,
    offp.OFFP_RETORNO_GRAVE     AS severe_return,
    of_.OF_P_ID                 AS product_id,
    of_.OF_TURN_ID              AS shift_id,
    of_.OF_OF_ID_MLD            AS mold_work_order_id,
    pt.TP_NOME                  AS product_type_name,
    fp.FP_AUTOMATICA            AS phase_is_automatic
FROM        dbo.OF_FP            offp WITH (NOLOCK)
INNER JOIN  dbo.FASES_PRODUCAO   fp   WITH (NOLOCK) ON fp.FP_ID = offp.OFFP_FP_ID
INNER JOIN  dbo.ORDEMFABRICO     of_  WITH (NOLOCK) ON of_.OF_ID = offp.OFFP_OF_ID
INNER JOIN  dbo.PRODUTO          p    WITH (NOLOCK) ON p.P_ID = of_.OF_P_ID
LEFT JOIN   dbo.PRODUTO_TIPO     pt   WITH (NOLOCK) ON pt.TP_ID = p.P_TP_ID
LEFT JOIN   dbo.PRODUTO_FASE     pf   WITH (NOLOCK)
            ON pf.PRODF_P_ID = of_.OF_P_ID
           AND pf.PRODF_FP_ID = offp.OFFP_FP_ID
           AND pf.PRODF_DATA_ELIMINADO IS NULL
"""


# Q.26.C.2 — per-order labour: every OF_FP execution of one work order
# joined to its operators via OFFP_EQ. One row per (operation, operator);
# the inner join drops phases with no operator (Cura etc.).
_VW_ORDER_LABOR_SQL = """
SELECT
    offp.OFFP_ID         AS operation_id,
    offp.OFFP_OF_ID      AS work_order_id,
    offp.OFFP_FP_ID      AS phase_id,
    fp.FP_NOME           AS phase_name,
    offp.OFFP_DATAINICIO AS start_at,
    offp.OFFP_DATAFIM    AS end_at,
    offp.OFFP_RETURN     AS is_return,
    eq.OFFPEQ_E_ID       AS operator_id,
    eq.OFFPEQ_CHEFE      AS is_chefe
FROM        dbo.OF_FP          offp WITH (NOLOCK)
INNER JOIN  dbo.OFFP_EQ        eq   WITH (NOLOCK) ON eq.OFFPEQ_OFFP_ID = offp.OFFP_ID
INNER JOIN  dbo.FASES_PRODUCAO fp   WITH (NOLOCK) ON fp.FP_ID = offp.OFFP_FP_ID
WHERE offp.OFFP_OF_ID = :work_order_id
"""


_VW_MOVEMENTS_SQL = """
SELECT
    m.MOV_ID                 AS movement_id,
    m.MOV_DATA               AS moved_at,
    m.MOV_DATASAIDA          AS exit_date,
    m.MOV_QUANTIDADE         AS quantity,
    m.MOV_PRECOUNITARIO      AS unit_price,
    m.MOV_PRECOVENDA         AS sale_price,
    m.MOV_DESCONTO           AS discount,
    m.MOV_TPMOV_ID           AS movement_type_id,
    m.MOV_OF_ID              AS work_order_id,
    m.MOV_OFFP_ID            AS work_order_phase_id,
    m.MOV_P_ID               AS product_id,
    m.MOV_E_ID               AS entity_id,
    m.MOV_ARM_ID             AS warehouse_id,
    m.MOV_FP_ID              AS phase_id,
    m.MOV_PRODF_ID           AS routing_id,
    m.MOV_MOV_ID             AS parent_movement_id,
    m.MOV_LOTE               AS batch,
    m.MOV_QTD_BAL            AS balance_quantity,
    m.MOV_ACERTO             AS is_adjustment,
    m.MOV_DEFEITUOSO         AS is_defective,
    m.MOV_SATISFEITO         AS is_satisfied,
    m.MOV_DATA_APROVADO      AS approved_at,
    m.MOV_OBSERVACOES        AS observations,
    m.MOV_PROBLEMA           AS problem
FROM dbo.MOVIMENTO m WITH (NOLOCK)
WHERE m.MOV_DATA >= DATEADD(month, -12, CAST(GETDATE() AS date))
"""


# Q.20.A — master-data view bodies (used by the ETL mirrors). Column
# names verified against agent_docs/mar_kayaks_schema_discovery.md —
# FASES_PRODUCAO (FP_*), ENTIDADE (E_*), ENTIDADE_FASE (EFP_*),
# MOLDES (MLD_*). No guessed names.

_VW_PHASES_SQL = """
SELECT
    fp.FP_ID            AS phase_id,
    fp.FP_NOME          AS phase_name,
    fp.FP_DESCRICAO     AS phase_description,
    fp.FP_SEQUENCIA     AS sequence,
    fp.FP_PRODUCAO      AS is_production,
    fp.FP_AUTOMATICA    AS is_automatic,
    fp.FP_PODE_REPETIR  AS can_repeat,
    fp.FP_FP_ID         AS parent_phase_id,
    fp.FP_HORA_COEF     AS hour_coefficient,
    fp.FP_VALOR_REF_K1  AS k1_reference_hours,
    fp.FP_VALOR_REF_K2  AS k2_reference_hours,
    fp.FP_VALOR_REF_K4  AS k4_reference_hours
FROM dbo.FASES_PRODUCAO fp WITH (NOLOCK)
"""

_VW_ENTITIES_SQL = """
SELECT
    e.E_ID            AS entity_id,
    e.E_NOME          AS name,
    e.E_ACTIVO        AS active,
    e.E_NELO          AS is_internal,
    e.E_TRANSPORTADOR AS is_carrier,
    e.E_CHEFE         AS is_supervisor,
    e.E_CUSTOHORA     AS cost_per_hour,
    e.E_NIVEL         AS level,
    e.E_PRODUTIVIDADE AS productivity,
    e.E_ENT_ID        AS entity_type_id,
    et.ENT_NOME       AS entity_type_name,
    e.E_DATAENTRADA   AS entry_date,
    e.E_PAIS          AS country,
    e.E_EMAIL         AS email
FROM        dbo.ENTIDADE      e   WITH (NOLOCK)
LEFT JOIN   dbo.ENTIDADE_TIPO et  WITH (NOLOCK) ON et.ENT_ID = e.E_ENT_ID
"""

_VW_ENTITY_PHASES_SQL = """
SELECT
    ef.EFP_ID            AS entity_phase_id,
    ef.EFP_E_ID          AS entity_id,
    ef.EFP_FP_ID         AS phase_id,
    ef.EFP_PRODUTIVIDADE AS proficiency,
    ef.EFP_CHEFE         AS is_supervisor,
    ef.EFP_QUALIFICADO   AS qualified,
    ef.EFP_DATAINICIO    AS start_date,
    ef.EFP_DATAFIM       AS end_date
FROM dbo.ENTIDADE_FASE ef WITH (NOLOCK)
"""

_VW_MOLDS_SQL = """
SELECT
    mld.MLD_ID       AS mold_id,
    mld.MLD_NOME     AS mold_name,
    mld.MLD_MLDTP_ID AS mold_type_id,
    mld.MLD_UTILIZ   AS usage_count,
    mld.MLD_DATA     AS acquired_at
FROM dbo.MOLDES mld WITH (NOLOCK)
"""


# Q.167.A — canonical root-cause source. `OF_CHECKLIST` is the only place
# the ERP separates the phase that CAUSED a defect (`OFCH_FP_ID`) from the
# phase that DETECTED it (`OFCH_FP_ID_CHK`) — distinct in 78.5% of rows —
# and names the culprit operation (`OFCH_OFFP_ID_CULPA`), from which the
# responsible operator + chefe come via `OFFP_EQ`. Only real defects
# (`OFCH_GRAVIDADE >= 1`) are surfaced; gravidade 0 is an "Ok" tick.
# Heavy table (3 M rows) — always window on `OFCH_DATA_ACTUALIZACAO`.
_VW_CHECKLIST_SQL = """
SELECT
    ch.OFCH_ID            AS checklist_id,
    ch.OFCH_OF_ID         AS work_order_id,
    ch.OFCH_FP_ID         AS phase_id_causer,
    ch.OFCH_FP_ID_CHK     AS phase_id_detector,
    ch.OFCH_GRAVIDADE     AS gravidade,
    ch.OFCH_ESTADO        AS estado,
    ch.OFCH_CULPA_CHEFE   AS culpa_chefe,
    ch.OFCH_MOLDE_REPARAR AS molde_reparar,
    ch.OFCH_OFFP_ID       AS detector_op_id,
    ch.OFCH_OFFP_ID_CULPA AS causer_op_id,
    ch.OFCH_DESCR         AS description,
    COALESCE(ch.OFCH_DATA_VERIFICACAO, ch.OFCH_DATA_ACTUALIZACAO) AS detected_at,
    of_.OF_P_ID           AS product_id,
    pt.TP_NOME            AS product_type_name,
    chefe.OFFPEQ_E_ID     AS causer_chefe_eid,
    oper.OFFPEQ_E_ID      AS causer_operator_eid
FROM        dbo.OF_CHECKLIST ch  WITH (NOLOCK)
INNER JOIN  dbo.ORDEMFABRICO of_ WITH (NOLOCK) ON of_.OF_ID = ch.OFCH_OF_ID
INNER JOIN  dbo.PRODUTO      p   WITH (NOLOCK) ON p.P_ID = of_.OF_P_ID
LEFT JOIN   dbo.PRODUTO_TIPO pt  WITH (NOLOCK) ON pt.TP_ID = p.P_TP_ID
OUTER APPLY (SELECT TOP 1 eq.OFFPEQ_E_ID FROM dbo.OFFP_EQ eq WITH (NOLOCK)
             WHERE eq.OFFPEQ_OFFP_ID = ch.OFCH_OFFP_ID_CULPA AND eq.OFFPEQ_CHEFE = 1) chefe
OUTER APPLY (SELECT TOP 1 eq.OFFPEQ_E_ID FROM dbo.OFFP_EQ eq WITH (NOLOCK)
             WHERE eq.OFFPEQ_OFFP_ID = ch.OFCH_OFFP_ID_CULPA AND eq.OFFPEQ_CHEFE = 0) oper
WHERE ch.OFCH_GRAVIDADE >= 1
"""


async def _fetch_all(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a SELECT and return list of row dicts (column → value)."""
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params or {})
        return [dict(r) for r in result.mappings().all()]


async def _fetch_scalar(sql: str, params: dict[str, Any] | None = None) -> Any:
    """Run a query returning a single scalar value."""
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params or {})
        row = result.first()
        return row[0] if row else None


# ─── Public services ────────────────────────────────────────────────────


async def list_open_orders(limit: int = 100) -> list[OrderRow]:
    """Open work orders — `OF_DATAFIM IS NULL` (still in production).

    Ordered by ordered_at DESC. Replace inline subquery with
    `dbo.vw_pp1_orders` once view is created.
    """
    sql = f"""
    SELECT TOP {int(limit)} * FROM (
        {_VW_ORDERS_SQL}
    ) v
    WHERE v.end_date IS NULL
    ORDER BY v.ordered_at DESC
    """
    rows = await _fetch_all(sql)
    return [OrderRow(**r) for r in rows]


async def count_open_orders() -> int:
    """Count WOs with `OF_DATAFIM IS NULL`. Direct query — faster than view subquery."""
    sql = """
    SELECT COUNT_BIG(*)
    FROM dbo.ORDEMFABRICO WITH (NOLOCK)
    WHERE OF_DATAFIM IS NULL AND OF_DATA > '1900-01-02'
    """
    n = await _fetch_scalar(sql)
    return int(n or 0)


async def get_routing(product_id: int) -> list[RoutingRow]:
    """Routing (phase sequence) for a product, ordered by `sequence`."""
    sql = f"""
    SELECT * FROM (
        {_VW_ROUTINGS_SQL}
    ) v
    WHERE v.product_id = :product_id
    ORDER BY v.sequence
    """
    rows = await _fetch_all(sql, {"product_id": product_id})
    return [RoutingRow(**r) for r in rows]


async def get_bom(product_id: int) -> list[BomRow]:
    """BOM of a product. Returns active component lines (`COMP_ELIMINADO IS NULL`)."""
    sql = f"""
    SELECT * FROM (
        {_VW_BOM_SQL}
    ) v
    WHERE v.parent_product_id = :product_id
    ORDER BY v.consumption_phase_id, v.component_product_id
    """
    rows = await _fetch_all(sql, {"product_id": product_id})
    return [BomRow(**r) for r in rows]


async def list_recent_movements(limit: int = 100) -> list[MovementRow]:
    """Most recent stock movements (within the view's 12-month window)."""
    sql = f"""
    SELECT TOP {int(limit)} * FROM (
        {_VW_MOVEMENTS_SQL}
    ) v
    ORDER BY v.moved_at DESC
    """
    rows = await _fetch_all(sql)
    return [MovementRow(**r) for r in rows]


async def list_current_schedule(limit: int = 50) -> list[ScheduleRow]:
    """Daily schedule rows ordered by day DESC (most recent first)."""
    sql = f"""
    SELECT TOP {int(limit)} * FROM (
        {_VW_SCHEDULE_SQL}
    ) v
    ORDER BY v.day DESC
    """
    rows = await _fetch_all(sql)
    return [ScheduleRow(**r) for r in rows]


# ─── Operations (source for OEE) ────────────────────────────────────────


async def list_operations(
    date_from: date,
    date_to: date,
    limit: int = 100_000,
) -> list[OperationRow]:
    """Operations executed within `[date_from, date_to]` window (filter by `end_at`).

    Heavy query — `OF_FP` has 2.6 M rows total. Always pass a tight window.
    Default limit 100 k covers ~3 months at NELO's current cadence.
    Replace inline subquery with `dbo.vw_pp1_operations` once views are
    deployed.
    """
    sql = f"""
    SELECT TOP {int(limit)} v.* FROM (
        {_VW_OPERATIONS_SQL}
    ) v
    WHERE v.end_at >= :date_from
      AND v.end_at <  :date_to_plus_one
      AND v.start_at IS NOT NULL
    ORDER BY v.end_at DESC
    """
    # NELO data has datetimes; pass full-day bounds to be inclusive.
    from datetime import datetime, timedelta
    params = {
        "date_from": datetime.combine(date_from, datetime.min.time()),
        "date_to_plus_one": datetime.combine(date_to + timedelta(days=1), datetime.min.time()),
    }
    rows = await _fetch_all(sql, params)
    return [OperationRow(**r) for r in rows]


async def list_checklist_incidents(
    date_from: date,
    date_to: date,
    limit: int = 200_000,
) -> list[ChecklistIncidentRow]:
    """Quality-checklist defects (`OF_CHECKLIST`) updated within the window.

    The canonical root-cause source — see `_VW_CHECKLIST_SQL`. Window on
    `OFCH_DATA_ACTUALIZACAO` (the table is 3 M rows; the 12-month window is
    ~99 k of which `OFCH_GRAVIDADE >= 1` is a subset).
    """
    sql = f"""
    SELECT TOP {int(limit)} v.* FROM (
        {_VW_CHECKLIST_SQL}
          AND ch.OFCH_DATA_ACTUALIZACAO >= :date_from
          AND ch.OFCH_DATA_ACTUALIZACAO <  :date_to_plus_one
    ) v
    ORDER BY v.detected_at DESC
    """
    from datetime import datetime, timedelta
    params = {
        "date_from": datetime.combine(date_from, datetime.min.time()),
        "date_to_plus_one": datetime.combine(date_to + timedelta(days=1), datetime.min.time()),
    }
    rows = await _fetch_all(sql, params)
    return [ChecklistIncidentRow(**r) for r in rows]


async def list_order_labor(work_order_id: int) -> list[OrderLaborRow]:
    """Phase executions × operators for one work order (`OF_FP`×`OFFP_EQ`).

    One row per (operation, operator) — the source for the per-order
    labour cost (Q.26.C.2). Bounded by a single `OFFP_OF_ID`, so the
    query is cheap despite `OF_FP` having 2.6 M rows.
    """
    rows = await _fetch_all(
        _VW_ORDER_LABOR_SQL, {"work_order_id": int(work_order_id)}
    )
    return [OrderLaborRow(**r) for r in rows]


# ─── Master data (for the ERP→Postgres ETL mirrors) ─────────────────────


async def list_phases() -> list[PhaseRow]:
    """All production phases (work centres) from `FASES_PRODUCAO` (~71 rows)."""
    sql = f"SELECT * FROM ({_VW_PHASES_SQL}) v ORDER BY v.sequence, v.phase_id"
    rows = await _fetch_all(sql)
    return [PhaseRow(**r) for r in rows]


async def list_products(limit: int = 50_000) -> list[ProductRow]:
    """Product catalogue (`PRODUTO`, ~14 k rows). Bounded by `limit`."""
    sql = f"""
    SELECT TOP {int(limit)}
        p.P_ID            AS product_id,
        p.P_NOME          AS product_name,
        p.P_NOME_EN       AS product_name_en,
        p.P_TP_ID         AS product_type_id,
        p.P_ACTIVO        AS active,
        p.P_DESCONTINUADO AS discontinued,
        p.P_FABRICOINTERNO AS in_house,
        p.P_PRECOCUSTO    AS cost_price
    FROM dbo.PRODUTO p WITH (NOLOCK)
    ORDER BY p.P_ID
    """
    rows = await _fetch_all(sql)
    return [ProductRow(**r) for r in rows]


async def list_product_stock(limit: int = 50_000) -> list[ProductStockRow]:
    """Live on-hand stock cache (`P_STOCK` / `P_STOCKMIN`) per product.

    Reads `dbo.PRODUTO` directly — the ERP keeps a per-product on-hand
    cache there, so a current snapshot does not need the 12M-row
    `MOVIMENTO` ledger.
    """
    sql = f"""
    SELECT TOP {int(limit)}
        p.P_ID       AS product_id,
        p.P_STOCK    AS stock,
        p.P_STOCKMIN AS stock_min
    FROM dbo.PRODUTO p WITH (NOLOCK)
    ORDER BY p.P_ID
    """
    rows = await _fetch_all(sql)
    return [ProductStockRow(**r) for r in rows]


async def list_stock_by_warehouse(limit: int = 200_000) -> list[WarehouseStockRow]:
    """Per-warehouse on-hand stock from the ERP view
    `dbo.produto_stocks_por_armazem` (~8 k rows).

    The granular truth the factory uses — stock split across the ~20
    warehouses. Used by the supply stock mirror.
    """
    sql = f"""
    SELECT TOP {int(limit)}
        v.P_ID       AS product_id,
        v.Armazem_Id AS warehouse_id,
        v.Armazem    AS warehouse_name,
        v.Stock      AS stock
    FROM dbo.produto_stocks_por_armazem v WITH (NOLOCK)
    ORDER BY v.P_ID, v.Armazem_Id
    """
    rows = await _fetch_all(sql)
    return [WarehouseStockRow(**r) for r in rows]


async def list_entities(internal_only: bool = False, limit: int = 20_000) -> list[EntityRow]:
    """Entities from `ENTIDADE`. `internal_only=True` restricts to the
    factory operators.

    `E_NELO=1` alone only flags ~52 records — not the operator set the
    skill matrix and operations reference. The canonical operators are
    the entities with a competence row in `ENTIDADE_FASE`; both sets are
    unioned so `core.employees` covers every operator the skills mirror
    needs (otherwise every employee_skill row is skipped)."""
    where = (
        "WHERE v.is_internal = 1 "
        "OR v.entity_id IN ("
        "SELECT DISTINCT EFP_E_ID FROM dbo.ENTIDADE_FASE "
        "WHERE EFP_E_ID IS NOT NULL)"
    ) if internal_only else ""
    sql = f"""
    SELECT TOP {int(limit)} * FROM (
        {_VW_ENTITIES_SQL}
    ) v
    {where}
    ORDER BY v.entity_id
    """
    rows = await _fetch_all(sql)
    return [EntityRow(**r) for r in rows]


async def list_entity_phases() -> list[EntityPhaseRow]:
    """Operator × phase competence matrix (`ENTIDADE_FASE`, ~1.3 k rows)."""
    sql = f"SELECT * FROM ({_VW_ENTITY_PHASES_SQL}) v ORDER BY v.entity_id, v.phase_id"
    rows = await _fetch_all(sql)
    return [EntityPhaseRow(**r) for r in rows]


async def list_variables() -> list[ErpVariableRow]:
    """ERP config variables (`dbo.VARIAVEIS`, ~poucas linhas). `VAR_VALOR` é
    `nvarchar` (texto) — ex.: VAR_ID=2 = '1.065' (factor de correcção das mãos
    de obra, Q.167.F). Read-only, NOLOCK."""
    sql = """
    SELECT
        v.VAR_ID        AS var_id,
        v.VAR_VALOR     AS var_value,
        v.VAR_DESCRICAO AS var_description
    FROM dbo.VARIAVEIS v WITH (NOLOCK)
    ORDER BY v.VAR_ID
    """
    rows = await _fetch_all(sql)
    return [ErpVariableRow(**r) for r in rows]


async def list_molds() -> list[MoldRow]:
    """ERP-side mold catalogue (`MOLDES`, ~91 rows). The full ~510 molds
    live in Excel; this is used for reconciliation + pocket enrichment."""
    sql = f"SELECT * FROM ({_VW_MOLDS_SQL}) v ORDER BY v.mold_id"
    rows = await _fetch_all(sql)
    return [MoldRow(**r) for r in rows]


async def list_all_routings(limit: int = 200_000) -> list[RoutingRow]:
    """Every product routing row (`PRODUTO_FASE` joined to `FASES_PRODUCAO`).

    Unlike :func:`get_routing` (one product) this returns the whole
    routing surface for the master-data mirror to group into templates.
    Heavy — `PRODUTO_FASE` has ~42 k rows; the `limit` is a safety cap.
    """
    sql = f"""
    SELECT TOP {int(limit)} * FROM (
        {_VW_ROUTINGS_SQL}
    ) v
    ORDER BY v.product_id, v.sequence
    """
    rows = await _fetch_all(sql)
    return [RoutingRow(**r) for r in rows]


async def list_all_bom(limit: int = 200_000) -> list[BomRow]:
    """Every active BOM line (`PRODUTO_COMPONENTE`). Heavy — ~117 k rows;
    `limit` is a safety cap. Used by the master-data mirror."""
    sql = f"""
    SELECT TOP {int(limit)} * FROM (
        {_VW_BOM_SQL}
    ) v
    ORDER BY v.parent_product_id, v.bom_id
    """
    rows = await _fetch_all(sql)
    return [BomRow(**r) for r in rows]


# ─── Aggregations for health-check ──────────────────────────────────────


async def top_products_by_orders(limit: int = 5) -> list[ProductOrderCount]:
    """Top N products ranked by total work order count."""
    sql = f"""
    SELECT TOP {int(limit)}
        of_.OF_P_ID         AS product_id,
        p.P_NOME            AS product_name,
        p.P_NOME_EN         AS product_name_en,
        COUNT_BIG(*)        AS order_count
    FROM        dbo.ORDEMFABRICO of_  WITH (NOLOCK)
    INNER JOIN  dbo.PRODUTO       p   WITH (NOLOCK) ON p.P_ID = of_.OF_P_ID
    WHERE of_.OF_DATA > '1900-01-02'
    GROUP BY of_.OF_P_ID, p.P_NOME, p.P_NOME_EN
    ORDER BY order_count DESC
    """
    rows = await _fetch_all(sql)
    return [ProductOrderCount(**r) for r in rows]


async def count_movements_last_n_days(days: int = 30) -> int:
    """Count stock movements within the last `days` (default 30)."""
    # SQL Server's `DATEADD(day, -N, ...)` doesn't accept a named parameter
    # for the interval component in some driver versions — interpolate as
    # int literal. Safe: explicit int() cast.
    sql = f"""
    SELECT COUNT_BIG(*)
    FROM dbo.MOVIMENTO WITH (NOLOCK)
    WHERE MOV_DATA >= DATEADD(day, -{int(days)}, CAST(GETDATE() AS date))
    """
    n = await _fetch_scalar(sql)
    return int(n or 0)


# ─── Phase history (Q.115.T) ────────────────────────────────────────────


async def list_phase_history(
    since: "date | None" = None,
    limit: int = 50_000,
) -> list[FasesOfHistoryRow]:
    """Historico de fases por OF de `dbo.FasesOf`.

    Q.115.T: fonte para `plan.fases_of_history`. Ordena por fase_inicio ASC
    para que o watermark incremental avance correctamente.

    ``since`` filtra por `FaseOf_DataInicio >= since` (janela incremental).
    ``limit`` e um cap de seguranca — full sync diario 3 anos passa um limit
    generoso (ou None para sem limite no full sync, mas usar com cuidado em
    tabela de 2.6M linhas).
    """
    top_clause = f"TOP {int(limit)}" if limit else ""
    since_clause = (
        "WHERE fo.FaseOf_DataInicio >= :since_dt"
        if since is not None
        else ""
    )
    params: dict[str, Any] = {}
    if since is not None:
        params["since_dt"] = since
    sql = f"""
    SELECT {top_clause}
        fo.OF_Id            AS of_id,
        fo.FaseOf_Id        AS phase_id,
        fo.FaseOf_DataInicio AS fase_inicio,
        fo.FaseOf_DataFim    AS fase_fim,
        fo.WorkerId          AS worker_id,
        fo.MoldeId           AS mold_id
    FROM dbo.FasesOf fo WITH (NOLOCK)
    {since_clause}
    ORDER BY fo.FaseOf_DataInicio ASC
    """
    rows = await _fetch_all(sql, params if params else None)
    return [FasesOfHistoryRow(**r) for r in rows]


async def list_worker_assignments(
    since: "date | None" = None,
    limit: int = 50_000,
) -> list[WorkerAssignmentRow]:
    """Atribuicoes de operadores a fases de `dbo.WorkerAssignment`.

    Q.115.T: fonte para `hr.worker_phase_assignment`.
    ``since`` filtra por `Atribuido_Em >= since`.
    """
    top_clause = f"TOP {int(limit)}" if limit else ""
    since_clause = (
        "WHERE wa.Atribuido_Em >= :since_dt"
        if since is not None
        else ""
    )
    params: dict[str, Any] = {}
    if since is not None:
        params["since_dt"] = since
    sql = f"""
    SELECT {top_clause}
        wa.WorkerId      AS worker_id,
        wa.OF_Id         AS of_id,
        wa.FaseOf_Id     AS phase_id,
        wa.Atribuido_Em  AS assigned_at,
        wa.Iniciado_Em   AS started_at,
        wa.Terminado_Em  AS ended_at,
        wa.Tipo          AS tipo
    FROM dbo.WorkerAssignment wa WITH (NOLOCK)
    {since_clause}
    ORDER BY wa.Atribuido_Em ASC
    """
    rows = await _fetch_all(sql, params if params else None)
    return [WorkerAssignmentRow(**r) for r in rows]


# ─── Health-check aggregate ─────────────────────────────────────────────


async def health_check() -> HealthCheckResult:
    """Run all status queries in parallel and assemble snapshot."""
    open_count, top, schedule, mov_count = await asyncio.gather(
        count_open_orders(),
        top_products_by_orders(limit=5),
        list_current_schedule(limit=10),
        count_movements_last_n_days(days=30),
    )
    return HealthCheckResult(
        open_orders_count=open_count,
        top_products=top,
        current_schedule=schedule,
        movements_last_30d=mov_count,
    )


__all__: Sequence[str] = (
    "close_engine",
    "count_movements_last_n_days",
    "count_open_orders",
    "get_bom",
    "get_engine",
    "get_routing",
    "health_check",
    "list_all_bom",
    "list_all_routings",
    "list_current_schedule",
    "list_entities",
    "list_entity_phases",
    "list_variables",
    "list_molds",
    "list_open_orders",
    "list_operations",
    "list_phases",
    "list_product_stock",
    "list_products",
    "list_phase_history",
    "list_recent_movements",
    "list_stock_by_warehouse",
    "list_worker_assignments",
    "top_products_by_orders",
)
