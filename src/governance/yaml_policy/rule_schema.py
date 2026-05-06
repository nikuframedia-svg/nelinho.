"""Pydantic schema for ``tenant_rules.yaml`` — Sprint Q.17.B.

Defines the canonical DSL for declarative business rules that the LLM
emits from natural-language input via Q.17.C ``/regras`` page. The
schema enforces a closed whitelist of:

- 12 trigger events  (when_event)
- 9 action types     (then_action)
- 8 condition operators

The LLM cannot emit anything outside these whitelists — both by
function-calling spec restriction (Q.17.B llm_tools) and by Pydantic
validation at load time. The runtime engine (Q.17.D) dispatches actions
through a fixed registry; unknown action types raise at validation, never
at runtime.

Ground rules:
- Always-human-approval (decision Luis 2026-05-06): every proposed rule
  starts ``status=proposed``, must be approved before ``activated``.
- Spelke axioms compulsory: ``constraints.axioms_required`` is checked
  pre-activation by Q.17.E sandbox.
- Kill switch admin-SQL-only: this schema deliberately omits a
  ``kill_switch`` action.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Whitelists — closed enums (LLM cannot extend at runtime)
# ---------------------------------------------------------------------------


class EventType(str, Enum):
    """The 12 events a rule can subscribe to.

    Each maps to a specific emission point in the existing codebase:

    - ``schedule_propose``        — CPO emits a proposed schedule
    - ``schedule_committed``      — schedule reaches DB commit
    - ``kpi_threshold_crossed``   — daily KPI rolls below/above target
    - ``mold_usage_threshold``    — mold cycle counter passes a threshold
    - ``worker_absent``           — worker marks absence (HR)
    - ``quality_event_logged``    — defect/rework recorded
    - ``transport_loaded``        — truck batch sealed
    - ``phase_drift_detected``    — drift detector flags a phase
    - ``decision_pending``        — new decision enters timeline
    - ``rule_rejected``           — Camada 1 detector signal
    - ``wip_threshold``           — WIP per phase exceeds bound
    - ``time_trigger``            — cron-like temporal event (e.g. fri-16h)
    """

    SCHEDULE_PROPOSE = "schedule_propose"
    SCHEDULE_COMMITTED = "schedule_committed"
    KPI_THRESHOLD_CROSSED = "kpi_threshold_crossed"
    MOLD_USAGE_THRESHOLD = "mold_usage_threshold"
    WORKER_ABSENT = "worker_absent"
    QUALITY_EVENT_LOGGED = "quality_event_logged"
    TRANSPORT_LOADED = "transport_loaded"
    PHASE_DRIFT_DETECTED = "phase_drift_detected"
    DECISION_PENDING = "decision_pending"
    RULE_REJECTED = "rule_rejected"
    WIP_THRESHOLD = "wip_threshold"
    TIME_TRIGGER = "time_trigger"


class ActionType(str, Enum):
    """The 9 actions a rule can dispatch.

    Each maps to a handler in the runtime dispatcher (Q.17.D).
    Whitelist is closed: rules cannot invoke arbitrary code.

    - ``alert``                — emit an AlertCard
    - ``block``                — refuse the proposed action
    - ``modify_fitness``       — multiply a fitness weight (bounded ±50%)
    - ``reassign_worker``      — substitute operator on a phase
    - ``propose_maintenance``  — create maintenance suggestion
    - ``notify``               — push toast / SSE channel
    - ``set_config``           — update ConfigStore key (audit trail)
    - ``create_decision``      — open a governance decision
    - ``pause_writes``         — fail-closed temporarily on a route prefix
    """

    ALERT = "alert"
    BLOCK = "block"
    MODIFY_FITNESS = "modify_fitness"
    REASSIGN_WORKER = "reassign_worker"
    PROPOSE_MAINTENANCE = "propose_maintenance"
    NOTIFY = "notify"
    SET_CONFIG = "set_config"
    CREATE_DECISION = "create_decision"
    PAUSE_WRITES = "pause_writes"


class ConditionOp(str, Enum):
    """The 8 condition operators supported in ``when.conditions[*].op``.

    Restricted set — no boolean combinators (``and``/``or``) at this
    layer. Rule conditions are AND-joined by construction; OR semantics
    must be expressed by emitting two separate rules.
    """

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    IN = "in"
    MATCHES = "matches"  # regex (compiled with timeout)


class RuleStatus(str, Enum):
    """Workflow states for a rule's life-cycle."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ROLLED_BACK = "rolled_back"


# ---------------------------------------------------------------------------
# Per-event field schemas
# ---------------------------------------------------------------------------

