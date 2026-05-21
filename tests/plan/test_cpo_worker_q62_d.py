"""Q.62.D.1 — smoke test do Arq worker para CPO scheduler.

Tests verificam que:
  * `WorkerSettings` importa e tem a configuracao esperada.
  * `cpo_schedule_job` e callable, accepta a assinatura correcta.
  * Job stub levanta `NotImplementedError` (sinaliza que D.2 ainda
    nao extraiu o body do endpoint).
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock
from uuid import UUID

import pytest


_TENANT = "11111111-1111-1111-1111-111111111111"


def test_worker_settings_importable():
    """`WorkerSettings` deve ser importavel sem efeitos colaterais."""
    from src.plan.cpo.worker import WorkerSettings

    assert hasattr(WorkerSettings, "functions")
    assert hasattr(WorkerSettings, "redis_settings")
    assert hasattr(WorkerSettings, "job_timeout")


def test_worker_settings_lists_cpo_schedule_job():
    """Worker deve registar `cpo_schedule_job` como um dos functions."""
    from src.plan.cpo.worker import WorkerSettings, cpo_schedule_job

    assert cpo_schedule_job in WorkerSettings.functions, (
        "cpo_schedule_job nao esta registado em WorkerSettings.functions"
    )


def test_worker_settings_redis_from_settings():
    """Redis URL deve vir de settings.redis_url (config central)."""
    from src.plan.cpo.worker import WorkerSettings
    from src.shared.config import settings

    # `redis_settings` é uma instancia de RedisSettings; .host/port
    # devem corresponder ao redis_url configurado. Smoke check:
    rs = WorkerSettings.redis_settings
    assert rs is not None
    # `from_dsn` parseou a URL; basta confirmar que o host nao é None.
    assert getattr(rs, "host", None) is not None


def test_worker_settings_has_reasonable_timeout():
    """CPO max time_limit_sec é 300s; job_timeout deve ser > isso."""
    from src.plan.cpo.worker import WorkerSettings

    assert WorkerSettings.job_timeout >= 300, (
        f"job_timeout {WorkerSettings.job_timeout}s e menor que CPO "
        "time_limit_sec max (300s)"
    )


def test_cpo_schedule_job_signature():
    """`cpo_schedule_job(ctx, request_dict, tenant_id_str, user_id_str)`."""
    from src.plan.cpo.worker import cpo_schedule_job

    assert inspect.iscoroutinefunction(cpo_schedule_job)
    sig = inspect.signature(cpo_schedule_job)
    params = list(sig.parameters)
    assert params == ["ctx", "request_dict", "tenant_id_str", "user_id_str"], (
        f"assinatura inesperada: {params}"
    )


def test_cpo_schedule_job_calls_run_cpo_schedule():
    """Q.62.D.2 — verifica que o worker delega para run_cpo_schedule.
    Test estatico: lê o source e confirma o import + invocação.

    Foi `NotImplementedError` em D.1; D.2 wireou e este test passou a
    confirmar o wiring."""
    from pathlib import Path

    text = Path("src/plan/cpo/worker.py").read_text(encoding="utf-8")
    assert "from src.plan.cpo.scheduler_run import run_cpo_schedule" in text
    assert "await run_cpo_schedule(session, tenant_id, request)" in text
    assert "NotImplementedError" not in text, (
        "D.2 wireou o worker — NotImplementedError nao devia mais existir"
    )


def test_systemd_unit_exists():
    """`deploy/systemd/nelinho-arq.service` deve existir como template prod."""
    from pathlib import Path

    unit = Path("deploy/systemd/nelinho-arq.service")
    assert unit.exists(), "systemd unit em falta"
    text = unit.read_text(encoding="utf-8")
    assert "ExecStart=" in text
    assert "src.plan.cpo.worker.WorkerSettings" in text
