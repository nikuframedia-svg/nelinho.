"""
F4.E — HR: endpoint morto removido + agregação de produtividade única.

* POST /allocations/create era código morto (zero consumidores — o
  frontend só chama /daily via workforceApi) com semântica sobreposta
  ao /daily; foi removido da API pública.
* A agregação (somas de horas/quantidades + eficiência/qualidade) estava
  copiada em 3 sítios; agora vive em
  ``productivity_service.aggregate_productivity_totals``.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.hr.api.allocations import router as allocations_router
from src.hr.services.productivity_service import aggregate_productivity_totals
from tests.conftest import TEST_TENANT_ID, FakeSession


# ─── /allocations/create removido ──────────────────────────────────────────


def _route_paths(router):
    return {r.path for r in router.routes}


def test_allocations_create_endpoint_removed():
    paths = _route_paths(allocations_router)
    assert "/allocations/create" not in paths


def test_allocations_daily_endpoint_still_exists():
    # O caminho vivo (Q.31.D.2/Q.55.B) tem de continuar registado.
    paths = _route_paths(allocations_router)
    assert "/allocations/daily" in paths


# ─── agregação única ────────────────────────────────────────────────────────


def _record(std="8", act="10", act_qty="10", good="9"):
    return SimpleNamespace(
        standard_hours=Decimal(std),
        actual_hours=Decimal(act),
        actual_quantity=Decimal(act_qty),
        good_quantity=Decimal(good),
    )


def test_aggregate_totals_matches_legacy_formula():
    # 2 registos: std 8+4=12, act 10+10=20 → eficiência 60%;
    # qty 10+10=20, good 9+11=20 → qualidade 100%.
    records = [_record(), _record(std="4", act="10", act_qty="10", good="11")]

    totals = aggregate_productivity_totals(records)

    assert totals["total_std_hours"] == Decimal("12")
    assert totals["total_act_hours"] == Decimal("20")
    assert totals["efficiency_percent"] == Decimal("60")
    assert totals["quality_percent"] == Decimal("100")


def test_aggregate_totals_empty_is_honest_zero():
    totals = aggregate_productivity_totals([])
    assert totals["total_std_hours"] == Decimal("0")
    assert totals["efficiency_percent"] == Decimal("0")
    assert totals["quality_percent"] == Decimal("0")


def test_aggregate_totals_zero_hours_no_division_error():
    totals = aggregate_productivity_totals(
        [_record(std="5", act="0", act_qty="0", good="0")]
    )
    assert totals["efficiency_percent"] == Decimal("0")
    assert totals["quality_percent"] == Decimal("0")


@pytest.mark.asyncio
async def test_get_order_productivity_uses_shared_aggregation():
    # Paridade de comportamento: o serviço devolve os mesmos números que a
    # fórmula antiga (in-place) devolvia.
    from src.hr.services.productivity_service import ProductivityService

    session = FakeSession()
    rec = _record(std="6", act="8", act_qty="4", good="3")
    rec.employee_id = uuid4()
    session.queue_scalars([rec])

    svc = ProductivityService(session, TEST_TENANT_ID)
    result = await svc.get_order_productivity(order_id="OF-123")

    assert result["records_count"] == 1
    assert result["total_standard_hours"] == 6.0
    assert result["total_actual_hours"] == 8.0
    assert result["efficiency_percent"] == 75.0
    assert result["quality_percent"] == 75.0
    assert result["employees_involved"] == [str(rec.employee_id)]
