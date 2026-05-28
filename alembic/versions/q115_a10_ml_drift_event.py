"""Q.115.A.10 — schema ml + tabela ml.drift_event (deteccao de drift de ML).

Cada vez que o sistema detecta drift num modelo (KS test, PSI, AUC delta,
WMAPE delta), regista aqui com severidade warn/critical. Permite alertas
automaticos e historico de saude dos modelos.

decision_id e FK soft para governance.decision_runs — referencia opcional
quando o drift gerou uma decisao de retreino.

Revision ID: q115_a10_ml_drift_event
Revises: q115_a09_worker_phase_assignment
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_a10_ml_drift_event"
down_revision = "q115_a09_worker_phase_assignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ml")

    op.create_table(
        "drift_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_name", sa.String(80), nullable=False),
        # NULL quando e score-level drift (nao especifico a uma feature)
        sa.Column("feature_name", sa.String(120), nullable=True),
        sa.Column("metric", sa.String(40), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # FK soft para governance.decision_runs
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "metric IN ('ks_stat','psi','auc_delta','wmape_delta')",
            name="ck_drift_event_metric",
        ),
        sa.CheckConstraint(
            "severity IN ('warn','critical')",
            name="ck_drift_event_severity",
        ),
        schema="ml",
    )
    op.create_index(
        "ix_ml_drift_event_tenant_id",
        "drift_event",
        ["tenant_id"],
        schema="ml",
    )
    op.create_index(
        "ix_ml_drift_event_model_name",
        "drift_event",
        ["model_name"],
        schema="ml",
    )

    # RLS — padrao Q.62.B
    op.execute("ALTER TABLE ml.drift_event ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON ml.drift_event")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON ml.drift_event
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON ml.drift_event")
    op.execute("ALTER TABLE ml.drift_event DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_ml_drift_event_model_name", table_name="drift_event", schema="ml")
    op.drop_index("ix_ml_drift_event_tenant_id", table_name="drift_event", schema="ml")
    op.drop_table("drift_event", schema="ml")
    # Nao drop do schema ml — pode ter outras tabelas futuras
