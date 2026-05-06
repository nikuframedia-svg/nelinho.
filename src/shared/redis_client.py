"""
ProdPlan ONE - Redis Client
============================

Async Redis client for caching and session management.
"""

import json
import logging
from datetime import timedelta
from typing import Any, Optional, TypeVar, Type
from uuid import UUID

import redis.asyncio as redis
from pydantic import BaseModel

from .config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class RedisClient:
    """
    Async Redis client wrapper.
    
    Provides:
    - Simple key-value caching
    - TTL management
    - JSON serialization for Pydantic models
    - Session storage
    """
    
    def __init__(self):
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        if self._pool is not None:
            return
        
        # Sprint S6: explicit timeouts so a stalled Redis cannot block the
        # async event loop forever. Was unbounded.
        self._pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_pool_size,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=2.0,
        )
        self._client = redis.Redis(connection_pool=self._pool)
        
        # Test connection
        await self._client.ping()
        logger.info("Redis connected")
    
    async def disconnect(self) -> None:
        """Close Redis connections."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        self._client = None
        self._pool = None
        logger.info("Redis disconnected")
    
    @property
    def client(self) -> redis.Redis:
        """Get the Redis client."""
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client
    
    # Key-Value Operations
    
    async def get(self, key: str) -> Optional[str]:
        """Get a string value."""
        return await self.client.get(key)
    
    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[timedelta] = None,
    ) -> bool:
        """Set a string value with optional TTL."""
        if ttl:
            return await self.client.setex(key, ttl, value)
        return await self.client.set(key, value)
    
    async def delete(self, key: str) -> int:
        """Delete a key."""
        return await self.client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return bool(await self.client.exists(key))
    
    async def expire(self, key: str, ttl: timedelta) -> bool:
        """Set TTL on existing key."""
        return await self.client.expire(key, ttl)
    
    # JSON Operations (for Pydantic models)
    
    async def get_json(self, key: str) -> Optional[dict]:
        """Get a JSON value as dict."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set_json(
        self,
        key: str,
        value: dict,
        ttl: Optional[timedelta] = None,
    ) -> bool:
        """Set a JSON value from dict."""
        return await self.set(key, json.dumps(value), ttl)
    
    async def get_model(self, key: str, model_class: Type[T]) -> Optional[T]:
        """Get and deserialize a Pydantic model."""
        data = await self.get_json(key)
        if data:
            return model_class.model_validate(data)
        return None
    
    async def set_model(
        self,
        key: str,
        model: BaseModel,
        ttl: Optional[timedelta] = None,
    ) -> bool:
        """Serialize and set a Pydantic model."""
        return await self.set_json(key, model.model_dump(mode="json"), ttl)
    
    # Cache Key Builders
    
    @staticmethod
    def build_key(*parts: Any) -> str:
        """Build a cache key from parts."""
        return ":".join(str(p) for p in parts)
    
    @staticmethod
    def tenant_key(tenant_id: UUID, *parts: Any) -> str:
        """Build a tenant-scoped cache key."""
        return RedisClient.build_key("tenant", str(tenant_id), *parts)
    
    # Rate Configuration Cache
    
    async def get_labor_rate(
        self,
        tenant_id: UUID,
        employee_id: UUID,
    ) -> Optional[float]:
        """Get cached labor rate."""
        key = self.tenant_key(tenant_id, "labor_rate", str(employee_id))
        value = await self.get(key)
        return float(value) if value else None
    
    async def set_labor_rate(
        self,
        tenant_id: UUID,
        employee_id: UUID,
        rate: float,
        ttl: timedelta = timedelta(hours=1),
    ) -> bool:
        """Cache labor rate."""
        key = self.tenant_key(tenant_id, "labor_rate", str(employee_id))
        return await self.set(key, str(rate), ttl)
    
    async def get_machine_rate(
        self,
        tenant_id: UUID,
        machine_id: UUID,
    ) -> Optional[float]:
        """Get cached machine rate."""
        key = self.tenant_key(tenant_id, "machine_rate", str(machine_id))
        value = await self.get(key)
        return float(value) if value else None
    
    async def set_machine_rate(
        self,
        tenant_id: UUID,
        machine_id: UUID,
        rate: float,
        ttl: timedelta = timedelta(hours=1),
    ) -> bool:
        """Cache machine rate."""
        key = self.tenant_key(tenant_id, "machine_rate", str(machine_id))
        return await self.set(key, str(rate), ttl)
    
    # Invalidation
    
    async def invalidate_tenant_cache(self, tenant_id: UUID) -> int:
        """Invalidate all cache for a tenant."""
        pattern = self.tenant_key(tenant_id, "*")
        keys = []
        async for key in self.client.scan_iter(match=pattern):
            keys.append(key)
        
        if keys:
            return await self.client.delete(*keys)
        return 0


# Global instance
_redis_client: Optional[RedisClient] = None


async def get_redis() -> RedisClient:
    """Get or create the global Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()
    return _redis_client


async def shutdown_redis() -> None:
    """Shutdown Redis client."""
    global _redis_client
    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None


# Health check
async def check_redis_health() -> bool:
    """Check Redis connectivity."""
    try:
        client = await get_redis()
        await client.client.ping()
        return True
    except Exception:
        return False










