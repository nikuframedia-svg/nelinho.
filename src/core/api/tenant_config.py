"""
ProdPlan ONE - Tenant Configuration API (Sprint L.3)
=====================================================

REST surface over `TenantConfigService`. Admin-only. The API is minimal by
design — it exposes only the operations the Timeline UI and seeder need:
read by category, single set, bulk set, history, rollback, snapshot
import/export.

NOTE ON ROUTE ORDERING: FastAPI matches routes in declaration order. Literal
sub-paths (`/bulk`, `/rollback/...`, `/snapshot/...`) MUST be declared before
the generic `/{category}` and `/{category}/{key}` routes or they'll be
swallowed by the path-param match.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.tenant_config_service import (
    TenantConfigNotFoundError,
    TenantConfigService,
    TenantConfigValidationError,
)
from src.shared.database import get_session

router = APIRouter(prefix="/v1/config", tags=["Config"])


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


def get_user_id(x_user_id: Optional[UUID] = Header(None, alias="X-User-Id")) -> Optional[UUID]:
    """Optional actor for audit. Real auth is wired in Sprint Y (Keycloak)."""
    return x_user_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ConfigEntryOut(BaseModel):
    id: UUID
    category: str
    key: str
    value: Any
    data_type: str
    valid_from: datetime
    valid_to: Optional[datetime]
    last_modified_by: Optional[UUID]
    last_modified_at: datetime


class ConfigSetIn(BaseModel):
    value: Any
    data_type: str = Field(..., description="int|float|bool|string|json|duration|currency")


class ConfigBulkEntry(BaseModel):
    category: str
    key: str
    value: Any
    data_type: str


class ConfigBulkIn(BaseModel):
    entries: list[ConfigBulkEntry]


class CategoryValuesOut(BaseModel):
    category: str
    values: dict[str, Any]


def _to_out(row) -> ConfigEntryOut:
    return ConfigEntryOut(
        id=row.id,
        category=row.category,
        key=row.key,
        value=row.raw_value,
        data_type=row.data_type,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        last_modified_by=row.last_modified_by,
        last_modified_at=row.last_modified_at,
    )


# ---------------------------------------------------------------------------
# Literal sub-paths — MUST come first (see module docstring)
# ---------------------------------------------------------------------------

@router.patch("/bulk", response_model=list[ConfigEntryOut])
async def bulk_set(
    body: ConfigBulkIn,
    tenant_id: UUID = Depends(get_tenant_id),
    user_id: Optional[UUID] = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[ConfigEntryOut]:
    svc = TenantConfigService(session, tenant_id)
    try:
        rows = await svc.bulk_set(
            [e.model_dump() for e in body.entries],
            user_id=user_id,
        )
    except TenantConfigValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return [_to_out(r) for r in rows]


@router.post("/rollback/{config_id}", response_model=ConfigEntryOut)
async def rollback(
    config_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    user_id: Optional[UUID] = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> ConfigEntryOut:
    svc = TenantConfigService(session, tenant_id)
    try:
        row = await svc.rollback(config_id, user_id=user_id)
    except TenantConfigNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TenantConfigValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _to_out(row)


@router.get("/snapshot/export")
async def export_snapshot(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    svc = TenantConfigService(session, tenant_id)
    return await svc.export_snapshot()


@router.post("/snapshot/import", response_model=dict)
async def import_snapshot(
    snapshot: dict,
    tenant_id: UUID = Depends(get_tenant_id),
    user_id: Optional[UUID] = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    svc = TenantConfigService(session, tenant_id)
    try:
        count = await svc.import_snapshot(snapshot, user_id=user_id)
    except TenantConfigValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"written": count}


# ---------------------------------------------------------------------------
# Parameterised paths — declared last
# ---------------------------------------------------------------------------

@router.get("/{category}/{key}/history", response_model=list[ConfigEntryOut])
async def get_history(
    category: str,
    key: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> list[ConfigEntryOut]:
    svc = TenantConfigService(session, tenant_id)
    try:
        rows = await svc.history(category, key)
    except TenantConfigValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return [_to_out(r) for r in rows]


@router.get("/{category}/{key}", response_model=ConfigEntryOut)
async def get_key(
    category: str,
    key: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> ConfigEntryOut:
    svc = TenantConfigService(session, tenant_id)
    try:
        rows = await svc.history(category, key)
    except TenantConfigValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    current = next((r for r in rows if r.valid_to is None), None)
    if current is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Config {category}.{key} not set",
        )
    return _to_out(current)


@router.post(
    "/{category}/{key}",
    response_model=ConfigEntryOut,
    status_code=status.HTTP_201_CREATED,
)
async def set_key(
    category: str,
    key: str,
    body: ConfigSetIn,
    tenant_id: UUID = Depends(get_tenant_id),
    user_id: Optional[UUID] = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> ConfigEntryOut:
    svc = TenantConfigService(session, tenant_id)
    try:
        row = await svc.set(
            category=category,
            key=key,
            value=body.value,
            user_id=user_id,
            data_type=body.data_type,
        )
    except TenantConfigValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _to_out(row)


@router.get("/{category}", response_model=CategoryValuesOut)
async def list_category(
    category: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> CategoryValuesOut:
    """Return `{key: value}` for all active keys in the category."""
    svc = TenantConfigService(session, tenant_id)
    try:
        values = await svc.get_category(category)
    except TenantConfigValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return CategoryValuesOut(category=category, values=values)
