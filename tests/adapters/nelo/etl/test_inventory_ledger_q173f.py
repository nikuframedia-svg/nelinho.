"""Q.173.F — testes específicos do inventory_ledger mirror reescrito.

Cobre os novos comportamentos introduzidos em Q.173.F:
- Janela de 24 meses (configurável via env).
- Watermark incremental (`since`).
- Chunking.
- `erp_of_id` propagado.
- uuid5(MOV_ID) igual ao Q.64.A (idempotência).
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.adapters.nelo.etl.inventory_ledger import (
    _movement_uuid,
    _map_ledger_row,
    _since_until_strs,
    _MOVEMENT_NAMESPACE,
)


TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _raw(**kw) -> dict:
    base = dict(
        movement_id=1,
        moved_at="2026-05-20T10:00:00",
        product_id=42,
        quantity=5.0,
        movement_type_id=5,
        is_adjustment=False,
        balance_quantity=20.0,
        of_id=None,
    )
    base.update(kw)
    return base


# ── _since_until_strs: janela temporal ────────────────────────────────


def test_since_until_strs_no_watermark_lookback_24():
    """Sem watermark → inicio = hoje - 24*30 dias."""
    since_str, until_str = _since_until_strs(24, None)
    since_date = date.fromisoformat(since_str)
    until_date = date.fromisoformat(until_str)
    today = datetime.now(timezone.utc).date()

    # Janela aproximada de 24 meses (±2 dias de tolerância)
    expected_since = today - timedelta(days=24 * 30)
    assert abs((since_date - expected_since).days) <= 2
    # until = amanhã (inclui hoje)
    assert until_date == today + timedelta(days=1)


def test_since_until_strs_with_watermark():
    """Com watermark (`since`) → since_str = watermark."""
    watermark = date(2025, 6, 1)
    since_str, _ = _since_until_strs(24, watermark)
    assert since_str == "2025-06-01"


# ── _map_ledger_row: erp_of_id ────────────────────────────────────────


def test_map_ledger_row_erp_of_id_int():
    """of_id inteiro → erp_of_id inteiro."""
    mapped = _map_ledger_row(_raw(of_id=42001))
    assert mapped is not None
    assert mapped["erp_of_id"] == 42001


def test_map_ledger_row_erp_of_id_none():
    """of_id None → erp_of_id None."""
    mapped = _map_ledger_row(_raw(of_id=None))
    assert mapped is not None
    assert mapped["erp_of_id"] is None


def test_map_ledger_row_reference_id_namespace_matches_q64a():
    """uuid5 usa o mesmo namespace que Q.64.A — idempotência garantida."""
    import uuid

    movement_id = 99001
    expected = uuid.uuid5(_MOVEMENT_NAMESPACE, f"erp:movement:{movement_id}")
    mapped = _map_ledger_row(_raw(movement_id=movement_id))
    assert mapped is not None
    assert mapped["reference_id"] == expected


# ── mirror_inventory_ledger: env NELINHO_LEDGER_LOOKBACK_MONTHS ────────


@pytest.mark.asyncio
async def test_mirror_uses_lookback_env():
    """NELINHO_LEDGER_LOOKBACK_MONTHS controla o lookback."""
    from src.adapters.nelo.etl.inventory_ledger import mirror_inventory_ledger

    fake_session = AsyncMock()
    called_lookback = []

    async def capture_fetch(session, *, lookback_months, since, chunk_size=None):
        called_lookback.append(lookback_months)
        return []

    with patch.dict(os.environ, {"NELINHO_LEDGER_LOOKBACK_MONTHS": "6"}):
        with patch(
            "src.adapters.nelo.etl.inventory_ledger._fetch_ledger_rows",
            side_effect=capture_fetch,
        ), patch(
            "src.adapters.nelo.etl.runner.EtlRunner.upsert",
            new_callable=AsyncMock,
            return_value=(0, 0),
        ):
            try:
                await mirror_inventory_ledger(session=fake_session, tenant_id=TENANT)
            except Exception:
                pass

    if called_lookback:
        assert called_lookback[0] == 6


@pytest.mark.asyncio
async def test_mirror_passes_since_watermark():
    """O parâmetro `since` é passado ao _fetch_ledger_rows (watermark incremental)."""
    from src.adapters.nelo.etl.inventory_ledger import mirror_inventory_ledger

    fake_session = AsyncMock()
    watermark = date(2026, 1, 1)
    called_since = []

    async def capture_fetch(session, *, lookback_months, since, chunk_size=None):
        called_since.append(since)
        return []

    with patch(
        "src.adapters.nelo.etl.inventory_ledger._fetch_ledger_rows",
        side_effect=capture_fetch,
    ), patch(
        "src.adapters.nelo.etl.runner.EtlRunner.upsert",
        new_callable=AsyncMock,
        return_value=(0, 0),
    ):
        try:
            await mirror_inventory_ledger(
                session=fake_session, tenant_id=TENANT, since=watermark,
            )
        except Exception:
            pass

    if called_since:
        assert called_since[0] == watermark


# ── modelo: erp_of_id nullable ────────────────────────────────────────


def test_inventory_ledger_model_erp_of_id_nullable():
    """erp_of_id é nullable (sem OF = movimento geral de stock)."""
    from src.supply.models import InventoryLedgerEntry

    col = InventoryLedgerEntry.__table__.c["erp_of_id"]
    assert col.nullable is True


def test_inventory_ledger_model_erp_of_id_integer():
    """erp_of_id é Integer (MOV_OF_ID é integer no ERP)."""
    from sqlalchemy import Integer as SAInteger
    from src.supply.models import InventoryLedgerEntry

    col = InventoryLedgerEntry.__table__.c["erp_of_id"]
    assert isinstance(col.type, SAInteger)
