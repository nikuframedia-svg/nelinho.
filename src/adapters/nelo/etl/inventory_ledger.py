"""Q.64.A / Q.173.F — inventory ledger mirror (espelho local → supply.inventory_ledger_entries).

Q.173.F corrige dois problemas da versão anterior (Q.64.A):
  1. A versão Q.64.A lia o ERP LIVE com limit=5000 → só ~14 dias de
     histórico (a view do ERP devolvia os últimos N movimentos, não uma
     janela temporal). `StockoutPredictor` exige ≥30 dias
     (`_HIGH_CONF_MIN_DAYS=30`) e o rop_calculator lookback 90d — ambos
     famintos com apenas 14 dias.
  2. O campo `MOV_OF_ID` (Ordem de Fabrico) era descartado; necessário
     para consumo-por-barco nas Fases 4/5.

Solução Q.173.F:
  - Lê directamente de `factory_raw.movimento` (espelho local, sem limit
    artificial) com janela de 24 meses (env `NELINHO_LEDGER_LOOKBACK_MONTHS`,
    default 24).
  - Watermark incremental por `MOV_DATA`: re-runs só relêem o delta
    desde o último `synced_from` gravado no env ou passado como `since`.
    O backfill inicial lê 24 meses; corridas subsequentes lêem apenas o
    novo.
  - Preenche `erp_of_id` ← `MOV_OF_ID`.
  - Chunking de 5000 linhas para o backfill inicial (~2,5M linhas).
  - `reference_id` = uuid5(MOV_ID) — idêntico ao actual → idempotente
    com as linhas já existentes (upsert por reference_id, não duplica).

Mapeamento de tipos (`_classify_movement`) mantido intacto — idêntico
ao de Q.64.A para preservar o comportamento pin-testado.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.supply.models import InventoryLedgerEntry

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Namespace UUID determinístico para gerar UUID de cada movement_id.
# IMUTÁVEL — alterar quebra a idempotência com as linhas existentes.
_MOVEMENT_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
_Q6 = Decimal("0.000001")

#: Chunk size para iterar sobre `factory_raw.movimento`.
#: ~2,5M linhas / 5000 = ~500 batches no backfill inicial.
_CHUNK_SIZE = 5000


def _movement_uuid(movement_id: int) -> UUID:
    """UUID determinístico para um movement_id (uuid5).

    IMUTÁVEL — mesmo namespace e prefixo que Q.64.A para garantir
    idempotência com as 34.076 linhas já existentes.
    """
    return uuid.uuid5(_MOVEMENT_NAMESPACE, f"erp:movement:{movement_id}")


# ---------------------------------------------------------------------------
# Classificação de movimentos (idêntica a Q.64.A — pin-testada)
# ---------------------------------------------------------------------------


def _classify_movement(
    movement_type_id: Optional[int],
    is_adjustment: bool,
    quantity: float,
) -> tuple[str, Decimal, Decimal]:
    """Devolve (transaction_type, qty_in, qty_out) consoante o tipo.

    movement_type_id == 9 ('Pedidos a fornecedor') → receive (qty_in).
    is_adjustment True → adjust (qty_in se positivo, qty_out se negativo).
    Resto → consume (qty_out).

    Mantém a lógica exacta de Q.64.A (_classify_movement) para não
    alterar as 34.076 linhas existentes.
    """
    qty = Decimal(str(quantity or 0)).quantize(_Q6)

    if is_adjustment:
        if qty >= 0:
            return "adjust", qty, Decimal("0")
        return "adjust", Decimal("0"), -qty

    if movement_type_id == 9:
        return "receive", qty if qty >= 0 else Decimal("0"), Decimal("0") if qty >= 0 else -qty

    # Default: consume.
    return "consume", Decimal("0"), qty if qty >= 0 else -qty


# ---------------------------------------------------------------------------
# SQL de leitura do espelho local
# ---------------------------------------------------------------------------

_FETCH_LEDGER_SQL = text("""
    SELECT
        m."MOV_ID"             AS movement_id,
        m."MOV_DATA"           AS moved_at,
        m."MOV_P_ID"           AS product_id,
        m."MOV_QUANTIDADE"     AS quantity,
        m."MOV_TPMOV_ID"       AS movement_type_id,
        m."MOV_ACERTO"         AS is_adjustment,
        m."MOV_QTD_BAL"        AS balance_quantity,
        m."MOV_OF_ID"          AS of_id
    FROM factory_raw.movimento m
    WHERE m."MOV_DATA" >= :since_str
      AND m."MOV_DATA" <  :until_str
    ORDER BY m."MOV_ID"
    LIMIT  :chunk_size
    OFFSET :offset
