"""
Schema Drift Detector — P2 Enterprise Feature
==============================================

Detects schema changes between Excel ingestions:
- New columns added
- Columns removed
- Column renames (heuristic)
- Type changes (where detectable)

On drift detection:
- WARNING: New columns → proceed with warning
- BLOCKING: Critical columns removed → block ingestion
- INFO: Minor type changes → log only
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class DriftSeverity(str, Enum):
    """Severity of schema drift."""
    INFO = "info"          # Cosmetic changes, proceed
    WARNING = "warning"    # Notable changes, proceed with caution
    BLOCKING = "blocking"  # Critical changes, block ingestion


class DriftType(str, Enum):
    """Types of schema drift."""
    COLUMN_ADDED = "column_added"
    COLUMN_REMOVED = "column_removed"
    COLUMN_RENAMED = "column_renamed"
    TYPE_CHANGED = "type_changed"
    SHEET_ADDED = "sheet_added"
    SHEET_REMOVED = "sheet_removed"


@dataclass
class DriftItem:
    """Single drift detection item."""
    
    drift_type: DriftType
    severity: DriftSeverity
    sheet_name: str
    column_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    message: str = ""
    suggestion: Optional[str] = None


@dataclass
class DriftReport:
    """Complete drift analysis report."""
    
    has_drift: bool = False
    has_blocking: bool = False
    items: List[DriftItem] = field(default_factory=list)
    summary: str = ""
    
    # Stats
    columns_added: int = 0
    columns_removed: int = 0
    columns_renamed: int = 0
    sheets_added: int = 0
    sheets_removed: int = 0
    
    # Timestamps
    baseline_ingestion_id: Optional[str] = None
    baseline_timestamp: Optional[datetime] = None
    current_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_item(self, item: DriftItem) -> None:
        """Add a drift item to the report."""
        self.items.append(item)
        self.has_drift = True
        
        if item.severity == DriftSeverity.BLOCKING:
            self.has_blocking = True
        
        # Update stats
        if item.drift_type == DriftType.COLUMN_ADDED:
            self.columns_added += 1
        elif item.drift_type == DriftType.COLUMN_REMOVED:
            self.columns_removed += 1
        elif item.drift_type == DriftType.COLUMN_RENAMED:
            self.columns_renamed += 1
        elif item.drift_type == DriftType.SHEET_ADDED:
            self.sheets_added += 1
        elif item.drift_type == DriftType.SHEET_REMOVED:
            self.sheets_removed += 1
    
    def generate_summary(self) -> str:
        """Generate human-readable summary."""
        if not self.has_drift:
            return "No schema drift detected. Schema is stable."
        
        parts = []
        
        if self.has_blocking:
            parts.append("⛔ BLOCKING DRIFT DETECTED")
        else:
            parts.append("⚠️ Schema drift detected")
        
        changes = []
        if self.columns_added > 0:
            changes.append(f"{self.columns_added} column(s) added")
        if self.columns_removed > 0:
            changes.append(f"{self.columns_removed} column(s) removed")
        if self.columns_renamed > 0:
            changes.append(f"{self.columns_renamed} column(s) renamed")
        if self.sheets_added > 0:
            changes.append(f"{self.sheets_added} sheet(s) added")
        if self.sheets_removed > 0:
            changes.append(f"{self.sheets_removed} sheet(s) removed")
        
        if changes:
            parts.append("Changes: " + ", ".join(changes))
        
        self.summary = " | ".join(parts)
        return self.summary
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "has_drift": self.has_drift,
            "has_blocking": self.has_blocking,
            "summary": self.summary or self.generate_summary(),
            "stats": {
                "columns_added": self.columns_added,
                "columns_removed": self.columns_removed,
                "columns_renamed": self.columns_renamed,
                "sheets_added": self.sheets_added,
                "sheets_removed": self.sheets_removed,
            },
            "items": [
                {
                    "drift_type": item.drift_type.value,
                    "severity": item.severity.value,
                    "sheet_name": item.sheet_name,
                    "column_name": item.column_name,
                    "old_value": item.old_value,
                    "new_value": item.new_value,
                    "message": item.message,
                    "suggestion": item.suggestion,
                }
                for item in self.items
            ],
            "baseline_ingestion_id": self.baseline_ingestion_id,
            "baseline_timestamp": self.baseline_timestamp.isoformat() if self.baseline_timestamp else None,
            "current_timestamp": self.current_timestamp.isoformat(),
        }


# Onda 3.5 — column/sheet definitions sourced from the central catalogue.
# The pre-existing literals here used names that don't exist in the real
# Folha_IA_extra.xlsx (`OF_Id`, `OF_Referencia`, `Modelo_Referencia`,
# `FaseStandardModelo_*`, etc.) — drift detection would fire BLOCKING on
# every ingest because it was looking for ghost columns. The central
# catalogue tracks the actual workbook headers.
from src.factory_data_product.excel_columns import (
    CRITICAL_COLUMNS,
    CRITICAL_SHEETS,
)


@dataclass
class SchemaSnapshot:
    """Snapshot of Excel schema at a point in time."""
    
    ingestion_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sheets: Dict[str, Set[str]] = field(default_factory=dict)  # sheet_name -> column names
    column_types: Dict[str, Dict[str, str]] = field(default_factory=dict)  # sheet_name -> {col: type}
    
    @classmethod
    def from_parsed_excel(cls, parsed_data: Dict[str, "SheetData"], ingestion_id: Optional[str] = None) -> "SchemaSnapshot":
        """Create snapshot from parsed Excel data."""
        snapshot = cls(ingestion_id=ingestion_id)
        
        for sheet_name, sheet_data in parsed_data.items():
            snapshot.sheets[sheet_name] = set(sheet_data.headers)
        
        return snapshot
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SchemaSnapshot":
        """Create from dictionary (for storage/retrieval)."""
        snapshot = cls(
            ingestion_id=data.get("ingestion_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(timezone.utc),
        )
        
        for sheet_name, columns in data.get("sheets", {}).items():
            snapshot.sheets[sheet_name] = set(columns)
        
        for sheet_name, types in data.get("column_types", {}).items():
            snapshot.column_types[sheet_name] = types
        
        return snapshot
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "ingestion_id": self.ingestion_id,
            "timestamp": self.timestamp.isoformat(),
            "sheets": {name: list(cols) for name, cols in self.sheets.items()},
            "column_types": self.column_types,
        }


class SchemaDriftDetector:
    """
    Detects schema drift between Excel file versions.
    
    Usage:
        detector = SchemaDriftDetector()
        
        # First ingestion - establish baseline
        detector.set_baseline(parsed_excel)
        
        # Subsequent ingestions - check for drift
        report = detector.detect_drift(new_parsed_excel)
        
        if report.has_blocking:
            raise DriftBlockingError(report)
    """
    
    def __init__(self):
        self._baseline: Optional[SchemaSnapshot] = None
        self._history: List[SchemaSnapshot] = []
        
        # Threshold for column rename similarity (0.0 to 1.0)
        self.rename_similarity_threshold = 0.8
    
    def set_baseline(
        self,
        parsed_data: Dict[str, Any],
        ingestion_id: Optional[str] = None,
    ) -> SchemaSnapshot:
        """
        Set the baseline schema from parsed Excel data.
        
        Args:
            parsed_data: Dictionary of sheet_name -> SheetData
            ingestion_id: ID of the baseline ingestion
        
        Returns:
            The created SchemaSnapshot
        """
        self._baseline = SchemaSnapshot.from_parsed_excel(parsed_data, ingestion_id)
        self._history.append(self._baseline)
        logger.info(f"Schema baseline set with {len(self._baseline.sheets)} sheets")
        return self._baseline
    
    def set_baseline_from_dict(self, data: Dict) -> SchemaSnapshot:
        """Set baseline from stored dictionary."""
        self._baseline = SchemaSnapshot.from_dict(data)
        return self._baseline
    
    def get_baseline(self) -> Optional[SchemaSnapshot]:
        """Get current baseline snapshot."""
        return self._baseline
    
    def detect_drift(
        self,
        current_data: Dict[str, Any],
        ingestion_id: Optional[str] = None,
    ) -> DriftReport:
        """
        Detect schema drift between baseline and current data.
        
        Args:
            current_data: Dictionary of sheet_name -> SheetData (with .headers)
            ingestion_id: ID of the current ingestion
        
        Returns:
            DriftReport with all detected changes
        """
        report = DriftReport()
        
        if self._baseline is None:
            # No baseline - this is the first ingestion
            logger.info("No baseline schema - skipping drift detection")
            report.summary = "First ingestion - no baseline to compare"
            return report
        
        report.baseline_ingestion_id = self._baseline.ingestion_id
        report.baseline_timestamp = self._baseline.timestamp
        
        # Create current snapshot
        current_snapshot = SchemaSnapshot.from_parsed_excel(current_data, ingestion_id)
        
        # Compare sheets
        self._check_sheets(report, current_snapshot)
        
        # Compare columns within common sheets
        self._check_columns(report, current_snapshot)
        
        # Generate summary
        report.generate_summary()
        
        # Store in history
        self._history.append(current_snapshot)
        
        return report
    
    def _check_sheets(self, report: DriftReport, current: SchemaSnapshot) -> None:
        """Check for added/removed sheets."""
        baseline_sheets = set(self._baseline.sheets.keys())
        current_sheets = set(current.sheets.keys())
        
        # Added sheets
        added = current_sheets - baseline_sheets
        for sheet_name in added:
            severity = DriftSeverity.WARNING
            message = f"New sheet '{sheet_name}' detected"
            suggestion = "Review new sheet and update processing logic if needed"
            
            report.add_item(DriftItem(
                drift_type=DriftType.SHEET_ADDED,
                severity=severity,
                sheet_name=sheet_name,
                message=message,
                suggestion=suggestion,
            ))
        
        # Removed sheets
        removed = baseline_sheets - current_sheets
        for sheet_name in removed:
            # Critical sheets removal is blocking
            if sheet_name in CRITICAL_SHEETS:
                severity = DriftSeverity.BLOCKING
                message = f"CRITICAL sheet '{sheet_name}' is missing"
                suggestion = "This sheet is required. Check if file is correct version."
            else:
                severity = DriftSeverity.WARNING
                message = f"Sheet '{sheet_name}' is missing"
                suggestion = "Verify this is expected. Data from this sheet will not be ingested."
            
            report.add_item(DriftItem(
                drift_type=DriftType.SHEET_REMOVED,
                severity=severity,
                sheet_name=sheet_name,
                message=message,
                suggestion=suggestion,
            ))
    
    def _check_columns(self, report: DriftReport, current: SchemaSnapshot) -> None:
        """Check for column changes within sheets."""
        common_sheets = set(self._baseline.sheets.keys()) & set(current.sheets.keys())
        
        for sheet_name in common_sheets:
            baseline_cols = self._baseline.sheets[sheet_name]
            current_cols = current.sheets[sheet_name]
            
            added_cols = current_cols - baseline_cols
            removed_cols = baseline_cols - current_cols
            
            # Check for potential renames
            renames = self._detect_renames(added_cols, removed_cols)
            renamed_old = {old for old, new in renames}
            renamed_new = {new for old, new in renames}
            
            # Handle renames
            for old_name, new_name in renames:
                report.add_item(DriftItem(
                    drift_type=DriftType.COLUMN_RENAMED,
                    severity=DriftSeverity.WARNING,
                    sheet_name=sheet_name,
                    column_name=new_name,
                    old_value=old_name,
                    new_value=new_name,
                    message=f"Column '{old_name}' appears renamed to '{new_name}'",
                    suggestion=f"Verify rename. Update transformers to use '{new_name}' instead of '{old_name}'",
                ))
            
            # Handle truly new columns (not renamed)
            for col_name in added_cols - renamed_new:
                report.add_item(DriftItem(
                    drift_type=DriftType.COLUMN_ADDED,
                    severity=DriftSeverity.INFO,
                    sheet_name=sheet_name,
                    column_name=col_name,
                    message=f"New column '{col_name}' in sheet '{sheet_name}'",
                    suggestion="Review if this column contains useful data for processing",
                ))
            
            # Handle truly removed columns (not renamed)
            for col_name in removed_cols - renamed_old:
                critical_cols = CRITICAL_COLUMNS.get(sheet_name, set())
                
                if col_name in critical_cols:
                    severity = DriftSeverity.BLOCKING
                    message = f"CRITICAL column '{col_name}' is missing from sheet '{sheet_name}'"
                    suggestion = "This column is required. Cannot proceed without it."
                else:
                    severity = DriftSeverity.WARNING
                    message = f"Column '{col_name}' is missing from sheet '{sheet_name}'"
                    suggestion = "Verify this is expected. Dependent calculations may fail."
                
                report.add_item(DriftItem(
                    drift_type=DriftType.COLUMN_REMOVED,
                    severity=severity,
                    sheet_name=sheet_name,
                    column_name=col_name,
                    message=message,
                    suggestion=suggestion,
                ))
    
    def _detect_renames(
        self,
        added: Set[str],
        removed: Set[str],
    ) -> List[Tuple[str, str]]:
        """
        Detect potential column renames using string similarity.
        
        Returns list of (old_name, new_name) tuples.
        """
        renames = []
        used_added = set()
        
        for old_col in removed:
            best_match = None
            best_score = 0.0
            
            for new_col in added:
                if new_col in used_added:
                    continue
                
                # Calculate similarity
                score = SequenceMatcher(None, old_col.lower(), new_col.lower()).ratio()
                
                if score > self.rename_similarity_threshold and score > best_score:
                    best_match = new_col
                    best_score = score
            
            if best_match:
                renames.append((old_col, best_match))
                used_added.add(best_match)
        
        return renames
    
    def get_history(self) -> List[Dict]:
        """Get schema history as list of dicts."""
        return [s.to_dict() for s in self._history]


class DriftBlockingError(Exception):
    """Exception raised when blocking drift is detected."""
    
    def __init__(self, report: DriftReport):
        self.report = report
        blocking_items = [i for i in report.items if i.severity == DriftSeverity.BLOCKING]
        messages = [i.message for i in blocking_items]
        super().__init__(f"Blocking schema drift detected: {'; '.join(messages)}")


# Singleton instance for global access
_drift_detector: Optional[SchemaDriftDetector] = None


def get_drift_detector() -> SchemaDriftDetector:
    """Get the global drift detector instance."""
    global _drift_detector
    if _drift_detector is None:
        _drift_detector = SchemaDriftDetector()
    return _drift_detector





