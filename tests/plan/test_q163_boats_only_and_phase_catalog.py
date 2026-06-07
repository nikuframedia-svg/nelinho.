"""Q.163 — /overall só-barcos: realizado filtrado a barcos + catálogo de fases.

Dois invariantes do fix:
  1. `actuals_items(boats_only=...)` escolhe o SQL certo — a variante com INNER JOIN
     a `v_of_is_boat` (default) vs a variante "tudo" (toggle "Mostrar acessórios").
  2. `GET /v1/plan/phases/catalog` mapeia `factory_raw.fases_producao` para
     `PhaseCatalogItem` preservando a ordem (FP_SEQUENCIA, garantida pelo SQL).

Caminho SQL coberto com FakeSession (queue de mappings) que REGISTA o statement
executado — sem BD real. DAMP > DRY.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import pytest

from src.plan.api.phase_preferred_operators import (
    PhaseCatalogItem,
    list_phase_catalog,
)
from src.plan.services.timeline_actuals_service import (
    _BOAT_IDS_SQL,
    _FASES_BY_RANGE_BOATS_SQL,
    _FASES_BY_RANGE_SQL,
    TimelineActualsService,
)

_TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _MapResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)


class _RecSession:
    """FakeSession que devolve filas de mappings E regista os statements."""

    def __init__(self, queues):
        self._queues = list(queues)
        self.statements: list = []

    async def execute(self, stmt, *_a, **_k):
        self.statements.append(stmt)
        return _MapResult(self._queues.pop(0) if self._queues else [])


def _row(of_id, phase_id):
    return {
        "offp_id": f"{of_id}-{phase_id}", "of_id": of_id, "phase_id": phase_id,
        "fase_inicio": datetime(2026, 5, 1, 8), "fase_fim": None, "duration_min": None,
    }


# ── 1. boats_only escolhe o SQL certo ────────────────────────────────────────
# Q.163 — boats_only=True faz 2 queries: (a) ids de barco (_BOAT_IDS_SQL),
# (b) of_fp filtrado por ANY(:boat_ids) (_FASES_BY_RANGE_BOATS_SQL). Filas:
# boat_ids, phase_rows, of-names, fase-names, workers.

@pytest.mark.asyncio
async def test_actuals_boats_only_default_fetches_boat_ids_then_boat_sql():
    """Default (sem arg) → ids de barco primeiro, depois of_fp com ANY(boat_ids)."""
    session = _RecSession([[{"of_id": 1}], [_row("OF1", "1")], [], [], []])
    svc = TimelineActualsService(session, _TENANT)  # type: ignore[arg-type]
    await svc.actuals_items(date(2026, 5, 1), date(2026, 5, 7), cap=100)
    assert session.statements[0] is _BOAT_IDS_SQL
    assert session.statements[1] is _FASES_BY_RANGE_BOATS_SQL


@pytest.mark.asyncio
async def test_actuals_boats_only_true_fetches_boat_ids():
    session = _RecSession([[{"of_id": 1}], [_row("OF1", "1")], [], [], []])
    svc = TimelineActualsService(session, _TENANT)  # type: ignore[arg-type]
    await svc.actuals_items(date(2026, 5, 1), date(2026, 5, 7), cap=100, boats_only=True)
    assert session.statements[0] is _BOAT_IDS_SQL
    assert session.statements[1] is _FASES_BY_RANGE_BOATS_SQL


@pytest.mark.asyncio
async def test_actuals_boats_only_false_uses_all_sql_no_boat_ids():
    """Toggle 'Mostrar acessórios' → SQL sem filtro de barcos; NÃO busca boat_ids."""
    session = _RecSession([[_row("OF1", "1")], [], [], []])
    svc = TimelineActualsService(session, _TENANT)  # type: ignore[arg-type]
    await svc.actuals_items(date(2026, 5, 1), date(2026, 5, 7), cap=100, boats_only=False)
    assert session.statements[0] is _FASES_BY_RANGE_SQL
    assert _BOAT_IDS_SQL not in session.statements


def test_boat_sql_filters_via_canonical_view():
    """A query de ids usa o critério canónico; a de fases filtra por ANY(boat_ids)."""
    ids_sql = str(_BOAT_IDS_SQL)
    assert "v_of_is_boat" in ids_sql and "is_boat = true" in ids_sql
    boats_sql = str(_FASES_BY_RANGE_BOATS_SQL)
    assert "ANY(" in boats_sql and "boat_ids" in boats_sql
    # a variante "tudo" NÃO filtra barcos.
    assert "boat_ids" not in str(_FASES_BY_RANGE_SQL)
    assert "v_of_is_boat" not in str(_FASES_BY_RANGE_SQL)


# ── 2. catálogo de fases mapeia + preserva ordem ─────────────────────────────

@pytest.mark.asyncio
async def test_phase_catalog_maps_and_preserves_order():
    """Mapeia fases_producao → PhaseCatalogItem; ordem vem do SQL (FP_SEQUENCIA)."""
    session = _RecSession([[
        {"phase_id": "11", "phase_name": "Não Laminado", "sequence": 1, "is_production": True},
        {"phase_id": "1", "phase_name": "Laminagem", "sequence": 10, "is_production": True},
        {"phase_id": "9", "phase_name": "Armazem", "sequence": 30, "is_production": False},
    ]])
    out = await list_phase_catalog(_tenant_id=_TENANT, session=session)  # type: ignore[arg-type]
    assert [p.phase_id for p in out] == ["11", "1", "9"]  # ordem preservada
    assert all(isinstance(p, PhaseCatalogItem) for p in out)
    assert out[1].phase_name == "Laminagem" and out[1].sequence == 10
    assert out[2].is_production is False  # terminal (Armazem)


@pytest.mark.asyncio
async def test_phase_catalog_empty_is_tolerated():
    session = _RecSession([[]])
    out = await list_phase_catalog(_tenant_id=_TENANT, session=session)  # type: ignore[arg-type]
    assert out == []
