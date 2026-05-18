"""Q.37.B — COGS usa o custo de retrabalho REAL em vez da taxa padrão.

Duas superfícies:
* o calculador puro `COGSCalculator._calculate_scrap_cost` / `calculate`
  — `actual_rework_cost_eur` substitui a estimativa por `scrap_rate`;
* o serviço `CostService` — agrega `quality.rework_entry.cost_estimate_eur`
  por `of_id` e injecta-o no calculador, com fallback à taxa padrão.
"""

from decimal import Decimal
from uuid import UUID

import pytest

from src.profit.calculators.cogs_calculator import COGSCalculator
from src.profit.services.cost_service import CostService

TENANT = UUID("00000000-0000-0000-0000-000000000001")
PRODUCT = UUID("00000000-0000-0000-0000-0000000000aa")


# ── calculador puro ───────────────────────────────────────────────────────


def test_scrap_uses_actual_rework_cost_when_provided():
    """Com `actual_rework_cost_eur` o scrap é exactamente esse valor."""
    calc = COGSCalculator()
    result = calc.calculate(
        order_id="OF-1",
        product_id="K1",
        quantity=Decimal("10"),
        bom_costs={"RESINA": Decimal("500")},
        scrap_rate=Decimal("0.02"),
        actual_rework_cost_eur=Decimal("2350.00"),
    )
    assert result.breakdown.scrap.total == Decimal("2350.00")
    assert result.breakdown.scrap.details["source"] == "actual_rework"
    assert result.assumptions["scrap_source"] == "actual_rework"


def test_scrap_falls_back_to_rate_estimate_when_no_actual():
    """Sem dados reais o scrap continua a vir da estimativa por taxa."""
    calc = COGSCalculator()
    result = calc.calculate(
        order_id="OF-2",
        product_id="K1",
        quantity=Decimal("10"),
        bom_costs={"RESINA": Decimal("500")},
        scrap_rate=Decimal("0.02"),
    )
    # 10 × 0.02 × 50 €/un = 10 € de material perdido (sem mão-de-obra)
    assert result.breakdown.scrap.total == Decimal("10.00")
    assert result.breakdown.scrap.details["source"] == "scrap_rate_estimate"
    assert result.assumptions["scrap_source"] == "scrap_rate_estimate"


def test_actual_rework_cost_zero_is_honoured_not_treated_as_missing():
    """0 € explícito é um valor real (retrabalho de custo nulo), não fallback."""
    calc = COGSCalculator()
    result = calc.calculate(
        order_id="OF-3",
        product_id="K1",
        quantity=Decimal("10"),
        bom_costs={"RESINA": Decimal("500")},
        scrap_rate=Decimal("0.02"),
        actual_rework_cost_eur=Decimal("0"),
    )
    assert result.breakdown.scrap.total == Decimal("0")
    assert result.breakdown.scrap.details["source"] == "actual_rework"


# ── CostService: agregação de ReworkEntry ─────────────────────────────────


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


class _FakeSession:
    """Devolve a soma + contagem de retrabalho preparada para a ordem."""

    def __init__(self, *, sum_eur, count):
        self._sum = sum_eur
        self._count = count
        self.added: list = []

    async def execute(self, _stmt):
        return _FakeResult((self._sum, self._count))

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


@pytest.mark.asyncio
async def test_cost_service_uses_aggregated_rework_when_entries_exist(monkeypatch):
    """Com ReworkEntry reais, o scrap do COGS é a soma de cost_estimate_eur."""
    async def _no_publish(*a, **k):
        return True

    monkeypatch.setattr(
        "src.profit.services.cost_service.publish_event", _no_publish
    )

    session = _FakeSession(sum_eur=Decimal("1800.00"), count=3)
    svc = CostService(session=session, tenant_id=TENANT)
    result = await svc.calculate_cogs(
        order_id="OF-100",
        product_id=PRODUCT,
        quantity=Decimal("5"),
        bom_costs={"RESINA": Decimal("250")},
        scrap_rate=Decimal("0.02"),
        save=False,
    )
    assert result.breakdown.scrap.total == Decimal("1800.00")
    assert result.breakdown.scrap.details["source"] == "actual_rework"


@pytest.mark.asyncio
async def test_cost_service_falls_back_when_no_rework_entries(monkeypatch):
    """Sem ReworkEntry com € (count=0), o COGS cai na estimativa por taxa."""
    async def _no_publish(*a, **k):
        return True

    monkeypatch.setattr(
        "src.profit.services.cost_service.publish_event", _no_publish
    )

    session = _FakeSession(sum_eur=Decimal("0"), count=0)
    svc = CostService(session=session, tenant_id=TENANT)
    result = await svc.calculate_cogs(
        order_id="OF-200",
        product_id=PRODUCT,
        quantity=Decimal("5"),
        bom_costs={"RESINA": Decimal("250")},
        scrap_rate=Decimal("0.02"),
        save=False,
    )
    assert result.breakdown.scrap.details["source"] == "scrap_rate_estimate"


@pytest.mark.asyncio
async def test_cost_service_flag_off_disables_actual_rework(monkeypatch):
    """`use_actual_rework_cost=False` reverte ao comportamento pré-Q.37.B."""
    async def _no_publish(*a, **k):
        return True

    monkeypatch.setattr(
        "src.profit.services.cost_service.publish_event", _no_publish
    )

    session = _FakeSession(sum_eur=Decimal("1800.00"), count=3)
    svc = CostService(
        session=session, tenant_id=TENANT, use_actual_rework_cost=False
    )
    result = await svc.calculate_cogs(
        order_id="OF-300",
        product_id=PRODUCT,
        quantity=Decimal("5"),
        bom_costs={"RESINA": Decimal("250")},
        scrap_rate=Decimal("0.02"),
        save=False,
    )
    assert result.breakdown.scrap.details["source"] == "scrap_rate_estimate"
