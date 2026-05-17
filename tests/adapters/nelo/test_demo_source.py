"""Q.24.A — tests for the demo-package ETL source.

The demo source reads the real `agent_docs/demo_orders.json` (50 closed
MAR-KAYAKS work orders) and exposes the same async interface as the live
ERP adapter. These tests run against that real package — it is in the
repo, deterministic, and is exactly what Q.24.A ingests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.adapters.nelo import demo_source
from src.adapters.nelo.schemas import BomRow, OrderRow, ProductRow, RoutingRow


@pytest.fixture(autouse=True)
def _clean_cache(monkeypatch):
    """Each test parses the package fresh — the loader is lru_cached."""
    demo_source._load.cache_clear()
    monkeypatch.delenv("DEMO_PACKAGE_PATH", raising=False)
    yield
    demo_source._load.cache_clear()


async def test_list_open_orders_returns_the_fifty_real_ofs():
    orders = await demo_source.list_open_orders(limit=1000)
    assert len(orders) == 50
    assert all(isinstance(o, OrderRow) for o in orders)
    assert all(o.work_order_id > 0 for o in orders)


async def test_list_open_orders_honours_limit():
    assert len(await demo_source.list_open_orders(limit=5)) == 5


async def test_routings_fill_the_trimmed_columns():
    """The builder trimmed `created_at` + `phase_can_repeat`; the demo
    source fills them so RoutingRow constructs."""
    routings = await demo_source.list_all_routings()
    assert len(routings) > 700
    assert all(isinstance(r, RoutingRow) for r in routings)
    assert all(r.created_at is not None for r in routings)
    assert all(r.phase_can_repeat is False for r in routings)


async def test_bom_fills_the_trimmed_columns():
    bom = await demo_source.list_all_bom()
    assert len(bom) > 1000
    assert all(isinstance(b, BomRow) for b in bom)
    assert all(b.configurable is False and b.is_unique is False for b in bom)


async def test_products_cover_every_referenced_id():
    """Every product the routing and BOM join on must exist in the
    derived catalogue, or the master mirror skips those rows."""
    products = await demo_source.list_products()
    assert all(isinstance(p, ProductRow) for p in products)
    pids = {p.product_id for p in products}

    routings = await demo_source.list_all_routings()
    bom = await demo_source.list_all_bom()
    for r in routings:
        assert r.product_id in pids
    for b in bom:
        assert b.component_product_id in pids
        assert b.parent_product_id in pids


async def test_phases_are_derived_from_routing():
    phases = await demo_source.list_phases()
    assert phases
    routing_phase_ids = {
        r.phase_id for r in await demo_source.list_all_routings()
    }
    assert {p.phase_id for p in phases} == routing_phase_ids


async def test_absent_sections_return_empty():
    """Operators, skills and molds are not in the package."""
    assert await demo_source.list_entities(internal_only=True) == []
    assert await demo_source.list_entity_phases() == []
    assert await demo_source.list_molds() == []


async def test_operations_empty_when_package_predates_q24d_builder():
    """The shipped demo_orders.json has no `operations` key yet — until
    the Q.24.D builder extension is re-run, list_operations is empty."""
    assert await demo_source.list_operations(date_from=None, date_to=None) == []


async def test_health_check_reports_the_package_size():
    snap = await demo_source.health_check()
    assert snap.open_orders_count == 50


async def test_missing_package_raises_explicitly(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_PACKAGE_PATH", str(tmp_path / "nope.json"))
    demo_source._load.cache_clear()
    with pytest.raises(FileNotFoundError, match="demo package not found"):
        await demo_source.list_open_orders()


async def test_package_path_override(monkeypatch, tmp_path):
    """A synthetic one-order package loads via DEMO_PACKAGE_PATH."""
    pkg = {
        "generated_at": "2026-01-01T00:00:00",
        "source": "test",
        "order_count": 1,
        "orders": [
            {
                "order": {
                    "work_order_id": 9001,
                    "cost_price": 100.0,
                    "sale_price": 200.0,
                    "discount": 0.0,
                    "paid_amount": 200.0,
                    "coefficient_eur": 0.0,
                    "is_paid": True,
                    "supervised": False,
                    "sequence": 1,
                    "product_id": 7,
                    "product_name": "K1 Test",
                    "current_phase_id": 3,
                    "warehouse_id": 1,
                },
                "routing": [],
                "bom": [],
                "movements": [],
            }
        ],
    }
    path = tmp_path / "demo.json"
    path.write_text(json.dumps(pkg), encoding="utf-8")
    monkeypatch.setenv("DEMO_PACKAGE_PATH", str(path))
    demo_source._load.cache_clear()

    orders = await demo_source.list_open_orders()
    assert len(orders) == 1
    assert orders[0].work_order_id == 9001


def _pkg_with_operations(ops: list[dict]) -> dict:
    """A one-order synthetic package carrying an `operations` block —
    models a demo package built by the Q.24.D builder extension."""
    return {
        "generated_at": "2026-01-01T00:00:00",
        "source": "test",
        "order_count": 1,
        "orders": [
            {
                "order": {
                    "work_order_id": 9001,
                    "cost_price": 100.0,
                    "sale_price": 200.0,
                    "discount": 0.0,
                    "paid_amount": 200.0,
                    "coefficient_eur": 0.0,
                    "is_paid": True,
                    "supervised": False,
                    "sequence": 1,
                    "product_id": 42,
                    "current_phase_id": 3,
                    "warehouse_id": 1,
                },
                "routing": [],
                "bom": [],
                "movements": [],
                "operations": ops,
            }
        ],
    }


def _op(operation_id: int, phase_id: int, end_at: str) -> dict:
    return {
        "operation_id": operation_id,
        "work_order_id": 9001,
        "phase_id": phase_id,
        "phase_name": f"Fase {phase_id}",
        "start_at": "2026-03-01T08:00:00",
        "end_at": end_at,
    }


async def test_operations_loaded_and_product_id_injected(monkeypatch, tmp_path):
    """Q.24.D — operations bundled by the builder load, with product_id
    injected from the parent order (OF_FP has no product column)."""
    path = tmp_path / "demo.json"
    path.write_text(
        json.dumps(_pkg_with_operations([_op(1, 3, "2026-03-01T12:00:00")])),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEMO_PACKAGE_PATH", str(path))
    demo_source._load.cache_clear()

    ops = await demo_source.list_operations(date_from=None, date_to=None)
    assert len(ops) == 1
    assert ops[0].operation_id == 1
    assert ops[0].product_id == 42  # injected from the order
    assert ops[0].end_at is not None


async def test_operations_filtered_by_end_at_window(monkeypatch, tmp_path):
    from datetime import date

    path = tmp_path / "demo.json"
    path.write_text(
        json.dumps(
            _pkg_with_operations(
                [
                    _op(1, 3, "2026-01-15T12:00:00"),
                    _op(2, 4, "2026-03-15T12:00:00"),
                    _op(3, 5, "2026-06-15T12:00:00"),
                ]
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEMO_PACKAGE_PATH", str(path))
    demo_source._load.cache_clear()

    ops = await demo_source.list_operations(
        date_from=date(2026, 3, 1), date_to=date(2026, 4, 1)
    )
    assert [o.operation_id for o in ops] == [2]

