"""Q.66.D.4a — dependencies partilhadas pelos sub-routers do copilot.

`get_tenant_id` e `dev_only` viviam em `src/copilot/api.py` e eram
usadas em múltiplos endpoints. Centralizar aqui evita duplicação e
mantém o `api.py` agregador como um simples wire-up de sub-routers.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Header, HTTPException, status

from src.shared.config import settings


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    """Extract tenant ID from header."""
    return x_tenant_id


def dev_only() -> None:
    """Dependency that 404s when ``settings.environment == "production"``.

    Sprint Q.12 Onda 0.5 — the ``/*-dev`` endpoints (no auth, hardcoded
    tenant) used to be reachable in any environment, leaking tenant-zero
    data to anyone who knew the URL. Now they're hidden in prod. The
    long-term answer is to remove them outright once each surface has a
    proper auth path; until then this guard makes "shipped to prod by
    accident" loud instead of quiet.
    """
    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )
