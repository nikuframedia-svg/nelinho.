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


def curing_gap_pairs() -> Set[Tuple[str, str]]:
    """Q.116.B — todos os pares (from_phase, to_phase) com gap declarado.

    Usado por `scripts/verify_invariants.py` para validar que cada par
    (predecessor_alternativo, fase_flexivel) declarado em
    `plan.routing_template_phase.allowed_predecessors` tem um gap de
    cura conhecido em `NELO_CURING_GAPS_SEED`.

    Sem gap = ordem alternativa sem suporte fisico — o decoder nao
    pode garantir que a quimica respeita a transicao.
    """
    return {(from_p, to_p) for from_p, to_p, *_ in NELO_CURING_GAPS_SEED}


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

    # FASE 1B.1 (CRIT-15) — `True` when load() actually populated the
    # state from the curated layer; `False` when load() fell back to an
    # empty state because the semantic layer was unavailable. Callers
    # that want strict behaviour (no schedule on missing data) should
    # gate on this flag rather than silently emitting INSUFFICIENT_DATA.
    loaded_ok: bool = True
    load_error: Optional[str] = None

    # skill_matrix[fase_id] = set of funcionario_id able to do this phase
    skill_matrix: Dict[str, Set[str]] = field(default_factory=dict)

    # molds_by_model[modelo_id] = list of molds compatible with this model
    molds_by_model: Dict[str, List[MoldInfo]] = field(default_factory=dict)

    # all molds indexed by id
    molds: Dict[str, MoldInfo] = field(default_factory=dict)

    # median historical real duration per (fase_id, modelo_id), in hours
    historical_durations: Dict[Tuple[str, str], float] = field(default_factory=dict)

    # Q.126.B — median real duration per fase_id alone (across all models),
    # used as a second-tier fallback in `median_duration_h` BEFORE the 2x
    # synthetic buffer. Populated from factory_raw.of_fp (ERP vivo). Empty =
    # no DB history loaded (keeps the legacy 2x behaviour).
    historical_durations_by_fase: Dict[str, float] = field(default_factory=dict)

    # Q.133.A2 — p50 CALIBRADO por (fase_id, modelo) em HORAS + n_obs, do job
    # phase_calibration (plan.phase_duration_calibration). `median_duration_h`
    # prefere-o sobre a mediana crua de of_fp quando n_obs >= _CALIBRATION_MIN_OBS.
    # Vazio = sem calibração → comportamento legado (back-compat).
    calibrated_durations: Dict[Tuple[str, str], Tuple[float, int]] = field(
        default_factory=dict
    )

    # Q.133.B — nº de estações paralelas por fase (fase_id → N), do p95 da
    # concorrência histórica real. O scheduler cria N máquinas por fase e o
    # resolver atribui a op ao work-center da fase → paralelismo real. Vazio =
    # pool "MANUAL" único (back-compat).
    phase_stations: Dict[str, int] = field(default_factory=dict)

    # Q.126.B — real production route per model (OF_P_ID) reconstructed from
    # factory_raw.of_fp: ordered production phases + median real duration.
    # Each step: {fase_id, fase_nome, sequence, duration_hours}. Lets the
    # resolver build a real route when the in-memory curated layer (Excel) is
    # empty — the production reality. Empty = no DB history loaded.
    historical_routes_by_model: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # Q.131.G — routing master do ERP (tabela PRODUTO_FASE), espelhado em
    # plan.model_routing_assignment + routing_template_phase, keyed por OF_P_ID.
    # Fallback REAL (rota do ERP + duration_p50_h minerado de of_fp por
    # time_mining) para modelos sem >=2 observações por fase em of_fp — cobre
    # ~99% das ordens (vs 73% só com histórico per-order). Cada step:
    # {fase_id, fase_nome, sequence, duration_p50_h (float|None), requires_mold,
    # team_size_default}. Empty = sem templates carregados.
    template_routes_by_model: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

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

    # Q.53.B — factory working calendar. When populated (load() reads
    # `plan.factory_calendar_day`), the decoder walks op durations
    # through it so work never lands on a weekend or public holiday.
    # `None` means "no calendar" — decoder keeps the legacy 24/7
    # behaviour, so old callers and tests are unaffected.
    calendar: Optional[Any] = None

    # Sprint E.4 — confirmed PreferenceRule rows (Camada 1 learning).
    # Each entry is a plain dict with `type` + `predicate` (+ optional
    # `description`/`confidence` for debugging). Populated by
    # `FactoryState.load()` from `governance.preference_rule` filtered
    # on `status=confirmed`. Consumed by
    # `src.plan.cpo.preference_adapter.compute_preference_penalty` from
    # inside the fitness function. Empty list means "no adaptive
    # enforcement yet" — scheduler keeps its defaults.
    preference_rules: List[Dict[str, Any]] = field(default_factory=list)

    # Q.135.F3 — overrides de configuração de fase (plan.phase_config).
    # phase_config[fase_id] = {"team_size_override": int|None,
    #                          "num_stations_override": int|None,
    #                          "allowed_worker_ids": list[str]|None}
    # Vazio = sem overrides (comportamento legado intacto).
    phase_config: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Q.140.F — preferência por sector → fase, por (employee_code, fase_id),
    # valor em [0,1]. Deriva do nível efectivo por sector (override manual >
    # derivado do histórico real > semente ERP), mapeado da fase para o seu
    # grupo de área e normalizado /3.0. É o sinal que o `_pick_workers` usa
    # para REORDENAR o pool apto por preferência (NUNCA alarga — axioma 5).
    # Vazio = sem preferência → ranking por skill_count (back-compat exacto).
    # NUNCA contém € (CoeficienteX): vem só de nível/qualidade/afinidade.
    sector_preferences: Dict[Tuple[str, str], float] = field(default_factory=dict)

    # ----- NELO domain rules ---------------------------------------

    #: Phase codes where the scheduler MUST place a 2-person crew (hard
    #: constraint). Empty after Sprint Q.8 — see `PAIR_PREFERRED_PHASES`.
    #: NOTE: `CoeficienteX` in the ERP is a monetary bonus (€), NOT a
    #: time coefficient — do NOT derive pair requirement from it.
    PAIR_REQUIRED_PHASES: Tuple[str, ...] = ()

    #: Phase codes where the scheduler PREFERS a 2-person crew but a
    #: solo assignment is still feasible (the decoder pays a soft fitness
    #: penalty rather than treating it as infeasible).
    #: - Laminagem standard: 88.5% historical pair, 11.5% solo → PREFERRED.
    #:   CEO confirmed 2026-04-26 that the 11.5% solo runs are real
    #:   ("é mesmo assim"), not punch-in errors, so this can no longer be
    #:   a hard rule.
    #: - Laminagem Infusão: 40% pair, 58% solo → never required at all.
    PAIR_PREFERRED_PHASES: Tuple[str, ...] = (
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
        curated_error: Optional[str] = None
        if sq is None:
            try:
                # fix Q.124 — SemanticQueriesInMemory exige `engine`; antes era
                # chamado sem argumento → TypeError silencioso → estado vazio.
                # Resolver o IngestEngine global; sem engine ou sem ingestão ativa,
                # a camada curada está vazia.
                from src.factory_data_product.api.endpoints import get_engine
                from src.factory_data_product.services.semantic_queries_inmemory import (
                    SemanticQueriesInMemory,
                )
                engine = get_engine()
                if engine is None or engine.get_active_run() is None:
                    raise RuntimeError(
                        "camada curada sem ingestão ativa (sem Excel/ETL ERP→curated)"
                    )
                sq = SemanticQueriesInMemory(engine)
            except Exception as e:
                # Q.126.B — em vez de desistir (loaded_ok=False → 503), cair
                # para o ERP vivo (factory_raw.of_fp). Só fica loaded_ok=False
                # no fim se a BD TAMBÉM não tiver histórico real. Isto faz o
                # CPO planear com dados reais sem depender do Excel curado.
                curated_error = str(e)
                logger.warning(
                    "FactoryState: camada curada indisponível (%s); a tentar "
                    "histórico real da BD (factory_raw). Tenant=%s",
                    e,
                    tenant_id,
                )
                sq = None

        state = cls(tenant_id=tenant_id)

        if sq is not None:
            # ----- camada curada in-memory (Excel/ETL) -----
            wip = _safe_call(sq, "get_wip")
            if wip and "data" in wip:
                state.open_orders = wip["data"].get("open_orders_list", []) or []
            elif wip and "rows" in wip:
                state.open_orders = list(wip["rows"])

            skills = _safe_call(sq, "get_skills_risk", min_capable=1)
            if skills:
                engine = getattr(sq, "engine", None)
                if engine is not None:
                    state.skill_matrix = _extract_skill_matrix(engine)

            engine = getattr(sq, "engine", None)
            if engine is not None:
                state.molds_by_model, state.molds = _extract_molds(engine)
                state.historical_durations = _extract_durations(engine)
                state.historical_error_rates = _extract_error_rates(engine)

        # ----- Q.126.B/C/D — BD viva (factory_raw.*): DB-first p/ dados reais.
        # Durações/rotas reais ganham sempre (resolvem o fallback 2x sintético);
        # molds/skills/open_orders preenchem quando a camada curada não trouxe.
        # Tudo best-effort (session None / tabela ausente → sem alteração).
        routes_db, dur_pair_db, dur_fase_db = await _load_historical_durations_routes_db(
            session, tenant_id,
        )
        if dur_pair_db:
            state.historical_durations = dur_pair_db
        if dur_fase_db:
            state.historical_durations_by_fase = dur_fase_db
        if routes_db:
            state.historical_routes_by_model = routes_db

        # Q.131.G — routing master do ERP (PRODUTO_FASE). Fallback-de-fallback:
        # carregado sempre (modelos diferentes caem em camadas diferentes do
        # resolver). Best-effort; tenant-scoped (≠ factory_raw.*).
        templates_db = await _load_route_templates_db(session, tenant_id)
        if templates_db:
            state.template_routes_by_model = templates_db

        # Q.133.A2 — p50 calibrado (loop de aprendizagem). median_duration_h
        # prefere-o quando n_obs suficiente. Best-effort; vazio = legado.
        calibration_db = await _load_phase_calibration_db(session, tenant_id)
        if calibration_db:
            state.calibrated_durations = calibration_db

        # Q.133.B — N estações paralelas por fase (concorrência histórica real).
        # Best-effort; vazio → o scheduler usa o pool "MANUAL" (back-compat).
        try:
            from src.plan.services.phase_workcenters import derive_phase_stations
            state.phase_stations = await derive_phase_stations(session, tenant_id)
        except ImportError as exc:  # pragma: no cover — best-effort
            logger.debug("Q.133.B phase_stations skipped: %s", exc)

        molds_by_model_db, molds_db = await _load_molds_db(session, tenant_id)
        if molds_db:
            state.molds_by_model, state.molds = molds_by_model_db, molds_db

        if not state.skill_matrix:
            state.skill_matrix = await _load_skills_db(session, tenant_id)

        # Q.140.F — preferência por sector → fase (override manual > derivado).
        # Best-effort; vazio = ranking por skill_count (back-compat). Só
        # REORDENA o pool apto no decoder, nunca o alarga (axioma 5).
        if not state.sector_preferences:
            state.sector_preferences = await _load_sector_preferences_db(
                session, tenant_id,
            )

        if not state.open_orders:
            # Q.136.A — `planning.scope` decide boats_only (default) vs all.
            from sqlalchemy.exc import SQLAlchemyError
            scope = "boats_only"
            try:
                from src.core.services.tenant_config_service import (
                    TenantConfigService,
                )
                _planning = await TenantConfigService(
                    session, tenant_id
                ).get_category("planning")
                scope = str(_planning.get("scope") or "boats_only")
            except (SQLAlchemyError, ImportError, ValueError, AttributeError) as exc:
                logger.debug("planning.scope indisponível (%s); boats_only", exc)
            state.open_orders = await _load_open_orders_db(
                session, tenant_id, scope=scope
            )

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

        # Q.135.F3 — overrides de configuração de fase (plan.phase_config).
        # Best-effort: tabela ausente / session None → {} (back-compat).
        state.phase_config = await _load_phase_config_db(session, tenant_id)

        # Q.53.B — factory working calendar. Best-effort: a missing /
        # empty table leaves `calendar` falling back to Mon-Fri; only an
        # unexpected error leaves it None (legacy 24/7 decoder behaviour).
        try:
            from src.plan.services.factory_calendar import FactoryCalendar
            state.calendar = await FactoryCalendar.load(session, tenant_id)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("FactoryCalendar load skipped: %s", exc)
            state.calendar = None

        # Q.126.B — loaded_ok=False só quando NÃO há camada curada NEM
        # histórico real na BD (mantém o 503 honesto do scheduler nesse caso).
        if sq is None and not (
            state.historical_durations or state.historical_routes_by_model
        ):
            state.loaded_ok = False
            state.load_error = (
                f"semantic_layer_unavailable: {curated_error}; "
                "sem histórico real em factory_raw"
            )
            try:
                from src.shared.metrics import bump_silent_fallback
                bump_silent_fallback(
                    "factory_state", "semantic_layer_unavailable",
                )
            except Exception:  # noqa: S110  Q.61.06: metrics best-effort
                pass

        logger.info(
            f"FactoryState loaded: {len(state.open_orders)} orders, "
            f"{len(state.skill_matrix)} phases with skills, "
            f"{len(state.molds)} molds, "
            f"{len(state.historical_durations)} duration medians, "
            f"{len(state.historical_routes_by_model)} model routes, "
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
        # Q.135.F3 — respeita whitelist se existir; NUNCA alarga além do skill_matrix
        if funcionario_id not in self.skill_matrix.get(fase_id, set()):
            return False
        cfg = self.phase_config.get(fase_id)
        if cfg and cfg.get("allowed_worker_ids") is not None:
            return funcionario_id in cfg["allowed_worker_ids"]
        return True

    def workers_for(self, fase_id: str) -> Set[str]:
        """Operadores elegíveis para a fase.

        Q.135.F3: se allowed_worker_ids definido, devolve a intersecção com
        skill_matrix (axioma 5 — NUNCA alarga além das competências reais).
        """
        base = self.skill_matrix.get(fase_id, set())
        cfg = self.phase_config.get(fase_id)
        if cfg and cfg.get("allowed_worker_ids") is not None:
            whitelist = set(cfg["allowed_worker_ids"])
            return base & whitelist  # intersecção — axioma 5 intacto
        return base

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

    def preference_score_for(
        self, funcionario_id: str, fase_id: str,
    ) -> Optional[float]:
        """Q.140.F — preferência [0,1] do worker para a fase, ou None.

        Lookup directo em `sector_preferences[(employee_code, fase_id)]`
        (já com o nível por sector resolvido e mapeado da fase para a área).
        `None` = sem sinal → o decoder cai no `skill_count` (back-compat).
        Função pura, sem efeitos — segura no hot-path da GA.
        """
        if not self.sector_preferences:
            return None
        return self.sector_preferences.get((str(funcionario_id), str(fase_id)))

    def median_duration_h(
        self,
        fase_id: str,
        modelo_id: str,
        fallback_hours: float,
    ) -> float:
        key = (str(fase_id), str(modelo_id))
        # Q.133.A2 — preferir o p50 CALIBRADO (job phase_calibration) quando há
        # amostra suficiente. É histórico real agregado + (Q.133.A3) o desvio
        # plano-vs-real. Degrau, não blend → determinístico; dict vazio =
        # comportamento anterior (back-compat total).
        cal = self.calibrated_durations.get(key)
        if cal and cal[1] >= _CALIBRATION_MIN_OBS and cal[0] > 0:
            return cal[0]
        if key in self.historical_durations:
            return self.historical_durations[key]
        # Q.126.B — second tier: real median for the fase across all models
        # (still REAL ERP history, not synthetic) before falling to the 2x
        # buffer. Covers known fases of new/rare models without inventing a
        # number. Empty dict (no DB history) => unchanged legacy behaviour.
        by_fase = self.historical_durations_by_fase.get(str(fase_id))
        if by_fase and by_fase > 0:
            return by_fase
        # FASE 6.4 — buffer multiplier was hardcoded 2.0 (NELO rule:
        # standard times diverge from real by up to 25× in the worst
        # cases, so 2× is a conservative-but-cheap default). Now
        # overridable via `PRODPLAN_PLAN_STD_DURATION_BUFFER` so a
        # tenant can tune it without a redeploy. Behaviour preserved
        # when the env var is unset.
        import os
        try:
            buffer_factor = float(
                os.environ.get("PRODPLAN_PLAN_STD_DURATION_BUFFER", "2.0")
            )
        except (TypeError, ValueError):
            buffer_factor = 2.0
        return fallback_hours * buffer_factor

    def team_size_for(self, fase_id: str, phase_name: str = "") -> int:
        """Team size para a fase.

        Q.135.F3: usa team_size_override se definido, respeitando o mínimo
        da fase (Laminagem ≥ 2 quando PAIR_PREFERRED).
        """
        normalized = phase_name.upper().replace(" ", "_")
        pair_phases = tuple(self.PAIR_REQUIRED_PHASES) + tuple(self.PAIR_PREFERRED_PHASES)
        pair_required = any(p in normalized for p in pair_phases)
        # mínimo obrigatório da fase
        min_size = 2 if pair_required else 1

        cfg = self.phase_config.get(fase_id)
        if cfg and cfg.get("team_size_override") is not None:
            # override respeitado mas nunca abaixo do mínimo da fase
            return max(min_size, int(cfg["team_size_override"]))

        # Both REQUIRED and PREFERRED return 2 here so the routing/decoder
        # plans for a pair by default. The decoder downgrades to a solo
        # assignment only when the pair pool is exhausted (PREFERRED) or
        # raises infeasibility (REQUIRED). See `pair_assignment.requires_pair`
        # vs `prefers_pair`.
        return min_size

    def num_stations_for(self, fase_id: str) -> int:
        """N estações paralelas para a fase.

        Q.135.F3: usa num_stations_override se definido (≥ 1).
        Fallback: phase_stations[fase_id] (p95 ERP) ou 1.
        """
        cfg = self.phase_config.get(fase_id)
        if cfg and cfg.get("num_stations_override") is not None:
            return max(1, int(cfg["num_stations_override"]))
        return self.phase_stations.get(fase_id, 1)

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


# ---------------------------------------------------------------------------
# Q.126 — DB-backed real data from the live ERP mirror (factory_raw.*)
# ---------------------------------------------------------------------------
# The in-memory curated layer (SemanticQueriesInMemory, fed by the Excel
# `Folha_IA_extra.xlsx`) is empty in production, so the CPO fell back to the
# 2x synthetic buffer (RoutingResolver._standard_template). The ML was already
# repointed to factory_raw.of_fp (Q.124); these loaders do the same for the
# CPO. Tempos vêm SEMPRE do histórico real (axioma Spelke). Best-effort: any
# failure returns empties and never crashes load() nor flips loaded_ok.

# Duration of one phase execution, in hours, from the ISO-text timestamps.
_OFFP_DUR_H = (
    "EXTRACT(EPOCH FROM ("
    "CAST(NULLIF(op.\"OFFP_DATAFIM\", '')    AS timestamp) - "
    "CAST(NULLIF(op.\"OFFP_DATAINICIO\", '') AS timestamp)))/3600.0"
)
# Cleaning shared with build_duration_dataset (Q.124) PLUS a floor.
# Without the floor the Pintura phase (FP 18) collapses to a ~0.083h median
# because of ~1600 near-zero punch rows (verified in _audit/q126/); the floor
# restores the real 3.18h. The ceiling drops phases left open across days.
_OFFP_DUR_OK = (
    "NULLIF(op.\"OFFP_DATAINICIO\", '') IS NOT NULL "
    "AND NULLIF(op.\"OFFP_DATAFIM\", '') IS NOT NULL "
    "AND CAST(NULLIF(op.\"OFFP_DATAFIM\", '') AS timestamp) "
    "  > CAST(NULLIF(op.\"OFFP_DATAINICIO\", '') AS timestamp)"
)
# Duration bounds (hours): floor = drop sub-3-minute punch artifacts; ceiling
# = one week (phases left open across days are calendar artifacts, not work).
# Expressed as 24*7 so it reads as "1 semana", not a magic number.
_DUR_FLOOR_H = 0.05
_DUR_CEIL_H = 24.0 * 7

# Q.133.A2 — amostra mínima por (modelo, fase) para preferir o p50 calibrado
# sobre a mediana crua de of_fp (alinhado com o HAVING count>=5 do job).
_CALIBRATION_MIN_OBS = 5

# Q.131.F — horizonte de planeamento interactivo. O WIP real tem ~5300 OFs
# abertas; planear todas (~11k operações) esgota o orçamento da GA logo na
# geração 1 (sem optimização real) e demora demasiado para um "Replanear"
# interactivo. Planeamos as N ordens MAIS URGENTES (menor data de entrega) —
# rolling horizon. O Luis pediu ~200; é o nº onde a GA optimiza em segundos.
_OPEN_ORDERS_PLAN_CAP = 200


async def _load_historical_durations_routes_db(
    session: Any,
    tenant_id: UUID,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[Tuple[str, str], float], Dict[str, float]]:
    """Q.126.B — real durations + routes from `factory_raw.of_fp` (ERP vivo).

    Returns ``(routes_by_model, durations_by_pair, durations_by_fase)``:
      * ``routes_by_model[str(OF_P_ID)]`` = ordered production-phase steps
        ``{fase_id, fase_nome, sequence, duration_hours}`` (ordered by
        ``FP_SEQUENCIA``, only ``FP_PRODUCAO=true``). Lets the resolver build
        a REAL route when the in-memory curated layer (Excel) is empty.
      * ``durations_by_pair[(str(fase), str(model))]`` = real median hours.
      * ``durations_by_fase[str(fase)]`` = real median per fase across all
        models — the 2nd-tier fallback before the 2x synthetic buffer.
    """
    empty: Tuple[Dict[str, List[Dict[str, Any]]], Dict[Tuple[str, str], float], Dict[str, float]] = ({}, {}, {})
    if session is None:
        return empty
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    pair_sql = text(
        f"""
        WITH d AS (
            SELECT ofb."OF_P_ID" AS model, op."OFFP_FP_ID" AS fase_id, {_OFFP_DUR_H} AS h
            FROM factory_raw.of_fp op
            JOIN factory_raw.ordemfabrico ofb ON ofb."OF_ID" = op."OFFP_OF_ID"
            WHERE {_OFFP_DUR_OK} AND ofb."OF_P_ID" IS NOT NULL
        )
        SELECT d.model::text AS model, d.fase_id::text AS fase_id,
               f."FP_NOME" AS fase_nome, f."FP_SEQUENCIA" AS seq,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY d.h) AS median_h
        FROM d
        JOIN factory_raw.fases_producao f ON f."FP_ID" = d.fase_id
        WHERE d.h > {_DUR_FLOOR_H} AND d.h <= {_DUR_CEIL_H} AND f."FP_PRODUCAO" = true
        GROUP BY d.model, d.fase_id, f."FP_NOME", f."FP_SEQUENCIA"
        HAVING count(*) >= 2
        ORDER BY d.model, f."FP_SEQUENCIA"
        """
    )
    fase_sql = text(
        f"""
        SELECT op."OFFP_FP_ID"::text AS fase_id,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY {_OFFP_DUR_H}) AS median_h
        FROM factory_raw.of_fp op
        WHERE {_OFFP_DUR_OK}
          AND {_OFFP_DUR_H} > {_DUR_FLOOR_H} AND {_OFFP_DUR_H} <= {_DUR_CEIL_H}
        GROUP BY op."OFFP_FP_ID"
        HAVING count(*) >= 5
        """
    )
    try:
        pair_rows = (await session.execute(pair_sql)).mappings().all()
        fase_rows = (await session.execute(fase_sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.126.B durations/routes DB load skipped: %s", exc)
        return empty

    by_pair: Dict[Tuple[str, str], float] = {}
    routes: Dict[str, List[Dict[str, Any]]] = {}
    for r in pair_rows:
        median_h = float(r["median_h"] or 0.0)
        if median_h <= 0:
            continue
        model = str(r["model"])
        fase_id = str(r["fase_id"])
        by_pair[(fase_id, model)] = median_h
        routes.setdefault(model, []).append(
            {
                "fase_id": fase_id,
                "fase_nome": str(r["fase_nome"] or fase_id),
                "sequence": int(r["seq"] or 0),
                "duration_hours": median_h,
            }
        )
    # Defensive: keep each route ordered by FP_SEQUENCIA even if the row
    # order ever changes (the SQL already ORDERs by it).
    for steps in routes.values():
        steps.sort(key=lambda s: s["sequence"])
    by_fase: Dict[str, float] = {
        str(r["fase_id"]): float(r["median_h"])
        for r in fase_rows
        if r["median_h"] and float(r["median_h"]) > 0
    }
    return routes, by_pair, by_fase


async def _load_route_templates_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, List[Dict[str, Any]]]:
    """Q.131.G — routing master do ERP: rota por modelo (OF_P_ID) a partir de
    `plan.model_routing_assignment` JOIN `plan.routing_template_phase`. Espelha a
    tabela ERP PRODUTO_FASE (sequência de fases) e a `duration_p50_h` minerada
    de `of_fp` pelo job `time_mining` (Spelke: tempo real, NUNCA CoeficienteX).

    Fallback REAL para modelos sem ≥2 observações por fase em of_fp (cobre os
    ~27% que o histórico per-order não cobre). Keyed por `str(model_id)`=OF_P_ID,
    igual a `historical_routes_by_model`. p50 pode vir NULL (fases sem amostra) —
    o resolver decide a duração (p50 → mediana-por-fase → ordem em unplanned).

    Best-effort: session None / tabela ausente / outra BD → `{}`. NOTA: estas
    são tabelas `TenantBase` (tenant-scoped), ao contrário de factory_raw.* —
    daí o filtro explícito de tenant."""
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    sql = text(
        """
        SELECT mra.model_id::text          AS model_id,
               rtp.seq                      AS seq,
               rtp.phase_id::text           AS phase_id,
               rtp.phase_name               AS phase_name,
               rtp.duration_p50_h           AS duration_p50_h,
               rtp.requires_mold            AS requires_mold,
               rtp.team_size_default        AS team_size_default
        FROM plan.model_routing_assignment mra
        JOIN plan.routing_template_phase rtp
          ON rtp.template_id = mra.primary_template_id
        WHERE mra.tenant_id = :tenant AND rtp.tenant_id = :tenant
        ORDER BY mra.model_id, rtp.seq
        """
    )
    try:
        rows = (await session.execute(
            sql, {"tenant": str(tenant_id)}
        )).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.131.G route_templates DB load skipped: %s", exc)
        return {}

    templates: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        p50 = r["duration_p50_h"]
        templates.setdefault(str(r["model_id"]), []).append({
            "fase_id": str(r["phase_id"]),
            "fase_nome": str(r["phase_name"] or r["phase_id"]),
            "sequence": int(r["seq"] or 0),
            "duration_p50_h": float(p50) if p50 is not None else None,
            "requires_mold": bool(r["requires_mold"]),
            "team_size_default": int(r["team_size_default"] or 1),
        })
    for steps in templates.values():
        steps.sort(key=lambda s: s["sequence"])
    return templates


async def _load_phase_calibration_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[Tuple[str, str], Tuple[float, int]]:
    """Q.133.A2 — p50 CALIBRADO por (fase_id, modelo) do job phase_calibration
    (`plan.phase_duration_calibration`). Devolve `{(fase,modelo): (p50_horas,
    n_obs)}`. Best-effort: session None / tabela ausente → `{}`. Tenant-scoped
    (PK composto inclui tenant_id). p50 vem em minutos → converte para horas."""
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    sql = text(
        """
        SELECT phase_id::text AS fase_id, modelo::text AS modelo, p50_min, n_obs
        FROM plan.phase_duration_calibration
        WHERE tenant_id = :tenant AND p50_min > 0
        """
    )
    try:
        rows = (await session.execute(
            sql, {"tenant": str(tenant_id)}
        )).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.133.A2 phase_calibration DB load skipped: %s", exc)
        return {}
    out: Dict[Tuple[str, str], Tuple[float, int]] = {}
    for r in rows:
        out[(str(r["fase_id"]), str(r["modelo"]))] = (
            float(r["p50_min"]) / 60.0,
            int(r["n_obs"]),
        )
    return out


async def _load_molds_db(
    session: Any,
    tenant_id: UUID,
) -> Tuple[Dict[str, List[MoldInfo]], Dict[str, MoldInfo]]:
    """Q.126.C — real molds from `factory_raw.of_fp.OFFP_OF_ID_MLD` joined to
    the model (`OF_P_ID`) via `ordemfabrico`. 1186 (mold, model) pairs vs only
    6 from ordemfabrico alone (verified in _audit/q126/). Best-effort."""
    if session is None:
        return {}, {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    sql = text(
        """
        SELECT DISTINCT op."OFFP_OF_ID_MLD"::text AS molde_id,
                        ofb."OF_P_ID"::text        AS modelo_id
        FROM factory_raw.of_fp op
        JOIN factory_raw.ordemfabrico ofb ON ofb."OF_ID" = op."OFFP_OF_ID"
        WHERE op."OFFP_OF_ID_MLD" IS NOT NULL AND op."OFFP_OF_ID_MLD" <> 0
          AND ofb."OF_P_ID" IS NOT NULL
        """
    )
    try:
        rows = (await session.execute(sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.126.C molds DB load skipped: %s", exc)
        return {}, {}
    by_model: Dict[str, List[MoldInfo]] = {}
    by_id: Dict[str, MoldInfo] = {}
    for r in rows:
        molde_id = str(r["molde_id"])
        modelo_id = str(r["modelo_id"])
        if not molde_id or molde_id == "0":
            continue
        info = by_id.get(molde_id)
        if info is None:
            info = MoldInfo(molde_id=molde_id, modelo_id=modelo_id, pocket_count=1)
            by_id[molde_id] = info
        by_model.setdefault(modelo_id, []).append(info)
    return by_model, by_id


async def _load_skills_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, Set[str]]:
    """Q.126.D — real skill matrix from `factory_raw.offp_eq` (crew records)
    joined to `of_fp` (phase). ``skill_matrix[str(fase_id)] = {str(E_ID)}``.
    483 (fase, worker) pairs across 40 phases verified. A PARTIAL matrix is
    safe: the decoder schedules a phase as manual when it has no workers in
    the matrix (decoder_resources.py:356), never infeasible."""
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    sql = text(
        """
        SELECT DISTINCT o."OFFP_FP_ID"::text   AS fase_id,
                        eq."OFFPEQ_E_ID"::text AS func_id
        FROM factory_raw.offp_eq eq
        JOIN factory_raw.of_fp o ON o."OFFP_ID" = eq."OFFPEQ_OFFP_ID"
        WHERE eq."OFFPEQ_E_ID" IS NOT NULL AND o."OFFP_FP_ID" IS NOT NULL
        """
    )
    try:
        rows = (await session.execute(sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.126.D skills DB load skipped: %s", exc)
        return {}
    matrix: Dict[str, Set[str]] = {}
    for r in rows:
        fase_id = str(r["fase_id"])
        func_id = str(r["func_id"])
        if fase_id and func_id:
            matrix.setdefault(fase_id, set()).add(func_id)
    return matrix


async def _load_sector_preferences_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[Tuple[str, str], float]:
    """Q.140.F — preferência por (employee_code, fase_id) ∈ [0,1] para o CPO.

    Deriva do nível por sector (override manual > derivado do histórico real
    > semente ERP), via `SectorPreferenceService.phase_preference_map`. Keyed
    por `employee_code` (= a chave do skill_matrix do CPO) — o serviço já
    resolve o gap UUID↔employee_code internamente. Best-effort: serviço/tabela
    ausente ou vazia → {} (back-compat exacto: o decoder usa skill_count).
    NUNCA usa € (CoeficienteX) — só nível/qualidade/afinidade.
    """
    if session is None:
        return {}
    try:
        from src.workforce.sector_preference_service import (
            SectorPreferenceService,
        )
    except ImportError as exc:  # pragma: no cover — workforce ausente
        logger.debug("Q.140.F sector preferences skipped (import): %s", exc)
        return {}
    try:
        return await SectorPreferenceService(session, tenant_id).phase_preference_map()
    except Exception as exc:  # pragma: no cover — best-effort
        logger.warning("Q.140.F sector preferences load failed: %s", exc)
        return {}


async def _load_open_orders_db(
    session: Any,
    tenant_id: UUID,
    scope: str = "boats_only",
) -> List[Dict[str, Any]]:
    """Q.126.B — real WIP from `factory_raw.ordemfabrico`: open orders
    (`OF_DATAFIM` NULL) whose current phase (`OF_FP_ID`) is a production phase
    (`FP_PRODUCAO=true`, which already excludes Entregue/Armazem/Embalado/...).
    ``modelo_id=OF_P_ID``, deadline = COALESCE of the three date columns.
    Best-effort, capped. Only used when no curated open_orders are present.

    Q.136.A — `scope` (config `planning.scope`): `boats_only` (default) planeia
    SÓ barcos (`PRODUTO.P_QTDDECK>0 AND P_QTDCASCO>0`); sem isto ~56% do WIP são
    acessórios/componentes (Banco/Leme/Strap…). `all` = comportamento legacy
    (LEFT JOIN não dropa nada → back-compat exacto).

    Q.136.B — devolve `current_fase_id` (= `OF_FP_ID`) para o RoutingResolver
    truncar a rota à fase atual (não re-planear fases já feitas)."""
    if session is None:
        return []
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    # Filtro boats-only: P_QTDDECK/P_QTDCASCO>0 = barco (deck+casco). Acessórios/
    # componentes = 0/NULL → excluídos. LEFT JOIN para `all` não dropar órfãos.
    boats_filter = (
        'AND p."P_QTDDECK" > 0 AND p."P_QTDCASCO" > 0'
        if scope == "boats_only"
        else ""
    )
    sql = text(
        f"""
        SELECT ofb."OF_ID"::text   AS of_id,
               ofb."OF_P_ID"::text AS modelo_id,
               ofb."OF_FP_ID"::text AS current_fase_id,
               COALESCE(ofb."OF_DATAENTREGA", ofb."OF_TR_DATA_PREVISTA",
                        ofb."OF_PLANO_DATA_PREVISTA") AS data_entrega_prevista
        FROM factory_raw.ordemfabrico ofb
        JOIN factory_raw.fases_producao f ON f."FP_ID" = ofb."OF_FP_ID"
        LEFT JOIN factory_raw.produto p ON p."P_ID" = ofb."OF_P_ID"
        WHERE ofb."OF_DATAFIM" IS NULL
          AND ofb."OF_P_ID" IS NOT NULL
          AND f."FP_PRODUCAO" = true
          {boats_filter}
        ORDER BY data_entrega_prevista NULLS LAST
        LIMIT :plan_cap
        """
    )
    try:
        rows = (await session.execute(
            sql, {"plan_cap": _OPEN_ORDERS_PLAN_CAP}
        )).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.126.B open_orders DB load skipped: %s", exc)
        return []
    # Q.136.A — visibilidade: scope=boats_only exclui acessórios/componentes (e
    # barcos sem match em `produto`, ex. catálogo incompleto) — não é silencioso.
    logger.info(
        "open_orders DB: scope=%s → %d ordens (cap %d)",
        scope, len(rows), _OPEN_ORDERS_PLAN_CAP,
    )
    return [
        {
            "of_id": str(r["of_id"]),
            "order_id": str(r["of_id"]),
            "modelo_id": str(r["modelo_id"]),
            "current_fase_id": (
                str(r["current_fase_id"]) if r["current_fase_id"] is not None else None
            ),
            "data_entrega_prevista": r["data_entrega_prevista"],
        }
        for r in rows
    ]


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


# ---------------------------------------------------------------------------
# Q.135.F3 — phase config overrides loader
# ---------------------------------------------------------------------------


async def _load_phase_config_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, Dict[str, Any]]:
    """Q.135.F3 — overrides de configuração de fase de `plan.phase_config`.

    Devolve ``{fase_id: {"team_size_override": int|None,
                          "num_stations_override": int|None,
                          "allowed_worker_ids": list[str]|None}}``.
    Best-effort: session None / tabela ausente → ``{}`` (back-compat).
    Espelha o padrão de `_load_phase_calibration_db`.
    """
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    sql = text(
        """
        SELECT phase_id::text            AS phase_id,
               team_size_override        AS team_size_override,
               num_stations_override     AS num_stations_override,
               allowed_worker_ids        AS allowed_worker_ids
        FROM plan.phase_config
        WHERE tenant_id = :tenant
        """
    )
    try:
        rows = (await session.execute(
            sql, {"tenant": str(tenant_id)}
        )).mappings().all()
    except SQLAlchemyError as exc:
        logger.debug("Q.135.F3 phase_config DB load skipped: %s", exc)
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        out[str(r["phase_id"])] = {
            "team_size_override": r["team_size_override"],
            "num_stations_override": r["num_stations_override"],
            "allowed_worker_ids": list(r["allowed_worker_ids"]) if r["allowed_worker_ids"] else None,
        }
    return out
