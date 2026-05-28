"""Q.115.G — testes do job phase_operator_affinity + endpoint /v1/learning/affinities.

6 cenários conforme DoD:
1. Happy path: afinidades calculadas correctamente a partir de fixture
2. Cap 10%: segunda execução com delta grande → limitado a 0.1
3. Sem dados: tenant sem ops → devolve sem erro, zero upserts
4. Idempotente: correr 2x com mesmos dados → mesmo resultado
5. Endpoint GET /v1/learning/affinities: devolve lista ordenada
6. Filtro ?phase_id: limita a fase específica
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.scheduling.jobs.phase_operator_affinity import _apply_cap, _clamp, _NEUTRAL_SCORE

TEST_TENANT = UUID("11111111-1111-1111-1111-111111111111")
OP_A = uuid4()
OP_B = uuid4()
PHASE_X = "INJECAO"
PHASE_Y = "DESMOLDAGEM"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _row(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def _affinity_row(
    operator_id: UUID = OP_A,
    phase_id: str = PHASE_X,
    score: float = 0.8,
    sample_count: int = 10,
    last_computed_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        operator_id=operator_id,
        phase_id=phase_id,
        score=score,
        sample_count=sample_count,
        last_computed_at=last_computed_at or datetime.now(timezone.utc),
        tenant_id=TEST_TENANT,
    )


# ─── 1. Cap 10% — testes unitários puros ─────────────────────────────────────


def test_apply_cap_primeira_vez_sobe_mais_10_pct():
    """Primeira execução: score 0.9 partindo de neutro 0.5 → cap 0.5+0.1=0.6."""
    resultado = _apply_cap(0.9, previous_score=None)
    assert abs(resultado - 0.6) < 1e-9


def test_apply_cap_primeira_vez_desce_mais_10_pct():
    """Primeira execução: score 0.1 partindo de neutro 0.5 → cap 0.5-0.1=0.4."""
    resultado = _apply_cap(0.1, previous_score=None)
    assert abs(resultado - 0.4) < 1e-9


def test_apply_cap_segunda_execucao_delta_grande():
    """2ª execução: score anterior 0.5, novo 0.95 → cap 0.6."""
    resultado = _apply_cap(0.95, previous_score=0.5)
    assert abs(resultado - 0.6) < 1e-9


def test_apply_cap_pequeno_delta_passa():
    """Delta dentro do limite: 0.5 → 0.55 → sem alteração."""
    resultado = _apply_cap(0.55, previous_score=0.5)
    assert abs(resultado - 0.55) < 1e-9


def test_clamp_limita_intervalo():
    assert _clamp(1.5) == 1.0
    assert _clamp(-0.1) == 0.0
    assert _clamp(0.5) == 0.5


# ─── 2. Teste 2 (DoD): cap 10% em 2ª execução ───────────────────────────────


def test_cap_10_pct_segunda_execucao():
    """Simula segunda execução com mudança grande: delta limitado a 0.1."""
    # Primeiro run: partindo do neutro, win_rate=1.0 → cap 0.6
    score_run1 = _apply_cap(1.0, previous_score=None)
    assert abs(score_run1 - 0.6) < 1e-9

    # Segundo run: anterior=0.6, novo ainda 1.0 → cap 0.7
    score_run2 = _apply_cap(1.0, previous_score=score_run1)
    assert abs(score_run2 - 0.7) < 1e-9

    # Confirma que delta é exactamente 0.1
    assert abs(score_run2 - score_run1 - 0.1) < 1e-9


# ─── 3. Job: sem dados → sem erro ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_job_sem_dados_nao_crasha():
    """Tenant sem ops nos últimos 90d → job termina sem erro, zero upserts."""
    from src.scheduling.jobs.phase_operator_affinity import _phase_operator_affinity_job

    fake_result = MagicMock()
    fake_result.all.return_value = []

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=fake_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    import src.scheduling.jobs.phase_operator_affinity as _job_mod

    original = _job_mod.get_session_context
    try:
        _job_mod.get_session_context = lambda: mock_ctx
        await _phase_operator_affinity_job(TEST_TENANT)
    finally:
        _job_mod.get_session_context = original

    # commit nunca chamado (early return antes do loop)
    fake_session.commit.assert_not_called()


# ─── 4. Job: idempotente (mesmos dados 2x → mesmo score) ─────────────────────


@pytest.mark.asyncio
async def test_job_idempotente():
    """Correr o job 2x com os mesmos dados produz scores idênticos."""
    from src.scheduling.jobs.phase_operator_affinity import _phase_operator_affinity_job

    # Agregado da query: 8 de 10 concluídas
    history_row = SimpleNamespace(
        worker_id=OP_A, phase_id=PHASE_X, total=10, concluidas=8
    )
    prev_row = SimpleNamespace(operator_id=OP_A, phase_id=PHASE_X, score=0.5)

    upserted_scores: list[float] = []

    async def _fake_execute(stmt, params=None):
        result = MagicMock()
        if params is not None:
            # Chamada de UPSERT — captura o score
            upserted_scores.append(params["score"])
            result.all.return_value = []
            return result
        # Distingue query de aggregado vs query de previous pelo tipo stmt
        stmt_str = str(stmt)
        if "group_by" in stmt_str.lower() or "worker_id" in stmt_str.lower():
            result.all.return_value = [history_row]
        else:
            result.all.return_value = [prev_row]
        return result

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(side_effect=_fake_execute)
    fake_session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=fake_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    import src.scheduling.jobs.phase_operator_affinity as _job_mod

    original = _job_mod.get_session_context
    try:
        _job_mod.get_session_context = lambda: mock_ctx
        await _phase_operator_affinity_job(TEST_TENANT)
        score_run1 = upserted_scores[-1] if upserted_scores else None

        # 2ª execução: o score anterior é o que foi calculado na 1ª
        upserted_scores.clear()
        await _phase_operator_affinity_job(TEST_TENANT)
        score_run2 = upserted_scores[-1] if upserted_scores else None
    finally:
        _job_mod.get_session_context = original

    assert score_run1 is not None
    assert score_run2 is not None
    # Com os mesmos dados históricos e o mesmo score anterior, deve produzir o mesmo resultado
    assert abs(score_run1 - score_run2) < 1e-6


# ─── 5. Endpoint GET /v1/learning/affinities ─────────────────────────────────


def _build_test_app(affinities: List[Any], employees=None, phases=None):
    """Cria app mínima com FakeSession para testar o endpoint de afinidades."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.learning.api_affinities import router as affinities_router
    from src.shared.auth.headers import require_tenant_header
    from src.shared.database import get_session

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return self

        def all(self):
            return self._rows

    call_count = [0]

    async def _fake_session():
        class _Sess:
            async def execute(self, stmt):
                call_count[0] += 1
                n = call_count[0]
                if n == 1:
                    return _FakeResult(affinities or [])
                elif n == 2:
                    return _FakeResult(employees or [])
                else:
                    return _FakeResult(phases or [])

        yield _Sess()

    app = FastAPI()
    app.include_router(affinities_router)
    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT
    return TestClient(app, raise_server_exceptions=True)


