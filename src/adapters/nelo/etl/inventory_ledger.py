"""Q.64.A — inventory ledger mirror (ERP → supply.inventory_ledger_entries).

Desbloqueia o endpoint `shortage-risks` que devolvia `items=[]` porque
a tabela `supply.inventory_ledger_entries` estava a 0 linhas.

A fonte canónica é `dbo.MOVIMENTO` (12M linhas, view 12 meses). Cada
movimento representa uma entrada (recepção fornecedor) ou saída
(consumo, ajuste). O `balance_quantity` da view é o saldo ERP após
o movimento — usamos directo para `qty_closing`.

Mapping:
  * `movement_id` (int)           → `reference_id` (UUID determinístico via uuid5)
  * `moved_at`                    → `date`
  * `product_id` (int)            → `sku_id` (string)
  * `quantity` + `movement_type_id` → `qty_in` / `qty_out` consoante tipo
  * `balance_quantity`            → `qty_closing` (saldo ERP)
  * `qty_closing - qty_in + qty_out` → `qty_opening` (computado)

`movement_type_id == 9` é "Pedidos a fornecedor" → recepção → `qty_in`,
`transaction_type='receive'`. Outros tipos → consumo → `qty_out`,
`transaction_type='consume'` (com excepção de `is_adjustment=True` →
`transaction_type='adjust'`).

Idempotente: upsert por `(tenant_id, reference_id)`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from src.adapters.nelo import services
from src.adapters.nelo.schemas import MovementRow
from src.supply.models import InventoryLedgerEntry

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Namespace UUID determinístico para gerar UUID de cada movement_id.
# Permite re-runs idempotentes — mesmo movement_id sempre dá mesmo UUID.
_MOVEMENT_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
_Q6 = Decimal("0.000001")


def _movement_uuid(movement_id: int) -> UUID:
    """UUID determinístico para um movement_id (uuid5)."""
    return uuid.uuid5(_MOVEMENT_NAMESPACE, f"erp:movement:{movement_id}")


def _classify_movement(row: MovementRow) -> tuple[str, Decimal, Decimal]:
    """Devolve (transaction_type, qty_in, qty_out) consoante o tipo.

    movement_type_id == 9 ('Pedidos a fornecedor') → receive (qty_in).
    is_adjustment True → adjust (qty_in se positivo, qty_out se negativo).
    Resto → consume (qty_out).
    """
    qty = Decimal(str(row.quantity or 0)).quantize(_Q6)

    if row.is_adjustment:
        if qty >= 0:
            return "adjust", qty, Decimal("0")
        return "adjust", Decimal("0"), -qty

    if row.movement_type_id == 9:
        return "receive", qty if qty >= 0 else Decimal("0"), Decimal("0") if qty >= 0 else -qty

    # Default: consume.
    return "consume", Decimal("0"), qty if qty >= 0 else -qty


def _map_movement(row: MovementRow) -> Optional[Dict[str, Any]]:
    """`MovementRow` → row para `inventory_ledger_entries`."""
    if row.product_id is None or row.movement_id is None:
        return None
    if row.moved_at is None:
        return None

    txn_type, qty_in, qty_out = _classify_movement(row)
    qty_closing = Decimal(str(row.balance_quantity or 0)).quantize(_Q6)
    qty_opening = (qty_closing - qty_in + qty_out).quantize(_Q6)

    return {
        "sku_id": str(row.product_id),
        "date": row.moved_at if isinstance(row.moved_at, datetime) else datetime.combine(
            row.moved_at, datetime.min.time(), tzinfo=timezone.utc,
        ),
        "qty_opening": qty_opening,
        "qty_in": qty_in,
        "qty_out": qty_out,
        "qty_closing": qty_closing,
        "transaction_type": txn_type,
        "reference_id": _movement_uuid(row.movement_id),
    }


async def mirror_inventory_ledger(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror `dbo.MOVIMENTO` view → `supply.inventory_ledger_entries`.

    Q.64.A — desbloqueia shortage-risks. A view do ERP tem 12M linhas
    (12 meses); por defeito faz fetch limit 100 (pode-se subir via env
    `NELINHO_LEDGER_FETCH_LIMIT`).
    """
    import os

    limit = int(os.environ.get("NELINHO_LEDGER_FETCH_LIMIT", "5000"))

    async with EtlRunner(session, tenant_id, source="inventory_ledger") as run:
        rows = await services.list_recent_movements(limit=limit)
        run.count_read(len(rows))

        mapped = [m for m in (_map_movement(r) for r in rows) if m is not None]
        run.count_skipped(len(rows) - len(mapped))

        await run.upsert(
            InventoryLedgerEntry,
            mapped,
            key_fields=["reference_id"],
            update_fields=[
                "sku_id", "date", "qty_opening", "qty_in",
                "qty_out", "qty_closing", "transaction_type",
            ],
        )
        logger.info(
            "inventory_ledger mirror — %d movement(s) processed (read %d)",
            len(mapped), len(rows),
        )

    return run.result


register_mirror("inventory_ledger", mirror_inventory_ledger)
