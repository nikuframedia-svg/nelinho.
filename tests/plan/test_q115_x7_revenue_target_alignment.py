"""Q.115.X7 — CPO fitness: revenue_target_alignment component.

Testa que o scheduler distribui planeamento conforme o objetivo de faturação
diária configurado em `core.daily_revenue_target`.

Invariantes testados:
  1. Sem target → score neutro 1.0 (não penaliza)
  2. Target=4000 exato → score 1.0
  3. Target=4000, produz 2000 (50% under) → score 0.0
  4. Target=4000, produz 8000 (100% over) → score 0.0
  5. Target=4000, mix [3500, 4500, 4000] → score >0.7
  6. Re-balance: soma v2 weights = 1.0
  7. Fitness com revenue_target_alignment weight=0 → comportamento inalterado
  8. Safety_net flag revenue_alignment quando desvio >50%
  9. CPOScheduleResponse tem campo revenue_alignment_pct (Optional[float])
  10. Property: score ∈ [0, 1] para qualquer schedule + target
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from src.plan.cpo.fitness import FitnessConfig, _revenue_target_alignment, compute_fitness


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _schedule_with_throughput_by_day(daily_values: dict) -> dict:
    """Cria um schedule mínimo com throughput_by_day preenchido."""
    return {
        "makespan_hours": 24.0,
        "total_tardiness_hours": 0.0,
        "setups": 0,
        "quality_risk": 0.0,
        "throughput_eur_day": sum(daily_values.values()) / max(len(daily_values), 1),
        "throughput_by_day": daily_values,
        "safety_violated": False,
    }


# ─────────────────────────────────────────────────────────────────────────
# Testes unitários
# ─────────────────────────────────────────────────────────────────────────

def test_x7_sem_target_score_neutro():
    """Teste 1 — sem target configurado → score 1.0 (neutro, não penaliza)."""
    cfg = FitnessConfig(daily_revenue_target_eur=None)
    schedule = _schedule_with_throughput_by_day({"2026-06-01": 4000.0})
    score = _revenue_target_alignment(schedule, cfg)
    assert score == 1.0


def test_x7_target_exacto_score_maximo():
    """Teste 2 — produz exactamente o target → score 1.0."""
    cfg = FitnessConfig(daily_revenue_target_eur=4000.0)
    schedule = _schedule_with_throughput_by_day({
        "2026-06-01": 4000.0,
        "2026-06-02": 4000.0,
    })
    score = _revenue_target_alignment(schedule, cfg)
    assert score == pytest.approx(1.0, abs=1e-6)


def test_x7_50pct_under_score_zero():
    """Teste 3 — 50% abaixo do target → score 0.0."""
    cfg = FitnessConfig(daily_revenue_target_eur=4000.0)
    # avg_dev_pct = |2000-4000|/4000 = 0.5 → score = max(0, 1 - 2*0.5) = 0
    schedule = _schedule_with_throughput_by_day({"2026-06-01": 2000.0})
    score = _revenue_target_alignment(schedule, cfg)
    assert score == pytest.approx(0.0, abs=1e-6)


def test_x7_100pct_over_score_zero():
    """Teste 4 — 100% acima do target → score 0.0."""
    cfg = FitnessConfig(daily_revenue_target_eur=4000.0)
    # avg_dev_pct = |8000-4000|/4000 = 1.0 → score = max(0, 1 - 2*1.0) = 0
    schedule = _schedule_with_throughput_by_day({"2026-06-01": 8000.0})
    score = _revenue_target_alignment(schedule, cfg)
    assert score == pytest.approx(0.0, abs=1e-6)


def test_x7_mix_proximo_target_score_alto():
    """Teste 5 — mix próximo do target → score >0.7."""
    cfg = FitnessConfig(daily_revenue_target_eur=4000.0)
    # desvios: |3500-4000|/4000=0.125, |4500-4000|/4000=0.125, |4000-4000|/4000=0
    # avg_dev_pct = (0.125 + 0.125 + 0.0) / 3 = 0.0833
    # score = 1 - 2*0.0833 = 0.833
    schedule = _schedule_with_throughput_by_day({
        "2026-06-01": 3500.0,
        "2026-06-02": 4500.0,
        "2026-06-03": 4000.0,
    })
    score = _revenue_target_alignment(schedule, cfg)
    assert score > 0.7


def test_x7_v2_weights_somam_um():
    """Teste 6 — re-balance: pesos v2 somam 1.0."""
    cfg = FitnessConfig()
    total = (
        cfg.w_v2_makespan
        + cfg.w_v2_tardiness_transport
        + cfg.w_v2_idle_operators
        + cfg.w_v2_setup_time
        + cfg.w_v2_quality_risk
        + cfg.w_v2_throughput_eur_day
        + cfg.w_v2_revenue_target_alignment
    )
    assert total == pytest.approx(1.0, abs=1e-9), (
        f"Pesos v2 somam {total:.6f} (esperado 1.0). "
        "Q.115.X7: throughput=0.10 + revenue_target=0.10 (split de 0.15)"
    )


def test_x7_weight_zero_comportamento_inalterado():
    """Teste 7 — weight=0 → resultado idêntico ao anterior (regressão)."""
    schedule_a = {
        "makespan_hours": 100.0,
        "total_tardiness_hours": 5.0,
        "setups": 10,
        "quality_risk": 0.1,
        "throughput_eur_day": 3000.0,
        "safety_violated": False,
    }
    # Sem novo componente (weight=0)
    cfg_sem = FitnessConfig(use_v2_weights=True, w_v2_revenue_target_alignment=0.0)
    # Com novo componente mas mesmo schedule → deve mudar apenas quando target existe
    cfg_com_sem_target = FitnessConfig(
        use_v2_weights=True,
        w_v2_revenue_target_alignment=0.0,
        daily_revenue_target_eur=None,
    )
    fit_sem = compute_fitness(schedule_a, cfg_sem)
    fit_com = compute_fitness(schedule_a, cfg_com_sem_target)
    assert fit_sem == pytest.approx(fit_com, abs=1e-9)


# Q.171.D — testes 8/9 removidos com a função `check_revenue_alignment_warning`:
# era dead code (zero callsites em produção desde Q.115.X7; só estes testes a
# invocavam). O alinhamento ao target vive na fitness (testes acima) e o
# enforcement € fica fora do CPO (CoeficienteX é dinheiro — invariante #5).


def test_x7_cpo_schedule_response_tem_campo():
    """Teste 9 — CPOScheduleResponse tem campo revenue_alignment_pct Optional[float]."""
    from src.plan.api.cpo_routers.schedule import CPOScheduleResponse

    fields = CPOScheduleResponse.model_fields
    assert "revenue_alignment_pct" in fields, (
        "CPOScheduleResponse deve ter campo revenue_alignment_pct"
    )
    # Deve aceitar None (Optional)
    obj = CPOScheduleResponse(
        tenant_id="t",
        engine_used="cpo_v4",
        status="ok",
        solve_time_sec=1.0,
        makespan_hours=0.0,
        total_tardiness_hours=0.0,
        num_late_orders=0,
        setups=0,
        avg_utilization=0.0,
    )
    assert obj.revenue_alignment_pct is None, "revenue_alignment_pct deve ter default None"


# ─────────────────────────────────────────────────────────────────────────
# Property test — score ∈ [0, 1]
# ─────────────────────────────────────────────────────────────────────────

@given(
    daily_values=st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.floats(min_value=0.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=10,
    ),
    target=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_x7_property_score_entre_zero_e_um(daily_values, target):
    """Property: para qualquer schedule + target positivo, score ∈ [0, 1]."""
    cfg = FitnessConfig(daily_revenue_target_eur=target)
    schedule = _schedule_with_throughput_by_day(daily_values)
    score = _revenue_target_alignment(schedule, cfg)
    assert 0.0 <= score <= 1.0, f"score={score} fora de [0,1] para target={target}, days={daily_values}"
