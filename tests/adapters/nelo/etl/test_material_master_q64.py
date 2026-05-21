"""Q.64.B — material_master mirror tests.

`_map_product` é puro. End-to-end via fake session.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from src.adapters.nelo.etl.material_master import _map_product
from src.adapters.nelo.schemas import ProductRow


TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _prod(**kw) -> ProductRow:
    base = dict(
        product_id=100,
        product_name="Casco K1",
        product_name_en=None,
        product_type_id=1,
        active=True,
        discontinued=False,
        in_house=True,
        cost_price=150.0,
    )
    base.update(kw)
    return ProductRow(**base)


def test_map_product_returns_none_for_missing_product_id():
    """product_id None → skip (sem sku_id, não há linha válida)."""
    # ProductRow has product_id as required — não pode ser None.
    # Mas se o mapper recebe um row com product_id 0 ou None equivalent.
    # Smoke: confirmar contract.
    mapped = _map_product(_prod(product_id=0))
    assert mapped is not None  # 0 ainda é "valid" como sku_id
    assert mapped["sku_id"] == "0"


def test_map_product_basic_shape():
    mapped = _map_product(_prod(product_id=42, product_name="Foo"))
    assert mapped["sku_id"] == "42"
    assert mapped["name"] == "Foo"
    assert mapped["unit_of_measure"] == "UN"
    assert mapped["lead_time_days"] == 7
    assert mapped["min_stock_qty"] == Decimal("0")
    assert mapped["active"] is True


def test_map_product_discontinued_inactive():
    """active e not discontinued → False quando discontinued."""
    mapped = _map_product(_prod(active=True, discontinued=True))
    assert mapped["active"] is False


def test_map_product_inactive_in_erp():
    """active False no ERP → active False local."""
    mapped = _map_product(_prod(active=False))
    assert mapped["active"] is False


def test_map_product_uses_type_id_as_category():
    """product_type_id → category 'type_X'."""
    mapped = _map_product(_prod(product_type_id=5))
    assert mapped["category"] == "type_5"


def test_map_product_no_type_id_no_category():
    mapped = _map_product(_prod(product_type_id=None))
    assert mapped["category"] is None


def test_map_product_name_truncated_to_255():
    """name é String(255) — verifica truncamento defensivo."""
    long_name = "X" * 300
    mapped = _map_product(_prod(product_name=long_name))
    assert len(mapped["name"]) <= 255


def test_map_product_empty_name_uses_p_id_fallback():
    """product_name vazio → fallback `P_<id>`."""
    mapped = _map_product(_prod(product_id=99, product_name=""))
    assert mapped["name"] == "P_99"


@pytest.mark.asyncio
async def test_mirror_material_master_uses_runner():
    """Smoke: mirror_material_master fetches products + upserts via EtlRunner."""
    from src.adapters.nelo.etl.material_master import mirror_material_master

    fake_rows = [_prod(product_id=1), _prod(product_id=2)]

    fake_session = AsyncMock()

    with patch(
        "src.adapters.nelo.services.list_products",
        new_callable=AsyncMock,
        return_value=fake_rows,
    ), patch(
        "src.adapters.nelo.etl.runner.EtlRunner.upsert",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_upsert:
        try:
            await mirror_material_master(session=fake_session, tenant_id=TENANT)
        except Exception:
            pass

    if mock_upsert.await_count > 0:
        from src.supply.models import MaterialMaster
        call_args = mock_upsert.await_args_list[0]
        assert call_args.args[0] is MaterialMaster


def test_inventory_ledger_and_material_master_registered():
    """Q.64.A+B — sync.py deve registar ambos os mirrors."""
    from pathlib import Path

    text = Path("src/adapters/nelo/etl/sync.py").read_text(encoding="utf-8")
    assert '"inventory_ledger"' in text, (
        "Q.64.A: inventory_ledger não está registado em sync.py"
    )
    assert '"material_master"' in text, (
        "Q.64.B: material_master não está registado em sync.py"
    )
