"""Q.20.A — ERP→Postgres sync orchestration tests.

The orchestrator is exercised without a SQL Server: ``run_nelo_sync``
short-circuits when ``settings.sqlserver_enabled`` is False, and the
mirror registry is a plain in-process dict.
"""

from __future__ import annotations

import pytest

from src.adapters.nelo.etl import sync as sync_mod
from src.adapters.nelo.etl.runner import EtlRunResult
from src.adapters.nelo.etl.sync import (
    register_mirror,
    registered_mirrors,
    run_nelo_sync,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Each test sees a pristine mirror registry."""
    saved = dict(sync_mod._MIRRORS)
    sync_mod._MIRRORS.clear()
    yield
    sync_mod._MIRRORS.clear()
    sync_mod._MIRRORS.update(saved)


def test_register_and_list_mirrors():
    async def _noop(**_kw):
        return EtlRunResult("x")

    register_mirror("alpha", _noop)
    register_mirror("beta", _noop)
    assert registered_mirrors() == ["alpha", "beta"]


async def test_run_nelo_sync_skipped_when_sqlserver_disabled(monkeypatch):
    """With ``sqlserver_enabled`` False the sync returns [] and never
    touches the adapter — the safe default in dev."""
    from src.shared.config import settings

    monkeypatch.setattr(settings, "sqlserver_enabled", False, raising=False)

    called = {"hit": False}

    async def _mirror(**_kw):
        called["hit"] = True
        return EtlRunResult("master")

    register_mirror("master", _mirror)

    results = await run_nelo_sync()
    assert results == []
    assert called["hit"] is False


async def test_run_nelo_sync_rejects_unknown_mirror(monkeypatch):
    from src.shared.config import settings

    monkeypatch.setattr(settings, "sqlserver_enabled", True, raising=False)
    with pytest.raises(ValueError, match="unknown mirror"):
        await run_nelo_sync(only=["does_not_exist"])


# ---------------------------------------------------------------------------
# Q.168 F4.E — corrida falhada persiste o etl_run de erro
# ---------------------------------------------------------------------------


class _CtxFakeSession:
    """FakeSession canónica embrulhada como async context manager.

    ``run_nelo_sync`` faz ``async with async_session_factory() as session``;
    a FakeSession do conftest não implementa ``__aenter__``/``__aexit__``,
    por isso o teste compõe-na aqui.
    """

    def __init__(self, inner) -> None:
        self._inner = inner

    async def __aenter__(self):
        return self._inner

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _wire_fake_erp(monkeypatch, session):
    """sqlserver on + health_check/close_engine inertes + sessão fake."""
    import types

    import src.adapters.nelo.services as services_mod
    import src.shared.database as database_mod
    from src.shared.config import settings

    monkeypatch.setattr(settings, "sqlserver_enabled", True, raising=False)

    async def _fake_health_check():
        return types.SimpleNamespace(open_orders_count=1, movements_last_30d=1)

    async def _fake_close_engine():
        return None

    monkeypatch.setattr(services_mod, "health_check", _fake_health_check)
    monkeypatch.setattr(services_mod, "close_engine", _fake_close_engine)
    monkeypatch.setattr(
        database_mod, "async_session_factory", lambda: _CtxFakeSession(session),
    )


async def test_failed_mirror_persists_error_etl_run_q168_f4e(monkeypatch):
    """Mirror que rebenta → rollback explícito + etl_run status='error' COMMITADO.

    Antes do Q.168 F4.E a exceção saía do ``async with`` sem commit: o
    rollback implícito descartava o etl_run de erro que o EtlRunner tinha
    flushed → a corrida falhada não deixava rasto na BD.
    """
    from tests.conftest import FakeSession

    from src.core.models.etl_run import EtlRun

    session = FakeSession()
    _wire_fake_erp(monkeypatch, session)

    async def _boom(**_kw):
        raise RuntimeError("ERP caiu a meio")

    register_mirror("boom", _boom)

    results = await run_nelo_sync(only=["boom"])

    assert len(results) == 1
    assert results[0].status == "error"
    assert "RuntimeError" in (results[0].error or "")
    # rollback explícito descartou as escritas parciais do mirror
    assert session.rollback_calls == 1
    # o registo de auditoria foi re-gravado e COMMITADO numa tx limpa
    error_runs = [o for o in session.added if isinstance(o, EtlRun)]
    assert len(error_runs) == 1
    assert error_runs[0].status == "error"
    assert error_runs[0].source == "boom"
    assert "ERP caiu a meio" in (error_runs[0].error or "")
    assert error_runs[0].finished_at is not None
    # Q.173.C — 1 commit do etl_run de erro + 1 commit do alerta ETL_SYNC_FAILED
    assert session.commit_calls == 2
    from src.copilot.alerts.models import CODE_ETL_SYNC_FAILED, CopilotAlert

    alerts = [o for o in session.added if isinstance(o, CopilotAlert)]
    assert len(alerts) == 1
    assert alerts[0].code == CODE_ETL_SYNC_FAILED
    assert alerts[0].context["source"] == "boom"


async def test_failing_mirror_does_not_abort_the_rest_q168_f4e(monkeypatch):
    """Um mirror mau nunca aborta o sync — o seguinte ainda corre e commita."""
    from tests.conftest import FakeSession

    session = FakeSession()
    _wire_fake_erp(monkeypatch, session)

    async def _boom(**_kw):
        raise RuntimeError("falha transiente")

    async def _ok(**_kw):
        result = EtlRunResult("bom")
        result.status = "ok"
        return result

    register_mirror("boom", _boom)
    register_mirror("bom", _ok)

    results = await run_nelo_sync(only=["boom", "bom"])

    assert [r.status for r in results] == ["error", "ok"]
    # 1 commit do etl_run de erro + 1 do alerta Q.173.C + 1 do mirror saudável
    assert session.commit_calls == 3
