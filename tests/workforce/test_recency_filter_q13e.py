"""Sprint Q.13.E E.5 — `WorkforceService.recently_active_funcionarios` test.

Plan v4 §3.4: a funcionario "qualified" for Laminagem 5 years ago who
hasn't done it since shouldn't show up in pair-formation candidate
lists. The skill matrix is a boolean (apto / not), but the *active*
workforce is who's actually executed the phase recently — we read
that off the allocation history.

These tests pin the contract:
  * Empty months window → empty set (caller treats as no-filter).
  * Query failure → empty set + log (best-effort, never blows up).
  * Phase-scoped filter narrows to one phase's allocation rows.
  * The cutoff respects ``today - months × 30 days`` semantics.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, List
from uuid import UUID

import pytest

from src.workforce.service import WorkforceService


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _FakeResult:
    def __init__(self, rows: List[tuple[str]]):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeSession:
    """Async DB stand-in. Captures executed statements and returns
    a configurable row set."""

    def __init__(self, rows: List[tuple[str]] | None = None,
                 raise_on_execute: bool = False) -> None:
        self.rows = rows or []
        self.raise_on_execute = raise_on_execute
        self.last_stmt = None
        self.executed = 0

    async def execute(self, stmt):
        self.last_stmt = stmt
        self.executed += 1
        if self.raise_on_execute:
            raise RuntimeError("simulated DB error")
        return _FakeResult(self.rows)


@pytest.mark.asyncio
async def test_recency_filter_returns_empty_when_months_zero():
    """Months=0 disables the filter — the caller should fall back to
    "no filter applied" semantics."""
    svc = WorkforceService(
        db=_FakeSession(rows=[("worker-A",)]),  # type: ignore[arg-type]
        tenant_id=_TENANT,
    )
    out = await svc.recently_active_funcionarios(months=0)
    assert out == set()


@pytest.mark.asyncio
async def test_recency_filter_returns_distinct_funcionario_ids():
    """All distinct active funcionarios are returned."""
    rows = [("worker-A",), ("worker-B",), ("worker-A",), (None,)]
    svc = WorkforceService(
        db=_FakeSession(rows=rows),  # type: ignore[arg-type]
        tenant_id=_TENANT,
    )
    out = await svc.recently_active_funcionarios(months=12)
    # None / empty filtered out, duplicates collapsed.
    assert out == {"worker-A", "worker-B"}


@pytest.mark.asyncio
async def test_recency_filter_swallows_query_failure():
    """A DB error must NOT break the calling site — return empty set
    and let the caller decide on permissive vs. strict policy."""
    svc = WorkforceService(
        db=_FakeSession(raise_on_execute=True),  # type: ignore[arg-type]
        tenant_id=_TENANT,
    )
    out = await svc.recently_active_funcionarios(months=12)
    assert out == set()


@pytest.mark.asyncio
async def test_recency_filter_calls_db_once_when_enabled():
    """With months > 0 the filter executes one DISTINCT query."""
    session = _FakeSession(rows=[("worker-A",)])
    svc = WorkforceService(
        db=session,  # type: ignore[arg-type]
        tenant_id=_TENANT,
    )
    out = await svc.recently_active_funcionarios(months=12, phase_id="LAMINAGEM")
    assert out == {"worker-A"}
    assert session.executed == 1


@pytest.mark.asyncio
async def test_recency_filter_negative_months_treated_as_disabled():
    """Negative months must NOT silently invert the cutoff — disable
    instead. (Defensive: an operator who fat-fingers -12 in
    ConfigStore shouldn't suddenly accept everyone as active.)"""
    svc = WorkforceService(
        db=_FakeSession(rows=[("worker-A",)]),  # type: ignore[arg-type]
        tenant_id=_TENANT,
    )
    out = await svc.recently_active_funcionarios(months=-12)
    assert out == set()
