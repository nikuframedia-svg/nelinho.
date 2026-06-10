"""
Characterization tests for `src/factory_data_product/api/endpoints.py` — Q.66.D.1d.

These are **Feathers-style snapshot tests** taken BEFORE Q.66.D.4b decomposes
the 1311-line router. Each test pins one endpoint's status code + the *shape*
(top-level keys) of its response, so an accidental contract drift during the
refactor will fail loudly.

We avoid asserting on exact strings or numeric internals — those belong to
service-level tests (`semantic_queries_inmemory`, `IngestEngine`, etc.).
Here we only verify wiring: route registration, response_model, parameter
binding, dependency overrides, and HTTPException branches.

The router uses an in-memory `IngestEngine` global; each test injects a fresh
engine via `dependency_overrides[get_engine]` so the tests are order-independent.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.factory_data_product.api.endpoints import (
    router as factory_router,
    get_engine,
    get_semantic,
)
from src.factory_data_product.models.meta import (
    IngestionRun,
    IngestionStatus,
    QualityGateStatus,
    SourceType,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _StubEngine:
    """Minimal IngestEngine shape — only the attributes/methods endpoints touch."""

    def __init__(self) -> None:
        self._ingestion_runs: Dict[UUID, IngestionRun] = {}
        self._quality_checks: list = []
        self._curated_data: Dict[str, dict] = {}
        self._active_run: Optional[Dict[str, Any]] = None
        self._schema_history: list = []

    # public API used by the router ----------------------------------------
    def get_active_run(self):
        return self._active_run

    def list_ingestions(self):
        return [
            {
                "id": str(run.id),
                "file_name": run.file_name,
                "status": run.status.value,
                "quality_gate_status": run.quality_gate_status.value,
                "created_at_utc": run.created_at_utc.isoformat(),
                "total_rows_raw": 0,
            }
            for run in self._ingestion_runs.values()
        ]

    def get_schema_history(self):
        return self._schema_history

    def activate(self, ingestion_id: UUID, user: str) -> bool:
        # Match real engine: raise ValueError on unknown id.
        if ingestion_id not in self._ingestion_runs:
            raise ValueError(f"Ingestion {ingestion_id} not found")
        self._active_run = {
            "active_ingestion_id": ingestion_id,
            "activated_at_utc": datetime.now(timezone.utc),
            "activated_by": user,
        }
        return True

    def rollback(self, ingestion_id: UUID, user: str, reason: str) -> bool:
        if ingestion_id not in self._ingestion_runs:
            raise ValueError(f"Ingestion {ingestion_id} not found")
        return True


class _StubSemantic:
    """In-memory semantic queries stub — every method returns the canonical
    SemanticQueryResponse-shaped dict."""

    _BASE = {
        "data": {"items": []},
        "data_confidence": 50.0,
        "trust_status": "WARNING",
        "semantic_label": "stub",
        "metadata": {"source": "stub"},
    }

    def get_wip(self): return dict(self._BASE)
    def get_backlog(self, top_n: int = 20): return dict(self._BASE)
    def get_bottlenecks(self, top_n: int = 10): return dict(self._BASE)
    def get_quality(self, top_errors: int = 10, group_by: str = "error"): return dict(self._BASE)
    def get_mold_conflicts(self): return dict(self._BASE)
    def get_skills_risk(self, min_capable: int = 3): return dict(self._BASE)
    def get_lead_time(self, days_back: int = 90): return dict(self._BASE)


def _build_run(status: IngestionStatus = IngestionStatus.SUCCEEDED) -> IngestionRun:
    """Build a minimally-valid IngestionRun for the in-memory store."""
    return IngestionRun(
        id=uuid4(),
        created_at_utc=datetime.now(timezone.utc),
        created_by="test",
        source_type=SourceType.UPLOAD,
        file_name="test.xlsx",
        file_size_bytes=1024,
        file_sha256="a" * 64,
        status=status,
        quality_gate_status=QualityGateStatus.PASSED,
        started_at_utc=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_engine() -> _StubEngine:
    return _StubEngine()


@pytest.fixture
def stub_semantic() -> _StubSemantic:
    return _StubSemantic()


@pytest.fixture
def fake_db() -> "FakeSession":
    from tests.conftest import FakeSession

    return FakeSession()


@pytest.fixture
def client(
    stub_engine: _StubEngine, stub_semantic: _StubSemantic, fake_db,
) -> TestClient:
    # Q.168.D — /v1/factory ganhou o gate de tenant (require_tenant_header no
    # router-pai) + a quarentena passou a ler a BD real (get_session) com
    # utilizador autenticado (get_current_user_or_dev_header).
    from uuid import UUID as _UUID

    from src.shared.auth.headers import (
        get_current_user_or_dev_header,
        require_tenant_header,
    )
    from src.shared.auth.jwt_handler import UserContext
    from src.shared.database import get_session
    from tests.conftest import TEST_TENANT_ID

    app = FastAPI()
    app.include_router(factory_router)
    app.dependency_overrides[get_engine] = lambda: stub_engine
    app.dependency_overrides[get_semantic] = lambda: stub_semantic
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT_ID

    async def _db():
        yield fake_db

    app.dependency_overrides[get_session] = _db
    app.dependency_overrides[get_current_user_or_dev_header] = lambda: UserContext(
        user_id=_UUID("22222222-2222-2222-2222-222222222222"),
        tenant_id=TEST_TENANT_ID,
        role="ADMIN",
    )
    return TestClient(app)


# ---------------------------------------------------------------------------
# META — /meta/active-run
# ---------------------------------------------------------------------------


def test_meta_active_run_empty(client: TestClient):
    """No active run → has_active=False, null IDs."""
    resp = client.get("/v1/factory/meta/active-run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_active"] is False
    assert body["active_ingestion_id"] is None


def test_meta_active_run_with_run(client: TestClient, stub_engine: _StubEngine):
    run = _build_run()
    stub_engine._ingestion_runs[run.id] = run
    stub_engine._active_run = {
        "active_ingestion_id": run.id,
        "activated_at_utc": datetime.now(timezone.utc),
        "activated_by": "tester",
    }
    resp = client.get("/v1/factory/meta/active-run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_active"] is True
    assert body["active_ingestion_id"] == str(run.id)
    assert body["activated_by"] == "tester"


# ---------------------------------------------------------------------------
# META — /meta/quality-report/{id}
# ---------------------------------------------------------------------------


def test_quality_report_invalid_uuid_returns_400(client: TestClient):
    resp = client.get("/v1/factory/meta/quality-report/not-a-uuid")
    assert resp.status_code == 400


def test_quality_report_unknown_id_returns_404(client: TestClient):
    resp = client.get(f"/v1/factory/meta/quality-report/{uuid4()}")
    assert resp.status_code == 404


def test_quality_report_happy_path(client: TestClient, stub_engine: _StubEngine):
    run = _build_run()
    stub_engine._ingestion_runs[run.id] = run
    stub_engine._quality_checks = [
        {"ingestion_id": run.id, "passed": True, "severity": "blocking"},
        {"ingestion_id": run.id, "passed": False, "severity": "warning"},
    ]
    resp = client.get(f"/v1/factory/meta/quality-report/{run.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ingestion_id"] == str(run.id)
    assert set(body) >= {
        "quality_gate_status", "checks", "total_checks",
        "passed_checks", "failed_blocking", "failed_warning",
    }
    assert body["total_checks"] == 2
    assert body["passed_checks"] == 1
    assert body["failed_warning"] == 1


# ---------------------------------------------------------------------------
# META — /meta/schema-drift, /meta/schema-history
# ---------------------------------------------------------------------------


def test_schema_drift_no_history(client: TestClient):
    resp = client.get("/v1/factory/meta/schema-drift")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_drift"] is False
    assert body["has_blocking"] is False
    assert set(body) >= {"stats", "items", "current_timestamp", "summary"}


def test_schema_drift_with_two_snapshots(client: TestClient, stub_engine: _StubEngine):
    stub_engine._schema_history = [
        {
            "ingestion_id": "base",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sheets": {"OrdensFabrico": ["of_id", "produto_id"]},
        },
        {
            "ingestion_id": "curr",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sheets": {"OrdensFabrico": ["of_id", "produto_id", "novo_col"]},
        },
    ]
    resp = client.get("/v1/factory/meta/schema-drift")
    assert resp.status_code == 200
    body = resp.json()
    # New column "novo_col" should be detected.
    assert body["has_drift"] is True
    assert body["stats"]["columns_added"] >= 1


def test_schema_history_empty(client: TestClient):
    resp = client.get("/v1/factory/meta/schema-history")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"snapshots": [], "total": 0}


# ---------------------------------------------------------------------------
# META — /meta/ingestions (listing + filter + limit)
# ---------------------------------------------------------------------------


def test_list_ingestions_empty(client: TestClient):
    resp = client.get("/v1/factory/meta/ingestions")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"ingestions": [], "total": 0}


def test_list_ingestions_with_filter(client: TestClient, stub_engine: _StubEngine):
    run1 = _build_run(status=IngestionStatus.SUCCEEDED)
    run2 = _build_run(status=IngestionStatus.FAILED)
    stub_engine._ingestion_runs[run1.id] = run1
    stub_engine._ingestion_runs[run2.id] = run2

    resp = client.get("/v1/factory/meta/ingestions?status=succeeded")
    assert resp.status_code == 200
    body = resp.json()
    # Total reflects post-filter list length (matches router behaviour).
    assert body["total"] == 1
    assert body["ingestions"][0]["status"] == "succeeded"


def test_list_ingestions_limit_validation(client: TestClient):
    # Out-of-range limit triggers FastAPI 422.
    resp = client.get("/v1/factory/meta/ingestions?limit=9999")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# SEMANTIC — view discovery + blocked metrics
# ---------------------------------------------------------------------------


def test_list_semantic_views(client: TestClient):
    resp = client.get("/v1/factory/semantic")
    assert resp.status_code == 200
    body = resp.json()
    assert "views" in body and "total" in body
    assert body["total"] >= 1
    first = body["views"][0]
    assert set(first) >= {"view_id", "name", "description", "trust_score"}


def test_blocked_metrics_endpoint(client: TestClient):
    resp = client.get("/v1/factory/semantic/blocked-metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {
        "blocked_metrics", "allowed_metrics",
        "total_blocked", "total_allowed",
    }


# ---------------------------------------------------------------------------
# SEMANTIC — /semantic/{view_id}
# ---------------------------------------------------------------------------


def test_semantic_view_disallowed_returns_400(client: TestClient):
    resp = client.get("/v1/factory/semantic/v_not_a_real_view")
    assert resp.status_code == 400


def test_semantic_view_no_active_run_returns_empty(client: TestClient):
    resp = client.get("/v1/factory/semantic/v_lead_time_historico")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["total"] == 0
    # Disclaimer informing user no ingestion data available is appended.
    assert any("ingestion" in d.lower() for d in body["disclaimers"])


def test_semantic_view_invalid_sort_field_returns_400(
    client: TestClient, stub_engine: _StubEngine
):
    run = _build_run()
    stub_engine._ingestion_runs[run.id] = run
    stub_engine._active_run = {
        "active_ingestion_id": run.id,
        "activated_at_utc": datetime.now(timezone.utc),
        "activated_by": "x",
    }
    resp = client.get(
        "/v1/factory/semantic/v_lead_time_historico?sort_by=not_a_sortable_field"
    )
    assert resp.status_code == 400


def test_semantic_view_pagination_validation(client: TestClient):
    # page=0 is below ge=1 → 422.
    resp = client.get("/v1/factory/semantic/v_lead_time_historico?page=0")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# INGEST — /ingest (multipart), /ingest-by-path
# ---------------------------------------------------------------------------


def test_ingest_missing_file_returns_422(client: TestClient):
    resp = client.post("/v1/factory/ingest")
    assert resp.status_code == 422


def test_ingest_oversize_returns_413(
    client: TestClient, stub_engine: _StubEngine, monkeypatch
):
    # Patch the MAX_UPLOAD_BYTES path: just submit 101 MB worth of bytes. We
    # avoid actually creating the file in memory by overriding the constant
    # path implicitly — the check is `len(content) > MAX_UPLOAD_BYTES`.
    big = io.BytesIO(b"\x00" * (100 * 1024 * 1024 + 1))
    resp = client.post(
        "/v1/factory/ingest",
        files={"file": ("big.xlsx", big, "application/octet-stream")},
    )
    assert resp.status_code == 413


def test_ingest_by_path_requires_absolute(client: TestClient):
    resp = client.post(
        "/v1/factory/ingest-by-path",
        json={"path": "relative/file.xlsx"},
    )
    assert resp.status_code == 400


def test_ingest_by_path_nonexistent_returns_400(client: TestClient):
    resp = client.post(
        "/v1/factory/ingest-by-path",
        json={"path": "/tmp/does/not/exist/file.xlsx"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# ACTIVATE / ROLLBACK
# ---------------------------------------------------------------------------


def test_activate_unknown_id_returns_400(client: TestClient):
    resp = client.post(
        f"/v1/factory/activate/{uuid4()}",
        json={"user": "tester"},
    )
    assert resp.status_code == 400


def test_activate_happy_path(client: TestClient, stub_engine: _StubEngine):
    run = _build_run()
    stub_engine._ingestion_runs[run.id] = run
    resp = client.post(
        f"/v1/factory/activate/{run.id}",
        json={"user": "tester"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["activated_ingestion_id"] == str(run.id)
    assert body["activated_by"] == "tester"
    # drift_alert_id is None because no X-Tenant-Id header was supplied.
    assert body["drift_alert_id"] is None


def test_rollback_short_reason_returns_422(client: TestClient):
    resp = client.post(
        "/v1/factory/rollback",
        json={"to_ingestion_id": str(uuid4()), "reason": "short"},
    )
    assert resp.status_code == 422


def test_rollback_happy_path(client: TestClient, stub_engine: _StubEngine):
    run = _build_run()
    stub_engine._ingestion_runs[run.id] = run
    resp = client.post(
        "/v1/factory/rollback",
        json={
            "to_ingestion_id": str(run.id),
            "reason": "Rollback to known-good ingestion",
            "user": "tester",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["rolled_back_to"] == str(run.id)


# ---------------------------------------------------------------------------
# WATCHER status
# ---------------------------------------------------------------------------


def test_watcher_status_shape(client: TestClient):
    resp = client.get("/v1/factory/watcher/status")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {
        "enabled", "watch_path", "last_hash",
        "last_ingestion_id", "last_error",
    }


# ---------------------------------------------------------------------------
# SEMANTIC QUERIES (real data wrappers) — wire each method, assert canonical shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/v1/factory/semantic/queries/wip",
        "/v1/factory/semantic/queries/backlog",
        "/v1/factory/semantic/queries/bottlenecks",
        "/v1/factory/semantic/queries/quality",
        "/v1/factory/semantic/queries/mold-conflicts",
        "/v1/factory/semantic/queries/skills-risk",
        "/v1/factory/semantic/queries/lead-time",
    ],
)
def test_semantic_query_returns_canonical_shape(client: TestClient, path: str):
    resp = client.get(path)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # SemanticQueryResponse contract — these keys are load-bearing for the
    # frontend copilot view; any rename here is a breaking change.
    assert set(body) >= {
        "data", "data_confidence", "trust_status",
        "semantic_label", "metadata",
    }


def test_semantic_query_backlog_validates_top_n(client: TestClient):
    resp = client.get("/v1/factory/semantic/queries/backlog?top_n=9999")
    assert resp.status_code == 422


def test_semantic_query_quality_invalid_group_by_returns_422(client: TestClient):
    resp = client.get("/v1/factory/semantic/queries/quality?group_by=invalid")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TRUST HEATMAP
# ---------------------------------------------------------------------------


def test_trust_heatmap_shape(client: TestClient):
    resp = client.get("/v1/factory/quality/trust-heatmap")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Locked contract (TrustHeatmapResponse) — extras allowed but these keys
    # MUST be present.
    assert set(body) >= {
        "overall_trust", "overall_status", "domains",
        "segments", "summary", "generated_at",
    }


# ---------------------------------------------------------------------------
# QUARANTINE
# ---------------------------------------------------------------------------


def test_quarantine_list_default_empty_is_honest(client: TestClient):
    """Q.168.D — o mock (2 rows hardcoded) foi substituído pela fonte REAL
    (tabelas curadas com QuarantineMixin). Camada curada vazia → lista vazia
    HONESTA, nunca dados de exemplo (invariantes #1/#8)."""
    resp = client.get("/v1/factory/quarantine")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {
        "rows", "total", "page", "page_size", "by_code", "by_table",
    }
    assert body["total"] == 0
    assert body["rows"] == []
    assert body["capped_tables"] == []


def test_quarantine_list_unknown_table_is_400(client: TestClient):
    resp = client.get("/v1/factory/quarantine?table=Funcionarios")
    assert resp.status_code == 400
    assert "tabela desconhecida" in resp.json()["detail"]


def test_quarantine_list_filter_by_code_empty(client: TestClient):
    resp = client.get("/v1/factory/quarantine?code=INVALID_TIMING")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_quarantine_resolve_requires_action(client: TestClient):
    # `action` is a required Query parameter.
    resp = client.post(
        "/v1/factory/quarantine/q-001/resolve",
        params={"reason": "Fixed manually by ops team"},
    )
    assert resp.status_code == 422


def test_quarantine_resolve_short_reason_returns_422(client: TestClient):
    resp = client.post(
        "/v1/factory/quarantine/q-001/resolve",
        params={"action": "repair", "reason": "short"},
    )
    assert resp.status_code == 422


def test_quarantine_resolve_unknown_row_is_404(client: TestClient):
    """Q.168.D — o resolve era um 200 fake sem persistência; agora procura a
    row a sério e 404 quando não existe (id não-UUID incluído)."""
    resp = client.post(
        "/v1/factory/quarantine/q-001/resolve",
        params={"action": "repair", "reason": "Fixed manually in source system"},
    )
    assert resp.status_code == 404
