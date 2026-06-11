"""Q.54.A — sync ERP incremental de 5/5 min.

Cobre:
* :func:`_since_for` — resolução do watermark por mirror.
* :func:`last_sync_watermarks` — lê o último ``finished_at`` de
  ``core.etl_run`` por mirror.
* :func:`_nelo_erp_incremental_sync_job` — no-op limpo sem o ERP.
* ``start_scheduler`` regista o job ``nelo_erp_incremental_sync`` com
  trigger de 5 min.
* o job só usa mirrors registados — nunca inventa ``purchase_orders``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pytest

from src.adapters.nelo.etl import sync as sync_mod
from src.adapters.nelo.etl.sync import _since_for, last_sync_watermarks
from src.shared import scheduler
from src.shared.config import settings

TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ─── _since_for ──────────────────────────────────────────────────────────


def test_since_for_none_returns_none():
    assert _since_for(None, "stock") is None


def test_since_for_single_date_applies_to_every_mirror():
    d = date(2026, 5, 10)
    assert _since_for(d, "stock") == d
    assert _since_for(d, "calendar") == d
    assert _since_for(d, "quality") == d


def test_since_for_dict_is_per_mirror():
    watermarks = {"stock": date(2026, 5, 1), "quality": date(2026, 5, 5)}
    assert _since_for(watermarks, "stock") == date(2026, 5, 1)
    assert _since_for(watermarks, "quality") == date(2026, 5, 5)
    # Um mirror sem entrada cai em None → look-back por defeito.
    assert _since_for(watermarks, "calendar") is None


# ─── last_sync_watermarks ────────────────────────────────────────────────


class _EtlRunRow:
    """Linha falsa de core.etl_run."""

    def __init__(self, source, status, finished_at):
        self.source = source
        self.status = status
        self.finished_at = finished_at


class _WatermarkSession:
    """Sessão que devolve pares (source, max_finished_at) para o
    GROUP BY de last_sync_watermarks."""

    def __init__(self, pairs):
        self._pairs = list(pairs)

    async def execute(self, _stmt):
        pairs = self._pairs

        class _R:
            def all(self_inner):
                return list(pairs)

        return _R()


@pytest.mark.asyncio
async def test_last_sync_watermarks_returns_date_per_mirror():
    now = datetime(2026, 5, 18, 14, 30, tzinfo=timezone.utc)
    session = _WatermarkSession([
        ("stock", now),
        ("quality", now - timedelta(days=2)),
    ])
    out = await last_sync_watermarks(session, TENANT, ["stock", "calendar", "quality"])
    # finished_at (datetime tz-aware) convertido para date — sem bug tz.
    assert out["stock"] == date(2026, 5, 18)
    assert out["quality"] == date(2026, 5, 16)
    # calendar nunca correu → não entra no dict (look-back por defeito).
    assert "calendar" not in out


@pytest.mark.asyncio
async def test_last_sync_watermarks_empty_mirrors_is_empty():
    session = _WatermarkSession([])
    assert await last_sync_watermarks(session, TENANT, []) == {}


@pytest.mark.asyncio
async def test_last_sync_watermarks_skips_null_finished_at():
    session = _WatermarkSession([("stock", None)])
    out = await last_sync_watermarks(session, TENANT, ["stock"])
    assert out == {}


# ─── incremental job ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_incremental_job_noop_when_sqlserver_disabled(monkeypatch):
    """Sem o flag ligado o job devolve sem tocar no ERP nem na BD."""
    monkeypatch.setattr(settings, "sqlserver_enabled", False, raising=False)
    assert await scheduler._nelo_erp_incremental_sync_job() is None


def test_incremental_mirrors_are_operational_only():
    """Q.54.A — só mirrors operacionais leves; nada de master/molds/
    skills/time_mining no incremental, nem inventados. Q.167.E adicionou
    `checklist` (defeitos RCA, fonte única) ao incremental."""
    assert scheduler._INCREMENTAL_MIRRORS == ["stock", "calendar", "quality", "checklist"]
    # Nunca inventar purchase_orders / suppliers (não existem).
    assert "purchase_orders" not in scheduler._INCREMENTAL_MIRRORS
    assert "suppliers" not in scheduler._INCREMENTAL_MIRRORS


def test_incremental_mirrors_all_registered():
    """Os mirrors do incremental registam-se no registo de mirrors.

    Q.173.R — asserção ESTÁTICA ao código-fonte: a versão anterior fazia
    ``importlib.reload`` dos módulos, o que ENVENENAVA outros testes sob
    ordem aleatória (monkeypatch por string-path patcha o módulo NOVO em
    sys.modules enquanto funções importadas antes apontam para o dict de
    globals ANTIGO — ex.: test_checklist.test_backfill_* falhava). O
    registo é efeito de import, por isso a fonte auditável é o código.
    """
    import importlib
    import inspect

    loader_src = inspect.getsource(sync_mod._load_mirror_modules)
    for mirror in scheduler._INCREMENTAL_MIRRORS:
        # 1) o loader de produção importa o módulo…
        assert f'"{mirror}"' in loader_src, (
            f"{mirror} não está em _load_mirror_modules"
        )
        # 2) …e o módulo regista-se no import (linha ativa, não comentada).
        mod = importlib.import_module(f"src.adapters.nelo.etl.{mirror}")
        active = [
            line for line in inspect.getsource(mod).splitlines()
            if line.strip().startswith("register_mirror(")
        ]
        assert active, f"{mirror} não chama register_mirror no import"


# ─── scheduler registration ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_scheduler_registers_incremental_sync_job():
    # async para garantir que há event loop a correr — o
    # AsyncIOScheduler.start() exige-o.
    scheduler._scheduler = None
    sched = scheduler.start_scheduler(tenants=None)
    if sched is None:
        pytest.skip("APScheduler não instalado")
    try:
        jobs = {job.id: job for job in sched.get_jobs()}
        assert "nelo_erp_incremental_sync" in jobs
        # O trigger é de intervalo de 5 minutos.
        trigger = jobs["nelo_erp_incremental_sync"].trigger
        assert "0:05:00" in str(trigger) or "300" in str(trigger)
        # Q.54.B — o job de reconciliação de estado também é registado.
        assert "order_status_reconcile" in jobs
    finally:
        sched.shutdown(wait=False)
        scheduler._scheduler = None
