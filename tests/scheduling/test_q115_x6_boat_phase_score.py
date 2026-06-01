"""Q.115.X6.A — testes do job boat_phase_score + endpoint /v1/learning/boat-phase-scores.

5 cenários conforme DoD:
1. Happy path: score calculado correctamente a partir de fixture
2. Sample vazio: tenant sem ops → termina sem erro, zero upserts
3. Cap 10%: delta grande → limitado a 0.1
4. Idempotente: correr 2x com mesmos dados → mesmo score
5. Endpoint GET /v1/learning/boat-phase-scores: devolve lista ordenada
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.scheduling.jobs.boat_phase_score_job import (
    _apply_cap,
    _clamp,
    _NEUTRAL_SCORE,
    _DEFECT_WEIGHT,
)

TEST_TENANT = UUID("22222222-2222-2222-2222-222222222222")
BOAT_A = "Nelo 510 K1"
BOAT_B = "Nelo 400 C1"
PHASE_X = "INJECAO"
PHASE_Y = "DESMOLDAGEM"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _score_row(
    boat_id: str = BOAT_A,
    phase_id: str = PHASE_X,
    score: float = 0.7,
    sample_count: int = 10,
    last_computed_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        boat_id=boat_id,
        phase_id=phase_id,
        score=score,
        sample_count=sample_count,
        last_computed_at=last_computed_at or datetime.now(timezone.utc),
        tenant_id=TEST_TENANT,
    )


# ─── 1. Fórmula score unitária ────────────────────────────────────────────────


def test_score_formula_sem_defeitos():
    """Win rate 1.0, zero defeitos → raw_score=1.0; com cap desde neutro → 0.6."""
    win_rate = 1.0
    defect_count = 0
    total = 10
    penalty = _DEFECT_WEIGHT * (defect_count / total)
    raw_score = _clamp(win_rate - penalty)
    assert raw_score == 1.0
    # aplicando cap desde neutro
    final = _apply_cap(raw_score, previous_score=None)
    assert abs(final - 0.6) < 1e-9


def test_score_formula_com_defeitos():
    """Win rate 0.8, 2 defeitos em 10 → penalidade 0.06; raw=0.74."""
    win_rate = 0.8
    defect_count = 2
    total = 10
    penalty = _DEFECT_WEIGHT * (defect_count / total)
    raw_score = _clamp(win_rate - penalty)
    assert abs(raw_score - 0.74) < 1e-9


def test_clamp_intervalo():
    assert _clamp(1.5) == 1.0
    assert _clamp(-0.5) == 0.0
    assert _clamp(0.5) == 0.5


# ─── 2. Sample vazio → sem erro ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_job_sem_dados_nao_crasha():
    """Tenant sem ops nos últimos 90d → job termina sem erro, commit não chamado."""
    from src.scheduling.jobs.boat_phase_score_job import _boat_phase_score_job

    fake_result = MagicMock()
    fake_result.all.return_value = []

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=fake_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    import src.scheduling.jobs.boat_phase_score_job as _job_mod

    original = _job_mod.get_session_context
    try:
        _job_mod.get_session_context = lambda: mock_ctx
        await _boat_phase_score_job(TEST_TENANT)
    finally:
        _job_mod.get_session_context = original

    # early return antes do commit
    fake_session.commit.assert_not_called()


# ─── 3. Cap 10% ──────────────────────────────────────────────────────────────


def test_cap_10_pct_segunda_execucao():
    """Delta acima de 0.1 fica limitado em cada execução."""
    score_run1 = _apply_cap(1.0, previous_score=None)
    assert abs(score_run1 - 0.6) < 1e-9

    score_run2 = _apply_cap(1.0, previous_score=score_run1)
    assert abs(score_run2 - 0.7) < 1e-9

    assert abs(score_run2 - score_run1 - 0.1) < 1e-9


# ─── 4. Job repontado (Q.150): of_fp, boat_id=product_name, defeito=OFFP_RETURN ─


def _run_boat_job(agg_rows, prev_rows):
    """Corre o job com sessão fake. Devolve (go, captured_upserts)."""
    captured: list[dict] = []

    class _Res:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    async def _exec(stmt, params=None):
        if params and "cutoff" in params:    # 1) agregação of_fp
            return _Res(agg_rows)
        if params and "bid" in params:        # 3) UPSERT — captura
            captured.append(params)
            return _Res([])
        return _Res(prev_rows)                 # 2) scores anteriores

    sess = AsyncMock()
    sess.execute = AsyncMock(side_effect=_exec)
    sess.commit = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=sess)
    ctx.__aexit__ = AsyncMock(return_value=False)

    import src.scheduling.jobs.boat_phase_score_job as _job_mod

    async def _go():
        original = _job_mod.get_session_context
        try:
            _job_mod.get_session_context = lambda: ctx
            from src.scheduling.jobs.boat_phase_score_job import _boat_phase_score_job
            await _boat_phase_score_job(TEST_TENANT)
        finally:
            _job_mod.get_session_context = original
        return sess

    return _go, captured


@pytest.mark.asyncio
async def test_job_score_com_defeito_e_boat_id():
    """Q.150: boat_id = product_name; score = win_rate − 0.3·taxa_defeito."""
    agg = [SimpleNamespace(
        boat_id="Nacra 450", phase_id="40", total=10, concluidas=8, defects=2,
    )]
    # previous=0.7 → raw 0.74 passa o cap (delta 0.04)
    prev = [SimpleNamespace(boat_id="Nacra 450", phase_id="40", score=0.7)]

    go, captured = _run_boat_job(agg, prev)
    await go()

    assert len(captured) == 1
    p = captured[0]
    assert p["bid"] == "Nacra 450"
    assert p["pid"] == "40"
    assert p["cnt"] == 10
    # raw = 0.8 − 0.3·(2/10) = 0.8 − 0.06 = 0.74
    assert abs(p["score"] - 0.74) < 1e-9


@pytest.mark.asyncio
async def test_job_idempotente():
    """Mesmos dados + mesmo score anterior → mesmo resultado."""
    agg = [SimpleNamespace(
        boat_id=BOAT_A, phase_id=PHASE_X, total=10, concluidas=8, defects=0,
    )]
    prev = [SimpleNamespace(boat_id=BOAT_A, phase_id=PHASE_X, score=0.7)]

    go1, c1 = _run_boat_job(agg, prev)
    await go1()
    go2, c2 = _run_boat_job(agg, prev)
    await go2()

    assert c1 and c2
    assert abs(c1[0]["score"] - c2[0]["score"]) < 1e-9


# ─── 5. Endpoint GET /v1/learning/boat-phase-scores ──────────────────────────


def _build_boat_score_app(scores: List[Any]):
    """Cria app mínima com FakeSession para testar o endpoint."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.learning.api_boat_scores import router as boat_scores_router
    from src.shared.auth.headers import require_tenant_header
    from src.shared.database import get_session

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return self

        def all(self):
            return self._rows

    async def _fake_session():
        class _Sess:
            async def execute(self, stmt):
                return _FakeResult(scores)

        yield _Sess()

    app = FastAPI()
    app.include_router(boat_scores_router)
    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT
    return TestClient(app, raise_server_exceptions=True)


def test_endpoint_boat_phase_scores_ordenado():
    """GET /v1/learning/boat-phase-scores → lista por score desc."""
    now = datetime.now(timezone.utc)
    rows = [
        _score_row(boat_id=BOAT_A, phase_id=PHASE_X, score=0.9),
        _score_row(boat_id=BOAT_B, phase_id=PHASE_Y, score=0.5),
    ]
    client = _build_boat_score_app(rows)
    resp = client.get(
        "/v1/learning/boat-phase-scores",
        headers={"X-Tenant-Id": str(TEST_TENANT)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 2
    assert data[0]["score"] >= data[1]["score"]
    assert data[0]["boat_id"] == BOAT_A
