"""
ProdPlan ONE - BOM API
========================

REST endpoints for Bill of Materials management.

F4.E — todas as escritas (POST/PUT/DELETE) escrevem `core.audit_log` na
mesma transacção (invariante #7, Q.61.18 `audit_change`).

F4.E — DECISÃO (auditoria "BOM endpoints órfãos"): MANTER. O frontend
ainda não consome o bomApi (UI adiada), mas a BOM é dado vivo — a
explosão em plan/engines/bom_adapter lê `core.bom_items` e estes
endpoints são o único CRUD. UI no MasterDataBrowser = outro lote
(frontend). Nota: o PUT→PATCH (consistência REST) também espera por
esse lote — o método tem de mudar em simultâneo com masterDataApi.ts.
"""

from datetime import date
from decimal import Decimal
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from src.core.services.master_data_service import MasterDataService
from .schemas import BOMItemCreate, BOMItemUpdate, BOMItemResponse

router = APIRouter(prefix="/bom", tags=["BOM"])

get_tenant_id = require_tenant_header

# Campos do BOMItem espelhados no audit_log (chave + parametrização da linha).
_AUDITED_FIELDS = (
    "parent_product_id",
    "component_product_id",
    "quantity_per",
    "unit_of_measure",
    "sequence",
    "operation_id",
    "scrap_factor",
    "effective_from",
    "effective_to",
    "bom_version",
    "position_ref",
    "notes",
)


def _audit_value(value: Any) -> Any:
    """Decimal/UUID/date → str para o JSON do audit_log; resto passa."""
    if isinstance(value, (Decimal, UUID, date)):
        return str(value)
    return value


def _snapshot(bom_item: Any) -> dict[str, Any]:
    return {f: _audit_value(getattr(bom_item, f, None)) for f in _AUDITED_FIELDS}


@router.get("/products/{product_id}", response_model=List[BOMItemResponse])
async def get_bom_by_product(
    product_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get BOM for a product."""
    service = MasterDataService(session, tenant_id)
    
    # Verify product exists
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    
    bom_items = await service.get_bom(product_id)
    return bom_items


@router.post("", response_model=BOMItemResponse, status_code=status.HTTP_201_CREATED)
async def create_bom_item(
    data: BOMItemCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Add a BOM item."""
    service = MasterDataService(session, tenant_id)
    
    # Verify parent product exists
    parent_product = await service.get_product(data.parent_product_id)
    if not parent_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent product {data.parent_product_id} not found",
        )
    
    # Verify component product exists
    component_product = await service.get_product(data.component_product_id)
    if not component_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Component product {data.component_product_id} not found",
        )
    
    bom_item = await service.add_bom_item(
        parent_product_id=data.parent_product_id,
        component_product_id=data.component_product_id,
        quantity_per=data.quantity_per,
        sequence=data.sequence,
        scrap_factor=data.scrap_factor,
    )
    
    # Update additional fields if provided
    if data.unit_of_measure:
        bom_item.unit_of_measure = data.unit_of_measure
    if data.operation_id:
        bom_item.operation_id = data.operation_id
    if data.effective_from:
        bom_item.effective_from = data.effective_from
    if data.effective_to:
        bom_item.effective_to = data.effective_to
    if data.bom_version:
        bom_item.bom_version = data.bom_version
    if data.position_ref:
        bom_item.position_ref = data.position_ref
    if data.notes:
        bom_item.notes = data.notes

    await session.flush()
    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="bom_item",
        entity_id=bom_item.id,
        action="INSERT",
        old_values=None,
        new_values=_snapshot(bom_item),
        reason="F4.E — criação de linha BOM via API",
    )
    return bom_item


@router.get("/{bom_id}", response_model=BOMItemResponse)
async def get_bom_item(
    bom_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get BOM item by ID."""
    service = MasterDataService(session, tenant_id)
    bom_item = await service.get_bom_item(bom_id)
    
    if not bom_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BOM item {bom_id} not found",
        )
    
    return bom_item


@router.put("/{bom_id}", response_model=BOMItemResponse)
async def update_bom_item(
    bom_id: UUID,
    data: BOMItemUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Update a BOM item."""
    service = MasterDataService(session, tenant_id)
    bom_item = await service.get_bom_item(bom_id)
    
    if not bom_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BOM item {bom_id} not found",
        )
    
    # Update fields if provided — captura old/new para o audit_log.
    old_values: dict[str, Any] = {}
    new_values: dict[str, Any] = {}
    for field in (
        "quantity_per", "unit_of_measure", "sequence", "operation_id",
        "scrap_factor", "effective_from", "effective_to", "bom_version",
        "position_ref", "notes",
    ):
        value = getattr(data, field)
        if value is None:
            continue
        old_values[field] = _audit_value(getattr(bom_item, field))
        setattr(bom_item, field, value)
        new_values[field] = _audit_value(value)

    await session.flush()
    if new_values:
        await audit_change(
            session,
            tenant_id=tenant_id,
            entity_type="bom_item",
            entity_id=bom_item.id,
            action="UPDATE",
            old_values=old_values,
            new_values=new_values,
            reason="F4.E — actualização de linha BOM via API",
        )
    return bom_item


@router.delete("/{bom_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bom_item(
    bom_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Delete a BOM item."""
    service = MasterDataService(session, tenant_id)
    bom_item = await service.get_bom_item(bom_id)
    
    if not bom_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BOM item {bom_id} not found",
        )

    old_values = _snapshot(bom_item)
    await service.delete_bom_item(bom_id)
    await session.flush()
    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="bom_item",
        entity_id=bom_id,
        action="DELETE",
        old_values=old_values,
        new_values=None,
        reason="F4.E — remoção de linha BOM via API",
    )
    return None








