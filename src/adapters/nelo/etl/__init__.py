"""Q.20 — ERP→Postgres ETL mirrors for NELO MAR-KAYAKS.

Each mirror reads from the read-only NELO adapter
(:mod:`src.adapters.nelo.services`) and idempotently upserts operational
rows into the ProdPlan ONE Postgres. The :class:`~.runner.EtlRunner`
owns the idempotent write + the ``core.etl_run`` audit trail;
:func:`~.sync.run_nelo_sync` orchestrates the registered mirrors.

Mirrors (one per Q.20 sub-sprint):

* ``master_data``  (Q.20.B) — products, operators, BOM, routing templates
* ``molds``        (Q.20.C) — ERP mold catalogue → ``plan.mold``
* ``skills``       (Q.20.D) — skill catalogue + worker×phase matrix
* ``quality``      (Q.20.E) — error catalogue + rework entries
* ``time_mining``  (Q.20.F) — real durations → routing_template_phase
"""

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror, registered_mirrors, run_nelo_sync

__all__ = [
    "EtlRunner",
    "EtlRunResult",
    "register_mirror",
    "registered_mirrors",
    "run_nelo_sync",
]
