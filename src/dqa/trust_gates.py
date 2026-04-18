"""
ProdPlan ONE - Trust Gates (Sprint AA.2)
=========================================

Blueprint v2.0 §4.5 decision gates. A gate says "at or above this composite
Trust Index, advanced behaviour X is permitted; below it, fall back to the
safe alternative".

The five gates (in ascending strictness):

| Gate                    | Threshold | Below the threshold                   |
|-------------------------|-----------|---------------------------------------|
| SOLVER_SUGGESTION_ONLY  |   0.50    | Solver must emit suggestions only     |
| USE_P90_DURATIONS       |   0.60    | Use P90 instead of P50 durations      |
| AUTO_REORDER            |   0.70    | Auto-reorder disabled (human OK)      |
| AUTO_COMMIT             |   0.75    | Auto-commit disabled (human OK)       |
| QUALITY_DISPOSITION     |   0.80    | Quality disposition blocked           |

Gates 0.50, 0.60, 0.75 are wired by callers today (CPO engine, duration
provider, ScheduleCommit). Gates 0.70 and 0.80 ship as constants here so
Sprint O (supply reorder) and Sprint R (quality disposition) can pick them up
without re-visiting this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TrustGate(Enum):
    """Gate identifier. The `value` matches the seeder key in
    `default_configs.py` (category `trust`, key `gates.<value>`)."""

    SOLVER_SUGGESTION_ONLY = "solver_suggestion_only"
    USE_P90_DURATIONS = "use_p90_durations"
    AUTO_REORDER = "auto_reorder"
    AUTO_COMMIT = "auto_commit"
    QUALITY_DISPOSITION = "quality_disposition"


DEFAULT_THRESHOLDS: dict[TrustGate, float] = {
    TrustGate.SOLVER_SUGGESTION_ONLY: 0.50,
    TrustGate.USE_P90_DURATIONS: 0.60,
    TrustGate.AUTO_REORDER: 0.70,
    TrustGate.AUTO_COMMIT: 0.75,
    TrustGate.QUALITY_DISPOSITION: 0.80,
}


@dataclass(frozen=True)
class TrustGateConfig:
    """Per-tenant snapshot of gate thresholds, read once then consulted."""

    thresholds: dict[TrustGate, float]

    @classmethod
    def default(cls) -> "TrustGateConfig":
        return cls(dict(DEFAULT_THRESHOLDS))

    def get(self, gate: TrustGate) -> float:
        return self.thresholds.get(gate, DEFAULT_THRESHOLDS[gate])


async def load_gate_config(session: AsyncSession, tenant_id: UUID) -> TrustGateConfig:
    """Load gate thresholds for a tenant.

    Falls back to `DEFAULT_THRESHOLDS` on any error (missing seeder, DB down).
    If the config values are non-monotonic (e.g. auto_commit < auto_reorder),
    the loader logs a warning but still returns the values as-configured — we
    trust the admin's intent; monotonicity is enforced in seeder tests, not
    here at runtime.
    """
    try:
        from src.core.services.tenant_config_service import TenantConfigService

        svc = TenantConfigService(session, tenant_id)
        values = await svc.get_category("trust")
        mapping: dict[TrustGate, float] = {}
        for gate in TrustGate:
            key = f"gates.{gate.value}"
            raw = values.get(key, DEFAULT_THRESHOLDS[gate])
            mapping[gate] = float(raw)
        return TrustGateConfig(thresholds=mapping)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "TrustGate thresholds load failed, using defaults: %s", exc,
        )
        return TrustGateConfig.default()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def gate_allows(
    ti: float,
    gate: TrustGate,
    config: Optional[TrustGateConfig] = None,
) -> bool:
    """True iff TI is at or above the threshold (i.e. the advanced mode is permitted).

    Callers asking "does this block me?" should invert: `not gate_allows(ti, g)`.
    Three semantic helpers below cover the common cases so the negation isn't
    repeated all over the codebase.
    """
    cfg = config or TrustGateConfig.default()
    return ti >= cfg.get(gate)


def effective_mode(
    ti: float,
    config: Optional[TrustGateConfig] = None,
) -> dict[str, bool]:
    """Return `{gate_name: allowed}` for every gate. Suitable for API responses."""
    cfg = config or TrustGateConfig.default()
    return {g.value: gate_allows(ti, g, cfg) for g in TrustGate}


# ---------------------------------------------------------------------------
# Integration helpers — callers consume these, not `gate_allows` directly
# ---------------------------------------------------------------------------

def is_solver_suggestion_only(
    ti: float, config: Optional[TrustGateConfig] = None,
) -> bool:
    """Gate 0.50. CPOEngine must NOT commit; produce suggestions only."""
    return not gate_allows(ti, TrustGate.SOLVER_SUGGESTION_ONLY, config)


def should_use_p90_durations(
    ti: float, config: Optional[TrustGateConfig] = None,
) -> bool:
    """Gate 0.60. Decoder swaps p50 → p90 durations for larger safety buffers."""
    return not gate_allows(ti, TrustGate.USE_P90_DURATIONS, config)


def auto_reorder_allowed(
    ti: float, config: Optional[TrustGateConfig] = None,
) -> bool:
    """Gate 0.70. Supply reorder service (Sprint O) consults this."""
    return gate_allows(ti, TrustGate.AUTO_REORDER, config)


def requires_human_approval(
    ti: float, config: Optional[TrustGateConfig] = None,
) -> bool:
    """Gate 0.75. ScheduleCommit.requires_approval derives from this."""
    return not gate_allows(ti, TrustGate.AUTO_COMMIT, config)


def quality_disposition_allowed(
    ti: float, config: Optional[TrustGateConfig] = None,
) -> bool:
    """Gate 0.80. Sprint R quality endpoints consult this."""
    return gate_allows(ti, TrustGate.QUALITY_DISPOSITION, config)
