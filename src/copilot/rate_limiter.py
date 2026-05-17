"""
ProdPlan ONE - COPILOT Rate Limiter
====================================

Rate limiting via Redis.

Sprint Q.12 Onda 0.3 — fail-closed. The previous implementation
fell through to ``return True, None`` when Redis was offline, which
made the rate limit trivially bypassable: an attacker could DoS Redis
(or the cache module could be misconfigured) and the limiter would
silently let everything through. Now Redis-down → 503 with a clear
error so SRE notices and the limit isn't quietly disabled.

In development we honour ``settings.environment != "production"`` to
keep the dev loop usable when Redis is down (the dev tooling spins
Redis up later than the API). The fallback ONLY applies in dev.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from src.shared.config import settings
from src.shared.redis_client import get_redis

logger = logging.getLogger(__name__)


class RateLimiterUnavailableError(Exception):
    """Raised when the rate-limit backend (Redis) is not reachable.

    The HTTP layer maps this to 503 — the bug we're closing was that
    the previous code converted backend failures into "allowed=True",
    which is exactly the wrong fail-mode for a security control.
    """


# Sprint Q.12 Onda 3.3 — atomic INCR-and-conditionally-allow Lua.
# Replaces the previous GET → check → INCR → EXPIRE sequence which
# had two distinct bugs:
#   1. Race: two callers both saw count=N below the limit and both
#      incremented past it.
#   2. Crash window: ``EXPIRE`` ran AFTER ``INCR`` so a process kill
#      between the two left the key alive forever — that user got
#      blocked permanently.
# The script does an atomic INCR + EXPIRE-on-first-write, then
# decides allow/deny in the same transaction.
#
# KEYS[1]   counter key
# ARGV[1]   limit (string-encoded int)
# ARGV[2]   ttl seconds (string-encoded int)
# Returns:  {allowed (1|0), retry_after_seconds, current_count}
_RATE_LIMIT_LUA = """
local limit = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ttl)
end
if current > limit then
  local remaining = redis.call('TTL', KEYS[1])
  if remaining < 0 then
    -- Belt and braces: TTL went missing somehow. Reset it so the
    -- caller doesn't get stuck.
    redis.call('EXPIRE', KEYS[1], ttl)
    remaining = ttl
  end
  return {0, remaining, current}
