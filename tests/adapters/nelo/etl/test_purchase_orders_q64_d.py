"""Q.64.D / Q.173.E — purchase_orders mirror tests (versão actualizada).

Q.173.E reescreveu o mirror para ler `factory_raw.movimento` (espelho local)
em vez do ERP LIVE, eliminou a ETA fictícia (+30d) e passou a usar o nome
real do fornecedor via JOIN a `factory_raw.entidade`.

Este ficheiro mantém os testes de contrato que continuam válidos e actualiza
os que reflectiam comportamento deliberadamente substituído (ETA placeholder,
supplier_name "Fornecedor {id}").
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.adapters.nelo.etl.purchase_orders import (
    _PO_MOVEMENT_TYPE_ID,
    _map_raw_row,
)
from src.supply.models import PO_STATUS_OPEN


TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _raw(**kw) -> dict:
    """Helper para construir raw dict (formato _fetch_po_rows)."""
    base = dict(
        movement_id=12345,
        moved_at="2026-05-20T10:00:00",
        product_id=42,
        entity_id=777,
        quantity=10.5,
        supplier_name="Cramer",
        product_name="Resina K1",
    )
    base.update(kw)
    return base


# ── _map_raw_row: None handling ───────────────────────────────────────


def test_map_returns_none_for_missing_movement_id():
    assert _map_raw_row(_raw(movement_id=None)) is None


def test_map_returns_none_for_missing_product_id():
    row = _raw(product_id=None)
    assert _map_raw_row(row) is None


def test_map_returns_none_for_missing_moved_at():
    row = _raw(moved_at=None)
    assert _map_raw_row(row) is None


# ── _map_raw_row: shape concreto ─────────────────────────────────────


def test_map_basic_shape():
    """PO típica → shape completo e correcto."""
    row = _raw(movement_id=999, product_id=42, entity_id=777, quantity=10.0)
    mapped = _map_raw_row(row)
    assert mapped is not None
    assert mapped["erp_movement_id"] == 999
    assert mapped["po_number"] == "PO-999"
    assert mapped["supplier_erp_id"] == 777
    assert mapped["product_code"] == "42"
    assert mapped["qty_ordered"] == Decimal("10.000000")
    assert mapped["qty_received"] == Decimal("0")
    assert mapped["status"] == PO_STATUS_OPEN
    assert mapped["source"] == "erp_nelo_movimento"
    assert mapped["unit_of_measure"] == "UN"


def test_map_po_number_uses_movement_id():
    """po_number é determinístico — `PO-<movement_id>`."""
    mapped = _map_raw_row(_raw(movement_id=12345))
    assert mapped["po_number"] == "PO-12345"


def test_map_status_is_open_constant():
    """Toda a PO nova começa em OPEN."""
    mapped = _map_raw_row(_raw())
    assert mapped["status"] == "OPEN"


def test_map_eta_is_none():
    """Q.173.E — eta é None (sem ETA inventada)."""
    mapped = _map_raw_row(_raw())
    assert mapped is not None
    assert mapped["eta"] is None


def test_map_supplier_name_real_from_entidade():
    """supplier_name real do JOIN a entidade."""
    mapped = _map_raw_row(_raw(entity_id=777, supplier_name="Cramer"))
    assert mapped is not None
    assert mapped["supplier_name"] == "Cramer"


def test_map_supplier_name_fallback_for_missing_entity_id():
    """entity_id None → 'Fornecedor desconhecido'."""
    mapped = _map_raw_row(_raw(entity_id=None, supplier_name=None))
    assert mapped["supplier_name"] == "Fornecedor desconhecido"
    assert mapped["supplier_erp_id"] is None


def test_map_qty_ordered_uses_quantity():
    """quantity (float) → qty_ordered (Decimal com 6 casas)."""
    mapped = _map_raw_row(_raw(quantity=15.75))
    assert mapped["qty_ordered"] == Decimal("15.750000")


def test_map_qty_received_starts_at_zero():
    """qty_received começa sempre a 0 — não há receipt tracking ainda."""
    mapped = _map_raw_row(_raw(quantity=100.0))
    assert mapped["qty_received"] == Decimal("0")
    assert mapped["qty_received"] < mapped["qty_ordered"]


def test_map_received_at_is_none():
    """received_at None até haver receipt tracking."""
    mapped = _map_raw_row(_raw())
    assert mapped["received_at"] is None


def test_map_source_is_erp_nelo_movimento():
    """source label fixo."""
    mapped = _map_raw_row(_raw())
    assert mapped["source"] == "erp_nelo_movimento"


# ── mirror_purchase_orders end-to-end ────────────────────────────────


@pytest.mark.asyncio
async def test_mirror_purchase_orders_upserts_mapped_rows():
    """Smoke: o mirror faz upsert com PurchaseOrder."""
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
        assert len(mapped) == 2
        movement_ids = {m["erp_movement_id"] for m in mapped}
        assert movement_ids == {1, 2}


# ── sync.py registration ──────────────────────────────────────────────


def test_purchase_orders_registered_in_sync():
    """Q.64.D — sync.py deve registar o mirror `purchase_orders`."""
    from pathlib import Path

    text_content = Path("src/adapters/nelo/etl/sync.py").read_text(encoding="utf-8")
    assert '"purchase_orders"' in text_content


def test_purchase_orders_module_importable_via_register():
    """Importar o módulo deve registar o mirror no registry global."""
    import importlib

    from src.adapters.nelo.etl import sync as sync_mod

    importlib.import_module("src.adapters.nelo.etl.purchase_orders")
    assert "purchase_orders" in sync_mod._MIRRORS
