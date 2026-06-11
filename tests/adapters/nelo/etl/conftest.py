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


class _UpdateResult:
    """Mimics the Result of a Core ``update()`` — exposes ``rowcount``."""

    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class RecordingSession:
    """A fake ``AsyncSession`` that records ``add``-ed objects and serves
    ``execute`` from them.

    ``flush`` assigns UUIDs to id-less objects so a mirror can read an
    object's ``id`` right after adding it. ``execute`` supports:

    * ``select(Entity)`` — yields the ORM objects;
    * ``select(Entity.col_a, Entity.col_b)`` — yields value tuples;
    * ``update(Entity).where(...).values(...)`` — applies the values to
      every recorded object matching the equality ``where`` clauses and
      returns a result with ``rowcount``.
    """

    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        """No-op — a sessão real comita; o fake só regista os adds."""

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    async def scalar(self, statement, *_a, **_kw):
        return (await self.execute(statement)).scalar()

    async def execute(self, statement, *_a, **_kw):
        if statement.__class__.__name__ == "Update":
            return self._apply_update(statement)
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

    def _apply_update(self, statement) -> _UpdateResult:
        """Apply a Core ``update()`` with equality ``where`` clauses to
        the recorded objects of the target table."""
        table = statement.table
        model = next(
            (
                m.class_
                for m in _mapped_classes()
                if getattr(m.class_, "__table__", None) is table
            ),
            None,
        )
        # Equality conditions: column name → required value.
        conds = {}
        for crit in statement._where_criteria:
            try:
                conds[crit.left.name] = crit.right.value
            except AttributeError:  # pragma: no cover - non-equality clause
                pass
        values = {
            (k.name if hasattr(k, "name") else k): getattr(v, "value", v)
            for k, v in statement._values.items()
        }
        hit = 0
        for obj in self.added:
            if model is not None and not isinstance(obj, model):
                continue
            if all(getattr(obj, col, None) == val for col, val in conds.items()):
                for col, val in values.items():
                    setattr(obj, col, val)
                hit += 1
        return _UpdateResult(hit)


def _mapped_classes():
    """All ORM mappers known to SQLAlchemy — used to resolve an
    ``update()`` target table back to its model class."""
    from src.shared.database import Base

    return list(Base.registry.mappers)


@pytest.fixture
def recording_session() -> RecordingSession:
    """A fresh recording fake session per test."""
    return RecordingSession()
