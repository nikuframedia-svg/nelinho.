"""Q.67.6.C — Coverage tests for ``factory_data_product.api.blocked_metrics``.

The blocked-metrics enforcement layer is the wall between the API and a list
of metrics the Folha data simply cannot answer (OEE, real productivity, OTD,
…). Until Q.67.6.C the module had no dedicated tests, so the actual raise
path (``MetricBlockedError``), the alias normalization, and the decorator
were dark in coverage.

Tests here pin:

* ``check_metric_blocked`` raises a structured 422 with the canonical
  PT-PT message + ``required_data`` echoed back.
* ``check_metric_blocked`` is a no-op for non-blocked / unknown metrics —
  callers don't have to special-case "is the id in the whitelist?".
* ``is_metric_blocked`` / ``get_blocked_reason`` / ``is_metric_allowed``
  return the correct booleans / payloads.
* ``normalize_metric_id`` maps every documented alias (PT and EN) onto the
  canonical id and leaves unknown ids untouched (case-insensitive lookup).
* ``check_metric_blocked_with_aliases`` walks the alias map before
  checking — a Portuguese alias like ``"disponibilidade"`` must raise.
* ``enforce_blocked_metrics`` decorator: blocks via kwarg and via first
  positional arg, lets allowed ids through.
* The error object exposes ``status_code == 422`` and a ``detail`` dict
  shaped exactly as the frontend `BlockedMetricBanner` expects
  (status="BLOCKED", how_to_unblock pt-PT prefix).
"""

from __future__ import annotations

import asyncio

import pytest

from src.factory_data_product.api.blocked_metrics import (
    METRIC_ALIASES,
    MetricBlockedError,
    check_metric_blocked,
    check_metric_blocked_with_aliases,
    enforce_blocked_metrics,
    get_blocked_reason,
    is_metric_allowed,
    is_metric_blocked,
    normalize_metric_id,
)
from src.factory_data_product.config import ALLOWED_METRICS, BLOCKED_METRICS


# ---------------------------------------------------------------------------
# 1. MetricBlockedError shape — the 422 contract the frontend reads
# ---------------------------------------------------------------------------


def test_metric_blocked_error_carries_canonical_422_detail() -> None:
    """The exception encodes the metric id, reason, required data and a
    PT-PT human-readable message in a single ``detail`` dict so the
    frontend can render the BLOCKED banner without a second lookup."""
    err = MetricBlockedError(
        metric_id="oee_real",
        reason="Não existem dados de paragens/máquinas",
        required_data=["machine_downtime", "planned_production_time"],
    )

    assert err.status_code == 422
    assert err.detail["error"] == "metric_blocked"
    assert err.detail["metric_id"] == "oee_real"
    assert err.detail["status"] == "BLOCKED"
    assert "BLOQUEADA" in err.detail["message"]
    assert "oee_real" in err.detail["message"]
    # Both required-data items echoed back, joined by ', '
    assert "machine_downtime" in err.detail["how_to_unblock"]
    assert "planned_production_time" in err.detail["how_to_unblock"]


# ---------------------------------------------------------------------------
# 2. check_metric_blocked — raise vs no-op
# ---------------------------------------------------------------------------


def test_check_metric_blocked_raises_for_known_blocked_metric() -> None:
    """A canonical blocked id raises a MetricBlockedError with the
    BLOCKED_METRICS entry threaded through (reason + required_data)."""
    with pytest.raises(MetricBlockedError) as ei:
        check_metric_blocked("oee_real")

    assert ei.value.status_code == 422
    assert ei.value.detail["metric_id"] == "oee_real"
    assert ei.value.detail["reason"] == BLOCKED_METRICS["oee_real"]["reason"]


def test_check_metric_blocked_is_noop_for_allowed_metric() -> None:
    """An ALLOWED metric passes through without raising."""
    # Just must not raise.
    check_metric_blocked("wip_theoretical")


def test_check_metric_blocked_is_noop_for_unknown_metric() -> None:
    """An id that's neither blocked nor allowed is also passed through —
    the wall only blocks the explicit deny-list."""
    check_metric_blocked("__totally_unknown_metric__")


# ---------------------------------------------------------------------------
# 3. is_metric_blocked / get_blocked_reason / is_metric_allowed
# ---------------------------------------------------------------------------


def test_is_metric_blocked_returns_true_for_each_blocked_id() -> None:
    """Every id in BLOCKED_METRICS reports as blocked."""
    for metric_id in BLOCKED_METRICS:
        assert is_metric_blocked(metric_id) is True


def test_is_metric_blocked_false_for_allowed_and_unknown() -> None:
    """ALLOWED and unknown ids report False."""
    assert is_metric_blocked("wip_theoretical") is False
    assert is_metric_blocked("__nope__") is False


def test_get_blocked_reason_returns_full_payload_for_blocked_metric() -> None:
    """``get_blocked_reason`` returns the raw dict (reason + required_data)
    or None — used by the API to attach context to a 422."""
    payload = get_blocked_reason("otd_official")
    assert payload is not None
    assert "reason" in payload
    assert "required_data" in payload
    assert isinstance(payload["required_data"], list)


