"""
ProdPlan ONE — DurationModel (Sprint H.2)
==========================================

Predicts real phase duration (hours) per (modelo_id, fase_id) using
Gradient Boosting. Replaces the NELO `horas_standard` coefficients that
diverge from reality by up to 25x.

Consumed by `RoutingResolver` (Sprint E) when the active model is newer
than the in-memory median aggregates. RetrainJob schedule: daily at
02:30 UTC.
"""

from __future__ import annotations

import logging

from src.shared.coerce import safe_float as _safe_float
from dataclasses import dataclass, field
from statistics import median
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from uuid import UUID

# Q.59.F.3 — numpy/sklearn movidos para dentro de `train()`. Estavam
# top-level e custavam ~500 ms no arranque (sklearn é pesado). Com PEP
# 563 (from __future__ import annotations, em vigor neste ficheiro) as
# anotações são strings, por isso `Optional[GradientBoostingRegressor]`
# resolve-se em tempo de check, não em tempo de import.
if TYPE_CHECKING:
    from sklearn.ensemble import GradientBoostingRegressor

from src.ml.jobs.base import RetrainJob
from src.ml.models_domain._common import encode_categoricals, wmape

logger = logging.getLogger(__name__)


CATEGORICAL_COLS = ("modelo_id", "fase_id")
# Q.115.V — plan_error_prior adicionado: erro médio histórico plano/real
# para (modelo_id, fase_id). Default 0 quando histórico vazio.
NUMERIC_COLS = ("team_size", "mold_pocket_count", "is_rework", "queue_depth", "plan_error_prior")


