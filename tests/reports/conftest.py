"""Shared fakes for the reports test suite.

The reports models live in the ``reports`` PostgreSQL schema with JSONB
columns — SQLite cannot host them — so the endpoints are exercised
against an in-memory ``FakeSession`` that stores ORM rows in typed
lists. It implements only the methods the reports API uses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from src.core.models.audit import AuditLog
from src.reports.models import ReportRun, ReportSchedule


class _FakeResult:
    def __init__(self, rows: list, *, count: int | None = None):
        self._rows = rows
        self._count = count

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        if self._count is not None:
            return self._count
        return self._rows[0] if self._rows else None


class FakeSession:
    """Minimal AsyncSession stand-in for the reports API.

    ``add`` assigns the primary key + timestamps a real flush would
    populate. ``execute`` returns rows by inspecting which table the
    statement targets — good enough for single-row CRUD tests.
    """

    def __init__(self):
        self.schedules: list[ReportSchedule] = []
        self.runs: list[ReportRun] = []
        self.audit: list[AuditLog] = []
        self.commits = 0
        # Canned generator source rows, keyed by a table-name fragment
        # (e.g. "hr_allocations"). Each value is a list of tuples.
        self.gen_rows: dict[str, list] = {}

    def add(self, obj: Any) -> None:
        now = datetime.utcnow()
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = now
        if hasattr(obj, "updated_at") and obj.updated_at is None:
            obj.updated_at = now
        if isinstance(obj, ReportSchedule):
            self.schedules.append(obj)
        elif isinstance(obj, ReportRun):
            self.runs.append(obj)
        elif isinstance(obj, AuditLog):
            self.audit.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass

    async def delete(self, obj: Any) -> None:
        if isinstance(obj, ReportSchedule) and obj in self.schedules:
            self.schedules.remove(obj)
        elif isinstance(obj, ReportRun) and obj in self.runs:
            self.runs.remove(obj)

    async def execute(self, stmt) -> _FakeResult:
        compiled = str(stmt)
        is_count = "count(" in compiled.lower()
        if "report_schedule" in compiled:
            return _FakeResult(
                list(self.schedules),
                count=len(self.schedules) if is_count else None,
            )
        if "report_run" in compiled:
            return _FakeResult(
                list(self.runs),
                count=len(self.runs) if is_count else None,
            )
        if "audit_log" in compiled:
            return _FakeResult(list(self.audit))
        for fragment, rows in self.gen_rows.items():
            if fragment in compiled:
                return _FakeResult(list(rows))
        return _FakeResult([])
