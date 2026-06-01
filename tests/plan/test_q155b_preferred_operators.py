"""Q.155.B — testes da API "melhores operadores por fase".

Foco na lógica nova: o shrinkage da afinidade (corrige o flaw de amostras
pequenas saturarem em 1.0) + o entity_id determinístico do audit. O contrato
HTTP completo (GET/PUT + persistência + audit) está verificado ao vivo.
"""
from __future__ import annotations

from src.plan.api.phase_preferred_operators import (
    _SHRINK_K,
    _phase_entity_id,
    _shrink,
)


def test_shrink_amostra_grande_quase_nao_muda():
    """Score com muitas amostras ≈ inalterado (confiamos no histórico)."""
    assert abs(_shrink(0.9, 1000) - 0.9) < 0.02


def test_shrink_amostra_pequena_puxa_para_neutro():
    """5 amostras a 1.0 não pode ficar acima de 600 amostras a 0.8 (o flaw)."""
    poucos = _shrink(1.0, 5)      # satura em 1.0 sem shrinkage
    muitos = _shrink(0.8, 600)
    assert poucos < 1.0           # foi puxado para baixo
    assert muitos > poucos        # o de muito histórico ganha
    # 5 amostras: (1.0*5 + 0.5*20)/(25) = 15/25 = 0.6
    assert abs(poucos - 0.6) < 1e-9


def test_shrink_zero_amostras_e_neutro():
    assert abs(_shrink(0.0, 0) - 0.5) < 1e-9
    assert _SHRINK_K > 0


def test_phase_entity_id_deterministico():
    a = _phase_entity_id("40")
    b = _phase_entity_id("40")
    c = _phase_entity_id("5")
    assert a == b          # mesmo phase → mesmo UUID (audit estável)
    assert a != c          # fases diferentes → UUIDs diferentes
