"""Sprint Q.53.F — diagnóstico da ligação ao ERP NELO.

Cobre :func:`collect_erp_connection` + o endpoint
``GET /v1/diagnostics/erp-connection``.

O endpoint responde "a ERP está ligada e os dados estão frescos?" — o
``/infrastructure`` pinga DB/Redis/Kafka/Ollama mas nunca a ERP. Aqui
verificamos: URL mascarado (sem credenciais), ligado/offline,
última sync por mirror de ``core.etl_run``, contagens e lag.

Best-effort: ERP morta ou ``core.etl_run`` em falta → 200 degradado,
nunca 500.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.diagnostics.service import (
    ERP_MIRRORS,
    collect_erp_connection,
    mask_db_url,
)


# ---------------------------------------------------------------------------
# mask_db_url — credentials never leak to the dashboard
# ---------------------------------------------------------------------------

class TestMaskDbUrl:
    def test_none_yields_placeholder(self):
        assert mask_db_url(None) == "(não configurado)"
        assert mask_db_url("") == "(não configurado)"

    def test_password_is_stripped(self):
        url = "mssql+aioodbc://nelo:s3cr3t@erp.lan:1433/NELO_ERP"
        masked = mask_db_url(url)
        assert "s3cr3t" not in masked
        assert "nelo" not in masked
        assert "erp.lan:1433" in masked
        assert masked.startswith("mssql+aioodbc://***@")

    def test_url_without_credentials_kept(self):
        url = "mssql+aioodbc://erp.lan:1433/NELO_ERP"
        assert mask_db_url(url) == url

    def test_garbage_url_does_not_leak(self):
        assert mask_db_url("no-scheme-here") == "***"


# ---------------------------------------------------------------------------
# collect_erp_connection — service layer
# ---------------------------------------------------------------------------

def _etl_run(source: str, *, status: str, finished_offset_min: int | None,
             rows_read: int = 100):
    """Build an EtlRun-like object for the FakeSession queue."""
    from src.core.models.etl_run import EtlRun

    run = EtlRun(
        tenant_id=uuid4(),
        source=source,
        status=status,
    )
    run.started_at = datetime.now(timezone.utc) - timedelta(minutes=120)
    if finished_offset_min is not None:
        run.finished_at = datetime.now(timezone.utc) - timedelta(
            minutes=finished_offset_min
        )
    else:
        run.finished_at = None
    run.rows_read = rows_read
    run.rows_inserted = 10
    run.rows_updated = 5
    run.rows_skipped = 0
    run.error = None
    return run


class TestCollectErpConnection:
    async def test_erp_disabled_reports_offline_not_error(
        self, fake_session, tenant_id, monkeypatch,
    ):
        """ERP desligada na config → connected=False, detalhe claro."""
        from src.shared import config as config_mod

        monkeypatch.setattr(config_mod.settings, "sqlserver_enabled", False)
        # 6 mirrors, nenhuma sync ainda.
        for _ in ERP_MIRRORS:
            fake_session.queue_scalar(None)

        result = await collect_erp_connection(fake_session, tenant_id)

        assert result["enabled"] is False
        assert result["connected"] is False
        assert "desligado" in result["detail"]
        # url_masked reflecte a config (haja ou não URL); nunca expõe
        # credenciais — ":pass@" nunca aparece.
        masked = result["url_masked"]
        if "@" in masked:
            creds = masked.split("@")[0].split("://")[-1]
            assert creds == "***", f"credenciais expostas em {masked!r}"

    async def test_shape_has_all_expected_keys(
        self, fake_session, tenant_id, monkeypatch,
    ):
        from src.shared import config as config_mod

        monkeypatch.setattr(config_mod.settings, "sqlserver_enabled", False)
        for _ in ERP_MIRRORS:
            fake_session.queue_scalar(None)

        result = await collect_erp_connection(fake_session, tenant_id)

        for key in (
            "enabled", "url_masked", "connected", "detail", "latency_ms",
            "mirrors", "last_sync_at", "lag_seconds", "lag_human",
            "total_rows_last_sync", "sampled_at",
        ):
            assert key in result, f"falta a chave {key}"
        # Um mirror por fonte conhecida.
        assert len(result["mirrors"]) == len(ERP_MIRRORS)
        sources = {m["source"] for m in result["mirrors"]}
        assert sources == set(ERP_MIRRORS)

    async def test_never_synced_mirrors_marked(
        self, fake_session, tenant_id, monkeypatch,
    ):
        from src.shared import config as config_mod

        monkeypatch.setattr(config_mod.settings, "sqlserver_enabled", False)
        for _ in ERP_MIRRORS:
            fake_session.queue_scalar(None)

        result = await collect_erp_connection(fake_session, tenant_id)

        for m in result["mirrors"]:
            assert m["status"] == "never_synced"
            assert m["last_run_at"] is None
            assert m["rows_read"] == 0
        assert result["last_sync_at"] is None
        assert result["lag_seconds"] is None

    async def test_last_sync_and_lag_computed_from_ok_runs(
        self, fake_session, tenant_id, monkeypatch,
    ):
        from src.shared import config as config_mod

        monkeypatch.setattr(config_mod.settings, "sqlserver_enabled", False)
        # master sync'd 90 min atrás (ok), molds 30 min atrás (ok),
        # restantes nunca.
        runs = {
            "master": _etl_run("master", status="ok", finished_offset_min=90,
                               rows_read=12000),
            "molds": _etl_run("molds", status="ok", finished_offset_min=30,
                              rows_read=510),
        }
        for source in ERP_MIRRORS:
            fake_session.queue_scalar(runs.get(source))

        result = await collect_erp_connection(fake_session, tenant_id)

        # Lag = desde a sync ok mais recente (molds, 30 min).
        assert result["last_sync_at"] is not None
        assert 25 * 60 <= result["lag_seconds"] <= 35 * 60
        assert result["lag_human"] is not None
        # Contagem de linhas soma todos os mirrors.
        assert result["total_rows_last_sync"] == 12000 + 510

    async def test_error_run_excluded_from_lag(
        self, fake_session, tenant_id, monkeypatch,
    ):
        """Uma sync com status=error não conta como 'última sync ok'."""
        from src.shared import config as config_mod

        monkeypatch.setattr(config_mod.settings, "sqlserver_enabled", False)
        runs = {
            "master": _etl_run("master", status="ok", finished_offset_min=200),
            "quality": _etl_run("quality", status="error",
                                finished_offset_min=10),
        }
        for source in ERP_MIRRORS:
            fake_session.queue_scalar(runs.get(source))

        result = await collect_erp_connection(fake_session, tenant_id)

        # A sync ok mais recente é master (200 min), não a quality errada.
        assert result["lag_seconds"] >= 195 * 60
        quality = next(m for m in result["mirrors"] if m["source"] == "quality")
        assert quality["status"] == "error"

    async def test_etl_run_read_failure_degrades_gracefully(
        self, tenant_id, monkeypatch,
    ):
        """Se o read de core.etl_run rebenta, a resposta degrada — não 500."""
        from src.shared import config as config_mod

        monkeypatch.setattr(config_mod.settings, "sqlserver_enabled", False)

        class _ExplodingSession:
            async def execute(self, stmt):
                raise RuntimeError("relation core.etl_run does not exist")

        result = await collect_erp_connection(_ExplodingSession(), tenant_id)

        assert result["mirrors"] == []
        assert result["sync_history_error"] == "RuntimeError"
        # Continua a ter forma — o resto da resposta é válido.
        assert result["connected"] is False
        assert "sampled_at" in result


# ---------------------------------------------------------------------------
# Endpoint integration
# ---------------------------------------------------------------------------

class TestErpConnectionEndpoint:
    def test_endpoint_returns_200_and_shape(self):
        """O endpoint responde 200 com a forma esperada, ligado ou não."""
        logging.disable(logging.CRITICAL)
        from src.main import app

        client = TestClient(app)
        r = client.get(
            "/v1/diagnostics/erp-connection",
            headers={"X-Tenant-Id": str(uuid4())},
        )
        assert r.status_code == 200
        body = r.json()
        for key in (
            "enabled", "url_masked", "connected", "mirrors",
            "lag_seconds", "total_rows_last_sync", "sampled_at",
        ):
            assert key in body, f"endpoint sem a chave {key}"
        assert isinstance(body["mirrors"], list)
        assert isinstance(body["connected"], bool)

    def test_endpoint_never_leaks_credentials(self):
        """url_masked nunca contém uma password — mesmo num 200 degradado."""
        logging.disable(logging.CRITICAL)
        from src.main import app

        client = TestClient(app)
        r = client.get(
            "/v1/diagnostics/erp-connection",
            headers={"X-Tenant-Id": str(uuid4())},
        )
        assert r.status_code == 200
        masked = r.json()["url_masked"]
        # Nem "://user:pass@" — só "://***@" ou sem credenciais.
        assert ":" not in masked.split("@")[0].split("://")[-1] if "@" in masked else True
