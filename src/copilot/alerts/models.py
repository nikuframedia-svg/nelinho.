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

# Sprint O.4 — material shortage codes (MR04 / AL02)
CODE_MATERIAL_SHORTAGE_PROJECTED = "MATERIAL_SHORTAGE_PROJECTED"  # WARN — under min_stock
CODE_MATERIAL_STOCKOUT_IMMINENT = "MATERIAL_STOCKOUT_IMMINENT"   # CRITICAL — within critical_days

# FASE 1B.3 (CRIT-13) — emitted when RoutingResolver couldn't reach the
# curated semantic engine and fell back to FasesStandardModelos with a
# 2x buffer (NELO rule). Schedules built in this state can have
# durations off by up to 25x reality, so the operator should know.
CODE_ROUTING_ENGINE_UNAVAILABLE = "ROUTING_ENGINE_UNAVAILABLE"   # WARN

# Q.126.E — emitted when more than a threshold fraction of the resolved
# operations fell back to the 2x synthetic buffer (no real history covered
# the (fase, modelo) pair). The plan is still returned (degraded=True) so the
# operator can decide, but the durations may diverge materially from reality.
CODE_DURATION_FALLBACK_HIGH = "DURATION_FALLBACK_HIGH"            # WARN

# Q.131.H — emitted when one or more orders could NOT be planned at all: no
# per-order history, no model history, no ERP routing template. Instead of
# silently dropping them from the plan, the scheduler surfaces them so the
# operator knows exactly which orders (and why) were left out.
CODE_ORDERS_WITHOUT_ROUTING = "ORDERS_WITHOUT_ROUTING"           # WARN

# Q.173.C — emitted when an ERP→Postgres ETL mirror run fails. Before this,
# a mirror could fail 100% of its runs for weeks (auditoria 2026-06-11:
# phase_history/worker_assignment 9/9 'error') with the failure visible only
# in core.etl_run — nobody looks there. One ACTIVE alert per mirror.
CODE_ETL_SYNC_FAILED = "ETL_SYNC_FAILED"                          # WARN

# Q.162.B — emitted when a completed schedule covered far too few of the orders
# it was asked to plan (big scope, tiny coverage) — a transient solver failure or
# a data regression. The plan is persisted for audit but flagged
# `cpo_meta.degenerate=true` so /overall skips it and keeps showing the last
# healthy plan (never a frozen 2-op plan masquerading as "current").
CODE_PLAN_DEGENERATE = "PLAN_DEGENERATE"                          # WARN

# Q.173.AR — emitted when no LIVE plan has been approved for N days. The
# plan-vs-actual calibration loop (Q.131-134) only learns from LIVE commits;
# with the factory running on DRAFTs forever (auditoria 2026-06-11: 154 DRAFT
# vs 2 LIVE, last 2026-06-02) the deviation model goes silently blind.
CODE_PLAN_LIVE_STALENESS = "PLAN_LIVE_STALENESS"                  # WARN/CRITICAL


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
