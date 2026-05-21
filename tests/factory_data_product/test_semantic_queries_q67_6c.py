"""Q.67.6.C — Coverage for ``factory_data_product.semantic.queries``.

The existing `test_lead_time_query.py` walks two scenarios on
``lead_time_analysis``. Every other method on ``SemanticQueries`` was dark:

* ``_get_active_ingestion_id`` — both branches (explicit injection vs DB
  lookup of the latest ``ActiveRun``).
* The "no active ingestion" early-return on every public method, which
  funnels through ``_no_data_response`` (BLOCKED status, ``data=None``).
* ``backlog_by_phase`` — typical multi-row aggregation, including coverage
  math and the ``backlog_dias_teoricos`` rounding.
* ``bottlenecks`` — delegates to backlog_by_phase + builds the ranking
  with ``is_critical`` (>5 dias).
* ``quality_analysis``, ``mold_conflicts`` — both currently return
  hard-coded placeholders gated on having an active ingestion; we pin
  the response shape so the API contract is locked.
* ``skills_risk`` — bucket breakdown across CRITICAL / HIGH / MEDIUM / OK.
* Pure helpers: ``_calculate_confidence`` (coverage / sample-size factors)
  and ``_get_trust_status`` (BLOCKED / WARNING / OK thresholds).
* Static helpers ``is_metric_blocked`` and ``get_allowed_metrics``.

We use ``AsyncMock`` for the DB plus tiny ``_Result`` stubs that match the
SQLAlchemy surface the queries actually call (``.one()`` / ``.all()`` /
``.scalar_one_or_none()``) — same pattern as ``test_lead_time_query.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.factory_data_product.semantic.queries import SemanticQueries


# ---------------------------------------------------------------------------
# Helpers: result stubs that match the SQLAlchemy surface
# ---------------------------------------------------------------------------


class _RowResult:
    """Result of ``.execute(...)``: ``.one()`` returns a single row tuple/ns."""

    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row

    def scalar(self):
        return self._row

    def scalar_one_or_none(self):
        return self._row


class _RowsResult:
    """Result of ``.execute(...)``: ``.all()`` returns a list of rows."""

    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)

    def scalar_one_or_none(self):  # pragma: no cover — defensive
        return self._rows[0] if self._rows else None


def _async_db_returning(*results):
    """Build an AsyncMock whose successive ``.execute`` calls return each
    stub result in order."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=list(results))
    return db


# ---------------------------------------------------------------------------
# Pure helpers — confidence / trust status
# ---------------------------------------------------------------------------


def test_calculate_confidence_multiplies_trust_coverage_and_sample() -> None:
    sq = SemanticQueries(db=AsyncMock(), ingestion_id=uuid4())
    # base_trust=80, coverage=50%, sample=20 (above min) → 80 * 0.5 * 1.0 = 40
    assert sq._calculate_confidence(80, 50.0, 20) == 40.0


def test_calculate_confidence_penalises_tiny_samples() -> None:
    sq = SemanticQueries(db=AsyncMock(), ingestion_id=uuid4())
    # sample_size=5, min_sample=10 → factor 0.5 ⇒ 80 * 1.0 * 0.5 = 40
    assert sq._calculate_confidence(80, 100.0, 5) == 40.0


def test_calculate_confidence_clamps_coverage_above_100() -> None:
    sq = SemanticQueries(db=AsyncMock(), ingestion_id=uuid4())
    # coverage=150% must be clamped to 1.0
    assert sq._calculate_confidence(80, 150.0, 100) == 80.0


def test_get_trust_status_returns_each_bucket() -> None:
    sq = SemanticQueries(db=AsyncMock(), ingestion_id=uuid4())
    assert sq._get_trust_status(40) == "BLOCKED"  # <50%
    assert sq._get_trust_status(65) == "WARNING"  # 50%–70%
    assert sq._get_trust_status(85) == "OK"       # ≥70%


# ---------------------------------------------------------------------------
# _get_active_ingestion_id — explicit ID vs DB lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_ingestion_id_returns_constructor_id_when_set() -> None:
    """If an ID is injected in the constructor, no DB lookup happens."""
    db = AsyncMock()
    explicit = uuid4()
    sq = SemanticQueries(db=db, ingestion_id=explicit)
    got = await sq._get_active_ingestion_id()
    assert got == explicit
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_active_ingestion_id_falls_back_to_db_lookup() -> None:
    """No constructor id ⇒ we query ActiveRun for the latest activated one."""
    found = uuid4()
    db = _async_db_returning(_RowResult(found))
    sq = SemanticQueries(db=db, ingestion_id=None)
    got = await sq._get_active_ingestion_id()
    assert got == found


