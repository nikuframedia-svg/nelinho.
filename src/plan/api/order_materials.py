"""GET /v1/plan/orders/{legacy_id}/materials — materiais restantes por OF (Q.173.U).

Devolve os materiais reservados ainda não consumidos (TPMOV=4 não satisfeitos)
e os já consumidos (TPMOV=11) para uma Ordem de Fabrico, com stock actual
de ``supply.warehouse_stock`` por componente.

Fonte de dados: ``factory_raw.movimento`` (espelho local do ERP NELO).
Estado honesto: OF sem reservas/consumos relevantes → ``items=[]``.
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.services.order_materials_service import OrderMaterialsService
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

router = APIRouter(tags=["PLAN.Orders"])


class MaterialRestanteSchema(BaseModel):
    """Material de uma OF com estado de reserva, consumo e stock."""

    produto_id: int
    produto_nome: Optional[str]
    qty_reservada_aberta: float
    """Quantidade reservada (TPMOV=4, MOV_SATISFEITO=False) ainda por satisfazer."""
    qty_consumida: float
    """Quantidade já consumida (TPMOV=11)."""
    stock_disponivel: Optional[float]
    """Stock actual em warehouse_stock (soma por armazém). Null = sem snapshot ERP."""
    stock_suficiente: Optional[bool]
    """True se stock >= qty_reservada_aberta. Null quando stock_disponivel é null."""


class OrdemMaterialsResponse(BaseModel):
    """Resposta do endpoint de materiais restantes por OF."""

    of_legacy_id: int
    items: List[MaterialRestanteSchema]
    fonte: str
    """Indica a fonte dos dados (movimento(tpmov=4,11))."""
    stock_snapshot_disponivel: bool
    """True quando supply.warehouse_stock tem dados (ETL de stock correu)."""


@router.get(
    "/orders/{legacy_id}/materials",
    response_model=OrdemMaterialsResponse,
    summary="Materiais restantes por OF",
    description=(
        "Devolve os materiais reservados ainda não consumidos (TPMOV=4 não satisfeitos) "
        "e os já consumidos (TPMOV=11) para a Ordem de Fabrico indicada. "
        "Stock actual cruzado com supply.warehouse_stock. "
        "Lista vazia quando a OF não tem movimentos relevantes — nunca inventa dados."
    ),
)
async def get_order_materials(
    legacy_id: int,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> OrdemMaterialsResponse:
    """Materiais restantes para a OF `legacy_id`.

    `legacy_id` é o inteiro do ERP (MOV_OF_ID em factory_raw.movimento).
    Devolve 404 apenas quando o endpoint é chamado com formato inválido;
    OF sem movimentos devolve 200 com `items=[]` (estado honesto).
    """
    svc = OrderMaterialsService(session, tenant_id)
    try:
        result = await svc.materiais_restantes(legacy_id)
    except Exception as exc:  # noqa: BLE001  # fronteira HTTP: re-levanta como 503 honesto
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro ao consultar materiais da OF {legacy_id}: {exc}",
        ) from exc

    return OrdemMaterialsResponse(
        of_legacy_id=result.of_legacy_id,
        items=[
            MaterialRestanteSchema(
                produto_id=item.produto_id,
                produto_nome=item.produto_nome,
                qty_reservada_aberta=item.qty_reservada_aberta,
                qty_consumida=item.qty_consumida,
                stock_disponivel=item.stock_disponivel,
                stock_suficiente=item.stock_suficiente,
            )
            for item in result.items
        ],
        fonte=result.fonte,
        stock_snapshot_disponivel=result.stock_snapshot_disponivel,
    )
