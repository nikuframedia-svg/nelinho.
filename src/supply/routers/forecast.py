"""
Supply forecast endpoints — `/v1/supply/forecast` + stockout-forecast.

Q.67.6.B4 — extracted from the 1009-line god-module ``src/supply/api.py``.
Collaborators (``ARIMAForecaster``, ``InventoryLedger``, ``StockoutPredictor``)
are resolved lazily through ``src.supply.api`` so that characterization
tests' ``patch.object(supply_api, "ARIMAForecaster")`` continues to swap
the class actually used at request time.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

from ._common import (
    ForecastRequest,
    ForecastResponse,
    StockoutForecastResponse,
)


router = APIRouter(tags=["Supply Chain"])


@router.post("/forecast", response_model=ForecastResponse)
async def forecast_demand(
    request: ForecastRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Generate demand forecast for a SKU."""
    # Lazy lookup: characterization tests patch ``supply_api.ARIMAForecaster``.
    from src.supply import api as supply_api

    forecaster = supply_api.ARIMAForecaster()

    result = await forecaster.forecast(
        sku_id=request.sku_id,
        historical_data=[p.model_dump() for p in request.historical_data],
        periods_ahead=request.periods_ahead,
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result,
        )

    return ForecastResponse(
        sku_id=request.sku_id,
        forecast=result.get("forecast", []),
        method=result.get("method"),
        quality=result.get("quality"),
        extra={k: v for k, v in result.items() if k not in {"forecast", "method", "quality"}},
    )


@router.get(
    "/materials/{sku_id}/stockout-forecast",
    response_model=StockoutForecastResponse,
)
async def get_stockout_forecast(
    sku_id: str,
    window_days: int = 90,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Q.53.D — data prevista de rutura a partir do consumo histórico real.

    Em vez da heurística `on_hand / avg_daily_demand` configurada à mão,
    estima o consumo médio diário a partir do ledger de movimentos reais
    (`InventoryLedgerEntry`, transaction_type="consume") numa janela
    móvel, e devolve a `predicted_stockout_date` com um nível de
    confiança. Sem histórico suficiente devolve a data `null` com
    `confidence="none"` — honesto, sem inventar.
    """
    if window_days < 7 or window_days > 730:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="window_days must be in [7, 730]",
        )

    from src.supply import api as supply_api

    ledger = supply_api.InventoryLedger(session, tenant_id)
    on_hand = float(await ledger.get_current_on_hand(sku_id))

    predictor = supply_api.StockoutPredictor(session, tenant_id, window_days=window_days)
    result = await predictor.predict(sku_id=sku_id, on_hand=on_hand)

    return StockoutForecastResponse(
        sku_id=result["sku_id"],
        predicted_stockout_date=result["predicted_stockout_date"],
        confidence=result["confidence"],
        avg_daily_consumption=result["avg_daily_consumption"],
        history_days=result["history_days"],
        total_consumed=result["total_consumed"],
        window_days=result["window_days"],
        days_to_stockout=result["days_to_stockout"],
        on_hand=on_hand,
        reason=result["reason"],
        method=result["method"],
    )
