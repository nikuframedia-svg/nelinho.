"""
ProdPlan ONE — Decorator factories (Sprint Q.14.A)
==================================================

Cross-cutting decorators that wrap business functions. The first
inhabitant is :func:`record_rule_firing`, which captures every fire
of a deterministic detector / LLM suggestion producer into the
``governance.rule_firing`` audit table.

Why a decorator (and not a base class / mixin)?
-----------------------------------------------

The 16 producer sites in this codebase span 5 different modules
(``copilot/recommendations``, ``plan/services/transport_suggestions``,
``copilot/alerts/engine``, ``improve/service``,
``governance/preference_learning/detector``). Each has its own class
hierarchy / module structure. A decorator is the only intervention
that:

  * Doesn't force a refactor of the producer's class shape.
  * Stays opt-in per site (instrument as you go).
  * Captures exact function inputs / outputs (no hand-rolled "log
    this here" boilerplate that drifts).

Best-effort persistence
-----------------------

The decorator MUST NOT break the producer. If the audit table is
gone, the connection fails, or the payload is unserialisable, the
decorator logs a warning and returns the original function's result
unchanged. The audit log is a side-effect for observability, not a
gate on operations.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import json
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional, Sequence, TypeVar
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


T = TypeVar("T")

# Default dedupe window: a row is considered "still open" for this many
# seconds after its first fire. Subsequent fires of the same dedupe_key
# inside the window update `fire_count` + `last_fired_at` instead of
# inserting a new row. 1 hour matches the alerts engine's typical
# operator review cadence.
_DEFAULT_DEDUPE_WINDOW_SECONDS = 3600


def record_rule_firing(
    *,
    rule_id: str,
    extract_payload: Optional[Callable[..., Dict[str, Any]]] = None,
    serialise_output: Optional[Callable[[Any], Dict[str, Any]]] = None,
    dedupe_key: Optional[Callable[..., Optional[str]]] = None,
    dedupe_window_seconds: int = _DEFAULT_DEDUPE_WINDOW_SECONDS,
    extract_tenant_id: Optional[Callable[..., Optional[UUID]]] = None,
    variants: Optional[Sequence[str]] = None,
    variant_kwarg: str = "variant",
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator factory: persist a ``rule_firing`` row per call.

    The decorated function MUST be ``async``. Sync detectors should be
    wrapped in a ``run_in_executor`` first or refactored to async; the
    audit step itself is async (DB write).

    Args:
        rule_id: stable identifier for this rule, e.g.
            ``"transport.complete_truck"``. The audit dashboard groups
            firings by this id, so it's the API of the rule.
        extract_payload: callable that receives the same args/kwargs
            as the wrapped function and returns a JSON-serialisable
            dict to persist as ``trigger_payload``. When omitted, the
            decorator attempts a best-effort capture (only repr-ifies
            primitives + dataclasses; opaque objects become
            ``{"_repr": "<...>"}``).
        serialise_output: callable that takes the function's return
            value and returns a JSON-serialisable dict to persist as
            ``rule_output``. When omitted, the decorator stores
            ``{"result": <repr>}`` for opaque results.
        dedupe_key: callable returning a string used to collapse
            repeated firings into one row. ``None`` (default) → no
            dedupe. Returning ``None`` from the callable also skips
            dedupe for that specific call.
        dedupe_window_seconds: how far back to look for an "open" row
            with the same ``dedupe_key`` before considering it a fresh
            firing. Default 1 hour.
        extract_tenant_id: callable returning the tenant UUID to
            associate the row with. When omitted, the decorator looks
            for ``self.tenant_id`` on the bound instance (the most
            common shape across producers).

    Returns:
        A decorator that wraps the producer function in-place.

    Example::

        @record_rule_firing(
            rule_id="transport.complete_truck",
            dedupe_key=lambda self, batch, *_: f"batch:{batch.id}",
            extract_payload=lambda self, batch, assigned, unassigned: {
                "batch_id": str(batch.id),
                "assigned": assigned,
                "unassigned_count": len(unassigned),
            },
            serialise_output=lambda result: {"suggestion_count": len(result)},
        )
        async def _detect_complete_truck(self, batch, assigned, unassigned):
            ...
    """
    # Lazy imports inside the wrapper so the module can be imported
    # even when the SQLAlchemy session machinery isn't ready (tests,
    # CLI scripts).

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        if not asyncio.iscoroutinefunction(fn):
            raise TypeError(
                f"@record_rule_firing requires an async function; "
                f"{fn.__qualname__} is sync. Wrap it in run_in_executor "
                f"or convert to async."
            )

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Sprint Q.14.C — A/B variant resolution. When `variants`
            # is set on the decorator, we resolve a variant for this
            # (rule_id, tenant_id) BEFORE calling the wrapped function
            # and inject it as a kwarg the producer can read. The
            # `variant_id` persists on the audit row so adoption stats
            # can group by it later.
            resolved_variant: Optional[str] = None
            if variants:
                resolved_variant = _resolve_variant_for_call(
                    rule_id=rule_id,
                    args=args,
                    kwargs=kwargs,
                    candidates=variants,
                    extract_tenant_id=extract_tenant_id,
                )
                if resolved_variant is not None and variant_kwarg not in kwargs:
                    kwargs[variant_kwarg] = resolved_variant

            # Run the producer FIRST. Audit log is best-effort; if the
            # producer fails the exception propagates as-is.
            result = await fn(*args, **kwargs)

            # Audit step — every branch caught + logged; never raises.
            try:
                await _persist_firing(
                    rule_id=rule_id,
                    args=args,
                    kwargs=kwargs,
                    result=result,
                    extract_payload=extract_payload,
                    serialise_output=serialise_output,
                    dedupe_key_fn=dedupe_key,
                    dedupe_window_seconds=dedupe_window_seconds,
                    extract_tenant_id=extract_tenant_id,
                    variant_id=resolved_variant,
                )
            except Exception as exc:
                logger.warning(
                    "record_rule_firing(%s): persist failed (%s) — "
                    "result unaffected",
                    rule_id, exc,
                )
            return result

        # Mark the wrapper so introspection tools can find it later
        # (the audit dashboard lists known rules by walking decorated
        # functions in the producer modules).
        wrapper.__rule_firing_id__ = rule_id  # type: ignore[attr-defined]
        wrapper.__rule_firing_variants__ = (  # type: ignore[attr-defined]
            tuple(variants) if variants else ()
        )
        return wrapper

    return decorator


