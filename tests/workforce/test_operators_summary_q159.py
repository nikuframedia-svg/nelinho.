"""Q.159 — GET /v1/workforce/operators/summary: contagem de "operadores ativos"
(E_ACTIVO + últimos 2 meses, ~107) + quebra por área.

Best-effort: quando a view `factory_raw.v_active_operators` falta (dev sem sync)
devolve `{count:0, by_area:[]}` — estado honesto, nunca rebenta nem inventa.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from src.workforce.operators_summary_api import operators_summary

TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _AreaRow:
    def __init__(self, area, ops):
        self.area = area
        self.ops = ops


class _Sess:
    """Session fake: `scalar()` devolve em sequência [exists, count]; `execute()`
    devolve as linhas por área."""

    def __init__(self, scalars, area_rows=None):
        self._scalars = list(scalars)
        self._area_rows = area_rows or []
        self._i = 0

    async def scalar(self, stmt, *args, **kwargs):
        val = self._scalars[self._i] if self._i < len(self._scalars) else None
        self._i += 1
        return val

    async def execute(self, stmt, *args, **kwargs):
        return iter(self._area_rows)


@pytest.mark.asyncio
async def test_summary_happy_path():
    sess = _Sess(
        scalars=[1, 107],  # view existe, count=107
        area_rows=[_AreaRow("Laminagem", 22), _AreaRow("Corte", 10)],
    )
    out = await operators_summary(tenant_id=TENANT, session=sess)
    assert out["count"] == 107
    assert out["window_days"] == 60
    assert out["by_area"] == [
        {"area": "Laminagem", "ops": 22},
        {"area": "Corte", "ops": 10},
    ]


@pytest.mark.asyncio
async def test_summary_view_missing_returns_zero():
    sess = _Sess(scalars=[None])  # view não existe
    out = await operators_summary(tenant_id=TENANT, session=sess)
    assert out == {"count": 0, "window_days": 60, "by_area": []}
