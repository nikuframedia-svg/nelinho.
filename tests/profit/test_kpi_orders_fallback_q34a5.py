"""
Sprint Q.34.A.5 — testes do fallback de contagem de ordens em calculate_kpis.

Quando `plan.production_schedules` está vazio (CPO ainda não correu) mas
`plan.production_orders` tem ordens reais sincronizadas do ERP, as
contagens de ordens passam a vir das production_orders. As métricas que
precisam de actuals (oee/availability/performance) ficam None — honesto.

Fake session local: devolve scalars de uma fila ordenada; `first()` → None
(o conftest `_FakeResult` não tem `.first()`, que a query de performance usa).

Ordem dos `execute` em calculate_kpis:
  1-3   ordens via production_schedules        (.scalar)
  4-6   fallback production_orders (só se 1==0) (.scalar)
  7-8   phases_started / phases_total          (.scalar)
  9     performance                            (.first → None)
"""

from __future__ import annotations

from uuid import UUID

import pytest

from src.profit.api.kpis import calculate_kpis

_TENANT = UUID("00000000-0000-0000-0000-000000000001")


class _Result:
    def __init__(self, scalar=None):
        self._scalar = scalar

    def scalar(self):
        return self._scalar

    def first(self):
        return None


class _KpiFakeSession:
    """Devolve scalars de uma fila ordenada pela ordem dos `execute`."""

    def __init__(self, scalars):
        self._scalars = list(scalars)

    async def execute(self, stmt):
        val = self._scalars.pop(0) if self._scalars else None
        return _Result(val)


async def test_orders_count_falls_back_to_production_orders():
    """schedules a 0 → contagens vêm de plan.production_orders."""
    session = _KpiFakeSession([0, 0, 0, 521, 500, 21, 0, 0])

    kpis = await calculate_kpis(session, _TENANT)

    assert kpis["orders_total"].value == 521.0
    assert kpis["orders_in_progress"].value == 500.0
    assert kpis["orders_completed"].value == 21.0
    assert "plan.production_orders" in kpis["orders_total"].citations[0].ref
    # Métricas sem actuals continuam None — não se fabrica.
    assert kpis["oee"].value is None
    assert kpis["performance"].value is None
    assert kpis["quality_fpy"].value is None


async def test_no_fallback_when_schedules_have_orders():
    """schedules com ordens → não se toca; citação aponta a schedules."""
    session = _KpiFakeSession([159, 159, 0, 0, 0])

    kpis = await calculate_kpis(session, _TENANT)

    assert kpis["orders_total"].value == 159.0
    assert (
        "plan.production_schedules" in kpis["orders_total"].citations[0].ref
    )


async def test_both_sources_empty_stays_no_source_data():
    """Sem ordens em lado nenhum → orders_total None / NO_SOURCE_DATA."""
    session = _KpiFakeSession([0, 0, 0, 0, 0, 0, 0, 0])

    kpis = await calculate_kpis(session, _TENANT)

    assert kpis["orders_total"].value is None
    assert kpis["orders_total"].reason == "NO_SOURCE_DATA"
