"""Q.54.O — ordem canónica das fases derivada do routing real.

O endpoint ``/v1/plan/orders/active`` precisa de saber a posição de cada
fase na sequência de fabrico para o frontend ordenar as colunas Kanban da
Fábrica. Até aqui usava ``NELO_PHASE_ORDER`` — um dicionário fixo de 16
entradas com correspondência **exacta**. Os nomes reais do ERP não batem
certo ("Laminagem peças" ≠ "laminagem", "Corte peças" ≠ "corte"), por isso
as três maiores colunas ficavam com ``phase_sequence = None`` e o frontend
mandava-as para o fim — colunas trocadas.

Este módulo deriva a ordem das 1429 linhas de ``routing_template_phase`` —
a sequência real dos 141 templates de routing minados do histórico. A
posição de cada fase é a **média do ``seq``** em todos os templates onde
aparece; ranqueada, dá um inteiro estável e determinístico.

Porquê o ``seq`` cru e não ``seq / phase_count``: as peças (sub-conjuntos)
têm templates curtos próprios — "Laminagem peças" é o ``seq=1`` de um
template de 2 fases. Normalizar pelo tamanho empurra-a para o meio (0,5)
quando, no fabrico, é cedo. O ``seq`` cru mantém-na cedo, e os templates
longos — que definem a espinha do fabrico — dominam a média na mesma.

Degrada com honestidade: routing não-semeado → mapa vazio → quem chama cai
no dicionário estático antigo. ZERO MOCKS.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.routing_template import RoutingTemplatePhase

__all__ = [
    "normalise_phase_name",
    "build_phase_order",
    "resolve_phase_sequence",
    "PhaseOrderingService",
]


def normalise_phase_name(value: Optional[str]) -> str:
    """Lower-case, sem acentos, sem pontuação, espaços colapsados.

    Mais agressiva que o ``_norm`` de :mod:`phase_classification` — remove
    também pontuação, para que "Lixagem - água" e "Lixagem água" colem, e
    "Pintura Acabam." e "Pintura Acabamento" fiquem comparáveis.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", stripped.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def build_phase_order(
    rows: Iterable[tuple[Optional[str], object]],
) -> dict[str, int]:
    """Constrói ``{nome_normalizado: rank}`` a partir de pares brutos.

    Args:
        rows: iterável de ``(phase_name, posição_média)`` — a posição é a
            média do ``seq`` para essa fase. ``None`` / posições inválidas
            são ignorados.

    O ranking é por posição média crescente; empates partem-se pelo nome
    (determinístico). O resultado é um inteiro 0..N-1, escala única.
    """
    agg: dict[str, list[float]] = {}
    for name, pos in rows:
        key = normalise_phase_name(name)
        if not key or pos is None:
            continue
        try:
            agg.setdefault(key, []).append(float(pos))
        except (TypeError, ValueError):  # pragma: no cover — defensivo
            continue

    ranked = sorted(
        agg.items(),
        key=lambda kv: (sum(kv[1]) / len(kv[1]), kv[0]),
    )
    return {key: idx for idx, (key, _) in enumerate(ranked)}


def resolve_phase_sequence(
    phase_name: Optional[str],
    order_map: dict[str, int],
) -> Optional[int]:
    """Posição de uma fase no ``order_map`` — exacta, depois substring.

    O ERP e o routing às vezes escrevem o mesmo passo com pontuação ou
    abreviatura diferente ("Pintura Acabam." vs "Pintura Acabamento"). A
    seguir à correspondência exacta, tenta substring em qualquer direcção.
    ``None`` quando nada casa — honesto, sem inventar uma posição.
    """
    key = normalise_phase_name(phase_name)
    if not key or not order_map:
        return None
    exact = order_map.get(key)
    if exact is not None:
        return exact
    # Substring tolerante — preferir o match mais longo (mais específico).
    best: Optional[tuple[int, int]] = None  # (comprimento_match, rank)
    for known, rank in order_map.items():
        if key in known or known in key:
            overlap = min(len(key), len(known))
            if best is None or overlap > best[0]:
                best = (overlap, rank)
    return best[1] if best is not None else None


class PhaseOrderingService:
    """Lê o routing e devolve a ordem canónica das fases para um tenant."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def phase_order_map(self) -> dict[str, int]:
        """``{nome_normalizado: rank}`` derivado de ``routing_template_phase``.

        Mapa vazio quando o routing não está semeado — quem chama deve cair
        no dicionário estático nesse caso.
        """
        stmt = (
            select(
                RoutingTemplatePhase.phase_name,
                func.avg(RoutingTemplatePhase.seq),
            )
            .where(RoutingTemplatePhase.tenant_id == self.tenant_id)
            .where(RoutingTemplatePhase.phase_name.isnot(None))
            .group_by(RoutingTemplatePhase.phase_name)
        )
        result = await self.session.execute(stmt)
        return build_phase_order(result.all())
