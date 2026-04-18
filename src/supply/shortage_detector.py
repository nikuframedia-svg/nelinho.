"""
ProdPlan ONE - Shortage Detector (Sprint O.4)
==============================================

Scans the active `MaterialMaster` catalogue and emits a `CopilotAlert` when
a SKU's projected stock (on-hand + in-transit ≤ lead_time_days) is below
its configured `min_stock_qty` (× `supply.safety_multiplier`).

Severity mapping
----------------
* **WARN → CODE_MATERIAL_SHORTAGE_PROJECTED** — projected_stock < min_stock
* **CRITICAL → CODE_MATERIAL_STOCKOUT_IMMINENT** — days_to_stockout below
  `supply.stockout_critical_days` OR material marked `critical_flag`.

The hourly job wired into `src/shared/scheduler.py::register_tenant` uses
this class; tests instantiate it directly with `FakeSession`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.alerts.models import (
    CODE_MATERIAL_SHORTAGE_PROJECTED,
    CODE_MATERIAL_STOCKOUT_IMMINENT,
    CopilotAlert,
    STATUS_ACTIVE,
)

from .material_service import MaterialService
from .models import MaterialMaster

logger = logging.getLogger(__name__)


DEFAULT_STOCKOUT_CRITICAL_DAYS = 3


class ShortageDetector:
    """Periodic SKU-by-SKU shortage scanner."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def _load_thresholds(self) -> dict[str, Any]:
        try:
            from src.core.services.tenant_config_service import TenantConfigService

            cfg = TenantConfigService(self.session, self.tenant_id)
            return {
                "critical_days": int(await cfg.get(
                    "supply", "stockout_critical_days",
                    default=DEFAULT_STOCKOUT_CRITICAL_DAYS,
                )),
            }
        except Exception:
            return {"critical_days": DEFAULT_STOCKOUT_CRITICAL_DAYS}

    async def scan(self) -> dict[str, Any]:
        """Walk active materials, emit CopilotAlerts where warranted.

        Returns a summary: `{materials_scanned, warn_created,
        critical_created, skipped_duplicate}`. An alert is considered
        duplicate when an ACTIVE row with the same (code, sku_id) already
        exists — this prevents the UI from flooding after a multi-hour
        outage.
        """
        thresholds = await self._load_thresholds()
        critical_days = int(thresholds["critical_days"])

        # Load all active materials for the tenant.
        stmt = select(MaterialMaster).where(
            and_(
                MaterialMaster.tenant_id == self.tenant_id,
                MaterialMaster.active.is_(True),
            )
        )
        materials = list((await self.session.execute(stmt)).scalars().all())

        service = MaterialService(self.session, self.tenant_id)

        warn_created = 0
        critical_created = 0
        skipped = 0

        for m in materials:
            position = await service.get_position(
                sku_id=m.sku_id,
                horizon_days=max(m.lead_time_days, 7),
            )
            below_min = position["below_min"]
            if not below_min:
                continue

            # Pick severity.
            days_to_stockout = position.get("days_to_stockout")
            is_imminent = (
                (days_to_stockout is not None and days_to_stockout < critical_days)
                or m.critical_flag
            )
            code = (
                CODE_MATERIAL_STOCKOUT_IMMINENT if is_imminent
                else CODE_MATERIAL_SHORTAGE_PROJECTED
            )
            severity = "CRITICAL" if is_imminent else "WARN"

            if await self._duplicate(code=code, sku_id=m.sku_id):
                skipped += 1
                continue

            title = (
                f"Rutura iminente: {m.sku_id}"
                if is_imminent else
                f"Stock abaixo do mínimo: {m.sku_id}"
            )
            message = _format_message(m, position, is_imminent, critical_days)
            alert = CopilotAlert(
                id=uuid4(),
                tenant_id=self.tenant_id,
                severity=severity,
                code=code,
                title=title,
                message_pt=message,
                context={
                    "sku_id": m.sku_id,
                    "on_hand": position["on_hand"],
                    "in_transit": position["in_transit"]["qty"],
                    "min_stock": position["min_stock"],
                    "days_to_stockout": days_to_stockout,
                    "lead_time_days": position.get("lead_time_days"),
                },
                entity_refs=[f"material:{m.sku_id}"],
                status=STATUS_ACTIVE,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.session.add(alert)
            if is_imminent:
                critical_created += 1
            else:
                warn_created += 1

        await self.session.flush()
        return {
            "materials_scanned": len(materials),
            "warn_created": warn_created,
            "critical_created": critical_created,
            "skipped_duplicate": skipped,
        }

    async def _duplicate(self, *, code: str, sku_id: str) -> bool:
        stmt = select(CopilotAlert.id).where(
            and_(
                CopilotAlert.tenant_id == self.tenant_id,
                CopilotAlert.code == code,
                CopilotAlert.status == STATUS_ACTIVE,
                CopilotAlert.entity_refs.contains([f"material:{sku_id}"]),  # JSONB @>
            )
        ).limit(1)
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        return existing is not None


def _format_message(
    m: MaterialMaster,
    position: dict[str, Any],
    is_imminent: bool,
    critical_days: int,
) -> str:
    days = position.get("days_to_stockout")
    days_str = f"{days:.1f}d" if isinstance(days, (int, float)) else "sem demanda média"
    if is_imminent:
        return (
            f"Material {m.sku_id} em rutura iminente. "
            f"Stock actual {position['on_hand']:.1f}, em trânsito "
            f"{position['in_transit']['qty']:.1f}, mínimo efectivo "
            f"{position['min_stock']:.1f}. Autonomia: {days_str} "
            f"(gate CRITICAL = {critical_days}d)."
        )
    return (
        f"Stock de {m.sku_id} abaixo do mínimo. "
        f"Projectado {position['projected_stock_horizon']:.1f} vs "
        f"mínimo {position['min_stock']:.1f}. Autonomia: {days_str}."
    )
