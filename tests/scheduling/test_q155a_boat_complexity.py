"""Q.155.A — testes do índice de complexidade do barco (ICB).

Cobre a lógica pura (sem DB): ranker percentil + combinação dos 3 sinais com o
fix prepreg. O job em si é um UPSERT idempotente sobre o mirror (verificado live).
"""
from __future__ import annotations

from src.scheduling.jobs.boat_complexity_job import (
    _W_PAINT,
    _icb_score,
    _pctile_ranker,
)


# ─── ranker percentil ────────────────────────────────────────────────────────

def test_pctile_ranker_distribuicao_conhecida():
    rank = _pctile_ranker([10.0, 20.0, 30.0, 40.0, 50.0])
    assert rank(10.0) == 0.2   # 1/5 ≤ 10
    assert rank(30.0) == 0.6   # 3/5 ≤ 30
    assert rank(50.0) == 1.0   # todos ≤ 50
    assert rank(5.0) == 0.0    # nenhum ≤ 5


def test_pctile_ranker_vazio_e_neutro():
    """Sem população de referência → 0.5 neutro (não inventa extremos)."""
    rank = _pctile_ranker([])
    assert rank(123.0) == 0.5


# ─── combinação ICB ──────────────────────────────────────────────────────────

def test_icb_pesos_40_30_30():
    # peças=1.0, tinta=0.5, fases=0.0 → 0.40·1 + 0.30·0.5 + 0.30·0 = 0.55
    score = _icb_score(1.0, 0.5, 0.0, is_prepreg=False)
    assert abs(score - 0.55) < 1e-9


def test_icb_score_clamp_0_1():
    assert _icb_score(1.0, 1.0, 1.0, is_prepreg=False) == 1.0
    assert _icb_score(0.0, 0.0, 0.0, is_prepreg=False) == 0.0


def test_icb_prepreg_ignora_tinta():
    """Barco prepreg tem tinta≈0 estrutural — não pode ser penalizado por isso.

    Mesmo barco (peças=0.8, fases=0.8) com tinta=0: o prepreg fica MAIS alto que
    o cálculo normal (que somava 0.30·0 da tinta)."""
    comp, phases = 0.8, 0.8
    normal = _icb_score(comp, 0.0, phases, is_prepreg=False)   # 0.40·0.8+0+0.30·0.8 = 0.56
    prepreg = _icb_score(comp, 0.0, phases, is_prepreg=True)   # 0.55·0.8+0.45·0.8 = 0.80
    assert prepreg > normal
    assert abs(prepreg - 0.80) < 1e-9
    # sanity: a tinta tem peso real no caminho normal
    assert _W_PAINT > 0
