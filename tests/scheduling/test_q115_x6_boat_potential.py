"""Q.115.X6.B — testes do job boat_potential + endpoint /v1/learning/boat-potential.

5 cenários conforme DoD:
1. Componentes: 4 componentes calculadas correctamente
2. Score normalizado: potential_score ∈ [0,1]
3. Lifetime soma: revenue_eur_lifetime acumula vendas
4. Idempotente: correr 2x → mesmo resultado
5. Endpoint GET /v1/learning/boat-potential: ordenado por potential_score desc
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.scheduling.jobs.boat_potential_job import _clamp, _percentile_90

TEST_TENANT = UUID("33333333-3333-3333-3333-333333333333")
BOAT_A = "Nelo 510 K1"
BOAT_B = "Nelo 400 C1"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _potential_row(
    boat_id: str = BOAT_A,
    potential_score: float = 0.75,
    revenue_eur_lifetime: Decimal = Decimal("50000.00"),
    last_computed_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        boat_id=boat_id,
        potential_score=potential_score,
        revenue_eur_lifetime=revenue_eur_lifetime,
        last_computed_at=last_computed_at or datetime.now(timezone.utc),
        tenant_id=TEST_TENANT,
    )


# ─── 1. Componentes calculadas correctamente ─────────────────────────────────


def test_componentes_score_formula():
    """4 componentes produzem potential_score no intervalo esperado."""
    p90_tp = 100.0
    p90_dur = 500.0
    p90_rev = 1000.0

    tp_val = 80.0       # 80% do p90 → throughput_norm=0.8
    dur_val = 200.0     # 40% do p90 → lead_time_norm=0.6
    defect_count = 5.0
    rev_val = 900.0     # 90% do p90 → margin_norm=0.9

    margin_norm = _clamp(rev_val / p90_rev)
    throughput_norm = _clamp(tp_val / p90_tp)
    defect_rate = defect_count / max(tp_val, 1)
    low_defect_norm = _clamp(1.0 - defect_rate)
    lead_time_norm = _clamp(1.0 - (dur_val / p90_dur))

    assert abs(margin_norm - 0.9) < 1e-9
    assert abs(throughput_norm - 0.8) < 1e-9
    # 1 - 5/80 = 1 - 0.0625 = 0.9375
    assert abs(low_defect_norm - 0.9375) < 1e-4
    assert abs(lead_time_norm - 0.6) < 1e-9

    potential_score = _clamp(
        (margin_norm + throughput_norm + low_defect_norm + lead_time_norm) / 4.0
    )
    # mean(0.9, 0.8, 0.9375, 0.6) = 3.2375/4 ≈ 0.809
    assert 0.0 <= potential_score <= 1.0
    assert abs(potential_score - 0.809375) < 1e-4


# ─── 2. Score normalizado ─────────────────────────────────────────────────────


def test_score_sempre_entre_0_e_1():
    """Mesmo com valores extremos, potential_score ∈ [0,1]."""
    for margin, tp, defect, lead in [
        (0.0, 0.0, 1.0, 1.0),    # pior caso
        (1.0, 1.0, 0.0, 0.0),    # melhor caso
        (2.0, 3.0, -0.1, 1.5),   # valores fora de range → clamp
    ]:
        score = _clamp((margin + tp + defect + lead) / 4.0)
        assert 0.0 <= score <= 1.0


def test_percentile_90_lista_vazia_retorna_1():
    """Lista vazia → percentil 90 retorna 1.0 (evita divisão por zero)."""
    assert _percentile_90([]) == 1.0


def test_percentile_90_valores():
    vals = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p90 = _percentile_90(vals)
    assert p90 == 90.0


# ─── 3. Lifetime soma ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_job_soma_revenue_lifetime():
    """revenue_eur_lifetime deve reflectir o somatório de vendas históricas."""
    from src.scheduling.jobs.boat_potential_job import _boat_potential_job

    tp_row = SimpleNamespace(boat_id=BOAT_A, concluidas=50, avg_duration_min=120.0)
    defect_row_empty: list = []
    rev_row = SimpleNamespace(
        boat_id=BOAT_A,
        total_eur=75000.0,
        num_orders=10,
    )

    upserted: list[dict] = []
    call_idx = [0]

    async def _fake_execute(stmt_or_text, params=None):
        result = MagicMock()
        if params is not None and "score" in (params or {}):
            upserted.append(dict(params))
            result.all.return_value = []
            return result
        call_idx[0] += 1
        n = call_idx[0]
        if n == 1:
            result.all.return_value = [tp_row]
        elif n == 2:
            result.all.return_value = defect_row_empty
        else:
            result.all.return_value = [rev_row]
        return result

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(side_effect=_fake_execute)
    fake_session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=fake_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    import src.scheduling.jobs.boat_potential_job as _job_mod

    original = _job_mod.get_session_context
    try:
        _job_mod.get_session_context = lambda: mock_ctx
        await _boat_potential_job(TEST_TENANT)
    finally:
        _job_mod.get_session_context = original

    assert len(upserted) == 1
    assert abs(upserted[0]["rev"] - 75000.0) < 1e-2
    # potential_score ∈ [0,1]
    assert 0.0 <= upserted[0]["score"] <= 1.0


# ─── 4. Idempotente ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_job_idempotente():
    """Correr o job 2x com os mesmos dados produz scores idênticos."""
    from src.scheduling.jobs.boat_potential_job import _boat_potential_job

    tp_row = SimpleNamespace(boat_id=BOAT_A, concluidas=40, avg_duration_min=200.0)
    rev_row = SimpleNamespace(boat_id=BOAT_A, total_eur=40000.0, num_orders=8)
    upserted_scores: list[float] = []

    call_idx = [0]

    async def _fake_execute(stmt_or_text, params=None):
        result = MagicMock()
        if params is not None and "score" in (params or {}):
            upserted_scores.append(params["score"])
            result.all.return_value = []
            return result
        call_idx[0] += 1
        n = call_idx[0]
        if n == 1:
            result.all.return_value = [tp_row]
        elif n == 2:
            result.all.return_value = []
        else:
            result.all.return_value = [rev_row]
        return result

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(side_effect=_fake_execute)
    fake_session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=fake_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    import src.scheduling.jobs.boat_potential_job as _job_mod

    original = _job_mod.get_session_context
    try:
        _job_mod.get_session_context = lambda: mock_ctx

        await _boat_potential_job(TEST_TENANT)
        score1 = upserted_scores[-1] if upserted_scores else None

        call_idx[0] = 0
        upserted_scores.clear()
        await _boat_potential_job(TEST_TENANT)
        score2 = upserted_scores[-1] if upserted_scores else None
    finally:
        _job_mod.get_session_context = original

    assert score1 is not None
    assert score2 is not None
    assert abs(score1 - score2) < 1e-6


# ─── 5. Endpoint GET /v1/learning/boat-potential ─────────────────────────────


def _build_potential_app(potentials: List[Any]):
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
                return _FakeResult(potentials)

        yield _Sess()

    app = FastAPI()
    app.include_router(boat_scores_router)
    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT
    return TestClient(app, raise_server_exceptions=True)


def test_endpoint_boat_potential_ordenado():
    """GET /v1/learning/boat-potential → lista por potential_score desc."""
    rows = [
        _potential_row(boat_id=BOAT_A, potential_score=0.85, revenue_eur_lifetime=Decimal("50000")),
        _potential_row(boat_id=BOAT_B, potential_score=0.60, revenue_eur_lifetime=Decimal("30000")),
    ]
    client = _build_potential_app(rows)
    resp = client.get(
        "/v1/learning/boat-potential",
        headers={"X-Tenant-Id": str(TEST_TENANT)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 2
    assert data[0]["potential_score"] >= data[1]["potential_score"]
    assert data[0]["boat_id"] == BOAT_A
    assert float(data[0]["revenue_eur_lifetime"]) == 50000.0
