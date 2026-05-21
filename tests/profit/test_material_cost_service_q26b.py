"""Q.26.B — testes do MaterialCostService.

Duas superficies:
* o nucleo puro (`MaterialCostLine`, `MaterialCostResult.from_lines`) —
  aritmetica de custo, sem BD;
* o servico (`MaterialCostService.material_cost`) contra uma sessao falsa
  que devolve linhas de BOM canned.
"""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.profit.services.material_cost_service import (
    MaterialCostLine,
    MaterialCostResult,
    MaterialCostService,
)
from tests.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ── sessao falsa ──────────────────────────────────────────────────────────


def _session_with_rows(rows) -> FakeSession:
    """Q.68.3.3 — Canonical FakeSession with BOM rows queued for ``execute().all()``."""
    session = FakeSession()
    session.queue_scalars(list(rows))
    return session


# ── nucleo puro ───────────────────────────────────────────────────────────


def test_line_cost_is_qty_times_scrap_times_unit_cost():
    line = MaterialCostLine(
        component_code="RESINA",
        component_name="Resina epoxi",
        quantity_per=Decimal("2"),
        scrap_factor=Decimal("1.05"),
        unit_cost=Decimal("10"),
        has_cost=True,
    )
    assert line.line_cost == Decimal("21.00")  # 2 x 1.05 x 10


def test_from_lines_totals_cost_and_counts_missing():
    lines = [
        MaterialCostLine("A", "a", Decimal("1"), Decimal("1"), Decimal("4"), True),
        MaterialCostLine("B", "b", Decimal("2"), Decimal("1"), Decimal("0"), False),
    ]
    res = MaterialCostResult.from_lines(uuid4(), lines)
    assert res.total_material_cost == Decimal("4")
    assert res.component_count == 2
    assert res.missing_cost_count == 1


def test_bom_costs_sums_repeated_component_codes():
    """Componente que aparece em duas linhas de BOM nao se perde — soma-se."""
    lines = [
        MaterialCostLine("DUP", "x", Decimal("1"), Decimal("1"), Decimal("3"), True),
        MaterialCostLine("DUP", "x", Decimal("2"), Decimal("1"), Decimal("3"), True),
    ]
    res = MaterialCostResult.from_lines(uuid4(), lines)
    assert res.bom_costs == {"DUP": Decimal("9")}  # 3 + 6, uma so chave


def test_is_complete_false_when_a_component_has_no_cost():
    lines = [
        MaterialCostLine("A", "a", Decimal("1"), Decimal("1"), Decimal("4"), True),
        MaterialCostLine("B", "b", Decimal("1"), Decimal("1"), Decimal("0"), False),
    ]
    assert MaterialCostResult.from_lines(uuid4(), lines).is_complete is False


def test_is_complete_true_when_all_components_priced():
    lines = [
        MaterialCostLine("A", "a", Decimal("1"), Decimal("1"), Decimal("4"), True),
    ]
    assert MaterialCostResult.from_lines(uuid4(), lines).is_complete is True


# ── servico ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_material_cost_service_sums_bom_from_db_rows():
    rows = [
        (Decimal("2"), Decimal("1.0"), "RESINA", "Resina", Decimal("5.00")),
        (Decimal("1"), Decimal("1.05"), "FOAM", "Foam FP", Decimal("10.00")),
        (Decimal("3"), Decimal("1.0"), "PARAF", "Parafuso", None),  # sem custo
    ]
    svc = MaterialCostService(_session_with_rows(rows), TENANT)

    res = await svc.material_cost(uuid4())

    # 2x1.0x5 + 1x1.05x10 + 3x1.0x0 = 10 + 10.5 + 0
    assert res.total_material_cost == Decimal("20.5")
    assert res.component_count == 3
    assert res.missing_cost_count == 1
    assert res.is_complete is False
    assert res.bom_costs["FOAM"] == Decimal("10.50")


@pytest.mark.asyncio
async def test_material_cost_service_empty_bom_is_zero():
    """Produto sem BOM -> custo 0, zero componentes (nao e erro)."""
    svc = MaterialCostService(_session_with_rows([]), TENANT)
    res = await svc.material_cost(uuid4())
    assert res.total_material_cost == Decimal("0")
    assert res.component_count == 0
    assert res.is_complete is False  # zero componentes != completo
