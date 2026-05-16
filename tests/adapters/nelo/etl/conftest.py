"""Shared fixtures for the Q.20 ETL mirror tests.

The dev box has neither a live SQL Server (the ERP source) nor a running
Postgres (the dev target). ETL mirror tests therefore run against:

* ``AsyncMock`` for the read-only NELO adapter (``services.list_*``);
* :class:`RecordingSession` — a fake ``AsyncSession`` that records
  ``add``-ed objects and serves ``execute`` from them, modelling a
  Postgres where rows written earlier in the transaction are visible to
  later reads in the same mirror.

The operational ORM models use Postgres-only column types (JSONB on
``Employee``), so an in-memory SQLite engine is not an option — the
recording session is.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


class _Result:
    """Mimics a SQLAlchemy Result over a fixed list of objects/rows."""

    def __init__(self, items) -> None:
        self._items = list(items)

    def scalars(self):
        return self

    def scalar(self):
        return self._items[0] if self._items else None

    def all(self):
        return list(self._items)

    def __iter__(self):
        return iter(self._items)


class RecordingSession:
    """A fake ``AsyncSession`` that records ``add``-ed objects and serves
    ``execute`` from them.

    ``flush`` assigns UUIDs to id-less objects so a mirror can read an
    object's ``id`` right after adding it. ``execute`` supports both
    ``select(Entity)`` (yields the ORM objects) and
    ``select(Entity.col_a, Entity.col_b)`` (yields value tuples).
    """

    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    async def scalar(self, statement, *_a, **_kw):
        return (await self.execute(statement)).scalar()

    async def execute(self, statement, *_a, **_kw) -> _Result:
        descs = list(getattr(statement, "column_descriptions", []) or [])
        if not descs:
            return _Result([])
        model = descs[0].get("entity")
        matches = [
            o for o in self.added if model is not None and isinstance(o, model)
        ]
        if len(descs) == 1 and descs[0].get("expr") is model:
            # select(Model) → yield the ORM objects themselves.
            return _Result(matches)
        # select(Model.col_a, Model.col_b, ...) → yield value tuples.
        attrs = [d["name"] for d in descs]
        return _Result([tuple(getattr(o, a) for a in attrs) for o in matches])


@pytest.fixture
def recording_session() -> RecordingSession:
    """A fresh recording fake session per test."""
    return RecordingSession()
