"""Q.173.Z/AA — Endpoints de previsão de ruturas e consumo por modelo.

GET /v1/supply/shortage-forecast
GET /v1/supply/consumption-by-model/{model_id}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

router = APIRouter(tags=["Supply Chain"])


# ---------------------------------------------------------------------------
# Schemas de resposta
# ---------------------------------------------------------------------------

class OrdemAfetadaOut(BaseModel):
    order_id: str
    modelo: str
    start_time: str


class MaterialEmRiscoOut(BaseModel):
    product_code: str
    product_name: str
    stock_atual: float
    stock_negativo_erp: bool = Field(
        description="True se o ERP reporta stock negativo — dado real, não erro"
    )
    min_stock: float
    min_stock_source: str = Field(
        description="Origem do mínimo: 'erp' | 'manual' | 'default'"
    )
    data_rutura_prevista: Optional[str]
    defice: float = Field(description="Qty em falta até à data de rutura")
    ordens_afetadas: List[OrdemAfetadaOut] = Field(
        description="Até 5 ordens cujas ops consomem este material antes da rutura"
    )
    sugestao: str = Field(
        description="'compra' | 'transferencia' | 'replaneamento' | 'ok'"
    )
    sugestao_detalhe: str
    lead_time_days: int
    lead_time_source: str = Field(
        description="Origem do lead time: 'erp' | 'manual' | 'default'"
    )
    data_limite_encomenda: Optional[str] = Field(
        description="Data-limite para encomender (rutura - lead_time); null se transferência"
    )
    outros_armazens: List[Dict[str, Any]] = Field(
        description="Stock nos outros armazéns do mesmo produto (para avaliação de transferência)"
    )
    consumo_mediano_por_barco: Optional[float] = Field(
        description="Mediana histórica de consumo por OF (contexto para validação humana)"
    )


class ShortageforecastOut(BaseModel):
    materiais_em_risco: List[MaterialEmRiscoOut]
    total_em_risco: int
    excluidos_sem_stock_rastreado: int = Field(
        description=(
            "Pseudo-componentes excluídos (sem linha em warehouse_stock e sem "
            "movimentos físicos — ex. 'Gastos Gerais', 'Mão de Obra')"
        )
    )
    horizonte_dias: int
    commit_sha: Optional[str]
    commit_ops: int
    gerado_em: str
    fontes: List[str]


class ConsumoMaterialOut(BaseModel):
    product_code: str
    product_name: str
    mediana_qty_por_of: Optional[float]
    moda_qty_por_of: Optional[float]
    n_ofs: int


class ConsumptionByModelOut(BaseModel):
    model_id: int
    model_name: str
    materiais: List[ConsumoMaterialOut]
    total_materiais: int
    gerado_em: str
    fonte: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/shortage-forecast",
    response_model=ShortageforecastOut,
    summary="Previsão de ruturas de material (Q.173.Z)",
    description=(
        "Projeta a posição de stock de cada material no horizonte pedido, "
        "cruzando o plano CPO atual com BOM, POs OPEN e reservas abertas. "
        "Stock negativo do ERP é mostrado como dado real (flag stock_negativo_erp). "
        "Estimativas de ETA estão etiquetadas (eta_estimada via sugestao_detalhe). "
        "Materiais sem stock rastreado (pseudo-componentes) são contados mas excluídos."
    ),
)
async def get_shortage_forecast(
    horizonte_dias: int = Query(
        default=60,
        ge=7,
        le=365,
        description="Horizonte de projeção em dias (default 60)",
    ),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ShortageforecastOut:
    from src.supply.services.shortage_forecast_service import ShortageForecastService

    svc = ShortageForecastService(session, tenant_id)
    result = await svc.forecast(horizonte_dias=horizonte_dias)
    return ShortageforecastOut(**result.to_dict())


@router.get(
    "/consumption-by-model/{model_id}",
    response_model=ConsumptionByModelOut,
    summary="Consumo histórico por modelo (Q.173.AA)",
    description=(
        "Mediana e moda de consumo de cada material por OF de um modelo. "
        "Fonte: factory_raw.movimento TPMOV=11 (consumo real de OF). "
        "Sem histórico devolve lista vazia — honesto, sem inventar."
    ),
)
async def get_consumption_by_model(
    model_id: int,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ConsumptionByModelOut:
    from src.supply.services.consumption_by_model_service import ConsumptionByModelService

    if model_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="model_id deve ser um inteiro positivo",
        )

    svc = ConsumptionByModelService(session, tenant_id)
    result = await svc.by_model(model_id)
    return ConsumptionByModelOut(**result.to_dict())
