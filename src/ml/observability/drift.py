"""
ProdPlan ONE — DriftDetector (Q.115.U)
=======================================

KS-test + PSI + AUC delta semanal sobre features e scores dos modelos ML.
Escreve em ml.drift_event (migração 079).
Se severity=critical emite Q.17 action ALERT.

Job semanal: domingo 06:00 UTC.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.ml.models.drift_event import DriftEvent

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Thresholds (configuráveis via system_defaults futuramente)
# ------------------------------------------------------------------

_KS_WARN_P = 0.05
_KS_CRITICAL_P = 0.01
_KS_CRITICAL_STAT = 0.30
_PSI_CRITICAL = 0.25
_AUC_DELTA_CRITICAL = -0.05


class DriftEventResult(BaseModel):
    model_name: str
    feature_name: Optional[str]
    metric: str  # ks_stat | psi | auc_delta | wmape_delta
    value: float
    threshold: float
    severity: str  # warn | critical


class DriftDetector:
    def __init__(self, model_name: str, db: AsyncSession, tenant_id: Optional[UUID] = None) -> None:
        self.model_name = model_name
        self.db = db
        self.tenant_id = tenant_id or UUID(int=0)

    # ------------------------------------------------------------------
    # KS-test por feature
    # ------------------------------------------------------------------

    @staticmethod
    def _ks_test(baseline: pd.Series, current: pd.Series):
        """Scipy KS-test. Retorna (statistic, p_value)."""
        from scipy.stats import ks_2samp  # type: ignore[import]

        base_clean = baseline.dropna().values
        curr_clean = current.dropna().values
        if len(base_clean) < 5 or len(curr_clean) < 5:
            return 0.0, 1.0
        stat, pval = ks_2samp(base_clean, curr_clean)
        return float(stat), float(pval)

    # ------------------------------------------------------------------
    # PSI (Population Stability Index)
    # ------------------------------------------------------------------

    @staticmethod
    def _psi(baseline: pd.Series, current: pd.Series, n_bins: int = 10) -> float:
        """PSI = Σ (actual% - expected%) * ln(actual% / expected%)."""
        base_clean = baseline.dropna().values
        curr_clean = current.dropna().values
        if len(base_clean) < 5 or len(curr_clean) < 5:
            return 0.0

        min_v = min(base_clean.min(), curr_clean.min())
        max_v = max(base_clean.max(), curr_clean.max())
        if min_v == max_v:
            return 0.0

        bins = np.linspace(min_v, max_v, n_bins + 1)
        base_hist, _ = np.histogram(base_clean, bins=bins)
        curr_hist, _ = np.histogram(curr_clean, bins=bins)

        base_pct = (base_hist + 0.5) / (len(base_clean) + 0.5 * n_bins)
        curr_pct = (curr_hist + 0.5) / (len(curr_clean) + 0.5 * n_bins)

        psi = float(np.sum((curr_pct - base_pct) * np.log(curr_pct / base_pct)))
        return round(psi, 6)

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    async def check_drift(
        self,
        current_features: pd.DataFrame,
        baseline_features: pd.DataFrame,
        baseline_auc: Optional[float] = None,
        current_auc: Optional[float] = None,
    ) -> list[DriftEventResult]:
        """
        KS-test por feature numérica.
        PSI por feature numérica.
        AUC delta se modelos de classificação (baseline_auc + current_auc fornecidos).
        """
        events: list[DriftEventResult] = []
        numeric_cols = [
            c for c in baseline_features.columns
            if pd.api.types.is_numeric_dtype(baseline_features[c])
        ]

        for col in numeric_cols:
            base_s = baseline_features[col]
            curr_s = current_features[col] if col in current_features.columns else pd.Series([], dtype=float)

            # KS-test
            stat, pval = self._ks_test(base_s, curr_s)
            if pval < _KS_CRITICAL_P and stat > _KS_CRITICAL_STAT:
                severity = "critical"
            elif pval < _KS_WARN_P:
                severity = "warn"
            else:
                severity = None

            if severity:
                events.append(DriftEventResult(
                    model_name=self.model_name,
                    feature_name=col,
                    metric="ks_stat",
                    value=round(stat, 6),
                    threshold=_KS_CRITICAL_STAT if severity == "critical" else _KS_WARN_P,
                    severity=severity,
                ))

            # PSI
            psi_val = self._psi(base_s, curr_s)
            if psi_val > _PSI_CRITICAL:
                events.append(DriftEventResult(
                    model_name=self.model_name,
                    feature_name=col,
                    metric="psi",
                    value=round(psi_val, 6),
                    threshold=_PSI_CRITICAL,
                    severity="critical",
                ))

        # AUC delta
        if baseline_auc is not None and current_auc is not None:
            delta = current_auc - baseline_auc
            if delta < _AUC_DELTA_CRITICAL:
                events.append(DriftEventResult(
                    model_name=self.model_name,
                    feature_name=None,
                    metric="auc_delta",
                    value=round(delta, 6),
                    threshold=_AUC_DELTA_CRITICAL,
                    severity="critical",
                ))

        return events

    async def record_drift_event(self, event: DriftEventResult) -> None:
        """INSERT em ml.drift_event. Se critical → emite Q.17 ALERT (best-effort)."""
        row = DriftEvent(
            id=uuid4(),
            tenant_id=self.tenant_id,
            model_name=event.model_name,
            feature_name=event.feature_name,
            metric=event.metric,
            value=event.value,
            threshold=event.threshold,
            severity=event.severity,
            detected_at=datetime.now(timezone.utc),
        )
        self.db.add(row)
        # flush mas não commit — responsabilidade do chamador
        await self.db.flush()

        if event.severity == "critical":
            await self._emit_q17_alert(event)

    async def _emit_q17_alert(self, event: DriftEventResult) -> None:
        """Emite alerta Q.17 (best-effort — falha silenciosa para não bloquear detecção)."""
        try:
            from src.governance.service import GovernanceService
            governance = GovernanceService(db=self.db, tenant_id=self.tenant_id)
            await governance.on_event(
                event_type="ML_DRIFT_CRITICAL",
                payload={
                    "model_name": event.model_name,
                    "feature_name": event.feature_name,
                    "metric": event.metric,
                    "value": event.value,
                    "threshold": event.threshold,
                },
                triggered_by="drift_detector",
            )
        except Exception as exc:
            logger.warning(
                "DriftDetector: emissão Q.17 ALERT falhou (ignorado): %s", exc
            )


# ------------------------------------------------------------------
# Job semanal
# ------------------------------------------------------------------

class DriftDetectionJob:
    """Job cron: domingo 06:00 UTC. Corre drift para cada modelo activo."""

    schedule_cron: str = "0 6 * * 0"

    async def run(self, session: AsyncSession, tenant_id: UUID) -> dict:
        """
        Para cada modelo activo no ModelRegistry, compara features da
        última semana com baseline (semana anterior) e regista eventos.
        """
        from src.ml.models.registry import ModelRegistry

        registry = ModelRegistry(session=session, tenant_id=tenant_id)
        try:
            model_names = await registry.list_models()
        except Exception as exc:
            logger.warning("DriftDetectionJob: falha a listar modelos: %s", exc)
            return {"status": "error", "reason": str(exc)}

        total_events = 0
        for model_name in model_names:
            # Q.120.A — scaffold: instanciado para o caminho futuro (feature
            # snapshots persistidos), ainda não usado neste job. `_` evita F841.
            _detector = DriftDetector(
                model_name=model_name, db=session, tenant_id=tenant_id
            )
            # Sem features históricas disponíveis via registry nesta fase —
            # o job é um scaffold para quando os modelos persistirem feature snapshots.
            # Por agora regista apenas se houver artefacto activo.
            active = await registry.get_active(model_name)
            if active is None:
                continue
            logger.info(
                "DriftDetectionJob: modelo '%s' activo v%d — sem feature snapshot disponível",
                model_name,
                active.version,
            )

        logger.info(
            "DriftDetectionJob: tenant=%s, modelos=%d, eventos=%d",
            tenant_id,
            len(model_names),
            total_events,
        )
        return {"status": "ok", "models_checked": len(model_names), "events": total_events}
