"""Q.62.A.1 — create governance tables that were create_all-only.

Sprint Q.61.15 audit found 5 tables in `Base.metadata` under schema
`governance` that no migration creates. They existed in dev/prod because
`init_db.create_all()` ran on startup and silently filled the gap. With
Q.61.16 making prod `alembic upgrade head`-only, `alembic upgrade head`
on a fresh DB now fails at migration 027 (which alters
`governance.approval`).

This migration creates the 5 missing tables BEFORE 027 alters them.
027 is rebased: `down_revision = 028a_q62_governance_orphan`.

Tables created:
  * governance.decision_policy           — policy templates per decision_type
  * governance.decision_run              — immutable decision ledger
  * governance.approval                  — approval rows (FK -> decision_run)
  * governance.yaml_policy_rule          — Q.17.C tenant rule state
  * governance.yaml_policy_rule_revision — Q.17.C revision audit (FK -> rule)

Plus 2 ENUM types used by yaml_policy_rule(_revision):
  * yaml_policy_rule_status
  * yaml_policy_rule_revision_action

Q.61.15 trail-fix: 015 (CREATE SCHEMA plan) + 018b (postgresql.ENUM)
+ 028a (this) closes the chain through 027.

Revision ID: 028a_q62_governance_orphan
Revises: 026_preference_rule_review_notes
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "028a_q62_governance_orphan"
down_revision = "026_preference_rule_review_notes"
branch_labels = None
depends_on = None


# Enum values for yaml_policy_rule.status (RuleLifecycleStatus).
RULE_STATUS_VALUES = (
    "proposed", "approved", "active", "suspended", "rolled_back", "rejected",
)
# Enum values for yaml_policy_rule_revision.action (RuleRevisionAction).
REVISION_ACTION_VALUES = (
    "proposed", "approved", "rejected", "modified", "suspended",
    "rolled_back", "reactivated",
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS governance")

    # ─── ENUMS ────────────────────────────────────────────────────────
    rule_status = postgresql.ENUM(
        *RULE_STATUS_VALUES,
        name="yaml_policy_rule_status",
        create_type=False,
    )
    rule_status.create(op.get_bind(), checkfirst=True)

    revision_action = postgresql.ENUM(
        *REVISION_ACTION_VALUES,
        name="yaml_policy_rule_revision_action",
        create_type=False,
    )
    revision_action.create(op.get_bind(), checkfirst=True)

    # ─── decision_policy ──────────────────────────────────────────────
    op.create_table(
        "decision_policy",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("decision_type", sa.String(100), nullable=False, unique=True),
        sa.Column(
            "autonomy_level",
            sa.String(10),
            nullable=False,
            server_default="L2",
        ),
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "required_approvers",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "requires_different_approver",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "auto_approve_if_low_risk",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("max_impact_threshold", sa.Float(), nullable=True),
        sa.Column(
            "requires_sandbox",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "requires_canary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("canary_percentage", sa.Integer(), nullable=True),
        sa.Column(
            "version",
            sa.String(20),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Index("ix_decision_policy_type", "decision_type"),
        sa.Index("ix_governance_decision_policy_tenant_id", "tenant_id"),
        schema="governance",
    )

    # ─── decision_run ─────────────────────────────────────────────────
    op.create_table(
        "decision_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("decision_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "policy_version",
            sa.String(20),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column(
            "autonomy_level",
            sa.String(10),
            nullable=False,
            server_default="L2",
        ),
        sa.Column(
            "action_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "expected_impact",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "actual_impact",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "risk_level",
            sa.String(20),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "evidence_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("input_snapshot_hash", sa.String(64), nullable=True),
        sa.Column("outcome_hash", sa.String(64), nullable=True),
        sa.Column("prev_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("prev_hash", sa.String(64), nullable=True),
        sa.Column("audit_hash", sa.String(64), nullable=False),
        # NB: chain_invalidated* sao adicionados por 033_decision_chain_invalidated.
        sa.Column(
            "proposed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("proposed_by", sa.String(100), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_by", sa.String(100), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_by", sa.String(100), nullable=True),
        sa.Column("rollback_reason", sa.Text(), nullable=True),
        sa.Index("ix_decision_run_type", "decision_type"),
        sa.Index("ix_decision_run_status", "status"),
        sa.Index("ix_decision_run_proposed_at", "proposed_at"),
        sa.Index("ix_governance_decision_run_tenant_id", "tenant_id"),
        schema="governance",
    )

    # ─── approval ─────────────────────────────────────────────────────
    # NB: 027 will add `rejection_category` column. Não a metemos aqui.
    op.create_table(
        "approval",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "decision_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("governance.decision_run.id"),
            nullable=False,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("approved_by", sa.String(100), nullable=False),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("approver_role", sa.String(100), nullable=True),
        sa.Index("ix_approval_decision", "decision_run_id"),
        sa.Index("ix_approval_user", "approved_by"),
        sa.Index("ix_governance_approval_tenant_id", "tenant_id"),
        schema="governance",
    )

    # ─── yaml_policy_rule ─────────────────────────────────────────────
    op.create_table(
        "yaml_policy_rule",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("rule_id", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                *RULE_STATUS_VALUES,
                name="yaml_policy_rule_status",
                create_type=False,
            ),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("proposed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fire_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nl_source", sa.Text(), nullable=True),
        sa.Index(
            "uq_yaml_policy_rule_tenant_rule_id",
            "tenant_id", "rule_id",
            unique=True,
        ),
        sa.Index("ix_yaml_policy_rule_status", "tenant_id", "status"),
        sa.Index("ix_yaml_policy_rule_event_type", "tenant_id", "event_type"),
        sa.Index("ix_governance_yaml_policy_rule_tenant_id", "tenant_id"),
        schema="governance",
    )

    # ─── yaml_policy_rule_revision ────────────────────────────────────
    op.create_table(
        "yaml_policy_rule_revision",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "rule_db_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("governance.yaml_policy_rule.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_id", sa.String(120), nullable=False),
        sa.Column(
            "action",
            postgresql.ENUM(
                *REVISION_ACTION_VALUES,
                name="yaml_policy_rule_revision_action",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "payload_before",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "payload_after",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("nl_source", sa.Text(), nullable=True),
        sa.Index("ix_yaml_policy_rule_revision_rule", "tenant_id", "rule_db_id"),
        sa.Index("ix_yaml_policy_rule_revision_at", "tenant_id", "created_at"),
        sa.Index("ix_governance_yaml_policy_rule_revision_tenant_id", "tenant_id"),
        schema="governance",
    )


def downgrade() -> None:
    op.drop_table("yaml_policy_rule_revision", schema="governance")
    op.drop_table("yaml_policy_rule", schema="governance")
    op.drop_table("approval", schema="governance")
    op.drop_table("decision_run", schema="governance")
    op.drop_table("decision_policy", schema="governance")
    op.execute("DROP TYPE IF EXISTS yaml_policy_rule_revision_action")
    op.execute("DROP TYPE IF EXISTS yaml_policy_rule_status")
