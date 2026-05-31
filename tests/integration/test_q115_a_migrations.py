"""Q.115.A — testes de integracao das 10 migrations.

Marcados com `integration` — precisam de DB Postgres real.
Para correr: pytest tests/integration/test_q115_a_migrations.py -v -m integration

Test 1: model_registry importa todas as classes sem ImportError
Test 2: CHECK constraints rejeitam valores invalidos
Test 3: tabelas existem com schema correcto (requer alembic upgrade head)
Test 4: RLS habilitado e policy tenant_isolation activa (requer DB real)
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Test 1 — imports sem erro (pode correr sempre, sem DB)
# ---------------------------------------------------------------------------

def test_model_registry_imports_without_error() -> None:
    """model_registry.py importa todas as classes Q.115.A sem ImportError."""
    # side-effect import — se houver circular import ou typo, explode aqui
    import src.shared.model_registry  # noqa: F401


def test_q115_models_importable_directly() -> None:
    """Cada classe Q.115.A e importavel directamente do modulo."""
    from src.core.models.user_input import UserInput
    from src.core.models.daily_revenue_target import DailyRevenueTarget
    from src.core.models.client_priority import ClientPriority
    from src.governance.models.phase_operator_affinity import PhaseOperatorAffinity
    from src.quality.models.runbook import Runbook, ErrorTypeRunbookLink
    from src.plan.models.fases_of_history import FasesOfHistory
    from src.hr.models.worker_phase_assignment import WorkerPhaseAssignment
    from src.ml.models.drift_event import DriftEvent

    # verificar tablenames + schemas
    assert UserInput.__tablename__ == "user_input"
    assert UserInput.__table_args__[-1]["schema"] == "core"

    assert DailyRevenueTarget.__tablename__ == "daily_revenue_target"
    assert DailyRevenueTarget.__table_args__[-1]["schema"] == "core"

    assert ClientPriority.__tablename__ == "client_priority"
    assert ClientPriority.__table_args__[-1]["schema"] == "core"

    assert PhaseOperatorAffinity.__tablename__ == "phase_operator_affinity"
    assert PhaseOperatorAffinity.__table_args__[-1]["schema"] == "governance"

    assert Runbook.__tablename__ == "runbook"
    assert Runbook.__table_args__[-1]["schema"] == "quality"

    assert ErrorTypeRunbookLink.__tablename__ == "error_type_runbook_link"
    assert ErrorTypeRunbookLink.__table_args__[-1]["schema"] == "quality"

    assert FasesOfHistory.__tablename__ == "fases_of_history"
    assert FasesOfHistory.__table_args__[-1]["schema"] == "plan"

    assert WorkerPhaseAssignment.__tablename__ == "worker_phase_assignment"
    assert WorkerPhaseAssignment.__table_args__[-1]["schema"] == "hr"

    assert DriftEvent.__tablename__ == "drift_event"
    assert DriftEvent.__table_args__[-1]["schema"] == "ml"


# ---------------------------------------------------------------------------
# Test 2 — CHECK constraints (validacao pelo SQLAlchemy metadata, sem DB)
# ---------------------------------------------------------------------------

def _check_names_for_model(model_cls) -> set:
    """Extrai nomes de CheckConstraint de __table_args__, ignorando dicts."""
    from sqlalchemy import CheckConstraint
    return {
        c.name
        for c in model_cls.__table_args__
        if isinstance(c, CheckConstraint)
    }


def test_user_input_check_constraints_declared() -> None:
    """UserInput tem CHECK constraints declaradas.

    O naming convention do metadata e 'ck_%(table_name)s_%(constraint_name)s'
    — portanto os nomes ficam prefixados pelo SQLAlchemy.
    """
    from src.core.models.user_input import UserInput

    names = _check_names_for_model(UserInput)
    # nomes apos aplicacao de naming convention (ck_<table>_<name>)
    assert "ck_user_input_what_min" in names
    assert "ck_user_input_economic_reason_min" in names
    assert "ck_user_input_where_page" in names
    assert "ck_user_input_status" in names


def test_client_priority_check_constraint_declared() -> None:
    from src.core.models.client_priority import ClientPriority

    names = _check_names_for_model(ClientPriority)
    assert "ck_client_priority_range" in names


def test_drift_event_check_constraints_declared() -> None:
    from src.ml.models.drift_event import DriftEvent

    names = _check_names_for_model(DriftEvent)
    assert "ck_drift_event_metric" in names
    assert "ck_drift_event_severity" in names


def test_worker_phase_assignment_check_constraint_declared() -> None:
    from src.hr.models.worker_phase_assignment import WorkerPhaseAssignment

    names = _check_names_for_model(WorkerPhaseAssignment)
    assert "ck_worker_phase_assignment_assignment_type" in names


def test_runbook_check_constraints_declared() -> None:
    from src.quality.models.runbook import Runbook

    names = _check_names_for_model(Runbook)
    assert "ck_runbook_source" in names
    assert "ck_runbook_confidence" in names


def test_phase_operator_affinity_check_constraints_declared() -> None:
    from src.governance.models.phase_operator_affinity import PhaseOperatorAffinity

    names = _check_names_for_model(PhaseOperatorAffinity)
    assert "ck_phase_operator_affinity_score" in names
    assert "ck_phase_operator_affinity_sample_count" in names


# ---------------------------------------------------------------------------
# Test 3 + 4 — tabelas + RLS (requerem DB real com alembic upgrade head)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_tables_exist_after_migrations() -> None:
    """Verifica que as 10 tabelas Q.115.A existem apos alembic upgrade head.

    Requer: DB Postgres com alembic upgrade head ja corrido.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.shared.config import settings

    engine = create_async_engine(settings.database_url, echo=False)
    tables_to_check = [
        ("core", "user_input"),
        ("core", "daily_revenue_target"),
        ("core", "client_priority"),
        ("governance", "phase_operator_affinity"),
        ("quality", "runbook"),
        ("quality", "error_type_runbook_link"),
        ("plan", "fases_of_history"),
        ("hr", "worker_phase_assignment"),
        ("ml", "drift_event"),
    ]
    # rework_entry.boat_id verificada separadamente
    async with engine.connect() as conn:
        for schema, table in tables_to_check:
            result = await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_name = :table"
                ),
                {"schema": schema, "table": table},
            )
            row = result.fetchone()
            assert row is not None, f"Tabela {schema}.{table} nao existe"

        # boat_id em rework_entry
        result = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'quality' AND table_name = 'rework_entry' "
                "AND column_name = 'boat_id'"
            )
        )
        assert result.fetchone() is not None, "Coluna quality.rework_entry.boat_id nao existe"

    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rls_policies_active_on_new_tables() -> None:
    """Verifica que RLS esta habilitado e policy tenant_isolation activa."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.shared.config import settings

    engine = create_async_engine(settings.database_url, echo=False)
    tables_to_check = [
        ("core", "user_input"),
        ("core", "daily_revenue_target"),
        ("core", "client_priority"),
        ("governance", "phase_operator_affinity"),
        ("quality", "runbook"),
        ("quality", "error_type_runbook_link"),
        ("plan", "fases_of_history"),
        ("hr", "worker_phase_assignment"),
        ("ml", "drift_event"),
    ]
    async with engine.connect() as conn:
        for schema, table in tables_to_check:
            # verifica rowsecurity habilitado
            result = await conn.execute(
                text(
                    # pg_class expõe `relrowsecurity` (não `rowsecurity` — essa
                    # é da view pg_tables). Q.134.M1 corrigiu o nome da coluna.
                    "SELECT relrowsecurity FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = :schema AND c.relname = :table"
                ),
                {"schema": schema, "table": table},
            )
            row = result.fetchone()
            assert row is not None, f"{schema}.{table} nao encontrada em pg_class"
            assert row[0] is True, f"RLS nao habilitado em {schema}.{table}"

            # verifica policy tenant_isolation existe
            result = await conn.execute(
                text(
                    "SELECT 1 FROM pg_policies "
                    "WHERE schemaname = :schema AND tablename = :table "
                    "AND policyname = 'tenant_isolation'"
                ),
                {"schema": schema, "table": table},
            )
            assert result.fetchone() is not None, (
                f"Policy tenant_isolation nao existe em {schema}.{table}"
            )

    await engine.dispose()
