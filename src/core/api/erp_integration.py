"""Q.44.Z — API de configuração da Integração ERP.

A ligação ao ERP NELO (URL da API Laravel + token, flags de tempo-real e
escrita) deixa de viver em ficheiros `.env` e passa a ser editável numa
página das Configurações. Os valores são guardados em
`core.tenant_configuration` (categoria `system`, chaves prefixadas `erp.`)
via o `TenantConfigService` — versionado e auditado como qualquer config.

**O token é write-only no limite da API:** o `GET` nunca o devolve em
claro — só diz se está definido e mostra os últimos 4 caracteres. Um
`PUT` sem token não apaga o que já lá está.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.tenant_configuration import (
    CATEGORY_SYSTEM,
    DATA_TYPE_BOOL,
    DATA_TYPE_INT,
    DATA_TYPE_STRING,
)
from src.core.services.tenant_config_service import TenantConfigService
from src.shared.auth.headers import require_tenant_header, require_user_uuid
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/erp-integration", tags=["Config"])

# Chaves em `core.tenant_configuration`, categoria `system`.
_K_URL = "erp.api_url"
_K_TOKEN = "erp.api_token"
_K_RT_ENABLED = "erp.realtime_enabled"
_K_RT_INTERVAL = "erp.realtime_interval_minutes"
_K_WRITE_ENABLED = "erp.write_enabled"

_DEFAULT_INTERVAL = 5


class ErpIntegrationOut(BaseModel):
    """Estado da config — NUNCA inclui o token em claro."""

    api_url: Optional[str] = None
    token_set: bool = False
    token_hint: Optional[str] = Field(
        None, description="Últimos 4 caracteres do token, se definido."
    )
    realtime_enabled: bool = False
    realtime_interval_minutes: int = _DEFAULT_INTERVAL
    write_enabled: bool = False


class ErpIntegrationIn(BaseModel):
    """Campos a actualizar — todos opcionais (PUT parcial).

    `api_token` é write-only: se vier preenchido, substitui o token; se
    vier `None`/vazio, o token actual mantém-se intacto.
    """

    api_url: Optional[str] = Field(None, max_length=500)
    api_token: Optional[str] = Field(None, max_length=500)
    realtime_enabled: Optional[bool] = None
    realtime_interval_minutes: Optional[int] = Field(None, ge=1, le=120)
    write_enabled: Optional[bool] = None


class ErpConnectionTestOut(BaseModel):
    sql_server_ok: bool
    sql_server_detail: str
    api_ok: bool
    api_detail: str


async def _read_config(svc: TenantConfigService) -> dict:
    """Lê as chaves `erp.*` da categoria `system`."""
    values = await svc.get_category(CATEGORY_SYSTEM)
    return {k: v for k, v in values.items() if k.startswith("erp.")}


@router.get("", response_model=ErpIntegrationOut)
async def get_erp_integration(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ErpIntegrationOut:
    """Estado actual da Integração ERP. O token nunca volta em claro."""
    svc = TenantConfigService(session, tenant_id)
    cfg = await _read_config(svc)
    token = cfg.get(_K_TOKEN) or ""
    return ErpIntegrationOut(
        api_url=cfg.get(_K_URL) or None,
        token_set=bool(token),
        token_hint=(f"…{token[-4:]}" if len(token) >= 4 else None),
        realtime_enabled=bool(cfg.get(_K_RT_ENABLED, False)),
        realtime_interval_minutes=int(
            cfg.get(_K_RT_INTERVAL, _DEFAULT_INTERVAL) or _DEFAULT_INTERVAL
        ),
        write_enabled=bool(cfg.get(_K_WRITE_ENABLED, False)),
    )


@router.put("", response_model=ErpIntegrationOut)
async def update_erp_integration(
    body: ErpIntegrationIn,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: UUID = Depends(require_user_uuid),
    session: AsyncSession = Depends(get_session),
) -> ErpIntegrationOut:
    """Actualiza a config. PUT parcial — só escreve os campos enviados.

    O `api_token` só é escrito quando vem preenchido (write-only): um PUT
    sem token preserva o token existente.
    """
    svc = TenantConfigService(session, tenant_id)

    writes: list[tuple[str, object, str]] = []
    if body.api_url is not None:
        writes.append((_K_URL, body.api_url.strip(), DATA_TYPE_STRING))
    if body.api_token is not None and body.api_token.strip():
        # Write-only: token vazio não apaga; só um valor real substitui.
        writes.append((_K_TOKEN, body.api_token.strip(), DATA_TYPE_STRING))
    if body.realtime_enabled is not None:
        writes.append((_K_RT_ENABLED, body.realtime_enabled, DATA_TYPE_BOOL))
    if body.realtime_interval_minutes is not None:
        writes.append(
            (_K_RT_INTERVAL, body.realtime_interval_minutes, DATA_TYPE_INT)
        )
    if body.write_enabled is not None:
        writes.append((_K_WRITE_ENABLED, body.write_enabled, DATA_TYPE_BOOL))

    for key, value, data_type in writes:
        await svc.set(
            category=CATEGORY_SYSTEM,
            key=key,
            value=value,
            user_id=user_id,
            data_type=data_type,
        )
    # `set` não comita — o caller (get_session) fecha a transacção.
    await session.commit()

    return await get_erp_integration(tenant_id=tenant_id, session=session)


@router.post("/test", response_model=ErpConnectionTestOut)
async def test_erp_connection(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ErpConnectionTestOut:
    """Testa a ligação ao ERP: ping read-only ao SQL Server + ping HTTP à
    API Laravel (se houver URL configurada). Devolve OK/erro legível —
    nunca rebenta."""
    # 1. SQL Server (read-only) — usa o adaptador NELO já existente.
    sql_ok, sql_detail = False, ""
    try:
        from src.adapters.nelo import services

        value = await services._fetch_scalar("SELECT 1")
        sql_ok = value == 1
        sql_detail = "SQL Server respondeu" if sql_ok else "resposta inesperada"
    except Exception as exc:  # pragma: no cover - depende do ERP
        sql_detail = f"falhou: {str(exc)[:160]}"

    # 2. API HTTP Laravel — só se houver URL.
    svc = TenantConfigService(session, tenant_id)
    cfg = await _read_config(svc)
    api_url = (cfg.get(_K_URL) or "").strip()
    api_ok, api_detail = False, "sem URL de API configurada"
    if api_url:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(api_url)
            api_ok = resp.status_code < 500
            api_detail = f"HTTP {resp.status_code}"
        except Exception as exc:  # pragma: no cover - depende da rede
            api_detail = f"falhou: {str(exc)[:160]}"

    return ErpConnectionTestOut(
        sql_server_ok=sql_ok,
        sql_server_detail=sql_detail,
        api_ok=api_ok,
        api_detail=api_detail,
    )


__all__ = ["router"]
