"""Q.20.B — master-data mirror tests.

Two surfaces, both runnable with neither Postgres nor SQL Server:

* the pure mappers (``_map_product`` / ``_map_worker`` / ``_map_bom``)
  and the routing-pattern grouping run with no DB at all;
* the end-to-end ``mirror_master_data`` runs against a recording fake
  session — the adapter is mocked with ``AsyncMock`` (the dev box has no
  SQL Server) and every ``EtlRunner.upsert`` call is captured so the test
  asserts the mirror mapped + routed the data correctly.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.adapters.nelo.etl import master_data
from src.adapters.nelo.etl.master_data import (
    _map_bom,
    _map_product,
    _map_worker,
    _routing_signature,
    group_routing_patterns,
    mirror_master_data,
)
from src.adapters.nelo.schemas import BomRow, EntityRow, ProductRow, RoutingRow
from src.core.models.bom import BOMItem
from src.core.models.employee import Employee, EmploymentStatus
from src.core.models.product import Product, ProductStatus, ProductType
from src.plan.models.routing_template import (
    ModelRoutingAssignment,
    RoutingTemplate,
    RoutingTemplatePhase,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ── pure mappers ──────────────────────────────────────────────────────────


def _product(**kw) -> ProductRow:
    base = dict(
        product_id=999, product_name="K1 Vanquish", product_name_en=None,
        product_type_id=1, active=True, discontinued=False, in_house=True,
        cost_price=1200.0,
    )
    base.update(kw)
    return ProductRow(**base)


def test_map_product_uses_erp_id_as_business_key():
    mapped = _map_product(_product(product_id=999, product_name="K1 Vanquish"))
    assert mapped["product_code"] == "999"               # ERP id = join key
    assert mapped["product_name"] == "K1 Vanquish"
    assert mapped["product_type"] == ProductType.FINISHED_GOOD
    assert mapped["status"] == ProductStatus.ACTIVE


def test_map_product_discontinued_status():
    mapped = _map_product(_product(active=True, discontinued=True))
    assert mapped["status"] == ProductStatus.DISCONTINUED


def test_map_product_inactive_status():
    mapped = _map_product(_product(active=False, discontinued=False))
    assert mapped["status"] == ProductStatus.INACTIVE


def _entity(**kw) -> EntityRow:
    base = dict(
        entity_id=42, name="João", active=True, is_internal=True,
        is_carrier=False, is_supervisor=False, cost_per_hour=9.5, level=2,
        productivity=1.0, entity_type_id=5, entity_type_name="Laminador",
        entry_date=None, country="PT", email=None,
    )
    base.update(kw)
    return EntityRow(**base)


def test_map_worker_falls_back_when_entry_date_missing():
    mapped = _map_worker(_entity(entity_id=42, name="João", entry_date=None))
    assert mapped["employee_code"] == "42"
    assert mapped["hire_date"] == date(1900, 1, 1)       # explicit sentinel
    assert mapped["status"] == EmploymentStatus.ACTIVE


def test_map_worker_uses_entry_date_when_present():
    mapped = _map_worker(_entity(entry_date=datetime(2018, 3, 1, 9, 0)))
    assert mapped["hire_date"] == date(2018, 3, 1)


def test_map_worker_inactive_status():
    mapped = _map_worker(_entity(entity_id=7, active=False))
    assert mapped["status"] == EmploymentStatus.TERMINATED


# ── BOM mapping ───────────────────────────────────────────────────────────


def _bom(**kw) -> BomRow:
    base = dict(
        bom_id=1, parent_product_id=10, parent_product_name="K1",
        parent_product_name_en=None, component_product_id=20,
        component_product_name="Casca", component_product_name_en=None,
        component_unit_id=1, component_stock=0.0, component_stock_min=0.0,
        component_cost_price=5.0, quantity=2.0, component_type_id=2,
        consumption_phase_id=None, is_final_phase=False, configurable=False,
        is_unique=False, list_id=None, observations=None, changed_at=None,
    )
    base.update(kw)
    return BomRow(**base)


def test_map_bom_uses_comp_id_as_sequence():
    """PRODUTO_COMPONENTE has no sequence column — the COMP_ID (bom_id)
    is used so the (parent, component, seq) key is unique."""
    parent_uuid, comp_uuid = uuid4(), uuid4()
    by_code = {"10": parent_uuid, "20": comp_uuid}
    mapped, skipped = _map_bom([_bom(bom_id=777, quantity=3)], by_code)
    assert skipped == 0
    assert mapped[0]["sequence"] == 777
    assert mapped[0]["parent_product_id"] == parent_uuid
    assert mapped[0]["component_product_id"] == comp_uuid
    assert mapped[0]["quantity_per"] == Decimal("3")


def test_map_bom_skips_row_with_unknown_product():
    """A BOM line whose parent/component the mirror never saw is skipped,
    not crashed (QA01 spirit)."""
    by_code = {"10": uuid4()}  # component 20 is missing
    mapped, skipped = _map_bom([_bom(parent_product_id=10, component_product_id=20)], by_code)
    assert mapped == []
    assert skipped == 1


# ── routing pattern grouping ──────────────────────────────────────────────


def _routing(product_id: int, phase_id: int, seq: int, phase_name: str = "F") -> RoutingRow:
    return RoutingRow(
        routing_id=product_id * 100 + seq, product_id=product_id,
        phase_id=phase_id, phase_name=phase_name, phase_description=None,
        routing_description=None, sequence=seq, time_hours=0.0,
        phase_hour_coefficient=1.0, k1_reference_hours=0.0,
        k2_reference_hours=0.0, k4_reference_hours=0.0,
        phase_is_production=True, phase_is_automatic=False,
        phase_can_repeat=False, routing_in_production=True,
        routing_coefficient=0.0, routing_coefficient_x=0.0,
        layer_type_id=None, created_at=datetime(2020, 1, 1), updated_at=None,
    )


def test_routing_signature_is_order_sensitive():
    assert _routing_signature(["A", "B"]) != _routing_signature(["B", "A"])
    assert _routing_signature(["A", "B"]) == _routing_signature(["A", "B"])


def test_group_routing_patterns_collapses_identical_routes():
    """Two products with the SAME ordered phase list share one pattern;
    a third with a different list gets its own."""
    rows = [
        _routing(1, 10, 1), _routing(1, 11, 2),
        _routing(2, 10, 1), _routing(2, 11, 2),
        _routing(3, 11, 1),
    ]
    patterns = group_routing_patterns(rows)
    assert len(patterns) == 2
    shared = [p for p in patterns.values() if len(p[1]) == 2][0]
    assert sorted(shared[1]) == ["1", "2"]


def test_group_routing_patterns_sorts_by_sequence():
    """Phases supplied out of order are sorted before signing."""
    rows = [_routing(1, 11, 2, "B"), _routing(1, 10, 1, "A")]
    patterns = group_routing_patterns(rows)
    (phases, _), = patterns.values()
    assert [f for _, f, _ in phases] == ["10", "11"]


def test_group_routing_patterns_drops_rows_without_phase():
    """PRODUTO_FASE allows NULL phase (free-text instruction lines) —
    those rows must not poison the pattern signature."""
    rows = [
        _routing(1, 10, 1),
        RoutingRow(
            routing_id=2, product_id=1, phase_id=None, phase_name="instrução",
            phase_description=None, routing_description=None, sequence=2,
            time_hours=0.0, phase_hour_coefficient=1.0, k1_reference_hours=0.0,
            k2_reference_hours=0.0, k4_reference_hours=0.0,
            phase_is_production=True, phase_is_automatic=False,
            phase_can_repeat=False, routing_in_production=True,
            routing_coefficient=0.0, routing_coefficient_x=0.0,
            layer_type_id=None, created_at=datetime(2020, 1, 1), updated_at=None,
        ),
    ]
    patterns = group_routing_patterns(rows)
    (phases, _), = patterns.values()
    assert [f for _, f, _ in phases] == ["10"]


# ── end-to-end mirror (recording fake session — no DB) ────────────────────


class _Result:
    """Mimics a SQLAlchemy Result over a fixed list of objects/rows."""

    def __init__(self, items) -> None:
        self._items = list(items)

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self._items)


class _RecordingSession:
    """A fake AsyncSession that records ``add``-ed objects and serves
    ``execute`` from them — modelling a Postgres where rows written
    earlier in the transaction are visible to later reads in the same
    mirror (which is exactly how the real session behaves).

    ``flush`` assigns UUIDs to id-less objects so ``_mirror_routing`` can
    read ``template.id``. Supports both ``select(Entity)`` (returns the
    objects) and ``select(Entity.col_a, Entity.col_b)`` (returns tuples).
    """

    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    async def execute(self, statement, *_a, **_kw) -> _Result:
        descs = list(getattr(statement, "column_descriptions", []) or [])
        if not descs:
            return _Result([])
        # The model class is the `entity` of the first column description.
        model = descs[0].get("entity")
        matches = [o for o in self.added if model is not None and isinstance(o, model)]
        if len(descs) == 1 and descs[0].get("expr") is model:
            # select(Model) → yield the ORM objects themselves.
            return _Result(matches)
        # select(Model.col_a, Model.col_b, ...) → yield value tuples.
        attrs = [d["name"] for d in descs]
        return _Result([tuple(getattr(o, a) for a in attrs) for o in matches])


@pytest.fixture
def _fake_adapter(monkeypatch):
    """Mock the read-only NELO adapter — the dev box has no SQL Server."""
    monkeypatch.setattr(
        master_data.services, "list_products",
        AsyncMock(return_value=[
            _product(product_id=1, product_name="K1 Vanquish"),
            _product(product_id=2, product_name="K2 Quantium"),
        ]),
    )
    monkeypatch.setattr(
        master_data.services, "list_entities",
        AsyncMock(return_value=[
            _entity(entity_id=101, name="Op Um"),
            _entity(entity_id=102, name="Op Dois"),
        ]),
    )
    monkeypatch.setattr(
        master_data.services, "list_all_bom",
        AsyncMock(return_value=[
            _bom(bom_id=1, parent_product_id=1, component_product_id=2),
        ]),
    )
    monkeypatch.setattr(
        master_data.services, "list_all_routings",
        AsyncMock(return_value=[
            _routing(1, 10, 1, "Laminagem"), _routing(1, 11, 2, "Acabamento"),
            _routing(2, 10, 1, "Laminagem"), _routing(2, 11, 2, "Acabamento"),
        ]),
    )


async def test_mirror_master_data_runs_and_audits(_fake_adapter):
    """Full mirror against the recording session: status ok, audit row
    written, products/employees inserted, routing collapsed to 1 pattern."""
    session = _RecordingSession()
    result = await mirror_master_data(session=session, tenant_id=TENANT, since=None)

    assert result.status == "ok"
    # 2 products + 2 entities + 1 bom + 4 routing rows read.
    assert result.rows_read == 9

    products = [o for o in session.added if isinstance(o, Product)]
    employees = [o for o in session.added if isinstance(o, Employee)]
    boms = [o for o in session.added if isinstance(o, BOMItem)]
    templates = [o for o in session.added if isinstance(o, RoutingTemplate)]
    assignments = [o for o in session.added if isinstance(o, ModelRoutingAssignment)]

    assert {p.product_code for p in products} == {"1", "2"}
    assert {e.employee_code for e in employees} == {"101", "102"}
    assert len(boms) == 1 and boms[0].sequence == 1
    # M1 and M2 share the route → exactly one ERP template, coverage 2.
    assert len(templates) == 1
    assert templates[0].model_coverage == 2
    assert {a.model_id for a in assignments} == {"1", "2"}


async def test_mirror_master_data_leaves_durations_untouched(_fake_adapter):
    """Q.20.F owns p50/p90 — the master mirror must never set them."""
    session = _RecordingSession()
    await mirror_master_data(session=session, tenant_id=TENANT, since=None)

    phases = [o for o in session.added if isinstance(o, RoutingTemplatePhase)]
    assert len(phases) == 2
    assert all(p.duration_p50_h is None for p in phases)
    assert all(p.duration_p90_h is None for p in phases)
