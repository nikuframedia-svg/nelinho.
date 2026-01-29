"""
Quality Runner — Contrato 010
=============================

Executes quality checks and aggregates results.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.factory_data_product.models.meta import QualityGateStatus, CheckSeverity
from src.factory_data_product.quality.gates import (
    QualityCheck,
    CheckResult,
    QUALITY_CHECKS,
)

logger = logging.getLogger(__name__)


@dataclass
class QualityResult:
    """Aggregated quality check results."""
    
    overall_status: QualityGateStatus = QualityGateStatus.PENDING
    checks: List[Dict] = field(default_factory=list)
    
    # Counts
    total_checks: int = 0
    passed_checks: int = 0
    failed_blocking: int = 0
    failed_warning: int = 0
    
    # Details
    blocking_failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class QualityRunner:
    """
    Run quality checks and aggregate results.
    
    BLOCKING checks must all pass for ingestion to proceed.
    WARNING checks are logged but don't fail ingestion.
    """
    
    def __init__(self, checks: Optional[Dict[str, QualityCheck]] = None):
        self.checks = checks or QUALITY_CHECKS
    
    def run_all_checks(
        self,
        ingestion_id: UUID,
        raw_rows: List[Dict],
        context: Optional[Dict] = None,
    ) -> QualityResult:
        """
        Run all quality checks.
        
        Args:
            ingestion_id: The ingestion being validated
            raw_rows: List of RAW row records
            context: Additional context for checks
        
        Returns:
            QualityResult with aggregated status
        """
        context = context or {}
        context["ingestion_id"] = ingestion_id
        
        result = QualityResult()
        result.total_checks = len(self.checks)
        
        for check_id, check in self.checks.items():
            try:
                logger.info(f"Running check: {check_id}")
                check_result = self._run_check(check, raw_rows, context)
                
                # Store result
                result.checks.append({
                    "check_id": check_id,
                    "severity": check.severity.value,
                    "passed": check_result.passed,
                    "details": check_result.details,
                    "message": check_result.message,
                })
                
                # Aggregate
                if check_result.passed:
                    result.passed_checks += 1
                else:
                    if check.severity == CheckSeverity.BLOCKING:
                        result.failed_blocking += 1
                        result.blocking_failures.append(
                            check_result.message or f"Check {check_id} failed"
                        )
                    elif check.severity == CheckSeverity.WARNING:
                        result.failed_warning += 1
                        result.warnings.append(
                            check_result.message or f"Check {check_id} warning"
                        )
                
            except Exception as e:
                logger.error(f"Error running check {check_id}: {e}")
                result.checks.append({
                    "check_id": check_id,
                    "severity": check.severity.value,
                    "passed": False,
                    "details": {"error": str(e)},
                    "message": f"Check error: {str(e)}",
                })
                
                if check.severity == CheckSeverity.BLOCKING:
                    result.failed_blocking += 1
                    result.blocking_failures.append(f"Check {check_id} error: {str(e)}")
        
        # Determine overall status
        if result.failed_blocking > 0:
            result.overall_status = QualityGateStatus.FAILED
        else:
            result.overall_status = QualityGateStatus.PASSED
        
        logger.info(
            f"Quality gates: {result.overall_status.value} "
            f"({result.passed_checks}/{result.total_checks} passed, "
            f"{result.failed_blocking} blocking failures)"
        )
        
        return result
    
    def _run_check(
        self,
        check: QualityCheck,
        raw_rows: List[Dict],
        context: Dict,
    ) -> CheckResult:
        """Run a single check."""
        if check.check_fn:
            return check.check_fn(raw_rows, context)
        else:
            # No check function, pass by default
            return CheckResult(
                check_id=check.check_id,
                severity=check.severity,
                passed=True,
                details={"note": "No check function defined"},
            )
    
    def get_check_info(self, check_id: str) -> Optional[Dict]:
        """Get information about a check."""
        check = self.checks.get(check_id)
        if not check:
            return None
        
        return {
            "check_id": check.check_id,
            "name": check.name,
            "description": check.description,
            "severity": check.severity.value,
        }
    
    def list_checks(self) -> List[Dict]:
        """List all available checks."""
        return [
            {
                "check_id": check.check_id,
                "name": check.name,
                "description": check.description,
                "severity": check.severity.value,
            }
            for check in self.checks.values()
        ]


