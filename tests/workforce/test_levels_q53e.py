"""Sprint Q.53.E — escala de níveis invertida + grupos de área.

A auditoria pediu duas coisas ao módulo workforce:

1. **Inverter a escala**: até Q.18 o nível ia de 1 (melhor) a 3 (pior).
   O Luis quer 3=melhor, 1=pior, com meios-níveis (1.0/1.5/2.0/2.5/3.0)
   e atribuído por grupo de área (~7 grupos), não por fase.
2. **Compatibilidade CPO**: a representação interna 1=melhor não pode
   partir. `cpo_internal_level()` mapeia no limite.

DAMP > DRY — cada teste lê como spec independente.
"""

from __future__ import annotations

import pytest

from src.workforce.levels import (
    AREA_GROUPS,
    LEVEL_MEANING,
    LEVEL_MAX,
    LEVEL_MIN,
    LEVEL_STEPS,
    area_group_for_phase,
    clamp_level,
    cpo_internal_level,
    level_meaning,
    level_summary_payload,
    public_level_from_cpo,
    quality_to_level,
)


# ─────────────────────────────────────────────────────────────────────────
# Escala invertida — 3=melhor, 1=pior
# ─────────────────────────────────────────────────────────────────────────

def test_scale_is_inverted_top_score_maps_to_three():
    """O bug da auditoria: antes 1=melhor. Agora score alto → nível 3.0."""
    assert quality_to_level(10.0) == 3.0
    assert quality_to_level(9.0) == 3.0


def test_scale_is_inverted_low_score_maps_to_one():
    """Score baixo → nível 1.0 (pior). Era 3 na escala antiga."""
    assert quality_to_level(1.0) == 1.0
    assert quality_to_level(4.9) == 1.0


def test_quality_to_level_monotonic_non_decreasing():
    """Quanto melhor o quality score, maior (ou igual) o nível — nunca menor."""
    prev = LEVEL_MIN
    for score in [1.0, 3.0, 5.0, 6.5, 7.9, 8.0, 8.9, 9.0, 10.0]:
        level = quality_to_level(score)
        assert level >= prev, f"score {score} quebrou a monotonia"
        prev = level


# ─────────────────────────────────────────────────────────────────────────
# Meios-níveis — passos de 0.5
# ─────────────────────────────────────────────────────────────────────────

def test_level_steps_are_half_steps_between_one_and_three():
    assert LEVEL_STEPS == (1.0, 1.5, 2.0, 2.5, 3.0)
    assert LEVEL_MIN == 1.0
    assert LEVEL_MAX == 3.0


def test_quality_to_level_only_emits_valid_half_steps():
    """Qualquer quality score [1-10] tem de cair num meio-passo válido."""
    for tenth in range(10, 101):
        score = tenth / 10.0
        assert quality_to_level(score) in LEVEL_STEPS


def test_mid_levels_are_reachable():
    """Os meios-níveis 1.5 e 2.5 existem e são alcançáveis (não só inteiros)."""
    assert quality_to_level(5.5) == 1.5
    assert quality_to_level(8.5) == 2.5


def test_clamp_level_snaps_to_nearest_half_step():
    assert clamp_level(2.3) == 2.5
    assert clamp_level(2.2) == 2.0
    assert clamp_level(1.74) == 1.5
    assert clamp_level(1.76) == 2.0


def test_clamp_level_bounds_to_one_three():
    assert clamp_level(0.1) == 1.0
    assert clamp_level(-5.0) == 1.0
    assert clamp_level(9.9) == 3.0
    assert clamp_level(3.5) == 3.0


# ─────────────────────────────────────────────────────────────────────────
# Grupos de área — ~7 grupos, mapa fase→grupo
# ─────────────────────────────────────────────────────────────────────────

def test_seven_area_groups_defined():
    """O Luis pediu ~7 grupos de área."""
    assert len(AREA_GROUPS) == 7
    assert "Laminagem" in AREA_GROUPS
    assert "Pintura" in AREA_GROUPS
    assert "Montagem" in AREA_GROUPS
    assert "Acabamento" in AREA_GROUPS


