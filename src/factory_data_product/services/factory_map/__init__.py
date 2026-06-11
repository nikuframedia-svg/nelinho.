"""Q.67.6.C4 — `factory_map_service` decomposition.

This package holds the implementation pieces that `factory_map_service.py`
re-exports as a single façade. The split keeps the original public surface
(class `FactoryMapService`, dataclasses `Availability`/`RiskFlag`, and the
module-level snapshot-cache helpers) untouched.

* `snapshot` — in-memory snapshot cache + the `snapshot` /
  `_gather_snapshot_parts` orchestration + cheap DB summaries used by the
  snapshot.
* `risk_flags` — `Availability` + `RiskFlag` value objects and the KPI /
  risk-style computations (`kpis`, `_defect_rate_from_db`,
  `_bottlenecks_*`, `_throughput_eur_day`, `_trust_payload`, `line_load`,
  `shortage_risks`).

Q.172 (F4.E) — `trajectory` (boat view + projection) removido: os endpoints
que o serviam eram órfãos (zero consumo frontend). Ver DELETION_LOG.md.
"""

from __future__ import annotations
