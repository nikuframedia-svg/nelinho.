"""Quality/skills/lead-time semantic queries (Q.67.6.C5).

Covers the "shop-floor risk" side of the curated dataset:

- ``get_quality`` — defect events grouped by error / phase.
- ``get_skills_risk`` — SPOF/HIGH/MEDIUM coverage per production phase.
- ``get_lead_time`` — stats on closed orders' total elapsed days.
- ``get_mold_conflicts`` — molds open on more than one order at once.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List

from ...config import (
    NON_PRODUCTION_PHASES,
    SEMANTIC_LABELS,
    TRUST_INDEX,
)

logger = logging.getLogger(__name__)


class _SemanticQualityMixin:
    """Quality, skills risk, lead time and mold conflicts."""

    # =========================================================================
    # SKILLS RISK
    # =========================================================================

    def get_skills_risk(self, min_capable: int = 3) -> Dict[str, Any]:
        """Get skills risk assessment by phase.

        Risk Levels:
        - CRITICAL: 0-1 capable employees (SPOF)
        - HIGH: < ``min_capable``
        - MEDIUM: < ``min_capable + 2``
        - OK: >= ``min_capable + 2``
        """
        logger.info(f"Calculating skills risk (min capable: {min_capable})")

        curated = self._get_active_curated()
        if not curated:
            return self._empty_response("skills_risk", "Sem dados - execute ingestão primeiro")

        skills = curated.get("skill_matrix", [])
        capacities = curated.get("phase_capacities", [])

        if not skills:
            return self._empty_response("skills_risk", "Sem dados de competências")

        aptos_por_fase: Dict[str, Dict] = {}

        for s in skills:
            if not s.get("apto"):
                continue

            fase_id = s.get("fase_id")
            if not fase_id:
                continue

            if fase_id not in aptos_por_fase:
                aptos_por_fase[fase_id] = {
                    "fase_id": fase_id,
                    "fase_nome": s.get("fase_nome", f"Fase {fase_id}"),
                    "capable_count": 0,
                    "funcionario_ids": [],
                }

            aptos_por_fase[fase_id]["capable_count"] += 1
            func_id = s.get("funcionario_id")
            if func_id:
                aptos_por_fase[fase_id]["funcionario_ids"].append(func_id)

        production_phases = []
        for c in capacities:
            fase_nome = c.get("fase_nome", "")
            if fase_nome not in NON_PRODUCTION_PHASES:
                production_phases.append(c)

        at_risk_phases = []
        risk_breakdown = {"critical": 0, "high": 0, "medium": 0, "ok": 0}

        for cap in production_phases:
            fase_id = cap.get("fase_id")
            if not fase_id:
                continue

            apto_data = aptos_por_fase.get(fase_id, {"capable_count": 0, "funcionario_ids": []})
            capable_count = apto_data["capable_count"]

            if capable_count <= 1:
                risk_level = "CRITICAL"
                risk_breakdown["critical"] += 1
            elif capable_count < min_capable:
                risk_level = "HIGH"
                risk_breakdown["high"] += 1
            elif capable_count < min_capable + 2:
                risk_level = "MEDIUM"
                risk_breakdown["medium"] += 1
            else:
                risk_level = "OK"
                risk_breakdown["ok"] += 1

            if risk_level in ("CRITICAL", "HIGH", "MEDIUM"):
                at_risk_phases.append({
                    "fase_id": fase_id,
                    "fase_nome": cap.get("fase_nome", f"Fase {fase_id}"),
                    "capable_count": capable_count,
                    "risk_level": risk_level,
                    "is_spof": capable_count <= 1,
                    "gap_to_min": max(0, min_capable - capable_count),
                })

        at_risk_phases.sort(key=lambda x: x["capable_count"])

        confidence = self._calculate_confidence(
            base_trust=TRUST_INDEX.get("FuncionariosFasesAptos", 55),
            coverage_pct=100,
            sample_size=len(skills),
        )

        spof_count = sum(1 for p in at_risk_phases if p["is_spof"])
        logger.info(f"Skills risk: {len(at_risk_phases)} at risk, {spof_count} SPOF")

        return {
            "data": {
                "total_production_phases": len(production_phases),
                "phases_at_risk": len(at_risk_phases),
                "spof_count": spof_count,
                "risk_breakdown": risk_breakdown,
                "at_risk_phases": at_risk_phases[:20],
                "total_skill_records": len(skills),
                "unique_phases_with_skills": len(aptos_por_fase),
            },
            "data_confidence": confidence,
            "trust_status": self._get_trust_status(confidence),
            "semantic_label": SEMANTIC_LABELS.get("skills", "risco de competências"),
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "min_capable_threshold": min_capable,
                "source": "curated",
                "warning": "Não considera turnos/férias/disponibilidade real",
            },
        }

    # =========================================================================
    # QUALITY ANALYSIS
    # =========================================================================

    def get_quality(self, top_errors: int = 10, group_by: str = "error") -> Dict[str, Any]:
        """Get quality analysis from error records."""
        logger.info(f"Calculating quality analysis (group by: {group_by})")

        curated = self._get_active_curated()
        if not curated:
            return self._empty_response("quality", "Sem dados - execute ingestão primeiro")

        errors = curated.get("quality_events", [])

        if not errors:
            return {
                "data": {
                    "total_errors": 0,
                    "message": "Nenhum erro registado",
                },
                "data_confidence": TRUST_INDEX.get("OrdemFabricoErros", 67),
                "trust_status": "OK",
                "semantic_label": SEMANTIC_LABELS.get("quality", "análise de qualidade"),
                "metadata": {
                    "query_time": datetime.now(timezone.utc).isoformat(),
                    "source": "curated",
                },
            }

        total_errors = len(errors)
        with_fase = sum(1 for e in errors if e.get("fase_id"))

        grouped: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "quantidade_total": 0})

        for e in errors:
            if group_by == "error":
                key = e.get("erro_tipo", "Unknown")
            elif group_by == "phase":
                key = e.get("fase_id", "Unknown")
            else:
                key = e.get("erro_tipo", "Unknown")

            grouped[key]["count"] += 1
            grouped[key]["quantidade_total"] += e.get("quantidade", 1)

        top_items = sorted(
            grouped.items(),
            key=lambda x: x[1]["count"],
            reverse=True,
        )[:top_errors]

        with_fase_pct = (with_fase / total_errors * 100) if total_errors else 0
        confidence = self._calculate_confidence(
            base_trust=TRUST_INDEX.get("OrdemFabricoErros", 67),
            coverage_pct=with_fase_pct,
            sample_size=total_errors,
        )

        logger.info(f"Quality: {total_errors} errors, {len(grouped)} types")

        return {
            "data": {
                "total_errors": total_errors,
                "unique_error_types": len(grouped),
                "with_fase_culpada": with_fase,
                "with_fase_culpada_pct": round(with_fase_pct, 1),
                "grouped_by": group_by,
                "top_items": [
                    {
                        "key": k,
                        "count": v["count"],
                        "quantidade_total": v["quantidade_total"],
                        "pct_of_total": round(v["count"] / total_errors * 100, 1),
                    }
                    for k, v in top_items
                ],
            },
            "data_confidence": confidence,
            "trust_status": "WARNING" if with_fase_pct < 70 else "OK",
            "semantic_label": SEMANTIC_LABELS.get("quality", "análise de qualidade"),
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "top_n": top_errors,
                "group_by": group_by,
                "warning": f"{round(100 - with_fase_pct, 1)}% dos erros sem fase culpada",
                "source": "curated",
            },
        }

    # =========================================================================
    # LEAD TIME
    # =========================================================================

    def get_lead_time(self, days_back: int = 90) -> Dict[str, Any]:
        """Get lead time analysis for completed orders.

        Lead Time = ``data_conclusao`` - ``data_entrada``.
        """
        logger.info("Calculating lead time analysis")

        curated = self._get_active_curated()
        if not curated:
            return self._empty_response("lead_time", "Sem dados - execute ingestão primeiro")

        orders = curated.get("orders", [])

        lead_times: List[Dict[str, Any]] = []

        for o in orders:
            entrada = o.get("data_entrada")
            conclusao = o.get("data_conclusao")

            if not entrada or not conclusao:
                continue

            try:
                if isinstance(entrada, str):
                    entrada = date.fromisoformat(entrada)
                if isinstance(conclusao, str):
                    conclusao = date.fromisoformat(conclusao)

                if hasattr(entrada, 'date'):
                    entrada = entrada.date() if callable(entrada.date) else entrada
                if hasattr(conclusao, 'date'):
                    conclusao = conclusao.date() if callable(conclusao.date) else conclusao

                lt_days = (conclusao - entrada).days

                if lt_days >= 0:
                    lead_times.append({
                        "of_id": o.get("of_id"),
                        "lead_time_days": lt_days,
                        "produto_id": o.get("produto_id"),
                    })
            except Exception as e:
                logger.warning(f"Error calculating lead time: {e}")
                continue

        if not lead_times:
            return self._empty_response(
                "lead_time",
                "Sem ordens concluídas com datas válidas",
            )

        lt_values = sorted([lt["lead_time_days"] for lt in lead_times])

        avg_lt = sum(lt_values) / len(lt_values)
        median_idx = len(lt_values) // 2
        median_lt = lt_values[median_idx]

        distribution = {
            "< 7 dias": sum(1 for lt in lt_values if lt < 7),
            "7-14 dias": sum(1 for lt in lt_values if 7 <= lt < 14),
            "14-30 dias": sum(1 for lt in lt_values if 14 <= lt < 30),
            "30-60 dias": sum(1 for lt in lt_values if 30 <= lt < 60),
            "> 60 dias": sum(1 for lt in lt_values if lt >= 60),
        }

        p90_idx = int(len(lt_values) * 0.9)
        p90_lt = lt_values[min(p90_idx, len(lt_values) - 1)]

        confidence = self._calculate_confidence(
            base_trust=TRUST_INDEX.get("OrdensFabrico", 82),
            coverage_pct=100,
            sample_size=len(lead_times),
        )

        logger.info(f"Lead time: {len(lead_times)} orders, avg {avg_lt:.1f} days")

        return {
            "data": {
                "total_completed_orders": len(lead_times),
                "avg_lead_time_days": round(avg_lt, 1),
                "median_lead_time_days": median_lt,
                "min_lead_time_days": min(lt_values),
                "max_lead_time_days": max(lt_values),
                "p90_lead_time_days": p90_lt,
                "distribution": distribution,
            },
            "data_confidence": confidence,
            "trust_status": "OK",
            "semantic_label": SEMANTIC_LABELS.get("lead_time", "lead time observado"),
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "days_back": days_back,
                "source": "curated",
                "calculation": "lead_time = data_conclusao - data_entrada",
            },
        }

    # =========================================================================
    # MOLD CONFLICTS
    # =========================================================================

    def get_mold_conflicts(self) -> Dict[str, Any]:
        """Get potential mold conflicts.

        WARNING: ``DataPrevista`` has only ~4.8% coverage, so this is very
        limited (and therefore reported as BLOCKED).
        """
        logger.info("Calculating mold conflicts (limited by DataPrevista coverage)")

        curated = self._get_active_curated()
        if not curated:
            return self._empty_response("mold_conflicts", "Sem dados - execute ingestão primeiro")

        phases = curated.get("order_phases", [])

        phases_with_mold = [
            p for p in phases
            if p.get("molde_id") and (p.get("data_inicio") or p.get("data_fim"))
        ]

        by_mold: Dict[str, List] = defaultdict(list)
        for p in phases_with_mold:
            by_mold[p["molde_id"]].append(p)

        conflicts = []
        for molde_id, uses in by_mold.items():
            if len(uses) > 1:
                open_uses = [u for u in uses if not u.get("data_fim")]
                if len(open_uses) > 1:
                    conflicts.append({
                        "molde_id": molde_id,
                        "concurrent_uses": len(open_uses),
                        "of_ids": [u.get("of_id") for u in open_uses[:5]],
                    })

        coverage_pct = (len(phases_with_mold) / len(phases) * 100) if phases else 0

        logger.info(f"Mold conflicts: {len(conflicts)} potential conflicts")

        return {
            "data": {
                "conflicts": conflicts[:20],
                "total_conflicts": len(conflicts),
                "phases_analyzed": len(phases),
                "phases_with_mold_and_date": len(phases_with_mold),
                "unique_molds": len(by_mold),
                "data_limitation": "DataPrevista coverage is only ~4.8%",
            },
            "data_confidence": 4.8,
            "trust_status": "BLOCKED",
            "semantic_label": SEMANTIC_LABELS.get("mold_conflict", "conflito potencial"),
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "data_prevista_coverage_pct": round(coverage_pct, 1),
                "warning": "Resultados não confiáveis devido a baixa cobertura de DataPrevista",
                "source": "curated",
            },
        }
