"""Q.64.D — purchase_orders mirror (ERP → supply.purchase_orders).

Desbloqueia o endpoint `GET /v1/supply/purchase-orders` que devolvia
`data_available=false` porque `supply.purchase_orders` estava a 0 linhas.
A tab Entregas (Materiais page) depende deste mirror para mostrar o
tracking de encomendas a fornecedor com fornecedor, material, qty
encomendada vs recebida, ETA e estado de recepção.

A fonte canónica é `dbo.MOVIMENTO WHERE MOV_TPMOV_ID=9` ("Pedidos a
fornecedor"). Cada movimento desse tipo é uma encomenda a fornecedor;
o ERP NELO mantém um único registo por encomenda (não há receipt
tracking granular na MOVIMENTO em si — isso vive na MOVIMENTO_FORNECEDOR
que não está no scope deste mirror).

Estratégia: filtramos inline em Python o resultado de
`services.list_recent_movements()` por `movement_type_id == 9` — evita
adicionar uma nova função NELO só para isto e mantém a janela de 12
meses da view.

Mapping concreto:

* `movement_id`              → `erp_movement_id` (idempotency key)
* `f"PO-{movement_id}"`      → `po_number` (slug determinístico)
* `entity_id`                → `supplier_erp_id`
* `f"Fornecedor {entity_id}"` → `supplier_name` (placeholder; lookup
                                ENTIDADE futuro — TODO Q.65+)
* `product_id`               → `product_code` (string)
* `quantity`                 → `qty_ordered`
* 0                          → `qty_received` (até haver receipt tracking)
* `moved_at`                 → `ordered_at`
* `moved_at + 30 dias`       → `eta` (placeholder; ETA real vive em
                                MOVIMENTO_FORNECEDOR.MOVFOR_ETA — TODO)
* "ORDERED" (legacy alias)   → na verdade `PO_STATUS_OPEN` ("OPEN")
* "EUR"                      → `currency_code` (não persistido — model
                                não tem coluna; mantemos só `unit_cost`
                                em €)

Idempotente: upsert por `(tenant_id, erp_movement_id)`.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.adapters.nelo import services
from src.adapters.nelo.schemas import MovementRow
from src.supply.models import PO_STATUS_OPEN, PurchaseOrder

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

#: Movement type for "Pedidos a fornecedor" (supplier purchase orders).
#: Defined in `dbo.TIPO_MOVIMENTO` (MAR-KAYAKS ERP) — see
#: `agent_docs/mar_kayaks_schema_discovery.md`.
_PO_MOVEMENT_TYPE_ID = 9

#: ETA placeholder lead-time (days). The ERP keeps the real ETA on
#: `dbo.MOVIMENTO_FORNECEDOR.MOVFOR_ETA`, a separate table not yet
#: covered by an adapter service. 30d matches the factory's typical
#: lead time for non-critical raw materials.
_ETA_PLACEHOLDER_DAYS = 30

_Q6 = Decimal("0.000001")


def _map_movement_to_po(row: MovementRow) -> Optional[Dict[str, Any]]:
    """`MovementRow` → linha para `supply.purchase_orders`.

    Devolve `None` quando o movimento não é uma PO (tipo != 9), ou
    quando faltam campos essenciais (movement_id, product_id, moved_at).
    O upsert ignora `None` — `mirror_purchase_orders` filtra a lista.
    """
    if row.movement_type_id != _PO_MOVEMENT_TYPE_ID:
        return None
    if row.movement_id is None:
        return None
    if row.product_id is None:
        return None
    if row.moved_at is None:
        return None

    qty_ordered = Decimal(str(row.quantity or 0)).quantize(_Q6)
    # `unit_price` em € no ERP. O model `PurchaseOrder` (Q.53.D) ainda
    # não tem coluna `unit_cost`/`total_cost`; quando for adicionada,
    # o mapping abaixo enriquece a row. Por agora a precisão fica no
    # ERP e o frontend mostra apenas `qty_ordered`. TODO Q.65+.
    _ = Decimal(str(row.unit_price or 0)).quantize(_Q6)  # touch unit_price to surface schema drift

    # `moved_at` é datetime; o model guarda `ordered_at` como Date.
    ordered_at: date = row.moved_at.date()
    eta_at: date = ordered_at + timedelta(days=_ETA_PLACEHOLDER_DAYS)

    # Supplier name placeholder. ENTIDADE lookup é caro (uma query por
    # PO ou um join 30k linhas) — fica para um mirror futuro que
    # popule ENTIDADE local e o JOIN seja local. TODO Q.65+.
    supplier_name = (
        f"Fornecedor {row.entity_id}" if row.entity_id else "Fornecedor desconhecido"
    )

    return {
        "erp_movement_id": int(row.movement_id),
        "po_number": f"PO-{int(row.movement_id)}",
        "supplier_name": supplier_name[:255],
        "supplier_erp_id": int(row.entity_id) if row.entity_id else None,
        "product_code": str(row.product_id),
        "product_name": None,
        "qty_ordered": qty_ordered,
        "qty_received": Decimal("0"),  # no receipt tracking yet
        "unit_of_measure": "UN",
        "ordered_at": ordered_at,
        "eta": eta_at,
        "received_at": None,
        "status": PO_STATUS_OPEN,
        "source": "erp_nelo_movimento",
        "notes": None,
    }


async def mirror_purchase_orders(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror `dbo.MOVIMENTO WHERE MOV_TPMOV_ID=9` → `supply.purchase_orders`.

    Q.64.D — desbloqueia `/v1/supply/purchase-orders`. A view do ERP
    devolve a janela completa (12 meses); filtramos inline por
    `movement_type_id == 9` antes de mapear. Look-back limit por defeito
    5000, override via `NELINHO_PURCHASE_ORDERS_FETCH_LIMIT`.
    """
    import os

    limit = int(os.environ.get("NELINHO_PURCHASE_ORDERS_FETCH_LIMIT", "5000"))

    async with EtlRunner(session, tenant_id, source="purchase_orders") as run:
        rows = await services.list_recent_movements(limit=limit)
        run.count_read(len(rows))

        # Filtramos inline por tipo 9 — no_match não é "skipped" em sentido
        # útil (são saídas/consumos de outro tipo); contamos como skipped
        # os que matcham o tipo mas falham na validação de campos.
        po_candidates: List[MovementRow] = [
            r for r in rows if r.movement_type_id == _PO_MOVEMENT_TYPE_ID
        ]
        non_po = len(rows) - len(po_candidates)

        mapped = [m for m in (_map_movement_to_po(r) for r in po_candidates) if m is not None]
        invalid_po = len(po_candidates) - len(mapped)

        # Skipped = não-PO (esperado, é o filtro) + PO inválidas
        # (movement_id/product_id/moved_at em falta — anomalia ERP).
        run.count_skipped(non_po + invalid_po)

        await run.upsert(
            PurchaseOrder,
            mapped,
            key_fields=["erp_movement_id"],
            update_fields=[
                "po_number",
                "supplier_name",
                "supplier_erp_id",
                "product_code",
                "product_name",
                "qty_ordered",
                "qty_received",
                "unit_of_measure",
                "ordered_at",
                "eta",
                "received_at",
                "status",
                "source",
                "notes",
            ],
        )
        logger.info(
            "purchase_orders mirror — %d PO(s) mapped (read %d, non-po skipped %d, invalid %d)",
            len(mapped), len(rows), non_po, invalid_po,
        )

    return run.result


register_mirror("purchase_orders", mirror_purchase_orders)
