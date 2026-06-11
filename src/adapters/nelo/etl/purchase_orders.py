"""Q.64.D / Q.173.E — purchase_orders mirror (espelho local → supply.purchase_orders).

Q.173.E corrige dois problemas da versão anterior (Q.64.D):
  1. A versão Q.64.D lia o ERP LIVE com limit=5000 e filtrava tipo 9 em
     Python → cobria ~2% das POs dos últimos 12 meses (138 de ~5.987).
  2. Fabricava `eta = ordered_at + 30d` para 100% das linhas.
  3. Supplier_name ficava como "Fornecedor {id}" em vez do nome real.

Solução Q.173.E:
  - Lê directamente de `factory_raw.movimento` (espelho local, sem limit
    artificial) com JOIN a `factory_raw.entidade` para o nome do fornecedor
    e a `factory_raw.produto` para o nome do produto.
  - `eta = None` — sem ETA inventada. Os leitores do modelo já são
    NULL-safe (purchase_order_service.py usa `po.eta is not None`).
  - Janela: 12 meses (env `NELINHO_PURCHASE_ORDERS_LOOKBACK_MONTHS`,
    default 12).
  - Chunking: lê em blocos de 2000 para não sobrecarregar a sessão.
  - Idempotente: upsert por `(tenant_id, erp_movement_id)`.

`qty_received` mantém-se 0: as recepções vivem em dbo.MOVIMENTO_FORNECEDOR,
sem acesso ainda — ver comentário inline.

Gate `sqlserver_enabled` mantém-se inalterado (o espelho só está fresco
quando o sync NELO corre).
"""

from __future__ import annotations

import logging
import os
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.supply.models import PO_STATUS_OPEN, PurchaseOrder

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

#: Movement type "Pedidos a fornecedor" — `dbo.TIPO_MOVIMENTO.TPMOV_ID=9`.
_PO_MOVEMENT_TYPE_ID = 9

_Q6 = Decimal("0.000001")

#: Chunk size para iterar sobre `factory_raw.movimento` sem sobrecarregar
#: a sessão. ~5.987 linhas/12 meses → 3 batches de 2000.
_CHUNK_SIZE = 2000


# ---------------------------------------------------------------------------
# SQL de leitura do espelho local
# ---------------------------------------------------------------------------

_FETCH_POS_SQL = text("""
    SELECT
        m."MOV_ID"             AS movement_id,
        m."MOV_DATA"           AS moved_at,
        m."MOV_P_ID"           AS product_id,
        m."MOV_E_ID"           AS entity_id,
        m."MOV_QUANTIDADE"     AS quantity,
        e."E_NOME"             AS supplier_name,
        p."P_NOME"             AS product_name
    FROM factory_raw.movimento m
    LEFT JOIN factory_raw.entidade e ON e."E_ID" = m."MOV_E_ID"
    LEFT JOIN factory_raw.produto  p ON p."P_ID" = m."MOV_P_ID"
    WHERE m."MOV_TPMOV_ID" = :movement_type
      AND m."MOV_DATA"     >= to_char(
              NOW() - (:lookback_months * INTERVAL '1 month'),
              'YYYY-MM-DD'
          )
    ORDER BY m."MOV_ID"
    LIMIT  :chunk_size
    OFFSET :offset
""")


async def _fetch_po_rows(
    session: AsyncSession,
    *,
    lookback_months: int,
    chunk_size: int = _CHUNK_SIZE,
) -> List[Dict[str, Any]]:
    """Lê todos os movimentos tipo 9 do espelho local em chunks.

    Devolve lista de dicts com os campos necessários para o mapeamento.
    Usa OFFSET/LIMIT sobre `MOV_ID` ordenado — determinístico para
    re-runs (o espelho é append-only durante o sync).
    """
    all_rows: List[Dict[str, Any]] = []
    offset = 0
    params = {
        "movement_type": _PO_MOVEMENT_TYPE_ID,
        "lookback_months": lookback_months,
        "chunk_size": chunk_size,
        "offset": offset,
    }
    while True:
        params["offset"] = offset
        result = await session.execute(_FETCH_POS_SQL, params)
        batch = result.mappings().fetchall()
        if not batch:
            break
        all_rows.extend(dict(r) for r in batch)
        if len(batch) < chunk_size:
            break
        offset += chunk_size
    return all_rows


