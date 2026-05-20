"""Sprint Q.13.B (B2) — enable Postgres slow-query logging.

Sets ``log_min_duration_statement = 1000`` so any query that takes
longer than 1 second lands in the Postgres log. Combined with the
upcoming OTLP wiring (B1), this gives the team a fast path from
"the dashboard is slow" → "this exact query took 4.2s on every CEO
dashboard load".

`ALTER SYSTEM SET` writes to ``postgresql.auto.conf`` and survives
restarts. We also set ``log_statement_sample_rate = 1.0`` for the
slow ones so we get the full text, not a sampled subset.

Reverting (down) sets the threshold back to -1 (= disabled), the
Postgres default. The auto.conf entry is removed on the next
``RESET ALL``; this migration explicitly issues that reset on
downgrade so a rollback doesn't leave dangling config.

Notes / caveats:
* Requires the migration runner to have superuser privileges (or
  membership in pg_read_all_settings + pg_write_server_files). The
  ProdPlan deploy uses the dedicated `prodplan` role with these
  grants.
* `pg_reload_conf()` is called so the change takes effect without
  a full restart. Connections opened before the reload keep the
  old value until they cycle.

Revision ID: 040_slow_query_logging
Revises: 039_routing_assignment_ondelete
Create Date: 2026-05-02
"""

from alembic import op


revision = "040_slow_query_logging"
down_revision = "039_routing_assignment_ondelete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Q.62.A.2 — `ALTER SYSTEM` é non-transactional em Postgres.
    # Alembic envolve cada migration numa transacção implícita; com
    # `autocommit_block()` saímos temporariamente da tx para correr o
    # DDL non-tx, e voltamos depois.
    with op.get_context().autocommit_block():
        # Threshold 1000ms — anything slower lands in the log.
        op.execute("ALTER SYSTEM SET log_min_duration_statement = 1000")
        # Sample 100% of slow statements.
        op.execute("ALTER SYSTEM SET log_statement_sample_rate = 1.0")
        # Apply without restart.
        op.execute("SELECT pg_reload_conf()")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER SYSTEM RESET log_min_duration_statement")
        op.execute("ALTER SYSTEM RESET log_statement_sample_rate")
        op.execute("SELECT pg_reload_conf()")
