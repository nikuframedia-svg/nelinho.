"""Sprint S3 — guard tests for schema drift fixes.

These tests are pure-Python (no DB roundtrip): they introspect the SQLAlchemy
metadata and the alembic chain so a regression is caught at unit-test time,
not when the migration crashes against production.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from sqlalchemy import UniqueConstraint


# --- Φ2: governance model tablename matches migration 007 --------------------

def test_shared_decision_run_tablename_matches_migration():
    from src.shared.models.governance import SharedDecisionRun

    assert SharedDecisionRun.__table__.name == "decision_runs"
    assert SharedDecisionRun.__table__.schema == "shared"


def test_decision_approval_fk_targets_decision_runs():
    from src.shared.models.governance import DecisionApproval

    fks = list(DecisionApproval.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].target_fullname == "shared.decision_runs.id"
    assert fks[0].ondelete == "CASCADE"


# --- UNIQUE outbox in model --------------------------------------------------

def test_event_outbox_has_idempotency_unique_constraint():
    from src.shared.outbox_models import EventOutbox

    unique = [
        c for c in EventOutbox.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]
    assert len(unique) == 1, "exactly one UNIQUE constraint expected"
    cols = sorted(col.name for col in unique[0].columns)
    assert cols == ["aggregate_id", "event_type", "tenant_id"]


# --- Φ3 + S3.033 alembic chain ----------------------------------------------

VERSIONS_DIR = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def _load_revisions():
    revs = {}
    for f in sorted(os.listdir(VERSIONS_DIR)):
        if not f.endswith(".py") or f.startswith("__"):
            continue
        spec = importlib.util.spec_from_file_location(f, VERSIONS_DIR / f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rev = getattr(mod, "revision", None)
        down = getattr(mod, "down_revision", None)
        if rev:
            revs[rev] = down
    return revs


def test_alembic_chain_has_single_head():
    revs = _load_revisions()
    parents = {d for d in revs.values() if d}
    heads = set(revs.keys()) - parents
    # The chain head moves as new migrations land; what matters is that there
    # is exactly *one* head. Multiple heads mean two parallel branches that
    # would crash at `alembic upgrade head` time.
    assert len(heads) == 1, f"expected single head, got {heads}"


def test_migration_007_creates_shared_schema():
    """Φ3: ensure migration 007 explicitly creates the `shared` schema."""
    text = (VERSIONS_DIR / "007_create_decision_ledger.py").read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS shared" in text


def test_migration_create_core_creates_core_schema():
    """Φ3: ensure the core-tables migration creates the `core` schema."""
    target = VERSIONS_DIR / "20260120_1303_6a8943269014_create_core_tables.py"
    text = target.read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS core" in text


def test_migration_036_present():
    target = VERSIONS_DIR / "036_s3_schema_drift_fixes.py"
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    # Sanity: covers each of the 4 fixes.
    assert 'op.alter_column("tenants", "status"' in text
    assert "valid_from" in text
    assert "burden_rate" in text
    assert "idx_operations_machine_id" in text
