"""Q.116.E — testes do query-param ``order`` em /v1/learning/boat-phase-scores.

O endpoint passou a aceitar ``order=asc|desc``. Por omissão é ``desc`` (melhores
barcos primeiro, comportamento histórico do Q.115.X6). Com ``order=asc`` o
FaseSheet do Q.116.A consegue listar os barcos mais EXIGENTES por fase (pior
score = mais difícil).
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, List
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.learning.api_boat_scores import router as boat_scores_router
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

TEST_TENANT = UUID("22222222-2222-2222-2222-222222222222")


def _score_row(
    boat_id: str,
    phase_id: str,
    score: float,
    sample_count: int = 10,
) -> SimpleNamespace:
    return SimpleNamespace(
        boat_id=boat_id,
        phase_id=phase_id,
        score=score,
        sample_count=sample_count,
        last_computed_at=datetime.now(timezone.utc),
        tenant_id=TEST_TENANT,
    )


def _build_app(rows: List[Any]):
    """App de teste com FakeSession que respeita a direcção do ``ORDER BY``.

    Inspecciona o último ``order_by`` declarado no statement SQLAlchemy e
    devolve as ``rows`` ordenadas por ``score`` na direcção pedida — assim os
    testes verificam o param ``order`` ponta-a-ponta sem precisarem de DB real.
    """

    class _FakeResult:
        def __init__(self, sorted_rows):
            self._rows = sorted_rows

        def scalars(self):
            return self

        def all(self):
            return self._rows

    async def _fake_session():
        class _Sess:
            async def execute(self, stmt):
                # SQLAlchemy 2.0: stmt._order_by_clauses guarda a expressão.
                # Compilamos para texto e detectamos a direcção pelo sufixo.
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
                ascending = " ASC" in compiled.upper().split("ORDER BY", 1)[-1]
                sorted_rows = sorted(
                    rows, key=lambda r: r.score, reverse=not ascending
                )
                return _FakeResult(sorted_rows)

        yield _Sess()

    app = FastAPI()
    app.include_router(boat_scores_router)
    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT
    return TestClient(app, raise_server_exceptions=True)


def test_order_asc_devolve_pior_score_primeiro_q116_e():
    """``?order=asc`` lista os barcos mais EXIGENTES (pior score) primeiro."""
    rows = [
        _score_row("Nelo 510 K1", "INJECAO", 0.5),
        _score_row("Nelo 400 C1", "INJECAO", 0.1),
        _score_row("Nelo 600 K2", "INJECAO", 0.9),
    ]
    client = _build_app(rows)

    resp = client.get(
        "/v1/learning/boat-phase-scores?order=asc",
        headers={"X-Tenant-Id": str(TEST_TENANT)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    scores = [row["score"] for row in data]
    assert scores == [0.1, 0.5, 0.9], scores
    assert data[0]["boat_id"] == "Nelo 400 C1"


def test_order_desc_default_devolve_melhor_score_primeiro_q116_e():
    """Sem ``order`` (default ``desc``) lista os MELHORES barcos primeiro."""
    rows = [
        _score_row("Nelo 510 K1", "INJECAO", 0.5),
        _score_row("Nelo 400 C1", "INJECAO", 0.1),
        _score_row("Nelo 600 K2", "INJECAO", 0.9),
    ]
    client = _build_app(rows)

    resp = client.get(
        "/v1/learning/boat-phase-scores",
        headers={"X-Tenant-Id": str(TEST_TENANT)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    scores = [row["score"] for row in data]
    assert scores == [0.9, 0.5, 0.1], scores
    assert data[0]["boat_id"] == "Nelo 600 K2"


def test_order_invalido_rejeitado_q116_e():
    """``?order=bogus`` é rejeitado pela validação Pydantic (422)."""
    client = _build_app([])

    resp = client.get(
        "/v1/learning/boat-phase-scores?order=bogus",
        headers={"X-Tenant-Id": str(TEST_TENANT)},
    )
    assert resp.status_code == 422, resp.text
