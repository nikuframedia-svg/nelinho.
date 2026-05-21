"""
ProdPlan ONE - CEO Objectives Service (Sprint Q.53.C)
======================================================

Powers `GET /v1/profit/kpis/objectives`. The Direção page has an empty
"objetivos CEO" section: the target bands the CEO steers the factory
against. This service produces them.

Each objective is a `(low, target, high)` band per KPI. The defaults are
seeded in code (Blueprint §1.1 — €30–35K/dia; NELO management targets —
OTD 95%, FPY 95%, retrabalho 8%) and any matching `TenantConfiguration`
under the `cost` category overrides the seed. This keeps the endpoint
non-empty on a fresh install while still letting the CEO retune.

It also carries the PP1-impact signal: the € saved by suggestions the
CEO accepted. "Accepted" = a `DecisionRun` reached status EXECUTED /
EXECUTED_PARTIAL; the euros come from `actual_impact` (falling back to
`expected_impact`). No executed decisions → `eur_saved=0` with a clear
reason, never a fabricated figure.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Seed bands. `direction="higher"` means above-target is good (OTD, FPY,
# throughput); `direction="lower"` means below-target is good (rework).
_OBJECTIVE_SEEDS: dict[str, dict[str, Any]] = {
    "throughput_eur_day": {
        "label": "Faturação por dia",
        "unit": "EUR",
        "low": 30000.0,
        "target": 32500.0,
        "high": 35000.0,
        "direction": "higher",
        "config_keys": {
            "low": "target.throughput_eur_day_min",
            "high": "target.throughput_eur_day_max",
        },
    },
    "otd_pct": {
        "label": "Entregas no prazo (OTD)",
        "unit": "%",
        "low": 90.0,
        "target": 95.0,
        "high": 100.0,
        "direction": "higher",
        "config_keys": {"target": "target.otd_pct"},
    },
    "fpy_pct": {
        "label": "Qualidade à primeira (FPY)",
        "unit": "%",
        "low": 90.0,
        "target": 95.0,
        "high": 100.0,
        "direction": "higher",
        "config_keys": {"target": "target.fpy_pct"},
    },
    "rework_pct": {
        "label": "Taxa de retrabalho",
        "unit": "%",
        "low": 4.0,
        "target": 8.0,
        "high": 12.0,
        "direction": "lower",
        "config_keys": {"target": "target.rework_pct"},
    },
}

# Decision statuses that count as "the CEO accepted the suggestion".
_ACCEPTED_STATUSES = ("executed", "executed_partial")


class ObjectivesService:
    """Builds the CEO objective bands + the PP1-impact signal."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def objectives(self, *, pp1_window_days: int = 90) -> dict[str, Any]:
        """Return the full objectives payload for the Direção page."""
        overrides = await self._load_cost_overrides()
        kpis = [
            self._build_band(name, seed, overrides)
            for name, seed in _OBJECTIVE_SEEDS.items()
        ]
        pp1 = await self._pp1_impact(window_days=pp1_window_days)
        return {
            "kpis": kpis,
            "pp1_impact": pp1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _load_cost_overrides(self) -> dict[str, Any]:
        """Pull the `cost` config category — overrides for the seed bands."""
        try:
            from src.core.services.tenant_config_service import (
                TenantConfigService,
            )

            svc = TenantConfigService(self.session, self.tenant_id)
            return await svc.get_category("cost")
        except Exception as exc:  # pragma: no cover — defensive
            # Poisoned-transaction guard, mirrors ThroughputService.
            await self.session.rollback()
            logger.warning("objectives: cost config load failed: %s", exc)
            return {}

    @staticmethod
    def _build_band(
        name: str,
        seed: dict[str, Any],
        overrides: dict[str, Any],
    ) -> dict[str, Any]:
        """One KPI band: seed values, with any TenantConfig override applied."""
        low = float(seed["low"])
        target = float(seed["target"])
        high = float(seed["high"])
        source = "seed_default"

        for band_name, cfg_key in seed.get("config_keys", {}).items():
            if cfg_key in overrides:
                try:
                    value = float(overrides[cfg_key])
                except (TypeError, ValueError):
                    continue
                if band_name == "low":
                    low = value
                elif band_name == "high":
                    high = value
                elif band_name == "target":
                    target = value
                source = "tenant_config"

        return {
            "kpi": name,
            "label": seed["label"],
            "unit": seed["unit"],
            "direction": seed["direction"],
            "low": low,
            "target": target,
            "high": high,
            "source": source,
        }

    async def _pp1_impact(self, *, window_days: int) -> dict[str, Any]:
        """€ saved by accepted PP1 suggestions over the rolling window.

        Reads `DecisionRun` rows that reached an accepted status. The
        euro figure comes from `actual_impact["eur_saved"]` (the measured
        outcome) and falls back to `expected_impact["eur_saved"]` when the
        actual was not recorded.
        """
        from src.governance.models import DecisionRun

        since = datetime.now(timezone.utc) - timedelta(days=window_days)
        stmt = select(DecisionRun).where(
            and_(
                DecisionRun.tenant_id == self.tenant_id,
                DecisionRun.status.in_(_ACCEPTED_STATUSES),
                DecisionRun.proposed_at >= since,
            )
        )
        rows = list((await self.session.execute(stmt)).scalars().all())

        eur_saved = 0.0
        decisions_with_eur = 0
        for d in rows:
            value = _extract_eur_saved(d.actual_impact)
            if value is None:
                value = _extract_eur_saved(d.expected_impact)
            if value is not None:
                eur_saved += value
                decisions_with_eur += 1

        accepted_count = len(rows)
        return {
            "window_days": window_days,
            "accepted_decisions": accepted_count,
            "decisions_with_eur": decisions_with_eur,
            "eur_saved": round(eur_saved, 2),
            "reason": (
                None
                if accepted_count > 0
                else (
                    "Ainda não há decisões executadas na janela — o "
                    "impacto PP1 começa a contar quando as sugestões "
                    "forem aceites."
                )
            ),
        }


def _extract_eur_saved(impact: Optional[dict[str, Any]]) -> Optional[float]:
    """Pull a euro-saving figure from an impact JSON blob.

    Accepts the canonical `eur_saved` key and a couple of synonyms the
    decision authors have used. Returns None when no numeric figure is
    present — the caller treats that as "no signal", not zero.
    """
    if not isinstance(impact, dict):
        return None
    for key in ("eur_saved", "euros_saved", "savings_eur", "cost_saved_eur"):
        if key in impact:
            try:
                return float(impact[key])
            except (TypeError, ValueError):
                return None
    return None
