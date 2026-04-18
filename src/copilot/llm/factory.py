"""
ProdPlan ONE - LLM Factory (Sprint S.1)
=========================================

Instantiates an `LLMClient` based on `llm.backend` TenantConfig.

Precedence:
  1. Explicit `backend=` kwarg (tests)
  2. TenantConfig `llm.backend`
  3. `LLM_BACKEND` env var
  4. Default "ollama"

The factory is async because TenantConfig is an async read. Callers that
need a synchronous default can pass `backend="ollama"` directly.
"""

from __future__ import annotations

import logging
import os
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .base import LLMClient
from .ollama import OllamaBackend
from .vllm import VLLMBackend

logger = logging.getLogger(__name__)


async def get_llm_client(
    *,
    session: Optional[AsyncSession] = None,
    tenant_id: Optional[UUID] = None,
    backend: Optional[str] = None,
) -> LLMClient:
    """Return a configured LLMClient."""
    backend = backend or await _resolve_backend(session, tenant_id)
    backend = (backend or "ollama").lower()

    if backend == "vllm":
        return VLLMBackend(
            base_url=await _get_cfg(session, tenant_id, "vllm.base_url"),
            model=await _get_cfg(session, tenant_id, "vllm.model"),
        )
    if backend == "ollama":
        return OllamaBackend()

    logger.warning("Unknown llm.backend %r — defaulting to ollama", backend)
    return OllamaBackend()


async def _resolve_backend(
    session: Optional[AsyncSession],
    tenant_id: Optional[UUID],
) -> Optional[str]:
    """Read `llm.backend` from TenantConfig. Empty string → None."""
    if session is not None and tenant_id is not None:
        try:
            from src.core.services.tenant_config_service import TenantConfigService

            svc = TenantConfigService(session, tenant_id)
            cached = await svc.get("llm", "backend", default=None)
            if cached:
                return str(cached)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("llm.backend lookup failed: %s", exc)
    env = os.environ.get("LLM_BACKEND")
    if env:
        return env
    return None


async def _get_cfg(
    session: Optional[AsyncSession],
    tenant_id: Optional[UUID],
    key: str,
) -> Optional[str]:
    if session is None or tenant_id is None:
        return None
    try:
        from src.core.services.tenant_config_service import TenantConfigService

        svc = TenantConfigService(session, tenant_id)
        value = await svc.get("llm", key, default=None)
        return str(value) if value else None
    except Exception:
        return None
