"""
Q.67.3.D — Coverage tests for `SemanticQueriesInMemory`.

`SemanticQueriesInMemory` is the in-memory replacement for the old mock
endpoints: it answers the Factory Map's "WIP / bottlenecks / lead time /
quality" queries from the IngestEngine's curated dict, *without* touching
the database.

Strategy
--------
* Build a minimal `_StubEngine` that mimics the surface the service uses
  (`get_active_run()` + `_curated_data`).
* For each public query, exercise:
    - the happy path with curated rows present,
    - the "no active ingestion" path → BLOCKED response,
    - the "active ingestion but specific table missing/empty" path.
* No DB session, no Ollama, no real engine — these are pure unit tests.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import pytest

from src.factory_data_product.services.semantic_queries_inmemory import (
    SemanticQueriesInMemory,
    get_semantic_service,
)


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _StubEngine:
    """Minimal IngestEngine surface for the semantic queries service.

    The service only reads:
      * `engine.get_active_run()` — returns dict or None.
      * `engine._curated_data[str(ingestion_id)]` — dict[table, list[row]].
    """

    def __init__(
        self,
        *,
        active: bool = True,
        curated: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> None:
        self._ingestion_id: UUID = uuid4()
        self._active_run: Optional[Dict[str, Any]] = (
            {
                "active_ingestion_id": self._ingestion_id,
                "activated_at_utc": datetime.now(timezone.utc).isoformat(),
                "activated_by": "test",
            } if active else None
        )
        self._curated_data: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        if curated is not None:
            self._curated_data[str(self._ingestion_id)] = curated

    def get_active_run(self) -> Optional[Dict[str, Any]]:
        return self._active_run


def _service(**engine_kwargs: Any) -> SemanticQueriesInMemory:
    return SemanticQueriesInMemory(_StubEngine(**engine_kwargs))


# ---------------------------------------------------------------------------
# Trust + confidence helpers
# ---------------------------------------------------------------------------


def test_get_trust_status_thresholds():
    """Trust status thresholds: ≥85 OK, ≥50 WARNING, <50 BLOCKED. These
    constants are wired into the Factory Map UI — drifting them silently
    re-classifies every existing dashboard tile."""
    svc = _service()
    assert svc._get_trust_status(95.0) == "OK"
    assert svc._get_trust_status(85.0) == "OK"
    assert svc._get_trust_status(84.9) == "WARNING"
    assert svc._get_trust_status(50.0) == "WARNING"
    assert svc._get_trust_status(49.9) == "BLOCKED"
    assert svc._get_trust_status(0.0) == "BLOCKED"


def test_calculate_confidence_scales_by_coverage_and_sample_size():
    """Confidence = base × coverage_factor × sample_factor. With full
    coverage and a small sample we get a proportional haircut; with full
    coverage and a sample ≥ min we keep the base trust."""
    svc = _service()

    # Full coverage, full sample → equal to base_trust.
    assert svc._calculate_confidence(
        base_trust=80, coverage_pct=100, sample_size=50, min_sample=10,
    ) == 80.0

    # Full coverage, half-of-min sample → 50% sample factor.
    assert svc._calculate_confidence(
        base_trust=80, coverage_pct=100, sample_size=5, min_sample=10,
    ) == 40.0

    # 50% coverage, full sample → halved.
    assert svc._calculate_confidence(
        base_trust=80, coverage_pct=50, sample_size=50, min_sample=10,
    ) == 40.0


def test_empty_response_shape_is_blocked():
    """`_empty_response` is the canonical "no data" shape served by every
    query that can't proceed. The contract: `data` is None, status is
    BLOCKED, `metadata.source` is "no_active_ingestion"."""
    svc = _service(active=False)
    resp = svc._empty_response("anything", "Sem ingestão")
    assert resp["data"] is None
    assert resp["data_confidence"] == 0
    assert resp["trust_status"] == "BLOCKED"
    assert resp["metadata"]["source"] == "no_active_ingestion"
    assert "query_time" in resp["metadata"]


# ---------------------------------------------------------------------------
# get_active_curated → degrades gracefully
# ---------------------------------------------------------------------------


def test_get_active_curated_returns_none_when_no_active_run():
    """No active ingestion → None (every query short-circuits to BLOCKED)."""
    svc = _service(active=False)
    assert svc._get_active_curated() is None


def test_get_active_curated_returns_none_when_no_curated_data():
    """Active run exists but no curated dict was loaded → None."""
    svc = _service(active=True, curated=None)
    assert svc._get_active_curated() is None


# ---------------------------------------------------------------------------
# get_wip — happy path + empty
# ---------------------------------------------------------------------------


def test_get_wip_returns_blocked_when_no_active_ingestion():
    svc = _service(active=False)
    result = svc.get_wip()
    assert result["data"] is None
    assert result["trust_status"] == "BLOCKED"


def test_get_wip_returns_blocked_when_no_orders_in_curated():
    """Active ingestion but `orders=[]` → still BLOCKED (honest empty)."""
    svc = _service(curated={"orders": [], "order_phases": []})
    result = svc.get_wip()
    assert result["data"] is None
    assert "Sem ordens" in result["semantic_label"]


def test_get_wip_counts_open_orders_and_phases_with_hours():
    """One closed order + two open ones; phases attached to the open ones
    contribute to `total_horas_previstas`. The closed order's phases must
    NOT be counted."""
    svc = _service(curated={
        "orders": [
            {"of_id": "OF-1", "data_conclusao": None},
            {"of_id": "OF-2", "data_conclusao": None},
            {"of_id": "OF-3", "data_conclusao": date(2026, 1, 5)},
        ],
        "order_phases": [
            {"of_id": "OF-1", "fase_id": "F1", "horas_finais": 10.0},
            {"of_id": "OF-2", "fase_id": "F2", "horas_finais": 5.5},
            {"of_id": "OF-3", "fase_id": "F1", "horas_finais": 8.0},  # closed
            {"of_id": "OF-1", "fase_id": "F2", "horas_finais": None},
        ],
    })
    result = svc.get_wip()
    assert result["data"] is not None
    data = result["data"]
    assert data["open_orders"] == 2
    assert data["total_orders"] == 3
    # Only the 3 phases tied to OF-1/OF-2 count (3 open phases).
    assert data["open_phases_total"] == 3
    # Two of those have hours > 0; total = 15.5.
    assert data["phases_with_hours"] == 2
    assert data["total_horas_previstas"] == pytest.approx(15.5)
    assert result["trust_status"] in ("OK", "WARNING", "BLOCKED")


# ---------------------------------------------------------------------------
# get_backlog
# ---------------------------------------------------------------------------


def test_get_backlog_blocked_when_no_phases():
    svc = _service(curated={"orders": [{"of_id": "OF-1"}], "order_phases": []})
    result = svc.get_backlog()
    assert result["data"] is None


def test_get_backlog_groups_by_phase_and_skips_non_production():
    """Backlog aggregates `horas_finais` of phases on open orders, grouped
    by `fase_id`. Non-production phases (e.g. "Entregue") must be skipped."""
    svc = _service(curated={
        "orders": [
            {"of_id": "OF-1", "data_conclusao": None},
            {"of_id": "OF-2", "data_conclusao": None},
        ],
        "order_phases": [
            {"of_id": "OF-1", "fase_id": "F1", "fase_nome": "Laminagem",
             "horas_finais": 12.0},
            {"of_id": "OF-2", "fase_id": "F1", "fase_nome": "Laminagem",
             "horas_finais": 8.0},
            {"of_id": "OF-1", "fase_id": "F2", "fase_nome": "Entregue",
             "horas_finais": 5.0},  # excluded (NON_PRODUCTION_PHASES)
            {"of_id": "OF-2", "fase_id": "F3", "fase_nome": "Pintura",
             "horas_finais": 4.0},
        ],
        "phase_capacities": [
            {"fase_id": "F1", "capacidade_horas": 10.0},
        ],
    })
    result = svc.get_backlog(top_n=5)
    assert result["data"] is not None
    fases = result["data"]["backlog_by_phase"]
    by_id = {p["fase_id"]: p for p in fases}
    # "Entregue" must NOT show up.
    assert "F2" not in by_id
    # F1 backlog is 20h, divided by capacity 10 → 2.0 dias teóricos.
    assert by_id["F1"]["backlog_horas"] == pytest.approx(20.0)
    assert by_id["F1"]["backlog_dias_teoricos"] == pytest.approx(2.0)
    # F3 had no capacity in the map → falls back to WORKING_HOURS_PER_DAY.
    assert by_id["F3"]["backlog_horas"] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# get_bottlenecks
# ---------------------------------------------------------------------------


def test_get_bottlenecks_severity_classification():
    """`get_bottlenecks` reuses `get_backlog`; the severity thresholds are
    CRITICAL >5, HIGH >3, MEDIUM >1, OK ≤1 days."""
    # Build a single very-overloaded phase (CRITICAL) — capacity 1h, 100h
    # backlog → 100 days.
    svc = _service(curated={
        "orders": [{"of_id": "OF-1", "data_conclusao": None}],
        "order_phases": [
            {"of_id": "OF-1", "fase_id": "F1", "fase_nome": "Laminagem",
             "horas_finais": 100.0},
        ],
        "phase_capacities": [{"fase_id": "F1", "capacidade_horas": 1.0}],
    })
    result = svc.get_bottlenecks(top_n=5)
    assert result["data"] is not None
    items = result["data"]["bottlenecks"]
    assert len(items) == 1
    top = items[0]
    assert top["severity"] == "CRITICAL"
    assert top["is_critical"] is True
    assert top["rank"] == 1
    assert result["data"]["critical_count"] == 1


def test_get_bottlenecks_blocked_when_backlog_empty():
    """If `get_backlog` blocks (no phases) the bottleneck endpoint must
    also block — never return stale or empty success."""
    svc = _service(curated={"orders": [{"of_id": "OF-1"}], "order_phases": []})
    result = svc.get_bottlenecks()
    assert result["data"] is None


# ---------------------------------------------------------------------------
# get_skills_risk
# ---------------------------------------------------------------------------


def test_get_skills_risk_flags_spof_and_high():
    """Risk classification: ≤1 apto = CRITICAL (SPOF); <min_capable = HIGH;
    <min_capable+2 = MEDIUM; else OK. Only production phases (from
    `phase_capacities`) count."""
    svc = _service(curated={
        "skill_matrix": [
            {"funcionario_id": "E1", "fase_id": "F1",
             "fase_nome": "Laminagem", "apto": True},
            # F2 has nobody apto → CRITICAL.
            # F3 has one apto → CRITICAL (SPOF).
            {"funcionario_id": "E2", "fase_id": "F3",
             "fase_nome": "Acabamento", "apto": True},
            # F4 has 5 apto → OK (>= min_capable + 2 = 5).
            {"funcionario_id": "E3", "fase_id": "F4",
             "fase_nome": "Pintura", "apto": True},
            {"funcionario_id": "E4", "fase_id": "F4",
             "fase_nome": "Pintura", "apto": True},
            {"funcionario_id": "E5", "fase_id": "F4",
             "fase_nome": "Pintura", "apto": True},
            {"funcionario_id": "E6", "fase_id": "F4",
             "fase_nome": "Pintura", "apto": True},
            {"funcionario_id": "E7", "fase_id": "F4",
             "fase_nome": "Pintura", "apto": True},
        ],
        "phase_capacities": [
            {"fase_id": "F1", "fase_nome": "Laminagem"},
            {"fase_id": "F2", "fase_nome": "Cura"},
            {"fase_id": "F3", "fase_nome": "Acabamento"},
            {"fase_id": "F4", "fase_nome": "Pintura"},
            # Non-production phase — excluded from analysis.
            {"fase_id": "F5", "fase_nome": "Entregue"},
        ],
    })
    result = svc.get_skills_risk(min_capable=3)
    assert result["data"] is not None
    by_fase = {p["fase_id"]: p for p in result["data"]["at_risk_phases"]}
    # F1 and F3 have 1 apto → CRITICAL/SPOF.
    assert "F1" in by_fase and by_fase["F1"]["is_spof"]
    assert "F3" in by_fase and by_fase["F3"]["is_spof"]
    # F2 (0 apto) → CRITICAL.
    assert "F2" in by_fase
    assert by_fase["F2"]["risk_level"] == "CRITICAL"
    # F4 has 4 apto (>= min+2) → OK; absent from at_risk list.
    assert "F4" not in by_fase
    # F5 was non-production — must NOT be analysed.
    assert "F5" not in by_fase


def test_get_skills_risk_blocked_when_no_skills():
    svc = _service(curated={"skill_matrix": [], "phase_capacities": []})
    result = svc.get_skills_risk()
    assert result["data"] is None
    assert result["trust_status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# get_quality
# ---------------------------------------------------------------------------


def test_get_quality_returns_zero_errors_with_ok_status_when_empty():
    """`quality_events=[]` is an OK state (no errors recorded), not
    BLOCKED. The semantic label still flags the analysis intent."""
    svc = _service(curated={"quality_events": []})
    result = svc.get_quality()
    assert result["data"]["total_errors"] == 0
    assert result["trust_status"] == "OK"


def test_get_quality_groups_and_sorts_top_items():
    """Top items are sorted by `count` descending and reflect the
    `pct_of_total` correctly."""
    svc = _service(curated={
        "quality_events": [
            {"erro_tipo": "DENT", "fase_id": "F1", "quantidade": 2},
            {"erro_tipo": "DENT", "fase_id": "F1", "quantidade": 1},
            {"erro_tipo": "SCRATCH", "fase_id": "F2", "quantidade": 1},
            {"erro_tipo": "DENT", "fase_id": None, "quantidade": 1},  # no fase
        ],
    })
    result = svc.get_quality(top_errors=5, group_by="error")
    data = result["data"]
    assert data["total_errors"] == 4
    assert data["unique_error_types"] == 2
    top = data["top_items"][0]
    assert top["key"] == "DENT"
    assert top["count"] == 3
    # 3 of 4 errors → 75.0%.
    assert top["pct_of_total"] == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# get_lead_time
# ---------------------------------------------------------------------------


def test_get_lead_time_blocked_without_completed_orders():
    """Open-only orders → no valid lead times → BLOCKED."""
    svc = _service(curated={
        "orders": [
            {"of_id": "OF-1", "data_entrada": date(2026, 1, 1),
             "data_conclusao": None},
        ],
    })
    result = svc.get_lead_time()
    assert result["data"] is None
    assert "Sem ordens concluídas" in result["semantic_label"]


def test_get_lead_time_calculates_stats_for_completed_orders():
    """Closed orders with both entry+completion → percentile + distribution."""
    svc = _service(curated={
        "orders": [
            {"of_id": "OF-1", "data_entrada": date(2026, 1, 1),
             "data_conclusao": date(2026, 1, 8)},   # 7 days
            {"of_id": "OF-2", "data_entrada": date(2026, 1, 1),
             "data_conclusao": date(2026, 1, 15)},  # 14 days
            {"of_id": "OF-3", "data_entrada": "2026-01-01",
             "data_conclusao": "2026-03-01"},       # 59 days (str → parsed)
        ],
    })
    result = svc.get_lead_time()
    data = result["data"]
    assert data["total_completed_orders"] == 3
    assert data["min_lead_time_days"] == 7
    assert data["max_lead_time_days"] == 59
    # Distribution buckets: 7-14 holds OF-1 (lt=7); 14-30 holds OF-2;
    # 30-60 holds OF-3.
    assert data["distribution"]["7-14 dias"] == 1
    assert data["distribution"]["14-30 dias"] == 1
    assert data["distribution"]["30-60 dias"] == 1


def test_get_lead_time_skips_orders_with_inverted_dates():
    """If `data_conclusao < data_entrada` (corrupt source), the negative
    lead time is dropped silently — better than producing a -7d row."""
    svc = _service(curated={
        "orders": [
            {"of_id": "OF-1", "data_entrada": date(2026, 1, 10),
             "data_conclusao": date(2026, 1, 8)},  # negative
            {"of_id": "OF-2", "data_entrada": date(2026, 1, 1),
             "data_conclusao": date(2026, 1, 8)},  # OK 7 days
        ],
    })
    result = svc.get_lead_time()
    data = result["data"]
    assert data["total_completed_orders"] == 1
    assert data["min_lead_time_days"] == 7


# ---------------------------------------------------------------------------
# get_mold_conflicts
# ---------------------------------------------------------------------------


def test_get_mold_conflicts_flags_concurrent_open_uses():
    """A mold used on >1 phase whose `data_fim` is None is a conflict
    candidate. Single-use molds and closed phases are NOT conflicts."""
    svc = _service(curated={
        "order_phases": [
            # Conflict: mold M1 open on two orders.
            {"of_id": "OF-1", "molde_id": "M1",
             "data_inicio": date(2026, 1, 1), "data_fim": None},
            {"of_id": "OF-2", "molde_id": "M1",
             "data_inicio": date(2026, 1, 2), "data_fim": None},
            # Not a conflict — M2 only open in one phase.
            {"of_id": "OF-3", "molde_id": "M2",
             "data_inicio": date(2026, 1, 3), "data_fim": None},
            # Not counted: closed phase (has data_fim).
            {"of_id": "OF-4", "molde_id": "M3",
             "data_inicio": date(2026, 1, 4), "data_fim": date(2026, 1, 5)},
            # No molde — ignored.
            {"of_id": "OF-5", "molde_id": None,
             "data_inicio": date(2026, 1, 5)},
        ],
    })
    result = svc.get_mold_conflicts()
    data = result["data"]
    assert data["total_conflicts"] == 1
    assert data["conflicts"][0]["molde_id"] == "M1"
    assert data["conflicts"][0]["concurrent_uses"] == 2


# ---------------------------------------------------------------------------
# get_overview + factory function
# ---------------------------------------------------------------------------


def test_get_overview_summarises_each_curated_table():
    """`get_overview` reports `{count, sample}` per table — used by the
    admin/diagnostics page that confirms what was ingested."""
    svc = _service(curated={
        "orders": [{"of_id": "OF-1"}, {"of_id": "OF-2"}],
        "order_phases": [{"of_id": "OF-1", "fase_id": "F1"}],
    })
    result = svc.get_overview()
    tables = result["data"]["tables"]
    assert tables["orders"]["count"] == 2
    assert tables["order_phases"]["count"] == 1
    # `sample` capped at 3.
    assert len(tables["orders"]["sample"]) == 2
    assert result["trust_status"] == "OK"
    assert result["data_confidence"] == 100


def test_get_overview_blocked_without_active_ingestion():
    svc = _service(active=False)
    result = svc.get_overview()
    assert result["data"] is None
    assert result["trust_status"] == "BLOCKED"


def test_get_semantic_service_returns_singleton_per_engine():
    """`get_semantic_service` caches the instance per-engine — calling it
    again with the same engine returns the same object; a different engine
    yields a fresh service."""
    # Reset the module-level singleton so this test is independent.
    import src.factory_data_product.services.semantic_queries_inmemory as mod
    mod._service_instance = None

    engine_a = _StubEngine()
    svc_1 = get_semantic_service(engine_a)
    svc_2 = get_semantic_service(engine_a)
    assert svc_1 is svc_2  # cached per-engine

    engine_b = _StubEngine()
    svc_3 = get_semantic_service(engine_b)
    assert svc_3 is not svc_1  # different engine, fresh instance
