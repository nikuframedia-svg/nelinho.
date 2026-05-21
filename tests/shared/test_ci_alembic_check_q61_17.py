"""Q.61.17 — pin: CI tem job que corre `alembic check`.

Se alguem remove o job (ou o `alembic check` step dentro dele), o test
falha imediatamente — protege contra "stop the bleeding" regressao.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CI_YAML = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
)


def _load_ci_jobs() -> dict:
    assert CI_YAML.exists(), f".github/workflows/ci.yml em falta em {CI_YAML}"
    cfg = yaml.safe_load(CI_YAML.read_text(encoding="utf-8"))
    return cfg.get("jobs") or {}


def test_ci_has_alembic_job():
    jobs = _load_ci_jobs()
    assert "alembic" in jobs, (
        "CI sem job 'alembic' — Q.61.17 regression. "
        "Falta o gate que apanha drift entre Base.metadata e HEAD migration."
    )


def test_alembic_job_has_postgres_service():
    jobs = _load_ci_jobs()
    services = jobs["alembic"].get("services", {})
    assert "postgres" in services, (
        "Alembic job sem Postgres service — `alembic check` precisa de DB ligado."
    )


def test_alembic_job_runs_check_step():
    jobs = _load_ci_jobs()
    steps = jobs["alembic"].get("steps", [])
    has_check = any(
        "alembic check" in (s.get("run") or "")
        for s in steps
    )
    assert has_check, (
        "Alembic job nao corre `alembic check` — Q.61.17 incompleto."
    )


def test_alembic_job_applies_migrations_before_check():
    """`alembic check` so e util DEPOIS de `alembic upgrade head`."""
    jobs = _load_ci_jobs()
    steps = jobs["alembic"].get("steps", [])

    upgrade_idx = None
    check_idx = None
    for i, s in enumerate(steps):
        run = s.get("run") or ""
        if "alembic upgrade head" in run and upgrade_idx is None:
            upgrade_idx = i
        if "alembic check" in run and check_idx is None:
            check_idx = i

    assert upgrade_idx is not None, "Falta `alembic upgrade head`"
    assert check_idx is not None, "Falta `alembic check`"
    assert upgrade_idx < check_idx, (
        f"Ordem invertida: upgrade no step {upgrade_idx} mas check no "
        f"step {check_idx}. Check tem de vir DEPOIS do upgrade."
    )
