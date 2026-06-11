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
    build_otd_risk_dataset,
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

def test_quality_risk_dataset_labels_reais_por_of_fase_q173aq():
    """Q.173.AQ — o label vem REAL da query (EXISTS contra rework_entry por
    (OF, fase causadora)), não de estratificação sintética. A taxa por fase
    continua como feature."""
    phase_rows = [
        {
            "of_id": f"O{i}",
            "fase_id": "36",  # Laminagem
            "molde_id": "M1",
            "data_inicio": T0 + timedelta(hours=i),
            "product_type": "K1",
            # 3 execuções concretas COM rework registado — label real
            "is_error": i in (2, 5, 7),
        }
        for i in range(100)
    ] + [
        {
            "of_id": f"A{i}",
            "fase_id": "9",  # Armazem — no rework
            "molde_id": None,
            "data_inicio": T0 + timedelta(hours=i),
            "product_type": "K1",
            "is_error": False,
        }
        for i in range(50)
    ]
    rework_rows = [("36", 40)]  # eventos imputados à fase 36 (alimenta a FEATURE)

    session = _ScriptedSession([phase_rows, rework_rows])
    rows = build_quality_risk_dataset_sync(session)

    lam = [r for r in rows if r["fase_id"] == "36"]
    arm = [r for r in rows if r["fase_id"] == "9"]
    assert len(lam) == 100 and len(arm) == 50
    # labels = exatamente as execuções com rework real, não rate × n.
    assert sum(r["is_error"] for r in lam) == 3
    assert sum(r["is_error"] for r in arm) == 0
    # phase_error_rate feature reflects the real per-fase rate.
    assert lam[0]["phase_error_rate"] == pytest.approx(0.40)
    assert arm[0]["phase_error_rate"] == pytest.approx(0.0)


def test_quality_risk_phase_error_rate_clampada_q173aq():
    """A FEATURE phase_error_rate fica clampada a 0.95 mesmo quando o ERP
    tem mais eventos de rework do que execuções (dados sujos); o label de
    cada linha segue o rework real e não é afetado pelo clamp."""
    phase_rows = [
        {"of_id": f"O{i}", "fase_id": "1", "molde_id": None,
         "data_inicio": T0 + timedelta(hours=i), "product_type": "K2",
         "is_error": i == 0}
        for i in range(20)
    ]
    rework_rows = [("1", 500)]  # absurdly high rework count

    session = _ScriptedSession([phase_rows, rework_rows])
    rows = build_quality_risk_dataset_sync(session)

    assert rows[0]["phase_error_rate"] == pytest.approx(0.95)
    assert sum(r["is_error"] for r in rows) == 1  # só a execução com rework real


def test_quality_risk_dataset_empty_when_no_phases():
    session = _ScriptedSession([[], []])
    assert build_quality_risk_dataset_sync(session) == []


def test_quality_risk_dataset_surfaces_real_team_size():
    """Q.156.D (BD-3): o dataset de qualidade também tira team_size de offp_eq."""
    phase_rows = [
        {"of_id": "O1", "fase_id": "36", "molde_id": "M1",
         "data_inicio": T0, "product_type": "K1", "team_size": 2},
        {"of_id": "O2", "fase_id": "36", "molde_id": None,
         "data_inicio": T0 + timedelta(hours=1), "product_type": "K1",
         "team_size": 1},
    ]
    rework_rows: list[Any] = []
    rows = build_quality_risk_dataset_sync(_ScriptedSession([phase_rows, rework_rows]))
    assert sorted(r["team_size"] for r in rows) == [1, 2]


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


def test_duration_dataset_surfaces_real_team_size():
    """Q.156.D (BD-3): team_size vem de offp_eq (não hardcoded=1). A LEFT JOIN
    devolve a coluna por linha; o builder tem de a propagar (COALESCE → 1)."""
    phase_rows = [
        {"of_id": "O1", "fase_id": "36", "fase_nome": "Laminagem",
         "molde_id": "M1", "horas_reais": 7.5,
         "data_inicio": T0, "product_type": "K1", "team_size": 3},
        {"of_id": "O2", "fase_id": "40", "fase_nome": "Cura",
         "molde_id": None, "horas_reais": 4.0,
         "data_inicio": T0 + timedelta(hours=1), "product_type": "K2",
         "team_size": 1},
    ]
    rows = build_duration_dataset_sync(_ScriptedSession([phase_rows]))
    assert [r["team_size"] for r in rows] == [3, 1]
    assert any(r["team_size"] != 1 for r in rows)  # BD-3: não é tudo 1


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


# ─── OTD-risk dataset (Sprint Q.54.F) ─────────────────────────────────────

def _otd_session(order_rows, phase_rows, rework_rows) -> _ScriptedSession:
    """build_otd_risk_dataset executes 3 queries in order:
    order_sql (.mappings), phase_sql (.mappings), rework_sql (.all)."""
    return _ScriptedSession([order_rows, phase_rows, rework_rows])


def test_otd_risk_dataset_labels_late_orders():
    """An order whose completed_date is after its transport_date must be
    labelled is_late=1 with negative slack; an on-time one is_late=0."""
    from datetime import date

    order_rows = [
        # O1 — finished 3 days late
        {"legacy_id": 1, "product_type": "K1",
         "completed_date": date(2026, 5, 10),
         "transport_date": date(2026, 5, 7)},
        # O2 — finished 5 days early
        {"legacy_id": 2, "product_type": "K2",
         "completed_date": date(2026, 5, 2),
         "transport_date": date(2026, 5, 7)},
    ]
    phase_rows = [
        {"of_id": "1", "fase_id": "36", "horas_reais": 8.0},
        {"of_id": "1", "fase_id": "40", "horas_reais": 3.0},
        {"of_id": "2", "fase_id": "36", "horas_reais": 7.5},
    ]
    rework_rows: list[Any] = []

    rows = __import__("asyncio").run(
        build_otd_risk_dataset(
            _otd_session(order_rows, phase_rows, rework_rows), TENANT,
        )
    )
    assert len(rows) == 2
    o1 = next(r for r in rows if r["modelo_id"] == "K1")
    o2 = next(r for r in rows if r["modelo_id"] == "K2")
    assert o1["is_late"] == 1
    assert o1["slack_days"] == -3.0
    assert o1["n_phases"] == 2
    assert o1["total_planned_hours"] == 11.0
    assert o2["is_late"] == 0
    assert o2["slack_days"] == 5.0


def test_otd_risk_dataset_empty_when_no_completed_orders():
    rows = __import__("asyncio").run(
        build_otd_risk_dataset(_otd_session([], [], []), TENANT)
    )
    assert rows == []


def test_otd_risk_dataset_folds_in_phase_error_rate():
    """The per-fase rework rate is averaged into phase_error_rate_mean."""
    from datetime import date

    order_rows = [
        {"legacy_id": 1, "product_type": "K1",
         "completed_date": date(2026, 5, 10),
         "transport_date": date(2026, 5, 7)},
    ]
    # fase 36 appears 10× with 4 rework events → rate 0.4
    phase_rows = [{"of_id": "1", "fase_id": "36", "horas_reais": 5.0}]
    phase_rows += [
        {"of_id": f"X{i}", "fase_id": "36", "horas_reais": 5.0}
        for i in range(9)
    ]
    rework_rows = [("36", 4)]

    rows = __import__("asyncio").run(
        build_otd_risk_dataset(
            _otd_session(order_rows, phase_rows, rework_rows), TENANT,
        )
    )
    assert len(rows) == 1
    assert rows[0]["phase_error_rate_mean"] == pytest.approx(0.4, abs=0.001)
