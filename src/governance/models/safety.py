"""Safety + learning SQLA models: kill-switch state, rule firings, preference
rules, causal discovery reports.

Q.67.6.B5 — split out of legacy 936L ``src/governance/models.py``. These are
the auxiliary audit/learning tables that hang off the core decision ledger
without being part of the propose→approve→execute flow.

Schema metadata pinned by ``tests/governance/test_api_models_characterization
_q67.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base, TenantBase

from .enums import (
    CausalDiscoveryStatus,
    PreferenceRuleStatus,
    RuleFiringOutcome,
)


class KillSwitchActive(Base):
    """Sprint Q.12 Onda 2.2 — durable kill-switch state.

    One row per (tenant_id, scope) — activating an already-active scope
    is idempotent (the existing row is updated, not duplicated). When
    revoked we stamp ``deactivated_at`` instead of deleting so the
    audit trail survives. Handlers in :mod:`src.governance.action_executor`
    consult :func:`is_kill_switch_active` before mutating domain state.

    Lives on :class:`Base` (not :class:`TenantBase`) because the table
    is scoped per row (composite PK already includes tenant_id) and we
    want explicit composite-key joins rather than the implicit tenant
    filter ``TenantBase`` adds elsewhere.
    """

    __tablename__ = "kill_switch_active"
    __table_args__ = (
        {"schema": "governance"},
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        nullable=False,
        doc="Free-form scope identifier (e.g. 'all', 'decision_type:reschedule_order').",
    )
    decision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        doc="DecisionRun.id that activated this scope (audit anchor).",
    )
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    activated_by: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deactivated_by: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
    )


# ============================================================================
# Sprint C 2.1 — PreferenceRule (Camada 1 aprendizagem)
# ============================================================================


class PreferenceRule(TenantBase):
    """A pattern learned from `ScheduleCommit.rejected_alternatives`.

    The table is the first tangible moat (§50 of the blueprint): every
    time the manager rejects 5+ plans that share a structural signal
    (e.g. "Laminagem on Fridays"), the detector inserts a DETECTED row
    and the frontend asks the manager to confirm, reject or edit it.

    `predicate` is JSONB so each rule type can carry its own shape — the
    detector + the scheduler are the only consumers and they know the
    schema per type. Keep the column generic so we don't migrate the
    DB every time a new detector is added.
    """

    __tablename__ = "preference_rule"
    __table_args__ = (
        Index(
            "ix_preference_rule_tenant_status",
            "tenant_id", "status",
        ),
        Index(
            "ix_preference_rule_tenant_type",
            "tenant_id", "type",
        ),
        {"schema": "governance"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )

    type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    predicate: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False,
        default=PreferenceRuleStatus.DETECTED.value,
    )
    detected_from_commits: Mapped[List[str]] = mapped_column(
        JSONB, nullable=False, default=list,
    )

    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    confirmed_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True,
    )
    # Sprint E.3 — free-text operator feedback captured at confirm OR
    # reject time. Always optional on confirm; the API requires it on
    # reject so the audit trail has a human reason ("detector overfit on
    # a 2-week vacation gap", "rule is real but belongs to phase X").
    review_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )


# ============================================================================
# CAUSAL DISCOVERY (Sprint Q.13.D D.2)
# ============================================================================


class CausalDiscoveryReport(TenantBase):
    """One PCMCI+ run's output, persisted for human review.

    Sprint Q.13.D D.2 — closes the discovery side of Camada 4. The job
    that creates these rows is the weekly causal-discovery cron in
    :mod:`src.shared.scheduler`. Each row carries the candidate edges
    plus the metadata an operator needs to decide whether to fold them
    into :data:`src.copilot.causal.nelo_dag.ALL_NODES` (the SCM is an
    engineering artefact, not a stats lottery — see discovery module
    docstring).
    """

    __tablename__ = "causal_discovery_report"
    __table_args__ = (
        Index(
            "ix_causal_discovery_tenant_status",
            "tenant_id", "review_status",
        ),
        Index(
            "ix_causal_discovery_discovered_at",
            "discovered_at",
        ),
        {"schema": "governance"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    engine: Mapped[str] = mapped_column(
        String(64), nullable=False, default="tigramite-pcmci+",
    )

    # "ok" / "degraded" / "unavailable" — mirrors DiscoveryReport.status.
    run_status: Mapped[str] = mapped_column(
        String(32), nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tau_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nodes_examined: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # List of DiscoveredEdge.to_json() dicts.
    candidate_edges: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list,
    )

    # Review state.
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False,
        default=CausalDiscoveryStatus.PENDING.value,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    reviewed_by: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True,
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ============================================================================
# RULE FIRING LOG (Sprint Q.14.A)
# ============================================================================


class RuleFiring(TenantBase):
    """One row per rule trigger — the audit substrate for *why* a
    suggestion / alert appeared.

    Sprint Q.14.A — closes the *"why did the system suggest moving
    the batch 3 weeks ago?"* gap. The 16 deterministic + LLM detectors
    today fire silently; this table captures the trigger payload that
    caused the fire and the rule output that was produced, so
    forensics is a SQL query instead of `git blame` + reading detector
    source.

    ``dedupe_key`` collapses repeated firings of the same underlying
    problem (e.g. "batch B-1 has 3 unassigned boats" reported every
    15 min by the alerts engine) into a single row whose
    ``fire_count`` + ``last_fired_at`` track recurrence. A new row is
    only created when the dedupe lookup misses or the previous row's
    ``outcome`` is terminal.

    ``variant_id`` is forward-look for the A/B framework (Q.14.C);
    today it stays NULL. ``correlation_id`` ties related decisions
    (e.g. one CPO solve → 5 transport suggestions all sharing the
    correlation_id of the parent commit).
    """

    __tablename__ = "rule_firing"
    __table_args__ = (
        Index(
            "ix_rule_firing_tenant_rule_fired",
            "tenant_id", "rule_id", "fired_at",
        ),
        Index(
            "ix_rule_firing_tenant_dedupe_fired",
            "tenant_id", "dedupe_key", "fired_at",
        ),
        Index(
            "ix_rule_firing_outcome_fired",
            "outcome", "fired_at",
        ),
        {"schema": "governance"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )

    rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    variant_id: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True,
    )

    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    trigger_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    rule_output: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )

    correlation_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True,
    )
    dedupe_key: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
    )

    outcome: Mapped[str] = mapped_column(
        String(32), nullable=False,
        default=RuleFiringOutcome.PROPOSED.value,
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    accepted_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    fire_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
    )
    last_fired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )


__all__ = [
    "KillSwitchActive",
    "PreferenceRule",
    "CausalDiscoveryReport",
    "RuleFiring",
]