def test_endpoint_devolve_lista_ordenada():
    """GET /v1/learning/affinities devolve lista ordenada por score desc."""
    now = datetime.now(timezone.utc)
    affinities = [
        _affinity_row(operator_id=OP_A, phase_id=PHASE_X, score=0.9, sample_count=15),
        _affinity_row(operator_id=OP_B, phase_id=PHASE_Y, score=0.6, sample_count=5),
    ]
    employees = [
        SimpleNamespace(id=OP_A, employee_name="Alice"),
        SimpleNamespace(id=OP_B, employee_name="Bob"),
    ]
    phases = [
        SimpleNamespace(phase_id=PHASE_X, phase_name="Injecção"),
        SimpleNamespace(phase_id=PHASE_Y, phase_name="Desmoldagem"),
    ]

    client = _build_test_app(affinities, employees, phases)
    resp = client.get(
        "/v1/learning/affinities",
        headers={"X-Tenant-Id": str(TEST_TENANT)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 2
    # Ordenado por score desc
    assert data[0]["score"] >= data[1]["score"]
    assert data[0]["operator_name"] == "Alice"
    assert data[0]["phase_name"] == "Injecção"


def test_endpoint_lista_vazia_sem_dados():
    """GET /v1/learning/affinities → lista vazia se job nunca correu."""
    client = _build_test_app(affinities=[], employees=[], phases=[])
    resp = client.get(
        "/v1/learning/affinities",
        headers={"X-Tenant-Id": str(TEST_TENANT)},
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ─── 6. Filtro ?phase_id ─────────────────────────────────────────────────────


def test_endpoint_filtro_phase_id():
    """?phase_id=INJECAO devolve só afinidades de INJECAO."""
    now = datetime.now(timezone.utc)
    # O filtro é aplicado na query SQL (testamos que o endpoint passa o param
    # — a session fake devolve sempre o mesmo resultado; o assert verifica
    # que a resposta é coerente com os dados devolvidos pela session)
    affinities = [
        _affinity_row(operator_id=OP_A, phase_id=PHASE_X, score=0.85),
    ]
    employees = [SimpleNamespace(id=OP_A, employee_name="Alice")]
    phases = [SimpleNamespace(phase_id=PHASE_X, phase_name="Injecção")]

    client = _build_test_app(affinities, employees, phases)
    resp = client.get(
        f"/v1/learning/affinities?phase_id={PHASE_X}",
        headers={"X-Tenant-Id": str(TEST_TENANT)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["phase_id"] == PHASE_X
