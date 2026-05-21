"""Operations-side semantic queries (Q.67.6.C5).

Covers the flow/throughput questions: what's open right now, where is it
piling up, what's the broad picture of the curated dataset.

- ``get_wip`` — open orders + their open phases.
- ``get_backlog`` — total open hours grouped by phase, sorted by load.
- ``get_bottlenecks`` — backlog re-sorted by days, with severity labels.
- ``get_overview`` — table-level summary (counts + samples) for diagnostics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from ...config import (
    NON_PRODUCTION_PHASES,
    SEMANTIC_LABELS,
    TRUST_INDEX,
    WORKING_HOURS_PER_DAY,
)

logger = logging.getLogger(__name__)


class _SemanticOperationsMixin:
    """WIP, backlog, bottlenecks and dataset overview."""

    # =========================================================================
    # WIP (Work in Progress)
    # =========================================================================

    def get_wip(self) -> Dict[str, Any]:
        """Get Work in Progress: open orders and their open phases.

        Calculation:
        1. Filter orders where ``data_conclusao IS NULL``.
        2. Get all phases linked to these open orders.
        3. Sum ``horas_finais`` for these phases.
        4. Calculate coverage (% of phases with ``horas_finais``).

        Trust: based on ``FasesOrdemFabrico_HorasPrevistas`` coverage.
        """
        logger.info("Calculating WIP from curated data")

        curated = self._get_active_curated()
        if not curated:
            return self._empty_response("wip", "Sem dados - execute ingestão primeiro")

        orders = curated.get("orders", [])
        phases = curated.get("order_phases", [])

        if not orders:
            return self._empty_response("wip", "Sem ordens na camada CURATED")

        open_orders = [o for o in orders if not o.get("data_conclusao")]
        open_order_ids = {o["of_id"] for o in open_orders}

        open_phases = [p for p in phases if p.get("of_id") in open_order_ids]

        total_horas = 0.0
        phases_with_hours = 0

        for p in open_phases:
            horas = p.get("horas_finais")
            if horas is not None:
                try:
                    horas_float = float(horas) if not isinstance(horas, (int, float)) else horas
                    if horas_float > 0:
                        total_horas += horas_float
                        phases_with_hours += 1
                except (ValueError, TypeError):
                    pass

        coverage_pct = (phases_with_hours / len(open_phases) * 100) if open_phases else 0

        base_trust = TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58)
        confidence = self._calculate_confidence(
            base_trust=base_trust,
            coverage_pct=coverage_pct,
            sample_size=len(open_orders),
        )

        logger.info(
            f"WIP: {len(open_orders)} open orders, {len(open_phases)} open phases, "
            f"{total_horas:.1f}h"
        )

        return {
            "data": {
                "open_orders": len(open_orders),
                "total_orders": len(orders),
                "open_orders_pct": round(len(open_orders) / len(orders) * 100, 1) if orders else 0,
                "open_phases_total": len(open_phases),
                "phases_with_hours": phases_with_hours,
                "total_horas_previstas": round(total_horas, 2),
                "avg_horas_per_phase": round(total_horas / len(open_phases), 2) if open_phases else 0,
            },
            "data_confidence": confidence,
            "trust_status": self._get_trust_status(confidence),
            "semantic_label": SEMANTIC_LABELS.get("wip", "WIP teórico"),
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "horas_previstas_coverage_pct": round(coverage_pct, 1),
                "source": "curated",
                "calculation": "open_orders = orders WHERE data_conclusao IS NULL",
            },
        }

    # =========================================================================
    # BACKLOG
    # =========================================================================

    def get_backlog(self, top_n: int = 20) -> Dict[str, Any]:
        """Get theoretical backlog by phase.

        Backlog = SUM(``horas_finais``) for open phases, grouped by ``fase_id``.
        BacklogDias = ``backlog_horas`` / ``capacidade_horas_dia``.
        """
        logger.info(f"Calculating backlog by phase (top {top_n})")

        curated = self._get_active_curated()
        if not curated:
            return self._empty_response("backlog", "Sem dados - execute ingestão primeiro")

        orders = curated.get("orders", [])
        phases = curated.get("order_phases", [])
        capacities = curated.get("phase_capacities", [])

        if not phases:
            return self._empty_response("backlog", "Sem fases na camada CURATED")

        open_order_ids = {o["of_id"] for o in orders if not o.get("data_conclusao")}

        capacity_map: Dict[str, float] = {}
        for c in capacities:
            fase_id = c.get("fase_id")
            cap = c.get("capacidade_horas")
            if fase_id and cap:
                try:
                    capacity_map[fase_id] = float(cap)
                except (ValueError, TypeError):
                    capacity_map[fase_id] = WORKING_HOURS_PER_DAY

        backlog_by_fase: Dict[str, Dict] = {}

        for p in phases:
            if p.get("of_id") not in open_order_ids:
                continue

            fase_nome = p.get("fase_nome", "")
            if fase_nome in NON_PRODUCTION_PHASES:
                continue

            fase_id = p.get("fase_id")
            if not fase_id:
                continue

            if fase_id not in backlog_by_fase:
                backlog_by_fase[fase_id] = {
                    "fase_id": fase_id,
                    "fase_nome": fase_nome or f"Fase {fase_id}",
                    "fases_abertas": 0,
                    "backlog_horas": 0.0,
                    "phases_with_hours": 0,
                }

            backlog_by_fase[fase_id]["fases_abertas"] += 1

            horas = p.get("horas_finais")
            if horas is not None:
                try:
                    horas_float = float(horas) if not isinstance(horas, (int, float)) else horas
                    if horas_float > 0:
                        backlog_by_fase[fase_id]["backlog_horas"] += horas_float
                        backlog_by_fase[fase_id]["phases_with_hours"] += 1
                except (ValueError, TypeError):
                    pass

        results = []
        for fase_id, data in backlog_by_fase.items():
            cap = capacity_map.get(fase_id, WORKING_HOURS_PER_DAY)
            coverage = (
                data["phases_with_hours"] / data["fases_abertas"] * 100
            ) if data["fases_abertas"] else 0

            results.append({
                "fase_id": data["fase_id"],
                "fase_nome": data["fase_nome"],
                "fases_abertas": data["fases_abertas"],
                "backlog_horas": round(data["backlog_horas"], 2),
                "backlog_dias_teoricos": round(data["backlog_horas"] / cap, 1) if cap else 0,
                "capacidade_horas_dia": cap,
                "coverage_pct": round(coverage, 1),
            })

        results.sort(key=lambda x: x["backlog_horas"], reverse=True)

        total_backlog = sum(r["backlog_horas"] for r in results)
        total_phases = sum(r["fases_abertas"] for r in results)
        total_with_hours = sum(1 for r in results if r["coverage_pct"] > 0)

        overall_coverage = (total_with_hours / len(results) * 100) if results else 0
        confidence = self._calculate_confidence(
            base_trust=TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58),
            coverage_pct=overall_coverage,
            sample_size=total_phases,
        )

        logger.info(f"Backlog: {len(results)} phases, {total_backlog:.1f}h total")

        return {
            "data": {
                "total_phases_analyzed": len(phases),
                "production_phases_count": len(results),
                "total_backlog_horas": round(total_backlog, 2),
                "total_backlog_dias": round(total_backlog / WORKING_HOURS_PER_DAY, 1),
                "backlog_by_phase": results[:top_n],
            },
            "data_confidence": confidence,
            "trust_status": self._get_trust_status(confidence),
            "semantic_label": SEMANTIC_LABELS.get("bottleneck", "gargalo provável"),
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "top_n": top_n,
                "excluded_phases": NON_PRODUCTION_PHASES,
                "source": "curated",
            },
        }

    # =========================================================================
    # BOTTLENECKS
    # =========================================================================

    def get_bottlenecks(self, top_n: int = 10) -> Dict[str, Any]:
        """Get bottleneck ranking by backlog days.

        Severity thresholds:
        - CRITICAL: backlog_dias > 5
        - HIGH: backlog_dias > 3
        - MEDIUM: backlog_dias > 1
        """
        logger.info(f"Calculating bottleneck ranking (top {top_n})")

        CRITICAL_THRESHOLD = 5
        HIGH_THRESHOLD = 3
        MEDIUM_THRESHOLD = 1

        backlog_result = self.get_backlog(top_n=100)

        if backlog_result.get("data") is None:
            return self._empty_response("bottlenecks", "Sem dados de backlog")

        phases = backlog_result["data"].get("backlog_by_phase", [])

        phases.sort(key=lambda x: x.get("backlog_dias_teoricos", 0), reverse=True)

        bottlenecks = []
        for i, p in enumerate(phases[:top_n]):
            dias = p.get("backlog_dias_teoricos", 0)

            if dias > CRITICAL_THRESHOLD:
                severity = "CRITICAL"
                is_critical = True
            elif dias > HIGH_THRESHOLD:
                severity = "HIGH"
                is_critical = True
            elif dias > MEDIUM_THRESHOLD:
                severity = "MEDIUM"
                is_critical = False
            else:
                severity = "OK"
                is_critical = False

            bottlenecks.append({
                "rank": i + 1,
                "fase_id": p["fase_id"],
                "fase_nome": p["fase_nome"],
                "backlog_dias": dias,
                "backlog_horas": p["backlog_horas"],
                "fases_abertas": p["fases_abertas"],
                "coverage_pct": p["coverage_pct"],
                "severity": severity,
                "is_critical": is_critical,
            })

        critical_count = sum(1 for b in bottlenecks if b["severity"] == "CRITICAL")
        high_count = sum(1 for b in bottlenecks if b["severity"] == "HIGH")

        logger.info(f"Bottlenecks: {critical_count} critical, {high_count} high")

        return {
            "data": {
                "bottlenecks": bottlenecks,
                "critical_count": critical_count,
                "high_count": high_count,
                "total_analyzed": len(phases),
            },
            "data_confidence": backlog_result["data_confidence"],
            "trust_status": backlog_result["trust_status"],
            "semantic_label": SEMANTIC_LABELS.get("bottleneck", "gargalo provável"),
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "top_n": top_n,
                "thresholds": {
                    "critical_days": CRITICAL_THRESHOLD,
                    "high_days": HIGH_THRESHOLD,
                    "medium_days": MEDIUM_THRESHOLD,
                },
                "source": "curated",
            },
        }

    # =========================================================================
    # SUMMARY / OVERVIEW
    # =========================================================================

    def get_overview(self) -> Dict[str, Any]:
        """Get overview/summary of all curated data."""
        logger.info("Generating data overview")

        curated = self._get_active_curated()
        if not curated:
            return self._empty_response("overview", "Sem dados - execute ingestão primeiro")

        summary = {}
        for table_name, data in curated.items():
            if isinstance(data, list):
                summary[table_name] = {
                    "count": len(data),
                    "sample": data[:3] if data else [],
                }

        active = self.engine.get_active_run()

        return {
            "data": {
                "tables": summary,
                "active_ingestion_id": str(active["active_ingestion_id"]) if active else None,
                "activated_at": active.get("activated_at_utc") if active else None,
            },
            "data_confidence": 100,
            "trust_status": "OK",
            "semantic_label": "Visão geral dos dados curados",
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "source": "curated",
            },
        }