@dataclass
class DurationModel:
    """
    Wraps a `GradientBoostingRegressor` with a stable feature schema.

    Persistence is via `joblib` (through `ModelRegistry`) — the whole
    dataclass pickles cleanly.
    """

    regressor: Optional[GradientBoostingRegressor] = None
    vocabulary: Dict[str, List[str]] = field(default_factory=dict)
    p90_residual: float = 0.0  # empirical residual used to synthesize p90
    n_samples_trained: int = 0

    def train(
        self,
        rows: List[Dict[str, Any]],
        *,
        random_state: int = 42,
    ) -> Dict[str, Any]:
        """
        Train on a list of feature dicts with key `horas_reais` as the target.

        Returns a metrics dict suitable for `MLModelArtifact.metrics`.
        """
        if not rows:
            raise ValueError("DurationModel.train called with empty rows")

        # Q.59.F.3 — imports diferidos para fora do startup.
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import train_test_split

        targets = np.asarray([float(r.get("horas_reais", 0.0) or 0.0) for r in rows])
        valid_mask = targets > 0
        if valid_mask.sum() < 10:
            raise ValueError(
                f"DurationModel needs >=10 rows with positive horas_reais; "
                f"got {int(valid_mask.sum())}"
            )

        filtered = [r for r, ok in zip(rows, valid_mask) if ok]
        y = targets[valid_mask]

        # FASE 3.3 (HIGH-44) — temporal split when a timestamp is
        # available on every row. The previous random `train_test_split`
        # leaked future rows into training: in production durations
        # drift (new molds, new operators), and a model validated on
        # interleaved past+future rows over-estimated its WMAPE.
        # Now we sort by timestamp and hold out the most recent 20%.
        # Falls back to random split when timestamps are missing or the
        # sample is too small to slice.
        timestamps = [r.get("timestamp") for r in filtered]
        has_temporal = (
            len(filtered) >= 20
            and all(t is not None for t in timestamps)
        )

        if has_temporal:
            order_idx = sorted(
                range(len(filtered)),
                key=lambda i: timestamps[i],
            )
            split_at = round(len(order_idx) * 0.8)
            train_idx = order_idx[:split_at]
            val_idx = order_idx[split_at:]
            filtered = [filtered[i] for i in train_idx + val_idx]
            y = np.concatenate([y[train_idx], y[val_idx]])

            X, vocab = encode_categoricals(filtered, CATEGORICAL_COLS, NUMERIC_COLS)
            self.vocabulary = vocab
            self.n_samples_trained = len(filtered)

            X_train = X[: len(train_idx)]
            X_val = X[len(train_idx):]
            y_train = y[: len(train_idx)]
            y_val = y[len(train_idx):]
        else:
            X, vocab = encode_categoricals(filtered, CATEGORICAL_COLS, NUMERIC_COLS)
            self.vocabulary = vocab
            self.n_samples_trained = len(filtered)

            if len(filtered) >= 20:
                X_train, X_val, y_train, y_val = train_test_split(
                    X, y, test_size=0.2, random_state=random_state
                )
            else:
                X_train, X_val = X, X
                y_train, y_val = y, y

        # FASE 4.3 — hyperparams from MLConfig (env-overridable). Falls
        # back to the same legacy values (100/4/0.08) when the env var
        # is unset, so behaviour is unchanged out of the box.
        from src.ml.config import get_config
        hp = get_config().hyperparams_for("duration")
        model = GradientBoostingRegressor(
            n_estimators=int(hp.get("n_estimators", 100)),
            max_depth=int(hp.get("max_depth", 4)),
            learning_rate=float(hp.get("learning_rate", 0.08)),
            random_state=random_state,
        )
        model.fit(X_train, y_train)
        self.regressor = model

        y_pred = model.predict(X_val)
        residuals = y_val - y_pred
        self.p90_residual = float(np.percentile(np.abs(residuals), 90))

        metrics = {
            "wmape": round(wmape(y_val, y_pred), 4),
            "mae_hours": round(float(np.mean(np.abs(residuals))), 3),
            "p90_residual_hours": round(self.p90_residual, 3),
            "samples": len(filtered),
            "samples_train": len(X_train),
            "samples_val": len(X_val),
        }
        logger.info(
            f"DurationModel trained: WMAPE={metrics['wmape']}, "
            f"samples={metrics['samples']}"
        )
        return metrics

    def predict(self, row: Dict[str, Any]) -> Dict[str, float]:
        """
        Return point estimate + p90 (worst-case) for planning.

        {
          "p50_hours": 7.4,   # median prediction
          "p90_hours": 9.1,   # p50 + p90 residual
        }
        """
        if self.regressor is None:
            raise RuntimeError("DurationModel.predict called before train()")
        X, _ = encode_categoricals(
            [row],
            CATEGORICAL_COLS,
            NUMERIC_COLS,
            vocabulary=self.vocabulary,
        )
        p50 = float(max(0.0, self.regressor.predict(X)[0]))
        return {
            "p50_hours": round(p50, 3),
            "p90_hours": round(p50 + self.p90_residual, 3),
        }

    def predict_batch(self, rows: List[Dict[str, Any]]) -> List[Dict[str, float]]:
        if not rows or self.regressor is None:
            return []
        X, _ = encode_categoricals(
            rows, CATEGORICAL_COLS, NUMERIC_COLS, vocabulary=self.vocabulary
        )
        preds = self.regressor.predict(X)
        return [
            {
                "p50_hours": round(float(max(0.0, p)), 3),
                "p90_hours": round(float(max(0.0, p)) + self.p90_residual, 3),
            }
            for p in preds
        ]


# ---------------------------------------------------------------------------
# Q.115.V — carrega plan_error_priors sincronamente (síncrono: chamado
# dentro do RetrainJob que já corre num thread do scheduler).
# ---------------------------------------------------------------------------


