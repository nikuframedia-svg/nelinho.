"""Sprint Q.13.F F.1 — Sliding-window per-route rate limiter.

The fixed-window per-actor limiter (Sprint Q.12 Onda 0.3 / 3.3) handles
copilot-conversation quotas, but heavier endpoints (CPO schedule,
preview-delta, runbook execute) need a tighter, sliding-window limit
so a caller can't push 60 requests in the last second of a window
then 60 more in the first second of the next.

These tests cover:
  * Under-limit traffic is allowed.
  * Over-limit traffic is denied with `retry_after`.
  * Per-route isolation: hitting the limit on route A doesn't block
    route B for the same actor.
  * Per-actor isolation: actor A hitting the limit doesn't block
    actor B.
  * Window expiry: traffic resumes after the sliding window passes.
  * Disabled config (limit <= 0) → always allowed (no throttle).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Tuple
from uuid import UUID, uuid4

import pytest

import src.copilot.rate_limiter as rate_limiter_module
from src.copilot.rate_limiter import RateLimiter


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _FakeRedis:
    """Tiny in-memory Redis double exposing the ZSET ops the route
    rate limiter needs. EVAL is intentionally NOT supported so the
    tests exercise the per-command fallback path."""

    def __init__(self) -> None:
        self.zsets: Dict[str, List[Tuple[int, str]]] = {}

    async def eval(self, *_args, **_kwargs):
        raise NotImplementedError("fake redis: EVAL not implemented")

    async def zremrangebyscore(self, key: str, lo: int, hi: int):
        zs = self.zsets.get(key, [])
        kept = [(score, member) for (score, member) in zs if not (lo <= score <= hi)]
        self.zsets[key] = kept

    async def zcard(self, key: str) -> int:
        return len(self.zsets.get(key, []))

    async def zrange(self, key: str, start: int, stop: int, withscores: bool = False):
        zs = sorted(self.zsets.get(key, []), key=lambda x: x[0])
        # Inclusive stop, like redis-py.
        end = stop + 1 if stop >= 0 else len(zs) + stop + 1
        slice_ = zs[start:end]
        if withscores:
            return [(member, score) for (score, member) in slice_]
        return [member for (_score, member) in slice_]

    async def zadd(self, key: str, mapping: Dict[str, int]) -> int:
        zs = self.zsets.setdefault(key, [])
        for member, score in mapping.items():
            zs.append((int(score), member))
        return len(mapping)

    async def expire(self, key: str, ttl: int) -> int:
        return 1


@pytest.fixture
def fake_redis(monkeypatch):
    fake = _FakeRedis()

    async def _get():
        return fake

    monkeypatch.setattr(rate_limiter_module, "get_redis", _get)
    return fake


@pytest.mark.asyncio
async def test_allows_under_limit(fake_redis):
    rl = RateLimiter()
    actor = uuid4()
    for _ in range(5):
        allowed, retry = await rl.check_route_rate_limit(
            _TENANT, actor,
            route_name="cpo.schedule", limit=10, window_seconds=60,
        )
        assert allowed is True
        assert retry is None


@pytest.mark.asyncio
async def test_denies_over_limit_with_retry_after(fake_redis):
    rl = RateLimiter()
    actor = uuid4()
    for _ in range(5):
        allowed, _ = await rl.check_route_rate_limit(
            _TENANT, actor,
            route_name="cpo.schedule", limit=5, window_seconds=60,
        )
        assert allowed is True

    allowed, retry = await rl.check_route_rate_limit(
        _TENANT, actor,
        route_name="cpo.schedule", limit=5, window_seconds=60,
    )
    assert allowed is False
    assert retry is not None and retry > 0


@pytest.mark.asyncio
async def test_per_route_isolation(fake_redis):
    """Hitting the limit on one route must NOT block other routes for
    the same actor — the limiter's key includes route_name."""
    rl = RateLimiter()
    actor = uuid4()
    for _ in range(3):
        await rl.check_route_rate_limit(
            _TENANT, actor,
            route_name="cpo.schedule", limit=3, window_seconds=60,
        )
    blocked, _ = await rl.check_route_rate_limit(
        _TENANT, actor,
        route_name="cpo.schedule", limit=3, window_seconds=60,
    )
    assert blocked is False

    # Different route — fresh budget.
    other_allowed, _ = await rl.check_route_rate_limit(
        _TENANT, actor,
        route_name="copilot.respond", limit=3, window_seconds=60,
    )
    assert other_allowed is True


@pytest.mark.asyncio
async def test_per_actor_isolation(fake_redis):
    rl = RateLimiter()
    actor_a, actor_b = uuid4(), uuid4()
    for _ in range(3):
        await rl.check_route_rate_limit(
            _TENANT, actor_a,
            route_name="cpo.schedule", limit=3, window_seconds=60,
        )
    blocked, _ = await rl.check_route_rate_limit(
        _TENANT, actor_a,
        route_name="cpo.schedule", limit=3, window_seconds=60,
    )
    assert blocked is False

    # Different actor — fresh budget on the same route.
    other_allowed, _ = await rl.check_route_rate_limit(
        _TENANT, actor_b,
        route_name="cpo.schedule", limit=3, window_seconds=60,
    )
    assert other_allowed is True


@pytest.mark.asyncio
async def test_window_expiry_unblocks_traffic(fake_redis, monkeypatch):
    """When the sliding window scrolls forward, an actor previously
    over the limit can send again."""
    rl = RateLimiter()
    actor = uuid4()
    import time as _time

    # Freeze "now" so we can inject a future jump deterministically.
    base = int(_time.time() * 1_000_000)
    times = iter([base, base, base, base + 70 * 1_000_000])

    def _fake_time():
        return next(times) / 1_000_000

    monkeypatch.setattr(_time, "time", _fake_time)

    for _ in range(3):
        await rl.check_route_rate_limit(
            _TENANT, actor,
            route_name="cpo.schedule", limit=3, window_seconds=60,
        )
    # 4th call advances past the 60s window — old scores get trimmed.
    allowed, _ = await rl.check_route_rate_limit(
        _TENANT, actor,
        route_name="cpo.schedule", limit=3, window_seconds=60,
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_disabled_config_never_throttles(fake_redis):
    """An operator who sets `limit=0` or `window=0` in ConfigStore
    expects the throttle to silently turn off — not 503, not deny."""
    rl = RateLimiter()
    actor = uuid4()
    allowed, retry = await rl.check_route_rate_limit(
        _TENANT, actor,
        route_name="cpo.schedule", limit=0, window_seconds=60,
    )
    assert allowed is True
    assert retry is None

    allowed, retry = await rl.check_route_rate_limit(
        _TENANT, actor,
        route_name="cpo.schedule", limit=10, window_seconds=0,
    )
    assert allowed is True
    assert retry is None
