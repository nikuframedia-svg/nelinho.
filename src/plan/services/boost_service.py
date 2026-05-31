"""Q.116.D - calculo do boost efectivo no scheduler.

Boost = stack de 3 niveis (cliente + encomenda + barco), capped a 200.
ClientPriority 1-5 mapeia: client_boost = (6 - priority) * 20.

Funcoes puras — sem dependencias de DB, sem efeitos secundarios. O
decoder CPO unificado (Agent ainda por entregar) consome estas para
ordenar o cromossoma antes do greedy.

NUNCA tocar src/plan/cpo/* aqui. Este modulo nasce em services/ para
manter os invariantes Spelke do scheduler intactos.
"""
from __future__ import annotations

from typing import Optional

MAX_TOTAL_BOOST = 200


def client_boost_from_priority(priority: Optional[int]) -> int:
    """Mapeia ClientPriority 1-5 -> client_boost 100/80/60/40/20.

    None ou prioridade fora de [1, 5] -> 0 (sem boost).
    """
    if priority is None:
        return 0
    try:
        p = int(priority)
    except (TypeError, ValueError):
        return 0
    if not (1 <= p <= 5):
        return 0
    return (6 - p) * 20


def compute_effective_boost(
    client_priority: Optional[int],
    order_boost: int,
    boat_boost: int,
) -> int:
    """Boost efectivo somado e capped a MAX_TOTAL_BOOST.

    Componentes negativos (ou None / nao-int) viram 0 antes da soma.
    """
    cb = client_boost_from_priority(client_priority)
    try:
        ob_int = int(order_boost or 0)
    except (TypeError, ValueError):
        ob_int = 0
    try:
        bb_int = int(boat_boost or 0)
    except (TypeError, ValueError):
        bb_int = 0
    ob = max(0, ob_int)
    bb = max(0, bb_int)
    return min(cb + ob + bb, MAX_TOTAL_BOOST)