@pytest.mark.asyncio
async def test_get_active_ingestion_id_returns_none_when_no_active_run() -> None:
    """An empty ActiveRun table ⇒ ``None``; the public methods then return
    ``_no_data_response``."""
    db = _async_db_returning(_RowResult(None))
    sq = SemanticQueries(db=db, ingestion_id=None)
    got = await sq._get_active_ingestion_id()
    assert got is None


# ---------------------------------------------------------------------------
# _no_data_response — central shape for "no active ingestion" branches
# ---------------------------------------------------------------------------


def test_no_data_response_shape() -> None:
    sq = SemanticQueries(db=AsyncMock(), ingestion_id=uuid4())
    out = sq._no_data_response("backlog", "No active ingestion")
    assert out["data"] is None
    assert out["data_confidence"] == 0
    assert out["trust_status"] == "BLOCKED"
    assert "backlog" in out["semantic_label"]
    assert out["metadata"]["error"] == "No active ingestion"


# ---------------------------------------------------------------------------
# Every public method short-circuits to _no_data_response with no active run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_methods_return_no_data_when_no_active_ingestion() -> None:
    """Each query first calls ``_get_active_ingestion_id`` → ``None`` ⇒
    ``_no_data_response``. Walking the no-data branch on every method
    pins the contract: methods *never* raise on a cold tenant."""
    methods_returning_no_data = [
        # (method name, kwargs)
        ("wip", {}),
        ("backlog_by_phase", {"top_n": 5}),
        ("bottlenecks", {"top_n": 5}),
        ("quality_analysis", {"top_errors": 5, "group_by": "error"}),
        ("mold_conflicts", {}),
        ("skills_risk", {"min_capable": 2}),
        ("lead_time_analysis", {"days_back": 30}),
    ]

    for name, kwargs in methods_returning_no_data:
        # Each method calls _get_active_ingestion_id ⇒ 1 execute() returning
        # None. ``bottlenecks`` delegates to ``backlog_by_phase`` which has
        # its own _get_active_ingestion_id call ⇒ also returns no-data.
        db = _async_db_returning(_RowResult(None), _RowResult(None))
        sq = SemanticQueries(db=db, ingestion_id=None)
        method = getattr(sq, name)
        out = await method(**kwargs)
        assert out["trust_status"] == "BLOCKED", f"{name} should be BLOCKED"
        assert out["data"] is None, f"{name} should have data=None"


# ---------------------------------------------------------------------------
# backlog_by_phase — aggregate rows + coverage math
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backlog_by_phase_aggregates_rows_with_hours_and_coverage() -> None:
    """When the curated layer returns rows, the response includes the
    per-phase backlog and overall totals; ``backlog_dias_teoricos`` is
    backlog_horas / 8 (WORKING_HOURS_PER_DAY)."""
    rows = [
        SimpleNamespace(
            fase_id="phase-A",
            fase_nome="Laminagem",
            fases_abertas=10,
            backlog_horas=80.0,
            fases_com_horas=10,
        ),
        SimpleNamespace(
            fase_id="phase-B",
            fase_nome="Acabamento",
            fases_abertas=5,
            backlog_horas=20.0,
            fases_com_horas=4,
        ),
    ]
    db = _async_db_returning(_RowsResult(rows))
    sq = SemanticQueries(db=db, ingestion_id=uuid4())

    out = await sq.backlog_by_phase(top_n=10)

    assert out["data"]["total_phases_analyzed"] == 15
    assert out["data"]["total_backlog_horas"] == 100.0
    assert len(out["data"]["backlog_by_phase"]) == 2
    first = out["data"]["backlog_by_phase"][0]
    assert first["fase_id"] == "phase-A"
    assert first["backlog_horas"] == 80.0
    # 80h / 8h/day = 10 dias
    assert first["backlog_dias_teoricos"] == 10.0
    assert first["coverage_pct"] == 100.0


@pytest.mark.asyncio
async def test_backlog_by_phase_handles_empty_result_set() -> None:
    """No rows ⇒ totals stay at zero; coverage / confidence don't crash on
    the divide-by-zero guard."""
    db = _async_db_returning(_RowsResult([]))
    sq = SemanticQueries(db=db, ingestion_id=uuid4())

    out = await sq.backlog_by_phase(top_n=10)
    assert out["data"]["total_phases_analyzed"] == 0
    assert out["data"]["total_backlog_horas"] == 0.0
    assert out["data"]["backlog_by_phase"] == []


