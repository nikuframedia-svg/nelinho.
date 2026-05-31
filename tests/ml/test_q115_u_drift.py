"""
Q.115.U — testes DriftDetector
================================

≥4 testes:
1. KS-test detecta drift em fixture corrompida
2. PSI > 0.25 → severity=critical
3. AUC delta < -0.05 → critical + Q.17 ALERT emit
4. record_drift_event INSERT linha em ml.drift_event
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from src.ml.observability.drift import DriftDetector, DriftEventResult

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _make_db():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def _normal_df(n: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "feat_a": rng.normal(5.0, 1.0, n),
        "feat_b": rng.normal(10.0, 2.0, n),
    })


def _drifted_df(n: int = 200, shift: float = 5.0, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "feat_a": rng.normal(5.0 + shift, 1.0, n),
        "feat_b": rng.normal(10.0 + shift, 2.0, n),
    })


class TestDriftDetector:
    @pytest.mark.asyncio
    async def test_ks_detecta_drift_fixture_corrompida(self):
        """KS-test deve detectar drift quando distribuições são muito diferentes."""
        db = _make_db()
        detector = DriftDetector("test_model", db, TENANT)

        baseline = _normal_df(300, seed=0)
        current = _drifted_df(300, shift=8.0, seed=1)

        events = await detector.check_drift(current, baseline)

        ks_events = [e for e in events if e.metric == "ks_stat"]
        assert len(ks_events) > 0, "Deve detectar drift KS com shift=8σ"
        severities = [e.severity for e in ks_events]
        assert "critical" in severities or "warn" in severities

    @pytest.mark.asyncio
    async def test_psi_critical_maior_025(self):
        """PSI > 0.25 → severity=critical."""
        db = _make_db()
        detector = DriftDetector("test_model", db, TENANT)

        # Shift muito grande garante PSI > 0.25
        baseline = _normal_df(500, seed=0)
        current = _drifted_df(500, shift=10.0, seed=1)

        events = await detector.check_drift(current, baseline)

        psi_events = [e for e in events if e.metric == "psi" and e.severity == "critical"]
        assert len(psi_events) > 0, (
            f"Esperado PSI critical, got events: {[(e.metric, e.value, e.severity) for e in events]}"
        )

    @pytest.mark.asyncio
    async def test_auc_delta_critical_emite_q17(self):
        """AUC delta < -0.05 → critical + Q.17 ALERT."""
        db = _make_db()
        detector = DriftDetector("quality_risk", db, TENANT)

        # Features sem drift (só testamos o AUC delta path)
        baseline = _normal_df(100, seed=0)
        current = _normal_df(100, seed=2)

        with patch.object(detector, "_emit_q17_alert", new_callable=AsyncMock) as mock_alert:
            events = await detector.check_drift(
                current, baseline,
                baseline_auc=0.85,
                current_auc=0.75,  # delta = -0.10 < -0.05
            )

            auc_events = [e for e in events if e.metric == "auc_delta"]
            assert len(auc_events) == 1
            assert auc_events[0].severity == "critical"
            assert auc_events[0].value == pytest.approx(-0.10, abs=1e-4)

            # Chama record_drift_event para verificar emit Q.17
            await detector.record_drift_event(auc_events[0])
            mock_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_drift_event_insere_em_db(self):
        """record_drift_event deve db.add() + db.flush()."""
        db = _make_db()
        detector = DriftDetector("duration", db, TENANT)

        event = DriftEventResult(
            model_name="duration",
            feature_name="feat_a",
            metric="ks_stat",
            value=0.45,
            threshold=0.30,
            severity="critical",
        )

        with patch.object(detector, "_emit_q17_alert", new_callable=AsyncMock):
            await detector.record_drift_event(event)

        db.add.assert_called_once()
        db.flush.assert_called_once()

        # Verifica que o objecto inserido é um DriftEvent
        from src.ml.models.drift_event import DriftEvent
        added_obj = db.add.call_args[0][0]
        assert isinstance(added_obj, DriftEvent)
        assert added_obj.model_name == "duration"
        assert added_obj.metric == "ks_stat"
        assert added_obj.severity == "critical"

    @pytest.mark.asyncio
    async def test_sem_drift_em_distribuicoes_identicas(self):
        """Distribuições idênticas → sem eventos de drift."""
        db = _make_db()
        detector = DriftDetector("test_model", db, TENANT)

        baseline = _normal_df(500, seed=42)
        current = _normal_df(500, seed=43)  # mesma distribuição, seed diferente

        events = await detector.check_drift(current, baseline)

        # Pode haver alguns eventos marginais, mas não deve haver critical
        critical_ks = [e for e in events if e.metric == "ks_stat" and e.severity == "critical"]
        assert len(critical_ks) == 0, f"Não esperado critical com dist. idênticas: {critical_ks}"
