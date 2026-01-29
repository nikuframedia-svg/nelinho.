"""
Ingest Engine — Contrato 010
============================

Main orchestration for ingestion pipeline.

Steps:
1. Receive file, calculate SHA256
2. Check for duplicate (idempotency)
3. Extract sheets/rows → factory_raw.excel_row
4. Run quality gates → factory_meta.quality_check_result
5. If BLOCKING fail → status=failed, STOP
6. Transform → factory_curated.*
7. Mark run as succeeded
8. (Optional) Auto-activate if gates pass
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from src.factory_data_product.models.meta import (
    IngestionRun,
    IngestionStatus,
    QualityGateStatus,
    SourceType,
    ActiveRun,
    QualityCheckResult,
    CheckSeverity,
)
from src.factory_data_product.models.raw import ExcelRow
from src.factory_data_product.ingest.hasher import FileHasher, RowHasher
from src.factory_data_product.ingest.parser import ExcelParser
from src.factory_data_product.ingest.transformer import RawToCuratedTransformer
from src.factory_data_product.ingest.drift_detector import (
    SchemaDriftDetector,
    DriftReport,
    DriftBlockingError,
    get_drift_detector,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """Result of an ingestion."""
    
    success: bool = False
    ingestion_id: Optional[UUID] = None
    status: IngestionStatus = IngestionStatus.RECEIVED
    
    # Stats
    total_rows_raw: int = 0
    total_rows_curated: int = 0
    duration_seconds: float = 0.0
    
    # Quality
    quality_gate_status: QualityGateStatus = QualityGateStatus.PENDING
    quality_checks: List[Dict] = field(default_factory=list)
    blocking_failures: List[str] = field(default_factory=list)
    
    # Schema Drift
    drift_report: Optional[DriftReport] = None
    has_schema_drift: bool = False
    drift_blocking: bool = False
    
    # Idempotency
    is_duplicate: bool = False
    duplicate_of: Optional[UUID] = None
    
    # Errors/warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class IngestEngine:
    """
    Main ingestion engine.
    
    Orchestrates the full pipeline:
    file → RAW → validate → CURATED → activate
    
    Includes Schema Drift Detection (P2 feature):
    - Detects column/sheet changes between ingestions
    - Blocks ingestion if critical columns are missing
    - Warns on new columns or renames
    """
    
    def __init__(self):
        self.parser = ExcelParser()
        self.transformer = RawToCuratedTransformer()
        self.drift_detector = get_drift_detector()
        
        # In-memory storage for demo (would use DB in production)
        self._ingestion_runs: Dict[UUID, IngestionRun] = {}
        self._raw_rows: List[Dict] = []
        self._curated_data: Dict[str, List[Dict]] = {}
        self._quality_checks: List[Dict] = []
        self._active_run: Optional[Dict] = None
        self._schema_history: List[Dict] = []
    
    def ingest(
        self,
        file_path: Path,
        source_type: SourceType = SourceType.UPLOAD,
        created_by: str = "system",
        auto_activate: bool = False,
    ) -> IngestResult:
        """
        Ingest an Excel file.
        
        Args:
            file_path: Path to Excel file
            source_type: How the file was received
            created_by: User/system that initiated
            auto_activate: Whether to auto-activate on success
        
        Returns:
            IngestResult with status and stats
        """
        start_time = time.time()
        result = IngestResult()
        
        try:
            # Step 1: Calculate file hash
            logger.info(f"Step 1: Calculating file hash for {file_path.name}")
            file_hash = FileHasher.hash_file(file_path)
            file_size = file_path.stat().st_size
            
            # Step 2: Check for duplicate
            logger.info("Step 2: Checking for duplicate")
            duplicate = self._find_duplicate(file_hash)
            if duplicate:
                logger.info(f"Duplicate found: {duplicate}")
                result.is_duplicate = True
                result.duplicate_of = duplicate
                result.status = IngestionStatus.SKIPPED
                result.ingestion_id = self._create_skipped_run(
                    file_path, file_size, file_hash, source_type, created_by, duplicate
                )
                result.success = True
                return result
            
            # Step 3: Create ingestion run
            logger.info("Step 3: Creating ingestion run")
            ingestion_id = self._create_ingestion_run(
                file_path, file_size, file_hash, source_type, created_by
            )
            result.ingestion_id = ingestion_id
            
            # Step 4: Parse Excel and check schema drift
            logger.info("Step 4: Parsing Excel file")
            self._update_status(ingestion_id, IngestionStatus.VALIDATING)
            
            parsed = self.parser.parse(file_path)
            
            # Step 4.5: Schema Drift Detection
            logger.info("Step 4.5: Checking for schema drift")
            drift_report = self._check_schema_drift(parsed, ingestion_id)
            result.drift_report = drift_report
            result.has_schema_drift = drift_report.has_drift
            result.drift_blocking = drift_report.has_blocking
            
            if drift_report.has_drift:
                result.warnings.append(drift_report.summary)
            
            if drift_report.has_blocking:
                logger.error(f"Schema drift BLOCKED: {drift_report.summary}")
                self._update_status(ingestion_id, IngestionStatus.FAILED)
                result.status = IngestionStatus.FAILED
                result.errors.append(f"Schema drift blocked ingestion: {drift_report.summary}")
                for item in drift_report.items:
                    if item.severity.value == "blocking":
                        result.blocking_failures.append(item.message)
                result.success = False
                return result
            
            # Step 4.6: Extract to RAW
            logger.info("Step 4.6: Extracting to RAW storage")
            raw_count = self._extract_to_raw_from_parsed(parsed, ingestion_id)
            result.total_rows_raw = raw_count
            
            # Step 5: Run quality gates
            logger.info("Step 5: Running quality gates")
            from src.factory_data_product.quality import QualityRunner
            
            quality_runner = QualityRunner()
            quality_result = quality_runner.run_all_checks(
                ingestion_id=ingestion_id,
                raw_rows=self._get_raw_rows(ingestion_id),
            )
            
            result.quality_checks = quality_result.checks
            result.quality_gate_status = quality_result.overall_status
            result.blocking_failures = quality_result.blocking_failures
            
            self._store_quality_checks(ingestion_id, quality_result.checks)
            self._update_quality_status(ingestion_id, quality_result.overall_status)
            
            # Step 6: Check for blocking failures
            if quality_result.overall_status == QualityGateStatus.FAILED:
                logger.warning(f"Quality gates FAILED: {quality_result.blocking_failures}")
                self._update_status(ingestion_id, IngestionStatus.FAILED)
                result.status = IngestionStatus.FAILED
                result.errors.extend(quality_result.blocking_failures)
                result.success = False
                return result
            
            # Step 7: Transform to CURATED
            logger.info("Step 7: Transforming to CURATED")
            self._update_status(ingestion_id, IngestionStatus.CURATING)
            
            transform_result = self._transform_to_curated(ingestion_id)
            result.total_rows_curated = transform_result.total_curated
            result.warnings.extend(transform_result.warnings)
            
            # Step 8: Mark as succeeded
            logger.info("Step 8: Marking as succeeded")
            self._update_status(ingestion_id, IngestionStatus.SUCCEEDED)
            result.status = IngestionStatus.SUCCEEDED
            result.success = True
            
            # Step 9: Auto-activate if requested
            if auto_activate:
                logger.info("Step 9: Auto-activating")
                self.activate(ingestion_id, created_by)
            
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            result.errors.append(str(e))
            result.success = False
            if result.ingestion_id:
                self._update_status(result.ingestion_id, IngestionStatus.FAILED)
                result.status = IngestionStatus.FAILED
        
        result.duration_seconds = time.time() - start_time
        return result
    
    def activate(
        self,
        ingestion_id: UUID,
        activated_by: str,
    ) -> bool:
        """
        Activate an ingestion run.
        
        This makes the run the "current" data visible through semantic views.
        
        Args:
            ingestion_id: The ingestion to activate
            activated_by: User activating
        
        Returns:
            True if successful
        """
        run = self._ingestion_runs.get(ingestion_id)
        if not run:
            raise ValueError(f"Ingestion {ingestion_id} not found")
        
        if run.status != IngestionStatus.SUCCEEDED:
            raise ValueError(f"Cannot activate ingestion with status {run.status}")
        
        # Update active run
        self._active_run = {
            "active_ingestion_id": ingestion_id,
            "activated_at_utc": datetime.now(timezone.utc),
            "activated_by": activated_by,
        }
        
        logger.info(f"Activated ingestion {ingestion_id} by {activated_by}")
        return True
    
    def rollback(
        self,
        to_ingestion_id: UUID,
        rolled_back_by: str,
        reason: str,
    ) -> bool:
        """
        Rollback to a previous ingestion.
        
        This is a LOGICAL rollback — just swapping active_ingestion_id.
        No data is deleted.
        
        Args:
            to_ingestion_id: The ingestion to rollback to
            rolled_back_by: User performing rollback
            reason: Why rolling back
        
        Returns:
            True if successful
        """
        run = self._ingestion_runs.get(to_ingestion_id)
        if not run:
            raise ValueError(f"Ingestion {to_ingestion_id} not found")
        
        if run.status != IngestionStatus.SUCCEEDED:
            raise ValueError(f"Cannot rollback to ingestion with status {run.status}")
        
        # Update active run
        self._active_run = {
            "active_ingestion_id": to_ingestion_id,
            "activated_at_utc": datetime.now(timezone.utc),
            "activated_by": rolled_back_by,
        }
        
        logger.info(f"Rolled back to ingestion {to_ingestion_id} by {rolled_back_by}: {reason}")
        return True
    
    def get_active_run(self) -> Optional[Dict]:
        """Get the current active run."""
        return self._active_run
    
    def list_ingestions(self) -> List[Dict]:
        """List all ingestion runs."""
        return [
            {
                "id": str(run.id),
                "file_name": run.file_name,
                "status": run.status.value,
                "quality_gate_status": run.quality_gate_status.value,
                "created_at_utc": run.created_at_utc.isoformat(),
                "total_rows_raw": run.total_rows_raw,
            }
            for run in self._ingestion_runs.values()
        ]
    
    # Private methods
    
    def _find_duplicate(self, file_hash: str) -> Optional[UUID]:
        """Find a duplicate ingestion by file hash."""
        for run in self._ingestion_runs.values():
            if run.file_sha256 == file_hash and run.status == IngestionStatus.SUCCEEDED:
                return run.id
        return None
    
    def _create_ingestion_run(
        self,
        file_path: Path,
        file_size: int,
        file_hash: str,
        source_type: SourceType,
        created_by: str,
    ) -> UUID:
        """Create a new ingestion run."""
        run = IngestionRun(
            id=uuid4(),
            created_at_utc=datetime.now(timezone.utc),
            created_by=created_by,
            source_type=source_type,
            file_name=file_path.name,
            file_size_bytes=file_size,
            file_sha256=file_hash,
            status=IngestionStatus.RECEIVED,
            started_at_utc=datetime.now(timezone.utc),
        )
        
        self._ingestion_runs[run.id] = run
        return run.id
    
    def _create_skipped_run(
        self,
        file_path: Path,
        file_size: int,
        file_hash: str,
        source_type: SourceType,
        created_by: str,
        duplicate_of: UUID,
    ) -> UUID:
        """Create a skipped run record."""
        run = IngestionRun(
            id=uuid4(),
            created_at_utc=datetime.now(timezone.utc),
            created_by=created_by,
            source_type=source_type,
            file_name=file_path.name,
            file_size_bytes=file_size,
            file_sha256=file_hash,
            status=IngestionStatus.SKIPPED,
            duplicate_of_ingestion_id=duplicate_of,
        )
        
        self._ingestion_runs[run.id] = run
        return run.id
    
    def _update_status(self, ingestion_id: UUID, status: IngestionStatus) -> None:
        """Update ingestion status."""
        run = self._ingestion_runs.get(ingestion_id)
        if run:
            run.status = status
            if status in [IngestionStatus.SUCCEEDED, IngestionStatus.FAILED]:
                run.completed_at_utc = datetime.now(timezone.utc)
                if run.started_at_utc:
                    run.duration_seconds = (run.completed_at_utc - run.started_at_utc).total_seconds()
    
    def _update_quality_status(self, ingestion_id: UUID, status: QualityGateStatus) -> None:
        """Update quality gate status."""
        run = self._ingestion_runs.get(ingestion_id)
        if run:
            run.quality_gate_status = status
    
    def _extract_to_raw(self, file_path: Path, ingestion_id: UUID) -> int:
        """Extract Excel data to RAW storage."""
        count = 0
        
        for sheet_name, row_num, payload, bk_fields in self.parser.iter_rows(file_path):
            # Calculate hashes
            row_hash = RowHasher.hash_row(payload)
            bk_hash = None
            if bk_fields:
                bk_hash = RowHasher.hash_business_key(bk_fields, payload)
            
            # Store raw row
            raw_row = {
                "id": uuid4(),
                "ingestion_id": ingestion_id,
                "sheet_name": sheet_name,
                "row_number": row_num,
                "row_sha256": row_hash,
                "business_key_sha256": bk_hash,
                "payload_json": payload,
                "ingested_at_utc": datetime.now(timezone.utc),
            }
            
            self._raw_rows.append(raw_row)
            count += 1
        
        # Update run stats
        run = self._ingestion_runs.get(ingestion_id)
        if run:
            run.total_rows_raw = count
        
        return count
    
    def _get_raw_rows(self, ingestion_id: UUID) -> List[Dict]:
        """Get RAW rows for an ingestion."""
        return [r for r in self._raw_rows if r["ingestion_id"] == ingestion_id]
    
    def _store_quality_checks(self, ingestion_id: UUID, checks: List[Dict]) -> None:
        """Store quality check results."""
        for check in checks:
            self._quality_checks.append({
                **check,
                "ingestion_id": ingestion_id,
            })
    
    def _transform_to_curated(self, ingestion_id: UUID) -> Any:
        """Transform RAW to CURATED."""
        raw_rows = self._get_raw_rows(ingestion_id)
        result = self.transformer.transform(raw_rows, ingestion_id)
        
        # Store curated data
        self._curated_data[str(ingestion_id)] = {
            "orders": result.orders,
            "order_phases": result.order_phases,
            "phase_capacities": result.phase_capacities,
            "molds": result.molds,
            "mold_usages": result.mold_usages,
            "quality_events": result.quality_events,
            "skill_matrix": result.skill_matrix,
            "cost_references": result.cost_references,
        }
        
        # Update run stats
        run = self._ingestion_runs.get(ingestion_id)
        if run:
            run.total_rows_curated = result.total_curated
        
        return result
    
    def _check_schema_drift(self, parsed: Any, ingestion_id: UUID) -> DriftReport:
        """
        Check for schema drift between this ingestion and baseline.
        
        If no baseline exists, this ingestion becomes the baseline.
        """
        # Convert parsed result to dict format expected by drift detector
        parsed_dict = {}
        for sheet_name, sheet_data in parsed.sheets.items():
            parsed_dict[sheet_name] = sheet_data
        
        # Check if we have a baseline
        if self.drift_detector.get_baseline() is None:
            # First ingestion - set as baseline
            logger.info("First ingestion - setting schema baseline")
            self.drift_detector.set_baseline(parsed_dict, str(ingestion_id))
            return DriftReport(summary="First ingestion - schema baseline established")
        
        # Detect drift
        report = self.drift_detector.detect_drift(parsed_dict, str(ingestion_id))
        
        if report.has_drift:
            logger.warning(f"Schema drift detected: {report.summary}")
            for item in report.items:
                logger.warning(f"  - [{item.severity.value}] {item.message}")
        
        return report
    
    def _extract_to_raw_from_parsed(self, parsed: Any, ingestion_id: UUID) -> int:
        """Extract already-parsed Excel data to RAW storage."""
        count = 0
        
        for sheet_name, sheet_data in parsed.sheets.items():
            business_key_fields = sheet_data.business_key_fields
            
            for row_num, row in enumerate(sheet_data.rows, start=2):
                # Calculate hashes
                row_hash = RowHasher.hash_row(row)
                bk_hash = None
                if business_key_fields:
                    bk_hash = RowHasher.hash_business_key(business_key_fields, row)
                
                # Store raw row
                raw_row = {
                    "id": uuid4(),
                    "ingestion_id": ingestion_id,
                    "sheet_name": sheet_name,
                    "row_number": row_num,
                    "row_sha256": row_hash,
                    "business_key_sha256": bk_hash,
                    "payload_json": row,
                    "ingested_at_utc": datetime.now(timezone.utc),
                }
                
                self._raw_rows.append(raw_row)
                count += 1
        
        # Update run stats
        run = self._ingestion_runs.get(ingestion_id)
        if run:
            run.total_rows_raw = count
        
        return count
    
    def get_schema_history(self) -> List[Dict]:
        """Get the history of schema snapshots."""
        return self.drift_detector.get_history()
    
    def get_drift_report(self, ingestion_id: UUID) -> Optional[Dict]:
        """Get drift report for a specific ingestion."""
        # For now, return the last report if available
        # In production, this would query from storage
        run = self._ingestion_runs.get(ingestion_id)
        if run:
            return {
                "ingestion_id": str(ingestion_id),
                "schema_history_count": len(self.drift_detector.get_history()),
            }
        return None


