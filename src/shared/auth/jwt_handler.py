"""
ProdPlan ONE - JWT Handler
===========================

JWT token creation and verification.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from src.shared.config import settings

security = HTTPBearer()


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # user_id
    tenant_id: str
    role: str
    exp: datetime
    iat: datetime
    type: str  # access or refresh


class UserContext(BaseModel):
    """Current user context."""
    user_id: UUID
    tenant_id: UUID
    role: str
    email: Optional[str] = None


def create_access_token(
    user_id: UUID,
    tenant_id: UUID,
    role: str,
    expires_delta: timedelta = None,
) -> str:
    """Create JWT access token."""
    expires_delta = expires_delta or timedelta(
        minutes=settings.access_token_expire_minutes
    )
    
    now = datetime.utcnow()
    expire = now + expires_delta
    
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(
    user_id: UUID,
    tenant_id: UUID,
    role: str,
) -> str:
    """Create JWT refresh token."""
    expires_delta = timedelta(days=settings.refresh_token_expire_days)
    
    now = datetime.utcnow()
    expire = now + expires_delta
    
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }
    
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str, token_type: str = "access") -> TokenPayload:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        
        token_payload = TokenPayload(
            sub=payload.get("sub"),
            tenant_id=payload.get("tenant_id"),
            role=payload.get("role"),
            exp=datetime.fromtimestamp(payload.get("exp", 0)),
            iat=datetime.fromtimestamp(payload.get("iat", 0)),
            type=payload.get("type"),
        )
        
        if token_payload.type != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type}",
            )
        
        return token_payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserContext:
    """Get current user from JWT token."""
    token = credentials.credentials
    payload = verify_token(token, "access")
    
    return UserContext(
        user_id=UUID(payload.sub),
        tenant_id=UUID(payload.tenant_id),
        role=payload.role,
    )


async def get_current_tenant(
    user: UserContext = Depends(get_current_user),
) -> UUID:
    """Get current tenant ID."""
    return user.tenant_id


def refresh_access_token(refresh_token: str) -> Dict[str, str]:
    """Generate new access token from refresh token."""
    payload = verify_token(refresh_token, "refresh")
    
    new_access = create_access_token(
        user_id=UUID(payload.sub),
        tenant_id=UUID(payload.tenant_id),
        role=payload.role,
    )
    
    return {
        "access_token": new_access,
        "token_type": "bearer",
    }