# The fields a condition can reference depend on the event_type. Locking
# these per-event prevents the LLM from inventing fields that the
# dispatcher would not know how to bind.
EVENT_FIELDS: dict[EventType, frozenset[str]] = {
    EventType.SCHEDULE_PROPOSE: frozenset({
        "tenant_id", "schedule_id", "horizon_days", "operations_count",
        "fitness_score", "makespan_hours", "tardiness_hours",
    }),
    EventType.SCHEDULE_COMMITTED: frozenset({
        "tenant_id", "schedule_id", "commit_sha", "operations_count",
    }),
    EventType.KPI_THRESHOLD_CROSSED: frozenset({
        "kpi_name", "kpi_value", "threshold", "direction", "as_of_date",
    }),
    EventType.MOLD_USAGE_THRESHOLD: frozenset({
        "mold_id", "mold_code", "uses_count", "threshold",
    }),
    EventType.WORKER_ABSENT: frozenset({
        "worker_id", "worker_name", "phase_id", "shift", "day_of_week",
        "absence_type", "absence_date",
    }),
    EventType.QUALITY_EVENT_LOGGED: frozenset({
        "of_id", "phase_id", "error_code", "severity",
        "causer_employee_id", "mold_id", "supplier_id",
    }),
    EventType.TRANSPORT_LOADED: frozenset({
        "batch_id", "client_code", "boats_count", "transport_date",
        "fill_ratio",
    }),
    EventType.PHASE_DRIFT_DETECTED: frozenset({
        "phase_id", "metric", "drift_score", "p_value", "lookback_days",
    }),
    EventType.DECISION_PENDING: frozenset({
        "decision_id", "decision_type", "risk_level", "autonomy_level",
        "proposed_by",
    }),
    EventType.RULE_REJECTED: frozenset({
        "decision_type", "rejection_category", "rejected_by",
        "consecutive_count",
    }),
    EventType.WIP_THRESHOLD: frozenset({
        "phase_id", "wip_count", "threshold", "as_of_date",
    }),
    EventType.TIME_TRIGGER: frozenset({
        "cron", "day_of_week", "hour", "minute", "timezone",
    }),
}


