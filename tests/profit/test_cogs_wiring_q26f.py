"""Q.26.F.1 — testes da ligação do COGS ponta-a-ponta.

Duas superfícies:
* a função pura `assemble_cogs_inputs` — converte os resultados de
  material/mão-de-obra/overhead nos argumentos do COGSCalculator;
* o serviço `CostService.calculate_cogs_from_sources` — orquestra os 3
  serviços de custo (mockados) e corre o calculador real.
"""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.core.services.configuration_service import ConfigurationService
from src.profit.calculators.cogs_calculator import COGSResult
from src.profit.services.cost_service import CostService, assemble_cogs_inputs
from src.profit.services.labor_cost_service import (
    LaborCostLine,
    LaborCostResult,
    LaborCostService,
)
from src.profit.services.material_cost_service import (
    MaterialCostLine,
    MaterialCostResult,
    MaterialCostService,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ── construtores de dados ─────────────────────────────────────────────────


def _material(lines: list[MaterialCostLine]) -> MaterialCostResult:
    return MaterialCostResult.from_lines(uuid4(), lines)


def _mat_line(code: str, cost: Decimal) -> MaterialCostLine:
    return MaterialCostLine(
        component_code=code,
        component_name=code,
        quantity_per=Decimal("1"),
        scrap_factor=Decimal("1"),
        unit_cost=cost,
        has_cost=cost > 0,
    )


def _labor(lines: list[LaborCostLine]) -> LaborCostResult:
    return LaborCostResult.from_lines(9000, lines)


def _lab_line(
    *, phase_id: int, phase_name: str, hours: Decimal, sum_rate: Decimal,
    has_hours: bool = True,
) -> LaborCostLine:
    return LaborCostLine(
        operation_id=phase_id,
        phase_id=phase_id,
        phase_name=phase_name,
        is_return=False,
        hours=hours,
        operator_count=1,
        priced_operator_count=1,
        sum_operator_rate=sum_rate,
        has_hours=has_hours,
    )


# ── assemble_cogs_inputs (puro) ───────────────────────────────────────────


def test_assemble_maps_each_labor_phase_to_an_allocation():
    labor = _labor([
        _lab_line(phase_id=1, phase_name="Laminagem", hours=Decimal("4"), sum_rate=Decimal("22")),
        _lab_line(phase_id=2, phase_name="Acabamento", hours=Decimal("6"), sum_rate=Decimal("10")),
    ])
    out = assemble_cogs_inputs(_material([_mat_line("RESINA", Decimal("50"))]), labor, Decimal("3"))

    assert out["bom_costs"] == {"RESINA": Decimal("50")}
    assert len(out["labor_allocations"]) == 2
    first = out["labor_allocations"][0]
    assert first["hours"] == Decimal("4")
    assert first["rate"] == Decimal("22")
    assert first["employee_name"] == "Laminagem"


def test_assemble_total_hours_counts_only_lines_with_valid_elapsed():
    labor = _labor([
        _lab_line(phase_id=1, phase_name="Laminagem", hours=Decimal("4"), sum_rate=Decimal("22")),
        _lab_line(phase_id=2, phase_name="Cura", hours=Decimal("0"), sum_rate=Decimal("0"), has_hours=False),
    ])
    out = assemble_cogs_inputs(_material([]), labor, Decimal("3"))
    assert out["total_production_hours"] == Decimal("4")  # a fase sem decorrido não conta


def test_assemble_passes_overhead_rate_through():
    out = assemble_cogs_inputs(_material([]), _labor([]), Decimal("7.5"))
    assert out["overhead_rate"] == Decimal("7.5")


def test_assemble_empty_sources_give_zeros():
    out = assemble_cogs_inputs(_material([]), _labor([]), Decimal("0"))
    assert out["bom_costs"] == {}
    assert out["labor_allocations"] == []
    assert out["total_production_hours"] == Decimal("0")


# ── calculate_cogs_from_sources (orquestração) ────────────────────────────


@pytest.mark.asyncio
async def test_calculate_cogs_from_sources_combines_the_three_sources(monkeypatch):
    """Material (BOM) + mão-de-obra (OF_FP) + overhead → COGS real."""
    material = _material([_mat_line("RESINA", Decimal("50"))])           # 50 €
    labor = _labor([                                                      # 4h × 22 = 88 €
        _lab_line(phase_id=1, phase_name="Laminagem", hours=Decimal("4"), sum_rate=Decimal("22")),
    ])

    async def _fake_material(self, *a, **k):
        return material

    async def _fake_labor(self, *a, **k):
        return labor

    async def _fake_overhead(self, *a, **k):
        return Decimal("10")  # €/h

    async def _fake_publish(*a, **k):
        return True

    monkeypatch.setattr(MaterialCostService, "material_cost", _fake_material)
    monkeypatch.setattr(LaborCostService, "labor_cost", _fake_labor)
    monkeypatch.setattr(ConfigurationService, "get_overhead_rate_value", _fake_overhead)
    monkeypatch.setattr("src.profit.services.cost_service.publish_event", _fake_publish)

    svc = CostService(session=None, tenant_id=TENANT)
    result = await svc.calculate_cogs_from_sources(
        order_id="9000",
        product_id=uuid4(),
        work_order_id=9000,
        save=False,
    )

    assert isinstance(result, COGSResult)
    assert result.breakdown.material.total == Decimal("50")
    assert result.breakdown.labor.total == Decimal("88")
    assert result.breakdown.overhead.total == Decimal("40")   # 10 €/h × 4 h
    assert result.breakdown.machine.total == Decimal("0")     # Q.26.E — adiado (IoT)
    # total = 50 + 88 + 40 + scrap(1.088) = 179.088 -> 179.09
    assert result.total_cogs == Decimal("179.09")
