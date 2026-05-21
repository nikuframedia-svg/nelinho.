"""Q.54.S — endpoint de qualidade dos moldes.

`GET /v1/quality/molds` cruza o master curado de moldes
(`factory_curated.mold`, carregado no Q.54.R) com os eventos de qualidade
(`quality_event`). Substitui, na tab Moldes da Qualidade, os scores de
saúde sintéticos de `plan.mold` — cujo espaço de IDs não casava com os
dados de defeitos — por defeitos reais por molde.

A query agregada foi verificada contra a BD real (molde 70907 "K1
Vanquish 7 ML" → 2660 defeitos). Estes testes cobrem o shaping da
resposta com uma sessão falsa.
"""

from __future__ import annotations

from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.quality.api import router as quality_router
from src.shared.database import get_session
from tests.conftest import FakeSession

TENANT = "00000000-0000-0000-0000-000000000001"
HEADERS = {"X-Tenant-Id": TENANT}


def _session_with_rows(rows) -> FakeSession:
    """Q.68.3.3 — Canonical FakeSession seeded for one ``execute().all()`` call."""
    session = FakeSession()
    session.queue_scalars(list(rows))
    return session


def _app(session) -> FastAPI:
    app = FastAPI()
    app.include_router(quality_router)
    app.dependency_overrides[get_session] = lambda: session
    return app


def test_mold_quality_shapes_rows():
    rows = [
        ("70907", "1040136", "K1 Vanquish 7 ML", False, 2660, 2660, date(2026, 5, 1)),
        ("70025", "14", "Navigator", True, 0, 0, None),
    ]
    client = TestClient(_app(_session_with_rows(rows)))
    resp = client.get("/v1/quality/molds", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body[0] == {
        "molde_id": "70907",
        "nome": "1040136",
        "tipo": "K1 Vanquish 7 ML",
        "em_manutencao": False,
        "defect_events": 2660,
        "defect_qty": 2660,
        "last_defect": "2026-05-01",
    }
    # Molde sem defeitos: contagens a zero, data nula, flag de manutenção.
    assert body[1]["em_manutencao"] is True
    assert body[1]["defect_qty"] == 0
    assert body[1]["defect_events"] == 0
    assert body[1]["last_defect"] is None


def test_mold_quality_empty_is_explicit_not_500():
    client = TestClient(_app(_session_with_rows([])))
    resp = client.get("/v1/quality/molds", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []
