"""
ProdPlan ONE - Copilot Alerts Models
=====================================

Persisted proactive alerts raised by `AlertsEngine` detectors.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


# Alert severities (also enforced at API schema level)
SEVERITIES = ("INFO", "WARN", "CRITICAL")

# Alert lifecycle status
STATUS_ACTIVE = "active"
STATUS_ACKNOWLEDGED = "acknowledged"
STATUS_RESOLVED = "resolved"

# Detector codes — add a new one here whenever adding a detector
CODE_BOTTLENECK_FORMATION = "BOTTLENECK_FORMATION"
CODE_SKILLS_CONCENTRATION = "SKILLS_CONCENTRATION"
CODE_QUALITY_DEGRADATION = "QUALITY_DEGRADATION"
CODE_DELIVERY_RISK = "DELIVERY_RISK"  # currently blocked (no OTD data)


class CopilotAlert(TenantBase):
    """A proactive alert surfaced by the Copilot AlertsEngine."""

    __tablename__ = "copilot_alerts"
    __table_args__ = (
        Index("idx_copilot_alerts_tenant_status", "tenant_id", "status", "created_at"),
        Index("idx_copilot_alerts_code", "code"),
    )

    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message_pt: Mapped[str] = mapped_column(Text, nullable=False)

    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    entity_refs: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=STATUS_ACTIVE,
    )

    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