async def _persist_firing(
    *,
    rule_id: str,
    args: tuple,
    kwargs: dict,
    result: Any,
    extract_payload: Optional[Callable[..., Dict[str, Any]]],
    serialise_output: Optional[Callable[[Any], Dict[str, Any]]],
    dedupe_key_fn: Optional[Callable[..., Optional[str]]],
    dedupe_window_seconds: int,
    extract_tenant_id: Optional[Callable[..., Optional[UUID]]],
    variant_id: Optional[str] = None,
) -> None:
    """Internal: do the DB write. Raises on any path so the wrapper's
    try/except can log + swallow."""
    from sqlalchemy import and_, select, update
    from datetime import timedelta

    from src.governance.models import RuleFiring, RuleFiringOutcome
    from src.shared.database import get_session_context

    tenant_id = _resolve_tenant_id(args, kwargs, extract_tenant_id)
    if tenant_id is None:
        # Without tenant scope the row is meaningless to the audit
        # dashboard — skip silently with a debug log.
        logger.debug(
            "record_rule_firing(%s): no tenant_id resolvable from "
            "args; skipping persist.", rule_id,
        )
        return

    payload = _safe_extract(extract_payload, args, kwargs)
    output = _safe_serialise_output(serialise_output, result)

    dedupe_key = None
    if dedupe_key_fn is not None:
        try:
            dedupe_key = dedupe_key_fn(*args, **kwargs)
        except Exception as exc:
            logger.debug(
                "record_rule_firing(%s): dedupe_key fn raised (%s) — "
                "treating as no-dedupe", rule_id, exc,
            )

    now = datetime.now(timezone.utc)

    async with get_session_context() as session:
        existing = None
        if dedupe_key is not None:
            cutoff = now - timedelta(seconds=dedupe_window_seconds)
            stmt = (
                select(RuleFiring)
                .where(RuleFiring.tenant_id == tenant_id)
                .where(RuleFiring.rule_id == rule_id)
                .where(RuleFiring.dedupe_key == dedupe_key)
                .where(RuleFiring.fired_at >= cutoff)
                .where(
                    RuleFiring.outcome == RuleFiringOutcome.PROPOSED.value
                )
                .order_by(RuleFiring.fired_at.desc())
                .limit(1)
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()

        if existing is not None:
            # Collapse repeat firing into the open row.
            await session.execute(
                update(RuleFiring)
                .where(RuleFiring.id == existing.id)
                .values(
                    fire_count=RuleFiring.fire_count + 1,
                    last_fired_at=now,
                    # Refresh trigger_payload + output so the dashboard
                    # always shows the LATEST inputs that re-fired the
                    # rule (older payloads stay in fire_count history).
                    trigger_payload=payload,
                    rule_output=output,
                )
            )
        else:
            row = RuleFiring(
                id=uuid4(),
                tenant_id=tenant_id,
                rule_id=rule_id,
                variant_id=variant_id,
                fired_at=now,
                trigger_payload=payload,
                rule_output=output,
                dedupe_key=dedupe_key,
                outcome=RuleFiringOutcome.PROPOSED.value,
                fire_count=1,
            )
            session.add(row)
        await session.commit()


def _resolve_variant_for_call(
    *,
    rule_id: str,
    args: tuple,
    kwargs: dict,
    candidates: Sequence[str],
    extract_tenant_id: Optional[Callable[..., Optional[UUID]]],
) -> Optional[str]:
    """Resolve the A/B variant for a (rule_id, tenant_id) pair.

    Sprint Q.14.C — pre-call variant resolution. Same hash semantics as
    :func:`src.governance.ab_framework.resolve_variant`; defined here
    so the decorator stays import-light. When the tenant can't be
    resolved (defensive), returns ``None`` and the producer runs its
    default branch — auditable as ``variant_id=NULL``.
    """
    if not candidates:
        return None
    tenant_id = _resolve_tenant_id(args, kwargs, extract_tenant_id)
    if tenant_id is None:
        return None
    from src.governance.ab_framework import resolve_variant
    try:
        return resolve_variant(rule_id, tenant_id, candidates)
    except Exception as exc:
        logger.debug(
            "_resolve_variant_for_call(%s): resolve_variant raised "
            "(%s) — defaulting to None", rule_id, exc,
        )
        return None


def _resolve_tenant_id(
    args: tuple,
    kwargs: dict,
    extractor: Optional[Callable[..., Optional[UUID]]],
) -> Optional[UUID]:
    """Find a tenant UUID from the call's args or the bound instance.

    Order of resolution:
      1. ``extractor`` callable result, if provided.
      2. ``self.tenant_id`` on the bound instance (most common shape).
      3. ``kwargs["tenant_id"]`` if present and a UUID.

    Returns ``None`` when nothing matches. The decorator skips the
    persist in that case rather than producing a tenant=NULL row,
    which would be invisible to the per-tenant audit dashboard.
    """
    if extractor is not None:
        try:
            value = extractor(*args, **kwargs)
            if isinstance(value, UUID):
                return value
            if isinstance(value, str):
                try:
                    return UUID(value)
                except ValueError:
                    pass
        except Exception:  # noqa: S110  Q.61.06: tenant_id extraction fallback; downstream uses default
            pass
    if args:
        self = args[0]
        candidate = getattr(self, "tenant_id", None)
        if isinstance(candidate, UUID):
            return candidate
        if isinstance(candidate, str):
            try:
                return UUID(candidate)
            except ValueError:
                pass
    candidate = kwargs.get("tenant_id")
    if isinstance(candidate, UUID):
        return candidate
    return None


def _safe_extract(
    extractor: Optional[Callable[..., Dict[str, Any]]],
    args: tuple,
    kwargs: dict,
) -> Dict[str, Any]:
    """Run the extractor, swallowing any exception. Always returns a
    JSON-serialisable dict (the audit row's NOT NULL contract)."""
    if extractor is None:
        return _best_effort_payload(args, kwargs)
    try:
        out = extractor(*args, **kwargs)
        return _ensure_jsonable(out)
    except Exception as exc:
        logger.debug("extract_payload raised (%s) — using best-effort", exc)
        return _best_effort_payload(args, kwargs)


def _safe_serialise_output(
    serialiser: Optional[Callable[[Any], Dict[str, Any]]],
    result: Any,
) -> Dict[str, Any]:
    if serialiser is None:
        return _ensure_jsonable({"result": _repr_short(result)})
    try:
        return _ensure_jsonable(serialiser(result))
    except Exception as exc:
        logger.debug("serialise_output raised (%s) — using repr", exc)
        return {"result": _repr_short(result)}


def _best_effort_payload(args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Last-resort payload: skip ``self``, repr the rest. Stays small
    so the JSONB column doesn't blow up on accidental large objects."""
    extracted: Dict[str, Any] = {}
    if len(args) > 1:
        extracted["args_repr"] = [
            _repr_short(a) for a in args[1:]
        ]
    if kwargs:
        extracted["kwargs_repr"] = {
            k: _repr_short(v) for k, v in kwargs.items()
        }
    return _ensure_jsonable(extracted)


def _repr_short(value: Any, max_len: int = 200) -> str:
    try:
        out = repr(value)
    except Exception:
        out = "<unrepresentable>"
    return out if len(out) <= max_len else out[: max_len - 3] + "..."


def _ensure_jsonable(value: Any) -> Dict[str, Any]:
    """Force the payload through JSON encoding to catch unserialisable
    types early; fall back to a string-coerced wrapper when needed."""
    if value is None:
        return {}
    if isinstance(value, dict):
        try:
            json.dumps(value, default=str)
            return value
        except Exception:
            return {"_unserialisable": _repr_short(value)}
    return {"value": _repr_short(value)}


__all__ = ["record_rule_firing"]
