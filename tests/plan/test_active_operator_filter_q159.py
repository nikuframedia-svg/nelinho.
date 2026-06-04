"""Q.159 — filtro "operador ativo" (E_ACTIVO + últimos 2 meses) sobre o pool da
CPO. Property tests (hypothesis) dos invariantes Spelke do `_apply_active_operator_filter`
+ smoke do loader `_load_active_operators_db` (graceful quando a view falta).

Invariantes (axioma 5 — skill match, NUNCA alargar o pool):
  - input-only: cada pool resultante ⊆ pool original (nunca inventa operadores);
  - não-vazio: uma fase que TINHA operadores nunca fica vazia (fallback ao histórico);
  - inerte: `active` vazio → matriz intacta (back-compat exacto).
"""

from __future__ import annotations

from uuid import UUID

import pytest
from hypothesis import given, strategies as st
from sqlalchemy.exc import SQLAlchemyError

from src.plan.cpo.state import (
    _apply_active_operator_filter,
    _load_active_operators_db,
)

TENANT = UUID("11111111-1111-1111-1111-111111111111")

# Códigos de operador pequenos para o espaço de busca ser denso (colisões reais).
_codes = st.text(min_size=1, max_size=2, alphabet="abcde")
_matrix = st.dictionaries(
    keys=st.text(min_size=1, max_size=2, alphabet="123"),
    values=st.sets(_codes, max_size=6),
    max_size=6,
)
_active = st.sets(_codes, max_size=6)


@given(matrix=_matrix, active=_active)
def test_subset_never_empties_and_equals_intersection(matrix, active):
    src = {k: set(v) for k, v in matrix.items()}
    out = _apply_active_operator_filter({k: set(v) for k, v in src.items()}, set(active))

    assert set(out) == set(src), "mantém exactamente as mesmas fases"
    for fase, pool in src.items():
        assert out[fase] <= pool, "input-only: nunca alarga o pool (axioma 5)"
        if pool:
            assert out[fase], f"fase {fase} ficou vazia — fallback em falta"
        inter = pool & set(active)
        if active and inter:
            assert out[fase] == inter, "interseção quando há ativos nessa fase"
        elif active and pool:
            assert out[fase] == pool, "fallback ao histórico quando 0 ativos"


@given(matrix=_matrix)
def test_empty_active_is_inert(matrix):
    src = {k: set(v) for k, v in matrix.items()}
    assert _apply_active_operator_filter({k: set(v) for k, v in src.items()}, set()) == src


# ── loader graceful (sem BD) ─────────────────────────────────────────────────


class _Res:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar(self):
        return self._scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _Sess:
    def __init__(self, exists=None, rows=None, raise_exc=False):
        self.exists = exists
        self.rows = rows or []
        self.raise_exc = raise_exc

    async def execute(self, stmt, *args, **kwargs):
        if self.raise_exc:
            raise SQLAlchemyError("relation factory_raw.v_active_operators does not exist")
        if "information_schema" in str(stmt):
            return _Res(scalar=self.exists)
        return _Res(rows=self.rows)


@pytest.mark.asyncio
async def test_loader_returns_empty_when_view_missing():
    assert await _load_active_operators_db(_Sess(exists=None), TENANT) == set()


@pytest.mark.asyncio
async def test_loader_returns_codes_when_view_present():
    rows = [{"code": "7"}, {"code": "9"}, {"code": None}]
    out = await _load_active_operators_db(_Sess(exists=1, rows=rows), TENANT)
    assert out == {"7", "9"}  # None descartado


@pytest.mark.asyncio
async def test_loader_swallows_db_error():
    assert await _load_active_operators_db(_Sess(raise_exc=True), TENANT) == set()


@pytest.mark.asyncio
async def test_loader_none_session():
    assert await _load_active_operators_db(None, TENANT) == set()
