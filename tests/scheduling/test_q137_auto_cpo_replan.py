"""Q.137 — replan CPO automático (planos aparecem sozinhos).

O job enfileira `cpo_schedule_job` no Arq quando o WIP-barco mudou, com
rate-limit + deteção de mudança. DRAFT-only (Q.17). Best-effort. Aqui mockamos
config/watermark/enqueue/session — o end-to-end (worker→DRAFT persistido) é
provado ao vivo em _audit/q137.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from src.scheduling.jobs import auto_cpo_replan_job as job

TENANT = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """Estado in-memory limpo + session/tenant mockados por teste."""
    job._last_run.clear()

    @asynccontextmanager
    async def fake_ctx():
        yield object()  # session não usada (config/watermark mockados)

    monkeypatch.setattr("src.shared.database.get_session_context", fake_ctx)

    async def fake_resolve(_ids):
        return [TENANT]

    monkeypatch.setattr(job, "_resolve_tenants", fake_resolve)
    yield


def _patch(
    monkeypatch, *, enabled=True, gap=60, watermark=(777, "2026-05-31"),
    healthy_since=True,
):
    # Q.161.B — _read_config devolve agora (enabled, gap, plan_cap, time_limit).
    async def fake_config(_s, _t):
        return enabled, gap, job._DEFAULT_ROBOT_PLAN_CAP, job._DEFAULT_ROBOT_TIME_LIMIT_S

    async def fake_wm(_s):
        return watermark

    # Q.162.C — o robô só salta WIP-inalterado se o último plano vingou (commit
    # saudável). Mockamos a confirmação; default True = último plano saudável.
    async def fake_healthy(_s, _t, _ts):
        return healthy_since

    calls: list = []

    # Q.161.B — _enqueue_cpo recebe agora (tid, wm, plan_cap, time_limit).
    async def fake_enqueue(tid, _wm, *_args):
        calls.append(tid)
        return True

    monkeypatch.setattr(job, "_read_config", fake_config)
    monkeypatch.setattr(job, "_wip_watermark", fake_wm)
    monkeypatch.setattr(job, "_healthy_commit_since", fake_healthy)
    monkeypatch.setattr(job, "_enqueue_cpo", fake_enqueue)
    return calls


@pytest.mark.asyncio
async def test_first_run_enqueues(monkeypatch):
    """1ª corrida (sem watermark prévio) → enfileira (plano inicial + demo)."""
    calls = _patch(monkeypatch)
    await job._auto_cpo_replan_global_job([])
    assert calls == [TENANT]
    assert TENANT in job._last_run


@pytest.mark.asyncio
async def test_rate_limit_skips_within_gap(monkeypatch):
    """2ª corrida dentro do gap → não enfileira."""
    calls = _patch(monkeypatch, gap=60)
    # simula último run há 10 min (dentro do gap de 60)
    job._last_run[TENANT] = (
        datetime.now(timezone.utc) - timedelta(minutes=10),
        (700, "old"),
    )
    await job._auto_cpo_replan_global_job([])
    assert calls == []  # rate-limited


@pytest.mark.asyncio
async def test_unchanged_watermark_skips(monkeypatch):
    """Passado o gap, WIP inalterado E último plano SAUDÁVEL → não re-planeia."""
    wm = (777, "2026-05-31")
    calls = _patch(monkeypatch, gap=60, watermark=wm, healthy_since=True)
    job._last_run[TENANT] = (
        datetime.now(timezone.utc) - timedelta(minutes=90),  # fora do gap
        wm,  # watermark IGUAL
    )
    await job._auto_cpo_replan_global_job([])
    assert calls == []


@pytest.mark.asyncio
async def test_unchanged_watermark_but_last_failed_reenqueues(monkeypatch):
    """Q.162.C — WIP inalterado MAS o último job NÃO produziu commit saudável
    (estourou o timeout / degenerou) → re-enfileira. Antes ficava preso no
    commit anterior (o watermark avançava no enqueue, não na conclusão)."""
    wm = (777, "2026-05-31")
    calls = _patch(monkeypatch, gap=60, watermark=wm, healthy_since=False)
    job._last_run[TENANT] = (
        datetime.now(timezone.utc) - timedelta(minutes=90),  # fora do gap
        wm,  # watermark IGUAL
    )
    await job._auto_cpo_replan_global_job([])
    assert calls == [TENANT]  # re-tentou porque o último plano não vingou


@pytest.mark.asyncio
async def test_changed_watermark_after_gap_enqueues(monkeypatch):
    """Passado o gap E WIP mudou → enfileira."""
    calls = _patch(monkeypatch, gap=60, watermark=(778, "2026-06-01"))
    job._last_run[TENANT] = (
        datetime.now(timezone.utc) - timedelta(minutes=90),
        (777, "2026-05-31"),  # diferente
    )
    await job._auto_cpo_replan_global_job([])
    assert calls == [TENANT]


@pytest.mark.asyncio
async def test_no_boats_skips(monkeypatch):
    """Watermark 0 barcos → nada a planear."""
    calls = _patch(monkeypatch, watermark=(0, ""))
    await job._auto_cpo_replan_global_job([])
    assert calls == []


@pytest.mark.asyncio
async def test_config_disabled_skips(monkeypatch):
    calls = _patch(monkeypatch, enabled=False)
    await job._auto_cpo_replan_global_job([])
    assert calls == []


@pytest.mark.asyncio
async def test_enqueue_redis_down_is_best_effort(monkeypatch):
    """Redis em baixo → _enqueue_cpo devolve False; o job não crasha nem grava."""
    _patch(monkeypatch)  # config/watermark ok

    async def enqueue_fail(_tid, _wm, *_args):
        return False  # Redis/arq indisponível

    monkeypatch.setattr(job, "_enqueue_cpo", enqueue_fail)
    await job._auto_cpo_replan_global_job([])  # não levanta
    assert TENANT not in job._last_run  # não grava estado se não enfileirou


@pytest.mark.asyncio
async def test_enqueue_uses_deterministic_job_id(monkeypatch):
    """Q.142.A — mesmo watermark → MESMO `_job_id` (dedup multi-worker sob
    `--workers 2`); watermark diferente → `_job_id` diferente (novo plano)."""
    captured: list = []

    class FakeRedis:
        async def enqueue_job(self, *args, **kwargs):
            captured.append(kwargs.get("_job_id"))
            return object()  # arq devolve um Job; aqui basta truthy

        async def close(self):
            pass

    async def fake_create_pool(_settings):
        return FakeRedis()

    # `_enqueue_cpo` faz `from arq.connections import create_pool` em runtime,
    # logo patch no atributo do módulo intercepta a chamada real.
    monkeypatch.setattr("arq.connections.create_pool", fake_create_pool)

    wm = (777, "2026-05-31 10:00:00")
    ok1 = await job._enqueue_cpo(TENANT, wm)
    ok2 = await job._enqueue_cpo(TENANT, wm)                       # mesmo WIP
    ok3 = await job._enqueue_cpo(TENANT, (778, "2026-06-01 09:00"))  # WIP mudou

    assert ok1 and ok2 and ok3
    assert captured[0] is not None
    assert captured[0].startswith(f"auto_cpo:{TENANT}:")
    assert captured[0] == captured[1]   # watermark igual → MESMO job_id (Arq dedup)
    assert captured[2] != captured[0]   # watermark diferente → job_id diferente
