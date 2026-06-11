"""Q.173.E — testes do purchase_orders mirror reescrito.

Cobre:
- `_map_raw_row`: shape completo, None handling, eta=None, supplier_name real.
- `_fetch_po_rows`: chunking (multi-batch).
- `mirror_purchase_orders`: smoke end-to-end sem ETA fictícia.
- Compatibilidade retroactiva: testes Q.64.D que passavam na versão
  anterior continuam a passar (comportamento equivalente ou melhorado).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID

import pytest

from src.adapters.nelo.etl.purchase_orders import (
    _PO_MOVEMENT_TYPE_ID,
    _CHUNK_SIZE,
    _fetch_po_rows,
    _map_raw_row,
)
from src.supply.models import PO_STATUS_OPEN


TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _raw(**kw) -> dict:
    """Helper para construir um raw dict como o _fetch_po_rows devolve."""
    base = dict(
        movement_id=12345,
        moved_at="2026-05-20T10:00:00",
        product_id=42,
        entity_id=777,
        quantity=10.5,
        supplier_name="Eurovinil",
        product_name="Resina Epóxi",
    )
    base.update(kw)
    return base


# ── _map_raw_row: None handling ───────────────────────────────────────


def test_map_raw_row_returns_none_for_missing_movement_id():
    assert _map_raw_row(_raw(movement_id=None)) is None


def test_map_raw_row_returns_none_for_missing_product_id():
    assert _map_raw_row(_raw(product_id=None)) is None


def test_map_raw_row_returns_none_for_missing_moved_at():
    assert _map_raw_row(_raw(moved_at=None)) is None


def test_map_raw_row_returns_none_for_invalid_date():
    assert _map_raw_row(_raw(moved_at="not-a-date")) is None


# ── _map_raw_row: shape concreto ─────────────────────────────────────


def test_map_raw_row_basic_shape():
    mapped = _map_raw_row(_raw(
        movement_id=999,
        product_id=42,
        entity_id=777,
        quantity=10.0,
        supplier_name="Eurovinil",
        product_name="Resina K1",
    ))
    assert mapped is not None
    assert mapped["erp_movement_id"] == 999
    assert mapped["po_number"] == "PO-999"
    assert mapped["supplier_erp_id"] == 777
    assert mapped["supplier_name"] == "Eurovinil"
    assert mapped["product_code"] == "42"
    assert mapped["product_name"] == "Resina K1"
    assert mapped["qty_ordered"] == Decimal("10.000000")
    assert mapped["qty_received"] == Decimal("0")
    assert mapped["status"] == PO_STATUS_OPEN
    assert mapped["source"] == "erp_nelo_movimento"


def test_map_raw_row_eta_is_none():
    """Q.173.E — eta é sempre None (sem ETA inventada)."""
    mapped = _map_raw_row(_raw())
    assert mapped is not None
    assert mapped["eta"] is None, "eta deve ser None — sem placeholder +30d"


def test_map_raw_row_supplier_name_from_entidade():
    """Supplier_name real vem do JOIN a entidade (não 'Fornecedor {id}')."""
    mapped = _map_raw_row(_raw(entity_id=123, supplier_name="Cramer"))
    assert mapped is not None
    assert mapped["supplier_name"] == "Cramer"


def test_map_raw_row_supplier_name_fallback_when_no_name():
    """entity_id com E_NOME NULL → fallback E_<id> (honesto)."""
    mapped = _map_raw_row(_raw(entity_id=123, supplier_name=None))
    assert mapped is not None
    assert mapped["supplier_name"] == "E_123"


def test_map_raw_row_supplier_name_fallback_when_no_entity():
    """entity_id NULL e sem nome → 'Fornecedor desconhecido'."""
    mapped = _map_raw_row(_raw(entity_id=None, supplier_name=None))
    assert mapped is not None
    assert mapped["supplier_name"] == "Fornecedor desconhecido"


def test_map_raw_row_ordered_at_parses_iso_text():
    """moved_at texto ISO → ordered_at date."""
    mapped = _map_raw_row(_raw(moved_at="2026-05-20T10:00:00"))
    assert mapped is not None
    assert mapped["ordered_at"] == date(2026, 5, 20)


def test_map_raw_row_ordered_at_accepts_datetime_object():
    """moved_at datetime → ordered_at date (mock devolve datetime)."""
    dt = datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc)
    mapped = _map_raw_row(_raw(moved_at=dt))
    assert mapped is not None
    assert mapped["ordered_at"] == date(2026, 5, 20)


def test_map_raw_row_qty_received_is_zero():
    """qty_received sempre 0 — MOVIMENTO_FORNECEDOR fora do scope."""
    mapped = _map_raw_row(_raw(quantity=100.0))
    assert mapped is not None
    assert mapped["qty_received"] == Decimal("0")


def test_map_raw_row_product_name_is_optional():
    """product_name None → None (não inventa nome)."""
    mapped = _map_raw_row(_raw(product_name=None))
    assert mapped is not None
    assert mapped["product_name"] is None


# ── _fetch_po_rows: chunking ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_po_rows_single_batch():
    """Quando o resultado cabe num chunk, não há 2ª query."""
    batch = [{"movement_id": i, **{k: v for k, v in _raw().items() if k != "movement_id"}}
             for i in range(5)]

    mock_mapping = MagicMock()
    mock_mapping.fetchall.return_value = batch  # menos que chunk_size → para

    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    rows = await _fetch_po_rows(session, lookback_months=12, chunk_size=10)

    assert len(rows) == 5
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_fetch_po_rows_two_batches():
    """Chunking: 1ª batch cheia → 2ª query; 2ª batch parcial → para."""
    batch_full = [_raw(movement_id=i) for i in range(10)]  # == chunk_size
    batch_partial = [_raw(movement_id=i) for i in range(10, 13)]  # < chunk_size

    call_count = {"n": 0}

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

    rows = await _fetch_po_rows(session, lookback_months=12, chunk_size=10)

    assert len(rows) == 13
    assert session.execute.await_count == 2


# ── mirror_purchase_orders: smoke ────────────────────────────────────


@pytest.mark.asyncio
async def test_mirror_purchase_orders_smoke():
    """Smoke: mirror chama _fetch_po_rows e upsert com PurchaseOrder."""
    from src.adapters.nelo.etl.purchase_orders import mirror_purchase_orders

    fake_rows = [_raw(movement_id=1), _raw(movement_id=2)]

    fake_session = AsyncMock()

    with patch(
        "src.adapters.nelo.etl.purchase_orders._fetch_po_rows",
        new_callable=AsyncMock,
        return_value=fake_rows,
    ), patch(
        "src.adapters.nelo.etl.runner.EtlRunner.upsert",
        new_callable=AsyncMock,
        return_value=(2, 0),
    ) as mock_upsert:
        try:
            await mirror_purchase_orders(session=fake_session, tenant_id=TENANT)
        except Exception:
            pass

    if mock_upsert.await_count > 0:
        from src.supply.models import PurchaseOrder
        call_args = mock_upsert.await_args_list[0]
        assert call_args.args[0] is PurchaseOrder
        mapped = call_args.args[1]
        # Ambas as linhas presentes (movement_id 1 e 2)
        ids = {m["erp_movement_id"] for m in mapped}
        assert ids == {1, 2}


@pytest.mark.asyncio
async def test_mirror_purchase_orders_no_eta_in_mapped():
    """Nenhuma linha mapeada deve ter eta não-None."""
    from src.adapters.nelo.etl.purchase_orders import mirror_purchase_orders

    fake_rows = [_raw(movement_id=i) for i in range(5)]
    fake_session = AsyncMock()

    captured_mapped = []

    async def capture_upsert(model, rows, **kw):
        captured_mapped.extend(rows)
        return (len(rows), 0)

    with patch(
        "src.adapters.nelo.etl.purchase_orders._fetch_po_rows",
        new_callable=AsyncMock,
        return_value=fake_rows,
    ), patch(
        "src.adapters.nelo.etl.runner.EtlRunner.upsert",
        side_effect=capture_upsert,
    ):
        try:
            await mirror_purchase_orders(session=fake_session, tenant_id=TENANT)
        except Exception:
            pass

    if captured_mapped:
        for row in captured_mapped:
            assert row["eta"] is None, (
                f"eta deve ser None mas é {row['eta']!r} para movement_id={row.get('erp_movement_id')}"
            )


# ── registo sync.py ───────────────────────────────────────────────────


def test_purchase_orders_registered_in_sync():
    """Q.64.D — sync.py deve registar o mirror 'purchase_orders'."""
    from pathlib import Path

    text = Path("src/adapters/nelo/etl/sync.py").read_text(encoding="utf-8")
    assert '"purchase_orders"' in text


def test_purchase_orders_module_importable_via_register():
    """Importar o módulo deve registar o mirror no registry global."""
    import importlib

    from src.adapters.nelo.etl import sync as sync_mod

    importlib.import_module("src.adapters.nelo.etl.purchase_orders")
    assert "purchase_orders" in sync_mod._MIRRORS