# ---------------------------------------------------------------------------
# bottlenecks — delegates to backlog_by_phase and marks the critical ones
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bottlenecks_marks_phases_over_five_days_as_critical() -> None:
    """``bottlenecks`` calls ``backlog_by_phase`` then computes
    ``is_critical = backlog_dias_teoricos > 5`` per row."""
    rows = [
        # 80h ⇒ 10 dias ⇒ critical
        SimpleNamespace(
            fase_id="bn-1", fase_nome="Bottleneck",
            fases_abertas=10, backlog_horas=80.0, fases_com_horas=10,
        ),
        # 16h ⇒ 2 dias ⇒ NOT critical
        SimpleNamespace(
            fase_id="ok-1", fase_nome="OK",
            fases_abertas=2, backlog_horas=16.0, fases_com_horas=2,
        ),
    ]
    db = _async_db_returning(_RowsResult(rows))
    sq = SemanticQueries(db=db, ingestion_id=uuid4())

    out = await sq.bottlenecks(top_n=5)

    bottlenecks = out["data"]["bottlenecks"]
    assert len(bottlenecks) == 2
    assert bottlenecks[0]["is_critical"] is True
    assert bottlenecks[1]["is_critical"] is False
    assert out["data"]["critical_count"] == 1
    assert out["metadata"]["critical_threshold_days"] == 5


# ---------------------------------------------------------------------------
# quality_analysis / mold_conflicts — placeholder shape contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quality_analysis_returns_placeholder_shape_with_active_ingestion() -> None:
    """``quality_analysis`` is a placeholder until the errors curated model
    ships — pin the response shape so the API doesn't break unannounced."""
    db = AsyncMock()
    sq = SemanticQueries(db=db, ingestion_id=uuid4())

    out = await sq.quality_analysis(top_errors=5, group_by="severity")

    assert out["data"]["grouped_by"] == "severity"
    assert out["data"]["total_errors"] == 0
    assert out["data"]["with_fase_culpada_pct"] == 58.5
    assert "fase culpada" in out["metadata"]["warning"]


@pytest.mark.asyncio
async def test_mold_conflicts_returns_warning_status_with_active_ingestion() -> None:
    """Mold-conflict detection runs against ~4.8% DataPrevista coverage,
    so the response is fixed at ``trust_status=WARNING`` and
    ``conflicts=[]`` until the data improves."""
    db = AsyncMock()
    sq = SemanticQueries(db=db, ingestion_id=uuid4())

    out = await sq.mold_conflicts()

    assert out["trust_status"] == "WARNING"
    assert out["data"]["conflicts"] == []
    assert out["data"]["total_conflicts"] == 0
    assert out["metadata"]["data_prevista_coverage_pct"] == 4.8


# ---------------------------------------------------------------------------
# skills_risk — bucket math (critical / high / medium / ok)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skills_risk_buckets_phases_by_capable_count() -> None:
    """Bucketing rules (with min_capable=3):

      capable_count == 0 → CRITICAL
      capable_count == 1 → HIGH
      capable_count == 2 → MEDIUM
      capable_count >= 3 → OK
    """
    rows = [
        SimpleNamespace(fase_id="A", fase_nome="A", capable_count=0),
        SimpleNamespace(fase_id="B", fase_nome="B", capable_count=1),
        SimpleNamespace(fase_id="C", fase_nome="C", capable_count=2),
        SimpleNamespace(fase_id="D", fase_nome="D", capable_count=5),
    ]
    db = _async_db_returning(_RowsResult(rows))
    sq = SemanticQueries(db=db, ingestion_id=uuid4())

    out = await sq.skills_risk(min_capable=3)
    breakdown = out["data"]["risk_breakdown"]

    assert breakdown["critical"] == 1
    assert breakdown["high"] == 1
    assert breakdown["medium"] == 1
    assert breakdown["ok"] == 1
    # Phases with capable_count >= min are NOT listed in at_risk_phases.
    assert out["data"]["phases_at_risk"] == 3
    # at_risk_phases sorted ascending by capable_count
    at_risk = out["data"]["at_risk_phases"]
    assert [p["capable_count"] for p in at_risk] == [0, 1, 2]


# ---------------------------------------------------------------------------
# Static helpers — is_metric_blocked + get_allowed_metrics
# ---------------------------------------------------------------------------


def test_static_is_metric_blocked_returns_payload_or_none() -> None:
    """The static helper proxies BLOCKED_METRICS lookup; returns the dict
    or None depending on whether the id is in the deny-list."""
    payload = SemanticQueries.is_metric_blocked("oee_real")
    assert payload is not None
    assert "reason" in payload

    assert SemanticQueries.is_metric_blocked("wip_theoretical") is None


def test_static_get_allowed_metrics_returns_whitelist() -> None:
    """``get_allowed_metrics`` exposes the canonical whitelist string list."""
    allowed = SemanticQueries.get_allowed_metrics()
    assert isinstance(allowed, list)
    assert "wip_theoretical" in allowed