def _load_plan_error_priors(tenant_id: UUID) -> Dict[str, float]:
    """Lê deltas médios de plan.plan_execution_observed (síncrono).

    Devolve dict {"{modelo_id}::{phase_id}": avg_delta_min}.
    Fallback {} quando a tabela está vazia ou ocorre erro.
    """
    try:
        import asyncio

        async def _query() -> Dict[str, float]:
            from sqlalchemy import func, select

            from src.plan.models.execution_learning import PlanExecutionObserved
            from src.shared.database import get_session_context

            async with get_session_context() as session:
                stmt = (
                    select(
                        PlanExecutionObserved.modelo,
                        PlanExecutionObserved.phase_id,
                        func.avg(
                            PlanExecutionObserved.observed_duration_min
                            - PlanExecutionObserved.planned_duration_min
                        ).label("avg_delta"),
                    )
                    .where(
                        PlanExecutionObserved.tenant_id == tenant_id,
                        PlanExecutionObserved.observed_duration_min.isnot(None),
                        PlanExecutionObserved.planned_duration_min > 0,
                    )
                    .group_by(
                        PlanExecutionObserved.modelo,
                        PlanExecutionObserved.phase_id,
                    )
                )
                result = await session.execute(stmt)
                rows = result.all()
                return {
                    f"{r.modelo or ''}::{r.phase_id!s}": float(r.avg_delta or 0.0)
                    for r in rows
                    if r.avg_delta is not None
                }

        # Tenta reutilizar o event loop se já existe
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Estamos dentro de um contexto async — usa nest_asyncio ou devolve {}
                # (seguro: o retreino pode correr sem prior se não houver loop disponível)
                return {}
            return loop.run_until_complete(_query())
        except RuntimeError:
            return asyncio.run(_query())

    except Exception as exc:
        logger.warning(
            "_load_plan_error_priors tenant=%s falhou (fallback=0): %s", tenant_id, exc
        )
        return {}


# ---------------------------------------------------------------------------
# RetrainJob
# ---------------------------------------------------------------------------