end
return {1, 0, current}
"""


class RateLimiter:
    """
    Rate limiter para COPILOT.

    Limites:
    - Por hora: configurável (default 60)
    - Por dia: configurável (default 300)
    """

    def __init__(
        self,
        per_hour: Optional[int] = None,
        per_day: Optional[int] = None,
    ):
        self.per_hour = per_hour or settings.copilot_rate_limit_per_hour
        self.per_day = per_day or settings.copilot_rate_limit_per_day

    async def check_rate_limit(
        self,
        tenant_id: UUID,
        actor_id: UUID,
    ) -> tuple[bool, Optional[int]]:
        """
        Verificar se request está dentro dos limites.

        Returns:
            (allowed, retry_after_seconds)
            - allowed: True se permitido, False se excedido
            - retry_after_seconds: segundos até poder tentar novamente (se excedido)

        Raises:
            RateLimiterUnavailableError: when Redis is unreachable in
                production. Dev/test environments still log + allow so
                local runs without Redis stay usable.
        """
        try:
            redis = await get_redis()

            # Keys para contadores
            hour_key = f"copilot:rate:{tenant_id}:{actor_id}:hour"
            day_key = f"copilot:rate:{tenant_id}:{actor_id}:day"

            # Sprint Q.12 Onda 3.3 — atomic INCR+EXPIRE+check via Lua.
            # We run the hour script first; if that allows, we run the
            # day script. The day-side INCR happens regardless of the
            # hour outcome to keep counters consistent under retry, but
            # if the hour denied we surface its retry_after.
            hour_allowed, hour_retry, _ = await self._run_atomic_check(
                redis, hour_key, self.per_hour, 3600,
            )
            if not hour_allowed:
                # Don't double-charge the daily counter when the hourly
                # one already rejected — keeps "actor over hourly limit
                # but under daily" from leaking into the daily count.
                return False, max(hour_retry, 60)

            day_allowed, day_retry, _ = await self._run_atomic_check(
                redis, day_key, self.per_day, 86400,
            )
            if not day_allowed:
                return False, max(day_retry, 3600)

            return True, None

        except RateLimiterUnavailableError:
            raise
        except Exception as exc:
            # Fall through to the env-aware handler.
            return await self._handle_backend_failure(tenant_id, actor_id, exc)

    async def _run_atomic_check(
        self, redis, key: str, limit: int, ttl: int,
    ) -> tuple[bool, int, int]:
        """Run :data:`_RATE_LIMIT_LUA` and unpack the Lua response.

        Returns ``(allowed, retry_after, current_count)``.

        Falls back to a per-command path on backends without Lua
        (older fakeredis in unit tests). The fallback has the
        narrower-window race we accept for tests; production Redis
        always supports EVAL.
        """
        try:
            result = await redis.eval(_RATE_LIMIT_LUA, 1, key, str(limit), str(ttl))
            allowed_raw, retry_raw, current_raw = result[0], result[1], result[2]
            return bool(int(allowed_raw)), int(retry_raw), int(current_raw)
        except Exception as lua_exc:
            logger.debug(
                "rate_limiter: EVAL unavailable (%s); falling back to "
                "per-command path.", lua_exc,
            )
        # Fallback: INCR is atomic; we set EXPIRE on the first write.
        # Race window between INCR and EXPIRE is acceptable in dev/test.
        current = int(await redis.incr(key))
        if current == 1:
            await redis.expire(key, ttl)
        if current > limit:
            ttl_remaining = int(await redis.ttl(key))
            if ttl_remaining < 0:
                await redis.expire(key, ttl)
                ttl_remaining = ttl
            return False, ttl_remaining, current
        return True, 0, current

    async def _handle_backend_failure(
        self, tenant_id, actor_id, exc: BaseException,
    ) -> tuple[bool, Optional[int]]:
        """Original bug we closed in Onda 0.3 — keep the env-aware
        fail-closed behaviour after Lua-related failures too.
        """
        # Re-route through the original pathway so the policy is
        # consistent with Onda 0.3.
        try:
            raise exc
        except Exception:  # pragma: no cover — re-entry
            # Fail-CLOSED in production. The previous version returned
            # ``(True, None)`` here, turning a Redis outage into a
            # silent rate-limit bypass.
            logger.error(
                "rate_limiter: Redis backend unavailable "
                "(tenant=%s actor=%s): %s",
                tenant_id, actor_id, exc,
            )
            if settings.environment == "production":
                raise RateLimiterUnavailableError(str(exc)) from exc
            logger.warning(
                "rate_limiter: env=%s — allowing request through despite "
                "Redis outage (production would 503).",
                settings.environment,
            )
            return True, None

    # Sprint Q.13.F F.1 — sliding-window per-route limiter.
    # The fixed-window per-(tenant, actor) check above is the right
    # tool for Copilot conversational quotas (60/hour). Routes that
    # carry more cost (CPO schedule, preview-delta, runbook execute)
    # need a tighter limit AND want sliding-window precision so a
    # caller can't push 60 requests in the last second of a window
    # then 60 more in the first second of the next.
    #
    # Implementation: Redis ZSET keyed by (tenant, route, actor) with
    # microsecond-resolution timestamps as scores. Trim entries older
    # than `window_s`, count remaining; if under limit, ZADD the new
    # entry and allow. Atomic via Lua.

    _SLIDING_WINDOW_LUA = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window_us = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local ttl = tonumber(ARGV[4])
    redis.call('ZREMRANGEBYSCORE', key, 0, now - window_us)
    local current = redis.call('ZCARD', key)
    if current >= limit then
      local oldest_score = tonumber(redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')[2] or now)
      local retry_us = oldest_score + window_us - now
      return {0, math.max(1, math.ceil(retry_us / 1000000)), current}
    end
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, ttl)
    return {1, 0, current + 1}
    """

    async def check_route_rate_limit(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        *,
        route_name: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, Optional[int]]:
        """Sliding-window rate limit for a specific route.

        Args:
            tenant_id / actor_id: scope.
            route_name: stable identifier (e.g. "copilot.respond").
            limit: max requests within the sliding window.
            window_seconds: window length in seconds.

        Returns ``(allowed, retry_after_seconds)`` matching the
        per-actor surface above so HTTP middleware can branch on the
        same shape.

        Fail-closed in production (mirrors `check_rate_limit`).
        """
        if limit <= 0 or window_seconds <= 0:
            # Disabled by config — never throttle.
            return True, None
        try:
            import time as _time
            redis = await get_redis()
            key = f"copilot:rate:route:{tenant_id}:{route_name}:{actor_id}"
            now_us = int(_time.time() * 1_000_000)
            window_us = window_seconds * 1_000_000
            ttl = max(window_seconds * 2, 60)
            try:
                result = await redis.eval(
                    self._SLIDING_WINDOW_LUA,
                    1, key,
                    str(now_us), str(window_us), str(limit), str(ttl),
                )
                allowed = bool(int(result[0]))
                retry_after = int(result[1])
                return allowed, (retry_after if not allowed else None)
            except Exception as lua_exc:
                logger.debug(
                    "check_route_rate_limit: EVAL unavailable (%s); "
                    "falling back to per-command path.", lua_exc,
                )
            # Fallback: ZREMRANGEBYSCORE + ZCARD + ZADD. The race window
            # is acceptable for dev/test backends.
            await redis.zremrangebyscore(key, 0, now_us - window_us)
            current = int(await redis.zcard(key))
            if current >= limit:
                oldest = await redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_score = int(oldest[0][1])
                    retry_us = oldest_score + window_us - now_us
                    retry_s = max(1, retry_us // 1_000_000)
                else:
                    retry_s = window_seconds
                return False, retry_s
            await redis.zadd(key, {str(now_us): now_us})
            await redis.expire(key, ttl)
            return True, None
        except Exception as exc:
            return await self._handle_backend_failure(tenant_id, actor_id, exc)

    async def enforce_rate_limit(
        self,
        tenant_id: UUID,
        actor_id: UUID,
    ):
        """
        Enforce rate limit - raise HTTPException se excedido.

        Raises:
            HTTPException 429 se limite excedido
            HTTPException 503 se rate limiter backend offline (prod only)
        """
        try:
            allowed, retry_after = await self.check_rate_limit(tenant_id, actor_id)
        except RateLimiterUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter backend unavailable; refusing to serve.",
                headers={"Retry-After": "30"},
            ) from exc

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit excedido. Tente novamente em {retry_after}s",
                headers={"Retry-After": str(retry_after or 60)},
            )


# Instância global
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

