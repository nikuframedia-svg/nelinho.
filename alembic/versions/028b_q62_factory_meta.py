"""Q.62.A.2 — create factory_meta tables that were create_all-only.

Migration 028_curated_allocation has FK to `factory_meta.ingestion_run.id`
but `factory_meta` schema and tables were only created via
`init_db.create_all()`. Q.62.A.1 trail-fix continues: explicitly create
the 4 factory_meta tables BEFORE 028 uses them.

Tables created:
  * factory_meta.ingestion_run      — ingestion attempt audit
  * factory_meta.active_run         — singleton pointing to active ingestion
  * factory_meta.activation_history — activation log
  * factory_meta.quality_check_result — per-check audit row

Plus 4 ENUM types:
  * sourcetype, ingestionstatus, qualitygatestatus, checkseverity

Position: between 028a (governance orphan) and 028 (curated_allocation).
028's `down_revision` is rebased to `028b_q62_factory_meta`.

Revision ID: 028b_q62_factory_meta
Revises: 027_decision_rejection_category
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "028b_q62_factory_meta"
down_revision = "027_decision_rejection_category"
branch_labels = None
depends_on = None


SOURCE_TYPE_VALUES = ("UPLOAD", "WATCHER", "SCHEDULE")
INGESTION_STATUS_VALUES = (
    "RECEIVED", "VALIDATING", "FAILED", "CURATING", "SUCCEEDED", "SKIPPED",
)
QUALITY_GATE_STATUS_VALUES = ("PENDING", "PASSED", "FAILED")
CHECK_SEVERITY_VALUES = ("BLOCKING", "WARNING", "INFO")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS factory_meta")

    # ─── ENUMS ────────────────────────────────────────────────────────
    source_type = postgresql.ENUM(
        *SOURCE_TYPE_VALUES, name="sourcetype", create_type=False,
    )
    source_type.create(op.get_bind(), checkfirst=True)

    ingestion_status = postgresql.ENUM(
        *INGESTION_STATUS_VALUES, name="ingestionstatus", create_type=False,
    )
    ingestion_status.create(op.get_bind(), checkfirst=True)

    quality_gate_status = postgresql.ENUM(
        *QUALITY_GATE_STATUS_VALUES, name="qualitygatestatus", create_type=False,
    )
    quality_gate_status.create(op.get_bind(), checkfirst=True)

    check_severity = postgresql.ENUM(
        *CHECK_SEVERITY_VALUES, name="checkseverity", create_type=False,
    )
    check_severity.create(op.get_bind(), checkfirst=True)

    # ─── ingestion_run ────────────────────────────────────────────────
    op.create_table(
        "ingestion_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                *SOURCE_TYPE_VALUES, name="sourcetype", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                *INGESTION_STATUS_VALUES, name="ingestionstatus", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "duplicate_of_ingestion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("factory_meta.ingestion_run.id"),
            nullable=True,
        ),
        sa.Column(
            "quality_gate_status",
            postgresql.ENUM(
                *QUALITY_GATE_STATUS_VALUES,
                name="qualitygatestatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "quality_report_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_rows_raw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_rows_curated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Index("ix_ingestion_run_file_sha256", "file_sha256"),
        sa.Index("ix_ingestion_run_status", "status"),
        sa.Index("ix_ingestion_run_created_at", "created_at_utc"),
        schema="factory_meta",
    )

    # ─── active_run ───────────────────────────────────────────────────
    op.create_table(
        "active_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "active_ingestion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("factory_meta.ingestion_run.id"),
            nullable=False,
        ),
        sa.Column("activated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_by", sa.String(255), nullable=False),
        schema="factory_meta",
    )

    # ─── activation_history ───────────────────────────────────────────
    op.create_table(
        "activation_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ingestion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("factory_meta.ingestion_run.id"),
            nullable=False,
        ),
        sa.Column("activated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_by", sa.String(255), nullable=False),
        sa.Column("deactivated_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Index("ix_activation_history_ingestion", "ingestion_id"),
        schema="factory_meta",
    )

    # ─── quality_check_result ─────────────────────────────────────────
    op.create_table(
        "quality_check_result",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ingestion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("factory_meta.ingestion_run.id"),
            nullable=False,
        ),
        sa.Column("check_id", sa.String(100), nullable=False),
        sa.Column(
            "severity",
            postgresql.ENUM(
                *CHECK_SEVERITY_VALUES, name="checkseverity", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column(
            "details_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_quality_check_ingestion", "ingestion_id"),
        sa.Index("ix_quality_check_check_id", "check_id"),
        schema="factory_meta",
    )


def downgrade() -> None:
    op.drop_table("quality_check_result", schema="factory_meta")
    op.drop_table("activation_history", schema="factory_meta")
    op.drop_table("active_run", schema="factory_meta")
    op.drop_table("ingestion_run", schema="factory_meta")
    op.execute("DROP TYPE IF EXISTS checkseverity")
    op.execute("DROP TYPE IF EXISTS qualitygatestatus")
    op.execute("DROP TYPE IF EXISTS ingestionstatus")
    op.execute("DROP TYPE IF EXISTS sourcetype")