def _map_raw_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Raw dict do espelho → linha para `supply.purchase_orders`.

    Devolve `None` quando faltam campos essenciais.
    """
    movement_id = row.get("movement_id")
    product_id = row.get("product_id")
    moved_at_raw = row.get("moved_at")

    if movement_id is None or product_id is None or moved_at_raw is None:
        return None

    # MOV_DATA é texto ISO: '2026-06-11T13:30:00'
    try:
        if isinstance(moved_at_raw, str):
            ordered_at = date.fromisoformat(moved_at_raw[:10])
        else:
            # datetime ou date directos (ex: testes com mocks)
            ordered_at = (
                moved_at_raw.date()
                if hasattr(moved_at_raw, "date")
                else moved_at_raw
            )
    except (ValueError, TypeError):
        return None

    qty_ordered = Decimal(str(row.get("quantity") or 0)).quantize(_Q6)

    # Supplier_name real (JOIN a entidade); fallback apenas se o JOIN não
    # devolver nome (entidade sem nome ou entity_id NULL).
    entity_id = row.get("entity_id")
    supplier_name_raw = row.get("supplier_name")
    if supplier_name_raw:
        supplier_name = str(supplier_name_raw)[:255]
    elif entity_id:
        supplier_name = f"E_{entity_id}"
    else:
        supplier_name = "Fornecedor desconhecido"

    product_name_raw = row.get("product_name")
    product_name = str(product_name_raw)[:255] if product_name_raw else None

    return {
        "erp_movement_id": int(movement_id),
        "po_number": f"PO-{int(movement_id)}",
        "supplier_name": supplier_name,
        "supplier_erp_id": int(entity_id) if entity_id else None,
        "product_code": str(product_id),
        "product_name": product_name,
        "qty_ordered": qty_ordered,
        # qty_received mantém-se 0: as recepções vivem em
        # dbo.MOVIMENTO_FORNECEDOR, ainda sem acesso — pergunta pendente
        # ao Luis. Não inventamos um valor.
        "qty_received": Decimal("0"),
        "unit_of_measure": "UN",
        "ordered_at": ordered_at,
        # eta=None — sem ETA inventada. Q.173.E elimina o placeholder +30d.
        # Os leitores (purchase_order_service.py) já são NULL-safe.
        "eta": None,
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
    """Mirror `factory_raw.movimento WHERE MOV_TPMOV_ID=9` → `supply.purchase_orders`.

    Q.173.E — usa o espelho local (sem limit artificial, com JOIN real a
    entidade/produto) e remove a ETA fictícia.
    Janela configurável via `NELINHO_PURCHASE_ORDERS_LOOKBACK_MONTHS`
    (default 12).
    """
    lookback_months = int(
        os.environ.get("NELINHO_PURCHASE_ORDERS_LOOKBACK_MONTHS", "12")
    )

    async with EtlRunner(session, tenant_id, source="purchase_orders") as run:
        raw_rows = await _fetch_po_rows(
            session, lookback_months=lookback_months,
        )
        run.count_read(len(raw_rows))

        mapped: List[Dict[str, Any]] = []
        skipped = 0
        for row in raw_rows:
            m = _map_raw_row(row)
            if m is None:
                skipped += 1
            else:
                mapped.append(m)
        run.count_skipped(skipped)

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
            "purchase_orders mirror — %d PO(s) mapped (read %d, skipped %d), "
            "lookback %d meses",
            len(mapped), len(raw_rows), skipped, lookback_months,
        )

    return run.result


register_mirror("purchase_orders", mirror_purchase_orders)
