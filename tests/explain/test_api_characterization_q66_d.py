"""Q.66.D.1e — Characterization tests para `src/explain/api.py`.

Estes testes pinam o shape actual de cada endpoint do router
`explain` ANTES da decomposição da Fase 7 (Q.66.D.4c) — Feathers
pattern. Não são "specs aspiracionais"; descrevem o que o código
faz hoje. Se um teste falhar após o refactor, isso significa que o
contrato externo mudou e o frontend precisa de saber.

Estratégia:

* Mount-amos só o `router` num `FastAPI()` mínimo — main.py traz
  optional deps pesadas (Ollama, Kafka). Override de `get_session`
  e `require_tenant_header` via `dependency_overrides`.
* Engines causais (DoWhy, tigramite, PCMCI+) e detectores
  diagnósticos (ERRO-TREE, Reichenbach, MillDiff) são lentos — são
  mockados via `unittest.mock.patch` no ponto de import dentro de
  cada endpoint.
* CommitsService idem — mockamos `get_session_context` para
  devolver uma sessão controlada e o `service.get_by_sha*` directo.

Cobertura (15+ tests):

  GET /v1/explain/metric/{id}           — known, blocked, unknown
  GET /v1/explain/catalog               — list shape
  GET /v1/explain/blocked               — split blocked/available
  POST /v1/explain/compute              — known + 404 missing
  GET /v1/explain/catalog/full          — full catalog + domain filter
  GET /v1/explain/catalog/{id}/full     — 404 + happy
  GET /v1/explain/catalog/search        — query results
  GET /v1/explain/catalog/blocked/full
  GET /v1/explain/catalog/available/full
  GET /v1/explain/catalog/markdown
  GET /v1/explain/commit/{sha}          — 404 + happy
  GET /v1/explain/attribution           — engine response
  GET /v1/explain/discover              — engine response
  POST /v1/explain/diagnostics/investigate — 400 + happy
  POST /v1/explain/diagnostics/common-cause
  POST /v1/explain/diagnostics/what-changed — 400 + happy
  + tenant gate sanity check

NÃO testámos:
  * Lookup live via SemanticQueries (path interno mascarado pelo
    fallback do catálogo — comportamento ok pinado indirectamente).
  * Stream de erros não-determinísticos (timing, RLS, RBAC) — fora
    de scope da characterization de shape.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.explain.api import router
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
_HEADERS = {"X-Tenant-Id": str(TENANT_ID)}


# ============================================================================
# Test fixtures
# ============================================================================

class _NoOpSession:
    """Sessão async vazia — qualquer execute/get devolve None.

    Os endpoints do explain só usam a sessão para o lookup live via
    SemanticQueries; ao devolver None aqui, o `_resolve_metric_value`
    falha e cai sempre no catálogo de fallback.
    """

    async def execute(self, *args, **kwargs):
        return SimpleNamespace(
            scalar_one_or_none=lambda: None,
            scalar=lambda: None,
            scalars=lambda: SimpleNamespace(all=lambda: [], first=lambda: None),
            all=lambda: [],
        )

    async def get(self, *args, **kwargs):
        return None


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)

    async def _override_session():
        yield _NoOpSession()

    async def _override_tenant():
        return TENANT_ID

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[require_tenant_header] = _override_tenant
    return TestClient(app)


# ============================================================================
# GET /v1/explain/metric/{metric_id}
# ============================================================================

def test_get_metric_known_available_returns_full_shape(client):
    """Known available metric returns ExplainedMetric with all fields."""
    resp = client.get("/v1/explain/metric/wip_theoretical", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["metric_id"] == "wip_theoretical"
    assert body["metric_name"] == "WIP Teórico"
    # value cai no fallback estático (1523) — SemanticQueries não corre
    # com a NoOp session.
    assert body["value"] == 1523
    assert body["unit"] == "orders"
    assert isinstance(body["factors"], list) and len(body["factors"]) >= 1
    assert isinstance(body["suggestions"], list) and len(body["suggestions"]) >= 1
    assert isinstance(body["citations"], list) and len(body["citations"]) >= 1
    assert "computed_at" in body
    assert 0.0 <= body["trust_index"] <= 1.0


def test_get_metric_blocked_returns_no_value(client):
    """Blocked metrics return value=None + ⛔ explanation + 0 trust."""
    resp = client.get("/v1/explain/metric/oee_global", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["metric_id"] == "oee_global"
    assert body["value"] is None
    assert "BLOQUEADA" in body["explanation"]
    assert body["trust_index"] == 0.0
    assert body["citations"] == []
    # Blocked metrics expose suggestions (data improvement actions).
    assert len(body["suggestions"]) >= 1


def test_get_metric_unknown_returns_generic_explanation(client):
    """Métricas desconhecidas devolvem 200 com explicação genérica + trust 0."""
    resp = client.get("/v1/explain/metric/this_does_not_exist", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["metric_id"] == "this_does_not_exist"
    assert body["value"] is None
    assert body["trust_index"] == 0.0
    assert body["factors"] == []
    assert body["suggestions"] == []


def test_get_metric_warning_status_prefixes_explanation(client):
    """WARNING metrics get ⚠️ CONFIANÇA LIMITADA prefix in explanation."""
    resp = client.get(
        "/v1/explain/metric/backlog_horas_theoretical", headers=_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "CONFIANÇA LIMITADA" in body["explanation"]


# ============================================================================
# GET /v1/explain/catalog
# ============================================================================

def test_get_catalog_returns_list_of_entries(client):
    resp = client.get("/v1/explain/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 6  # WIP, backlog, lead_time, bottleneck, skills, quality + blocked
    sample = body[0]
    assert set(sample.keys()) >= {
        "id", "name", "domain", "unit", "description",
    }


# ============================================================================
# GET /v1/explain/blocked
# ============================================================================

def test_get_blocked_returns_split_blocked_available(client):
    resp = client.get("/v1/explain/blocked")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {
        "blocked", "blocked_count", "available", "available_count", "summary",
    }
    assert body["blocked_count"] == len(body["blocked"])
    assert body["available_count"] == len(body["available"])
    # Há pelo menos um BLOCKED (oee_global) e pelo menos um available.
    assert body["blocked_count"] >= 1
    assert body["available_count"] >= 1
    assert "blocked_reasons" in body["summary"]


# ============================================================================
# POST /v1/explain/compute
# ============================================================================

def test_compute_known_metric_returns_value_and_source(client):
    resp = client.post(
        "/v1/explain/compute?metric_id=wip_theoretical",
        headers=_HEADERS,
        json=None,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["metric_id"] == "wip_theoretical"
    # SemanticQueries não corre (NoOp session) → fallback 75.0.
    assert body["value"] == 75.0
    assert body["source"] == "catalogue_fallback"
    assert "computed_at" in body
    assert body["period"] == {"start": None, "end": None}


def test_compute_unknown_metric_returns_404(client):
    resp = client.post(
        "/v1/explain/compute?metric_id=nope", headers=_HEADERS, json=None,
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ============================================================================
# GET /v1/explain/catalog/full
# ============================================================================

def test_catalog_full_returns_metrics_and_domains(client):
    resp = client.get("/v1/explain/catalog/full")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {
        "metrics", "total", "domains", "blocked_count", "available_count",
    }
    assert body["total"] == len(body["metrics"])
    assert isinstance(body["domains"], list)


def test_catalog_full_filters_by_domain(client):
    resp = client.get("/v1/explain/catalog/full?domain=factory")
    assert resp.status_code == 200
    body = resp.json()
    # Filtragem reduz contagem; domínio inválido devolveria 400.
    assert isinstance(body["metrics"], list)


def test_catalog_full_rejects_invalid_domain(client):
    resp = client.get("/v1/explain/catalog/full?domain=not_a_real_domain")
    assert resp.status_code == 400
    assert "Invalid domain" in resp.json()["detail"]


def test_catalog_full_can_exclude_blocked(client):
    resp = client.get("/v1/explain/catalog/full?include_blocked=false")
    assert resp.status_code == 200
    body = resp.json()
    assert body["blocked_count"] == 0


# ============================================================================
# GET /v1/explain/catalog/{metric_id}/full
# ============================================================================

def test_catalog_metric_full_404_for_unknown(client):
    resp = client.get("/v1/explain/catalog/no_such_metric/full")
    assert resp.status_code == 404


# ============================================================================
# GET /v1/explain/catalog/search
# ============================================================================

def test_catalog_search_returns_query_results(client):
    resp = client.get("/v1/explain/catalog/search?q=oee")
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "oee"
    assert isinstance(body["results"], list)
    assert body["total"] == len(body["results"])


def test_catalog_search_rejects_short_query(client):
    """min_length=2 — single-char query is a 422."""
    resp = client.get("/v1/explain/catalog/search?q=a")
    assert resp.status_code == 422


# ============================================================================
# GET /v1/explain/catalog/blocked/full + /available/full + /markdown
# ============================================================================

def test_catalog_blocked_full_is_shadowed_by_metric_full_route(client):
    """KNOWN-BUG (characterized — do not "fix" silently in the refactor):

    `/catalog/blocked/full` and `/catalog/available/full` are declared
    AFTER `/catalog/{metric_id}/full`, so FastAPI matches them with
    `metric_id="blocked"` / `metric_id="available"`. The handler then
    returns 404 because no metric with that id exists.

    The Fase 7 decomposition MUST either re-order the routes (move the
    parameterised one to the bottom) or rename the literal paths — and
    update this test deliberately.
    """
    resp = client.get("/v1/explain/catalog/blocked/full")
    assert resp.status_code == 404
    assert "Metric 'blocked' not found" in resp.json()["detail"]


def test_catalog_available_full_is_shadowed_by_metric_full_route(client):
    """KNOWN-BUG (twin of `blocked/full`) — same shadowing."""
    resp = client.get("/v1/explain/catalog/available/full")
    assert resp.status_code == 404
    assert "Metric 'available' not found" in resp.json()["detail"]


def test_catalog_markdown_returns_format_and_content(client):
    resp = client.get("/v1/explain/catalog/markdown")
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "markdown"
    assert isinstance(body["content"], str) and len(body["content"]) > 0
    assert "generated_at" in body


# ============================================================================
# GET /v1/explain/commit/{commit_sha}
# ============================================================================

def test_commit_404_when_unknown(client):
    """Forçamos o CommitsService a devolver None — endpoint devolve 404."""
    fake_commit_service = SimpleNamespace(
        get_by_sha=lambda _sha: _async_none(),
        get_by_sha_prefix=lambda _sha: _async_none(),
    )

    class _DummyCtx:
        async def __aenter__(self):
            return _NoOpSession()

        async def __aexit__(self, *args):
            return None

    with patch("src.plan.cpo.commits.CommitsService", return_value=fake_commit_service), \
         patch("src.shared.database.get_session_context", lambda: _DummyCtx()):
        resp = client.get(
            "/v1/explain/commit/abc123def456", headers=_HEADERS,
        )
    assert resp.status_code == 404
    assert "commit not found" in resp.json()["detail"]


def test_commit_happy_returns_explanation(client):
    """Commit existente devolve KPIs + alternatives + narrativa gerada."""
    fake_commit = SimpleNamespace(
        commit_sha256="a" * 64,
        kpis={
            "makespan_hours": 100.0,
            "total_tardiness_hours": 2.0,
            "num_late_orders": 1,
            "throughput_eur_day": 30000,
            "setups": 5,
        },
        alternatives=[{"id": "alt1"}],
        rejected_alternatives=[{"id": "rej1"}],
        user_preference_signal={"weight_makespan": 0.6},
        trust_index=0.78,
        scenarios_tested=3,
    )

    class _SvcOk:
        def __init__(self, *_args, **_kwargs):
            pass

        async def get_by_sha(self, _sha):
            return fake_commit

        async def get_by_sha_prefix(self, _sha):
            return fake_commit

    class _DummyCtx:
        async def __aenter__(self):
            return _NoOpSession()

        async def __aexit__(self, *args):
            return None

    with patch("src.plan.cpo.commits.CommitsService", _SvcOk), \
         patch("src.shared.database.get_session_context", lambda: _DummyCtx()):
        resp = client.get(
            f"/v1/explain/commit/{'a' * 64}", headers=_HEADERS,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["commit_sha256"] == "a" * 64
    assert body["short_sha"] == "a" * 12
    assert body["kpis"]["makespan_hours"] == 100.0
    assert body["alternatives"] == [{"id": "alt1"}]
    assert body["rejected_alternatives"] == [{"id": "rej1"}]
    assert body["trust_index"] == 0.78
    assert body["scenarios_tested"] == 3
    assert "makespan" in body["why_these_choices"].lower() or "100" in body["why_these_choices"]


# ============================================================================
# GET /v1/explain/attribution
# ============================================================================

def test_attribution_returns_response_shape(client):
    """Mock-amos `attribution_analysis` para evitar DoWhy import."""

    # NodeAttribution-like — endpoint faz `a.__dict__` para serializar,
    # então precisamos de um objecto cujo __dict__ tenha as 4 chaves.
    class _Node:
        def __init__(self):
            self.node = "energy_kwh"
            self.share = 0.5
            self.direction = "negative"
            self.absolute = 1.2

    fake_report = SimpleNamespace(
        target="throughput_eur_day",
        status="degraded",
        reason="simulated data",
        engine="dowhy-gcm",
        sample_size=200,
        baseline_mean=10.0,
        target_value=12.0,
        ranked=[_Node()],
    )

    with patch(
        "src.copilot.causal.attribution.attribution_analysis",
        return_value=fake_report,
    ):
        resp = client.get(
            "/v1/explain/attribution?target=throughput_eur_day"
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["target"] == "throughput_eur_day"
    assert body["status"] == "degraded"
    assert body["engine"] == "dowhy-gcm"
    assert body["sample_size"] == 200
    assert len(body["ranked"]) == 1
    assert body["ranked"][0]["node"] == "energy_kwh"
    assert body["ranked"][0]["share"] == 0.5


def test_attribution_validates_sample_size_bounds(client):
    """sample_size has ge=50, le=2000 — 10 should 422."""
    resp = client.get("/v1/explain/attribution?target=foo&sample_size=10")
    assert resp.status_code == 422


# ============================================================================
# GET /v1/explain/discover
# ============================================================================

def test_discover_returns_response_shape(client):
    """Mock-amos `discover_edges` (lazy import dentro do endpoint)."""
    fake_edge = SimpleNamespace(
        to_json=lambda: {
            "src": "wip", "dst": "throughput", "lag": 1,
            "strength": 0.42, "pvalue": 0.001,
            "is_new": True, "direction": "positive",
        }
    )
    fake_report = SimpleNamespace(
        status="degraded",
        reason="simulated",
        engine="tigramite-pcmci+",
        sample_size=300,
        tau_max=2,
        nodes_examined=8,
        candidate_edges=[fake_edge],
    )

    with patch(
        "src.copilot.causal.discovery.discover_edges",
        return_value=fake_report,
    ):
        resp = client.get("/v1/explain/discover?tau_max=2&alpha=0.05")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["engine"] == "tigramite-pcmci+"
    assert body["nodes_examined"] == 8
    assert len(body["candidate_edges"]) == 1
    edge = body["candidate_edges"][0]
    assert edge["src"] == "wip" and edge["dst"] == "throughput"
    assert edge["is_new"] is True


def test_discover_validates_tau_max_bound(client):
    """tau_max has ge=0, le=5 — 99 should 422."""
    resp = client.get("/v1/explain/discover?tau_max=99")
    assert resp.status_code == 422


# ============================================================================
# POST /v1/explain/diagnostics/investigate
# ============================================================================

def test_investigate_rejects_invalid_trigger(client):
    resp = client.post(
        "/v1/explain/diagnostics/investigate",
        headers=_HEADERS,
        json={"trigger": "not_a_real_trigger", "period_days": 7},
    )
    assert resp.status_code == 400
    assert "Invalid trigger" in resp.json()["detail"]


def test_investigate_happy_returns_root_cause_envelope(client):
    """Mock-amos ErroTreeDetector para devolver um Hypothesis controlado."""
    fake_h = SimpleNamespace(
        type="mold_degradation",
        entity="MOLDE_42",
        confidence=0.83,
        evidence=["erro_rate 0.12 > baseline 0.05"],
        credible_interval=lambda level=0.95: (0.75, 0.91),
    )
    fake_result = SimpleNamespace(
        root_cause=fake_h,
        chain=["mold MOLDE_42 → quality_drop"],
        steps_checked=[{"step": "mold_check", "outcome": "tripped"}],
        recommendation={"action": "inspect_mold"},
    )

    class _Detector:
        def __init__(self, *_a, **_kw):
            pass

        async def investigate(self, **_kwargs):
            return fake_result

    with patch("src.explain.diagnostics.erro_tree.ErroTreeDetector", _Detector):
        resp = client.post(
            "/v1/explain/diagnostics/investigate",
            headers=_HEADERS,
            json={"trigger": "quality_drop", "period_days": 7},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["chain"] == ["mold MOLDE_42 → quality_drop"]
    assert body["steps_checked"][0]["step"] == "mold_check"
    assert body["recommendation"] == {"action": "inspect_mold"}
    assert body["root_cause"]["type"] == "mold_degradation"
    assert body["root_cause"]["entity"] == "MOLDE_42"
    assert body["root_cause"]["confidence"] == 0.83
    assert body["root_cause"]["credible_interval_95"]["low"] == 0.75


def test_investigate_no_root_cause_returns_null(client):
    """Quando o detector não isola causa, root_cause é None mas chain ainda existe."""
    fake_result = SimpleNamespace(
        root_cause=None,
        chain=[],
        steps_checked=[],
        recommendation={"action": "noop"},
    )

    class _Detector:
        def __init__(self, *_a, **_kw):
            pass

        async def investigate(self, **_kwargs):
            return fake_result

    with patch("src.explain.diagnostics.erro_tree.ErroTreeDetector", _Detector):
        resp = client.post(
            "/v1/explain/diagnostics/investigate",
            headers=_HEADERS,
            json={"trigger": "throughput_drop"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["root_cause"] is None


# ============================================================================
# POST /v1/explain/diagnostics/common-cause
# ============================================================================

def test_common_cause_returns_verdict_shape(client):
    fake_h = SimpleNamespace(
        type="shared_mold",
        entity="MOLDE_99",
        confidence=0.7,
        evidence=["3 phases share MOLDE_99"],
        credible_interval=lambda level=0.95: (0.6, 0.8),
    )
    fake_result = SimpleNamespace(
        verdict="common_cause",
        common_causes=[fake_h],
        independent_causes=[],
        checks_run=[{"check": "shared_mold"}],
    )

    class _Detector:
        def __init__(self, *_a, **_kw):
            pass

        async def find_common_cause(self, **_kwargs):
            return fake_result

    with patch("src.explain.diagnostics.reichenbach.ReichenbachDetector", _Detector):
        resp = client.post(
            "/v1/explain/diagnostics/common-cause",
            headers=_HEADERS,
            json={
                "deviating_phases": ["P01", "P02", "P03"],
                "period_days": 7,
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verdict"] == "common_cause"
    assert len(body["common_causes"]) == 1
    assert body["common_causes"][0]["type"] == "shared_mold"
    assert body["common_causes"][0]["credible_interval_95"]["low"] == 0.6
    assert body["independent_causes"] == []


def test_common_cause_rejects_single_phase(client):
    """min_length=2 — passar 1 fase é 422."""
    resp = client.post(
        "/v1/explain/diagnostics/common-cause",
        headers=_HEADERS,
        json={"deviating_phases": ["P01"], "period_days": 7},
    )
    assert resp.status_code == 422


# ============================================================================
# POST /v1/explain/diagnostics/what-changed
# ============================================================================

def test_what_changed_rejects_bad_period_before_good(client):
    """bad_period_end <= good_period_start → 400."""
    resp = client.post(
        "/v1/explain/diagnostics/what-changed",
        headers=_HEADERS,
        json={
            "good_period_start": "2024-06-01",
            "good_period_end": "2024-06-15",
            "bad_period_start": "2024-05-01",
            "bad_period_end": "2024-05-15",
        },
    )
    assert resp.status_code == 400
    assert "bad_period" in resp.json()["detail"]


def test_what_changed_happy_returns_report_dict(client):
    fake_report = SimpleNamespace(
        to_dict=lambda: {
            "metric_comparison": {"verdict": "shift", "cohens_d": 0.9},
            "changes_found": [
                {
                    "category": "molds",
                    "change": "MOLDE_42 saw +30% usage",
                    "correlation": 0.82,
                    "likely_cause": True,
                    "evidence": ["..."],
                },
            ],
            "unchanged": [],
            "verdict": "likely cause: MOLDE_42 reuse spike",
        }
    )

    class _Detector:
        def __init__(self, *_a, **_kw):
            pass

        async def what_changed(self, **_kwargs):
            return fake_report

    with patch("src.explain.diagnostics.mill_diff.MillDiffDetector", _Detector):
        resp = client.post(
            "/v1/explain/diagnostics/what-changed",
            headers=_HEADERS,
            json={
                "good_period_start": "2024-05-01",
                "good_period_end": "2024-05-15",
                "bad_period_start": "2024-06-01",
                "bad_period_end": "2024-06-15",
                "metric": "error_rate",
                "phase_id": "P01",
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metric_comparison"]["cohens_d"] == 0.9
    assert len(body["changes_found"]) == 1
    assert body["changes_found"][0]["likely_cause"] is True
    assert "MOLDE_42" in body["verdict"]


# ============================================================================
# Tenant gate sanity
# ============================================================================

def test_metric_endpoint_requires_tenant_header_when_no_override():
    """Sem o override de tenant, falta o header → 401."""
    app = FastAPI()
    app.include_router(router)

    async def _override_session():
        yield _NoOpSession()

    app.dependency_overrides[get_session] = _override_session
    # Sem `dependency_overrides[require_tenant_header]` — força o gate
    # real a correr.
    client = TestClient(app)
    resp = client.get("/v1/explain/metric/wip_theoretical")
    assert resp.status_code == 401


def test_router_exposes_all_documented_endpoints():
    """Sanity-check: o router carrega com as paths esperadas."""
    paths = {r.path for r in router.routes}
    expected = {
        "/v1/explain/metric/{metric_id}",
        "/v1/explain/catalog",
        "/v1/explain/blocked",
        "/v1/explain/compute",
        "/v1/explain/catalog/full",
        "/v1/explain/catalog/{metric_id}/full",
        "/v1/explain/catalog/search",
        "/v1/explain/catalog/blocked/full",
        "/v1/explain/catalog/available/full",
        "/v1/explain/catalog/markdown",
        "/v1/explain/commit/{commit_sha}",
        "/v1/explain/attribution",
        "/v1/explain/discover",
        "/v1/explain/diagnostics/investigate",
        "/v1/explain/diagnostics/common-cause",
        "/v1/explain/diagnostics/what-changed",
    }
    missing = expected - paths
    assert not missing, f"router lost endpoints: {missing}"


# ============================================================================
# Helpers
# ============================================================================

async def _async_none():
    """Coroutine that yields None — for patching async getters."""
    return None
