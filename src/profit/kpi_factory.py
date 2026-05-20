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

    # ─── Defect rate — 2 KPIs distintos com nomes claros (Q.62.C.2) ───
    #
    # `team_defect_rate(window_days)` — comportamento da equipa
    #     (Laplace agregada de todos os operadores).
    # `product_defect_rate(window_days)` — qualidade dos barcos
    #     entregues (% de ordens com retrabalho).
    #
    # São KPIs diferentes — podem mover em direccoes opostas. NAO ha
    # `defect_rate()` ambiguo: cada call-site escolhe explicitamente.

    async def team_defect_rate(
        self, *, window_days: int = 90,
    ) -> Decimal:
        """Hipótese A — comportamento da equipa.

        Delega para `EmployeeExtrasService.team_defect_rate` que aplica
        `(defects + α) / (ops + β)` (Laplace, α=1 β=10) aos contadores
        agregados de TODOS os operadores no tenant dentro da janela.
        Range [0, 1].
        """
        from src.workforce.employee_extras_service import EmployeeExtrasService

        svc = EmployeeExtrasService(self.session, self.tenant_id)
        rate = await svc.team_defect_rate(window_days=window_days)
        return Decimal(str(rate))

    async def product_defect_rate(
        self, *, window_days: int = 90,
    ) -> Optional[Decimal]:
        """Hipótese B — qualidade dos barcos entregues.

        Delega para `FactoryMapService._defect_rate_from_db` que calcula
        fracção de ordens (`ProductionOrder`) com >= 1 retrabalho na
        janela. Range [0, 1]. Pode devolver None quando não há ordens
        suficientes para calcular.
        """
        from src.factory_data_product.services.factory_map_service import (
            FactoryMapService,
        )

        svc = FactoryMapService(self.session, self.tenant_id)
        # `_defect_rate_from_db` precisa de orders_total como argumento.
        # Reaproveitar a query existente via `_orders_summary` mas pegar
        # so no total.
        try:
            summary = await svc._orders_summary()
            total = int(summary.get("total", 0))
        except Exception:  # pragma: no cover — defensivo
            total = 0
        rate = await svc._defect_rate_from_db(
            orders_total=total, window_days=window_days,
        )
        return Decimal(str(rate)) if rate is not None else None

    # ─── OEE + OTD (Q.62.C.3) ────────────────────────────────────────
    #
    # OEE: 1 servico canonico (OEEService) com availability × performance ×
    #      quality. KPIFactory delega.
    # OTD: 2 KPIs distintos (como defect_rate) — actual % vs predictive
    #      risk. Cada um com nome explicito.
    #
    # `otd()` ambiguo foi REMOVIDO — usar otd_actual_pct ou otd_risk.

    async def oee(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> Decimal:
        """OEE = Availability × Performance × Quality, no intervalo dado.

        Delega para `OEEService.calculate()`. Retorna o OEE global (não
        breakdown por grupo). Range [0, 1].
        """
        from src.profit.services.oee_service import OEEService

        # Q.62.C.3 — OEEService usa fetcher injectado (default = NELO adapter).
        # Para consumo via KPIFactory aceita-se o default; testes podem
        # mockar via dependency override.
        svc = OEEService()
        result = await svc.calculate(date_from=date_from, date_to=date_to)
        return Decimal(str(result.overall.oee))

    async def otd_actual_pct(
        self,
        *,
        window_days: int = 90,
    ) -> Decimal:
        """OTD actual (% de ordens entregues a tempo) no periodo.

        Delega para `DashboardMetricsService.otd()`. Critério:
        `data_conclusao <= data_entrega_prevista`. Range [0, 100] (é
        retornado em percentagem, não fracção).
        """
        from src.profit.services.dashboard_metrics_service import (
            DashboardMetricsService,
        )

        svc = DashboardMetricsService(self.session, self.tenant_id)
        result = await svc.otd(window_days=window_days)
        return Decimal(str(result.otd_pct))

    async def otd_risk(
        self,
        *,
        top_n: int = 50,
    ) -> dict[str, Any]:
        """Risco preditivo de atraso para ordens em curso.

        Delega para `OTDRiskService.otd_risk()`. **Distinct de
        `otd_actual_pct`** — actual mede o passado, risk prediz o futuro.
        Retorna dict com `predictions`, `model_available`, `feature_importance`.
        """
        from src.plan.services.otd_risk_service import OTDRiskService

        svc = OTDRiskService(self.session, self.tenant_id)
        return await svc.otd_risk(top_n=top_n)


__all__ = ["KPIFactory"]
