"""
Trust Heatmap — Data Quality Visualization
==========================================

Generates trust index heatmaps for data quality monitoring:
- Trust by segment (Fases, Ordens, Funcionários, etc.)
- Trust by KPI domain
- Historical trust trends
- Regression detection

Used for:
- Data quality dashboards
- Alerting on trust degradation
- Identifying data improvement priorities
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from src.factory_data_product.config import TRUST_INDEX, BLOCKED_METRICS, ALLOWED_METRICS

logger = logging.getLogger(__name__)


class TrustStatus(str, Enum):
    """Trust status categories."""
    EXCELLENT = "excellent"   # >= 85
    GOOD = "good"            # 70-84
    WARNING = "warning"      # 50-69
    CRITICAL = "critical"    # < 50


class TrustTrend(str, Enum):
    """Trust trend direction."""
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"


@dataclass
class TrustCell:
    """Single cell in trust heatmap."""
    
    segment: str
    domain: str
    trust_value: float
    status: TrustStatus
    
    # Metadata
    coverage_pct: float = 0.0
    record_count: int = 0
    null_count: int = 0
    
    # Trend (from history)
    trend: Optional[TrustTrend] = None
    previous_value: Optional[float] = None
    delta: float = 0.0
    
    # Issues
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class TrustHeatmapRow:
    """Row in trust heatmap (one segment)."""
    
    segment: str
    cells: Dict[str, TrustCell] = field(default_factory=dict)
    average_trust: float = 0.0
    min_trust: float = 0.0
    max_trust: float = 0.0
    status: TrustStatus = TrustStatus.GOOD


@dataclass
class TrustHeatmap:
    """Complete trust heatmap."""
    
    rows: Dict[str, TrustHeatmapRow] = field(default_factory=dict)
    domains: List[str] = field(default_factory=list)
    
    # Aggregates
    overall_trust: float = 0.0
    overall_status: TrustStatus = TrustStatus.GOOD
    
    # Segments by status
    excellent_segments: List[str] = field(default_factory=list)
    good_segments: List[str] = field(default_factory=list)
    warning_segments: List[str] = field(default_factory=list)
    critical_segments: List[str] = field(default_factory=list)
    
    # Metadata
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ingestion_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/API."""
        return {
            "overall_trust": self.overall_trust,
            "overall_status": self.overall_status.value,
            "domains": self.domains,
            "segments": {
                name: {
                    "average_trust": row.average_trust,
                    "min_trust": row.min_trust,
                    "max_trust": row.max_trust,
                    "status": row.status.value,
                    "cells": {
                        domain: {
                            "trust_value": cell.trust_value,
                            "status": cell.status.value,
                            "coverage_pct": cell.coverage_pct,
                            "trend": cell.trend.value if cell.trend else None,
                            "delta": cell.delta,
                            "issues": cell.issues,
                            "suggestions": cell.suggestions,
                        }
                        for domain, cell in row.cells.items()
                    },
                }
                for name, row in self.rows.items()
            },
            "summary": {
                "excellent": self.excellent_segments,
                "good": self.good_segments,
                "warning": self.warning_segments,
                "critical": self.critical_segments,
            },
            "generated_at": self.generated_at.isoformat(),
            "ingestion_id": self.ingestion_id,
        }


