"""Q.61.20 — KPI factory (consolidacao incremental).

Audit overnight identificou KPIs duplicados:
  * `defect_rate` em 3+ sitios (worker-level Laplace,
    factory-level ratio, plan-adherence) — semanticas DIFERENTES.
  * `throughput` em 2 sitios (canonical em ThroughputService;
    derivado em factory_map_service).
  * `oee` em ~4 sitios.
  * `otd` em ~4 sitios.

Consolidar SEM resolver "qual cálculo é canónico" produz theater
(Karpathy failure mode #2). Q.61.20 fica HONESTO:

  * `throughput_*` → delega para `ThroughputService` (canonical).
    Novo codigo deve usar `KPIFactory.throughput_today()` em vez de
    chamar o service directamente.
  * `defect_rate`, `oee`, `otd` → raise NotImplementedError com TODO
    explicito. Q.62 decide produto (qual definicao usar) ANTES de
    expor uma API que mascare a divergencia actual.

Touched-file pays: futuros call-sites que consolidem migram para
esta factory; os actuais continuam ate alguem mexer.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.profit.services.throughput_service import ThroughputService


class KPIFactory:
    """Ponto unico (em construcao) para KPIs de fabrica.

    Hoje so `throughput_*` esta consolidado — delega para
    `ThroughputService`. Outros KPIs (`defect_rate`, `oee`, `otd`)
    lancam `NotImplementedError` ate Q.62 decidir qual e o calculo
    canonico.
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self._throughput = ThroughputService(session, tenant_id)

    # ─── Throughput (CANONICAL via ThroughputService) ────────────────

    async def throughput_today(self, *, as_of: Optional[date] = None) -> Decimal:
        """€/dia hoje (default today). Delega para `ThroughputService`."""
        return await self._throughput.throughput_today(as_of=as_of)

    async def throughput_mtd(self, *, as_of: Optional[date] = None) -> Decimal:
        """€ acumulado mes-a-data."""
        return await self._throughput.throughput_mtd(as_of=as_of)

    async def throughput_ytd(self, *, as_of: Optional[date] = None) -> Decimal:
        """€ acumulado ano-a-data."""
        return await self._throughput.throughput_ytd(as_of=as_of)

    async def throughput_trend(
        self, *, days_back: int = 14, until: Optional[date] = None,
    ) -> list[dict[str, Any]]:
        """Serie €/dia para os ultimos `days_back` dias."""
        return await self._throughput.throughput_trend(
            days_back=days_back, until=until,
        )

    # ─── KPIs nao-consolidados (Q.62) ────────────────────────────────

    async def defect_rate(self, **_kwargs) -> Decimal:
        """Q.62: 3 semanticas divergentes hoje.

          1. Worker-level Laplace (src/workforce/employee_extras_service.py:170)
             — (rework + α) / (ops + β) por employee.
          2. Factory-level ratio (src/factory_data_product/services/
             factory_map_service.py:635) — total_errors / total_orders.
          3. Plan adherence (src/plan/services/plan_adherence_service.py:113)
             — outro proxy.

        Antes de consolidar tem de haver decisao de produto sobre
        qual e o defect_rate "oficial" no ecra Direcao. Ate la,
        `defect_rate()` lanca para forcar discussao em vez de mascarar.
        """
        raise NotImplementedError(
            "Q.62 — defect_rate tem 3 semanticas divergentes hoje. "
            "Decide produto antes de consolidar (ver docstring)."
        )

    async def oee(self, **_kwargs) -> Decimal:
        """Q.62: OEE espalhado em ~4 sitios; algumas implementacoes
        nao incluem availability x performance x quality como devia."""
        raise NotImplementedError(
            "Q.62 — OEE espalhado em ~4 sitios com formulas diferentes. "
            "Consolidacao depende de decisao sobre availability source."
        )

    async def otd(self, **_kwargs) -> Decimal:
        """Q.62: OTD calculado em ~4 sitios; risk vs actual nem sempre
        distinguidos."""
        raise NotImplementedError(
            "Q.62 — OTD calculado em ~4 sitios; risk vs actual misturados. "
            "Decide produto antes de consolidar."
        )


__all__ = ["KPIFactory"]
