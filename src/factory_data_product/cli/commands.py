"""
CLI Commands — Contrato 010
===========================

Commands:
- ingest --file ...
- validate --ingestion-id ...
- report --ingestion-id ...
- list-ingestions
- activate --ingestion-id ...
- rollback --to-ingestion-id ...
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from src.factory_data_product.ingest import IngestEngine
from src.factory_data_product.models.meta import SourceType


# Global engine instance (would be injected in production)
_engine: Optional[IngestEngine] = None


def get_engine() -> IngestEngine:
    """Get or create engine instance."""
    global _engine
    if _engine is None:
        _engine = IngestEngine()
    return _engine


def cli_ingest(file_path: str, auto_activate: bool = False, user: str = "cli_user") -> dict:
    """
    Ingest an Excel file.
    
    Usage:
        ingest --file /path/to/file.xlsx [--auto-activate]
    
    Args:
        file_path: Path to Excel file
        auto_activate: Whether to auto-activate on success
        user: User performing the ingest
    
    Returns:
        Result dict with status and details
    """
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    
    engine = get_engine()
    result = engine.ingest(
        file_path=path,
        source_type=SourceType.UPLOAD,
        created_by=user,
        auto_activate=auto_activate,
    )
    
    return {
        "success": result.success,
        "ingestion_id": str(result.ingestion_id) if result.ingestion_id else None,
        "status": result.status.value,
        "is_duplicate": result.is_duplicate,
        "duplicate_of": str(result.duplicate_of) if result.duplicate_of else None,
        "total_rows_raw": result.total_rows_raw,
        "total_rows_curated": result.total_rows_curated,
        "quality_gate_status": result.quality_gate_status.value,
        "blocking_failures": result.blocking_failures,
        "warnings": result.warnings,
        "errors": result.errors,
        "duration_seconds": round(result.duration_seconds, 2),
    }


def cli_validate(ingestion_id: str) -> dict:
    """
    Get validation report for an ingestion.
    
    Usage:
        validate --ingestion-id <uuid>
    
    Args:
        ingestion_id: UUID of the ingestion
    
    Returns:
        Quality check results
    """
    engine = get_engine()
    
    # In production, this would query the database
    # For demo, we return stored checks
    checks = [c for c in engine._quality_checks if str(c.get("ingestion_id")) == ingestion_id]
    
    return {
        "ingestion_id": ingestion_id,
        "checks": checks,
        "total_checks": len(checks),
        "passed": sum(1 for c in checks if c.get("passed")),
        "failed": sum(1 for c in checks if not c.get("passed")),
    }


def cli_report(ingestion_id: str) -> dict:
    """
    Get detailed report for an ingestion.
    
    Usage:
        report --ingestion-id <uuid>
    
    Args:
        ingestion_id: UUID of the ingestion
    
    Returns:
        Full ingestion report
    """
    engine = get_engine()
    
    try:
        uid = UUID(ingestion_id)
        run = engine._ingestion_runs.get(uid)
        
        if not run:
            return {"error": f"Ingestion not found: {ingestion_id}"}
        
        return {
            "id": str(run.id),
            "file_name": run.file_name,
            "file_size_bytes": run.file_size_bytes,
            "file_sha256": run.file_sha256,
            "status": run.status.value,
            "quality_gate_status": run.quality_gate_status.value,
            "total_rows_raw": run.total_rows_raw,
            "total_rows_curated": run.total_rows_curated,
            "created_at_utc": run.created_at_utc.isoformat(),
            "created_by": run.created_by,
            "duration_seconds": run.duration_seconds,
        }
        
    except ValueError:
        return {"error": f"Invalid UUID: {ingestion_id}"}


def cli_list_ingestions() -> dict:
    """
    List all ingestion runs.
    
    Usage:
        list-ingestions
    
    Returns:
        List of ingestion runs
    """
    engine = get_engine()
    ingestions = engine.list_ingestions()
    
    return {
        "ingestions": ingestions,
        "total": len(ingestions),
    }


def cli_activate(ingestion_id: str, user: str = "cli_user") -> dict:
    """
    Activate an ingestion run.
    
    Usage:
        activate --ingestion-id <uuid>
    
    Args:
        ingestion_id: UUID of the ingestion to activate
        user: User performing activation
    
    Returns:
        Activation result
    """
    engine = get_engine()
    
    try:
        uid = UUID(ingestion_id)
        success = engine.activate(uid, user)
        
        return {
            "success": success,
            "activated_ingestion_id": ingestion_id,
            "activated_by": user,
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }
        
    except ValueError as e:
        return {"error": str(e)}


def cli_rollback(to_ingestion_id: str, reason: str, user: str = "cli_user") -> dict:
    """
    Rollback to a previous ingestion.
    
    Usage:
        rollback --to-ingestion-id <uuid> --reason "..."
    
    Args:
        to_ingestion_id: UUID of the ingestion to rollback to
        reason: Why rolling back
        user: User performing rollback
    
    Returns:
        Rollback result
    """
    engine = get_engine()
    
    try:
        uid = UUID(to_ingestion_id)
        success = engine.rollback(uid, user, reason)
        
        return {
            "success": success,
            "rolled_back_to": to_ingestion_id,
            "reason": reason,
            "rolled_back_by": user,
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
        }
        
    except ValueError as e:
        return {"error": str(e)}


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Factory Data Product CLI",
        prog="factory-data-product",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest Excel file")
    ingest_parser.add_argument("--file", required=True, help="Path to Excel file")
    ingest_parser.add_argument("--auto-activate", action="store_true", help="Auto-activate on success")
    ingest_parser.add_argument("--user", default="cli_user", help="User name")
    
    # validate
    validate_parser = subparsers.add_parser("validate", help="Get validation report")
    validate_parser.add_argument("--ingestion-id", required=True, help="Ingestion UUID")
    
    # report
    report_parser = subparsers.add_parser("report", help="Get ingestion report")
    report_parser.add_argument("--ingestion-id", required=True, help="Ingestion UUID")
    
    # list-ingestions
    subparsers.add_parser("list-ingestions", help="List all ingestions")
    
    # activate
    activate_parser = subparsers.add_parser("activate", help="Activate ingestion")
    activate_parser.add_argument("--ingestion-id", required=True, help="Ingestion UUID")
    activate_parser.add_argument("--user", default="cli_user", help="User name")
    
    # rollback
    rollback_parser = subparsers.add_parser("rollback", help="Rollback to previous ingestion")
    rollback_parser.add_argument("--to-ingestion-id", required=True, help="Target ingestion UUID")
    rollback_parser.add_argument("--reason", required=True, help="Reason for rollback")
    rollback_parser.add_argument("--user", default="cli_user", help="User name")
    
    args = parser.parse_args()
    
    if args.command == "ingest":
        result = cli_ingest(args.file, args.auto_activate, args.user)
    elif args.command == "validate":
        result = cli_validate(args.ingestion_id)
    elif args.command == "report":
        result = cli_report(args.ingestion_id)
    elif args.command == "list-ingestions":
        result = cli_list_ingestions()
    elif args.command == "activate":
        result = cli_activate(args.ingestion_id, args.user)
    elif args.command == "rollback":
        result = cli_rollback(args.to_ingestion_id, args.reason, args.user)
    else:
        parser.print_help()
        sys.exit(1)
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()


