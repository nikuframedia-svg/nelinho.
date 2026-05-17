"""Q.20.C — molds mirror tests.

``_map_mold`` is pure. The end-to-end ``mirror_molds`` runs against the
recording fake session (conftest) with the adapter mocked — no SQL
Server, no Postgres.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock
from uuid import UUID

from src.adapters.nelo.etl import molds as molds_mod
from src.adapters.nelo.etl.molds import _map_mold, mirror_molds
from src.adapters.nelo.schemas import MoldRow
from src.plan.models.mold import Mold

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _mold(**kw) -> MoldRow:
    base = dict(
        mold_id=1, mold_name="B ST 01", mold_type_id=1, usage_count=0,
        acquired_at=datetime(2010, 2, 16, 19, 52),
    )
    base.update(kw)
    return MoldRow(**base)


# ── pure mapper ───────────────────────────────────────────────────────────


def test_map_mold_uses_mld_id_as_business_key():
    mapped = _map_mold(_mold(mold_id=42, mold_name="B ST 42"))
    assert mapped["mold_code"] == "42"
    assert mapped["name"] == "B ST 42"
    assert mapped["active"] is True


def test_map_mold_derives_type_from_type_id():
    assert _map_mold(_mold(mold_type_id=3))["mold_type"] == "tipo-3"


def test_map_mold_carries_acquired_date():
    mapped = _map_mold(_mold(acquired_at=datetime(2015, 6, 1, 8, 0)))
    assert mapped["acquired_date"] == date(2015, 6, 1)


def test_map_mold_model_id_is_insert_only_sentinel():
    """The ERP MOLDES row has no product linkage — model_id is the
    empty-string sentinel, passed insert-only so a curated sync can own
    it later."""
    assert _map_mold(_mold())["model_id"] == ""


def test_map_mold_falls_back_when_name_missing():
    """A mold with an empty name uses its id as the display name."""
    assert _map_mold(_mold(mold_id=9, mold_name=""))["name"] == "9"


# ── end-to-end mirror ─────────────────────────────────────────────────────


async def test_mirror_molds_inserts_erp_catalogue(monkeypatch, recording_session):
    monkeypatch.setattr(
        molds_mod.services, "list_molds",
        AsyncMock(return_value=[
            _mold(mold_id=1, mold_name="B ST 01"),
            _mold(mold_id=2, mold_name="B ST 02"),
            _mold(mold_id=3, mold_name="B ST 03"),
        ]),
    )
    result = await mirror_molds(session=recording_session, tenant_id=TENANT, since=None)

    assert result.status == "ok"
    assert result.rows_read == 3
    molds = [o for o in recording_session.added if isinstance(o, Mold)]
    assert {m.mold_code for m in molds} == {"1", "2", "3"}
    # NOT NULL model_id is seeded on insert.
    assert all(m.model_id == "" for m in molds)
    assert result.rows_inserted == 3


async def test_mirror_molds_empty_catalogue_is_clean(monkeypatch, recording_session):
    monkeypatch.setattr(
        molds_mod.services, "list_molds", AsyncMock(return_value=[]),
    )
    result = await mirror_molds(session=recording_session, tenant_id=TENANT, since=None)
    assert result.status == "ok"
    assert result.rows_read == 0
    assert result.rows_inserted == 0
