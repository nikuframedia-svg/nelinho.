"""
ProdPlan ONE - TrustIndex Calculator (DEPRECATED — Sprint Q.1)
==============================================================

⚠️  DEPRECATED: This v1 calculator (4 components: Completeness, Validity,
Consistency, Timeliness) has been superseded by the v2 calculator in
`src.dqa.trust_v2` (7+1 components: Completeness, Validity, Freshness,
Consistency, Provenance, Anomaly, Evidence, +Causal Coherence reserved).

New code MUST import from `src.dqa.trust_v2`. The Sprint Q.1 migration
removed the only production consumer of this module (`quality_gates.py`)
and rewired it to v2. This file is kept only as a fallback while we
verify no third-party integrations still reference it; it will be deleted
in a follow-up sprint once a grep confirms zero imports.

Differences vs v2 (see `trust_v2.py` docstring for full table):
- v1 evaluates a request payload's shape (is the dict complete + valid?)
- v2 evaluates factory/order/phase database state (Blueprint v2.0 §4.5)

Calculate TrustIndex (0-1 scale) with 4 components:
- Completeness (30%): % of required fields filled
- Validity (30%): % of values within valid ranges
- Consistency (20%): Cross-field conflicts
- Timeliness (20%): Latency vs SLA
"""

from enum import Enum
from typing import Any, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class DataQualityComponent(Enum):
    """Component weights for TrustIndex calculation."""
    COMPLETENESS = 0.3
    VALIDITY = 0.3
    CONSISTENCY = 0.2
    TIMELINESS = 0.2


