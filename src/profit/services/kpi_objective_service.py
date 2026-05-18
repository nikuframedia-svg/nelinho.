"""KPI objective-vs-realised service (Sprint Q.47 / F9).

Answers the CEO question "estou a bater os meus objectivos?" by joining
the KPI catalogue (`dbo.KPI`) with the objective records
(`dbo.KPI_OBJECTIVO`) the NELO ERP already carries.

Source
------
The Q.45.C readers ``src.adapters.nelo.services.list_kpi_definitions``
(``KPI``, ~115 rows — the catalogue) and ``list_kpi_objectives``
(``KPI_OBJECTIVO``, ~267 rows — realised value vs objective per date).

For each KPI we pick the **most recent** objective record (by
``objective_date`` when present, else ``objective_date_logged``) and
compute the attainment: how close the realised ``value`` is to the
``objective`` target. KPIs the ERP has defined but never logged an
objective for are returned with ``has_objective=False`` — no invented
numbers.

Honesty about the ERP being offline
-----------------------------------
The whole adapter raises ``RuntimeError`` when ``sqlserver_enabled`` is
``False`` (dev/no-credentials). The service catches it and returns an
explicit empty result with ``erp_available=False`` and a reason string.
ZERO MOCKS — no fallback numbers, no fabricated KPIs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from src.adapters.nelo.schemas import KpiObjectiveRow, KpiRow
from src.adapters.nelo.services import list_kpi_definitions, list_kpi_objectives

log = logging.getLogger(__name__)

# The objective-vs-realised slice cannot be served from local Postgres —
# `KPI` / `KPI_OBJECTIVO` live only in the read-only ERP. When the ERP
# adapter is disabled the service degrades to an explicit empty result.
ERP_OFFLINE_REASON = (
    "Objectivos de KPI vivem nas tabelas ERP KPI / KPI_OBJECTIVO — "
    "o adapter SQL Server está desligado (sqlserver_enabled=False). "
    "Fica vazio até ao sync ERP (F1)."
)

# Attainment band thresholds. `status` classifies how the realised value
# sits against the objective: hit (>=100%), near (>=90%), below (<90%).
NEAR_TARGET_RATIO = 0.90

KpiDefinitionFetcher = Callable[[], Awaitable[list[KpiRow]]]
KpiObjectiveFetcher = Callable[[], Awaitable[list[KpiObjectiveRow]]]


# ─── Result shapes ──────────────────────────────────────────────────────


@dataclass
class KpiObjectiveRow_:
    """One KPI with its latest objective vs realised value.

    ``attainment_pct`` is ``value / objective`` as a percentage — 100
    means the objective was exactly met. ``status`` buckets it into
    hit / near / below. When the KPI has no objective record at all,
    ``has_objective`` is False and the numeric fields stay ``None``.
    """

    kpi_id: int
    name: str
    description: str | None
    display_order: int
    has_objective: bool
    value: float | None = None
    objective: float | None = None
    attainment_pct: float | None = field(init=False, default=None)
    status: str = field(init=False, default="no_objective")
    objective_date: str | None = None

    def __post_init__(self) -> None:
        if not self.has_objective or self.value is None or self.objective is None:
            self.status = "no_objective"
            return
        # Objective of 0 is a degenerate target — cannot express a ratio.
        if self.objective == 0:
            self.attainment_pct = None
            self.status = "hit" if self.value >= 0 else "below"
            return
        ratio = self.value / self.objective
        self.attainment_pct = round(ratio * 100.0, 1)
        if ratio >= 1.0:
            self.status = "hit"
        elif ratio >= NEAR_TARGET_RATIO:
            self.status = "near"
        else:
            self.status = "below"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kpi_id": self.kpi_id,
            "name": self.name,
            "description": self.description,
            "display_order": self.display_order,
            "has_objective": self.has_objective,
            "value": self.value,
            "objective": self.objective,
            "attainment_pct": self.attainment_pct,
            "status": self.status,
            "objective_date": self.objective_date,
        }


@dataclass
class KpiObjectiveResult:
    erp_available: bool
    rows: list[KpiObjectiveRow_]
    kpi_count: int
    with_objective_count: int
    hit_count: int
    below_count: int
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "erp_available": self.erp_available,
            "reason": self.reason,
            "kpi_count": self.kpi_count,
            "with_objective_count": self.with_objective_count,
            "hit_count": self.hit_count,
            "below_count": self.below_count,
            "items": [r.to_dict() for r in self.rows],
        }


# ─── Service ────────────────────────────────────────────────────────────


class KpiObjectiveService:
    """Stateless service. Pass in fetchers (default to the ERP adapter)."""

    def __init__(
        self,
        definition_fetcher: KpiDefinitionFetcher | None = None,
        objective_fetcher: KpiObjectiveFetcher | None = None,
    ) -> None:
        self._definitions = definition_fetcher or list_kpi_definitions
        self._objectives = objective_fetcher or list_kpi_objectives

    async def objectives(self) -> KpiObjectiveResult:
        """KPI objective-vs-realised, ordered by `display_order`.

        Degrades to ``erp_available=False`` with a reason when the ERP
        adapter is disabled (``RuntimeError`` from ``get_engine``).
        """
        try:
            definitions = await self._definitions()
            objectives = await self._objectives()
        except RuntimeError as exc:
            log.info("KPI objectives: ERP adapter offline — %s", exc)
            return KpiObjectiveResult(
                erp_available=False,
                rows=[],
                kpi_count=0,
                with_objective_count=0,
                hit_count=0,
                below_count=0,
                reason=ERP_OFFLINE_REASON,
            )
        return self._assemble(definitions, objectives)

    def _assemble(
        self,
        definitions: list[KpiRow],
        objectives: list[KpiObjectiveRow],
    ) -> KpiObjectiveResult:
        """Join each KPI to its latest objective record."""
        latest = self._latest_objective_per_kpi(objectives)

        rows: list[KpiObjectiveRow_] = []
        for d in definitions:
            obj = latest.get(d.kpi_id)
            if obj is None:
                rows.append(
                    KpiObjectiveRow_(
                        kpi_id=d.kpi_id,
                        name=d.name,
                        description=d.description,
                        display_order=d.display_order,
                        has_objective=False,
                    )
                )
                continue
            rows.append(
                KpiObjectiveRow_(
                    kpi_id=d.kpi_id,
                    name=d.name,
                    description=d.description,
                    display_order=d.display_order,
                    has_objective=True,
                    value=float(obj.value),
                    objective=float(obj.objective),
                    objective_date=self._objective_date_iso(obj),
                )
            )

        rows.sort(key=lambda r: (r.display_order, r.kpi_id))
        with_objective = [r for r in rows if r.has_objective]
        return KpiObjectiveResult(
            erp_available=True,
            rows=rows,
            kpi_count=len(rows),
            with_objective_count=len(with_objective),
            hit_count=sum(1 for r in with_objective if r.status == "hit"),
            below_count=sum(1 for r in with_objective if r.status == "below"),
        )

    @staticmethod
    def _latest_objective_per_kpi(
        objectives: list[KpiObjectiveRow],
    ) -> dict[int, KpiObjectiveRow]:
        """Keep, per KPI, the most recent objective record.

        Recency uses ``objective_date`` when set, else
        ``objective_date_logged`` (always present)."""
        latest: dict[int, KpiObjectiveRow] = {}
        for o in objectives:
            key_date = o.objective_date or o.objective_date_logged
            current = latest.get(o.kpi_id)
            if current is None:
                latest[o.kpi_id] = o
                continue
            current_date = current.objective_date or current.objective_date_logged
            if key_date >= current_date:
                latest[o.kpi_id] = o
        return latest

    @staticmethod
    def _objective_date_iso(obj: KpiObjectiveRow) -> str:
        d = obj.objective_date or obj.objective_date_logged
        return d.isoformat()
