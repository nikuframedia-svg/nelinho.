"""Workforce levels — escala 1-3 derivada do quality score Laplace [1-10].

Sprint Q.18 fix-workforce — Luis: "1 é o melhor, 3 é o pior, e essa avaliação
está relacionada com a análise de erros de cada trabalhador".

Bucketize quality_score (já existente, suavizado por Laplace α=1, β=10) num
nível 1-3 para uso na UI e para o LLM contextualizar respostas. Polivalência
mantém-se per-fase via `SkillMatrixRow.nivel` (campo curado independente).

Out-of-scope: alterar Field(ge=1, le=5) no PATCH /skills. Mantém-se 1-5 por
retro-compatibilidade; UI bucketiza para 1-3 quando apresenta o nível global.
"""
from __future__ import annotations

from typing import TypedDict


# Limiares quality_score → level. Documentados também em docs/operador_niveis.md
# para o LLM ter base estável quando perguntado.
QUALITY_TO_LEVEL_THRESHOLDS = (8.0, 5.0)


class LevelMeaning(TypedDict):
    label: str
    description: str
    boats: list[str]


LEVEL_MEANING: dict[int, LevelMeaning] = {
    1: {
        "label": "Top",
        "description": (
            "Quality score ≥ 8.0. Apto a barcos elite K1 competição + K4 "
            "(mais caros). Pode mentorar operadores nível 2/3."
        ),
        "boats": ["K1 elite", "K4", "K1 standard", "K2", "Recreio"],
    },
    2: {
        "label": "Médio",
        "description": (
            "Quality score 5.0–7.9. Faz K2 standard + K1 standard com autónomia. "
            "Pode tentar K1 elite supervisionado por nível 1."
        ),
        "boats": ["K2", "K1 standard", "Recreio"],
    },
    3: {
        "label": "Em formação",
        "description": (
            "Quality score < 5.0. Recreio + ajudante em peças complexas. "
            "Necessita supervisão de nível 1 ou 2."
        ),
        "boats": ["Recreio (supervisionado)"],
    },
}


def quality_to_level(score: float) -> int:
    """Mapeia quality score Laplace [1-10] para nível global 1-3 (1=melhor)."""
    if score >= QUALITY_TO_LEVEL_THRESHOLDS[0]:
        return 1
    if score >= QUALITY_TO_LEVEL_THRESHOLDS[1]:
        return 2
    return 3


def level_summary_payload(score: float, skills_apt_names: list[str]) -> dict:
    """Estrutura canónica usada pelo endpoint /level-summary e pelo Copilot context."""
    level = quality_to_level(score)
    meaning = LEVEL_MEANING[level]
    return {
        "quality_score": round(score, 2),
        "derived_level": level,
        "level_label": meaning["label"],
        "level_description": meaning["description"],
        "recommended_boats": list(meaning["boats"]),
        "skills_apt": skills_apt_names[:10],
    }