class TrustIndexCalculator:
    """
    Calculate TrustIndex for any entity.
    
    TrustIndex (0-1 scale) is a weighted sum of 4 components:
    - Completeness: fraction of required fields filled (30%)
    - Validity: fraction of values within valid ranges (30%)
    - Consistency: cross-field validation (20%)
    - Timeliness: latency vs SLA (20%)
    
    Args:
        required_fields: Dict[field_name, type] - Required fields for completeness
        valid_ranges: Dict[field_name, (min, max)] - Valid ranges for validity check
        sla_latency_seconds: SLA latency in seconds (default: 60)
    """
    
    def __init__(
        self,
        required_fields: Dict[str, type],
        valid_ranges: Dict[str, Tuple[float, float]],
        sla_latency_seconds: int = 60,
    ):
        self.required_fields = required_fields
        self.valid_ranges = valid_ranges
        self.sla_latency_seconds = sla_latency_seconds
    
    def calculate(self, entity: Dict[str, Any], latency_ms: int = 0) -> Dict[str, Any]:
        """
        Calculate TrustIndex (0-1 scale).
        
        Args:
            entity: Entity dictionary to evaluate
            latency_ms: Latency in milliseconds (for timeliness calculation)
        
        Returns:
            {
                trust_index: float (0-1),
                components: {
                    completeness: float,
                    validity: float,
                    consistency: float,
                    timeliness: float,
                },
                issues: List[str],
                repair_recommended: bool,
            }
        """
        completeness = self._calculate_completeness(entity)
        validity = self._calculate_validity(entity)
        consistency = self._calculate_consistency(entity)
        timeliness = self._calculate_timeliness(latency_ms)
        
        # Weighted sum
        trust_index = (
            completeness * DataQualityComponent.COMPLETENESS.value +
            validity * DataQualityComponent.VALIDITY.value +
            consistency * DataQualityComponent.CONSISTENCY.value +
            timeliness * DataQualityComponent.TIMELINESS.value
        )
        
        issues = self._detect_issues(entity, latency_ms)
        repair_recommended = 0.65 <= trust_index < 0.70
        
        result = {
            "trust_index": round(trust_index, 3),
            "components": {
                "completeness": round(completeness, 3),
                "validity": round(validity, 3),
                "consistency": round(consistency, 3),
                "timeliness": round(timeliness, 3),
            },
            "issues": issues,
            "repair_recommended": repair_recommended,
        }
        
        logger.debug(
            f"TrustIndex calculated: {trust_index:.3f} "
            f"(C:{completeness:.2f}, V:{validity:.2f}, Co:{consistency:.2f}, T:{timeliness:.2f})"
        )
        
        return result
    
    def _calculate_completeness(self, entity: Dict[str, Any]) -> float:
        """
        Completeness: fraction of required fields filled.
        
        Returns: 0.0 to 1.0
        """
        if not self.required_fields:
            return 1.0
        
        filled = sum(1 for field in self.required_fields if entity.get(field) is not None)
        return filled / len(self.required_fields)
    
    def _calculate_validity(self, entity: Dict[str, Any]) -> float:
        """
        Validity: fraction of values within valid ranges.
        
        Returns: 0.0 to 1.0
        """
        if not self.valid_ranges:
            return 1.0
        
        invalid_count = 0
        
        for field, (min_val, max_val) in self.valid_ranges.items():
            value = entity.get(field)
            if value is not None:
                try:
                    numeric_value = float(value)
                    if numeric_value < min_val or numeric_value > max_val:
                        invalid_count += 1
                except (ValueError, TypeError):
                    # Non-numeric value outside range check
                    pass
        
        total = len(self.valid_ranges)
        return max(0.0, 1.0 - (invalid_count / total)) if total > 0 else 1.0
    
    def _calculate_consistency(self, entity: Dict[str, Any]) -> float:
        """
        Consistency: check for cross-field conflicts.

        Sprint Q.9 (2.4) — three concrete rules drawn from the NELO
        domain:

        1. **Date ordering** — `data_inicio` / `data_entrada` must not
           be after `data_conclusao` / `data_fim`.
        2. **Quantity sanity** — `quantidade_produzida` cannot exceed
           `quantidade` ordered.
        3. **Worker uniqueness** — when the row carries a list of
           workers (e.g. an allocation peer), no worker should appear
           twice (a person cannot be on the same op twice).

        Each rule violated subtracts ``1/N`` from the score (N =
        number of rules that *applied* — i.e. the relevant fields
        were present). A row where no rule applies returns 1.0.

        Returns: 0.0 to 1.0
        """
        applied = 0
        violations = 0

        # Rule 1 — date ordering
        start = entity.get("data_inicio") or entity.get("data_entrada")
        end = entity.get("data_fim") or entity.get("data_conclusao")
        if start is not None and end is not None:
            applied += 1
            try:
                if start > end:
                    violations += 1
            except TypeError:
                # Non-comparable types — count as violation rather than crash.
                violations += 1

        # Rule 2 — produced quantity cannot exceed ordered quantity
        ordered_qty = entity.get("quantidade")
        produced_qty = entity.get("quantidade_produzida")
        if ordered_qty is not None and produced_qty is not None:
            applied += 1
            try:
                if float(produced_qty) > float(ordered_qty):
                    violations += 1
            except (TypeError, ValueError):
                violations += 1

        # Rule 3 — worker uniqueness (when applicable)
        workers = entity.get("workers")
        if isinstance(workers, (list, tuple)):
            applied += 1
            if len(workers) != len(set(workers)):
                violations += 1

        if applied == 0:
            return 1.0
        return max(0.0, 1.0 - (violations / applied))
    
    def _calculate_timeliness(self, latency_ms: int) -> float:
        """
        Timeliness: latency vs SLA.
        
        - If latency <= SLA: return 1.0
        - If latency > SLA: linear degradation
        
        Returns: 0.0 to 1.0
        """
        latency_sec = latency_ms / 1000.0
        sla_sec = self.sla_latency_seconds
        
        if latency_sec <= sla_sec:
            return 1.0
        else:
            # Linear degradation after SLA
            # Formula: 1 - ((latency - SLA) / SLA)
            degradation = (latency_sec - sla_sec) / sla_sec
            return max(0.0, 1.0 - degradation)
    
    def _detect_issues(self, entity: Dict[str, Any], latency_ms: int) -> List[str]:
        """
        Detect specific data quality issues.
        
        Returns: List of issue descriptions
        """
        issues = []
        
        # Missing required fields
        for field in self.required_fields:
            if entity.get(field) is None:
                issues.append(f"Missing required field: {field}")
        
        # Values out of range
        for field, (min_val, max_val) in self.valid_ranges.items():
            value = entity.get(field)
            if value is not None:
                try:
                    numeric_value = float(value)
                    if numeric_value < min_val or numeric_value > max_val:
                        issues.append(
                            f"Field {field}={numeric_value} outside range [{min_val}, {max_val}]"
                        )
                except (ValueError, TypeError):
                    pass
        
        # Latency
        if latency_ms > self.sla_latency_seconds * 1000:
            issues.append(
                f"Latency {latency_ms}ms exceeds SLA {self.sla_latency_seconds}s"
            )
        
        return issues










