"""
Q.55.B.3 — `calculate_kpis` conta a tabela de ordens real e não inventa
uma disponibilidade de 0%.

Antes: as contagens de ordens vinham de `plan.production_schedules` (output
do scheduler, 159 linhas esparsas) → 0 ordens; e a disponibilidade era
`fases_iniciadas / fases_totais` = `0 / 159` = 0,0% — uma leitura falsa que
o copiloto reportava como real ("Disponibilidade: 0,00%").
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.profit.api.kpis import calculate_kpis

TENANT = uuid4()


class _Result:
    """Resultado de um `execute()` — devolve o que o teste programou."""

    def __init__(self, scalar=None, first=None):
        self._scalar = scalar
        self._first = first

    def scalar(self):
        return self._scalar

    def first(self):
        return self._first

    def all(self):
        return []


class _Session:
    """Sessão falsa que devolve resultados por ordem de `execute()`.

    Ordem em `calculate_kpis`: orders_total, orders_in_progress,
    orders_completed, phases_started, phases_total, performance.
    """

    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _stmt):
        return self._results.pop(0) if self._results else _Result()


@pytest.mark.asyncio
async def test_contagem_de_ordens_vem_de_production_orders():
    """As 3 contagens de ordens reflectem `plan.production_orders`."""
    session = _Session([
        _Result(scalar=521),   # orders_total
        _Result(scalar=164),   # orders_in_progress
        _Result(scalar=357),   # orders_completed
        _Result(scalar=120),   # phases_started
        _Result(scalar=159),   # phases_total
        _Result(first=None),   # performance
    ])

    kpis = await calculate_kpis(session, TENANT)

    assert kpis["orders_total"].value == 521.0
    assert kpis["orders_in_progress"].value == 164.0
    assert kpis["orders_completed"].value == 357.0
    assert "plan.production_orders" in kpis["orders_total"].citations[0].ref


@pytest.mark.asyncio
async def test_disponibilidade_nao_inventa_zero():
    """Sem fases iniciadas, a disponibilidade é None com motivo claro —
    nunca um 0,0% que parece uma leitura real."""
    session = _Session([
        _Result(scalar=521),   # orders_total
        _Result(scalar=164),   # orders_in_progress
        _Result(scalar=357),   # orders_completed
        _Result(scalar=0),     # phases_started — nenhuma iniciada
        _Result(scalar=159),   # phases_total
        _Result(first=None),   # performance
    ])

    kpis = await calculate_kpis(session, TENANT)

    assert kpis["availability"].value is None
    assert kpis["availability"].reason == "NO_SOURCE_DATA"
