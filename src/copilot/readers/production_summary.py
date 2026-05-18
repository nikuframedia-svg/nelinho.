"""
ProdPlan ONE — Copilot production summary reader (Sprint Q.34.A.1)
===================================================================

`build_production_summary` lê o estado de produção directamente da
tabela relacional `plan.production_orders` — populada pelo sync ERP
(`scripts/sync_nelo_to_postgres.py`).

Porquê: o `context_builder` lia a camada Factory Data Product
(`SemanticQueriesInMemory` / `factory_curated.*`), que arranca vazia. O
copiloto respondia "não tenho dados" mesmo com 521 ordens reais em
Postgres. Este reader fecha a lacuna sem tocar nos caminhos antigos.

Q.35.3.1 — o `status` das ordens vem todo `IN_PROGRESS` do sync (não é
sinal). O estado real está no `current_phase_name`: das 521 ordens, ~357
estão em fases administrativas (Entregue/Armazem/Embalado) — NÃO são WIP.
WIP real ≈ 164. O reader separa `orders_in_production` de
`orders_delivered_or_stored` e o `wip_by_phase` exclui as fases não-
produtivas, para o copiloto não chamar "Entregue" o maior gargalo.

Determinístico, read-only, tenant-scoped. Só expõe agregados que existem
mesmo — zero invenção de métricas.
"""

from __future__ import annotations

import hashlib
import logging
import unicodedata
from datetime import date
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.factory_data_product.config import NON_PRODUCTION_PHASES
from src.plan.models.order import OrderStatus, ProductionOrder

logger = logging.getLogger(__name__)

_TOP_PHASES = 10
_TRANSPORT_BUCKETS = 14

# Fases que NÃO são produção (ordem já saiu do chão de fábrica). Base na
# whitelist de `factory_data_product.config` + "Embalado" (produto
# acabado, embalado, à espera de expedição). A comparação é feita
# accent-/case-insensitive: o ERP grava "Armazem" sem acento, a config
# lista "Armazém" — sem normalizar, 26 ordens em armazém contavam como WIP.
_FINISHED_GOODS_EXTRA = ["Embalado"]


def _norm(phase: str) -> str:
    """Normaliza um nome de fase para comparação: sem acentos, minúsculas."""
    decomposed = unicodedata.normalize("NFKD", phase or "")
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.strip().lower()


_NON_PRODUCTION_NORM = frozenset(
    _norm(p) for p in list(NON_PRODUCTION_PHASES) + _FINISHED_GOODS_EXTRA
)


def _is_non_production(phase: str | None) -> bool:
    """True se a fase é administrativa (ordem já não está em produção)."""
    if not phase:
        return False  # fase desconhecida → conservador, conta como WIP
    return _norm(phase) in _NON_PRODUCTION_NORM


async def build_production_summary(
    session: AsyncSession, tenant_id: UUID,
) -> Dict[str, Any]:
    """Resumo de produção a partir de `plan.production_orders`.

    Devolve um dict JSON-serializável. `has_data` é False (e o resto fica
    de fora) quando não há ordens para o tenant ou a query falha — o
    chamador trata isso como "sem dados" e o copiloto não inventa.
    """
    query_hash = hashlib.sha256(
        f"prod_summary_{tenant_id}".encode()
    ).hexdigest()[:16]
    try:
        order = ProductionOrder
        scoped = order.tenant_id == tenant_id

        # Contagem por fase actual — é o sinal real de estado (o `status`
        # vem todo IN_PROGRESS do sync, não distingue nada).
        phase_rows = (await session.execute(
            select(order.current_phase_name, func.count().label("n"))
            .where(scoped)
            .group_by(order.current_phase_name)
            .order_by(func.count().desc())
        )).all()

        orders_total = sum(int(n) for _, n in phase_rows)
        if orders_total == 0:
            return {
                "has_data": False,
                "source": "db.production_orders",
                "query_hash": query_hash,
            }

        # Separar produção de não-produção (Entregue/Armazem/Embalado/...).
        wip_by_phase: list[Dict[str, Any]] = []
        delivered_or_stored_by_phase: list[Dict[str, Any]] = []
        orders_in_production = 0
        orders_delivered_or_stored = 0
        for phase, n in phase_rows:
            n = int(n)
            entry = {"phase": phase or "?", "orders": n}
            if _is_non_production(phase):
                orders_delivered_or_stored += n
                delivered_or_stored_by_phase.append(entry)
            else:
                orders_in_production += n
                wip_by_phase.append(entry)
        wip_by_phase = wip_by_phase[:_TOP_PHASES]

        # WIP por tipo de produto (K1/K2/K4/...) — só ordens em produção.
        type_rows = (await session.execute(
            select(order.product_type, func.count().label("n"))
            .where(scoped)
            .group_by(order.product_type)
            .order_by(func.count().desc())
        )).all()
        wip_by_product_type = {(t or "?"): int(n) for t, n in type_rows}

        # Ordens por data de transporte — visão de expedição (§9 do prompt).
        today = date.today()
        transport_rows = (await session.execute(
            select(order.transport_date, func.count().label("n"))
            .where(scoped, order.transport_date >= today)
            .group_by(order.transport_date)
            .order_by(order.transport_date.asc())
            .limit(_TRANSPORT_BUCKETS)
        )).all()
        orders_by_transport_date = [
            {"date": d.isoformat(), "orders": int(n)}
            for d, n in transport_rows
            if d is not None
        ]

        # Ordem mais antiga ainda em curso (NÃO é lead time — não há
        # actuals em Postgres; é só a data de criação mais antiga).
        oldest = (await session.execute(
            select(func.min(order.created_date))
            .where(scoped, order.status == OrderStatus.IN_PROGRESS.value)
        )).scalar_one_or_none()

        return {
            "has_data": True,
            "source": "db.production_orders",
            "query_hash": query_hash,
            "orders_total": orders_total,
            # Q.35.3.1 — contagens honestas, baseadas na fase actual.
            "orders_in_production": orders_in_production,
            "orders_delivered_or_stored": orders_delivered_or_stored,
            "wip_by_phase": wip_by_phase,
            "delivered_or_stored_by_phase": delivered_or_stored_by_phase,
            "wip_by_product_type": wip_by_product_type,
            "orders_by_transport_date": orders_by_transport_date,
            "oldest_in_progress_created": (
                oldest.isoformat() if oldest else None
            ),
        }
    except Exception as exc:
        logger.warning(f"build_production_summary falhou: {exc}")
        return {
            "has_data": False,
            "source": "unavailable",
            "query_hash": query_hash,
        }