class TrustHeatmapGenerator:
    """
    Generates trust heatmaps from data quality metrics.
    
    Usage:
        generator = TrustHeatmapGenerator()
        heatmap = generator.generate()
        
        # Get critical segments
        critical = heatmap.critical_segments
        
        # Check for regression
        if generator.detect_regression(previous_heatmap, current_heatmap):
            alert("Trust regression detected!")
    """
    
    # Domains for heatmap columns
    DOMAINS = [
        "structure",     # ID fields, relationships
        "timing",        # Dates, durations
        "quantities",    # Hours, counts
        "references",    # FKs, model refs
        "quality",       # Error data, flags
    ]
    
    # Mapping of segments to their primary domains
    SEGMENT_DOMAIN_MAP = {
        "OrdensFabrico": ["structure", "timing", "references"],
        "FasesOrdemFabrico_structure": ["structure", "references"],
        "FasesOrdemFabrico_Tempos": ["timing"],
        "FasesOrdemFabrico_HorasPrevistas": ["quantities"],
        "FasesOrdemFabrico_DataPrevista": ["timing"],
        "Funcionarios": ["structure"],
        "FuncionariosFaseOrdemFabrico": ["structure", "references"],
        "FuncionariosFasesAptos": ["structure", "references"],
        "Fases": ["structure"],
        "Moldes": ["structure", "references"],
        "Modelos": ["structure"],
        "FasesStandardModelos": ["quantities", "references"],
        "OrdemFabricoErros": ["quality", "references"],
        "Erros": ["structure"],
    }
    
    def __init__(self):
        self._history: List[TrustHeatmap] = []
        self._regression_threshold = 5.0  # Alert if trust drops > 5%
    
    def generate(
        self,
        ingestion_id: Optional[str] = None,
        custom_trust: Optional[Dict[str, float]] = None,
    ) -> TrustHeatmap:
        """
        Generate a trust heatmap.
        
        Args:
            ingestion_id: ID of the ingestion to analyze
            custom_trust: Optional custom trust values to use
        
        Returns:
            TrustHeatmap with all cells populated
        """
        trust_values = custom_trust or TRUST_INDEX
        
        heatmap = TrustHeatmap(
            domains=self.DOMAINS,
            ingestion_id=ingestion_id,
        )
        
        # Generate rows for each segment
        for segment, trust in trust_values.items():
            row = self._generate_row(segment, trust, trust_values)
            heatmap.rows[segment] = row
            
            # Categorize by status
            if row.status == TrustStatus.EXCELLENT:
                heatmap.excellent_segments.append(segment)
            elif row.status == TrustStatus.GOOD:
                heatmap.good_segments.append(segment)
            elif row.status == TrustStatus.WARNING:
                heatmap.warning_segments.append(segment)
            else:
                heatmap.critical_segments.append(segment)
        
        # Calculate overall trust
        if trust_values:
            heatmap.overall_trust = sum(trust_values.values()) / len(trust_values)
            heatmap.overall_status = self._get_status(heatmap.overall_trust)
        
        # Add to history
        self._history.append(heatmap)
        
        return heatmap
    
    def _generate_row(
        self,
        segment: str,
        trust: float,
        all_trust: Dict[str, float],
    ) -> TrustHeatmapRow:
        """Generate a heatmap row for a segment."""
        row = TrustHeatmapRow(segment=segment)
        
        # Get domains for this segment
        domains = self.SEGMENT_DOMAIN_MAP.get(segment, ["structure"])
        
        # Generate cells for each domain
        cell_trusts = []
        for domain in self.DOMAINS:
            if domain in domains:
                # This domain is relevant for this segment
                cell_trust = trust
            else:
                # Domain not directly relevant, use N/A or average
                cell_trust = trust * 0.9  # Slight discount for indirect
            
            cell = TrustCell(
                segment=segment,
                domain=domain,
                trust_value=cell_trust,
                status=self._get_status(cell_trust),
            )
            
            # Add issues/suggestions based on trust level
            if cell_trust < 50:
                cell.issues.append(f"Critical data quality in {domain}")
                cell.suggestions.append(f"Prioritize {domain} data cleanup for {segment}")
            elif cell_trust < 70:
                cell.issues.append(f"Data quality below threshold in {domain}")
                cell.suggestions.append(f"Review {domain} data for {segment}")
            
            row.cells[domain] = cell
            cell_trusts.append(cell_trust)
        
        # Calculate row aggregates
        if cell_trusts:
            row.average_trust = sum(cell_trusts) / len(cell_trusts)
            row.min_trust = min(cell_trusts)
            row.max_trust = max(cell_trusts)
            row.status = self._get_status(row.average_trust)
        
        return row
    
    def _get_status(self, trust: float) -> TrustStatus:
        """Get status category for trust value."""
        if trust >= 85:
            return TrustStatus.EXCELLENT
        elif trust >= 70:
            return TrustStatus.GOOD
        elif trust >= 50:
            return TrustStatus.WARNING
        else:
            return TrustStatus.CRITICAL
    
    def detect_regression(
        self,
        previous: Optional[TrustHeatmap],
        current: TrustHeatmap,
    ) -> Tuple[bool, List[str]]:
        """
        Detect trust regression between heatmaps.
        
        Args:
            previous: Previous heatmap (or None)
            current: Current heatmap
        
        Returns:
            (has_regression, list of regressed segments)
        """
        if previous is None:
            return False, []
        
        regressed = []
        
        for segment, current_row in current.rows.items():
            if segment in previous.rows:
                prev_row = previous.rows[segment]
                delta = current_row.average_trust - prev_row.average_trust
                
                if delta < -self._regression_threshold:
                    regressed.append(segment)
                    
                    # Update trend in current
                    for domain, cell in current_row.cells.items():
                        cell.trend = TrustTrend.DEGRADING
                        cell.previous_value = prev_row.average_trust
                        cell.delta = delta
        
        return len(regressed) > 0, regressed
    
    def get_improvement_priorities(
        self,
        heatmap: TrustHeatmap,
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get prioritized list of data improvements.
        
        Args:
            heatmap: Trust heatmap to analyze
            top_n: Number of top priorities to return
        
        Returns:
            List of improvement priorities
        """
        priorities = []
        
        # Collect all segments with issues
        for segment, row in heatmap.rows.items():
            if row.status in [TrustStatus.WARNING, TrustStatus.CRITICAL]:
                impact = 100 - row.average_trust
                
                # Find which KPIs are affected
                affected_kpis = []
                for metric_id, info in BLOCKED_METRICS.items():
                    if segment.lower() in str(info.get("required_data", [])).lower():
                        affected_kpis.append(metric_id)
                
                priorities.append({
                    "segment": segment,
                    "current_trust": row.average_trust,
                    "status": row.status.value,
                    "impact_score": impact,
                    "affected_kpis": affected_kpis,
                    "suggestions": [
                        sugg
                        for cell in row.cells.values()
                        for sugg in cell.suggestions
                    ],
                })
        
        # Sort by impact score
        priorities.sort(key=lambda x: x["impact_score"], reverse=True)
        
        return priorities[:top_n]
    
    def generate_alerts(
        self,
        heatmap: TrustHeatmap,
    ) -> List[Dict[str, Any]]:
        """
        Generate alerts based on heatmap.
        
        Args:
            heatmap: Trust heatmap to analyze
        
        Returns:
            List of alerts
        """
        alerts = []
        
        # Critical segments
        for segment in heatmap.critical_segments:
            alerts.append({
                "level": "critical",
                "segment": segment,
                "message": f"Critical data quality for {segment} (trust < 50%)",
                "action": "Immediate data cleanup required",
            })
        
        # Warning segments
        for segment in heatmap.warning_segments:
            row = heatmap.rows[segment]
            alerts.append({
                "level": "warning",
                "segment": segment,
                "message": f"Data quality warning for {segment} (trust: {row.average_trust:.1f}%)",
                "action": "Schedule data review",
            })
        
        # Overall trust
        if heatmap.overall_status == TrustStatus.CRITICAL:
            alerts.append({
                "level": "critical",
                "segment": "OVERALL",
                "message": f"Overall data quality is critical (trust: {heatmap.overall_trust:.1f}%)",
                "action": "System-wide data quality review needed",
            })
        
        return alerts


# Singleton instance
_generator: Optional[TrustHeatmapGenerator] = None


def get_trust_heatmap_generator() -> TrustHeatmapGenerator:
    """Get the global trust heatmap generator."""
    global _generator
    if _generator is None:
        _generator = TrustHeatmapGenerator()
    return _generator





