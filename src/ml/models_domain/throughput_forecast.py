"""
ProdPlan ONE — ThroughputForecastModel (Q.115.U)
=================================================

Forecast de throughput diário por barco usando Prophet.
Reutiliza o padrão de src/supply/forecaster.py.

Lê plan.fases_of_history agregado por (boat_id, day).

Schedule: terça/sexta 05:00 UTC.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_MIN_ROWS = 14  # mínimo de dias para treinar Prophet

try:
    from prophet import Prophet  # type: ignore[import]

    _PROPHET_AVAILABLE = True
except ImportError:
    _PROPHET_AVAILABLE = False
    logger.warning("Prophet não disponível — ThroughputForecastModel degradado")


class ThroughputDay(BaseModel):
    date: str  # ISO date YYYY-MM-DD
    yhat: float
    yhat_lower: float
    yhat_upper: float


class ThroughputForecast(BaseModel):
    model_config = {"protected_namespaces": ()}

    boat_id: str
    horizon_days: int
    predictions: list[ThroughputDay]
    mape: Optional[float] = None  # None se amostra insuficiente


class ThroughputForecastModel:
    """
    Treina um modelo Prophet por barco e produz forecasts N dias adiante.
    """

    def __init__(self) -> None:
        self._models: dict[str, object] = {}  # boat_id → Prophet instance
        self._mapes: dict[str, Optional[float]] = {}
        self._trained_boats: set[str] = set()

    # ------------------------------------------------------------------
    # Treino
    # ------------------------------------------------------------------

    def fit(self, ts: pd.DataFrame) -> None:
        """
        ts: colunas [date (str/date), boat_id (str), ops_concluidas (int)]
        Treina um modelo por barco com split temporal 80/20 para MAPE.
        """
        if ts.empty:
            raise ValueError("ThroughputForecastModel.fit: DataFrame vazio")

        required = {"date", "boat_id", "ops_concluidas"}
        missing = required - set(ts.columns)
        if missing:
            raise ValueError(f"Colunas em falta: {missing}")

        if not _PROPHET_AVAILABLE:
            raise RuntimeError("Prophet não instalado — impossível treinar")

        ts = ts.copy()
        ts["date"] = pd.to_datetime(ts["date"])

        for boat_id, grp in ts.groupby("boat_id"):
            boat_str = str(boat_id)
            df = grp[["date", "ops_concluidas"]].rename(
                columns={"date": "ds", "ops_concluidas": "y"}
            ).sort_values("ds")

            if len(df) < _MIN_ROWS:
                logger.info(
                    "ThroughputForecast: barco %s tem apenas %d pontos — skip",
                    boat_str, len(df),
                )
                continue

            # Split temporal 80/20
            split = int(len(df) * 0.8)
            train_df = df.iloc[:split]
            val_df = df.iloc[split:]

            model = Prophet(
                weekly_seasonality=True,
                yearly_seasonality=False,
                daily_seasonality=False,
                interval_width=0.80,
            )
            model.fit(train_df)
            self._models[boat_str] = model

            mape: Optional[float] = None
            if len(val_df) >= 2:
                future = model.make_future_dataframe(
                    periods=len(val_df), freq="D", include_history=False
                )
                # Usa as datas reais de validação
                future["ds"] = val_df["ds"].values
                fc = model.predict(future)
                y_true = val_df["y"].values
                y_pred = fc["yhat"].values
                denom = abs(y_true).sum()
                if denom > 0:
                    mape = float(abs(y_true - y_pred).sum() / denom)

            self._mapes[boat_str] = mape
            self._trained_boats.add(boat_str)
            logger.info(
                "ThroughputForecast: barco %s treinado, mape=%.3f, n=%d",
                boat_str,
                mape if mape is not None else float("nan"),
                len(df),
            )

    # ------------------------------------------------------------------
    # Inferência
    # ------------------------------------------------------------------

    def forecast(self, boat_id: str, days: int = 14) -> ThroughputForecast:
        """Devolve forecast N dias adiante para o barco dado."""
        boat_str = str(boat_id)
        if boat_str not in self._models:
            raise KeyError(f"Barco '{boat_str}' não treinado ou sem dados suficientes")

        model = self._models[boat_str]
        future = model.make_future_dataframe(periods=days, freq="D", include_history=False)
        fc = model.predict(future)

        predictions = [
            ThroughputDay(
                date=row["ds"].strftime("%Y-%m-%d"),
                yhat=round(float(row["yhat"]), 2),
                yhat_lower=round(float(row["yhat_lower"]), 2),
                yhat_upper=round(float(row["yhat_upper"]), 2),
            )
            for _, row in fc.iterrows()
        ]

        return ThroughputForecast(
            boat_id=boat_str,
            horizon_days=days,
            predictions=predictions,
            mape=self._mapes.get(boat_str),
        )

    def trained_boats(self) -> list[str]:
        return list(self._trained_boats)


# ------------------------------------------------------------------
# Job de retreino
# ------------------------------------------------------------------

class ThroughputForecastRetrainJob:
    """Job cron: terça e sexta 05:00 UTC."""

    schedule_cron: str = "0 5 * * 2,5"
    model_name: str = "throughput_forecast"

    async def run(
        self,
        session,
        tenant_id,
        governance_service=None,
        proposed_by: str = "scheduler",
    ) -> dict:
        from src.ml.models_domain.training_data import load_throughput_ts

        try:
            ts_df = await load_throughput_ts(session, tenant_id)
        except Exception as exc:
            logger.warning("ThroughputForecast: falha a carregar dados: %s", exc)
            return {"status": "skipped", "reason": str(exc)}

        if ts_df.empty:
            return {"status": "skipped", "reason": "sem dados de throughput"}

        model = ThroughputForecastModel()
        try:
            model.fit(ts_df)
        except (ValueError, RuntimeError) as exc:
            return {"status": "skipped", "reason": str(exc)}

        n_boats = len(model.trained_boats())
        avg_mape = None
        mapes = [v for v in model._mapes.values() if v is not None]
        if mapes:
            avg_mape = round(sum(mapes) / len(mapes), 4)

        logger.info(
            "ThroughputForecast retreino: %d barcos, avg_mape=%.3f",
            n_boats,
            avg_mape if avg_mape is not None else float("nan"),
        )
        return {
            "status": "ok",
            "metrics": {"n_boats": n_boats, "avg_mape": avg_mape},
            "training_samples": len(ts_df),
        }
