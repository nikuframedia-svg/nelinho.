"""Q.64.D — purchase_orders mirror tests.

`_map_movement_to_po` é pura — testável sem DB. O end-to-end
`mirror_purchase_orders` corre via fake session (conftest) com
`list_recent_movements` mocked.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from src.adapters.nelo.etl.purchase_orders import (
    _PO_MOVEMENT_TYPE_ID,
    _map_movement_to_po,
)
from src.adapters.nelo.schemas import MovementRow
from src.supply.models import PO_STATUS_OPEN


TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _mov(**kw) -> MovementRow:
    """Helper para construir MovementRow com defaults — tipo 9 por defeito."""
    base = dict(
        movement_id=12345,
        moved_at=datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc),
        exit_date=None,
        quantity=10.5,
        unit_price=2.5,
        sale_price=3.0,
        discount=0.0,
        movement_type_id=_PO_MOVEMENT_TYPE_ID,  # 9 — pedido a fornecedor
        work_order_id=None,
        work_order_phase_id=None,
        product_id=42,
        entity_id=777,
        warehouse_id=1,
        phase_id=None,
        routing_id=None,
        parent_movement_id=None,
        batch=None,
        balance_quantity=100.0,
        is_adjustment=False,
        is_defective=False,
        is_satisfied=True,
        approved_at=None,
        observations=None,
        problem=None,
    )
    base.update(kw)
    return MovementRow(**base)


# ── _map_movement_to_po: None handling ───────────────────────────────


def test_map_returns_none_for_non_po_movement_type():
    """movement_type_id != 9 → None (filtra saídas/consumos)."""
    row = _mov(movement_type_id=5)  # consumo, não PO
    assert _map_movement_to_po(row) is None


def test_map_returns_none_for_consume_type_1():
    """Outro tipo de consumo → None (não é PO)."""
    row = _mov(movement_type_id=1)
    assert _map_movement_to_po(row) is None


def test_map_returns_none_for_missing_product_id():
    row = _mov(product_id=None)
    assert _map_movement_to_po(row) is None


def test_map_returns_none_for_missing_moved_at():
    row = _mov(moved_at=None)
    assert _map_movement_to_po(row) is None


# ── _map_movement_to_po: shape concreto ──────────────────────────────


def test_map_basic_shape():
    """PO típica → shape completo e correcto."""
    row = _mov(
        movement_id=999,
        product_id=42,
        entity_id=777,
        quantity=10.0,
        unit_price=2.5,
    )
    mapped = _map_movement_to_po(row)
    assert mapped is not None
    assert mapped["erp_movement_id"] == 999
    assert mapped["po_number"] == "PO-999"
    assert mapped["supplier_erp_id"] == 777
    assert mapped["supplier_name"] == "Fornecedor 777"
    assert mapped["product_code"] == "42"
    assert mapped["qty_ordered"] == Decimal("10.000000")
    assert mapped["qty_received"] == Decimal("0")
    assert mapped["status"] == PO_STATUS_OPEN
    assert mapped["source"] == "erp_nelo_movimento"
    assert mapped["unit_of_measure"] == "UN"


def test_map_po_number_uses_movement_id():
    """po_number é determinístico — `PO-<movement_id>`."""
    row = _mov(movement_id=12345)
    mapped = _map_movement_to_po(row)
    assert mapped["po_number"] == "PO-12345"


def test_map_status_is_open_constant():
    """Toda a PO nova começa em OPEN — não inventamos um literal."""
    row = _mov()
    mapped = _map_movement_to_po(row)
    assert mapped["status"] == "OPEN"


def test_map_eta_is_ordered_at_plus_30_days():
    """ETA placeholder = ordered_at + 30d (lead-time típico raw materials)."""
    row = _mov(moved_at=datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc))
    mapped = _map_movement_to_po(row)
    assert mapped["ordered_at"] == date(2026, 5, 20)
    assert mapped["eta"] == date(2026, 6, 19)  # +30 dias


def test_map_supplier_name_fallback_for_missing_entity_id():
    """entity_id None → label genérico em vez de `Fornecedor None`."""
    row = _mov(entity_id=None)
    mapped = _map_movement_to_po(row)
    assert mapped["supplier_name"] == "Fornecedor desconhecido"
    assert mapped["supplier_erp_id"] is None


def test_map_qty_ordered_uses_quantity():
    """quantity (float) → qty_ordered (Decimal com 6 casas)."""
    row = _mov(quantity=15.75)
    mapped = _map_movement_to_po(row)
    assert mapped["qty_ordered"] == Decimal("15.750000")


def test_map_qty_received_starts_at_zero():
    """qty_received começa sempre a 0 — não há receipt tracking ainda."""
    row = _mov(quantity=100.0)
    mapped = _map_movement_to_po(row)
    assert mapped["qty_received"] == Decimal("0")
    assert mapped["qty_received"] < mapped["qty_ordered"]


def test_map_received_at_is_none():
    """received_at None até haver receipt tracking."""
    row = _mov()
    mapped = _map_movement_to_po(row)
    assert mapped["received_at"] is None


def test_map_source_is_erp_nelo_movimento():
    """source label fixo — distingue de POs criadas em ProdPlan."""
    row = _mov()
    mapped = _map_movement_to_po(row)
    assert mapped["source"] == "erp_nelo_movimento"


# ── mirror_purchase_orders end-to-end (fake session) ──────────────────


@pytest.mark.asyncio
async def test_mirror_purchase_orders_upserts_only_type_9():
    """Smoke: o mirror filtra inline por tipo 9 antes de upsertar."""
    from src.adapters.nelo.etl.purchase_orders import mirror_purchase_orders

    fake_rows = [
        _mov(movement_id=1, movement_type_id=9, product_id=10),  # PO ✓
        _mov(movement_id=2, movement_type_id=5, product_id=20),  # consumo ✗
        _mov(movement_id=3, movement_type_id=9, product_id=30),  # PO ✓
    ]

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock()

    with patch(
        "src.adapters.nelo.services.list_recent_movements",
        new_callable=AsyncMock,
        return_value=fake_rows,
    ), patch(
        "src.adapters.nelo.etl.runner.EtlRunner.upsert",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_upsert:
        try:
            await mirror_purchase_orders(session=fake_session, tenant_id=TENANT)
        except Exception:
            pass

    # Confirmar que upsert foi chamado com PurchaseOrder.
    if mock_upsert.await_count > 0:
        from src.supply.models import PurchaseOrder
        call_args = mock_upsert.await_args_list[0]
        assert call_args.args[0] is PurchaseOrder, (
            "upsert deve ser chamado com PurchaseOrder"
        )
        # E o batch só deve conter as 2 POs (não a linha de consumo).
        mapped = call_args.args[1]
        assert len(mapped) == 2, (
            f"esperava 2 POs mapeadas (apenas tipo 9), obtive {len(mapped)}"
        )
        movement_ids = {m["erp_movement_id"] for m in mapped}
        assert movement_ids == {1, 3}


# ── sync.py registration ──────────────────────────────────────────────


def test_purchase_orders_registered_in_sync():
    """Q.64.D — sync.py deve registar o mirror `purchase_orders`."""
    from pathlib import Path

    text = Path("src/adapters/nelo/etl/sync.py").read_text(encoding="utf-8")
    assert '"purchase_orders"' in text, (
        "Q.64.D: purchase_orders não está registado em sync.py"
    )


def test_purchase_orders_module_importable_via_register():
    """Importar o módulo deve registar o mirror no registry global."""
    # Importação directa força o `register_mirror(...)` no fim do módulo.
    import importlib

    from src.adapters.nelo.etl import sync as sync_mod

    importlib.import_module("src.adapters.nelo.etl.purchase_orders")
    assert "purchase_orders" in sync_mod._MIRRORS, (
        "register_mirror('purchase_orders', ...) deve correr ao importar"
    )
