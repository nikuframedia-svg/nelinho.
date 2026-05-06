"""Sprint S6 — guard tests for CORS, timeouts, middleware (Φ5).

Static checks against the source so a regression is caught at unit-test time.
The CORS test exercises the FastAPI app via TestClient.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


REPO = Path(__file__).resolve().parents[2]


# --- Φ5: CORS no longer wildcards methods/headers with credentials ----------

def test_cors_methods_explicit_not_wildcard():
    """Strip comment lines before searching so doc/why notes can mention the
    old buggy directive without tripping the guard."""
    text = (REPO / "src" / "main.py").read_text(encoding="utf-8")
    code_only = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    assert 'allow_methods=["*"]' not in code_only
    assert 'allow_headers=["*"]' not in code_only


def test_cors_headers_listed_explicitly():
    text = (REPO / "src" / "main.py").read_text(encoding="utf-8")
    # Sanity: explicit headers we expect the API to accept.
    for header in ("Authorization", "Content-Type", "X-Tenant-Id", "X-User-Id"):
        assert f'"{header}"' in text


# --- httpx timeouts ----------------------------------------------------------

def test_tool_registry_fetch_openapi_has_timeout():
    text = (REPO / "src" / "copilot" / "tool_registry.py").read_text(encoding="utf-8")
    # The two `httpx.AsyncClient()` call sites must now pass `timeout=`.
    bare_client = "httpx.AsyncClient()"
    assert text.count(bare_client) == 0, (
        f"`{bare_client}` (no timeout) still present in tool_registry.py — "
        "every async client must declare a bounded timeout."
    )


# --- Redis socket_timeout ----------------------------------------------------

def test_redis_pool_has_socket_timeout():
    text = (REPO / "src" / "shared" / "redis_client.py").read_text(encoding="utf-8")
    assert "socket_timeout=" in text
    assert "socket_connect_timeout=" in text


# --- E2E preflight: OPTIONS from a foreign origin ----------------------------

def test_cors_preflight_does_not_advertise_wildcard_credentials():
    """Sanity: a real OPTIONS preflight against the live app must not return
    `Access-Control-Allow-Methods: *` while `Access-Control-Allow-Credentials`
    is true."""
    from src.main import app

    client = TestClient(app)
    r = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    # Some FastAPI versions answer 200 with CORS headers, some answer 405; we
    # only care that the wildcard combo isn't advertised.
    methods = r.headers.get("access-control-allow-methods", "")
    creds = r.headers.get("access-control-allow-credentials", "").lower()
    if creds == "true":
        assert "*" not in methods, (
            "wildcard ACAM with credentials=true is forbidden by the CORS spec"
        )
