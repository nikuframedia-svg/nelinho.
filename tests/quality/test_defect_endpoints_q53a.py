"""
Q.53.A — Qualidade page endpoints: defect-zones, roi-actions, defect-risk.

The services run real SQL, so these tests cover the pure decision logic
(zone derivation, risk banding, ROI arithmetic) and drive the aggregation
through a scripted session that returns prepared rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from src.quality.services.defect_zone_service import (
    HULL_ZONES,
    DefectZoneService,
    derive_zone,
)
from src.quality.services.defect_risk_service import _risk_band
from src.quality.services.roi_service import (
    DEFAULT_ACTION_COST_EUR,
    LABOUR_RATE_EUR_PER_HOUR,
    ROIService,
)

TENANT = UUID("11111111-1111-1111-1111-111111111111")
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
NOW = datetime.now(timezone.utc)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _ScriptedSession:
    def __init__(self, results):
        self._results = results
        self.calls = 0

    async def execute(self, _stmt, _params=None):
        rows = self._results[self.calls]
        self.calls += 1
        return _Result(rows)


# ─── derive_zone ──────────────────────────────────────────────────────────

def test_derive_zone_from_error_code_prefix():
    assert derive_zone("laminagem-deslaminado", None) == "casco"
    assert derive_zone("interior-enrugado", None) == "casco"
    assert derive_zone("pintura-com-cor-errada", None) == "acabamento"
    assert derive_zone("molde-partido", None) == "molde"
    assert derive_zone("danos-transporte", None) == "conves"
    assert derive_zone("falta-acessorio", None) == "montagem"


def test_derive_zone_falls_back_to_phase_name():
    assert derive_zone("RETURN", "Laminagem") == "casco"
    assert derive_zone("RETURN", "Desmolde") == "conves"
    assert derive_zone("RETURN", "Pintura Acabamento") == "acabamento"


def test_derive_zone_unknown_is_outro():
    assert derive_zone("xyz", None) == "outro"
    assert derive_zone(None, None) == "outro"


# ─── _risk_band ───────────────────────────────────────────────────────────

def test_risk_band_thresholds():
    assert _risk_band(0.95) == "alto"
    assert _risk_band(0.40) == "alto"
    assert _risk_band(0.39) == "medio"
    assert _risk_band(0.20) == "medio"
    assert _risk_band(0.19) == "baixo"
    assert _risk_band(0.0) == "baixo"


# ─── DefectZoneService ────────────────────────────────────────────────────

async def test_defect_zones_returns_every_hull_zone():
    """Even with only two zones present in the data, the response must
    carry all canonical zones so the SVG renders the full hull."""
    # (location_zone, error_code, context, cost, hours)
    rows = [
        ("casco", "laminagem-x", {}, 10.0, 1.0),
        ("casco", "laminagem-y", {}, 20.0, 2.0),
        ("acabamento", "pintura-z", {}, 5.0, 0.5),
    ]
    session = _ScriptedSession([rows])
    svc = DefectZoneService(session, TENANT)
    out = await svc.zones(since=T0, until=NOW)

    assert {z["zone"] for z in out["zones"]} == set(HULL_ZONES)
    assert out["total_events"] == 3
    casco = next(z for z in out["zones"] if z["zone"] == "casco")
    assert casco["events"] == 2
    assert casco["cost_eur"] == 30.0
    cockpit = next(z for z in out["zones"] if z["zone"] == "cockpit")
    assert cockpit["events"] == 0  # clean zone still present


async def test_defect_zones_derives_zone_when_column_null():
    """A legacy row with location_zone=None must still land on a zone via
    derive_zone (here: error_code 'pintura-*' → acabamento)."""
    rows = [(None, "pintura-fios", {"phase_name": "Pintura"}, 0.0, 0.0)]
    session = _ScriptedSession([rows])
    out = await DefectZoneService(session, TENANT).zones(since=T0, until=NOW)

    acab = next(z for z in out["zones"] if z["zone"] == "acabamento")
    assert acab["events"] == 1


# ─── ROIService ───────────────────────────────────────────────────────────

async def test_roi_actions_computes_net_and_ratio():
    # rework aggregate: (error_code, events, cost_sum, hours_sum, resolved_hours)
    rework_rows = [
        ("laminagem-deslaminado", 10, 0.0, 20.0, 8.0),
    ]
    catalog_rows = []  # no catalog hint → action cost = reaction effort
    session = _ScriptedSession([rework_rows, catalog_rows])
    out = await ROIService(session, TENANT).roi_by_action(since=T0, until=NOW)

    action = out["actions"][0]
    # saved = 0 explicit + 20h × rate
    assert action["saved_eur"] == round(20.0 * LABOUR_RATE_EUR_PER_HOUR, 2)
    # invested = 8 resolved hours × rate (no catalog hint)
    assert action["invested_eur"] == round(8.0 * LABOUR_RATE_EUR_PER_HOUR, 2)
    assert action["action_basis"] == "reaction_effort"
    assert action["net_eur"] == round(
        action["saved_eur"] - action["invested_eur"], 2
    )
    assert action["roi_ratio"] == round(
        action["saved_eur"] / action["invested_eur"], 2
    )


async def test_roi_actions_uses_fixed_cost_when_catalog_hint_present():
    rework_rows = [("pintura-fios", 5, 100.0, 10.0, 0.0)]
    catalog_rows = [("pintura-fios", "Recalibrar pistola de pintura")]
    session = _ScriptedSession([rework_rows, catalog_rows])
    out = await ROIService(session, TENANT).roi_by_action(since=T0, until=NOW)

    action = out["actions"][0]
    assert action["action_basis"] == "fixed_corrective_action"
    assert action["invested_eur"] == DEFAULT_ACTION_COST_EUR
    assert action["preventive_action_hint"] == "Recalibrar pistola de pintura"


async def test_roi_actions_ranks_by_net_eur():
    # `winner` has explicit cost (saved) but no lost hours → invested 0 →
    # all of saved_eur is net. `effort-only` is pure reaction effort →
    # saved == invested → net 0. Net-€ ranking puts the winner first.
    rework_rows = [
        ("effort-only", 50, 0.0, 100.0, 0.0),
        ("winner", 1, 800.0, 0.0, 0.0),
    ]
    session = _ScriptedSession([rework_rows, []])
    out = await ROIService(session, TENANT).roi_by_action(since=T0, until=NOW)
    assert out["actions"][0]["error_code"] == "winner"


async def test_roi_actions_empty_when_no_rework():
    session = _ScriptedSession([[], []])
    out = await ROIService(session, TENANT).roi_by_action(since=T0, until=NOW)
    assert out["actions"] == []
    assert out["total_saved_eur"] == 0.0


# ─── Q.54.J — ROI fallback to total reaction effort ───────────────────────

async def test_roi_actions_uses_total_hours_when_nothing_resolved():
    """No catalog hint and no *resolved* events: the action cost falls back
    to the cumulative lost-hours of every event of that code, so roi_ratio
    is computed instead of leaking a null. Q.54.J."""
    # (error_code, events, cost_sum, hours_sum, resolved_hours)
    rework_rows = [("BOLHA", 3, 0.0, 6.0, 0.0)]
    catalog_rows = []  # no hint
    session = _ScriptedSession([rework_rows, catalog_rows])
    out = await ROIService(session, TENANT).roi_by_action(since=T0, until=NOW)

    action = out["actions"][0]
    assert action["action_basis"] == "total_reaction_effort"
    # invested = total 6h × rate (nothing resolved → use all hours)
    assert action["invested_eur"] == round(6.0 * LABOUR_RATE_EUR_PER_HOUR, 2)
    assert action["roi_ratio"] == round(
        action["saved_eur"] / action["invested_eur"], 2
    )
    assert action["roi_ratio"] is not None


async def test_roi_ratio_stays_null_when_no_hours_recorded():
    """When a code has no catalog hint and no hours_lost recorded at all,
    there is no honest basis to price prevention — roi_ratio stays None."""
    rework_rows = [("barco-com-lixo", 2, 0.0, 0.0, 0.0)]
    session = _ScriptedSession([rework_rows, []])
    out = await ROIService(session, TENANT).roi_by_action(since=T0, until=NOW)

    action = out["actions"][0]
    assert action["action_basis"] == "total_reaction_effort"
    assert action["invested_eur"] == 0.0
    assert action["roi_ratio"] is None


# ─── Q.54.J — most_frequent_error_code default for diagnostics ────────────

class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def first(self):
        return self._value


async def test_most_frequent_error_code_picks_top_code():
    """The diagnostic endpoints default to the most-frequent defect when no
    error_code is supplied — the tab never opens broken. Q.54.J."""
    from src.quality.services.impact_service import most_frequent_error_code

    class _Session:
        async def execute(self, _stmt, _params=None):
            return _ScalarResult("INTERIOR_ENRUGADO")

    code = await most_frequent_error_code(_Session(), TENANT)
    assert code == "INTERIOR_ENRUGADO"


async def test_most_frequent_error_code_none_when_no_rework():
    """No rework at all → None, so the endpoint can return an honest empty
    payload instead of 422."""
    from src.quality.services.impact_service import most_frequent_error_code

    class _Session:
        async def execute(self, _stmt, _params=None):
            return _ScalarResult(None)

    code = await most_frequent_error_code(_Session(), TENANT)
    assert code is None
