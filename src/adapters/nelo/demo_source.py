"""Q.24.A — demo-package source for the ERP→Postgres ETL.

The Q.20 ETL mirrors read from :mod:`src.adapters.nelo.services`, which
talks to the live SQL Server. This module exposes the **same async
interface** but reads from ``agent_docs/demo_orders.json`` — the 50 real
closed work orders the research extracted from MAR-KAYAKS. It lets the
whole ETL + scheduler pipeline run on the real *shape* of factory data
today, with zero dependency on IT Nelo credentials.

``run_nelo_sync(source="demo")`` swaps this module in for ``services``.

Coverage
--------
The demo package bundles, per order: ``order`` / ``routing`` / ``bom`` /
``movements``. Products and phases are **derived** from the nested
routing/bom rows. Operators, the skill matrix and the ERP mold catalogue
are NOT in the package — those services return ``[]`` and keep coming
from the curated Excel path (``factory_data_product``). Operations
(``OF_FP``) are also absent until Q.24.D extends the builder, so
``list_operations`` returns ``[]``.

Schema gaps
-----------
``scripts/validate_demo_package.py`` confirmed the builder trimmed a few
``vw_pp1_*`` columns. The mappers below fill them with documented
defaults so the Pydantic contract in :mod:`src.adapters.nelo.schemas`
still constructs cleanly:

* routing — ``phase_can_repeat=False``, ``created_at`` from the order's
  ``ordered_at``;
* bom — ``configurable=False``, ``is_unique=False``.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from .schemas import (
    BomRow,
    EntityPhaseRow,
    EntityRow,
    HealthCheckResult,
    MoldRow,
    OperationRow,
    OrderRow,
    PhaseRow,
    ProductRow,
    RoutingRow,
)

logger = logging.getLogger(__name__)

_DEFAULT_PACKAGE = (
    Path(__file__).resolve().parents[3] / "agent_docs" / "demo_orders.json"
)
# Fallback timestamp for routing rows the builder trimmed `created_at`
# from and whose order carries no `ordered_at` — the factory's planning
# era. Never used for scheduling time, only to satisfy NOT NULL.
_EPOCH = datetime(2019, 1, 1)


def _package_path() -> Path:
    """Resolve the demo package path — overridable via env for tests."""
    override = os.environ.get("DEMO_PACKAGE_PATH")
    return Path(override) if override else _DEFAULT_PACKAGE


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    """Parse the demo package once per process."""
    path = _package_path()
    if not path.exists():
        raise FileNotFoundError(
            f"demo package not found: {path}. Run scripts/build_demo_package.py "
            f"or set DEMO_PACKAGE_PATH."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _orders() -> List[Dict[str, Any]]:
    return list(_load().get("orders", []))


# ─── lifecycle (mirrors the services.py contract) ───────────────────────


async def health_check() -> HealthCheckResult:
    """Trivial OK snapshot — the demo package is a static file, always
    'reachable'. Shaped like the ERP health-check so the orchestrator
    stays source-agnostic."""
    return HealthCheckResult(
        open_orders_count=len(_orders()),
        top_products=[],
        current_schedule=[],
        movements_last_30d=0,
    )


async def close_engine() -> None:
    """No-op — the demo source holds no DB engine."""
    return None


# ─── orders ─────────────────────────────────────────────────────────────


async def list_open_orders(limit: int = 100) -> List[OrderRow]:
    """The 50 work orders in the package. They are genuinely *closed*
    OFs (the builder filters `OF_DATAFIM IS NOT NULL`); the orders mirror
    re-plans them, so they are exposed here regardless of status."""
    rows = [OrderRow.model_validate(o["order"]) for o in _orders()]
    return rows[: int(limit)] if limit else rows


# ─── routing ────────────────────────────────────────────────────────────


def _routing_row(raw: Dict[str, Any], created_at: Any) -> RoutingRow:
    """Demo routing dict → RoutingRow, filling the trimmed columns."""
    return RoutingRow.model_validate(
        {
            "phase_can_repeat": False,
            "created_at": created_at,
            **raw,
        }
    )


async def list_all_routings(limit: int = 200_000) -> List[RoutingRow]:
    """Every routing row across the 50 orders, ready for the master
    mirror to group into templates."""
    out: List[RoutingRow] = []
    for order in _orders():
        created = order.get("order", {}).get("ordered_at") or _EPOCH
        for raw in order.get("routing", []):
            out.append(_routing_row(raw, created))
    return out[: int(limit)] if limit else out


# ─── BOM ────────────────────────────────────────────────────────────────


def _bom_row(raw: Dict[str, Any]) -> BomRow:
    """Demo bom dict → BomRow, filling the trimmed columns."""
    return BomRow.model_validate(
        {"configurable": False, "is_unique": False, **raw}
    )


async def list_all_bom(limit: int = 200_000) -> List[BomRow]:
    """Every active BOM line across the 50 orders."""
    out: List[BomRow] = []
    for order in _orders():
        for raw in order.get("bom", []):
            out.append(_bom_row(raw))
    return out[: int(limit)] if limit else out


# ─── products (derived) ─────────────────────────────────────────────────


async def list_products(limit: int = 50_000) -> List[ProductRow]:
    """Product catalogue derived from the package — every product the
    routing and BOM reference, so the master mirror resolves all FKs.

    Boat products come from the `order` block; component products come
    from the BOM `component_*` columns. Keyed by `product_id` so a
    product seen on both sides collapses to one row.
    """
    by_id: Dict[int, Dict[str, Any]] = {}
    for order in _orders():
        o = order.get("order", {})
        pid = o.get("product_id")
        if pid is not None:
            by_id[pid] = {
                "product_id": pid,
                "product_name": o.get("product_name") or str(pid),
                "product_name_en": o.get("product_name_en"),
                "product_type_id": o.get("product_type_id"),
                "active": True,
                "discontinued": False,
                "in_house": True,
                "cost_price": float(o.get("cost_price") or 0.0),
            }
        for b in order.get("bom", []):
            cid = b.get("component_product_id")
            if cid is None or cid in by_id:
                continue
            by_id[cid] = {
                "product_id": cid,
                "product_name": b.get("component_product_name") or str(cid),
                "product_name_en": b.get("component_product_name_en"),
                "product_type_id": b.get("component_type_id"),
                "active": True,
                "discontinued": False,
                "in_house": False,
                "cost_price": float(b.get("component_cost_price") or 0.0),
            }
    rows = [ProductRow.model_validate(v) for v in by_id.values()]
    return rows[: int(limit)] if limit else rows


# ─── phases (derived from routing) ──────────────────────────────────────


async def list_phases() -> List[PhaseRow]:
    """Production phases derived from the routing rows — one PhaseRow per
    distinct `phase_id` the package references."""
    by_id: Dict[int, Dict[str, Any]] = {}
    for order in _orders():
        for r in order.get("routing", []):
            pid = r.get("phase_id")
            if pid is None or pid in by_id:
                continue
            by_id[pid] = {
                "phase_id": pid,
                "phase_name": r.get("phase_name") or str(pid),
                "sequence": int(r.get("sequence") or 0),
                "is_production": bool(r.get("phase_is_production")),
                "is_automatic": bool(r.get("phase_is_automatic")),
                "can_repeat": False,
                "hour_coefficient": float(r.get("phase_hour_coefficient") or 0.0),
                "k1_reference_hours": float(r.get("k1_reference_hours") or 0.0),
                "k2_reference_hours": float(r.get("k2_reference_hours") or 0.0),
                "k4_reference_hours": float(r.get("k4_reference_hours") or 0.0),
            }
    return [PhaseRow.model_validate(v) for v in by_id.values()]


# ─── absent in the package ──────────────────────────────────────────────


async def list_entities(internal_only: bool = False, limit: int = 20_000) -> List[EntityRow]:
    """The demo package has no operator data — operators stay on the
    curated Excel path. Returns an empty list (a no-op upsert)."""
    return []


async def list_entity_phases() -> List[EntityPhaseRow]:
    """No skill matrix in the package — returns empty."""
    return []


async def list_molds() -> List[MoldRow]:
    """No ERP mold catalogue in the package — returns empty."""
    return []


async def list_operations(date_from: Any = None, date_to: Any = None, limit: int = 100_000) -> List[OperationRow]:
    """Operation history (`OF_FP`) bundled per order by the Q.24.D
    builder extension. Feeds the quality + time_mining mirrors.

    Filters by ``end_at`` in ``[date_from, date_to]`` when a window is
    given. A package built before the Q.24.D builder extension has no
    ``operations`` key — this then returns ``[]`` and the dependent
    mirrors run as clean no-ops.

    ``product_id`` is not on `OF_FP`; it is injected from the parent
    order. ``standard_time_hours`` is not consulted by the mirrors
    (time_mining uses the real start/end span) so it defaults to 0.
    """
    lo, hi = _window_bounds(date_from, date_to)
    out: List[OperationRow] = []
    for order in _orders():
        product_id = order.get("order", {}).get("product_id")
        for raw in order.get("operations", []):
            end_at = _as_datetime(raw.get("end_at"))
            if end_at is not None:
                if lo is not None and end_at < lo:
                    continue
                if hi is not None and end_at >= hi:
                    continue
            out.append(_operation_row(raw, product_id))
    return out[: int(limit)] if limit else out


def _window_bounds(date_from: Any, date_to: Any) -> "tuple[datetime | None, datetime | None]":
    """Coerce a (date_from, date_to) filter to half-open datetime bounds
    ``[lo, hi)``. A plain ``date`` upper bound is inclusive of its whole
    day — matching ``services.list_operations`` (which adds one day) so
    the demo + ERP sources filter identically."""
    from datetime import date as _date_cls
    from datetime import timedelta

    lo = _as_datetime(date_from)
    hi = _as_datetime(date_to)
    if (
        hi is not None
        and isinstance(date_to, _date_cls)
        and not isinstance(date_to, datetime)
    ):
        hi = hi + timedelta(days=1)
    return lo, hi


def _as_datetime(value: Any) -> "datetime | None":
    """Coerce an ISO string / date / datetime / None to a datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    # a plain date
    try:
        return datetime(value.year, value.month, value.day)
    except AttributeError:
        return None


def _operation_row(raw: Dict[str, Any], product_id: Any) -> OperationRow:
    """Demo operation dict → OperationRow, injecting `product_id` from
    the parent order and defaulting the columns `OF_FP` lacks."""
    return OperationRow.model_validate(
        {
            "standard_time_hours": 0.0,
            **raw,
            "product_id": raw.get("product_id") or product_id,
            "temperature": raw.get("temperature") or 0.0,
            "humidity": raw.get("humidity") or 0.0,
            "is_return": bool(raw.get("is_return")),
            "severe_return": bool(raw.get("severe_return")),
        }
    )

