"""Workforce levels — escala 3=melhor por grupo de área + meios-níveis.

Sprint Q.53.E (Luis, 2026-05-19): inverter a escala de níveis. Até Q.18 o
nível ia de 1 (melhor) a 3 (pior); o Luis quer **3=melhor, 1=pior**, com
**meios-níveis** (1.0/1.5/2.0/2.5/3.0) e atribuído por **grupo de área**
(~7 grupos: Laminagem, Pintura, Montagem, Acabamento, Cura/Moldes,
Estrutura, Transversal) — não por fase individual.

Porquê grupo de área e não fase:
* 41 fases é granularidade a mais para um nível humano. Os operadores
  pensam em "sou bom na pintura", não "sou 2.5 na fase 17".
* O fit-score da página Fábrica (Q.53, frontend) agrega por área.

⚠️ Compatibilidade com o CPO: o pair-assignment/fitness NÃO consome este
módulo — usa o seu próprio `skill_match` booleano sobre a curated
`SkillMatrixRow.nivel` (campo 1-5, semântica ERP, intocada). A escala
aqui é **só para UI + Copilot**. `cpo_internal_level()` mapeia de volta
para a representação interna 1=melhor caso algum consumidor a precise.

Quality score Laplace [1-10] continua a ser a fonte: agora bucketiza para
um float meio-passo na escala invertida.
"""
from __future__ import annotations

from typing import TypedDict


# ─────────────────────────────────────────────────────────────────────────
# Escala invertida + meios-níveis
# ─────────────────────────────────────────────────────────────────────────
#
# Passos válidos: 1.0, 1.5, 2.0, 2.5, 3.0 (3.0 = melhor).
# Mapeamento quality_score Laplace [1-10] → nível float. Cada limiar é o
# piso (inclusivo) para esse meio-nível. Documentado em
# docs/operador_niveis.md para o LLM ter base estável.
LEVEL_STEPS = (1.0, 1.5, 2.0, 2.5, 3.0)
LEVEL_MIN = 1.0
LEVEL_MAX = 3.0

# (piso_quality_score, nivel) — avaliado do maior para o menor.
_QUALITY_TO_LEVEL = (
    (9.0, 3.0),
    (8.0, 2.5),
    (6.5, 2.0),
    (5.0, 1.5),
    (0.0, 1.0),
)


# ─────────────────────────────────────────────────────────────────────────
# Grupos de área — mapa fase → grupo
# ─────────────────────────────────────────────────────────────────────────
#
# 7 grupos. As chaves do mapa são substrings (lowercase) procuradas no
# nome da fase; a primeira que casar ganha. Fallback: "Transversal".
# A ordem importa — substrings mais específicas primeiro.
AREA_GROUPS = (
    "Laminagem",
    "Pintura",
    "Acabamento",
    "Montagem",
    "Cura/Moldes",
    "Estrutura",
    "Transversal",
)

_FASE_SUBSTRING_TO_GROUP: tuple[tuple[str, str], ...] = (
    # Laminagem (inclui infusão — processo de laminagem distinto)
    ("laminagem", "Laminagem"),
    ("infus", "Laminagem"),
    ("fibra", "Laminagem"),
    # Pintura (inclui lixagem ligada a acabamento de pintura e verniz)
    ("pintura", "Pintura"),
    ("verniz", "Pintura"),
    ("enverniz", "Pintura"),
    ("lixagem", "Pintura"),
    ("polimento", "Pintura"),
    # Acabamento
    ("acabamento", "Acabamento"),
    ("acabam", "Acabamento"),
    ("inspec", "Acabamento"),
    ("embalagem", "Acabamento"),
    # Montagem (colagens, junção de peças)
    ("montagem", "Montagem"),
    ("colagem", "Montagem"),
    ("colar", "Montagem"),
    ("gola", "Montagem"),
    # Cura / Moldes (preparação de molde, cura química, secagem)
    ("cura", "Cura/Moldes"),
    ("secagem", "Cura/Moldes"),
    ("molde", "Cura/Moldes"),
    ("desmold", "Cura/Moldes"),
    ("gelcoat", "Cura/Moldes"),
    ("gel coat", "Cura/Moldes"),
    # Estrutura (corte, costura de reforços, preparação estrutural)
    ("corte", "Estrutura"),
    ("costura", "Estrutura"),
    ("reforco", "Estrutura"),
    ("reforço", "Estrutura"),
    ("estrutura", "Estrutura"),
)


def area_group_for_phase(phase_name: str | None, phase_id: str | None = None) -> str:
    """Devolve o grupo de área (∈ AREA_GROUPS) de uma fase.

    Procura substrings no nome (e, em fallback, no id). Quando nada casa
    devolve "Transversal" — fases genéricas/administrativas que não
    pertencem a um grupo produtivo específico.
    """
    haystack = f"{phase_name or ''} {phase_id or ''}".lower()
    for needle, group in _FASE_SUBSTRING_TO_GROUP:
        if needle in haystack:
            return group
    return "Transversal"


