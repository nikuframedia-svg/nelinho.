"""Q.133.B — N estações paralelas por fase (work-centers da concorrência real).

`station_ids_for` (determinístico) + `derive_phase_stations` (p95→clamp). O
paralelismo no decoder + a exclusividade do molde são provados AO VIVO em
_audit/q133 (schedule real).
"""
from __future__ import annotations

from types import SimpleNamespace  # noqa: F401 (legível nos mocks)
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.plan.services import phase_workcenters as wc


def test_station_ids_deterministic_and_padded():
    ids = wc.station_ids_for("1", 3)
    assert ids == ["1::01", "1::02", "1::03"]
    assert ids == sorted(ids)            # tie-break determinístico do decoder
    assert wc.station_ids_for("LAM", 1) == ["LAM::01"]


def test_station_ids_min_one_station():
    assert wc.station_ids_for("x", 0) == ["x::01"]
    assert wc.station_ids_for("x", -5) == ["x::01"]   # axioma capacity>=1


class _Res:
    def __init__(self, rows):
        self._r = rows

    def mappings(self):
        return self

    def all(self):
        return self._r


@pytest.mark.asyncio
async def test_derive_ceils_and_clamps(monkeypatch):
    rows = [
        {"fase_id": "1", "p95": 10.2},     # Laminagem → ceil = 11
        {"fase_id": "2", "p95": 999.0},    # Corte peças → clamp a N_MAX
        {"fase_id": "3", "p95": None},     # sem amostra → ignorado
    ]
    session = MagicMock()
    session.execute = AsyncMock(return_value=_Res(rows))
    out = await wc.derive_phase_stations(session, uuid4())

    assert out["1"] == 11
    assert out["2"] == wc._N_MAX
    assert "3" not in out


@pytest.mark.asyncio
async def test_derive_session_none_is_safe():
    assert await wc.derive_phase_stations(None, uuid4()) == {}
