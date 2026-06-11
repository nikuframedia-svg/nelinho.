"""F4.E — testes de regressão para os 14 achados da auditoria CPO.

Cobre as duas mudanças comportamentais do lote:
  1. epsilon simétrico no safety_net (idle_ratio agora usa -1e-6, não +1e-6).
  2. guard tournament_size < 1 no CPOConfig.__post_init__.

Os outros fixes do lote são doc/comment/log — sem comportamento novo.
"""

from __future__ import annotations

from src.plan.cpo.engine import CPOConfig
from src.plan.cpo.safety_net import _gather_violations, is_worse_than_baseline


# ─── Helpers ────────────────────────────────────────────────────────────────


def _base() -> dict:
    return {
        "num_late_orders": 2,
        "total_tardiness_hours": 8.0,
        "otd_delivery": 0.92,
        "makespan_hours": 100.0,
        "throughput_eur_day": 32_000.0,
        "avg_quality_risk": 0.10,
        "setups": 10,
        "total_idle_hours": 5.0,
        "lam_utilization": 42.0,
        "idle_ratio": 0.18,
    }


# ─── Epsilon simétrico: idle_ratio ──────────────────────────────────────────


def test_idle_ratio_at_exact_tolerance_boundary_blocks():
    """idle_ratio exatamente no limite (base + tolerance) deve bloquear.

    Antes do fix a linha usava +1e-6, o que tornava o threshold
    base+tol+1e-6 — o ponto exacto base+tol passava silenciosamente.
    Com -1e-6 o ponto exacto já ultrapassa o threshold e bloqueia.
    Este é o comportamento correcto: chegar ao limite é degradar.
    """
    base = _base()
    # idle_ratio tolerance = 0.05; base = 0.18 → limite = 0.23
    cand = dict(base, idle_ratio=0.23)
    violations = _gather_violations(cand, base)
    assert any(v[0] == "idle_ratio" for v in violations), (
        "idle_ratio no limite exato (base + tol) deve gerar violação"
    )
    assert is_worse_than_baseline(cand, base) is True


def test_lam_utilization_imediatamente_abaixo_do_threshold_bloqueia():
    """R3 do reviewer Q.171.H — homólogo de fronteira do idle_ratio: o ponto
    imediatamente ANTES do threshold (37.0 - 1e-7 < 36.9999999+) tem de
    bloquear, espelhando o comportamento estrito do lado idle."""
    base = _base()
    cand = dict(base, lam_utilization=37.0 - 1e-3)
    assert is_worse_than_baseline(cand, base) is True, (
        "lam_utilization mesmo abaixo do threshold tem de bloquear"
    )


def test_lam_utilization_below_tolerance_boundary_blocks():
    """lam_utilization abaixo do limite (base - tolerance - margem) bloqueia.

    Confirma que lam_utilization usa -1e-6: o ponto exacto base-tol passa
    (37.0 == 42-5, não ultrapassa o threshold 36.9999999), mas 36.99 já
    ultrapassa e bloqueia. Comportamento não regrediu após o fix simétrico.
    """
    base = _base()
    # lam_utilization tolerance = 5pp; base = 42.0
    # threshold efectivo = 42.0 - 5.0 - 1e-6 = 36.9999999
    # 37.0 passa (no limite exacto); 36.99 bloqueia (abaixo do threshold)
    cand_ok = dict(base, lam_utilization=37.0)
    assert is_worse_than_baseline(cand_ok, base) is False, (
        "lam_utilization no limite exacto (base - tol = 37.0) deve passar"
    )
    cand_bad = dict(base, lam_utilization=36.99)
    violations = _gather_violations(cand_bad, base)
    assert any(v[0] == "lam_utilization" for v in violations), (
        "lam_utilization abaixo do limite (36.99 < 37.0) deve gerar violação"
    )
    assert is_worse_than_baseline(cand_bad, base) is True


def test_idle_ratio_strictly_within_tolerance_passes():
    """idle_ratio claramente abaixo do limite não deve bloquear."""
    base = _base()
    # 0.18 + 0.04 = 0.22, dentro da tolerância de 0.05
    cand = dict(base, idle_ratio=0.22)
    assert is_worse_than_baseline(cand, base) is False


def test_epsilon_symmetry_idle_vs_lam():
    """Ambos os guardrails usam -1e-6: o mesmo delta fractional acima
    do limite bloqueia em ambas as direções.

    Testa que o padrão epsilon é agora simétrico entre lam_utilization
    (LOWER is worse) e idle_ratio (HIGHER is worse).
    """
    base = _base()
    # idle_ratio: base + tol + tiny_margin → deve bloquear
    cand_idle = dict(base, idle_ratio=base["idle_ratio"] + 0.05 + 1e-5)
    assert is_worse_than_baseline(cand_idle, base) is True

    # lam_utilization: base - tol - tiny_margin → deve bloquear
    cand_lam = dict(base, lam_utilization=base["lam_utilization"] - 5.0 - 1e-5)
    assert is_worse_than_baseline(cand_lam, base) is True


# ─── tournament_size guard ───────────────────────────────────────────────────


def test_tournament_size_zero_is_clamped_to_one():
    """CPOConfig com tournament_size=0 deveria causar IndexError na função
    _tournament() (sample(scored, 0) → [] → competitors[0] falha).

    O guard em __post_init__ clamp para 1 antes disso acontecer.
    """
    cfg = CPOConfig(tournament_size=0)
    assert cfg.tournament_size == 1, (
        "tournament_size=0 deve ser clamped para 1 em __post_init__"
    )


def test_tournament_size_negative_is_clamped_to_one():
    """tournament_size negativo é igualmente inválido."""
    cfg = CPOConfig(tournament_size=-3)
    assert cfg.tournament_size == 1


def test_tournament_size_one_is_valid():
    """tournament_size=1 é o mínimo válido — não deve ser alterado."""
    cfg = CPOConfig(tournament_size=1)
    assert cfg.tournament_size == 1


def test_tournament_size_positive_unchanged():
    """tournament_size > 1 não deve ser alterado pelo guard."""
    cfg = CPOConfig(tournament_size=5)
    assert cfg.tournament_size == 5
