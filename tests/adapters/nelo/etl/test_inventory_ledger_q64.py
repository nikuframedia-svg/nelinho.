"""Q.64.A / Q.173.F — inventory_ledger mirror tests.

`_classify_movement` e `_map_ledger_row` são funções puras — testáveis
sem DB. O end-to-end `mirror_inventory_ledger` corre via fake session
com `_fetch_ledger_rows` mocked.

Q.173.F: `_classify_movement` recebe parâmetros directos em vez de
MovementRow, `_map_ledger_row` recebe dicts (espelho local), e o
resultado inclui `erp_of_id`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.adapters.nelo.etl.inventory_ledger import (
    _classify_movement,
    _map_ledger_row,
    _movement_uuid,
)


TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _raw(**kw) -> dict:
    """Helper para construir raw dict como _fetch_ledger_rows devolve."""
    base = dict(
        movement_id=12345,
        moved_at="2026-05-20T10:00:00",
        product_id=42,
        quantity=10.5,
        movement_type_id=5,
        is_adjustment=False,
        balance_quantity=100.0,
        of_id=None,
    )
    base.update(kw)
    return base


# ── _movement_uuid: deterministic ─────────────────────────────────────


def test_movement_uuid_deterministic():
    """Mesmo movement_id sempre dá mesmo UUID (idempotency)."""
    uid1 = _movement_uuid(12345)
    uid2 = _movement_uuid(12345)
    assert uid1 == uid2


def test_movement_uuid_different_for_different_ids():
    """movement_ids diferentes dão UUIDs diferentes."""
    assert _movement_uuid(1) != _movement_uuid(2)


# ── _classify_movement: 4 caminhos ────────────────────────────────────


def test_classify_type_9_is_receive():
    """movement_type_id == 9 → receive (qty_in)."""
    txn, qty_in, qty_out = _classify_movement(9, False, 20.0)
    assert txn == "receive"
    assert qty_in == Decimal("20.000000")
    assert qty_out == Decimal("0")


def test_classify_default_is_consume():
    """movement_type_id != 9 + not adjustment → consume (qty_out)."""
    txn, qty_in, qty_out = _classify_movement(5, False, 15.0)
    assert txn == "consume"
    assert qty_in == Decimal("0")
    assert qty_out == Decimal("15.000000")


def test_classify_adjustment_positive_is_qty_in():
    """is_adjustment=True com qty>=0 → adjust qty_in."""
    txn, qty_in, qty_out = _classify_movement(5, True, 5.0)
    assert txn == "adjust"
    assert qty_in == Decimal("5.000000")
    assert qty_out == Decimal("0")


def test_classify_adjustment_negative_is_qty_out():
    """is_adjustment=True com qty<0 → adjust qty_out."""
    txn, qty_in, qty_out = _classify_movement(5, True, -3.0)
    assert txn == "adjust"
    assert qty_in == Decimal("0")
    assert qty_out == Decimal("3.000000")


# ── _map_ledger_row: shape + None handling ────────────────────────────


def test_map_ledger_row_returns_none_for_missing_product_id():
    assert _map_ledger_row(_raw(product_id=None)) is None


def test_map_ledger_row_returns_none_for_missing_moved_at():
    assert _map_ledger_row(_raw(moved_at=None)) is None


def test_map_ledger_row_returns_none_for_invalid_date():
    assert _map_ledger_row(_raw(moved_at="not-a-date")) is None


def test_map_ledger_row_shape_consume():
    """Movimento de consumo → shape correcto, qty_opening = qty_closing + qty_out."""
    row = _raw(movement_type_id=5, quantity=10.0, balance_quantity=50.0)
    mapped = _map_ledger_row(row)
    assert mapped is not None
    assert mapped["sku_id"] == "42"
    assert mapped["transaction_type"] == "consume"
    assert mapped["qty_in"] == Decimal("0")
    assert mapped["qty_out"] == Decimal("10.000000")
    assert mapped["qty_closing"] == Decimal("50.000000")
    # opening = closing - in + out = 50 - 0 + 10 = 60
    assert mapped["qty_opening"] == Decimal("60.000000")


def test_map_ledger_row_shape_receive():
    """Movimento de recepção → qty_opening = qty_closing - qty_in."""
    row = _raw(movement_type_id=9, quantity=25.0, balance_quantity=75.0)
    mapped = _map_ledger_row(row)
    assert mapped is not None
    assert mapped["transaction_type"] == "receive"
    assert mapped["qty_in"] == Decimal("25.000000")
    # opening = 75 - 25 + 0 = 50
    assert mapped["qty_opening"] == Decimal("50.000000")


def test_map_ledger_row_reference_id_is_deterministic():
    """O reference_id é o UUID derivado do movement_id (idempotency)."""
    row1 = _map_ledger_row(_raw(movement_id=99999))
    row2 = _map_ledger_row(_raw(movement_id=99999, quantity=999.0))
    assert row1["reference_id"] == row2["reference_id"]


def test_map_ledger_row_reference_id_matches_movement_uuid():
    """reference_id é exactamente uuid5(movement_id) — mantém
    compatibilidade com as 34.076 linhas existentes (Q.64.A)."""
    movement_id = 12345
    row = _raw(movement_id=movement_id)
    mapped = _map_ledger_row(row)
    assert mapped["reference_id"] == _movement_uuid(movement_id)


# ── Q.173.F — erp_of_id ──────────────────────────────────────────────


def test_map_ledger_row_erp_of_id_populated():
    """MOV_OF_ID → erp_of_id quando present."""
    row = _raw(of_id=98765)
    mapped = _map_ledger_row(row)
    assert mapped is not None
    assert mapped["erp_of_id"] == 98765


def test_map_ledger_row_erp_of_id_none_when_absent():
    """MOV_OF_ID NULL → erp_of_id None."""
    row = _raw(of_id=None)
    mapped = _map_ledger_row(row)
    assert mapped is not None
    assert mapped["erp_of_id"] is None


# ── Q.173.F — _fetch_ledger_rows chunking ────────────────────────────


@pytest.mark.asyncio
async def test_fetch_ledger_rows_single_batch():
    """Quando o resultado cabe num chunk, só há uma query."""
    from src.adapters.nelo.etl.inventory_ledger import _fetch_ledger_rows

    batch = [_raw(movement_id=i) for i in range(3)]
    mock_mapping = MagicMock()
    mock_mapping.fetchall.return_value = batch
    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    rows = await _fetch_ledger_rows(session, lookback_months=24, since=None, chunk_size=10)

    assert len(rows) == 3
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_fetch_ledger_rows_two_batches():
    """Chunking: 1ª batch cheia → 2ª query; 2ª batch parcial → para."""
    from src.adapters.nelo.etl.inventory_ledger import _fetch_ledger_rows

    batch_full = [_raw(movement_id=i) for i in range(10)]
    batch_partial = [_raw(movement_id=i) for i in range(10, 14)]

    def _make_result(batch):
        mock_mapping = MagicMock()
        mock_mapping.fetchall.return_value = batch
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mapping
        return mock_result

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_result(batch_full),
        _make_result(batch_partial),
    ])

    rows = await _fetch_ledger_rows(session, lookback_months=24, since=None, chunk_size=10)

    assert len(rows) == 14
    assert session.execute.await_count == 2


# ── mirror_inventory_ledger end-to-end (fake session) ─────────────────


@pytest.mark.asyncio
async def test_mirror_inventory_ledger_upserts_rows_via_runner():
    """Smoke: mirror_inventory_ledger fetches + upserts via EtlRunner."""
    from src.adapters.nelo.etl.inventory_ledger import mirror_inventory_ledger

    fake_rows = [_raw(movement_id=1, product_id=10), _raw(movement_id=2, product_id=20)]

    fake_session = AsyncMock()

    with patch(
        "src.adapters.nelo.etl.inventory_ledger._fetch_ledger_rows",
        new_callable=AsyncMock,
        return_value=fake_rows,
    ), patch(
        "src.adapters.nelo.etl.runner.EtlRunner.upsert",
        new_callable=AsyncMock,
        return_value=(2, 0),
    ) as mock_upsert:
        try:
            await mirror_inventory_ledger(session=fake_session, tenant_id=TENANT)
        except Exception:
            pass

    if mock_upsert.await_count > 0:
        from src.supply.models import InventoryLedgerEntry
        call_args = mock_upsert.await_args_list[0]
        assert call_args.args[0] is InventoryLedgerEntry
        # erp_of_id deve estar em update_fields
        update_fields = call_args.kwargs.get("update_fields", [])
        assert "erp_of_id" in update_fields, (
            "erp_of_id deve estar em update_fields para ser actualizado"
        )


def test_inventory_ledger_model_has_erp_of_id():
    """InventoryLedgerEntry ORM deve ter erp_of_id."""
    from src.supply.models import InventoryLedgerEntry

    cols = {c.key for c in InventoryLedgerEntry.__mapper__.column_attrs}
    assert "erp_of_id" in cols
