"""
Q.53.A — DB-backed ML training datasets.

`build_quality_risk_dataset` / `build_duration_dataset` read the durable
factory tables via raw `text()` SQL. These tests drive them through a tiny
fake session that returns prepared `.mappings()` / `.all()` results, so the
labelling + feature logic is covered without a live Postgres.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest

from src.ml.models_domain.training_data import (
    _normalise_phase_key,
    build_duration_dataset,
    build_quality_risk_dataset,
)

TENANT = UUID("11111111-1111-1111-1111-111111111111")
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _Mappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, Any]]:
        return list(self._rows)


class _Result:
    """Mimics enough of SQLAlchemy Result for the dataset builders."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def mappings(self) -> _Mappings:
        return _Mappings(self._rows)

    def all(self) -> list[Any]:
        return list(self._rows)


class _ScriptedSession:
    """Returns queued results in call order — DAMP, no SQL parsing."""

    def __init__(self, results: list[list[Any]]) -> None:
        self._results = results
        self.calls = 0

    async def execute(self, _stmt, _params=None) -> _Result:
        rows = self._results[self.calls]
        self.calls += 1
        return _Result(rows)


# ─── quality-risk dataset ─────────────────────────────────────────────────

def test_quality_risk_dataset_labels_by_empirical_fase_rate():
    """A fase with 40 rework events over 100 phase rows must end up with
    ~40 of its 100 dataset rows labelled is_error=1."""
    phase_rows = [
        {
            "of_id": f"O{i}",
            "fase_id": "36",  # Laminagem
            "molde_id": "M1",
            "data_inicio": T0 + timedelta(hours=i),
            "product_type": "K1",
        }
        for i in range(100)
    ] + [
        {
            "of_id": f"A{i}",
            "fase_id": "9",  # Armazem — no rework
            "molde_id": None,
            "data_inicio": T0 + timedelta(hours=i),
            "product_type": "K1",
        }
        for i in range(50)
    ]
    rework_rows = [("36", 40)]  # 40 rework events blamed on fase 36

    session = _ScriptedSession([phase_rows, rework_rows])
    rows = build_quality_risk_dataset_sync(session)

    lam = [r for r in rows if r["fase_id"] == "36"]
    arm = [r for r in rows if r["fase_id"] == "9"]
    assert len(lam) == 100 and len(arm) == 50
    # 40 / 100 → 40 positives for Laminagem, 0 for Armazem.
    assert sum(r["is_error"] for r in lam) == 40
    assert sum(r["is_error"] for r in arm) == 0
    # phase_error_rate feature reflects the real rate.
    assert lam[0]["phase_error_rate"] == pytest.approx(0.40)
    assert arm[0]["phase_error_rate"] == pytest.approx(0.0)


def test_quality_risk_dataset_clamps_rate_below_one():
    """A fase with more rework events than phase rows must not produce an
    all-positive fase (the classifier needs both classes)."""
    phase_rows = [
        {"of_id": f"O{i}", "fase_id": "1", "molde_id": None,
         "data_inicio": T0 + timedelta(hours=i), "product_type": "K2"}
        for i in range(20)
    ]
    rework_rows = [("1", 500)]  # absurdly high rework count

    session = _ScriptedSession([phase_rows, rework_rows])
    rows = build_quality_risk_dataset_sync(session)

    positives = sum(r["is_error"] for r in rows)
    assert 0 < positives < len(rows)  # clamped to 0.95 → 19 of 20


def test_quality_risk_dataset_empty_when_no_phases():
    session = _ScriptedSession([[], []])
    assert build_quality_risk_dataset_sync(session) == []


# ─── duration dataset ─────────────────────────────────────────────────────

def test_duration_dataset_keeps_positive_hours_only():
    phase_rows = [
        {"of_id": "O1", "fase_id": "36", "fase_nome": "Laminagem",
         "molde_id": "M1", "horas_reais": 7.5,
         "data_inicio": T0, "product_type": "K1"},
        {"of_id": "O2", "fase_id": "36", "fase_nome": "Laminagem",
         "molde_id": None, "horas_reais": 4.0,
         "data_inicio": T0 + timedelta(hours=1), "product_type": "K2"},
    ]
    session = _ScriptedSession([phase_rows])
    rows = build_duration_dataset_sync(session)

    assert len(rows) == 2
    assert all(r["horas_reais"] > 0 for r in rows)
    assert rows[0]["modelo_id"] == "K1"
    assert rows[0]["queue_depth"] == 2  # both rows are fase 36


def test_duration_dataset_empty_when_no_rows():
    session = _ScriptedSession([[]])
    assert build_duration_dataset_sync(session) == []


# ─── phase-key normalisation ──────────────────────────────────────────────

def test_normalise_phase_key_keeps_numeric_ids():
    assert _normalise_phase_key("36") == "36"
    assert _normalise_phase_key(" 9 ") == "9"
    assert _normalise_phase_key("Laminagem") == "laminagem"
    assert _normalise_phase_key(None) == ""


# ─── async wrappers (the builders are coroutines) ─────────────────────────

def build_quality_risk_dataset_sync(session) -> list[dict[str, Any]]:
    import asyncio
    return asyncio.run(build_quality_risk_dataset(session, TENANT))


def build_duration_dataset_sync(session) -> list[dict[str, Any]]:
    import asyncio
    return asyncio.run(build_duration_dataset(session, TENANT))
