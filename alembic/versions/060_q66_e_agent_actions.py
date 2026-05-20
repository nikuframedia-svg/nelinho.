"""Q.66.E.3 - tabela core.agent_actions para observability do copiloto.

Cada chamada do copiloto (intent, model, latency, outcome, escalated)
fica registada com trace_id para correlacionar com audit_log + outbox.
Endpoint GET /v1/observability/agent-actions le paginated com filtros
(Honeycomb-style: traces searchable por intent/user/outcome/window).

Schema:
  * id UUID pk
  * tenant_id UUID NOT NULL indexed
  * user_id UUID NULL (null = sistema)
  * intent String(50) NOT NULL indexed (ex: "kpi_current")
  * model String(80) NULL ("gemma3:e4b", "ollama-llama"...)
  * latency_ms Integer NOT NULL
  * outcome String(20) NOT NULL ("success"|"error"|"timeout"|"skipped")
  * escalated Boolean NOT NULL default false (true = gerou DecisionRun)
  * decision_run_id UUID NULL (FK soft para shared.decision_runs)
  * trace_id String(64) NULL indexed (mesma convencao Q.66.B.1)
  * error_message Text NULL
  * created_at DateTime(tz) NOT NULL default now() indexed

RLS: aplicado (consistente com as outras 87 tabelas do Q.62.B). Policy
`tenant_isolation` filtra por current_setting('app.tenant_id').

Revision ID: 060_q66_e_agent_actions
Revises: 059_q66_e_outbox_backoff
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "060_q66_e_agent_actions"
down_revision = "059_q66_e_outbox_backoff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_actions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intent", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column(
            "escalated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("decision_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_agent_actions_tenant_id",
        "agent_actions",
        ["tenant_id"],
        schema="core",
    )
    op.create_index(
        "ix_core_agent_actions_intent",
        "agent_actions",
        ["intent"],
        schema="core",
    )
    op.create_index(
        "ix_core_agent_actions_trace_id",
        "agent_actions",
        ["trace_id"],
        schema="core",
    )
    op.create_index(
        "ix_core_agent_actions_created_at",
        "agent_actions",
        ["created_at"],
        schema="core",
    )

    # RLS consistente com Q.62.B (87 tabelas tenant-scoped). DROP first
    # para idempotency em re-run.
    op.execute("ALTER TABLE core.agent_actions ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON core.agent_actions")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON core.agent_actions
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON core.agent_actions")
    op.execute("ALTER TABLE core.agent_actions DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_core_agent_actions_created_at",
        table_name="agent_actions",
        schema="core",
    )
    op.drop_index(
        "ix_core_agent_actions_trace_id",
        table_name="agent_actions",
        schema="core",
    )
    op.drop_index(
        "ix_core_agent_actions_intent",
        table_name="agent_actions",
        schema="core",
    )
    op.drop_index(
        "ix_core_agent_actions_tenant_id",
        table_name="agent_actions",
        schema="core",
    )
    op.drop_table("agent_actions", schema="core")