class LevelMeaning(TypedDict):
    label: str
    description: str
    boats: list[str]


# Significado por meio-nível na escala invertida (3=melhor).
LEVEL_MEANING: dict[float, LevelMeaning] = {
    3.0: {
        "label": "Top",
        "description": (
            "Quality score ≥ 9.0. Apto a barcos elite K1 competição + K4 "
            "(mais caros). Pode mentorar operadores de nível inferior."
        ),
        "boats": ["K1 elite", "K4", "K1 standard", "K2", "Recreio"],
    },
    2.5: {
        "label": "Avançado",
        "description": (
            "Quality score 8.0–8.9. Faz K1 standard + K2 com total "
            "autonomia. Pode tentar K1 elite supervisionado por nível 3."
        ),
        "boats": ["K4", "K1 standard", "K2", "Recreio"],
    },
    2.0: {
        "label": "Médio",
        "description": (
            "Quality score 6.5–7.9. Faz K2 standard + K1 standard com "
            "autonomia. K1 elite só supervisionado."
        ),
        "boats": ["K2", "K1 standard", "Recreio"],
    },
    1.5: {
        "label": "Em progresso",
        "description": (
            "Quality score 5.0–6.4. Recreio + K2 supervisionado. "
            "Em formação para autonomia em peças standard."
        ),
        "boats": ["Recreio", "K2 (supervisionado)"],
    },
    1.0: {
        "label": "Em formação",
        "description": (
            "Quality score < 5.0. Recreio + ajudante em peças complexas. "
            "Necessita supervisão de nível 2.5 ou 3.0."
        ),
        "boats": ["Recreio (supervisionado)"],
    },
}


def quality_to_level(score: float) -> float:
    """Mapeia quality score Laplace [1-10] para nível float (3.0=melhor).

    Devolve um dos meios-passos em LEVEL_STEPS. Escala invertida face à
    versão Q.18 (era 1=melhor, int): agora 3.0=melhor, 1.0=pior.
    """
    for floor, level in _QUALITY_TO_LEVEL:
        if score >= floor:
            return level
    return LEVEL_MIN


def clamp_level(value: float) -> float:
    """Arredonda `value` ao meio-passo mais próximo e limita a [1.0, 3.0].

    Usado pelos endpoints que aceitam um nível editado pelo operador:
    qualquer float é normalizado para 1.0/1.5/2.0/2.5/3.0.
    """
    snapped = round(value * 2) / 2
    return max(LEVEL_MIN, min(LEVEL_MAX, snapped))


def cpo_internal_level(level: float) -> int:
    """Converte o nível público (3=melhor) para a convenção interna 1=melhor.

    A representação interna do CPO/ERP nunca foi alterada. Este helper
    existe para qualquer consumidor que precise de mapear no limite sem
    duplicar a fórmula. 3.0→1, 2.5/2.0→2, 1.5/1.0→3.
    """
    if level >= 2.5:
        return 1
    if level >= 2.0:
        return 2
    return 3


def public_level_from_cpo(internal: int) -> float:
    """Inverso aproximado de `cpo_internal_level` — 1→3.0, 2→2.0, 3→1.0.

    Usado para apresentar na UI um `nivel` curado da ERP (1-5, 1=melhor)
    sem partir a escala invertida. Valores fora de 1-3 são clamped.
    """
    mapping = {1: 3.0, 2: 2.0, 3: 1.0, 4: 1.0, 5: 1.0}
    return mapping.get(int(internal), LEVEL_MIN)


def level_meaning(level: float) -> LevelMeaning:
    """Significado do meio-nível mais próximo (label + descrição + barcos)."""
    return LEVEL_MEANING[clamp_level(level)]


def level_summary_payload(score: float, skills_apt_names: list[str]) -> dict:
    """Estrutura canónica usada pelo endpoint /level-summary e Copilot context.

    `derived_level` é agora float (3.0=melhor). `level_scale` documenta a
    convenção para o frontend não ter de a adivinhar.
    """
    level = quality_to_level(score)
    meaning = LEVEL_MEANING[level]
    return {
        "quality_score": round(score, 2),
        "derived_level": level,
        "level_scale": {
            "min": LEVEL_MIN,
            "max": LEVEL_MAX,
            "step": 0.5,
            "best": LEVEL_MAX,
            "convention": "3=melhor, 1=pior",
        },
        "level_label": meaning["label"],
        "level_description": meaning["description"],
        "recommended_boats": list(meaning["boats"]),
        "skills_apt": skills_apt_names[:10],
    }
