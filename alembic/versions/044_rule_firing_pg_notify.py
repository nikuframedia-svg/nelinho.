"""Sprint Q.14.B — `pg_notify` trigger on `governance.rule_firing`.

Adds the push side of the rule-firing log: every INSERT into
``governance.rule_firing`` whose ``rule_id`` matches the operator-
configurable allowlist fires a Postgres NOTIFY on channel
``rule_firing``. The asyncpg listener in
``src/shared/realtime/notify_listener.py`` consumes it and routes
the payload through the existing :class:`RealtimeBridge` so SSE
clients receive a push within ~5ms instead of waiting for the next
15-minute alert scan.

Allowlist policy
----------------

The trigger checks a small allowlist embedded in the function body:

  * ``alerts.bottleneck_formation``
  * ``alerts.skills_concentration``
  * ``alerts.quality_degradation``
  * ``improve.generate_via_llm``

These are the rules that today produce time-sensitive output worth
pushing immediately. Other rules still get logged to ``rule_firing``
(auditable in the dashboard) but DON'T trigger a NOTIFY — preventing
spam and keeping the SSE channel high-signal.

The allowlist intentionally lives in SQL (not Python config) because
the trigger function executes inside the DB on every INSERT and an
external lookup would defeat the purpose. The list is short + stable
enough that a migration is the right cadence to update it. Future
sprints can move it to a small `realtime_push_config` table when the
shape demands it.

Payload shape
-------------

The NOTIFY body is a JSON dict with the minimal fields a frontend
client needs to render a toast / popover:

  {
    "id": "<uuid>",
    "tenant_id": "<uuid>",
    "rule_id": "alerts.bottleneck_formation",
    "fired_at": "2026-05-04T15:23:11.123Z",
    "rule_output": {...},
    "fire_count": 1
  }

Postgres NOTIFY payloads have an 8000-byte ceiling. Big JSONB blobs
must NOT go into the payload — the trigger only forwards the small
summary shape above. The full row is still queryable via
``GET /v1/governance/rule-firings`` after the push lands.

Revision ID: 044_rule_firing_pg_notify
Revises: 043_rule_firing_log
Create Date: 2026-05-04
"""

from alembic import op


revision = "044_rule_firing_pg_notify"
down_revision = "043_rule_firing_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trigger function — allowlist hard-coded so the DB doesn't need to
    # join another table on every INSERT.
    op.execute("""
        CREATE OR REPLACE FUNCTION governance.notify_rule_firing()
        RETURNS TRIGGER AS $$
        DECLARE
            payload JSON;
        BEGIN
            -- Allowlist: only push for time-sensitive rules.
            IF NEW.rule_id NOT IN (
                'alerts.bottleneck_formation',
                'alerts.skills_concentration',
                'alerts.quality_degradation',
                'improve.generate_via_llm'
            ) THEN
                RETURN NEW;
            END IF;

            -- Compose the small summary shape. Full row stays queryable
            -- via GET /v1/governance/rule-firings.
            payload := json_build_object(
                'id', NEW.id::text,
                'tenant_id', NEW.tenant_id::text,
                'rule_id', NEW.rule_id,
                'fired_at', NEW.fired_at,
                'rule_output', NEW.rule_output,
                'fire_count', NEW.fire_count
            );

            -- pg_notify channel name doesn't accept dynamic SQL, so it's
            -- a literal. The asyncpg listener subscribes to this exact
            -- channel name in src/shared/realtime/notify_listener.py.
            PERFORM pg_notify('rule_firing', payload::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS rule_firing_notify_trigger
        ON governance.rule_firing;
    """)
    op.execute("""
        CREATE TRIGGER rule_firing_notify_trigger
        AFTER INSERT ON governance.rule_firing
        FOR EACH ROW
        EXECUTE FUNCTION governance.notify_rule_firing();
    """)


def downgrade() -> None:
    op.execute("""
        DROP TRIGGER IF EXISTS rule_firing_notify_trigger
        ON governance.rule_firing;
    """)
    op.execute("DROP FUNCTION IF EXISTS governance.notify_rule_firing();")