def test_get_blocked_reason_returns_none_for_unknown_metric() -> None:
    """Unknown id ⇒ None (defensive: callers can use ``if reason:``)."""
    assert get_blocked_reason("__nope__") is None


def test_is_metric_allowed_recognises_whitelist() -> None:
    """Every id in ALLOWED_METRICS reports as allowed; unknown is False."""
    for metric_id in ALLOWED_METRICS:
        assert is_metric_allowed(metric_id) is True
    assert is_metric_allowed("__nope__") is False
    # Blocked ids should not also be in the allowed list.
    for metric_id in BLOCKED_METRICS:
        assert is_metric_allowed(metric_id) is False


# ---------------------------------------------------------------------------
# 4. Alias normalization — PT and EN names must map to the canonical id
# ---------------------------------------------------------------------------


def test_normalize_metric_id_collapses_pt_pt_aliases() -> None:
    """PT-PT aliases (disponibilidade, entrega_prazo, …) map to canonical."""
    assert normalize_metric_id("disponibilidade") == "availability_oee"
    assert normalize_metric_id("entrega_prazo") == "otd_official"
    assert normalize_metric_id("conflito_molde") == "mold_conflict_confirmed"
    assert normalize_metric_id("produtividade_individual") == "productivity_individual_real"


def test_normalize_metric_id_is_case_insensitive() -> None:
    """Aliases are matched case-insensitively (the map uses .lower())."""
    assert normalize_metric_id("OEE") == "oee_real"
    assert normalize_metric_id("Disponibilidade") == "availability_oee"


def test_normalize_metric_id_passes_unknown_through_unchanged() -> None:
    """An id that is neither alias nor canonical is returned as-is."""
    assert normalize_metric_id("__unknown__") == "__unknown__"


def test_check_metric_blocked_with_aliases_raises_on_pt_alias() -> None:
    """The PT alias must trigger the same 422 as the canonical id."""
    with pytest.raises(MetricBlockedError) as ei:
        check_metric_blocked_with_aliases("disponibilidade")
    assert ei.value.detail["metric_id"] == "availability_oee"


def test_check_metric_blocked_with_aliases_is_noop_for_allowed() -> None:
    """An allowed id passes through ``check_metric_blocked_with_aliases``
    unchanged (no alias rewrite, no raise)."""
    check_metric_blocked_with_aliases("wip_theoretical")


# ---------------------------------------------------------------------------
# 5. enforce_blocked_metrics decorator — kwarg path + positional path
# ---------------------------------------------------------------------------


def test_enforce_blocked_metrics_blocks_via_kwarg() -> None:
    """When the wrapped function takes ``metric_id`` as a kwarg, the
    decorator inspects it and raises before the body runs."""

    @enforce_blocked_metrics
    async def _endpoint(metric_id: str) -> str:
        return f"ok-{metric_id}"  # pragma: no cover — guarded by decorator

    with pytest.raises(MetricBlockedError):
        asyncio.run(_endpoint(metric_id="oee_real"))


def test_enforce_blocked_metrics_blocks_via_first_positional_arg() -> None:
    """If ``metric_id`` is not a kwarg, the decorator falls back to
    ``args[0]`` — preserves the contract documented in the docstring."""

    @enforce_blocked_metrics
    async def _endpoint(metric_id: str) -> str:
        return f"ok-{metric_id}"  # pragma: no cover

    with pytest.raises(MetricBlockedError):
        asyncio.run(_endpoint("oee_real"))


def test_enforce_blocked_metrics_lets_allowed_metric_through() -> None:
    """Decorator must NOT raise for an allowed id; the wrapped body runs."""

    @enforce_blocked_metrics
    async def _endpoint(metric_id: str) -> str:
        return f"ok-{metric_id}"

    result = asyncio.run(_endpoint(metric_id="wip_theoretical"))
    assert result == "ok-wip_theoretical"


def test_enforce_blocked_metrics_passes_through_when_no_metric_id() -> None:
    """If the wrapped function is called with no metric_id at all (unusual
    but legal — e.g. a list endpoint) the decorator must not blow up."""

    @enforce_blocked_metrics
    async def _list() -> list[str]:
        return ["wip_theoretical"]

    assert asyncio.run(_list()) == ["wip_theoretical"]


# ---------------------------------------------------------------------------
# 6. METRIC_ALIASES sanity — every alias points to a real blocked canonical
# ---------------------------------------------------------------------------


def test_every_alias_resolves_to_a_blocked_canonical_id() -> None:
    """Catches drift: someone renames a canonical id in BLOCKED_METRICS
    without updating METRIC_ALIASES."""
    for alias, canonical in METRIC_ALIASES.items():
        assert canonical in BLOCKED_METRICS, (
            f"alias {alias!r} → {canonical!r} but {canonical!r} not in BLOCKED_METRICS"
        )