def test_area_group_for_known_phases():
    assert area_group_for_phase("Laminagem") == "Laminagem"
    assert area_group_for_phase("Laminagem Infusão") == "Laminagem"
    assert area_group_for_phase("Pintura Acabamento") == "Pintura"
    assert area_group_for_phase("Lixagem água") == "Pintura"
    assert area_group_for_phase("Colagem Peças") == "Montagem"
    assert area_group_for_phase("Colagem Golas") == "Montagem"
    assert area_group_for_phase("Cura") == "Cura/Moldes"
    assert area_group_for_phase("Preparação Molde") == "Cura/Moldes"


def test_area_group_fallback_is_transversal():
    """Fase desconhecida/genérica recai em Transversal — nunca crash."""
    assert area_group_for_phase("Reunião administrativa") == "Transversal"
    assert area_group_for_phase(None) == "Transversal"
    assert area_group_for_phase("", None) == "Transversal"


def test_area_group_always_in_whitelist():
    """area_group_for_phase devolve sempre um membro de AREA_GROUPS."""
    for name in ["Laminagem", "qualquer coisa", "", "Pintura X", None]:
        assert area_group_for_phase(name) in AREA_GROUPS


# ─────────────────────────────────────────────────────────────────────────
# Compatibilidade com o CPO — representação interna 1=melhor intocada
# ─────────────────────────────────────────────────────────────────────────

def test_cpo_internal_level_inverts_back():
    """O melhor nível público (3.0) mapeia para o melhor interno (1)."""
    assert cpo_internal_level(3.0) == 1
    assert cpo_internal_level(2.5) == 1
    assert cpo_internal_level(2.0) == 2
    assert cpo_internal_level(1.5) == 3
    assert cpo_internal_level(1.0) == 3


def test_public_level_from_cpo_round_trips_extremes():
    """ERP nivel 1 (melhor) → 3.0 público; nivel 3 → 1.0."""
    assert public_level_from_cpo(1) == 3.0
    assert public_level_from_cpo(2) == 2.0
    assert public_level_from_cpo(3) == 1.0


def test_public_level_from_cpo_handles_erp_one_to_five():
    """A curated skill_matrix usa 1-5; 4/5 não rebentam — clamped a 1.0."""
    assert public_level_from_cpo(4) == 1.0
    assert public_level_from_cpo(5) == 1.0
    assert public_level_from_cpo(99) == 1.0


# ─────────────────────────────────────────────────────────────────────────
# level_meaning / level_summary_payload
# ─────────────────────────────────────────────────────────────────────────

def test_level_meaning_covers_all_half_steps():
    for step in LEVEL_STEPS:
        m = LEVEL_MEANING[step]
        assert m["label"]
        assert m["description"]
        assert isinstance(m["boats"], list)


def test_level_meaning_best_level_is_top():
    assert level_meaning(3.0)["label"] == "Top"
    assert "K1 elite" in level_meaning(3.0)["boats"]


def test_level_meaning_worst_level_is_formacao():
    assert level_meaning(1.0)["label"] == "Em formação"


def test_level_summary_payload_exposes_inverted_scale():
    payload = level_summary_payload(9.5, ["Laminagem", "Pintura"])
    assert payload["derived_level"] == 3.0
    assert payload["level_scale"]["best"] == 3.0
    assert payload["level_scale"]["convention"] == "3=melhor, 1=pior"
    assert payload["level_scale"]["step"] == 0.5
    assert payload["level_label"] == "Top"
    assert payload["skills_apt"] == ["Laminagem", "Pintura"]


def test_level_summary_payload_low_score():
    payload = level_summary_payload(3.0, [])
    assert payload["derived_level"] == 1.0
    assert payload["level_label"] == "Em formação"


def test_level_summary_skills_apt_capped_at_ten():
    payload = level_summary_payload(8.0, [f"fase-{i}" for i in range(20)])
    assert len(payload["skills_apt"]) == 10


@pytest.mark.parametrize("score", [1.0, 4.99, 5.0, 6.5, 8.0, 9.0, 10.0])
def test_derived_level_always_valid_half_step(score):
    payload = level_summary_payload(score, [])
    assert payload["derived_level"] in LEVEL_STEPS
