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

TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ── sessao falsa ──────────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._scalar


class _FakeSession:
    """Serve duas queries: o factor de M.O. (Q.167.F, lê core.erp_variables) e
    as linhas de BOM canned — (qty, scrap, code, name, std_cost, erp_type_id).

    ``factor`` é a string que o espelho devolveria (ex.: '1.065'), ou None
    quando a variável não está espelhada (fallback honesto = 1)."""

    def __init__(self, rows, factor="1"):
        self._rows = rows
        self._factor = factor

    async def execute(self, stmt):
        if "erp_variables" in str(stmt).lower():
            return _FakeResult(scalar=self._factor)
        return _FakeResult(rows=self._rows)


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
        # (qty, scrap, code, name, std_cost, erp_type_id) — nenhum é P_TP_ID=90.
        (Decimal("2"), Decimal("1.0"), "RESINA", "Resina", Decimal("5.00"), None),
        (Decimal("1"), Decimal("1.05"), "FOAM", "Foam FP", Decimal("10.00"), 5),
        (Decimal("3"), Decimal("1.0"), "PARAF", "Parafuso", None, 5),  # sem custo
    ]
    svc = MaterialCostService(_FakeSession(rows), TENANT)

    res = await svc.material_cost(uuid4())

    # 2x1.0x5 + 1x1.05x10 + 3x1.0x0 = 10 + 10.5 + 0 (sem factor: nenhum é 90)
    assert res.total_material_cost == Decimal("20.5")
    assert res.component_count == 3
    assert res.missing_cost_count == 1
    assert res.is_complete is False
    assert res.bom_costs["FOAM"] == Decimal("10.50")


@pytest.mark.asyncio
async def test_material_cost_service_empty_bom_is_zero():
    """Produto sem BOM -> custo 0, zero componentes (nao e erro)."""
    svc = MaterialCostService(_FakeSession([]), TENANT)
    res = await svc.material_cost(uuid4())
    assert res.total_material_cost == Decimal("0")
    assert res.component_count == 0
    assert res.is_complete is False  # zero componentes != completo


# ── Q.167.F: factor de correcção das mãos-de-obra (P_TP_ID=90) ─────────────


@pytest.mark.asyncio
async def test_labor_factor_applies_only_to_p_tp_id_90():
    """Componente P_TP_ID=90 leva o factor 1.065; os outros ficam intactos."""
    rows = [
        (Decimal("1"), Decimal("1.0"), "COMP90", "Componente", Decimal("100.00"), 90),
        (Decimal("1"), Decimal("1.0"), "RESINA", "Resina", Decimal("100.00"), 5),
    ]
    svc = MaterialCostService(_FakeSession(rows, factor="1.065"), TENANT)
    res = await svc.material_cost(uuid4())

    assert res.bom_costs["COMP90"] == Decimal("106.500")   # 100 x 1.065
    assert res.bom_costs["RESINA"] == Decimal("100.0")     # sem factor


@pytest.mark.asyncio
async def test_labor_factor_read_from_mirror_not_literal():
    """O valor vem do espelho — pôr 1.10 prova que não é o literal 1.065."""
    rows = [(Decimal("1"), Decimal("1.0"), "COMP90", "C", Decimal("200.00"), 90)]
    svc = MaterialCostService(_FakeSession(rows, factor="1.10"), TENANT)
    res = await svc.material_cost(uuid4())
    assert res.bom_costs["COMP90"] == Decimal("220.000")   # 200 x 1.10


@pytest.mark.asyncio
async def test_labor_factor_absent_falls_back_to_one():
    """Variável não espelhada (None) -> factor 1 (honesto, sem fabricar)."""
    rows = [(Decimal("1"), Decimal("1.0"), "COMP90", "C", Decimal("100.00"), 90)]
    svc = MaterialCostService(_FakeSession(rows, factor=None), TENANT)
    res = await svc.material_cost(uuid4())
    assert res.bom_costs["COMP90"] == Decimal("100.0")     # inalterado


@pytest.mark.asyncio
async def test_labor_factor_not_applied_to_missing_cost():
    """Um componente 90 sem custo continua sem custo (não inflaciona o 0)."""
    rows = [(Decimal("1"), Decimal("1.0"), "COMP90", "C", None, 90)]
    svc = MaterialCostService(_FakeSession(rows, factor="1.065"), TENANT)
    res = await svc.material_cost(uuid4())
    assert res.total_material_cost == Decimal("0")
    assert res.missing_cost_count == 1
