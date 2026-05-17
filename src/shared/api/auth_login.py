"""POST /v1/auth/login + /v1/auth/refresh — login real (Q.31.G).

Decisão D3 do Luis: operadores autenticam por **password**. O endpoint
recebe email + password, confirma contra `shared.users.password_hash` e
devolve um par de tokens JWT (access + refresh) que o handler em
`jwt_handler.py` já sabe criar e verificar.

`/v1/auth/*` é bypassed pelo RBAC middleware — login é pré-auth. Por isso
o tenant vem do header `X-Tenant-Id` directamente (não via
`require_tenant_header`, que exige JWT em produção).
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import ZERO_UUID
from src.shared.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    refresh_access_token,
)
from src.shared.auth.passwords import verify_password
from src.shared.database import get_session
from src.shared.models.user import User

router = APIRouter(prefix="/v1/auth", tags=["auth"])

_log = logging.getLogger("auth.login")

# Mensagem genérica — não revela se o email existe.
_INVALID = "Email ou password inválidos"


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    role: str | None = None
    user_id: str | None = None


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-Id"),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Autentica por email + password e devolve tokens JWT."""
    if x_tenant_id == ZERO_UUID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant: zero UUID is reserved",
        )

    email = body.email.strip().lower()
    user = (
        await session.execute(
            select(User).where(
                User.tenant_id == x_tenant_id,
                func.lower(User.email) == email,
            )
        )
    ).scalar_one_or_none()

    if (
        user is None
        or not user.password_hash
        or not verify_password(body.password, user.password_hash)
    ):
        # Mesma resposta para email inexistente / sem password / errada.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID,
        )

    _log.info("login ok tenant=%s user=%s", x_tenant_id, user.id)
    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id, user.role),
        refresh_token=create_refresh_token(user.id, user.tenant_id, user.role),
        role=user.role,
        user_id=str(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest) -> TokenResponse:
    """Troca um refresh token válido por um novo access token."""
    result = refresh_access_token(body.refresh_token)  # 401 se inválido
    return TokenResponse(access_token=result["access_token"])
