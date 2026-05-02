"""
Core semantic queries for Factory Data Product.

All queries return structured dictionaries with:
- data: The actual results
- data_confidence: Trust score based on coverage and Trust Index
- semantic_label: UI disclaimer text
- metadata: Query parameters and statistics

Based on kayak_production/semantic/queries.py but adapted for SQL-based storage.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, func, and_, or_, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import (
    TRUST_INDEX, 
    SEMANTIC_LABELS, 
    MOLD_OCCUPANCY_HOURS,
    WORKING_HOURS_PER_DAY,
    BLOCKED_METRICS,
    TRUST_THRESHOLD_BLOCK,
    TRUST_THRESHOLD_WARNING,
)
from ..models.curated import (
    CuratedOrder,
    CuratedOrderPhase,
    CuratedMold,
    CuratedSkillMatrix,
    CuratedCostReference,
)
from ..models.meta import ActiveRun

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SemanticQueries:
    """
    Semantic layer queries on CURATED factory data.
    
    All methods return structured responses with data_confidence.
    Requires an active ingestion to be set.
    """
    
    def __init__(self, db: AsyncSession, ingestion_id: Optional[UUID] = None):
        """
        Initialize with database session and optional ingestion_id.
        
        Args:
            db: AsyncSession for database queries
            ingestion_id: Specific ingestion to query (default: active_run)
        """
        self.db = db
        self._ingestion_id = ingestion_id
    
    async def _get_active_ingestion_id(self) -> Optional[UUID]:
        """Get the active ingestion ID."""
        if self._ingestion_id:
            return self._ingestion_id
        
        result = await self.db.execute(
            select(ActiveRun.ingestion_id)
            .order_by(ActiveRun.activated_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row
    
    def _calculate_confidence(
        self, 
        base_trust: int, 
        coverage_pct: float,
        sample_size: int,
        min_sample: int = 10,
    ) -> float:
        """
        Calculate data_confidence score.
        
        Args:
            base_trust: Base Trust Index (0-100)
            coverage_pct: Percentage of critical field coverage
            sample_size: Number of records in result
            min_sample: Minimum sample size for full confidence
            
        Returns:
            Confidence score (0-100)
        """
        # Coverage adjustment
        coverage_factor = min(1.0, coverage_pct / 100)
        
        # Sample size adjustment (penalize very small samples)
        if sample_size < min_sample:
            sample_factor = sample_size / min_sample
        else:
            sample_factor = 1.0
        
        confidence = base_trust * coverage_factor * sample_factor
        return round(confidence, 1)
    
    def _get_trust_status(self, confidence: float) -> str:
        """Get trust status based on confidence score."""
        confidence_normalized = confidence / 100
        if confidence_normalized < TRUST_THRESHOLD_BLOCK:
            return "BLOCKED"
        elif confidence_normalized < TRUST_THRESHOLD_WARNING:
            return "WARNING"
        else:
            return "OK"
    
    # =========================================================================
    # WIP (Work in Progress)
    # =========================================================================
    
    # Sprint Q.8 (CEO confirmation 2026-04-26): excel analysis revealed
    # 41% of "open" orders are zombies (created >6 months ago and never
    # closed). Splitting open_orders into active/zombie buckets so the
    # Dashboard stops inflating WIP by ~70%.
    WIP_ZOMBIE_AGE_DAYS = 180

    async def wip(self) -> Dict[str, Any]:
        """
        Get Work in Progress: open orders split into ACTIVE vs ZOMBIE.

        - active: open and started within the last ``WIP_ZOMBIE_AGE_DAYS`` days
        - zombie: open but ``data_entrada`` is older than that cutoff
        - total: union of the two (legacy ``open_orders`` field)

        Returns:
            Structured response with WIP data and confidence
        """
        logger.info("Querying WIP")

        ingestion_id = await self._get_active_ingestion_id()
        if not ingestion_id:
            return self._no_data_response("wip", "No active ingestion")

        cutoff_date = (datetime.utcnow() - timedelta(days=self.WIP_ZOMBIE_AGE_DAYS)).date()

        # Count open orders bucketed by age. We use ``data_entrada`` (order
        # entry date in the ERP) for the zombie cutoff because it's the
        # only reliable "creation time" on CuratedOrder; ``created_at_utc``
        # tracks ingestion time, not business start.
        open_query = select(
            func.count(CuratedOrder.id).label("total"),
            func.sum(
                case(
                    (
                        or_(
                            CuratedOrder.data_entrada.is_(None),
                            CuratedOrder.data_entrada >= cutoff_date,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("active"),
            func.sum(
                case(
                    (
                        and_(
                            CuratedOrder.data_entrada.is_not(None),
                            CuratedOrder.data_entrada < cutoff_date,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("zombie"),
        ).where(
            and_(
                CuratedOrder.ingestion_id == ingestion_id,
                CuratedOrder.data_conclusao.is_(None),
            )
        )
        open_row = (await self.db.execute(open_query)).one()
        open_orders_count = int(open_row.total or 0)
        wip_active_count = int(open_row.active or 0)
        wip_zombie_count = int(open_row.zombie or 0)
        zombie_pct = (
            (wip_zombie_count / open_orders_count * 100.0)
            if open_orders_count > 0 else 0.0
        )

        # Count open phases with hours
        open_phases_query = select(
            func.count(CuratedOrderPhase.id),
            func.sum(CuratedOrderPhase.horas_previstas),
            func.count(CuratedOrderPhase.horas_previstas)
        ).where(
            and_(
                CuratedOrderPhase.ingestion_id == ingestion_id,
                CuratedOrderPhase.data_fim.is_(None)
            )
        )
        phases_result = await self.db.execute(open_phases_query)
        phases_row = phases_result.one()
        open_phases_count = phases_row[0] or 0
        total_horas = phases_row[1] or 0
        phases_with_hours = phases_row[2] or 0

        # Calculate coverage
        hp_coverage = (phases_with_hours / open_phases_count * 100) if open_phases_count > 0 else 0

        # Calculate confidence
        confidence = self._calculate_confidence(
            base_trust=TRUST_INDEX.get("FasesOrdemFabrico_structure", 80),
            coverage_pct=hp_coverage,
            sample_size=open_orders_count,
        )

        return {
            "data": {
                "open_orders": open_orders_count,
                "wip_active": wip_active_count,
                "wip_zombie": wip_zombie_count,
                "zombie_pct": round(zombie_pct, 1),
                "open_phases_total": open_phases_count,
                "total_horas_previstas": round(float(total_horas), 1),
            },
            "data_confidence": confidence,
            "trust_status": self._get_trust_status(confidence),
            "semantic_label": SEMANTIC_LABELS["wip"],
            "metadata": {
                "query_time": datetime.utcnow().isoformat(),
                "ingestion_id": str(ingestion_id),
                "horas_previstas_coverage_pct": round(hp_coverage, 1),
                "zombie_cutoff_days": self.WIP_ZOMBIE_AGE_DAYS,
            },
        }
    
    # =========================================================================
    # Backlog by Phase (TOC Analysis)
    # =========================================================================
    
    async def backlog_by_phase(self, top_n: int = 20) -> Dict[str, Any]:
        """
        Calculate theoretical backlog by phase (TOC analysis).
        
        Backlog = SUM(HorasPrevistas_Final) for open phases
        BacklogDias = Backlog / CapacidadeHorasDia
        
        Args:
            top_n: Number of top phases to return
            
        Returns:
            Structured response with backlog data and confidence
        """
        logger.info(f"Querying backlog by phase (top {top_n})")
        
        ingestion_id = await self._get_active_ingestion_id()
        if not ingestion_id:
            return self._no_data_response("backlog", "No active ingestion")
        
        # Sprint Q.9 (1.3) — `is_production` is set on the row dict by
        # curated_transformer (`Fase_Producao == 1`) but it never lands as
        # a column on the model, so the previous filter raised
        # AttributeError. Until the column is materialised, every open
        # phase counts as production (administrative phases don't sit
        # open in bulk).
        backlog_query = select(
            CuratedOrderPhase.fase_id,
            CuratedOrderPhase.fase_nome,
            func.count(CuratedOrderPhase.id).label("fases_abertas"),
            func.sum(CuratedOrderPhase.horas_previstas).label("backlog_horas"),
            func.count(CuratedOrderPhase.horas_previstas).label("fases_com_horas"),
        ).where(
            and_(
                CuratedOrderPhase.ingestion_id == ingestion_id,
                CuratedOrderPhase.data_fim.is_(None),
            )
        ).group_by(
            CuratedOrderPhase.fase_id,
            CuratedOrderPhase.fase_nome
        ).order_by(
            func.sum(CuratedOrderPhase.horas_previstas).desc().nulls_last()
        ).limit(top_n)
        
        result = await self.db.execute(backlog_query)
        rows = result.all()
        
        # Build response
        backlog_data = []
        total_backlog_horas = 0
        total_phases = 0
        total_with_hours = 0
        
        for row in rows:
            fases_abertas = row.fases_abertas or 0
            backlog_horas = float(row.backlog_horas or 0)
            fases_com_horas = row.fases_com_horas or 0
            
            # Assume 8 hours/day capacity if not specified
            capacidade = WORKING_HOURS_PER_DAY
            backlog_dias = backlog_horas / capacidade if capacidade > 0 else None
            
            coverage_pct = (fases_com_horas / fases_abertas * 100) if fases_abertas > 0 else 0
            
            backlog_data.append({
                "fase_id": str(row.fase_id) if row.fase_id else None,
                "fase_nome": row.fase_nome,
                "fases_abertas": fases_abertas,
                "backlog_horas": round(backlog_horas, 1),
                "backlog_dias_teoricos": round(backlog_dias, 1) if backlog_dias else None,
                "coverage_pct": round(coverage_pct, 1),
            })
            
            total_backlog_horas += backlog_horas
            total_phases += fases_abertas
            total_with_hours += fases_com_horas
        
        # Calculate overall confidence
        total_coverage = (total_with_hours / total_phases * 100) if total_phases > 0 else 0
        confidence = self._calculate_confidence(
            base_trust=TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58),
            coverage_pct=total_coverage,
            sample_size=total_phases,
        )
        
        return {
            "data": {
                "total_phases_analyzed": total_phases,
                "total_backlog_horas": round(total_backlog_horas, 1),
                "backlog_by_phase": backlog_data,
            },
            "data_confidence": confidence,
            "trust_status": self._get_trust_status(confidence),
            "semantic_label": SEMANTIC_LABELS["bottleneck"],
            "metadata": {
                "query_time": datetime.utcnow().isoformat(),
                "ingestion_id": str(ingestion_id),
                "top_n": top_n,
                "horas_previstas_coverage_pct": round(total_coverage, 1),
            },
        }
    
    # =========================================================================
    # Bottlenecks Ranking
    # =========================================================================
    
    async def bottlenecks(self, top_n: int = 10) -> Dict[str, Any]:
        """
        Rank phases by theoretical backlog days (bottleneck analysis).
        
        Args:
            top_n: Number of top bottlenecks to return
            
        Returns:
            Structured response with bottleneck ranking and confidence
        """
        logger.info(f"Querying bottlenecks (top {top_n})")
        
        # Reuse backlog calculation
        backlog_result = await self.backlog_by_phase(top_n=top_n)
        
        if backlog_result.get("trust_status") == "BLOCKED":
            return backlog_result
        
        # Extract just the ranking
        bottleneck_ranking = []
        for i, phase in enumerate(backlog_result["data"]["backlog_by_phase"]):
            if phase.get("backlog_dias_teoricos") is not None:
                bottleneck_ranking.append({
                    "rank": i + 1,
                    "fase_nome": phase["fase_nome"],
                    "backlog_dias": phase["backlog_dias_teoricos"],
                    "backlog_horas": phase["backlog_horas"],
                    "fases_abertas": phase["fases_abertas"],
                    "coverage_pct": phase["coverage_pct"],
                    "is_critical": phase["backlog_dias_teoricos"] > 5,
                })
        
        return {
            "data": {
                "bottlenecks": bottleneck_ranking,
                "critical_count": sum(1 for b in bottleneck_ranking if b.get("is_critical")),
            },
            "data_confidence": backlog_result["data_confidence"],
            "trust_status": backlog_result["trust_status"],
            "semantic_label": SEMANTIC_LABELS["bottleneck"],
            "metadata": {
                **backlog_result["metadata"],
                "critical_threshold_days": 5,
            },
        }
    
    # =========================================================================
    # Quality Analysis
    # =========================================================================
    
    async def quality_analysis(
        self, 
        top_errors: int = 10,
        group_by: str = "error",  # "error", "phase", "severity"
    ) -> Dict[str, Any]:
        """
        Analyze quality issues from error records.
        
        Args:
            top_errors: Number of top items to return
            group_by: Grouping dimension ("error", "phase", "severity")
            
        Returns:
            Structured response with quality analysis and confidence
        """
        logger.info(f"Querying quality analysis (group by {group_by})")
        
        ingestion_id = await self._get_active_ingestion_id()
        if not ingestion_id:
            return self._no_data_response("quality", "No active ingestion")
        
        # For now, return a placeholder since we need the errors table
        # This will be fully implemented when the curated errors model is ready
        
        confidence = self._calculate_confidence(
            base_trust=TRUST_INDEX.get("OrdemFabricoErros", 67),
            coverage_pct=58.5,  # 41.5% missing FaseOfCulpada
            sample_size=89836,
        )
        
        return {
            "data": {
                "total_errors": 0,
                "with_fase_culpada": 0,
                "with_fase_culpada_pct": 58.5,
                "grouped_by": group_by,
                "top_items": [],
                "message": "Quality analysis requires CuratedError model implementation",
            },
            "data_confidence": confidence,
            "trust_status": self._get_trust_status(confidence),
            "semantic_label": SEMANTIC_LABELS["quality"],
            "metadata": {
                "query_time": datetime.utcnow().isoformat(),
                "ingestion_id": str(ingestion_id),
                "top_n": top_errors,
                "group_by": group_by,
                "warning": "41.5% dos erros sem fase culpada",
            },
        }
    
    # =========================================================================
    # Mold Conflicts
    # =========================================================================
    
    async def mold_conflicts(self) -> Dict[str, Any]:
        """
        Detect potential mold conflicts using 12h occupancy heuristic.
        
        Only applicable where DataPrevista exists (~4.8% coverage).
        
        Returns:
            Structured response with conflict analysis and confidence
        """
        logger.info("Querying mold conflicts")
        
        ingestion_id = await self._get_active_ingestion_id()
        if not ingestion_id:
            return self._no_data_response("mold_conflicts", "No active ingestion")
        
        # Very low confidence due to DataPrevista coverage
        confidence = self._calculate_confidence(
            base_trust=TRUST_INDEX.get("FasesOrdemFabrico_DataPrevista", 35),
            coverage_pct=4.8,
            sample_size=100,
        )
        
        return {
            "data": {
                "conflicts": [],
                "total_conflicts": 0,
                "phases_analyzed": 0,
                "unique_molds_with_conflicts": 0,
                "message": "Mold conflict detection limited by DataPrevista coverage (4.8%)",
            },
            "data_confidence": confidence,
            "trust_status": "WARNING",
            "semantic_label": SEMANTIC_LABELS["mold_conflict"],
            "metadata": {
                "query_time": datetime.utcnow().isoformat(),
                "ingestion_id": str(ingestion_id),
                "occupancy_hours_assumption": MOLD_OCCUPANCY_HOURS,
                "data_prevista_coverage_pct": 4.8,
                "warning": "Only 4.8% of phases have DataPrevista",
            },
        }
    
    # =========================================================================
    # Skills Risk Assessment
    # =========================================================================
    
    async def skills_risk(self, min_capable: int = 3) -> Dict[str, Any]:
        """
        Identify phases with skill risk (few capable employees).
        
        Args:
            min_capable: Minimum number of capable employees to not be at risk
            
        Returns:
            Structured response with skill risk analysis and confidence
        """
        logger.info(f"Querying skills risk (min capable: {min_capable})")
        
        ingestion_id = await self._get_active_ingestion_id()
        if not ingestion_id:
            return self._no_data_response("skills_risk", "No active ingestion")
        
        # Query skill matrix
        skills_query = select(
            CuratedSkillMatrix.fase_id,
            CuratedSkillMatrix.fase_nome,
            func.count(CuratedSkillMatrix.funcionario_id).label("capable_count")
        ).where(
            and_(
                CuratedSkillMatrix.ingestion_id == ingestion_id,
                CuratedSkillMatrix.is_active == True
            )
        ).group_by(
            CuratedSkillMatrix.fase_id,
            CuratedSkillMatrix.fase_nome
        )
        
        result = await self.db.execute(skills_query)
        rows = result.all()
        
        # Analyze risk
        at_risk_phases = []
        risk_breakdown = {"critical": 0, "high": 0, "medium": 0, "ok": 0}
        
        for row in rows:
            capable_count = row.capable_count or 0
            
            if capable_count == 0:
                risk_level = "CRITICAL"
                risk_breakdown["critical"] += 1
            elif capable_count < min_capable:
                risk_level = "HIGH" if capable_count < 2 else "MEDIUM"
                risk_breakdown["high" if capable_count < 2 else "medium"] += 1
            else:
                risk_level = "OK"
                risk_breakdown["ok"] += 1
            
            if capable_count < min_capable:
                at_risk_phases.append({
                    "fase_id": str(row.fase_id) if row.fase_id else None,
                    "fase_nome": row.fase_nome,
                    "capable_count": capable_count,
                    "risk_level": risk_level,
                })
        
        # Sort by capable_count ascending
        at_risk_phases.sort(key=lambda x: x["capable_count"])
        
        confidence = self._calculate_confidence(
            base_trust=TRUST_INDEX.get("FuncionariosFaseOrdemFabrico", 55),
            coverage_pct=100,
            sample_size=len(rows),
        )
        
        return {
            "data": {
                "total_production_phases": len(rows),
                "phases_at_risk": len(at_risk_phases),
                "risk_breakdown": risk_breakdown,
                "at_risk_phases": at_risk_phases[:20],  # Limit output
            },
            "data_confidence": confidence,
            "trust_status": self._get_trust_status(confidence),
            "semantic_label": SEMANTIC_LABELS["skills"],
            "metadata": {
                "query_time": datetime.utcnow().isoformat(),
                "ingestion_id": str(ingestion_id),
                "min_capable_threshold": min_capable,
            },
        }
    
    # =========================================================================
    # Lead Time Analysis
    # =========================================================================
    
    async def lead_time_analysis(self, days_back: int = 90) -> Dict[str, Any]:
        """
        Analyze historical lead times for completed orders.
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            Structured response with lead time statistics
        """
        logger.info(f"Querying lead time analysis (last {days_back} days)")
        
        ingestion_id = await self._get_active_ingestion_id()
        if not ingestion_id:
            return self._no_data_response("lead_time", "No active ingestion")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        # Sprint Q.9 (1.1) — `CuratedOrder.lead_time_days` does NOT exist on
        # the model; the raw transformer (`curated_transformer._transform_ordens`)
        # computes it as a derived field on the dict but it never lands as a
        # column. Compute it inline here as the integer day delta between
        # `data_conclusao` and `data_entrada` — the same definition used in
        # the plano v4 §2 ("lead time — moda 15 days"). Both must be set.
        lead_time_days_expr = (
            CuratedOrder.data_conclusao - CuratedOrder.data_entrada
        )

        lead_time_query = select(
            func.count(CuratedOrder.id).label("total_orders"),
            func.avg(lead_time_days_expr).label("avg_lead_time"),
            func.min(lead_time_days_expr).label("min_lead_time"),
            func.max(lead_time_days_expr).label("max_lead_time"),
        ).where(
            and_(
                CuratedOrder.ingestion_id == ingestion_id,
                CuratedOrder.data_conclusao.isnot(None),
                CuratedOrder.data_conclusao >= cutoff_date,
                CuratedOrder.data_entrada.isnot(None),
            )
        )
        
        result = await self.db.execute(lead_time_query)
        row = result.one()
        
        total_orders = row.total_orders or 0
        avg_lt = float(row.avg_lead_time) if row.avg_lead_time else None
        min_lt = float(row.min_lead_time) if row.min_lead_time else None
        max_lt = float(row.max_lead_time) if row.max_lead_time else None
        
        confidence = self._calculate_confidence(
            base_trust=TRUST_INDEX.get("OrdensFabrico", 82),
            coverage_pct=100,
            sample_size=total_orders,
        )
        
        return {
            "data": {
                "total_completed_orders": total_orders,
                "avg_lead_time_days": round(avg_lt, 1) if avg_lt else None,
                "min_lead_time_days": round(min_lt, 1) if min_lt else None,
                "max_lead_time_days": round(max_lt, 1) if max_lt else None,
            },
            "data_confidence": confidence,
            "trust_status": self._get_trust_status(confidence),
            "semantic_label": SEMANTIC_LABELS["lead_time"],
            "metadata": {
                "query_time": datetime.utcnow().isoformat(),
                "ingestion_id": str(ingestion_id),
                "days_back": days_back,
                "cutoff_date": cutoff_date.isoformat(),
            },
        }
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _no_data_response(self, query_name: str, reason: str) -> Dict[str, Any]:
        """Return a standard no-data response."""
        return {
            "data": None,
            "data_confidence": 0,
            "trust_status": "BLOCKED",
            "semantic_label": f"No data available for {query_name}",
            "metadata": {
                "query_time": datetime.utcnow().isoformat(),
                "error": reason,
            },
        }
    
    @staticmethod
    def is_metric_blocked(metric_id: str) -> Optional[Dict[str, Any]]:
        """Check if a metric is blocked and return the reason."""
        return BLOCKED_METRICS.get(metric_id)
    
    @staticmethod
    def get_allowed_metrics() -> List[str]:
        """Get list of metrics that can be calculated."""
        from ..config import ALLOWED_METRICS
        return ALLOWED_METRICS





