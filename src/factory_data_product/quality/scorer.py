"""
Quality scoring and Trust Index calculation for Factory Data Product.

Implements:
- Trust Index per segment (as defined in config)
- Data confidence scoring
- Quality report generation with recommendations

Based on kayak_production/curated/quality.py but adapted for SQL-based storage.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from uuid import UUID

from ..config import (
    TRUST_INDEX,
    EXPECTED_VOLUMES,
    SEMANTIC_LABELS,
    TRUST_THRESHOLD_BLOCK,
    TRUST_THRESHOLD_WARNING,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class QualityScorer:
    """
    Calculates quality scores and generates reports for curated data.
    
    All scoring is based on:
    - Base Trust Index from config (derived from data analysis)
    - Actual data quality metrics (coverage, nulls, deviations)
    - Validation results from ingestion
    """
    
    def __init__(
        self,
        curated_data: Dict[str, List[Dict]],
        ingestion_id: Optional[UUID] = None,
        validation_errors: Optional[List[str]] = None,
    ):
        """
        Initialize scorer.
        
        Args:
            curated_data: Dictionary of table name to list of row dicts
            ingestion_id: ID of the ingestion run
            validation_errors: List of validation error messages
        """
        self.data = curated_data
        self.ingestion_id = ingestion_id
        self.validation_errors = validation_errors or []
        self.table_reports: Dict[str, Dict] = {}
    
    def score_all(self) -> Dict[str, Any]:
        """
        Calculate quality scores for all tables.
        
        Returns:
            Overall quality report dictionary
        """
        logger.info("Calculating quality scores")
        
        for name, rows in self.data.items():
            self.table_reports[name] = self._score_table(name, rows)
        
        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence()
        
        # Identify critical issues
        critical_issues = self._identify_critical_issues()
        
        # Generate recommendations
        recommendations = self._generate_recommendations()
        
        # Determine overall status
        if overall_confidence < TRUST_THRESHOLD_BLOCK * 100:
            overall_status = "BLOCKED"
        elif overall_confidence < TRUST_THRESHOLD_WARNING * 100:
            overall_status = "WARNING"
        else:
            overall_status = "OK"
        
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "ingestion_id": str(self.ingestion_id) if self.ingestion_id else None,
            "tables": self.table_reports,
            "overall_confidence": overall_confidence,
            "overall_status": overall_status,
            "critical_issues": critical_issues,
            "critical_issues_count": len(critical_issues),
            "recommendations": recommendations,
            "semantic_labels": SEMANTIC_LABELS,
            "thresholds": {
                "block": TRUST_THRESHOLD_BLOCK * 100,
                "warning": TRUST_THRESHOLD_WARNING * 100,
            },
        }
        
        return report
    
    def _score_table(self, name: str, rows: List[Dict]) -> Dict[str, Any]:
        """
        Score a single table.
        
        Args:
            name: Table name
            rows: List of row dictionaries
            
        Returns:
            Table quality report
        """
        row_count = len(rows)
        
        # Base trust index
        trust_index = TRUST_INDEX.get(name, 50)
        
        # Null analysis
        null_analysis = self._analyze_nulls(rows)
        
        # Expected volume check
        expected = EXPECTED_VOLUMES.get(name, {}).get("expected")
        deviation_pct = None
        volume_status = "OK"
        if expected:
            deviation_pct = round((row_count - expected) / expected * 100, 2)
            if abs(deviation_pct) > 20:
                volume_status = "WARNING"
            if abs(deviation_pct) > 50:
                volume_status = "CRITICAL"
        
        # Critical fields coverage (table-specific)
        critical_coverage = self._check_critical_coverage(name, rows)
        
        # Adjust trust index based on actual data quality
        adjusted_trust = self._adjust_trust_index(name, trust_index, critical_coverage)
        
        # Determine status
        if adjusted_trust < TRUST_THRESHOLD_BLOCK * 100:
            status = "BLOCKED"
        elif adjusted_trust < TRUST_THRESHOLD_WARNING * 100:
            status = "WARNING"
        else:
            status = "OK"
        
        return {
            "table_name": name,
            "row_count": row_count,
            "expected_count": expected,
            "deviation_pct": deviation_pct,
            "volume_status": volume_status,
            "base_trust_index": trust_index,
            "adjusted_trust_index": adjusted_trust,
            "status": status,
            "critical_coverage": critical_coverage,
            "null_summary": null_analysis,
        }
    
    def _analyze_nulls(self, rows: List[Dict]) -> Dict[str, Any]:
        """Analyze null values in rows."""
        if not rows:
            return {"total_null_cells": 0, "high_null_columns": []}
        
        row_count = len(rows)
        all_columns = set()
        for row in rows:
            all_columns.update(row.keys())
        
        null_counts: Dict[str, int] = {col: 0 for col in all_columns}
        
        for row in rows:
            for col in all_columns:
                val = row.get(col)
                if val is None or val == "":
                    null_counts[col] += 1
        
        total_nulls = sum(null_counts.values())
        high_null_columns = [
            col for col, count in null_counts.items()
            if count / row_count > 0.5
        ]
        
        return {
            "total_null_cells": total_nulls,
            "high_null_columns": high_null_columns,
            "high_null_columns_count": len(high_null_columns),
        }
    
    def _check_critical_coverage(self, name: str, rows: List[Dict]) -> Dict[str, float]:
        """
        Check coverage of critical fields for each table.
        
        Args:
            name: Table name
            rows: List of row dictionaries
            
        Returns:
            Coverage metrics (0-100%)
        """
        if not rows:
            return {}
        
        row_count = len(rows)
        coverage: Dict[str, float] = {}
        
        def calc_coverage(field: str) -> float:
            filled = sum(1 for r in rows if r.get(field) is not None and r.get(field) != "")
            return round(filled / row_count * 100, 1)
        
        def calc_nonzero_coverage(field: str) -> float:
            filled = sum(1 for r in rows if (r.get(field) or 0) > 0)
            return round(filled / row_count * 100, 1)
        
        if name == "OrdensFabrico":
            coverage["DataCriacao"] = calc_coverage("Of_DataCriacao")
            coverage["DataAcabamento"] = calc_coverage("Of_DataAcabamento")
            coverage["is_open"] = round(sum(1 for r in rows if r.get("is_open")) / row_count * 100, 1)
        
        elif name == "FasesOrdemFabrico":
            coverage["HorasPrevistas_Final"] = calc_coverage("HorasPrevistas_Final")
            coverage["DataPrevista"] = calc_coverage("FaseOf_DataPrevista")
            coverage["Inicio"] = calc_coverage("FaseOf_Inicio")
            coverage["Fim"] = calc_coverage("FaseOf_Fim")
            coverage["is_phase_open"] = round(sum(1 for r in rows if r.get("is_phase_open")) / row_count * 100, 1)
        
        elif name == "Funcionarios":
            coverage["ValorHora_Valid"] = calc_nonzero_coverage("FuncionarioValorHora")
            coverage["Active"] = round(sum(1 for r in rows if r.get("is_active")) / row_count * 100, 1)
        
        elif name == "OrdemFabricoErros":
            coverage["FaseCulpada"] = round(sum(1 for r in rows if r.get("has_fase_culpada")) / row_count * 100, 1)
        
        elif name == "FasesStandardModelos":
            coverage["HorasPrevistas_Filled"] = calc_nonzero_coverage("ProdutoFase_HorasPrevistas")
        
        elif name == "Fases":
            coverage["is_production"] = round(sum(1 for r in rows if r.get("is_production")) / row_count * 100, 1)
            coverage["CapacidadeHorasDia"] = calc_nonzero_coverage("Fase_CapacidadeHorasDia")
        
        return coverage
    
    def _adjust_trust_index(
        self,
        name: str,
        base_trust: int,
        critical_coverage: Dict[str, float],
    ) -> int:
        """
        Adjust trust index based on actual data quality.
        
        Args:
            name: Table name
            base_trust: Base trust index from config
            critical_coverage: Coverage metrics
            
        Returns:
            Adjusted trust index (0-100)
        """
        adjustment = 0
        
        # Penalize low coverage of critical fields
        for field, coverage in critical_coverage.items():
            if coverage < 30:
                adjustment -= 15
            elif coverage < 50:
                adjustment -= 10
            elif coverage < 80:
                adjustment -= 5
        
        # Specific adjustments
        if name == "FasesOrdemFabrico":
            # Heavy penalty for low HorasPrevistas coverage
            hp_coverage = critical_coverage.get("HorasPrevistas_Final", 0)
            if hp_coverage < 30:
                adjustment -= 20
            elif hp_coverage < 50:
                adjustment -= 15
        
        elif name == "OrdemFabricoErros":
            # Penalty for missing FaseCulpada
            if critical_coverage.get("FaseCulpada", 0) < 60:
                adjustment -= 10
        
        # Clamp to valid range
        adjusted = max(0, min(100, base_trust + adjustment))
        
        return adjusted
    
    def _calculate_overall_confidence(self) -> float:
        """
        Calculate weighted average confidence across all tables.
        
        Returns:
            Overall confidence score (0-100)
        """
        if not self.table_reports:
            return 0.0
        
        # Weight by row count (larger tables have more impact)
        total_rows = sum(r["row_count"] for r in self.table_reports.values())
        
        if total_rows == 0:
            return 0.0
        
        weighted_sum = sum(
            r["adjusted_trust_index"] * r["row_count"]
            for r in self.table_reports.values()
        )
        
        return round(weighted_sum / total_rows, 2)
    
    def _identify_critical_issues(self) -> List[str]:
        """
        Identify critical issues that need attention.
        
        Returns:
            List of critical issue descriptions
        """
        issues = []
        
        for name, report in self.table_reports.items():
            # Volume deviation
            if report["volume_status"] == "CRITICAL":
                issues.append(
                    f"⚠️ {name}: Row count deviates {report['deviation_pct']}% from expected"
                )
            
            # Low trust index
            if report["adjusted_trust_index"] < 50:
                issues.append(
                    f"🔴 {name}: Low trust index ({report['adjusted_trust_index']})"
                )
            
            # Critical coverage issues
            for field, coverage in report["critical_coverage"].items():
                if coverage < 30:
                    issues.append(
                        f"⚠️ {name}.{field}: Critical coverage only {coverage:.1f}%"
                    )
        
        # Add validation errors
        for error in self.validation_errors:
            issues.append(f"❌ Validation: {error}")
        
        return issues
    
    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate actionable recommendations based on quality analysis.
        
        Returns:
            List of recommendation objects
        """
        recommendations = []
        
        # Check FasesOrdemFabrico HorasPrevistas
        if "FasesOrdemFabrico" in self.table_reports:
            coverage = self.table_reports["FasesOrdemFabrico"]["critical_coverage"]
            hp_cov = coverage.get("HorasPrevistas_Final", 0)
            
            if hp_cov < 50:
                recommendations.append({
                    "priority": "HIGH",
                    "type": "data_improvement",
                    "table": "FasesOrdemFabrico",
                    "field": "HorasPrevistas",
                    "message": f"HorasPrevistas coverage is only {hp_cov:.1f}%. "
                               "Over 50% of values are zero/null. "
                               "Consider improving standard hours coverage.",
                    "action": "Review FaseOf_HorasPrevistas semantics with business",
                })
            
            dp_cov = coverage.get("DataPrevista", 0)
            if dp_cov < 10:
                recommendations.append({
                    "priority": "MEDIUM",
                    "type": "data_limitation",
                    "table": "FasesOrdemFabrico",
                    "field": "DataPrevista",
                    "message": f"DataPrevista only available for ~{dp_cov:.1f}% of phases. "
                               "Cannot use for global capacity planning.",
                    "action": "Label mold conflict analysis as 'potential' not 'confirmed'",
                })
        
        # Check standards duplicates
        if "FasesStandardModelos" in self.table_reports:
            # Would need to check for duplicates in data
            pass
        
        # Check error attribution
        if "OrdemFabricoErros" in self.table_reports:
            coverage = self.table_reports["OrdemFabricoErros"]["critical_coverage"]
            fc_cov = coverage.get("FaseCulpada", 0)
            
            if fc_cov < 60:
                recommendations.append({
                    "priority": "MEDIUM",
                    "type": "data_improvement",
                    "table": "OrdemFabricoErros",
                    "field": "FaseOfCulpada",
                    "message": f"Over {100 - fc_cov:.1f}% of errors missing FaseOfCulpada. "
                               "Quality analysis by phase will be incomplete.",
                    "action": "Improve error registration to include culprit phase",
                })
        
        # Check employee ValorHora
        if "Funcionarios" in self.table_reports:
            coverage = self.table_reports["Funcionarios"]["critical_coverage"]
            vh_cov = coverage.get("ValorHora_Valid", 0)
            
            if vh_cov < 80:
                recommendations.append({
                    "priority": "LOW",
                    "type": "data_limitation",
                    "table": "Funcionarios",
                    "field": "ValorHora",
                    "message": f"Many employees missing valid ValorHora ({100 - vh_cov:.1f}%). "
                               "Use median/trimmed values for cost calculations.",
                    "action": "Label all costs as 'theoretical estimated'",
                })
        
        # Always add semantic labeling recommendation
        recommendations.append({
            "priority": "INFO",
            "type": "ui_guidance",
            "message": "All cost/capacity metrics should be labeled as 'theoretical/estimated' in the UI.",
            "semantic_labels": SEMANTIC_LABELS,
        })
        
        return recommendations
    
    def get_table_trust(self, table_name: str) -> Optional[int]:
        """Get the trust index for a specific table."""
        if table_name in self.table_reports:
            return self.table_reports[table_name]["adjusted_trust_index"]
        return TRUST_INDEX.get(table_name)
    
    def get_field_coverage(self, table_name: str, field_name: str) -> Optional[float]:
        """Get the coverage percentage for a specific field."""
        if table_name in self.table_reports:
            return self.table_reports[table_name]["critical_coverage"].get(field_name)
        return None





