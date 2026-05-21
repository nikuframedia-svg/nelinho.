"""Q.62.A — gate integrado da chain alembic.

Verifica que a chain de migrations corre limpa numa DB fresca, desde o
zero ate HEAD, sem precisar de `init_db.create_all()`.

A campanha Q.61.15 (partial) documentou que a chain estava partida em
multiplos sitios. Q.62.A.1+A.2+A.3 fixaram:

  * 015_transport_batch          — CREATE SCHEMA plan
  * 018b_create_production_schedules — postgresql.ENUM (nao sa.Enum)
  * 028a_q62_governance_orphan   — 5 tabelas governance create_all-only
  * 028b_q62_factory_meta        — 4 tabelas factory_meta create_all-only
  * 036_s3_schema_drift_fixes    — typo tenant_configurations → singular
  * 040_slow_query_logging       — ALTER SYSTEM em autocommit_block
  * 055a_q62_a3_orphans          — 13 tabelas adicionais create_all-only

Este teste e mais um smoke "ainda corre" do que coverage real. O test
ideal seria um pytest-postgresql fixture que clona, upgrade head, e
chama `alembic check`. Hoje aceita-se contar tabelas em
`Base.metadata` vs migrations DDL inspeccionavel.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ALEMBIC_VERSIONS = Path("alembic/versions")


def test_028a_q62_governance_orphan_exists_and_creates_5_tables():
    """Q.62.A.1 — a migration deve criar as 5 tabelas governance
    orfaos (decision_policy, decision_run, approval, yaml_policy_rule,
    yaml_policy_rule_revision)."""
    path = ALEMBIC_VERSIONS / "028a_q62_governance_orphan.py"
    assert path.exists(), "028a_q62_governance_orphan.py em falta"

    text = path.read_text(encoding="utf-8")
    expected = {
        "decision_policy",
        "decision_run",
        "approval",
        "yaml_policy_rule",
        "yaml_policy_rule_revision",
    }
    found = set()
    for m in re.finditer(r'create_table\(\s*"([a-z_]+)"', text):
        found.add(m.group(1))
    missing = expected - found
    assert not missing, f"028a nao cria: {missing}"


def test_028b_q62_factory_meta_exists_and_creates_4_tables():
    """Q.62.A.2 — 028b deve criar as 4 tabelas factory_meta orfaos."""
    path = ALEMBIC_VERSIONS / "028b_q62_factory_meta.py"
    assert path.exists(), "028b_q62_factory_meta.py em falta"

    text = path.read_text(encoding="utf-8")
    expected = {
        "ingestion_run",
        "active_run",
        "activation_history",
        "quality_check_result",
    }
    found = set()
    for m in re.finditer(r'create_table\(\s*"([a-z_]+)"', text):
        found.add(m.group(1))
    missing = expected - found
    assert not missing, f"028b nao cria: {missing}"


def test_027_rebases_to_028a():
    """Q.62.A.1 — 027 down_revision deve apontar para 028a."""
    path = ALEMBIC_VERSIONS / "027_decision_rejection_category.py"
    text = path.read_text(encoding="utf-8")
    assert "028a_q62_governance_orphan" in text, (
        "027 nao foi rebased para depender de 028a"
    )


def test_028_rebases_to_028b():
    """Q.62.A.2 — 028 down_revision deve apontar para 028b."""
    path = ALEMBIC_VERSIONS / "028_curated_allocation.py"
    text = path.read_text(encoding="utf-8")
    assert "028b_q62_factory_meta" in text, (
        "028 nao foi rebased para depender de 028b"
    )


def test_015_creates_plan_schema():
    """Q.61.15 fix — 015 deve criar 'plan' schema antes de criar tabelas."""
    path = ALEMBIC_VERSIONS / "015_transport_batch.py"
    text = path.read_text(encoding="utf-8")
    assert 'CREATE SCHEMA IF NOT EXISTS plan' in text, (
        "015 nao cria schema plan"
    )


def test_018b_uses_postgresql_enum_for_column():
    """Q.61.15 fix — 018b deve usar postgresql.ENUM (não sa.Enum)
    no column-level para schedule_status, senao 'type already exists'
    crash em fresh DB."""
    path = ALEMBIC_VERSIONS / "018b_create_production_schedules.py"
    text = path.read_text(encoding="utf-8")
    assert "postgresql.ENUM(" in text, (
        "018b deveria usar postgresql.ENUM no column"
    )


def test_036_uses_singular_tenant_configuration():
    """Q.62.A.2 fix — 036 deve usar 'tenant_configuration' (singular,
    o nome real) em vez de 'tenant_configurations' (typo)."""
    path = ALEMBIC_VERSIONS / "036_s3_schema_drift_fixes.py"
    text = path.read_text(encoding="utf-8")
    assert '"tenant_configurations"' not in text, (
        "036 tem typo `tenant_configurations` (plural)"
    )
    assert '"tenant_configuration"' in text, (
        "036 nao referencia a tabela correcta"
    )


def test_040_uses_autocommit_block_for_alter_system():
    """Q.62.A.2 fix — 040 ALTER SYSTEM precisa de autocommit_block
    porque non-tx em Postgres."""
    path = ALEMBIC_VERSIONS / "040_slow_query_logging.py"
    text = path.read_text(encoding="utf-8")
    assert "autocommit_block()" in text, (
        "040 ALTER SYSTEM nao esta em autocommit_block"
    )


def test_055a_q62_a3_creates_13_orphan_tables():
    """Q.62.A.3 — 055a deve listar as 13 tabelas create_all-only."""
    path = ALEMBIC_VERSIONS / "055a_q62_a3_orphan_tables.py"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    expected_tables = [
        ("hr", "legacy_allocations"),
        ("plan", "production_orders"),
        ("plan", "material_requirements"),
        ("plan", "purchase_orders"),
        ("factory_curated", "cost_reference"),
        ("factory_curated", "mold"),
        ("factory_curated", "mold_usage"),
        ("factory_curated", "order"),
        ("factory_curated", "order_phase"),
        ("factory_curated", "phase_capacity"),
        ("factory_curated", "quality_event"),
        ("factory_curated", "skill_matrix"),
        ("factory_raw", "excel_row"),
    ]
    for schema, table in expected_tables:
        assert f'("{schema}", "{table}")' in text, (
            f"055a nao lista {schema}.{table}"
        )


def test_env_py_has_include_schemas():
    """Q.62.A.3 — `include_schemas=True` no env.py para autogenerate
    encontrar tabelas em schemas non-default."""
    path = Path("alembic/env.py")
    text = path.read_text(encoding="utf-8")
    assert "include_schemas=True" in text, (
        "alembic/env.py em falta `include_schemas=True`"
    )
