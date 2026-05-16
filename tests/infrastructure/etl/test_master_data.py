"""Q.20.B — master-data mirror tests.

Pure mappers / routing-pattern grouping run with no DB. The end-to-end
mirror runs against a live Postgres (marked ``integration``) inside a
transaction that is rolled back, so it leaves no rows behind.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.core.models.employee import EmploymentStatus
from src.core.models.product import ProductStatus, ProductType
from src.infrastructure.erp.etl.master_data import (
    _classify_product_type,
    _map_product,
    _map_worker,
    _routing_signature,
    group_routing_patterns,
    mirror_master_data,
)


# ── pure mappers ──────────────────────────────────────────────────────────


def test_map_product_uses_erp_id_as_business_key():
    row = {
        "product_id": "999", "product_code": "K1-VANQUISH",
        "product_name": "K1 Vanquish", "product_type_raw": "KAYAK", "active": 1,
    }
    mapped = _map_product(row)
    assert mapped["product_code"] == "999"               # ERP id = join key
    assert mapped["customer_product_code"] == "K1-VANQUISH"
    assert mapped["product_type"] == ProductType.FINISHED_GOOD
    assert mapped["status"] == ProductStatus.ACTIVE


def test_map_product_skips_row_without_id():
    assert _map_product({"product_id": None, "product_name": "x"}) is None


def test_classify_product_type_semi_finished():
    assert _classify_product_type("COMPONENTE") == ProductType.SEMI_FINISHED
    assert _classify_product_type("Sub-assembly") == ProductType.SEMI_FINISHED
    assert _classify_product_type("KAYAK K1") == ProductType.FINISHED_GOOD
    assert _classify_product_type(None) == ProductType.FINISHED_GOOD


def test_map_worker_falls_back_when_hire_date_missing():
    mapped = _map_worker({"entidade_id": "42", "nome": "João", "activo": 1})
    assert mapped["employee_code"] == "42"
    assert mapped["hire_date"] == date(1900, 1, 1)       # explicit sentinel
    assert mapped["status"] == EmploymentStatus.ACTIVE


def test_map_worker_inactive_status():
    mapped = _map_worker({"entidade_id": "7", "nome": "X", "activo": 0})
    assert mapped["status"] == EmploymentStatus.TERMINATED


# ── routing pattern grouping ──────────────────────────────────────────────


def test_routing_signature_is_order_sensitive():
    assert _routing_signature(["A", "B"]) != _routing_signature(["B", "A"])
    assert _routing_signature(["A", "B"]) == _routing_signature(["A", "B"])


def test_group_routing_patterns_collapses_identical_routes():
    """Two products with the SAME ordered phase list share one pattern;
    a third with a different list gets its own."""
    pf_rows = [
        {"product_id": "P1", "fase_id": "LAM", "sequencia": 1, "requires_mold": 1},
        {"product_id": "P1", "fase_id": "ACAB", "sequencia": 2, "requires_mold": 0},
        {"product_id": "P2", "fase_id": "LAM", "sequencia": 1, "requires_mold": 1},
        {"product_id": "P2", "fase_id": "ACAB", "sequencia": 2, "requires_mold": 0},
        {"product_id": "P3", "fase_id": "ACAB", "sequencia": 1, "requires_mold": 0},
    ]
    patterns = group_routing_patterns(pf_rows)
    assert len(patterns) == 2
    # The shared pattern carries both P1 and P2.
    shared = [p for p in patterns.values() if len(p[1]) == 2][0]
    assert sorted(shared[1]) == ["P1", "P2"]


def test_group_routing_patterns_sorts_by_sequence():
    """Phases supplied out of order are sorted before signing."""
    pf_rows = [
        {"product_id": "P1", "fase_id": "B", "sequencia": 2},
        {"product_id": "P1", "fase_id": "A", "sequencia": 1},
    ]
    patterns = group_routing_patterns(pf_rows)
    (phases, _), = patterns.values()
    assert [f for _, f, _ in phases] == ["A", "B"]


# ── integration: full mirror against a live Postgres ──────────────────────


class _FakeAdapter:
    """Canned ``vw_pp1_*`` rows for the master-data mirror."""

    async def fetch_products(self, **_kw):
        return [
            {"product_id": "M1", "product_code": "K1V", "product_name": "K1 Vanquish",
             "product_type_raw": "KAYAK", "active": 1},
            {"product_id": "M2", "product_code": "K2Q", "product_name": "K2 Quantium",
             "product_type_raw": "KAYAK", "active": 1},
        ]

    async def fetch_workers(self, **_kw):
        return [
            {"entidade_id": "E1", "nome": "Op Um", "activo": 1, "data_admissao": None},
            {"entidade_id": "E2", "nome": "Op Dois", "activo": 1, "data_admissao": None},
        ]

    async def fetch_components(self, **_kw):
        return [
            {"produto_id": "M1", "componente_id": "M2", "quantidade": 2,
             "unidade": "UN", "sequencia": 1},
            # references an unknown product → must be skipped, not crash
            {"produto_id": "M1", "componente_id": "GHOST", "quantidade": 1,
             "unidade": "UN", "sequencia": 2},
        ]

    async def fetch_product_phases(self, **_kw):
        return [
            {"product_id": "M1", "fase_id": "LAM", "sequencia": 1, "requires_mold": 1},
            {"product_id": "M1", "fase_id": "ACAB", "sequencia": 2, "requires_mold": 0},
            {"product_id": "M2", "fase_id": "LAM", "sequencia": 1, "requires_mold": 1},
            {"product_id": "M2", "fase_id": "ACAB", "sequencia": 2, "requires_mold": 0},
        ]

    async def fetch_phases(self, **_kw):
        return [
            {"fase_id": "LAM", "fase_nome": "Laminagem"},
            {"fase_id": "ACAB", "fase_nome": "Acabamento"},
        ]


@pytest.mark.integration
async def test_mirror_master_data_end_to_end():
    """Run the full mirror, assert it wrote core.*/plan.* rows, then roll
    back so the dev DB is left untouched."""
    from uuid import UUID

    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from src.core.models.product import Product
    from src.core.models.employee import Employee
    from src.plan.models.routing_template import RoutingTemplate, RoutingTemplatePhase
    from src.shared.config import settings

    tenant = UUID("00000000-0000-0000-0000-000000000001")
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            result = await mirror_master_data(
                session=session, tenant_id=tenant,
                adapter=_FakeAdapter(), since=None,
            )
            assert result.status == "ok"
            # 2 products + 2 employees + 4 phase rows read; bom reads 2.
            assert result.rows_inserted >= 6
            assert result.rows_skipped == 1   # the GHOST component

            products = await session.scalar(
                select(func.count()).select_from(Product).where(
                    Product.tenant_id == tenant, Product.product_code.in_(["M1", "M2"])
                )
            )
            assert products == 2

            employees = await session.scalar(
                select(func.count()).select_from(Employee).where(
                    Employee.tenant_id == tenant,
                    Employee.employee_code.in_(["E1", "E2"]),
                )
            )
            assert employees == 2

            # M1 and M2 share the same route → exactly one ERP template.
            templates = (await session.execute(
                select(RoutingTemplate).where(
                    RoutingTemplate.tenant_id == tenant,
                    RoutingTemplate.code.like("ERP-%"),
                )
            )).scalars().all()
            assert len(templates) == 1
            assert templates[0].model_coverage == 2

            # Q.20.F owns durations — the mirror must leave them NULL.
            phases = (await session.execute(
                select(RoutingTemplatePhase).where(
                    RoutingTemplatePhase.template_id == templates[0].id
                )
            )).scalars().all()
            assert len(phases) == 2
            assert all(p.duration_p50_h is None for p in phases)
            assert all(p.duration_p90_h is None for p in phases)

            await session.rollback()
    finally:
        await engine.dispose()
