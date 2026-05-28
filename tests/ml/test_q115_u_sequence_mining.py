"""
Q.115.U — testes SequenceMiningModel
=====================================

≥5 testes:
1. fit + predict happy path com fixture sintética
2. Lift > 1 para sequência conhecida tóxica
3. Sample insuficiente (<10 OFs) → ValueError
4. Endpoint GET /v1/ml/sequence-risk 200 + 404
5. AUC ≥0.7 em fixture controlada
"""

import pytest
import pandas as pd

from src.ml.models_domain.sequence_mining import SequenceMiningModel, SequenceRisk


# ------------------------------------------------------------------
# Fixtures sintéticas
# ------------------------------------------------------------------

def _make_phase_histories(n_ofs: int = 50) -> pd.DataFrame:
    """50 OFs com sequências A→B→C ou A→D→C."""
    rows = []
    for i in range(n_ofs):
        seq = ["A", "B", "C"] if i % 2 == 0 else ["A", "D", "C"]
        for order, phase in enumerate(seq):
            rows.append({"of_id": f"OF-{i:03d}", "phase_code": phase, "phase_order": order})
    return pd.DataFrame(rows)


def _make_defects(toxic_seq: bool = True) -> pd.DataFrame:
    """
    OFs 0,2,4,...,18 usam A→B→C e são marcados como defeituosos.
    Isso cria lift >1 para a sub-sequência (A,B,C).
    """
    if not toxic_seq:
        return pd.DataFrame(columns=["of_id"])
    # 10 primeiros OFs pares (A→B→C) são defeituosos
    defect_ofs = [f"OF-{i:03d}" for i in range(0, 20, 2)]
    return pd.DataFrame({"of_id": defect_ofs})


# ------------------------------------------------------------------
# Testes
# ------------------------------------------------------------------

class TestSequenceMiningFit:
    def test_fit_predict_happy_path(self):
        """Testa fit + predict devolve SequenceRisk válido."""
        model = SequenceMiningModel(min_support=0.05)
        ph = _make_phase_histories(50)
        defects = _make_defects()

        model.fit(ph, defects)

        assert model.is_trained
        risk = model.predict_risk_for_sequence(["A", "B", "C"])
        assert isinstance(risk, SequenceRisk)
        assert 0.0 <= risk.p_defect <= 1.0
        assert risk.support > 0

    def test_lift_maior_1_sequencia_toxica(self):
        """Sub-sequência A→B→C deve ter lift >1 pois está sobre-representada nos defeitos."""
        model = SequenceMiningModel(min_support=0.05)
        ph = _make_phase_histories(50)
        defects = _make_defects(toxic_seq=True)

        model.fit(ph, defects)

        # (A, B, C) é a sequência tóxica — todos os OFs pares usam-na e são defeituosos
        risky = model.top_risky_sequences(k=20)
        toxic = next(
            (r for r in risky if tuple(r.sequence) == ("A", "B", "C")),
            None,
        )
        assert toxic is not None, "Sequência (A,B,C) deve estar no top risky"
        assert toxic.lift > 1.0, f"Lift esperado >1, got {toxic.lift}"

    def test_sample_insuficiente_levanta_error(self):
        """Menos de 10 OFs levanta ValueError."""
        model = SequenceMiningModel()
        ph = pd.DataFrame([
            {"of_id": f"OF-{i}", "phase_code": "A", "phase_order": 0}
            for i in range(5)
        ])
        defects = pd.DataFrame(columns=["of_id"])

        with pytest.raises(ValueError, match="10"):
            model.fit(ph, defects)

    def test_auc_maior_07_fixture_controlada(self):
        """AUC ≥0.7 quando a sequência tóxica é claramente correlacionada com defeito."""
        model = SequenceMiningModel(min_support=0.04)
        # 100 OFs: metade com seq tóxica A→B→C→D (defeituosa), metade A→E→C
        rows = []
        for i in range(100):
            if i < 50:
                seq = ["A", "B", "C", "D"]
            else:
                seq = ["A", "E", "C"]
            for order, phase in enumerate(seq):
                rows.append({"of_id": f"OF-{i:03d}", "phase_code": phase, "phase_order": order})
        ph = pd.DataFrame(rows)
        # Todos os primeiros 50 OFs são defeituosos
        defects = pd.DataFrame({"of_id": [f"OF-{i:03d}" for i in range(50)]})

        model.fit(ph, defects)
        auc = model.evaluate_auc(ph, defects)
        assert auc >= 0.7, f"AUC esperado >=0.7, got {auc:.4f}"

    def test_top_risky_sequences_k(self):
        """top_risky_sequences(k) devolve ≤k items ordenados por lift desc."""
        model = SequenceMiningModel(min_support=0.05)
        ph = _make_phase_histories(40)
        defects = _make_defects()
        model.fit(ph, defects)

        top5 = model.top_risky_sequences(k=5)
        assert len(top5) <= 5
        lifts = [r.lift for r in top5]
        assert lifts == sorted(lifts, reverse=True), "Deve estar ordenado por lift desc"


# ------------------------------------------------------------------
# Endpoint tests (usa FastAPI TestClient)
# ------------------------------------------------------------------

@pytest.fixture()
def ml_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.ml.api import router
    import src.ml.api as ml_api

    app = FastAPI()
    app.include_router(router)

    # Injector de tenant header
    from starlette.middleware.base import BaseHTTPMiddleware
    class TenantMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            return await call_next(request)

    return TestClient(app, headers={"X-Tenant-Id": "00000000-0000-0000-0000-000000000001"})


def test_sequence_risk_endpoint_404_sem_modelo(ml_client):
    """404 quando modelo não treinado."""
    import src.ml.api as ml_api
    ml_api._sequence_model = None
    resp = ml_client.get("/v1/ml/sequence-risk?phase_sequence=A,B,C")
    assert resp.status_code == 404


def test_sequence_risk_endpoint_200_com_modelo_treinado():
    """200 quando modelo está treinado — usa app com estado partilhado."""
    import src.ml.api as ml_api
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    model = SequenceMiningModel(min_support=0.05)
    ph = _make_phase_histories(50)
    defects = _make_defects()
    model.fit(ph, defects)
    ml_api._sequence_model = model

    app = FastAPI()
    app.include_router(ml_api.router)
    client = TestClient(app, headers={"X-Tenant-Id": "00000000-0000-0000-0000-000000000001"})

    resp = client.get("/v1/ml/sequence-risk?phase_sequence=A,B,C")
    assert resp.status_code == 200
    data = resp.json()
    assert "lift" in data
    assert "p_defect" in data
    # cleanup
    ml_api._sequence_model = None
