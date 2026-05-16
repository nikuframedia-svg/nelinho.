"""Q.20 — Nelo ERP → Postgres ETL.

The :class:`NeloERPAdapter` reads the ``vw_pp1_*`` views; this package
turns those reads into idempotent writes into the operational schemas
(``core.*`` / ``plan.*`` / ``hr.*`` / ``quality.*``).

* :mod:`runner` — :class:`EtlRunner`, the generic idempotent-upsert
  helper plus the ``core.etl_run`` audit-row lifecycle.
* :mod:`models` — :class:`EtlRun`, the per-execution audit record.
* ``master_data`` / ``molds`` / ``skills`` / ``quality`` / ``time_mining``
  — one mirror module per data domain (added in Q.20.B…F).

Every mirror is idempotent: re-running a sync never duplicates rows.
"""

from .models import EtlRun
from .runner import EtlRunner, EtlRunResult

__all__ = ["EtlRun", "EtlRunner", "EtlRunResult"]
