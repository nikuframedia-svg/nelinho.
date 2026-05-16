"""Q.20.A — EtlRunner unit tests.

Two surfaces:
  * the idempotent `upsert` — exercised against a real aiosqlite DB with a
    minimal test model, so the load-existing/insert/update logic runs;
  * the `core.etl_run` audit lifecycle — exercised with a fake session,
    asserting status/counts/finished_at land on the EtlRun row.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.infrastructure.erp.etl.runner import EtlRunner


# ── Minimal test model (no schema, no PG types — runs on SQLite) ──────────


class _Base(DeclarativeBase):
    pass


class _Widget(_Base):
    __tablename__ = "widget"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(40), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


TENANT = "tenant-1"
OTHER_TENANT = "tenant-2"


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _runner(session: AsyncSession) -> EtlRunner:
    return EtlRunner(session, TENANT, source="test")


# ── upsert: insert ────────────────────────────────────────────────────────


async def test_upsert_inserts_new_rows(session):
    runner = _runner(session)
    rows = [
        {"code": "A", "name": "alpha", "value": 1},
        {"code": "B", "name": "beta", "value": 2},
    ]
    inserted, updated = await runner.upsert(_Widget, rows, key_fields=["code"])
    assert (inserted, updated) == (2, 0)
    assert runner.result.rows_inserted == 2

    stored = (await session.execute(_Widget.__table__.select())).fetchall()
    assert len(stored) == 2
    assert all(r.tenant_id == TENANT for r in stored)


# ── upsert: idempotency ───────────────────────────────────────────────────


async def test_upsert_is_idempotent(session):
    rows = [{"code": "A", "name": "alpha", "value": 1}]
    first = await _runner(session).upsert(_Widget, rows, key_fields=["code"])
    assert first == (1, 0)
    # Same data again — no insert, no update.
    second = await _runner(session).upsert(_Widget, rows, key_fields=["code"])
    assert second == (0, 0)

    count = (await session.execute(_Widget.__table__.select())).fetchall()
    assert len(count) == 1


# ── upsert: update only changed rows ──────────────────────────────────────


async def test_upsert_updates_changed_row(session):
    await _runner(session).upsert(
        _Widget, [{"code": "A", "name": "alpha", "value": 1}], key_fields=["code"],
    )
    inserted, updated = await _runner(session).upsert(
        _Widget, [{"code": "A", "name": "ALPHA", "value": 1}], key_fields=["code"],
    )
    assert (inserted, updated) == (0, 1)

    row = (await session.execute(_Widget.__table__.select())).fetchone()
    assert row.name == "ALPHA"


async def test_upsert_mixed_insert_and_update(session):
    await _runner(session).upsert(
        _Widget, [{"code": "A", "name": "alpha", "value": 1}], key_fields=["code"],
    )
    inserted, updated = await _runner(session).upsert(
        _Widget,
        [
            {"code": "A", "name": "alpha2", "value": 1},  # changed → update
            {"code": "B", "name": "beta", "value": 2},    # new → insert
        ],
        key_fields=["code"],
    )
    assert (inserted, updated) == (1, 1)


async def test_upsert_respects_update_fields_whitelist(session):
    await _runner(session).upsert(
        _Widget, [{"code": "A", "name": "alpha", "value": 1}], key_fields=["code"],
    )
    # `value` changed but not in update_fields → must be ignored.
    inserted, updated = await _runner(session).upsert(
        _Widget,
        [{"code": "A", "name": "alpha", "value": 999}],
        key_fields=["code"],
        update_fields=["name"],
    )
    assert (inserted, updated) == (0, 0)
    row = (await session.execute(_Widget.__table__.select())).fetchone()
    assert row.value == 1


async def test_upsert_is_tenant_scoped(session):
    """A row with the same business key under a different tenant must not
    collide — the runner inserts a fresh row for its own tenant."""
    await EtlRunner(session, OTHER_TENANT, source="test").upsert(
        _Widget, [{"code": "A", "name": "other", "value": 0}], key_fields=["code"],
    )
    inserted, updated = await _runner(session).upsert(
        _Widget, [{"code": "A", "name": "mine", "value": 1}], key_fields=["code"],
    )
    assert (inserted, updated) == (1, 0)
    rows = (await session.execute(_Widget.__table__.select())).fetchall()
    assert {r.tenant_id for r in rows} == {TENANT, OTHER_TENANT}


async def test_upsert_empty_rows_is_noop(session):
    assert await _runner(session).upsert(_Widget, [], key_fields=["code"]) == (0, 0)


async def test_upsert_requires_key_fields(session):
    with pytest.raises(ValueError, match="key field"):
        await _runner(session).upsert(
            _Widget, [{"code": "A", "name": "a", "value": 1}], key_fields=[],
        )


# ── audit lifecycle (fake session — no DB needed) ─────────────────────────


class _FakeSession:
    def __init__(self) -> None:
        self.added: list = []
        self.flushes = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1


async def test_etl_run_audit_row_marked_ok_on_success():
    fake = _FakeSession()
    async with EtlRunner(fake, TENANT, source="master") as run:  # type: ignore[arg-type]
        run.count_read(7)
        run.result.rows_inserted = 5

    assert len(fake.added) == 1
    etl_run = fake.added[0]
    assert etl_run.source == "master"
    assert etl_run.status == "ok"
    assert etl_run.rows_read == 7
    assert etl_run.rows_inserted == 5
    assert etl_run.finished_at is not None


async def test_etl_run_audit_row_marked_error_on_exception():
    fake = _FakeSession()
    with pytest.raises(ValueError, match="boom"):
        async with EtlRunner(fake, TENANT, source="quality") as run:  # type: ignore[arg-type]
            run.count_read(3)
            raise ValueError("boom")

    etl_run = fake.added[0]
    assert etl_run.status == "error"
    assert "boom" in etl_run.error
    assert etl_run.rows_read == 3
    assert etl_run.finished_at is not None
