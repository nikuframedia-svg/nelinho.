"""CubeClient — wrapper httpx do Cube REST API.

Endpoints usados:
    GET  /cubejs-api/v1/meta   → catálogo (cubes, measures, dimensions)
    POST /cubejs-api/v1/load   → executar query JSON

DEV_MODE: o Cube aceita qualquer Authorization. Em prod (CUBEJS_DEV_MODE=false)
o token JWT terá de ser passado via CUBE_AUTH_TOKEN (CUBEJS_API_SECRET sign).

Sem cache em memória do /meta — chamada local sub-50ms, cachear vem depois.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field


CUBE_BASE_URL_DEFAULT = "http://localhost:4000"
CUBE_AUTH_TOKEN_DEFAULT = "bogus-dev"  # aceite em DEV_MODE


# ────────────────────────────── Pydantic schemas ──────────────────────────────


class CubeMeasureSpec(BaseModel):
    """Uma medida no catálogo /meta."""

    model_config = ConfigDict(extra="ignore")

    name: str  # ex: "consumo_material.consumo"
    title: str | None = None
    description: str | None = None
    type: str | None = None  # "number", etc.
    agg_type: str | None = Field(default=None, alias="aggType")
    format: str | None = None
    is_visible: bool = Field(default=True, alias="isVisible")


class CubeDimensionSpec(BaseModel):
    """Uma dimensão no catálogo /meta."""

    model_config = ConfigDict(extra="ignore")

    name: str  # ex: "consumo_material.material"
    title: str | None = None
    description: str | None = None
    type: str | None = None  # "string", "number", "time"
    suggest_filter_values: bool = Field(default=False, alias="suggestFilterValues")


class CubeSpec(BaseModel):
    """Um cube no catálogo."""

    model_config = ConfigDict(extra="ignore")

    name: str
    title: str | None = None
    description: str | None = None
    measures: list[CubeMeasureSpec] = Field(default_factory=list)
    dimensions: list[CubeDimensionSpec] = Field(default_factory=list)


class CubeCatalog(BaseModel):
    """Resposta do /cubejs-api/v1/meta."""

    model_config = ConfigDict(extra="ignore")

    cubes: list[CubeSpec] = Field(default_factory=list)

    def all_measure_names(self) -> list[str]:
        return [m.name for c in self.cubes for m in c.measures]

    def all_dimension_names(self) -> list[str]:
        return [d.name for c in self.cubes for d in c.dimensions]

    def dimension(self, name: str) -> CubeDimensionSpec | None:
        for c in self.cubes:
            for d in c.dimensions:
                if d.name == name:
                    return d
        return None


class CubeResult(BaseModel):
    """Resposta do /cubejs-api/v1/load."""

    model_config = ConfigDict(extra="ignore")

    data: list[dict[str, Any]] = Field(default_factory=list)
    annotation: dict[str, Any] = Field(default_factory=dict)
    query: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = Field(default=None, alias="requestId")
    last_refresh_time: str | None = Field(default=None, alias="lastRefreshTime")


# ────────────────────────────── Client ──────────────────────────────


class CubeClient:
    """HTTP client para o Cube REST API (singleton lazy)."""

    def __init__(
        self,
        base_url: str | None = None,
        auth_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("CUBE_BASE_URL", CUBE_BASE_URL_DEFAULT)
        )
        self.auth_token = (
            auth_token or os.environ.get("CUBE_AUTH_TOKEN", CUBE_AUTH_TOKEN_DEFAULT)
        )
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=4, max_connections=8),
                headers={"Authorization": self.auth_token},
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_meta(self) -> CubeCatalog:
        client = await self._get_client()
        r = await client.get("/cubejs-api/v1/meta")
        r.raise_for_status()
        return CubeCatalog.model_validate(r.json())

    async def load(self, query: dict[str, Any]) -> CubeResult:
        """Executa uma query JSON contra /cubejs-api/v1/load.

        `query` é o payload Pydantic-serialized (dict) — passamos o body
        completo {"query": {...}} aqui dentro.
        """
        client = await self._get_client()
        r = await client.post(
            "/cubejs-api/v1/load",
            json={"query": query},
        )
        r.raise_for_status()
        return CubeResult.model_validate(r.json())


# Singleton para reuso por request (FastAPI dependency).
_default_client: CubeClient | None = None


def get_default_cube_client() -> CubeClient:
    global _default_client
    if _default_client is None:
        _default_client = CubeClient()
    return _default_client