class DurationRetrainJob(RetrainJob):
    model_name = "duration"
    schedule_cron = "30 2 * * *"  # daily 02:30 UTC

    def __init__(self, semantic_queries: Any = None):
        self.semantic_queries = semantic_queries

    def extract_features(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """
        Pull (fase, modelo, worker-team, mold, duration) rows from the
        curated layer. Empty list if the active ingestion isn't available.

        Q.115.V — inclui plan_error_prior (delta médio histórico plano/real
        por fase×modelo). Fallback 0.0 quando não há dados de plan_execution_observed.
        """
        priors = _load_plan_error_priors(tenant_id)
        rows = build_training_dataset(self.semantic_queries, plan_error_priors=priors)
        logger.info(f"DurationRetrainJob extracted {len(rows)} rows")
        return rows

    def train(self, features: List[Dict[str, Any]]) -> Tuple[DurationModel, int]:
        model = DurationModel()
        metrics = model.train(features)
        return model, int(metrics["samples"])

    def validate(
        self,
        model: DurationModel,
        features: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Re-use the WMAPE computed during train() — it's already a held-out
        score. We also run a quick sanity-check on a random subset.
        """
        if not features:
            return {}
        subset = features[:50]
        preds = model.predict_batch(subset)
        actuals = [float(r.get("horas_reais", 0.0)) for r in subset]
        predicted = [p["p50_hours"] for p in preds]
        return {
            "wmape": round(wmape(actuals, predicted), 4),
            "samples_checked": len(subset),
            "p90_residual_hours": round(model.p90_residual, 3),
        }

    def should_promote(
        self,
        new_metrics: Dict[str, Any],
        baseline_metrics: Optional[Dict[str, Any]],
    ) -> bool:
        # Promote only if WMAPE strictly improved OR we have no baseline yet.
        new_wmape = _safe_float(new_metrics.get("wmape"))
        if new_wmape is None:
            return False
        if not baseline_metrics:
            return True
        old_wmape = _safe_float(baseline_metrics.get("wmape"))
        return old_wmape is None or new_wmape < old_wmape


# ---------------------------------------------------------------------------
# Training dataset builder — independent so Sprint F surrogate can reuse
# ---------------------------------------------------------------------------

def _get_plan_error_priors(
    modelo_id: str,
    fase_id: str,
    priors: Optional[Dict[str, float]],
) -> float:
    """Devolve erro médio histórico plano/real para (modelo_id, fase_id).

    Q.115.V — feature `plan_error_prior` para o DurationModel.
    Chave do dict: f"{modelo_id}::{fase_id}".
    Fallback 0.0 quando histórico vazio ou sem dados para esta combinação.
    """
    if not priors:
        return 0.0
    return priors.get(f"{modelo_id}::{fase_id}", 0.0)


def build_training_dataset(
    semantic_queries: Any,
    plan_error_priors: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Assemble rows of shape {modelo_id, fase_id, team_size, mold_pocket_count,
    is_rework, queue_depth, horas_reais} from the curated layer.

    The extraction is best-effort: missing joins produce zeros/defaults, not
    exceptions.

    Returns ``[]`` when curated data has no usable phase rows; the caller
    (`RetrainJob.run`) detects empty datasets and surfaces them via
    ``EmptyDatasetError`` so silent training-on-nothing is no longer
    possible. We log a WARN here too so the failure mode shows up in
    operator logs even when this helper is invoked outside the job
    lifecycle.
    """
    if semantic_queries is None:
        logger.warning(
            "build_training_dataset: semantic_queries is None — returning empty "
            "dataset; caller should treat this as EmptyDatasetError."
        )
        return []
    engine = getattr(semantic_queries, "engine", None)
    if engine is None:
        logger.warning(
            "build_training_dataset: semantic engine missing — returning empty "
            "dataset; caller should treat this as EmptyDatasetError."
        )
        return []

    active_id = getattr(engine, "_active_ingestion_id", None)
    curated = getattr(engine, "_curated_data", {}) or {}
    scope = curated.get(active_id, {}) if active_id else {}

    phases = scope.get("order_phases") or scope.get("CuratedOrderPhase") or []
    orders = scope.get("orders") or scope.get("CuratedOrder") or []
    quality = scope.get("quality_events") or scope.get("CuratedQualityEvent") or []
    molds = scope.get("molds") or scope.get("CuratedMold") or []

    order_model = {
        str(getattr(o, "of_id", "")): str(getattr(o, "modelo_id", ""))
        for o in orders
        if getattr(o, "of_id", None) is not None
    }
    mold_pockets = {
        str(getattr(m, "molde_id", "")): int(getattr(m, "pocket_count", 1) or 1)
        for m in molds
    }
    rework_keys = {
        (str(getattr(e, "of_id", "")), str(getattr(e, "fase_id", "")))
        for e in quality
    }

    # queue_depth proxy: count of phases per fase_id in the dataset
    queue_depth: Dict[str, int] = {}
    for p in phases:
        fid = str(getattr(p, "fase_id", ""))
        queue_depth[fid] = queue_depth.get(fid, 0) + 1

    rows: List[Dict[str, Any]] = []
    for p in phases:
        horas = getattr(p, "horas_reais", None) or getattr(p, "horas_finais", None)
        if not horas or float(horas) <= 0:
            continue
        of_id = str(getattr(p, "of_id", ""))
        fase_id = str(getattr(p, "fase_id", ""))
        modelo_id = order_model.get(of_id, "")
        mold_id = str(getattr(p, "molde_id", "") or "")

        # FASE 3.3 (HIGH-44) — surface a sortable timestamp so the model
        # can do a temporal train/val split. Falls back through
        # data_fim_real → data_inicio_real → None; rows without any
        # timestamp keep the legacy random split path.
        ts = (
            getattr(p, "data_fim_real", None)
            or getattr(p, "data_inicio_real", None)
            or getattr(p, "created_at", None)
        )

        rows.append({
            "modelo_id": modelo_id,
            "fase_id": fase_id,
            "team_size": int(getattr(p, "team_size", 1) or 1),
            "mold_pocket_count": mold_pockets.get(mold_id, 1),
            "is_rework": 1 if (of_id, fase_id) in rework_keys else 0,
            "queue_depth": queue_depth.get(fase_id, 0),
            # Q.115.V — erro médio plano/real histórico; fallback 0.0
            "plan_error_prior": _get_plan_error_priors(
                modelo_id, fase_id, plan_error_priors
            ),
            "horas_reais": float(horas),
            "timestamp": ts,
        })

    return rows
