"""
ProdPlan ONE - Trust Signals providers (Sprint AA.3)
=====================================================

Concrete `SignalsProvider` implementations for the v2.0 TrustIndex calculator.
Each provider inspects the live database to produce a `TrustSignals` record
that the calculator then converts into `TrustComponents`.

Two providers ship here:

* `factory_signals`   — scope="factory": one signal per tenant (global).
* `order_signals`     — scope="order":   signal for a single `CuratedOrder`.
* `phase_signals`     — scope="phase":   signal for a single `CuratedPhase`.

All three are registered under `build_default_signals_provider()` so callers
can hand the calculator a single dispatcher regardless of scope.

Data sources touched
--------------------
* Freshness: `factory_curated.order_phase.created_at_utc`
  (τ from `TenantConfig.trust.freshness.tau_seconds_curated`).
* Consistency: z-score of `(horas_reais − horas_previstas) / stddev` over a
  sample window (last 30 days by default). Uses `horas_previstas` because it's
  already curated; swapping to `DurationModel.predict().p50` is a later refinement.
* Provenance: fixed "erp" for curated rows (they descend from an Excel/ERP load).
* Evidence: `True` if the row has an `ingestion_id` FK (verifiable back to its
  ingestion run); `None` otherwise.

Edge cases
----------
* Empty tenants (no curated rows) → freshness/consistency both default to
  optimistic (1.0) via the base scorers; completeness/validity default to 1.0
  as well. The composite collapses to the provenance cap (~0.955 with the
  default "erp" tier). This is intentional — a brand-new tenant is not
  *untrustworthy*, it's just unknown.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dqa.trust_v2 import (
    SCOPE_ORDER,
    SCOPE_PHASE,
    TrustSignals,
)

logger = logging.getLogger(__name__)


# Hard cap on the consistency sample window. We don't want "last 30 days" to
# blow up into a 6-year scan on a factory with years of data. 30d is the
# default; admins can override via tenant config (not yet wired, deferred).
DEFAULT_CONSISTENCY_WINDOW_DAYS = 30
DEFAULT_CONSISTENCY_SAMPLE_CAP = 500

# Fallback values when TenantConfig reads fail.
DEFAULT_TAU_SECONDS = 86_400.0  # 1 day
DEFAULT_KAPPA = 2.0


async def _load_freshness_params(session: AsyncSession, tenant_id: UUID) -> tuple[float, float]:
    """Return (tau_seconds, kappa) from TenantConfig with defaults."""
    try:
        from src.core.services.tenant_config_service import TenantConfigService

        svc = TenantConfigService(session, tenant_id)
        values = await svc.get_category("trust")
        tau = float(values.get("freshness.tau_seconds_curated", DEFAULT_TAU_SECONDS))
        kappa = float(values.get("consistency.kappa", DEFAULT_KAPPA))
        return tau, kappa
    except Exception as exc:  # pragma: no cover — defensive
        # Onda 2.1 — surface as error so ops sees that consistency/freshness
        # are running on hardcoded defaults rather than tenant config.
        logger.error(
            "trust config load failed for tenant=%s, using defaults: %s",
            tenant_id, exc, exc_info=True,
        )
        return DEFAULT_TAU_SECONDS, DEFAULT_KAPPA


async def _load_consistency_window(
    session: AsyncSession, tenant_id: UUID,
) -> tuple[int, int]:
    """Onda 3.6 — read consistency window/sample-cap from TenantConfig.

    Returns (window_days, sample_cap) with defaults preserved when keys
    are missing or the config service errors out. Tenant overrides matter
    for factories whose duration distributions shift on weekly cycles
    (window=7) vs monthly cycles (window=60).
    """
    try:
        from src.core.services.tenant_config_service import TenantConfigService

        svc = TenantConfigService(session, tenant_id)
        values = await svc.get_category("trust")
        window = int(values.get(
            "consistency.window_days_curated",
            DEFAULT_CONSISTENCY_WINDOW_DAYS,
        ))
        cap = int(values.get(
            "consistency.sample_cap",
            DEFAULT_CONSISTENCY_SAMPLE_CAP,
        ))
        return window, cap
    except Exception as exc:  # pragma: no cover — defensive
        logger.error(
            "consistency window load failed for tenant=%s, using defaults: %s",
            tenant_id, exc, exc_info=True,
        )
        return DEFAULT_CONSISTENCY_WINDOW_DAYS, DEFAULT_CONSISTENCY_SAMPLE_CAP


def _now_utc() -> datetime:
    # Centralised so tests can monkey-patch.
    return datetime.now(timezone.utc)


def _age_seconds(most_recent: Optional[datetime]) -> Optional[float]:
    """Diff between now and the most recent timestamp. Handles both aware and
    naive datetimes (treats naive as UTC)."""
    if most_recent is None:
        return None
    now = _now_utc()
    if most_recent.tzinfo is None:
        most_recent = most_recent.replace(tzinfo=timezone.utc)
    delta = now - most_recent
    return max(0.0, delta.total_seconds())


def _rows_to_z_scores(rows: list[tuple[float, float]]) -> list[float]:
    """Compute per-row z-scores of (real − predicted) / stddev(differences).

    `rows` are `(horas_reais, horas_previstas)` pairs where both are non-null.
    Returns an empty list when the sample is too small (< 3 points) — the
    consistency scorer then reads "no z-scores" as optimistic 1.0.

    Onda 4.2 bug: `statistics.pstdev` raises `AttributeError` (not the
    expected `StatisticsError`) when fed NaN or infinity. Postgres
    NUMERIC overflows and legacy sentinel values can both produce these,
    so we filter before computing rather than relying on the exception
    path. Any non-finite input is dropped silently.
    """
    import math

    diffs: list[float] = []
    for real, predicted in rows:
        if real is None or predicted is None:
            continue
        try:
            d = float(real) - float(predicted)
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(d):
            continue
        diffs.append(d)

    if len(diffs) < 3:
        return []

    try:
        stdev = statistics.pstdev(diffs)
    except (statistics.StatisticsError, AttributeError, ValueError):
        # AttributeError can leak from pstdev when intermediate values
        # are non-finite; fall back to "insufficient signal".
        return []
    if not math.isfinite(stdev) or stdev <= 0:
        # All differences identical OR pstdev returned non-finite
        # (Decimal/float interop edge case) → no variance signal.
        return [0.0] * len(diffs)

    mean = statistics.mean(diffs)
    return [(d - mean) / stdev for d in diffs]


# ---------------------------------------------------------------------------
# Per-scope queries
# ---------------------------------------------------------------------------

async def _query_most_recent_curated(
    session: AsyncSession,
    scope: str,
    scope_id: Optional[UUID],
    order_id_str: Optional[str] = None,
    phase_id_str: Optional[str] = None,
) -> Optional[datetime]:
    """Return MAX(created_at_utc) for the relevant curated rows.

    `scope_id` is a tenant UUID for factory scope or an optional identifier
    for order/phase scope. We also accept pre-resolved string business keys
    (`order_id_str` = of_id; `phase_id_str` = fase_id) because `CuratedOrderPhase`
    uses string business keys, not UUIDs, for its foreign scope.
    """
    # Import lazily so this module doesn't pull in heavy ORM deps at startup.
    from src.factory_data_product.models.curated import CuratedOrderPhase

    stmt = select(func.max(CuratedOrderPhase.created_at_utc))
    conditions = []
    if scope == SCOPE_ORDER and order_id_str is not None:
        conditions.append(CuratedOrderPhase.of_id == order_id_str)
    elif scope == SCOPE_PHASE and phase_id_str is not None:
        conditions.append(CuratedOrderPhase.fase_id == phase_id_str)
    # factory scope: no extra filter — global freshness

    if conditions:
        stmt = stmt.where(and_(*conditions))
    return (await session.execute(stmt)).scalar_one_or_none()


async def _query_duration_samples(
    session: AsyncSession,
    scope: str,
    scope_id: Optional[UUID],
    window_days: int = DEFAULT_CONSISTENCY_WINDOW_DAYS,
    sample_cap: int = DEFAULT_CONSISTENCY_SAMPLE_CAP,
    order_id_str: Optional[str] = None,
    phase_id_str: Optional[str] = None,
) -> list[tuple[float, float]]:
    """Fetch (horas_reais, horas_previstas) pairs within the window."""
    from src.factory_data_product.models.curated import CuratedOrderPhase

    since = _now_utc() - timedelta(days=window_days)
    # Onda 1.3: explicit order_by — without it Postgres returns rows in an
    # unspecified order, so `.limit(sample_cap)` could return any subset of
    # the window. Most-recent-first means the z-score reflects the latest
    # behaviour, not a random snapshot.
    stmt = (
        select(CuratedOrderPhase.horas_reais, CuratedOrderPhase.horas_previstas)
        .where(
            CuratedOrderPhase.created_at_utc >= since,
            CuratedOrderPhase.horas_reais.is_not(None),
            CuratedOrderPhase.horas_previstas.is_not(None),
        )
        .order_by(CuratedOrderPhase.created_at_utc.desc())
        .limit(sample_cap)
    )
    if scope == SCOPE_ORDER and order_id_str is not None:
        stmt = stmt.where(CuratedOrderPhase.of_id == order_id_str)
    elif scope == SCOPE_PHASE and phase_id_str is not None:
        stmt = stmt.where(CuratedOrderPhase.fase_id == phase_id_str)

    rows = (await session.execute(stmt)).all()
    return [(float(r[0]), float(r[1])) for r in rows if r[0] is not None and r[1] is not None]


# ---------------------------------------------------------------------------
# Public signals provider (AA.3 dispatcher)
# ---------------------------------------------------------------------------

async def curated_signals_provider(
    session: AsyncSession,
    tenant_id: UUID,
    scope: str,
    scope_id: Optional[UUID] = None,
    *,
    order_id_str: Optional[str] = None,
    phase_id_str: Optional[str] = None,
    window_days: int = DEFAULT_CONSISTENCY_WINDOW_DAYS,
) -> TrustSignals:
    """Sprint AA.3 canonical provider — factory / order / phase scope.

    The dispatcher signature is the minimum required by the calculator's
    `SignalsProvider` protocol (session, tenant_id, scope, scope_id). The
    business-key overrides (`order_id_str`, `phase_id_str`) allow real callers
    to pre-resolve an `of_id`/`fase_id` when the UUID scope_id doesn't map
    directly to the curated table's business key.
    """
    tau, kappa = await _load_freshness_params(session, tenant_id)
    # Onda 3.6 — caller-supplied `window_days` wins (tests still need
    # determinism); otherwise fall back to TenantConfig.
    cfg_window, cfg_cap = await _load_consistency_window(session, tenant_id)
    effective_window = (
        window_days if window_days != DEFAULT_CONSISTENCY_WINDOW_DAYS
        else cfg_window
    )

    most_recent = await _query_most_recent_curated(
        session, scope, scope_id,
        order_id_str=order_id_str, phase_id_str=phase_id_str,
    )
    samples = await _query_duration_samples(
        session, scope, scope_id,
        window_days=effective_window,
        sample_cap=cfg_cap,
        order_id_str=order_id_str, phase_id_str=phase_id_str,
    )
    z_scores = _rows_to_z_scores(samples)

    # If we managed to read real rows, mark evidence verifiable; otherwise
    # leave as None (optimistic-by-design).
    verifiable = True if samples or most_recent is not None else None

    return TrustSignals(
        age_seconds=_age_seconds(most_recent),
        tau_seconds=tau,
        z_scores=z_scores,
        kappa=kappa,
        provenance_tier="erp",
        anomaly_probability=0.0,  # wired in a future sprint once the anomaly ML path exists
        verifiable=verifiable,
    )
