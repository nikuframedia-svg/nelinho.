"""Q.26.C.2 — testes do LaborCostService (custo de mão-de-obra por OF).

Três superfícies:
* o núcleo puro (`LaborCostLine`, `LaborCostResult.from_lines`) —
  aritmética de custo, sem BD;
* `build_labor_lines` — agrupar operadores por operação e preçar;
* o serviço (`LaborCostService.labor_cost`) contra o adapter falsificado
  e uma sessão falsa que devolve taxas canned.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from src.adapters.nelo.schemas import OrderLaborRow
from src.profit.services.labor_cost_service import (
    LaborCostLine,
    LaborCostResult,
    LaborCostService,
    build_labor_lines,
)
from tests.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ── fixtures de dados ─────────────────────────────────────────────────────


def _row(
    operation_id: int,
    operator_id: int,
    *,
    phase_id: int = 1,
    phase_name: str = "Laminagem",
    start: datetime | None = None,
    end: datetime | None = None,
    is_return: bool = False,
    is_chefe: bool = False,
) -> OrderLaborRow:
    """Uma linha adapter (uma execução de fase × um operador)."""
    return OrderLaborRow(
        operation_id=operation_id,
        work_order_id=9000,
        phase_id=phase_id,
        phase_name=phase_name,
        start_at=start,
        end_at=end,
        is_return=is_return,
        operator_id=operator_id,
        is_chefe=is_chefe,
    )


def _line(
    *,
    hours: Decimal,
    sum_rate: Decimal,
    operator_count: int = 1,
    priced: int = 1,
    has_hours: bool = True,
) -> LaborCostLine:
    return LaborCostLine(
        operation_id=1,
        phase_id=1,
        phase_name="Laminagem",
        is_return=False,
        hours=hours,
        operator_count=operator_count,
        priced_operator_count=priced,
        sum_operator_rate=sum_rate,
        has_hours=has_hours,
    )


# ── sessão falsa ──────────────────────────────────────────────────────────


def _session_with_rate_rows(rate_rows) -> FakeSession:
    """Q.68.3.3 — Canonical FakeSession with rate rows queued for ``execute().all()``."""
    session = FakeSession()
    session.queue_scalars(list(rate_rows))
    return session


def _patch_adapter(monkeypatch, rows):
    """Substitui o adapter read-only por uma função que devolve `rows`."""

    async def _fake_list_order_labor(_work_order_id):
        return list(rows)

    monkeypatch.setattr(
        "src.profit.services.labor_cost_service.services.list_order_labor",
        _fake_list_order_labor,
    )


# ── núcleo puro ───────────────────────────────────────────────────────────


def test_line_cost_is_hours_times_sum_rate():
    line = _line(hours=Decimal("4"), sum_rate=Decimal("22.00"))
    assert line.line_cost == Decimal("88.00")  # 4h × (10 + 12)


def test_from_lines_totals_and_counts():
    lines = [
        _line(hours=Decimal("4"), sum_rate=Decimal("20")),
        _line(hours=Decimal("0"), sum_rate=Decimal("0"), has_hours=False),
        _line(hours=Decimal("2"), sum_rate=Decimal("10"), operator_count=2, priced=1),
    ]
    res = LaborCostResult.from_lines(9000, lines)
    assert res.total_labor_cost == Decimal("100")  # 80 + 0 + 20
    assert res.phase_count == 3
    assert res.missing_hours_count == 1
    assert res.unpriced_operator_count == 1  # 2 atribuídos, 1 precado


def test_is_complete_false_when_a_phase_has_no_hours():
    lines = [_line(hours=Decimal("0"), sum_rate=Decimal("0"), has_hours=False)]
    assert LaborCostResult.from_lines(9000, lines).is_complete is False


def test_is_complete_false_when_an_operator_is_unpriced():
    lines = [_line(hours=Decimal("4"), sum_rate=Decimal("10"), operator_count=2, priced=1)]
    assert LaborCostResult.from_lines(9000, lines).is_complete is False


def test_is_complete_true_when_all_phases_priced_with_hours():
    lines = [_line(hours=Decimal("4"), sum_rate=Decimal("10"))]
    assert LaborCostResult.from_lines(9000, lines).is_complete is True


def test_is_complete_false_when_no_phases():
    assert LaborCostResult.from_lines(9000, []).is_complete is False


# ── build_labor_lines ─────────────────────────────────────────────────────


def test_build_groups_operators_of_one_operation_into_one_line():
    """Par de operadores na mesma fase → uma linha, ambas as taxas somadas."""
    rows = [
        _row(1001, 20345, start=datetime(2026, 1, 5, 8), end=datetime(2026, 1, 5, 12)),
        _row(1001, 20350, start=datetime(2026, 1, 5, 8), end=datetime(2026, 1, 5, 12)),
    ]
    rates = {"20345": Decimal("10"), "20350": Decimal("12")}
    lines = build_labor_lines(rows, rates)
    assert len(lines) == 1
    assert lines[0].operator_count == 2
    assert lines[0].sum_operator_rate == Decimal("22")
    assert lines[0].line_cost == Decimal("88")  # 4h × 22


def test_build_counts_operator_without_a_rate_as_unpriced():
    rows = [
        _row(1001, 20345, start=datetime(2026, 1, 5, 8), end=datetime(2026, 1, 5, 12)),
        _row(1001, 99999, start=datetime(2026, 1, 5, 8), end=datetime(2026, 1, 5, 12)),
    ]
    rates = {"20345": Decimal("10")}  # 99999 sem taxa
    line = build_labor_lines(rows, rates)[0]
    assert line.operator_count == 2
    assert line.priced_operator_count == 1
    assert line.sum_operator_rate == Decimal("10")  # custo nunca inventado


def test_build_marks_missing_hours_when_dates_are_null():
    rows = [_row(1001, 20345, start=None, end=None)]
    line = build_labor_lines(rows, {"20345": Decimal("10")})[0]
    assert line.has_hours is False
    assert line.hours == Decimal("0")
    assert line.line_cost == Decimal("0")


def test_build_marks_missing_hours_when_elapsed_not_positive():
    """DATAFIM antes (ou igual) ao DATAINICIO é dado sujo — não conta horas."""
    rows = [
        _row(1001, 20345, start=datetime(2026, 1, 5, 12), end=datetime(2026, 1, 5, 8)),
    ]
    line = build_labor_lines(rows, {"20345": Decimal("10")})[0]
    assert line.has_hours is False
    assert line.hours == Decimal("0")


def test_build_separates_distinct_operations():
    rows = [
        _row(1001, 20345, start=datetime(2026, 1, 5, 8), end=datetime(2026, 1, 5, 12)),
        _row(1002, 20345, phase_id=2, phase_name="Acabamento",
             start=datetime(2026, 1, 6, 9), end=datetime(2026, 1, 6, 15, 30)),
    ]
    lines = build_labor_lines(rows, {"20345": Decimal("10")})
    assert len(lines) == 2
    by_op = {ln.operation_id: ln for ln in lines}
    assert by_op[1001].line_cost == Decimal("40")    # 4h × 10
    assert by_op[1002].line_cost == Decimal("65.0")  # 6.5h × 10


# ── serviço ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_labor_cost_service_prices_order_from_erp(monkeypatch):
    _patch_adapter(monkeypatch, [
        _row(1001, 20345, start=datetime(2026, 1, 5, 8), end=datetime(2026, 1, 5, 12)),
        _row(1001, 20350, start=datetime(2026, 1, 5, 8), end=datetime(2026, 1, 5, 12)),
        _row(1002, 20345, phase_id=2, phase_name="Acabamento",
             start=datetime(2026, 1, 6, 9), end=datetime(2026, 1, 6, 15, 30)),
    ])
    session = _session_with_rate_rows([
        ("20345", date(2026, 1, 1), Decimal("10.00")),
        ("20350", date(2026, 1, 1), Decimal("12.00")),
    ])
    svc = LaborCostService(session, TENANT)

    res = await svc.labor_cost(9000)

    assert res.total_labor_cost == Decimal("153.00")  # 4h×22 + 6.5h×10
    assert res.phase_count == 2
    assert res.missing_hours_count == 0
    assert res.unpriced_operator_count == 0
    assert res.is_complete is True


@pytest.mark.asyncio
async def test_labor_cost_service_empty_order_is_zero(monkeypatch):
    """OF sem execuções com operador → custo 0, não é erro."""
    _patch_adapter(monkeypatch, [])
    svc = LaborCostService(_session_with_rate_rows([]), TENANT)
    res = await svc.labor_cost(9000)
    assert res.total_labor_cost == Decimal("0")
    assert res.phase_count == 0
    assert res.is_complete is False


@pytest.mark.asyncio
async def test_labor_cost_service_uses_latest_effective_rate(monkeypatch):
    """Taxa time-phased: escolhe a effective_date mais recente ≤ as_of."""
    _patch_adapter(monkeypatch, [
        _row(1001, 20345, start=datetime(2026, 1, 5, 8), end=datetime(2026, 1, 5, 12)),
    ])
    session = _session_with_rate_rows([
        ("20345", date(2025, 1, 1), Decimal("8.00")),   # antiga
        ("20345", date(2026, 1, 1), Decimal("10.00")),  # mais recente
    ])
    svc = LaborCostService(session, TENANT)

    res = await svc.labor_cost(9000, as_of=date(2026, 5, 17))

    assert res.total_labor_cost == Decimal("40.00")  # 4h × 10, não × 8
