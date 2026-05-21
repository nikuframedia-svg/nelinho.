"""
ProdPlan ONE - Factory Map Service (Sprint N)
==============================================

Aggregator behind the `/v1/factory-map/*` endpoints. Composes data from
multiple existing sources — no new ORM tables — into the structures the
Factory Map UI (Sprint Z) will consume:

1. **Snapshot** (`snapshot()` — N.1)
   - WIP / bottlenecks / skills_risk from `SemanticQueriesInMemory`
   - Mold status from `CuratedMold`
   - Effective Trust Index + gates (Sprint AA)
   - Strategic KPIs (see `kpis()`)

2. **Per-boat view** (`boat_view()` — N.2)
   - ProductionOrder + its CuratedOrderPhase trajectory
   - Risk flags: LATE_VS_TRANSPORT, QUALITY_RISK_HIGH, MOLD_MAINT_DUE

3. **Projection** (`projection()` — N.3)
   - **Does NOT call CPO** (too heavy, and Sprint P's greedy pipeline
     hasn't landed). Uses historical average durations per (model, phase)
     from curated data to extrapolate a 7-day heatmap. Honest and cheap.

4. **Shortage risks** (`shortage_risks()` — N.4)
   - ROP-based check: `qty_closing` vs `ROPConfig.rop`; no BOM explosion
     (that's Sprint O.2). Surfaces the most-at-risk SKUs.

5. **Line load** (`line_load()` — N.5)
   - Aggregates `ProductionSchedule.scheduled_duration_hours` grouped by
     (phase, date).

6. **Strategic KPIs** (`kpis()` — N.6)
   - WIP, throughput_units_today, defect_rate, OTD. Throughput €/dia
     returns `"unavailable"` until Sprint Q.0 ships ProductPricing.

Design constraints
------------------
* **Read-only** — does NOT mutate any table.
* **Best-effort** — any source can be missing (no curated data ingested,
  no CPO run yet, no mold table populated); each method degrades with a
  clear `availability` block instead of raising.
* **Cache-friendly** — `snapshot()` is the expensive read and lives
  behind a short Redis TTL keyed by tenant + active ingestion.

Q.67.6.C4 — decomposition
-------------------------
The class body used to weigh ~1000 lines. It now composes three mixins
that live next to this file:

* `factory_map.snapshot.SnapshotMixin` — `snapshot()` orchestration,
  concurrent fan-out, per-source DB summaries, semantic helper.
* `factory_map.risk_flags.RiskFlagsMixin` — KPIs, defect-rate / bottleneck
  DB fallbacks, throughput band, trust payload, line load, shortage risks.
* `factory_map.trajectory.TrajectoryMixin` — boat view + projection.

The dataclasses (`Availability`, `RiskFlag`) and the snapshot-cache
module-level helpers (`_snapshot_cache`, `_snapshot_cache_get`,
`_snapshot_cache_put`, `_reset_snapshot_cache_for_tests`) are re-exported
here so existing imports and tests keep working untouched.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.factory_data_product.services.factory_map.risk_flags import (
    Availability,
    RiskFlag,
    RiskFlagsMixin,
)
from src.factory_data_product.services.factory_map.snapshot import (
    SnapshotMixin,
    _reset_snapshot_cache_for_tests,
    _snapshot_cache,
    _snapshot_cache_get,
    _snapshot_cache_put,
)
from src.factory_data_product.services.factory_map.trajectory import (
    TrajectoryMixin,
)

logger = logging.getLogger(__name__)


# Re-export so callers and tests can keep using
# `from src.factory_data_product.services.factory_map_service import ...`.
__all__ = [
    "Availability",
    "FactoryMapService",
    "RiskFlag",
    "_reset_snapshot_cache_for_tests",
    "_snapshot_cache",
    "_snapshot_cache_get",
    "_snapshot_cache_put",
]


class FactoryMapService(SnapshotMixin, RiskFlagsMixin, TrajectoryMixin):
    """Aggregator façade. Instantiate per request; methods are independent.

    The class itself only carries the constructor — every endpoint method
    lives on one of the three mixins above. The MRO matters: `Snapshot`
    first (it consumes `kpis`/`line_load` from `RiskFlags` and the boat /
    projection helpers from `Trajectory`), but each method name is unique
    across the mixins so the MRO never has to pick.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        semantic_service: Any = None,
        session_factory: Any = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        # Dependency-injected so tests can pass a stub; real callers use the
        # in-memory semantic service via `get_semantic_service()`.
        self._semantic = semantic_service
        # Q.54.C — when provided, `snapshot()` fans its independent DB reads
        # out concurrently, each on its OWN session (a single AsyncSession
        # is not safe for concurrent use). Tests pass a FakeSession and no
        # factory → the snapshot stays serial on the shared session, which
        # keeps the deterministic-queue test fixtures valid.
        self._session_factory = session_factory
