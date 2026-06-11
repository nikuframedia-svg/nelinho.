"""
Supply ROP / ABC endpoints — `/v1/supply/rop/*` + `/abc` + `/rop-configs/recompute`.

Q.67.6.B4 — extracted from ``src/supply/api.py``. ``ROPCalculator``,
``ABCAnalysis`` and ``recompute_rop_configs`` are resolved through
``src.supply.api`` to preserve test patches.

Q.172 (F4.E) — `/rop-configs/recompute` ganhou guarda anti-abuso: o recompute
itera todos os SKUs ativos (queries caras + upserts) e podia ser martelado em
paralelo até exaurir CPU/pool. Agora: janela deslizante por tenant (in-process)
→ 429, timeout explícito → 504, e log INFO com a duração.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

from ._common import (
    ABCAnalysisRequest,
    ABCBucket,
    ABCDistributionResponse,
    ROPSkuResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Supply Chain"])


# ─── Q.172 — guarda do recompute (rate limit in-process por tenant) ────────
#
# Janela deslizante simples com `time.monotonic()` — sem Redis de propósito:
# o objetivo é travar marteladas num endpoint administrativo caro, não quota
# exata multi-worker (com N workers o teto efetivo é N×limite, ainda finito).
# Padrão de referência: src/copilot/rate_limiter.py (sliding window).

_RECOMPUTE_MAX_CALLS = 10          # máx. de recomputes por tenant…
_RECOMPUTE_WINDOW_S = 3600.0       # …por hora (operação administrativa)
_recompute_calls: dict[UUID, deque[float]] = {}


def _check_recompute_rate_limit(tenant_id: UUID) -> None:
    """Levanta 429 quando o tenant excede o limite na janela deslizante."""
    now = time.monotonic()
    calls = _recompute_calls.setdefault(tenant_id, deque())
    while calls and now - calls[0] > _RECOMPUTE_WINDOW_S:
        calls.popleft()
    if len(calls) >= _RECOMPUTE_MAX_CALLS:
        retry_after = int(_RECOMPUTE_WINDOW_S - (now - calls[0])) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Limite de {_RECOMPUTE_MAX_CALLS} recomputes/hora por tenant "
                f"excedido. Tenta novamente em {retry_after}s."
            ),
            headers={"Retry-After": str(retry_after)},
        )
    calls.append(now)


def _reset_rop_recompute_limiter_for_tests() -> None:
    """Limpa o estado do limiter — usar em fixtures de teste."""
    _recompute_calls.clear()


@router.get("/rop/{sku_id}", response_model=ROPSkuResponse)
async def calculate_rop(
    sku_id: str,
    avg_daily_demand: float,
    lead_time_days: int,
    lead_time_std_dev: float,
    service_level: float = 0.95,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Calculate Reorder Point (ROP) for a SKU."""
    if avg_daily_demand < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="avg_daily_demand must be >= 0")
    if lead_time_days < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="lead_time_days must be >= 0")
    if lead_time_std_dev < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="lead_time_std_dev must be >= 0")
    if service_level not in (0.90, 0.95, 0.99):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="service_level must be one of 0.90, 0.95, 0.99",
        )

    from src.supply import api as supply_api

    calculator = supply_api.ROPCalculator()
    result = calculator.calculate_rop(
        avg_daily_demand=avg_daily_demand,
        lead_time_days=lead_time_days,
        lead_time_std_dev=lead_time_std_dev,
        service_level=service_level,
    )

    return ROPSkuResponse(sku_id=sku_id, **result)


@router.post("/abc", response_model=ABCDistributionResponse)
async def calculate_abc_analysis(
    request: ABCAnalysisRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Calculate ABC classification for inventory SKUs."""
    from src.supply import api as supply_api

    analyzer = supply_api.ABCAnalysis()
    result = analyzer.calculate_abc_distribution(
        skus_list=[s.model_dump() for s in request.skus_list],
    )
    return ABCDistributionResponse(
        distribution={
            "A": ABCBucket(count=len(result["A"]), skus=result["A"]),
            "B": ABCBucket(count=len(result["B"]), skus=result["B"]),
            "C": ABCBucket(count=len(result["C"]), skus=result["C"]),
        }
    )


@router.post("/rop-configs/recompute")
async def trigger_rop_recompute(
    lookback_days: int = Query(90, ge=7, le=365),
    service_level: float = Query(0.95, ge=0.8, le=0.999),
    timeout_seconds: int = Query(300, ge=10, le=600),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Q.64.C — recompute ROP configs from inventory_ledger history.

    Le `supply.inventory_ledger_entries` (qty_out, ultimos `lookback_days`)
    + `supply.supply_material_master` (active SKUs), e faz upsert em
    `supply.supply_rop_configs` aplicando a formula classica de inventory
    management. Idempotente: segunda chamada substitui, nao duplica.
    Devolve `{rows_processed, rows_upserted, rows_skipped}`.

    Q.172 — operação cara (itera todos os SKUs ativos): rate limit de
    10/hora por tenant (429) e timeout explícito (504). O timeout cancela
    ANTES do commit — nada fica meio-escrito.
    """
    _check_recompute_rate_limit(tenant_id)

    from src.supply import api as supply_api

    started = time.monotonic()
    try:
        async with asyncio.timeout(timeout_seconds):
            result = await supply_api.recompute_rop_configs(
                session,
                tenant_id,
                lookback_days=lookback_days,
                service_level=service_level,
            )
            await session.commit()
    except TimeoutError as exc:
        duration_s = time.monotonic() - started
        logger.warning(
            "rop_recompute timeout: tenant=%s lookback_days=%d "
            "timeout_seconds=%d duration_seconds=%.1f",
            tenant_id, lookback_days, timeout_seconds, duration_s,
        )
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                f"Recompute excedeu o timeout de {timeout_seconds}s — "
                "nenhuma alteração foi gravada. Reduz lookback_days ou "
                "aumenta timeout_seconds."
            ),
        ) from exc
    duration_s = time.monotonic() - started
    logger.info(
        "rop_recompute: tenant=%s lookback_days=%d service_level=%.3f "
        "rows_processed=%s rows_upserted=%s rows_skipped=%s "
        "duration_seconds=%.1f",
        tenant_id, lookback_days, service_level,
        result.get("rows_processed"), result.get("rows_upserted"),
        result.get("rows_skipped"), duration_s,
    )
    return result
