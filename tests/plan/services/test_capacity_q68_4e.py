"""Q.68.4.E — `src/plan/services/capacity_service.py` a 27%. A
`CapacityAnalysis` dataclass + `analyze_capacity()` + `get_machine_availability()`
+ `phase_capacity_summary()` ficaram sem testes. O CEO dashboard usa o
output deste service; um silent bias no `utilization_percent` põe a
fábrica a parecer saudável quando está em 110%.

Testes:

* `CapacityAnalysis.utilization_percent` — clamp a 100 quando overshoot.
* `CapacityAnalysis.is_over_capacity` / `severity` — bands critical/warning/normal.
* `CapacityAnalysis.to_dict()` shape — chaves obrigatórias.
* `analyze_capacity()` smoke — devolve summary + machine_analysis.
* `analyze_capacity()` detecta constraint quando allocated > available.
* `get_machine_availability()` — daily breakdown.
* `phase_capacity_summary()` — agrupa por fase.

`publish_event` é mocked. SQL stub via session custom (não FakeSession
queue) porque `analyze_capacity` faz uma execute por (machine × period).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from src.plan.services import capacity_service as cap_mod
from src.plan.services.capacity_service import (
    CapacityAnalysis,
    CapacityService,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ─── Helpers ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _silence_kafka(monkeypatch: pytest.MonkeyPatch):
    async def _ok(*_a, **_kw):
        return True

    monkeypatch.setattr(cap_mod, "publish_event", _ok)


class _ScalarSession:
    """Session que devolve um único valor por scalar() — usado para
    simular o `SUM(scheduled_duration_hours)` query."""

    def __init__(self, scalar_value):
        self._value = scalar_value
        self.executes = 0

    async def execute(self, _stmt, *_a, **_kw):
        self.executes += 1

        class _R:
            def scalar(self_inner):
                return self._value

            def scalars(self_inner):
                class _S:
                    def all(self_innermost):
                        return []

                return _S()

        return _R()


class _SequencedSession:
    """Devolve uma sequência de valores escalares por execute."""

    def __init__(self, values):
        self._values = list(values)

    async def execute(self, _stmt, *_a, **_kw):
        v = self._values.pop(0) if self._values else None

        class _R:
            def scalar(self_inner):
                return v

            def scalars(self_inner):
                class _S:
                    def all(self_innermost):
                        return v if isinstance(v, list) else []

                return _S()

            def all(self_inner):
                return v if isinstance(v, list) else []

        return _R()


# ─── CapacityAnalysis dataclass ───────────────────────────────────────────


def test_capacity_analysis_utilization_percent_clamped_to_100():
    """Sobrecarga real (allocated>available) tem que mostrar 100% no UI,
    nunca >100 — o badge "critical" já comunica o overshoot."""
    a = CapacityAnalysis(
        machine_id=uuid4(),
        machine_name="LAM-1",
        period=date.today(),
        available_minutes=600,
        allocated_minutes=900,  # 150% overshoot
    )
    assert a.utilization_percent == 100
    assert a.is_over_capacity is True
    assert a.severity == "critical"


def test_capacity_analysis_normal_severity_under_90():
    a = CapacityAnalysis(
        machine_id=uuid4(),
        machine_name="LAM-2",
        period=date.today(),
        available_minutes=600,
        allocated_minutes=300,  # 50%
    )
    assert a.utilization_percent == 50
    assert a.is_over_capacity is False
    assert a.severity == "normal"
    assert a.free_minutes == 300


def test_capacity_analysis_warning_severity_in_90_99_window():
    a = CapacityAnalysis(
        machine_id=uuid4(),
        machine_name="LAM-3",
        period=date.today(),
        available_minutes=600,
        allocated_minutes=550,  # 91.66%
    )
    assert 90 <= a.utilization_percent < 100
    assert a.severity == "warning"


def test_capacity_analysis_zero_available_handles_division():
    """`available_minutes=0` deve dar 0% (não ZeroDivisionError)."""
    a = CapacityAnalysis(
        machine_id=uuid4(),
        machine_name="DOWN-1",
        period=date.today(),
        available_minutes=0,
        allocated_minutes=10,
    )
    assert a.utilization_percent == 0
    assert a.free_minutes == 0


def test_capacity_analysis_to_dict_has_required_keys():
    a = CapacityAnalysis(
        machine_id=uuid4(),
        machine_name="M",
        period=date(2026, 5, 1),
        available_minutes=480,
        allocated_minutes=400,
    )
    d = a.to_dict()
    required = {
        "machine_id", "machine_name", "period",
        "available_minutes", "allocated_minutes",
        "utilization_percent", "free_minutes",
        "is_over_capacity", "severity",
    }
    assert required <= set(d)
    assert d["period"] == "2026-05-01"


# ─── analyze_capacity ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_capacity_summary_shape():
    """Smoke — single machine, single period, allocated < available."""
    sess = _ScalarSession(Decimal("4"))  # 4 horas alocadas
    svc = CapacityService(session=sess, tenant_id=TENANT)
    today = date.today()
    out = await svc.analyze_capacity(
        machines=[
            {"machine_id": uuid4(), "machine_name": "LAM-1", "available_hours_per_day": 8},
        ],
        from_date=today,
        to_date=today + timedelta(days=7),
        period_days=7,
    )
    assert out["status"] == "completed"
    assert out["machines_analyzed"] == 1
    assert out["periods_analyzed"] == 1
    assert "summary" in out
    assert out["summary"]["over_capacity_periods"] == 0
    assert len(out["machine_analysis"]) == 1


@pytest.mark.asyncio
async def test_analyze_capacity_detects_overcapacity_and_warns():
    """allocated >> available → 1 warning + 1 over_capacity_period."""
    # Para period_days=7 com 5 working-days: 8h * 60 * 5 = 2400 min available.
    # 50 horas = 3000 min allocated → over capacity.
    sess = _ScalarSession(Decimal("50"))
    svc = CapacityService(session=sess, tenant_id=TENANT)
    out = await svc.analyze_capacity(
        machines=[
            {"machine_id": uuid4(), "machine_name": "OVERLOADED",
             "available_hours_per_day": 8},
        ],
        from_date=date.today(),
        to_date=date.today() + timedelta(days=7),
        period_days=7,
    )
    assert out["summary"]["over_capacity_periods"] >= 1
    assert len(out["warnings"]) >= 1
    assert "OVERLOADED" in out["warnings"][0]


@pytest.mark.asyncio
async def test_analyze_capacity_handles_string_machine_id():
    """`machine_id` aceita string ou UUID."""
    sess = _ScalarSession(Decimal("0"))
    svc = CapacityService(session=sess, tenant_id=TENANT)
    out = await svc.analyze_capacity(
        machines=[
            {"machine_id": str(uuid4()), "machine_name": "STR", "available_hours_per_day": 8},
        ],
        from_date=date.today(),
        to_date=date.today() + timedelta(days=3),
        period_days=3,
    )
    assert out["machines_analyzed"] == 1


# ─── get_machine_availability ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_machine_availability_builds_daily_breakdown():
    """Devolve uma linha por dia do range com available/allocated/free."""
    # Stub — sem schedules.
    sess = _SequencedSession([[]])
    svc = CapacityService(session=sess, tenant_id=TENANT)
    out = await svc.get_machine_availability(
        machine_id=uuid4(),
        from_date=date.today(),
        to_date=date.today() + timedelta(days=2),
        available_hours_per_day=8.0,
    )
    assert out["machine_id"]
    assert "summary" in out
    assert "availability" in out
    # 3 dias no range (today, today+1, today+2).
    assert len(out["availability"]) == 3
    for d in out["availability"]:
        assert d["available_minutes"] == 480  # 8 * 60
        assert d["allocated_minutes"] == 0
        assert d["free_minutes"] == 480


# ─── phase_capacity_summary ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_phase_capacity_summary_returns_rows_per_phase():
    """Devolve uma linha por fase do snapshot ERP."""
    rows = [
        (1, "Laminagem", "DIA", Decimal("80.0"), 10),
        (2, "Pintura", "DIA", Decimal("60.0"), 8),
        (3, "Montagem", "DIA", None, 5),  # capacidade None
    ]
    sess = _SequencedSession([rows])
    svc = CapacityService(session=sess, tenant_id=TENANT)
    out = await svc.phase_capacity_summary()
    assert len(out) == 3
    assert out[0]["fase_id"] == 1
    assert out[0]["capacidade_horas"] == 80.0
    assert out[2]["capacidade_horas"] is None
