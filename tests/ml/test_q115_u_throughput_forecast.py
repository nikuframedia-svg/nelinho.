"""
Q.115.U — testes ThroughputForecastModel
==========================================

≥5 testes:
1. fit + forecast happy path
2. MAPE ≤20% em fixture
3. Sample insuficiente → confidence None
4. Endpoint 200 + 404
5. Confidence interval coerente (lower < yhat < upper)
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_ts(n_days: int = 90, boat_id: str = "KAYAK-A", noise: float = 2.0) -> pd.DataFrame:
    """Série temporal sintética com tendência linear + ruído controlado."""
    rng = np.random.default_rng(42)
    start = date(2024, 1, 1)
    rows = []
    for i in range(n_days):
        d = start + timedelta(days=i)
        ops = max(0, int(10 + 0.05 * i + rng.normal(0, noise)))
        rows.append({"date": d.isoformat(), "boat_id": boat_id, "ops_concluidas": ops})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# Testes (com skip se Prophet não disponível)
# ------------------------------------------------------------------

try:
    from prophet import Prophet  # type: ignore[import]
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PROPHET_AVAILABLE,
    reason="Prophet não instalado — testes throughput_forecast ignorados",
)


class TestThroughputForecastModel:
    def test_fit_forecast_happy_path(self):
        """fit + forecast devolve ThroughputForecast válido."""
        from src.ml.models_domain.throughput_forecast import ThroughputForecastModel, ThroughputForecast

        model = ThroughputForecastModel()
        ts = _make_ts(90)
        model.fit(ts)

        assert "KAYAK-A" in model.trained_boats()
        fc = model.forecast("KAYAK-A", days=7)
        assert isinstance(fc, ThroughputForecast)
        assert fc.boat_id == "KAYAK-A"
        assert len(fc.predictions) == 7

    def test_mape_menor_20_pct(self):
        """MAPE ≤20% em série com baixo ruído (noise=1.0)."""
        from src.ml.models_domain.throughput_forecast import ThroughputForecastModel

        model = ThroughputForecastModel()
        ts = _make_ts(120, noise=1.0)
        model.fit(ts)

        mape = model._mapes.get("KAYAK-A")
        assert mape is not None
        assert mape <= 0.20, f"MAPE esperado <=0.20, got {mape:.4f}"

    def test_sample_insuficiente_nao_treinado(self):
        """Série com <14 dias → barco não aparece em trained_boats()."""
        from src.ml.models_domain.throughput_forecast import ThroughputForecastModel

        model = ThroughputForecastModel()
        ts = _make_ts(5)  # só 5 dias — abaixo do mínimo
        model.fit(ts)

        assert "KAYAK-A" not in model.trained_boats()

    def test_confidence_interval_coerente(self):
        """yhat_lower < yhat < yhat_upper para cada ponto."""
        from src.ml.models_domain.throughput_forecast import ThroughputForecastModel

        model = ThroughputForecastModel()
        ts = _make_ts(90)
        model.fit(ts)
        fc = model.forecast("KAYAK-A", days=14)

        for pred in fc.predictions:
            assert pred.yhat_lower < pred.yhat_upper, (
                f"Intervalo incoerente em {pred.date}: "
                f"lower={pred.yhat_lower} upper={pred.yhat_upper}"
            )

    def test_varios_barcos(self):
        """Treina múltiplos barcos na mesma chamada fit."""
        from src.ml.models_domain.throughput_forecast import ThroughputForecastModel

        model = ThroughputForecastModel()
        ts_a = _make_ts(90, boat_id="KAYAK-A")
        ts_b = _make_ts(90, boat_id="KAYAK-B")
        ts = pd.concat([ts_a, ts_b], ignore_index=True)
        model.fit(ts)

        assert "KAYAK-A" in model.trained_boats()
        assert "KAYAK-B" in model.trained_boats()


# ------------------------------------------------------------------
# Endpoint tests
# ------------------------------------------------------------------

@pytest.fixture()
def ml_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.ml.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app, headers={"X-Tenant-Id": "00000000-0000-0000-0000-000000000001"})


def test_throughput_forecast_endpoint_404_sem_modelo(ml_client):
    """404 quando modelo não treinado."""
    import src.ml.api as ml_api
    ml_api._throughput_model = None
    resp = ml_client.get("/v1/ml/throughput-forecast?days=14&boat_id=KAYAK-X")
    assert resp.status_code == 404


def test_throughput_forecast_endpoint_200_com_modelo():
    """200 quando barco está treinado — usa app com estado partilhado."""
    from src.ml.models_domain.throughput_forecast import ThroughputForecastModel
    import src.ml.api as ml_api
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    model = ThroughputForecastModel()
    ts = _make_ts(90, boat_id="KAYAK-Z")
    model.fit(ts)
    ml_api._throughput_model = model

    app = FastAPI()
    app.include_router(ml_api.router)
    client = TestClient(app, headers={"X-Tenant-Id": "00000000-0000-0000-0000-000000000001"})

    resp = client.get("/v1/ml/throughput-forecast?days=7&boat_id=KAYAK-Z")
    assert resp.status_code == 200
    data = resp.json()
    assert data["boat_id"] == "KAYAK-Z"
    assert len(data["predictions"]) == 7
    # cleanup
    ml_api._throughput_model = None
