"""
Factory Data Product CLI
========================

Command-line interface for ingestion management.
"""

from src.factory_data_product.cli.commands import (
    cli_ingest,
    cli_validate,
    cli_report,
    cli_list_ingestions,
    cli_activate,
    cli_rollback,
)

__all__ = [
    "cli_ingest",
    "cli_validate",
    "cli_report",
    "cli_list_ingestions",
    "cli_activate",
    "cli_rollback",
]


