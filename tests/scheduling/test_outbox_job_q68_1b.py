"""Q.68.1.B — testes do job periódico de drain do outbox dispatcher.

Antes deste sprint o `OutboxDispatcher` só corria no shutdown
(`src/app/startup.py`), deixando eventos orphaned após crash. O job
`outbox_drain` registado em `start_scheduler()` corre cada 5s.

Cobertura:
  * job registado em scheduler após start_scheduler;
  * trigger é IntervalTrigger com 5 segundos;
  * coalesce=True + max_instances=1 (anti-paralelismo);
  * no-op limpo quando `get_producer()` devolve None;
  * smoke: quando o producer existe, o job invoca `dispatcher.run()`.
"""

from __future__ import annotations

import pytest

from src.shared import scheduler


@pytest.mark.asyncio
async def test_outbox_drain_job_registered_after_start():
    """`start_scheduler` regista o job `outbox_drain`."""
    scheduler._scheduler = None  # arranque limpo
    sched = scheduler.start_scheduler(tenants=None)
    if sched is None:
        pytest.skip("APScheduler nao instalado")
    try:
        job_ids = {job.id for job in sched.get_jobs()}
        assert "outbox_drain" in job_ids
    finally:
        sched.shutdown(wait=False)
        scheduler._scheduler = None


@pytest.mark.asyncio
async def test_outbox_drain_interval_is_5_seconds():
    """Trigger deve ser IntervalTrigger com 5s — drain frequente."""
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler._scheduler = None
    sched = scheduler.start_scheduler(tenants=None)
    if sched is None:
        pytest.skip("APScheduler nao instalado")
    try:
        job = sched.get_job("outbox_drain")
        assert job is not None
        assert isinstance(job.trigger, IntervalTrigger)
        # IntervalTrigger.interval é um timedelta
        assert job.trigger.interval.total_seconds() == 5
    finally:
        sched.shutdown(wait=False)
        scheduler._scheduler = None


@pytest.mark.asyncio
async def test_outbox_drain_has_coalesce_and_single_instance():
    """coalesce=True + max_instances=1 previnem corridas paralelas."""
    scheduler._scheduler = None
    sched = scheduler.start_scheduler(tenants=None)
    if sched is None:
        pytest.skip("APScheduler nao instalado")
    try:
        job = sched.get_job("outbox_drain")
        assert job is not None
        assert job.coalesce is True
        assert job.max_instances == 1
    finally:
        sched.shutdown(wait=False)
        scheduler._scheduler = None


@pytest.mark.asyncio
async def test_outbox_drain_noop_when_producer_none(monkeypatch):
    """Sem Kafka producer, o job devolve cedo sem instanciar dispatcher."""
    from src.scheduling.jobs import outbox as outbox_job

    instantiated: list[bool] = []

    class FakeDispatcher:
        def __init__(self, **kwargs):
            instantiated.append(True)

        async def run(self):
            instantiated.append(True)

    async def fake_get_producer():
        return None

    monkeypatch.setattr(
        "src.shared.kafka_client.get_producer", fake_get_producer
    )
    monkeypatch.setattr(outbox_job, "_outbox_drain_job", outbox_job._outbox_drain_job)
    # Patch OutboxDispatcher in its module so the import inside the job picks up the fake.
    monkeypatch.setattr(
        "src.shared.outbox_dispatcher.OutboxDispatcher", FakeDispatcher
    )

    result = await outbox_job._outbox_drain_job()
    assert result is None
    assert instantiated == []  # nunca instanciou nem chamou run


@pytest.mark.asyncio
async def test_outbox_drain_invokes_dispatcher(monkeypatch):
    """Quando Kafka responde, o job chama `dispatcher.run()` uma vez."""
    from src.scheduling.jobs import outbox as outbox_job

    called: list[str] = []

    class FakeDispatcher:
        def __init__(self, **kwargs):
            called.append("init")

        async def run(self):
            called.append("run")

    async def fake_get_producer():
        return object()  # truthy producer

    monkeypatch.setattr(
        "src.shared.kafka_client.get_producer", fake_get_producer
    )
    monkeypatch.setattr(
        "src.shared.outbox_dispatcher.OutboxDispatcher", FakeDispatcher
    )

    await outbox_job._outbox_drain_job()
    assert called == ["init", "run"]


@pytest.mark.asyncio
async def test_outbox_drain_swallows_dispatcher_errors(monkeypatch):
    """Erros no dispatcher.run() nunca rebentam o scheduler."""
    from src.scheduling.jobs import outbox as outbox_job

    class ExplodingDispatcher:
        def __init__(self, **kwargs):
            pass

        async def run(self):
            raise RuntimeError("kafka exploded")

    async def fake_get_producer():
        return object()

    monkeypatch.setattr(
        "src.shared.kafka_client.get_producer", fake_get_producer
    )
    monkeypatch.setattr(
        "src.shared.outbox_dispatcher.OutboxDispatcher", ExplodingDispatcher
    )

    # Não deve levantar — job é resiliente a falhas pontuais.
    result = await outbox_job._outbox_drain_job()
    assert result is None
