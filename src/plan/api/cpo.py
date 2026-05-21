"""Q.67.6.B2 — router agregador do CPO (decomp do god-file 1104L).

Sub-routers por domínio vivem em `src/plan/api/cpo_routers/`:

* ``schedule``   — `/schedule` (sync), `/schedule/async`,
  `/schedule/job/{id}`, `/schedule/job/{id}/approve`.
* ``commits``    — `/commits`, `/commits/{sha}`, `/commits/{sha}/orders`,
  `/commits/{from}/diff/{to}`, `/commits/{sha}/alternatives`,
  `/commits/{sha}/decide`.
* ``timeline``   — `/timeline`.
* ``operations`` — `/operations/{operation_id}/worker-pairs`.

Os símbolos públicos (Pydantic models + helpers `_compute_trust_index_for_schedule`,
`_load_product_prices`, `_extract_mapelites_representatives`, `_resolve_commit_or_404`,
`_relative_delta`, `_format_delta_pct`, `_build_narrative`) continuam acessíveis
via `from src.plan.api.cpo import …` para preservar imports legados
(scheduler_run.py, worker.py, poetiq.py, e characterization tests).
"""

from __future__ import annotations

from fastapi import APIRouter

# ──────────────────────────────────────────────────────────────────────────
# Re-exports — preserve contracto público com call-sites legados:
#   * src/plan/cpo/worker.py importa CPOScheduleRequest.
#   * src/plan/cpo/scheduler_run.py importa _compute_trust_index_for_schedule,
#     _load_product_prices, _extract_mapelites_representatives.
#   * src/copilot/poetiq.py importa _extract_mapelites_representatives.
#   * tests/plan/test_alternatives_and_decision_delta.py importa
#     _build_narrative, _format_delta_pct, _relative_delta.
#   * tests/plan/test_sprint_c_wire_pricing.py importa _load_product_prices.
#   * tests/plan/test_sprint_c_trust_gate.py importa
#     _compute_trust_index_for_schedule.
#   * tests/plan/test_sprint_q_e2e_smoke.py importa CommitDecisionRequest.
# ──────────────────────────────────────────────────────────────────────────

from src.plan.api._cpo_common import (
    _build_narrative,
    _compute_trust_index_for_schedule,
    _extract_mapelites_representatives,
    _format_delta_pct,
    _load_product_prices,
    _relative_delta,
    _resolve_commit_or_404,
)
from src.plan.api.cpo_routers import commits, operations, schedule, timeline
from src.plan.api.cpo_routers.commits import (
    AlternativeEnriched,
    AlternativesResponse,
    CommitDecisionRequest,
    CommitDecisionResponse,
    CommitOrderItem,
    CommitOrdersResponse,
    CommitResponse,
    DiffResponse,
)
from src.plan.api.cpo_routers.operations import (
    WorkerPairItem,
    WorkerPairsResponse,
)
from src.plan.api.cpo_routers.schedule import (
    CPOJobApproveResponse,
    CPOJobStatusResponse,
    CPOScheduleEnqueueResponse,
    CPOScheduleRequest,
    CPOScheduleResponse,
    MachineInput,
)
from src.plan.api.cpo_routers.timeline import (
    TimelineCandidate,
    TimelineResponse,
)

# ──────────────────────────────────────────────────────────────────────────
# Router agregador — mantém o prefix `/v1/plan/cpo` e a tag "CPO v4 Scheduler"
# para não partir o contrato URL (paths e OpenAPI tags inalteradas) nem o
# `src.main:app.include_router(plan_cpo_router)`.
# ──────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/v1/plan/cpo", tags=["CPO v4 Scheduler"])
router.include_router(schedule.router)
router.include_router(commits.router)
router.include_router(timeline.router)
router.include_router(operations.router)

__all__ = [
    "router",
    # Pydantic models
    "AlternativeEnriched", "AlternativesResponse",
    "CPOJobApproveResponse", "CPOJobStatusResponse",
    "CPOScheduleEnqueueResponse", "CPOScheduleRequest", "CPOScheduleResponse",
    "CommitDecisionRequest", "CommitDecisionResponse",
    "CommitOrderItem", "CommitOrdersResponse", "CommitResponse",
    "DiffResponse", "MachineInput",
    "TimelineCandidate", "TimelineResponse",
    "WorkerPairItem", "WorkerPairsResponse",
    # Helpers (re-exported for legacy call-sites)
    "_build_narrative", "_compute_trust_index_for_schedule",
    "_extract_mapelites_representatives", "_format_delta_pct",
    "_load_product_prices", "_relative_delta", "_resolve_commit_or_404",
]
