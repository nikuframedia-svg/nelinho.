"""FASE 6.2 (HIGH-40) — ondelete on ModelRoutingAssignment FKs

Migration 016 created `plan.model_routing_assignment` with FKs to
`plan.routing_template.id` but didn't specify `ondelete`. Postgres
defaulted to `NO ACTION`, which lets a template stay deletable only
when no assignment references it — but if someone forces a delete
(or the FK was never properly enforced) the assignments stayed
orphaned with a dangling primary_template_id.

Now:

* ``primary_template_id`` → ``ON DELETE CASCADE`` — the assignment
  is meaningless without the template it points to.
* ``alt_template_id`` → ``ON DELETE SET NULL`` — losing the variant
  template should leave the assignment functional (variant=B falls
  back to primary, as documented).

Constraint names match the legacy auto-generated pattern Postgres
uses on a column-level FK: ``<table>_<column>_fkey``.

Revision ID: 039_routing_assignment_ondelete
Revises: 038_idempotency_constraints
Create Date: 2026-05-02
"""
from alembic import op


revision = '039_routing_assignment_ondelete'
down_revision = '038_idempotency_constraints'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # primary_template_id → CASCADE
    op.execute(
        "ALTER TABLE plan.model_routing_assignment "
        "DROP CONSTRAINT IF EXISTS model_routing_assignment_primary_template_id_fkey"
    )
    op.create_foreign_key(
        "model_routing_assignment_primary_template_id_fkey",
        "model_routing_assignment",
        "routing_template",
        ["primary_template_id"],
        ["id"],
        source_schema="plan",
        referent_schema="plan",
        ondelete="CASCADE",
    )

    # alt_template_id → SET NULL
    op.execute(
        "ALTER TABLE plan.model_routing_assignment "
        "DROP CONSTRAINT IF EXISTS model_routing_assignment_alt_template_id_fkey"
    )
    op.create_foreign_key(
        "model_routing_assignment_alt_template_id_fkey",
        "model_routing_assignment",
        "routing_template",
        ["alt_template_id"],
        ["id"],
        source_schema="plan",
        referent_schema="plan",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Revert to NO ACTION (the legacy default).
    op.drop_constraint(
        "model_routing_assignment_primary_template_id_fkey",
        "model_routing_assignment",
        schema="plan",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "model_routing_assignment_primary_template_id_fkey",
        "model_routing_assignment",
        "routing_template",
        ["primary_template_id"],
        ["id"],
        source_schema="plan",
        referent_schema="plan",
    )

    op.drop_constraint(
        "model_routing_assignment_alt_template_id_fkey",
        "model_routing_assignment",
        schema="plan",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "model_routing_assignment_alt_template_id_fkey",
        "model_routing_assignment",
        "routing_template",
        ["alt_template_id"],
        ["id"],
        source_schema="plan",
        referent_schema="plan",
    )
