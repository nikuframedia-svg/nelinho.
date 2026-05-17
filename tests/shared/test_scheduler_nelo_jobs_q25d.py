"""Q.25.D — testes dos jobs agendados de sync ERP->Postgres.

Cobre dois invariantes:
  * os jobs fazem no-op limpo quando `sqlserver_enabled=False` (nunca
    tocam no ERP nem na BD sem o flag ligado);
  * `start_scheduler` regista os dois jobs (`nelo_erp_sync` e
    `nelo_erp_time_mining`).
"""

import pytest

from src.shared import scheduler
from src.shared.config import settings


@pytest.mark.asyncio
async def test_sync_job_noop_when_sqlserver_disabled(monkeypatch):
    """Com o flag desligado, o job nocturno devolve sem tocar no ERP."""
    monkeypatch.setattr(settings, "sqlserver_enabled", False)
    # se tentasse correr, importava run_nelo_sync e ligava ao ERP —
    # aqui tem de devolver None silenciosamente.
    assert await scheduler._nelo_erp_sync_job() is None


@pytest.mark.asyncio
async def test_time_mining_job_noop_when_sqlserver_disabled(monkeypatch):
    """O mirror pesado tambem faz no-op limpo sem o flag."""
    monkeypatch.setattr(settings, "sqlserver_enabled", False)
    assert await scheduler._nelo_erp_time_mining_job() is None


@pytest.mark.asyncio
async def test_start_scheduler_registers_both_nelo_erp_jobs():
    """`start_scheduler` regista `nelo_erp_sync` + `nelo_erp_time_mining`."""
    scheduler._scheduler = None  # arranque limpo, isolado de outros testes
    sched = scheduler.start_scheduler(tenants=None)
    if sched is None:
        pytest.skip("APScheduler nao instalado")
    try:
        job_ids = {job.id for job in sched.get_jobs()}
        assert "nelo_erp_sync" in job_ids
        assert "nelo_erp_time_mining" in job_ids
    finally:
        sched.shutdown(wait=False)
        scheduler._scheduler = None
