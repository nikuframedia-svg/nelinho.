"""Q.54.B — classificação de fases de produção por nome.

Sítio ÚNICO que sabe traduzir o nome de uma fase NELO (string crua vinda
do ERP, ``ProductionOrder.current_phase_name``) em três coisas:

* o **bucket de estado** — POR_COMECAR / A_DECORRER / CONCLUIDO;
* o **estado de ordem** correspondente (``OrderStatus``);
* a **sequência canónica** da fase no routing NELO.

Porquê aqui e não espalhado: o bug confirmado live era exactamente isto —
``/v1/plan/orders/active`` devolvia 521 ordens TODAS ``IN_PROGRESS`` quando
329 estavam "Entregue", 26 em "Armazem", 2 "Embalado". O ``status`` da
``ProductionOrder`` nunca transitava porque ninguém o derivava da fase.
Centralizar a regra garante que o endpoint e o sync concordam sempre.

A classificação é **por substring case-insensitive sobre o nome da fase** —
o ERP não tem um flag booleano de "fase terminal", só o nome. Fases que
não caem em CONCLUIDO nem POR_COMECAR são, por defeito, A_DECORRER (o
barco está no chão de fábrica).
"""

from __future__ import annotations

import unicodedata
from enum import Enum
from typing import Optional

from src.plan.models.order import OrderStatus

__all__ = [
    "PhaseBucket",
    "classify_phase",
    "phase_status",
    "phase_sequence",
    "is_completed_phase",
    "is_workable_phase",
    "NELO_PHASE_ORDER",
]


class PhaseBucket(str, Enum):
    """Bucket de estado de uma fase."""

    POR_COMECAR = "POR_COMECAR"
    A_DECORRER = "A_DECORRER"
    CONCLUIDO = "CONCLUIDO"


# ── Sequência canónica das fases NELO ───────────────────────────────────
# Quando o routing template não traz `seq`, esta ordem dá um `phase_sequence`
# determinístico. Casa com as 41 fases reais da Nelo colapsadas nos passos
# macro; chaves são lower-case sem acentos (ver `_norm`).
NELO_PHASE_ORDER: dict[str, int] = {
    "pendente": 0,
    "nao laminado": 1,
    "prep. molde": 2,
    "prep molde": 2,
    "preparacao molde": 2,
    "pintura gelcoat": 3,
    "gelcoat": 3,
    "laminagem": 4,
    "cura": 5,
    "desmolde": 6,
    "corte": 7,
    "colagem pecas": 8,
    "colagem": 8,
    "pintura acabam.": 9,
    "pintura acabamento": 9,
    "lixagem agua": 10,
    "lixagem": 10,
    "montagem": 11,
    "controlo de qualidade": 12,
    "cq final": 12,
    "embalado": 13,
    "armazem": 14,
    "entregue": 15,
}

# Substrings (normalizadas) que marcam uma fase como terminal — o barco já
# saiu do chão de fábrica.
_CONCLUIDO_MARKERS = ("entregue", "armazem", "embalado")

# Substrings que marcam uma fase como ainda-não-arrancada.
_POR_COMECAR_MARKERS = ("pendente", "nao laminado")


def _norm(value: Optional[str]) -> str:
    """Lower-case + sem acentos + trim — para casar 'Armazém' com 'Armazem'."""
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.strip().lower()


def classify_phase(phase_name: Optional[str]) -> PhaseBucket:
    """Devolve o :class:`PhaseBucket` de uma fase pelo nome.

    CONCLUIDO ("Entregue"/"Armazem"/"Embalado") tem prioridade sobre tudo;
    depois POR_COMECAR ("Pendente"/"Não Laminado"); o resto é A_DECORRER.
    Uma fase sem nome conta como A_DECORRER — é o estado conservador (não
    esconde a ordem nem a marca como concluída sem prova).
    """
    norm = _norm(phase_name)
    if any(marker in norm for marker in _CONCLUIDO_MARKERS):
        return PhaseBucket.CONCLUIDO
    if any(marker in norm for marker in _POR_COMECAR_MARKERS):
        return PhaseBucket.POR_COMECAR
    return PhaseBucket.A_DECORRER


def is_completed_phase(phase_name: Optional[str]) -> bool:
    """True se a fase é terminal (barco fora do chão de fábrica)."""
    return classify_phase(phase_name) is PhaseBucket.CONCLUIDO


def is_workable_phase(phase_name: Optional[str]) -> bool:
    """True se a fase é uma fase de trabalho real do routing.

    Q.55.B/D — usado para decidir se faz sentido atribuir um operador
    a uma ordem ou pontuar a adequação para a fase. É ``False`` para:

    * fases terminais (CONCLUIDO — o barco já saiu do chão de fábrica);
    * fases "por começar" (POR_COMECAR — "Pendente"/"Não Laminado": a
      ordem ainda não arrancou, não há operação de trabalho);
    * uma fase sem nome.

    Só as fases A_DECORRER são trabalháveis. Sítio único de verdade —
    o backend (atribuição) e o frontend (painel de operadores) leem daqui.
    """
    if not phase_name or not phase_name.strip():
        return False
    return classify_phase(phase_name) is PhaseBucket.A_DECORRER


def phase_status(phase_name: Optional[str]) -> OrderStatus:
    """Estado de ordem (``OrderStatus``) derivado do nome da fase.

    Mapeamento: CONCLUIDO → ``COMPLETED``; tudo o resto → ``IN_PROGRESS``
    (uma ordem POR_COMECAR continua activa, só ainda não arrancou). O
    estado ``CANCELLED`` nunca é inferível da fase — só vem do ERP.
    """
    if classify_phase(phase_name) is PhaseBucket.CONCLUIDO:
        return OrderStatus.COMPLETED
    return OrderStatus.IN_PROGRESS


def phase_sequence(phase_name: Optional[str]) -> Optional[int]:
    """Sequência canónica da fase no routing NELO, ou ``None`` se desconhecida.

    Usada quando o routing template não expõe um ``seq`` próprio. É
    determinística e estável — duas ordens na mesma fase têm a mesma
    sequência.
    """
    return NELO_PHASE_ORDER.get(_norm(phase_name))
