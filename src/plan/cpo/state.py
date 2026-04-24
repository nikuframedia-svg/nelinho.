"""
ProdPlan ONE — CPO v4 FactoryState
===================================

In-memory snapshot of curated-layer data for the scheduler. Loaded once
per schedule run (or cached by active_ingestion_id) to avoid per-op DB
queries during GA fitness evaluation.

Consumers: HeuristicDecoder (worker/mold assignment), GreedyPipeline,
RoutingResolver (indirectly via median durations).
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NELO curing / drying constraints — Blueprint v2.0 §3.8 (Sprint A / D2)
# ---------------------------------------------------------------------------
# 16 transitions where the successor phase cannot start before the modal
# gap elapses (resin cure, paint dry, glue set). These are PHYSICAL
# constraints, not queue time. Data-derived: each row matches the mode of
# the observed gap for that transition in the curated ERP dataset.
# Schema: (from_phase_code, to_phase_code, min_gap_hours, reason, n_obs)

NELO_CURING_GAPS_SEED: Tuple[Tuple[str, str, float, str, int], ...] = (
    ("LAMINAGEM", "CURA", 15.0, "curing_resin", 17012),
    ("PINTURA_ACABAMENTO", "LIXAGEM_SECO", 12.5, "drying_paint", 20335),
    ("PINTURA_ACABAMENTO", "COLAGEM_PECAS", 12.5, "drying_paint", 1229),
    ("PINTURA_ACABAMENTO", "COLAGEM_GOLAS", 15.5, "drying_paint", 134),
    ("COLAGEM_PECAS", "PINTURA_ACABAMENTO", 19.5, "curing_glue", 6912),
    ("COLAGEM_PECAS", "ACABAMENTO_2", 23.5, "curing_glue", 2290),
    ("COLAGEM_PECAS", "ACABAMENTO_3", 21.5, "curing_glue", 385),
    ("COLAGEM_PECAS", "ACABAMENTO_PREPARACAO", 23.5, "curing_glue", 676),
    ("COLAGEM_BARCOS", "PINTURA_ACABAMENTO", 19.0, "curing_glue", 777),
    ("ACABAMENTO_ENVERNIZ", "LIXAGEM_AGUA", 18.0, "drying_varnish", 3016),
    ("COLAGEM_GOLAS", "ACABAMENTO_3", 24.5, "curing_glue", 175),
    ("COLAGEM_GOLAS", "ACABAMENTO_2", 24.0, "curing_glue", 183),
    ("LIXAGEM_SECO", "ACABAMENTO_ENVERNIZ", 21.5, "drying", 474),
    ("LIXAGEM_SECO", "ACABAMENTO_PINTURA", 21.5, "drying", 548),
    ("LIXAGEM_AGUA", "ACABAMENTO_2", 15.0, "drying", 999),
    ("LAMINAGEM_INFUSAO", "CURA", 24.0, "curing_infusion", 300),
)


def normalize_phase_code(name: Optional[str]) -> str:
    """Canonical phase code: strip accents, UPPERCASE, spaces/hyphens/
    dots → underscores. Used for curing gap lookups and
    PAIR_REQUIRED_PHASES comparison.

    Accent-stripping matters because the ERP stores names like
    "Laminagem Infusão" while the seed table uses ASCII codes like
    "LAMINAGEM_INFUSAO".

    Returns empty string if input is falsy so callers can short-circuit
    on missing phase info.
    """
    if not name:
        return ""
    # NFKD decomposes accented chars into base + combining mark; keep
    # only ASCII so "Infusão" → "Infusao".
    decomposed = unicodedata.normalize("NFKD", str(name))
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    s = ascii_only.strip().upper()
    for ch in (" ", "-", "/", "."):
        s = s.replace(ch, "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


@dataclass
class MoldInfo:
    molde_id: str
    modelo_id: str
    pocket_count: int = 1
    em_manutencao: bool = False
    tipo: str = ""


@dataclass
class FactoryState:
    """Read-only snapshot of factory data needed by the CPO scheduler."""

    tenant_id: UUID
    active_ingestion_id: Optional[UUID] = None

    # skill_matrix[fase_id] = set of funcionario_id able to do this phase
    skill_matrix: Dict[str, Set[str]] = field(default_factory=dict)

    # molds_by_model[modelo_id] = list of molds compatible with this model
    molds_by_model: Dict[str, List[MoldInfo]] = field(default_factory=dict)

    # all molds indexed by id
    molds: Dict[str, MoldInfo] = field(default_factory=dict)

    # median historical real duration per (fase_id, modelo_id), in hours
    historical_durations: Dict[Tuple[str, str], float] = field(default_factory=dict)

    # historical error rate per fase_id (0.0-1.0)
    historical_error_rates: Dict[str, float] = field(default_factory=dict)

    # open orders available to schedule
    open_orders: List[Dict[str, Any]] = field(default_factory=list)

    # min mandatory gap between consecutive phases (curing/drying).
    # Key: (from_phase_code, to_phase_code) — both normalized via
    # `normalize_phase_code`. Value: hours.
    # Populated from the DB table `plan.phase_transition_gap`, falling
    # back to NELO_CURING_GAPS_SEED when the table is empty or missing.
    phase_transition_gaps: Dict[Tuple[str, str], float] = field(default_factory=dict)

    # Sprint E.4 — confirmed PreferenceRule rows (Camada 1 learning).
    # Each entry is a plain dict with `type` + `predicate` (+ optional
    # `description`/`confidence` for debugging). Populated by
    # `FactoryState.load()` from `governance.preference_rule` filtered
    # on `status=confirmed`. Consumed by
    # `src.plan.cpo.preference_adapter.compute_preference_penalty` from
    # inside the fitness function. Empty list means "no adaptive
    # enforcement yet" — scheduler keeps its defaults.
    preference_rules: List[Dict[str, Any]] = field(default_factory=list)

    # ----- NELO domain rules ---------------------------------------

    #: Phase codes that require a 2-person crew.
    #: Criterion: phases where ≥80% of historical operations ran with 2+
    #: workers (FuncionariosFaseOrdemFabrico, 2024 sample).
    #: - Laminagem standard: 88.5% pair → INCLUDED
    #: - Laminagem Infusão:  40% pair, 58% solo → EXCLUDED (pair optional)
    #: NOTE: `CoeficienteX` in the ERP is a monetary bonus (€), NOT a
    #: time coefficient — do NOT derive pair requirement from it.
    PAIR_REQUIRED_PHASES: Tuple[str, ...] = (
        "LAMINAGEM",
    )

    @classmethod
    async def load(
        cls,
        session,
        tenant_id: UUID,
        semantic_queries: Optional[Any] = None,
    ) -> "FactoryState":
        """
        Load a FactoryState from the curated layer.

        Falls back to SemanticQueriesInMemory if present; otherwise
        returns an empty state (the scheduler will emit INSUFFICIENT_DATA).

        `session` is kept for future DB-backed queries (currently unused,
        since semantic layer is in-memory).
        """
        sq = semantic_queries
        if sq is None:
            try:
                from src.factory_data_product.services.semantic_queries_inmemory import (
                    SemanticQueriesInMemory,
                )
                sq = SemanticQueriesInMemory()
            except Exception as e:
                logger.warning(f"Semantic layer unavailable: {e}")
                return cls(tenant_id=tenant_id)

        state = cls(tenant_id=tenant_id)

        # Open orders
        wip = _safe_call(sq, "get_wip")
        if wip and "data" in wip:
            state.open_orders = wip["data"].get("open_orders_list", []) or []
        elif wip and "rows" in wip:
            state.open_orders = list(wip["rows"])

        # Skill matrix
        skills = _safe_call(sq, "get_skills_risk", min_capable=1)
        if skills:
            # Walk curated engine directly if available for full matrix
            engine = getattr(sq, "engine", None)
            if engine is not None:
                state.skill_matrix = _extract_skill_matrix(engine)

        # Molds
        if sq is not None:
            engine = getattr(sq, "engine", None)
            if engine is not None:
                state.molds_by_model, state.molds = _extract_molds(engine)

        # Historical durations + error rates
        if sq is not None:
            engine = getattr(sq, "engine", None)
            if engine is not None:
                state.historical_durations = _extract_durations(engine)
                state.historical_error_rates = _extract_error_rates(engine)

        # Curing/drying gaps (Sprint A D2): DB first, seed fallback
        state.phase_transition_gaps = await _load_phase_transition_gaps(
            session, tenant_id,
        )

        # Sprint E.4 — confirmed preference rules (Camada 1). Best-effort:
        # a missing governance schema / table (tests / legacy dbs) leaves
        # the list empty and the scheduler keeps its defaults.
        state.preference_rules = await _load_confirmed_preference_rules(
            session, tenant_id,
        )

        logger.info(
            f"FactoryState loaded: {len(state.open_orders)} orders, "
            f"{len(state.skill_matrix)} phases with skills, "
            f"{len(state.molds)} molds, "
            f"{len(state.historical_durations)} duration medians, "
            f"{len(state.phase_transition_gaps)} curing gaps, "
            f"{len(state.preference_rules)} confirmed rules"
        )
        return state

    def min_gap_hours(
        self,
        from_phase: Optional[str],
        to_phase: Optional[str],
    ) -> float:
        """Mandatory minimum wait between two phases (hours).

        Accepts either phase_id or phase_name (either form is normalized).
        Returns 0.0 for transitions not in the curing/drying table —
        caller layers queue_time on top separately.
        """
        a = normalize_phase_code(from_phase)
        b = normalize_phase_code(to_phase)
        if not a or not b:
            return 0.0
        return float(self.phase_transition_gaps.get((a, b), 0.0))

    def can_perform(self, fase_id: str, funcionario_id: str) -> bool:
        return funcionario_id in self.skill_matrix.get(fase_id, set())

    def workers_for(self, fase_id: str) -> Set[str]:
        return self.skill_matrix.get(fase_id, set())

    def skill_count(self, funcionario_id: str) -> int:
        """How many phases this worker is approved to perform.

        Sprint A D5 — used by the decoder as a proxy for operator
        experience/versatility when ranking workers in the same pool.
        No per-worker quality model yet (that's Sprint H
        QualityRiskModel); workers who master more phases are a
        reasonable stand-in for "experienced".
        """
        return sum(
            1 for skill_pool in self.skill_matrix.values()
            if funcionario_id in skill_pool
        )

    def median_duration_h(
        self,
        fase_id: str,
        modelo_id: str,
        fallback_hours: float,
    ) -> float:
        key = (str(fase_id), str(modelo_id))
        if key in self.historical_durations:
            return self.historical_durations[key]
        # Fallback: 2x buffer on standard time
        return fallback_hours * 2.0

    def team_size_for(self, fase_id: str, phase_name: str = "") -> int:
        normalized = phase_name.upper().replace(" ", "_")
        if any(p in normalized for p in self.PAIR_REQUIRED_PHASES):
            return 2
        return 1

    def mold_for(self, modelo_id: str) -> Optional[MoldInfo]:
        candidates = self.molds_by_model.get(modelo_id, [])
        # First non-maintenance mold, largest pocket count first
        candidates_ok = [m for m in candidates if not m.em_manutencao]
        if not candidates_ok:
            return None
        return max(candidates_ok, key=lambda m: m.pocket_count)


# ---------------------------------------------------------------------------
# Helpers — extract from semantic engine's curated_data
# ---------------------------------------------------------------------------

def _safe_call(sq: Any, method: str, **kwargs) -> Optional[Dict[str, Any]]:
    try:
        fn = getattr(sq, method, None)
        if fn is None:
            return None
        result = fn(**kwargs)
        if isinstance(result, dict) and result.get("status") == "BLOCKED":
            return None
        return result
    except Exception as e:
        logger.debug(f"Semantic call {method} failed: {e}")
        return None


def _extract_skill_matrix(engine: Any) -> Dict[str, Set[str]]:
    """
    Build {fase_id: {funcionario_id, ...}} from CuratedSkillMatrix rows.
    Best-effort; returns {} if engine shape doesn't match.
    """
    try:
        active_id = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active_id, {}) if active_id else {}
        rows = scope.get("skill_matrix") or scope.get("CuratedSkillMatrix") or []
        matrix: Dict[str, Set[str]] = {}
        for row in rows:
            if not getattr(row, "apto", True):
                continue
            fase_id = str(getattr(row, "fase_id", ""))
            func_id = str(getattr(row, "funcionario_id", ""))
            if fase_id and func_id:
                matrix.setdefault(fase_id, set()).add(func_id)
        return matrix
    except Exception as e:
        logger.debug(f"skill matrix extraction failed: {e}")
        return {}


def _extract_molds(engine: Any) -> Tuple[Dict[str, List[MoldInfo]], Dict[str, MoldInfo]]:
    try:
        active_id = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active_id, {}) if active_id else {}
        rows = scope.get("molds") or scope.get("CuratedMold") or []
        by_model: Dict[str, List[MoldInfo]] = {}
        by_id: Dict[str, MoldInfo] = {}
        for row in rows:
            info = MoldInfo(
                molde_id=str(getattr(row, "molde_id", "")),
                modelo_id=str(getattr(row, "modelo_id", "")),
                pocket_count=int(getattr(row, "pocket_count", None) or getattr(row, "tamanho_id", 1) or 1),
                em_manutencao=bool(getattr(row, "em_manutencao", False)),
                tipo=str(getattr(row, "tipo", "")),
            )
            if info.molde_id:
                by_id[info.molde_id] = info
                if info.modelo_id:
                    by_model.setdefault(info.modelo_id, []).append(info)
        return by_model, by_id
    except Exception as e:
        logger.debug(f"mold extraction failed: {e}")
        return {}, {}


def _extract_durations(engine: Any) -> Dict[Tuple[str, str], float]:
    """
    Compute median horas_reais per (fase_id, modelo_id) from CuratedOrderPhase +
    CuratedOrder (to join modelo_id).
    """
    try:
        from statistics import median
    except ImportError:  # pragma: no cover
        return {}

    try:
        active_id = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active_id, {}) if active_id else {}
        phases = scope.get("order_phases") or scope.get("CuratedOrderPhase") or []
        orders = scope.get("orders") or scope.get("CuratedOrder") or []

        order_model: Dict[str, str] = {}
        for o in orders:
            oid = str(getattr(o, "of_id", ""))
            mid = str(getattr(o, "modelo_id", ""))
            if oid:
                order_model[oid] = mid

        buckets: Dict[Tuple[str, str], List[float]] = {}
        for p in phases:
            h_real = getattr(p, "horas_reais", None) or getattr(p, "horas_finais", None)
            if not h_real or h_real <= 0:
                continue
            fase_id = str(getattr(p, "fase_id", ""))
            of_id = str(getattr(p, "of_id", ""))
            modelo_id = order_model.get(of_id, "")
            if fase_id and modelo_id:
                buckets.setdefault((fase_id, modelo_id), []).append(float(h_real))

        return {k: float(median(v)) for k, v in buckets.items() if v}
    except Exception as e:
        logger.debug(f"duration extraction failed: {e}")
        return {}


async def _load_phase_transition_gaps(
    session: Any,
    tenant_id: UUID,
) -> Dict[Tuple[str, str], float]:
    """Load curing/drying gaps from the DB, fall back to the seed.

    Returns a dict keyed by (from_phase_code, to_phase_code) — both
    normalized via `normalize_phase_code`.
    """
    seed: Dict[Tuple[str, str], float] = {
        (normalize_phase_code(a), normalize_phase_code(b)): float(h)
        for (a, b, h, _reason, _n) in NELO_CURING_GAPS_SEED
    }

    if session is None:
        return seed

    try:
        from sqlalchemy import select

        from src.plan.models.phase_gap import PhaseTransitionGap

        stmt = (
            select(PhaseTransitionGap)
            .where(PhaseTransitionGap.tenant_id == tenant_id)
            .where(PhaseTransitionGap.active.is_(True))
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
    except Exception as exc:  # pragma: no cover — defensive (table absent etc.)
        logger.debug(f"phase_transition_gap DB load failed, using seed: {exc}")
        return seed

    if not rows:
        return seed

    db_gaps: Dict[Tuple[str, str], float] = {}
    for row in rows:
        key = (
            normalize_phase_code(row.from_phase_code),
            normalize_phase_code(row.to_phase_code),
        )
        if not key[0] or not key[1]:
            continue
        db_gaps[key] = float(row.min_gap_hours)

    # Seed entries the DB didn't override — this lets partial overrides
    # per tenant work without losing the physical NELO defaults.
    merged: Dict[Tuple[str, str], float] = dict(seed)
    merged.update(db_gaps)
    return merged


async def _load_confirmed_preference_rules(
    session: Any,
    tenant_id: UUID,
) -> List[Dict[str, Any]]:
    """Return the CONFIRMED PreferenceRule rows for this tenant as plain
    dicts. Swallows any failure (missing schema on a fresh test DB,
    governance module not installed, etc.) and returns an empty list so
    the scheduler boot path stays resilient.
    """
    if session is None:
        return []
    try:
        from sqlalchemy import and_, select

        from src.governance.models import (
            PreferenceRule,
            PreferenceRuleStatus,
        )

        stmt = select(PreferenceRule).where(
            and_(
                PreferenceRule.tenant_id == tenant_id,
                PreferenceRule.status == PreferenceRuleStatus.CONFIRMED.value,
            )
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
    except Exception as exc:  # pragma: no cover — defensive (table absent etc.)
        logger.debug(f"preference_rule DB load skipped: {exc}")
        return []

    return [
        {
            "id": str(r.id),
            "type": r.type,
            "description": r.description,
            "predicate": dict(r.predicate or {}),
            "confidence": float(r.confidence),
        }
        for r in rows
    ]


def _extract_error_rates(engine: Any) -> Dict[str, float]:
    """
    Compute per-phase error rate: count of CuratedQualityEvent per fase_id,
    divided by CuratedOrderPhase count for that phase. Best-effort, returns
    empty dict if shape doesn't match.
    """
    try:
        active_id = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active_id, {}) if active_id else {}

        errors = scope.get("quality_events") or scope.get("CuratedQualityEvent") or []
        phases = scope.get("order_phases") or scope.get("CuratedOrderPhase") or []

        phase_counts: Dict[str, int] = {}
        for p in phases:
            fid = str(getattr(p, "fase_id", ""))
            if fid:
                phase_counts[fid] = phase_counts.get(fid, 0) + 1

        error_counts: Dict[str, int] = {}
        for e in errors:
            fid = str(getattr(e, "fase_id", "") or getattr(e, "fase_culpada_id", ""))
            if fid:
                error_counts[fid] = error_counts.get(fid, 0) + 1

        rates: Dict[str, float] = {}
        for fid, n_phase in phase_counts.items():
            n_err = error_counts.get(fid, 0)
            if n_phase > 0:
                rates[fid] = min(1.0, n_err / n_phase)
        return rates
    except Exception as e:
        logger.debug(f"error rate extraction failed: {e}")
        return {}
