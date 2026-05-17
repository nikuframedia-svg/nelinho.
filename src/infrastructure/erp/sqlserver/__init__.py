"""Nelo ERP adapter (SQL Server). **DEPRECATED — use src.adapters.nelo instead.**

This module was written against the schema described in
PP1_NELO_Blueprint_v2.0.md §14 (tables `OrdensFabrico`, `FasesOrdemFabrico`,
`Funcionarios`, `Moldes` with 510 rows, `Fases` 41 active, …). The 2026-05-12
live schema discovery against `fabrica.nelo.eu:1039 / MAR-KAYAKS` revealed
**different table names** (`ORDEMFABRICO`, `OF_FP`, `ENTIDADE`, `MOLDES` with
91 rows, `FASES_PRODUCAO` with 71 phases, …). See
`agent_docs/mar_kayaks_schema_discovery.md` for the real schema and
`src/adapters/nelo/{models,schemas,services}.py` for the replacement.

This package is kept importable so any old references don't blow up at
import time, but every method now emits a `DeprecationWarning`. Migrate
callers to `src.adapters.nelo.services` and delete this package in a
follow-up sprint.
"""

import warnings

warnings.warn(
    "src.infrastructure.erp.sqlserver.NeloERPAdapter is deprecated and uses "
    "incorrect table names vs the real MAR-KAYAKS schema. Use "
    "src.adapters.nelo.services instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .nelo_erp import NeloERPAdapter, NeloERPError

__all__ = ["NeloERPAdapter", "NeloERPError"]
