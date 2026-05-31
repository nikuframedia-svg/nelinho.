"""Q.133.A2 — median_duration_h prefere o p50 CALIBRADO (loop de aprendizagem).

Degrau (não blend): n_obs>=_CALIBRATION_MIN_OBS → p50 calibrado; senão cai no
caminho actual (of_fp pair → by_fase → buffer 2x). Vazio = back-compat total.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.plan.cpo.state import _CALIBRATION_MIN_OBS, FactoryState


def _state():
    return FactoryState(tenant_id=uuid4())


def test_prefers_calibrated_when_enough_obs():
    s = _state()
    s.calibrated_durations = {("1", "20155"): (4.0, _CALIBRATION_MIN_OBS + 7)}
    s.historical_durations = {("1", "20155"): 9.9}  # of_fp cru — deve ser ignorado
    assert s.median_duration_h("1", "20155", 99.0) == pytest.approx(4.0)


def test_falls_to_historical_when_too_few_obs():
    s = _state()
    s.calibrated_durations = {("1", "20155"): (4.0, _CALIBRATION_MIN_OBS - 1)}
    s.historical_durations = {("1", "20155"): 9.9}
    # poucas obs → não confia na calibração; usa a mediana per-pair actual
    assert s.median_duration_h("1", "20155", 99.0) == pytest.approx(9.9)


def test_calibrated_zero_p50_is_ignored():
    s = _state()
    s.calibrated_durations = {("1", "x"): (0.0, 50)}  # p50=0 → ignora
    s.historical_durations = {("1", "x"): 5.0}
    assert s.median_duration_h("1", "x", 99.0) == pytest.approx(5.0)


def test_empty_calibration_is_backcompat_pair_and_fase():
    s = _state()  # sem calibração
    s.historical_durations = {("1", "20155"): 9.9}
    assert s.median_duration_h("1", "20155", 99.0) == pytest.approx(9.9)
    # 2º tier: mediana por fase (modelo desconhecido) — REAL, não buffer
    s.historical_durations_by_fase = {"2": 3.18}
    assert s.median_duration_h("2", "modelo_novo", 99.0) == pytest.approx(3.18)


def test_empty_everything_falls_to_buffer(monkeypatch):
    monkeypatch.delenv("PRODPLAN_PLAN_STD_DURATION_BUFFER", raising=False)
    s = _state()  # tudo vazio → buffer 2x sintético (comportamento legado)
    assert s.median_duration_h("999", "999", 5.0) == pytest.approx(10.0)