# Same idea for action params — locks the LLM to a known shape per action.
ACTION_PARAMS: dict[ActionType, frozenset[str]] = {
    ActionType.ALERT: frozenset({
        "severity", "title", "message_pt", "entity_refs",
    }),
    ActionType.BLOCK: frozenset({
        "reason_pt", "scope",  # scope: "phase" | "schedule" | "operation"
    }),
    ActionType.MODIFY_FITNESS: frozenset({
        "weight_key", "multiplier",  # bounded ±50% by validator
    }),
    ActionType.REASSIGN_WORKER: frozenset({
        "phase_id", "replacement_worker_id", "reason_pt",
    }),
    ActionType.PROPOSE_MAINTENANCE: frozenset({
        "mold_id", "maintenance_type", "scheduled_date", "reason_pt",
    }),
    ActionType.NOTIFY: frozenset({
        "channel",  # "alerts" | "timeline" | "dashboard" | "governance"
        "topic", "payload",
    }),
    ActionType.SET_CONFIG: frozenset({
        "category", "key", "value", "reason_pt",
    }),
    ActionType.CREATE_DECISION: frozenset({
        "decision_type", "title", "risk_level", "action_data",
    }),
    ActionType.PAUSE_WRITES: frozenset({
        "route_prefix", "duration_minutes", "reason_pt",
    }),
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Condition(BaseModel):
    """One condition in ``when.conditions[*]``.

    Conditions are AND-joined by the runtime. Each condition references
    a single field of the trigger event payload via ``field``, applies
    one of 8 operators, and compares against ``value``.
    """

    model_config = ConfigDict(extra="forbid")

    field: str = Field(..., min_length=1, max_length=120)
    op: ConditionOp
    value: Any


class TriggerSpec(BaseModel):
    """The ``when:`` block of a rule."""

    model_config = ConfigDict(extra="forbid")

    event: EventType
    conditions: list[Condition] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_condition_fields(self) -> "TriggerSpec":
        allowed = EVENT_FIELDS[self.event]
        bad = [c.field for c in self.conditions if c.field not in allowed]
        if bad:
            raise ValueError(
                f"event={self.event.value!r} does not expose fields {bad!r}; "
                f"allowed: {sorted(allowed)}"
            )
        return self


class ActionStep(BaseModel):
    """One action in ``then:[*]``."""

    model_config = ConfigDict(extra="forbid")

    action: ActionType
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_action_params(self) -> "ActionStep":
        allowed = ACTION_PARAMS[self.action]
        bad = [k for k in self.params if k not in allowed]
        if bad:
            raise ValueError(
                f"action={self.action.value!r} does not accept params {bad!r}; "
                f"allowed: {sorted(allowed)}"
            )
        # Specific action sanity checks
        if self.action == ActionType.MODIFY_FITNESS:
            mult = self.params.get("multiplier")
            if mult is None or not isinstance(mult, (int, float)):
                raise ValueError("modify_fitness requires numeric 'multiplier'")
            if not (0.5 <= float(mult) <= 1.5):
                raise ValueError(
                    f"modify_fitness multiplier {mult!r} out of bounds; "
                    "must be in [0.5, 1.5] (±50%)"
                )
        if self.action == ActionType.NOTIFY:
            channel = self.params.get("channel")
            allowed_channels = {"alerts", "timeline", "dashboard", "governance"}
            if channel not in allowed_channels:
                raise ValueError(
                    f"notify.channel={channel!r}; must be one of {sorted(allowed_channels)}"
                )
        return self


class AxiomRequirement(str, Enum):
    """The 7 Spelke axioms a rule may declare it preserves.

    Q.17.E sandbox runs each declared axiom against a dry-run schedule
    and refuses activation if any axiom fails. Mirrors the invariants in
    ``src/plan/cpo/safety_net.py``.
    """

    CAPACITY_NON_NEGATIVE = "capacity_non_negative"  # 1
    PRECEDENCE_MONOTONIC = "precedence_monotonic"  # 2
    MOLD_EXCLUSIVE = "mold_exclusive"  # 3
    DUAL_RESOURCE_LAMINAGEM = "dual_resource_laminagem"  # 4
    SKILL_MATCH = "skill_match"  # 5
    CURING_GAPS = "curing_gaps"  # 6
    SAFETY_NET_BASELINE = "safety_net_baseline"  # 7


class ConstraintsSpec(BaseModel):
    """Compile-time invariants the rule pledges to preserve."""

    model_config = ConfigDict(extra="forbid")

    axioms_required: list[AxiomRequirement] = Field(default_factory=list)


class SafetySpec(BaseModel):
    """Runtime safety knobs."""

    model_config = ConfigDict(extra="forbid")

    requires_human_approval: Literal[True] = True
    """Always-human-approval (Luis 2026-05-06). Cannot be disabled."""

    max_fires_per_day: int = Field(default=10, ge=1, le=10_000)
    expires: Optional[date] = None
    kill_switch: Literal["admin_only"] = "admin_only"
    """Kill-switch is admin-SQL-only — no schema toggle."""


class AuditFootprint(BaseModel):
    """Bookkeeping populated by the engine, not authored by the LLM."""

    model_config = ConfigDict(extra="forbid")

    created_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    last_fired: Optional[datetime] = None
    fire_count: int = Field(default=0, ge=0)


class Rule(BaseModel):
    """A single declarative business rule.

    Authored by the LLM (constrained by function-calling spec), validated
    by Pydantic, dry-run by Q.17.E sandbox, approved by an admin/manager,
    activated by the runtime engine.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    description: str = Field(..., min_length=4, max_length=400)
    proposed_by_user_id: Optional[UUID] = None
    proposed_at: Optional[datetime] = None
    status: RuleStatus = RuleStatus.PROPOSED

    when: TriggerSpec
    then: list[ActionStep] = Field(..., min_length=1, max_length=10)

    constraints: ConstraintsSpec = Field(default_factory=ConstraintsSpec)
    safety: SafetySpec = Field(default_factory=SafetySpec)
    audit: AuditFootprint = Field(default_factory=AuditFootprint)

    @field_validator("id")
    @classmethod
    def _id_no_double_separators(cls, v: str) -> str:
        if ".." in v or "--" in v or "__" in v:
            raise ValueError(f"rule.id {v!r}: double separators not allowed")
        return v


class TenantRulesYaml(BaseModel):
    """Top-level shape of ``config/yaml/tenant_rules.yaml``.

    File is editable by admins via Q.17.C ``/regras`` UI; rule entries
    are appended as the LLM emits them and the human approves.
    """

    model_config = ConfigDict(extra="forbid")

    version: int = Field(..., ge=1, le=2)
    schema_name: str = "tenant_rules.v1"
    rules: list[Rule] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_duplicate_ids(self) -> "TenantRulesYaml":
        ids = [r.id for r in self.rules]
        dup = {x for x in ids if ids.count(x) > 1}
        if dup:
            raise ValueError(f"duplicate rule ids: {sorted(dup)}")
        return self
