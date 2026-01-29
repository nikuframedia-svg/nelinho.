"""
SemanticQueriesInMemory — Real Data from CURATED Layer (In-Memory)
==================================================================

Replaces mock data endpoints with real queries against IN-MEMORY curated data.
No PostgreSQL required - uses IngestEngine._curated_data directly.

Every query:
- Filters by active_ingestion_id
- Returns trust metadata
- Is fully explainable
- Source = "curated" (not "mock")

Author: ProdPlan ONE Team
Date: 2026-01-29
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from uuid import UUID
from collections import defaultdict

from ..config import (
    TRUST_INDEX,
    SEMANTIC_LABELS,
    NON_PRODUCTION_PHASES,
    WORKING_HOURS_PER_DAY,
    BLOCKED_METRICS,
    TRUST_THRESHOLD_BLOCK,
    TRUST_THRESHOLD_WARNING,
)

if TYPE_CHECKING:
    from ..ingest.engine import IngestEngine

logger = logging.getLogger(__name__)


class SemanticQueriesInMemory:
    """
    Real semantic queries against IN-MEMORY CURATED data.
    
    Architecture:
    - Uses engine._curated_data[active_ingestion_id] as data source
    - All queries respect the active_ingestion_id filter
    - All responses include trust metadata
    - All calculations are explainable
    - NO DATABASE REQUIRED - works with in-memory data
    
    Usage:
        from factory_data_product.ingest.engine import get_engine
        from factory_data_product.services import get_semantic_service
        
        engine = get_engine()
        service = get_semantic_service(engine)
        result = service.get_wip()
    """
    
    def __init__(self, engine: "IngestEngine"):
        """
        Initialize with IngestEngine instance.
        
        Args:
            engine: IngestEngine instance with _curated_data
        """
        self.engine = engine
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 30  # seconds
    
    def _get_active_curated(self) -> Optional[Dict[str, List[Dict]]]:
        """
        Get curated data for active ingestion.
        
        Returns:
            Dict with curated tables or None if no active ingestion
        """
        active = self.engine.get_active_run()
        if not active:
            logger.warning("No active ingestion run")
            return None
        
        ingestion_id = str(active["active_ingestion_id"])
        data = self.engine._curated_data.get(ingestion_id)
        
        if not data:
            logger.warning(f"No curated data for ingestion {ingestion_id}")
            return None
        
        logger.info(f"Retrieved curated data for ingestion {ingestion_id}")
        return data
    
    def _get_trust_status(self, confidence: float) -> str:
        """
        Get trust status string based on confidence score.
        
        Args:
            confidence: Confidence score 0-100
            
        Returns:
            "OK", "WARNING", or "BLOCKED"
        """
        if confidence >= 85:
            return "OK"
        elif confidence >= 50:
            return "WARNING"
        else:
            return "BLOCKED"
    
    def _calculate_confidence(
        self,
        base_trust: int,
        coverage_pct: float,
        sample_size: int,
        min_sample: int = 10,
    ) -> float:
        """
        Calculate data confidence score.
        
        Args:
            base_trust: Base Trust Index from config (0-100)
            coverage_pct: Percentage of critical field coverage (0-100)
            sample_size: Number of records in result
            min_sample: Minimum sample size for full confidence
            
        Returns:
            Confidence score (0-100)
        """
        # Coverage adjustment
        coverage_factor = min(1.0, coverage_pct / 100)
        
        # Sample size adjustment
        if sample_size < min_sample:
            sample_factor = sample_size / min_sample
        else:
            sample_factor = 1.0
        
        confidence = base_trust * coverage_factor * sample_factor
        return round(confidence, 1)
    
    def _empty_response(self, query_type: str, message: str) -> Dict[str, Any]:
        """
        Return empty/error response structure.
        
        Args:
            query_type: Name of the query (for logging)
            message: Error/status message
            
        Returns:
            Standard response dict with no data
        """
        return {
            "data": None,
            "data_confidence": 0,
            "trust_status": "BLOCKED",
            "semantic_label": message,
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "source": "no_active_ingestion",
                "error": message,
            },
        }
    
    # =========================================================================
    # WIP (Work in Progress)
    # =========================================================================
    
    def get_wip(self) -> Dict[str, Any]:
        """
        Get Work in Progress: open orders and their open phases.
        
        Calculation:
        1. Filter orders where data_conclusao IS NULL
        2. Get all phases linked to these open orders
        3. Sum horas_finais for these phases
        4. Calculate coverage (% of phases with horas_finais)
        
        Trust: Based on FasesOrdemFabrico_HorasPrevistas coverage
        
        Returns:
            Structured response with WIP data and confidence
        """
        logger.info("Calculating WIP from curated data")
        
        curated = self._get_active_curated()
        if not curated:
            return self._empty_response("wip", "Sem dados - execute ingestão primeiro")
        
        orders = curated.get("orders", [])
        phases = curated.get("order_phases", [])
        
        if not orders:
            return self._empty_response("wip", "Sem ordens na camada CURATED")
        
        # Step 1: Find open orders (no data_conclusao)
        open_orders = [o for o in orders if not o.get("data_conclusao")]
        open_order_ids = {o["of_id"] for o in open_orders}
        
        # Step 2: Find phases linked to open orders
        open_phases = [p for p in phases if p.get("of_id") in open_order_ids]
        
        # Step 3: Calculate totals
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
        
        # Step 4: Calculate coverage
        coverage_pct = (phases_with_hours / len(open_phases) * 100) if open_phases else 0
        
        # Determine trust
        base_trust = TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58)
        confidence = self._calculate_confidence(
            base_trust=base_trust,
            coverage_pct=coverage_pct,
            sample_size=len(open_orders),
        )
        
        logger.info(f"WIP: {len(open_orders)} open orders, {len(open_phases)} open phases, {total_horas:.1f}h")
        
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
        """
        Get theoretical backlog by phase.
        
        Backlog = SUM(horas_finais) for open phases, grouped by fase_id
        BacklogDias = backlog_horas / capacidade_horas_dia
        
        Args:
            top_n: Number of top phases to return
            
        Returns:
            Structured response with backlog data and confidence
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
        
        # Get open order IDs
        open_order_ids = {o["of_id"] for o in orders if not o.get("data_conclusao")}
        
        # Build capacity map
        capacity_map = {}
        for c in capacities:
            fase_id = c.get("fase_id")
            cap = c.get("capacidade_horas")
            if fase_id and cap:
                try:
                    capacity_map[fase_id] = float(cap)
                except (ValueError, TypeError):
                    capacity_map[fase_id] = WORKING_HOURS_PER_DAY
        
        # Aggregate by phase
        backlog_by_fase: Dict[str, Dict] = {}
        
        for p in phases:
            # Skip non-open orders
            if p.get("of_id") not in open_order_ids:
                continue
            
            # Skip non-production phases
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
        
        # Calculate derived metrics
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
        
        # Sort by backlog_horas DESC
        results.sort(key=lambda x: x["backlog_horas"], reverse=True)
        
        total_backlog = sum(r["backlog_horas"] for r in results)
        total_phases = sum(r["fases_abertas"] for r in results)
        total_with_hours = sum(1 for r in results if r["coverage_pct"] > 0)
        
        # Calculate confidence
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
        """
        Get bottleneck ranking by backlog days.
        
        Identification thresholds:
        - CRITICAL: backlog_dias > 5
        - HIGH: backlog_dias > 3
        - MEDIUM: backlog_dias > 1
        
        Args:
            top_n: Number of top bottlenecks to return
            
        Returns:
            Structured response with bottleneck ranking
        """
        logger.info(f"Calculating bottleneck ranking (top {top_n})")
        
        CRITICAL_THRESHOLD = 5
        HIGH_THRESHOLD = 3
        MEDIUM_THRESHOLD = 1
        
        # Reuse backlog calculation
        backlog_result = self.get_backlog(top_n=100)
        
        if backlog_result.get("data") is None:
            return self._empty_response("bottlenecks", "Sem dados de backlog")
        
        phases = backlog_result["data"].get("backlog_by_phase", [])
        
        # Sort by backlog_dias
        phases.sort(key=lambda x: x.get("backlog_dias_teoricos", 0), reverse=True)
        
        # Add rank and severity
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
    # SKILLS RISK
    # =========================================================================
    
    def get_skills_risk(self, min_capable: int = 3) -> Dict[str, Any]:
        """
        Get skills risk assessment by phase.
        
        Risk Levels:
        - CRITICAL: 0-1 capable employees (SPOF)
        - HIGH: < min_capable
        - MEDIUM: < min_capable + 2
        - OK: >= min_capable + 2
        
        Args:
            min_capable: Minimum employees for phase to be "safe"
            
        Returns:
            Structured response with skills risk data
        """
        logger.info(f"Calculating skills risk (min capable: {min_capable})")
        
        curated = self._get_active_curated()
        if not curated:
            return self._empty_response("skills_risk", "Sem dados - execute ingestão primeiro")
        
        skills = curated.get("skill_matrix", [])
        capacities = curated.get("phase_capacities", [])
        
        if not skills:
            return self._empty_response("skills_risk", "Sem dados de competências")
        
        # Count capable per phase
        aptos_por_fase: Dict[str, Dict] = {}
        
        for s in skills:
            # Only count if marked as capable
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
        
        # Get production phases from capacities
        production_phases = []
        for c in capacities:
            fase_nome = c.get("fase_nome", "")
            if fase_nome not in NON_PRODUCTION_PHASES:
                production_phases.append(c)
        
        # Calculate risk
        at_risk_phases = []
        risk_breakdown = {"critical": 0, "high": 0, "medium": 0, "ok": 0}
        
        for cap in production_phases:
            fase_id = cap.get("fase_id")
            if not fase_id:
                continue
            
            apto_data = aptos_por_fase.get(fase_id, {"capable_count": 0, "funcionario_ids": []})
            capable_count = apto_data["capable_count"]
            
            # Determine risk level
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
        
        # Sort by capable_count ASC (most critical first)
        at_risk_phases.sort(key=lambda x: x["capable_count"])
        
        # Calculate confidence
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
        """
        Get quality analysis from error records.
        
        Args:
            top_errors: Number of top items to return
            group_by: Grouping dimension ("error", "phase", "severity")
            
        Returns:
            Structured response with quality analysis
        """
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
        
        # Group by dimension
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
        
        # Sort and take top
        top_items = sorted(
            grouped.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:top_errors]
        
        # Calculate confidence
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
        """
        Get lead time analysis for completed orders.
        
        Lead Time = data_conclusao - data_entrada
        
        Args:
            days_back: Number of days to look back (not used for in-memory)
            
        Returns:
            Structured response with lead time statistics
        """
        logger.info(f"Calculating lead time analysis")
        
        curated = self._get_active_curated()
        if not curated:
            return self._empty_response("lead_time", "Sem dados - execute ingestão primeiro")
        
        orders = curated.get("orders", [])
        
        # Calculate lead times for completed orders
        lead_times = []
        
        for o in orders:
            entrada = o.get("data_entrada")
            conclusao = o.get("data_conclusao")
            
            if not entrada or not conclusao:
                continue
            
            try:
                # Parse dates if needed
                if isinstance(entrada, str):
                    entrada = date.fromisoformat(entrada)
                if isinstance(conclusao, str):
                    conclusao = date.fromisoformat(conclusao)
                
                # Handle datetime objects
                if hasattr(entrada, 'date'):
                    entrada = entrada.date() if callable(entrada.date) else entrada
                if hasattr(conclusao, 'date'):
                    conclusao = conclusao.date() if callable(conclusao.date) else conclusao
                
                # Calculate difference
                lt_days = (conclusao - entrada).days
                
                if lt_days >= 0:  # Valid lead time
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
                "Sem ordens concluídas com datas válidas"
            )
        
        # Calculate statistics
        lt_values = sorted([lt["lead_time_days"] for lt in lead_times])
        
        avg_lt = sum(lt_values) / len(lt_values)
        median_idx = len(lt_values) // 2
        median_lt = lt_values[median_idx]
        
        # Distribution buckets
        distribution = {
            "< 7 dias": sum(1 for lt in lt_values if lt < 7),
            "7-14 dias": sum(1 for lt in lt_values if 7 <= lt < 14),
            "14-30 dias": sum(1 for lt in lt_values if 14 <= lt < 30),
            "30-60 dias": sum(1 for lt in lt_values if 30 <= lt < 60),
            "> 60 dias": sum(1 for lt in lt_values if lt >= 60),
        }
        
        # Calculate P90
        p90_idx = int(len(lt_values) * 0.9)
        p90_lt = lt_values[min(p90_idx, len(lt_values) - 1)]
        
        # Calculate confidence
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
        """
        Get potential mold conflicts.
        
        WARNING: DataPrevista has only ~4.8% coverage, so this is very limited.
        
        Returns:
            Structured response with mold conflict analysis
        """
        logger.info("Calculating mold conflicts (limited by DataPrevista coverage)")
        
        curated = self._get_active_curated()
        if not curated:
            return self._empty_response("mold_conflicts", "Sem dados - execute ingestão primeiro")
        
        phases = curated.get("order_phases", [])
        
        # Filter phases with molde_id and dates
        phases_with_mold = [
            p for p in phases
            if p.get("molde_id") and (p.get("data_inicio") or p.get("data_fim"))
        ]
        
        # Group by mold
        by_mold: Dict[str, List] = defaultdict(list)
        for p in phases_with_mold:
            by_mold[p["molde_id"]].append(p)
        
        # Count potential conflicts (molds with multiple concurrent uses)
        conflicts = []
        for molde_id, uses in by_mold.items():
            if len(uses) > 1:
                # Simplified: flag molds with multiple open phases
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
            "data_confidence": 4.8,  # Very low
            "trust_status": "BLOCKED",
            "semantic_label": SEMANTIC_LABELS.get("mold_conflict", "conflito potencial"),
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "data_prevista_coverage_pct": round(coverage_pct, 1),
                "warning": "Resultados não confiáveis devido a baixa cobertura de DataPrevista",
                "source": "curated",
            },
        }
    
    # =========================================================================
    # SUMMARY / OVERVIEW
    # =========================================================================
    
    def get_overview(self) -> Dict[str, Any]:
        """
        Get overview/summary of all curated data.
        
        Returns:
            Structured response with data summary
        """
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


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

_service_instance: Optional[SemanticQueriesInMemory] = None


def get_semantic_service(engine: "IngestEngine") -> SemanticQueriesInMemory:
    """
    Get or create SemanticQueriesInMemory service instance.
    
    Args:
        engine: IngestEngine instance
        
    Returns:
        SemanticQueriesInMemory service
    """
    global _service_instance
    
    if _service_instance is None or _service_instance.engine is not engine:
        _service_instance = SemanticQueriesInMemory(engine)
    
    return _service_instance