""")


def _since_until_strs(
    lookback_months: int,
    since: Optional[date],
) -> tuple[str, str]:
    """Calcula (since_str, until_str) para o filtro MOV_DATA.

    - Se `since` fornecido (watermark incremental), usa-o como início.
    - Caso contrário, usa NOW() - lookback_months meses.
    - `until_str` é sempre amanhã (inclui hoje inteiro).

    MOV_DATA é texto ISO 'YYYY-MM-DDTHH:MM:SS'; a comparação string-
    ordenada funciona porque o formato é lexicograficamente ordenável.
    """
    from datetime import timedelta

    today = datetime.now(timezone.utc).date()
    until_date = today + timedelta(days=1)  # inclui movimentos de hoje

    if since is not None:
        since_date = since
    else:
        # Aproximação: 30 dias por mês
        since_date = today - timedelta(days=lookback_months * 30)

    return since_date.isoformat(), until_date.isoformat()


async def _fetch_ledger_rows(
    session: AsyncSession,
    *,
    lookback_months: int,
    since: Optional[date],
    chunk_size: int = _CHUNK_SIZE,
) -> List[Dict[str, Any]]:
    """Lê todos os movimentos do espelho local em chunks.

    Devolve lista de dicts com os campos necessários para o mapeamento.
    OFFSET/LIMIT sobre `MOV_ID` ordenado — determinístico para re-runs.
    """
    since_str, until_str = _since_until_strs(lookback_months, since)
    logger.info(
        "inventory_ledger fetch — janela %s → %s", since_str, until_str,
    )

    all_rows: List[Dict[str, Any]] = []
    offset = 0
    params = {
        "since_str": since_str,
        "until_str": until_str,
        "chunk_size": chunk_size,
        "offset": offset,
    }
    while True:
        params["offset"] = offset
        result = await session.execute(_FETCH_LEDGER_SQL, params)
        batch = result.mappings().fetchall()
        if not batch:
            break
        all_rows.extend(dict(r) for r in batch)
        if len(batch) < chunk_size:
            break
        offset += chunk_size

    return all_rows


def _map_ledger_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Raw dict do espelho → linha para `inventory_ledger_entries`.

    Lógica de classificação idêntica a `_map_movement` (Q.64.A) para
    preservar idempotência com as linhas existentes.
    Adiciona `erp_of_id` ← `MOV_OF_ID` (Q.173.F).
    """
    movement_id = row.get("movement_id")
    product_id = row.get("product_id")
    moved_at_raw = row.get("moved_at")

    if movement_id is None or product_id is None or moved_at_raw is None:
        return None

    # MOV_DATA é texto ISO: '2026-06-11T13:30:00'
    try:
        if isinstance(moved_at_raw, str):
            dt = datetime.fromisoformat(moved_at_raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        elif isinstance(moved_at_raw, datetime):
            dt = moved_at_raw if moved_at_raw.tzinfo else moved_at_raw.replace(tzinfo=timezone.utc)
        else:
            # date → datetime midnight UTC
            dt = datetime.combine(moved_at_raw, datetime.min.time(), tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None

    txn_type, qty_in, qty_out = _classify_movement(
        movement_type_id=row.get("movement_type_id"),
        is_adjustment=bool(row.get("is_adjustment")),
        quantity=row.get("quantity") or 0,
    )
    qty_closing = Decimal(str(row.get("balance_quantity") or 0)).quantize(_Q6)
    qty_opening = (qty_closing - qty_in + qty_out).quantize(_Q6)

    of_id = row.get("of_id")

    return {
        "sku_id": str(product_id),
        "date": dt,
        "qty_opening": qty_opening,
        "qty_in": qty_in,
        "qty_out": qty_out,
        "qty_closing": qty_closing,
        "transaction_type": txn_type,
        "reference_id": _movement_uuid(int(movement_id)),
        "erp_of_id": int(of_id) if of_id is not None else None,
    }


async def mirror_inventory_ledger(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror `factory_raw.movimento` → `supply.inventory_ledger_entries`.

    Q.173.F — espelho local, 24 meses, chunking, watermark incremental,
    rastreio por OF (erp_of_id). O uuid5(MOV_ID) é idêntico ao de Q.64.A
    → upsert idempotente com as linhas já existentes.
    """
    lookback_months = int(
        os.environ.get("NELINHO_LEDGER_LOOKBACK_MONTHS", "24")
    )

    async with EtlRunner(session, tenant_id, source="inventory_ledger") as run:
        raw_rows = await _fetch_ledger_rows(
            session,
            lookback_months=lookback_months,
            since=since,
        )
        run.count_read(len(raw_rows))

        mapped: List[Dict[str, Any]] = []
        skipped = 0
        for row in raw_rows:
            m = _map_ledger_row(row)
            if m is None:
                skipped += 1
            else:
                mapped.append(m)
        run.count_skipped(skipped)

        await run.upsert(
            InventoryLedgerEntry,
            mapped,
            key_fields=["reference_id"],
            update_fields=[
                "sku_id", "date", "qty_opening", "qty_in",
                "qty_out", "qty_closing", "transaction_type",
                "erp_of_id",
            ],
        )
        logger.info(
            "inventory_ledger mirror — %d movimento(s) processado(s) "
            "(read %d, skipped %d), lookback %d meses",
            len(mapped), len(raw_rows), skipped, lookback_months,
        )

    return run.result


register_mirror("inventory_ledger", mirror_inventory_ledger)
