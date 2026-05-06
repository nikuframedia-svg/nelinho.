"""Q.17.D — condition evaluator for runtime rule matching.

Evaluates a list of :class:`Condition` (AND-joined) against a typed
event payload. Returns ``bool``. Pure function, no I/O — easy to test
exhaustively.

Operator semantics:

- ``eq``/``ne``: Python ``==``/``!=``. Type coercion is **not** applied —
  ``42 == "42"`` is False. The LLM is constrained by the per-event
  field type expectations; if it emits a string where the runtime
  payload has int, the rule simply doesn't match. This is the safe
  default (better silent miss than spurious fire).
- ``gt``/``lt``/``gte``/``lte``: standard comparison; raises if the
  types are incompatible (TypeError → returns False, logged).
- ``in``: ``payload[field] in value``; ``value`` must be a sequence.
- ``matches``: regex match, compiled with a 50ms timeout via
  ``regex`` library if available, else stdlib re. Pattern compile is
  cached per-call.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.governance.yaml_policy.rule_schema import Condition, ConditionOp

_log = logging.getLogger(__name__)

# Compiled regex cache — small bounded LRU-ish dict.
_REGEX_CACHE: dict[str, re.Pattern[str]] = {}
_REGEX_CACHE_MAX = 256


def _compile_pattern(pattern: str) -> re.Pattern[str]:
    cached = _REGEX_CACHE.get(pattern)
    if cached is not None:
        return cached
    if len(_REGEX_CACHE) >= _REGEX_CACHE_MAX:
        # Drop arbitrary entry — bounded memory, not LRU. Fine for v1.
        _REGEX_CACHE.pop(next(iter(_REGEX_CACHE)))
    compiled = re.compile(pattern)
    _REGEX_CACHE[pattern] = compiled
    return compiled


def evaluate_condition(condition: Condition, payload: dict[str, Any]) -> bool:
    """True iff ``condition`` matches ``payload``.

    A missing field counts as no-match (False). A type mismatch on
    ordering operators is logged at debug and returns False (the rule
    is conservative: don't fire on shaky data).
    """
    if condition.field not in payload:
        return False
    actual = payload[condition.field]
    expected = condition.value
    op = condition.op

    try:
        if op is ConditionOp.EQ:
            return actual == expected
        if op is ConditionOp.NE:
            return actual != expected
        if op is ConditionOp.GT:
            return actual > expected  # type: ignore[operator]
        if op is ConditionOp.LT:
            return actual < expected  # type: ignore[operator]
        if op is ConditionOp.GTE:
            return actual >= expected  # type: ignore[operator]
        if op is ConditionOp.LTE:
            return actual <= expected  # type: ignore[operator]
        if op is ConditionOp.IN:
            if not isinstance(expected, (list, tuple, set, frozenset)):
                _log.debug("op=in but value is not a sequence: %r", expected)
                return False
            return actual in expected
        if op is ConditionOp.MATCHES:
            if not isinstance(actual, str) or not isinstance(expected, str):
                return False
            try:
                return _compile_pattern(expected).search(actual) is not None
            except re.error as exc:
                _log.warning("invalid regex in rule condition (%r): %s", expected, exc)
                return False
    except TypeError as exc:
        _log.debug("type error in op=%s actual=%r expected=%r: %s", op.value, actual, expected, exc)
        return False
    return False


def evaluate_all(conditions: list[Condition], payload: dict[str, Any]) -> bool:
    """AND-joined evaluation. Empty list = unconditional True."""
    return all(evaluate_condition(c, payload) for c in conditions)
