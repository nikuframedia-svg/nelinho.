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


# ---------------------------------------------------------------------------
# Fases NÃO-produção (FP_PRODUCAO=false no ERP da NELO) — Slice E
# ---------------------------------------------------------------------------
# Phase IDs que NÃO devem ser agendados: barcos já fora da linha de produção
# (embalados, entregues, em armazém, etc.) ou fases auxiliares/administrativas.
# Confirmado na BD read-only 2026-06-02 via SELECT FP_ID WHERE FP_PRODUCAO=false.
# Defesa-em-profundidade: usado pelo resolver para garantir que nenhuma
# fase terminal entra num schedule mesmo que a SQL de carregamento falhe.
NON_PRODUCTION_PHASE_IDS: frozenset[str] = frozenset({
    "7",   # Parque Acabamento
    "9",   # Armazem
    "10",  # Embalado
    "12",  # Entregue
    "13",  # Para reparar
    "15",  # Em Uso
    "16",  # Para Abate
    "17",  # Abatido
    "24",  # CAD
    "25",  # CAM
    "26",  # Preparação CNC
    "27",  # Acabamento CNC
    "29",  # Solda
    "30",  # Montagem (auxiliar)
    "31",  # Lacagem
    "37",  # Logistica/Embalagem
    "39",  # Exterior
    "43",  # Serralharia
    "44",  # Multitarefa
    "49",  # Armazem 2ª escolha
    "50",  # Lixo
    "52",  # Escritorio
    "57",  # OF Venda
    "58",  # Avaliação
    "59",
    "60",
    "61",
    "62",
    "72",  # Reutilizado
    "73",  # Pintura-Verniz
})

# Q.158 — fases de REPARAÇÃO (todas FP_PRODUCAO=true; a 13 "Para reparar" é
# FP_PRODUCAO=false e está acima em NON_PRODUCTION_PHASE_IDS). Um barco com a
# fase atual numa destas é um barco entregue/em-uso que voltou para reparação:
# entra no scope (op aberta na fase atual) e marca-se `is_reparacao` para
# lane/UI/prioridade. NÃO usar LIKE '%epar%' (apanharia "Pr-epar-ação").
REPAIR_PHASE_IDS: frozenset[str] = frozenset({
    "14",  # A Reparar
    "76",  # Reparação Verniz
    "77",  # Reparação
})

# Q.166.D — fases de ESTADO/espera (NÃO são trabalho de mão-de-obra): o barco está
# parado à espera de entrar em produção. Têm duração ~0 no planeamento (senão o
# flow-time delas — dias parado — inflava o makespan). São o ponto de ENTRADA, não
# uma tarefa. Confirmado: "Não Laminado"/"Pendente" não consomem operador.
STATUS_PHASE_IDS: frozenset[str] = frozenset({
    "11",  # Não Laminado (estado inicial, à espera de laminar)
    "32",  # Pendente
})

# Q.167.I — fases SEM mão-de-obra: pool de operadores vazio é ESPERADO, não um
# gap de skill-seed. Não emitir o aviso "verify skill seed" para estas. Inclui as
# fases de estado/espera + a Cura (secagem química, não trabalho — ver
# NELO_CURING_GAPS_SEED). Confirmado live 2026-06-09: 0 crew em
# factory_raw.offp_eq para 2 ("Cura") e 11 ("Não Laminado").
NO_LABOR_PHASE_IDS: frozenset[str] = STATUS_PHASE_IDS | frozenset({
    "2",  # Cura — secagem química, sem operador
})


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


# Q.169.F — sinónimos seed→catálogo (drift de nomenclatura do ERP): o seed
# minou "ACABAMENTO_ENVERNIZ" do histórico antigo; a fase real chama-se
# "Acabamento - Envernizamento" (FP_ID=66). Só entradas comprovadas na BD.
_GAP_NAME_SYNONYMS: Dict[str, str] = {
    "ACABAMENTO_ENVERNIZ": "ACABAMENTO_ENVERNIZAMENTO",
}


def alias_gaps_by_phase_id(
    gaps: Dict[Tuple[str, str], float],
    phase_catalog: List[Dict[str, Any]],
) -> Dict[Tuple[str, str], float]:
    """Q.169.F — acrescenta chaves (from_id, to_id) ao mapa de gaps de cura.

    O mapa vem keyed por NOME normalizado (seed NELO_CURING_GAPS_SEED /
    tabela plan.phase_transition_gap) mas TODOS os caminhos de produção
    (decoder `_earliest_start`, CP-SAT `solve_timing`, postpass
    `assign_concrete`) fazem o lookup com o phase_id NUMÉRICO do ERP
    ("1"→"2") → `min_gap_hours` devolvia 0.0 e a CURA QUÍMICA ESTAVA
    MORTA EM PRODUÇÃO. Descoberto pelo validate_schedule (Q.169.B) no
    primeiro dia em serviço: 330 violações LAMINAGEM→CURA (gap real 0.4h
    = fila mediana Q.160, em vez de 15h) num plano live do robô — o
    commit foi recusado. Os testes nunca apanharam porque usam tokens
    consistentes dos dois lados.

    O alias (nome→id via phase_catalog) fecha o buraco para todos os
    callers sem tocar em nenhum. Transições sem fase correspondente no
    catálogo ficam só por nome (honesto; logado)."""
    id_by_name: Dict[str, str] = {}
    for step in phase_catalog or []:
        nome = normalize_phase_code(step.get("fase_nome"))
        fid = str(step.get("fase_id") or "")
        if nome and fid:
            id_by_name.setdefault(nome, fid)

    def _resolve(name: str) -> Optional[str]:
        return id_by_name.get(name) or id_by_name.get(
            _GAP_NAME_SYNONYMS.get(name, ""),
        )

    out = dict(gaps)
    aliased = 0
    for (a, b), hours in gaps.items():
        ia, ib = _resolve(a), _resolve(b)
        if ia and ib:
            out.setdefault((ia, ib), hours)
            aliased += 1
    if gaps:
        logger.info(
            "curing gaps: %d/%d transições com alias por phase_id",
            aliased, len(gaps),
        )
    return out


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

    # Q.160 — mediana REAL da fila inter-fase por fase de DESTINO (horas), de
    # factory_raw.of_fp (gap fim(fase anterior)→início(fase) do mesmo barco).
    # Substitui a constante global 5.2h: cada fase tem a SUA fila medida. É também
    # o mapa de gargalos (que fase acumula WIP). Keyed por phase_id (= OFFP_FP_ID).
    # Vazio = sem histórico → cai no fallback (mediana global → _QUEUE_FALLBACK_MIN).
    queue_median_by_phase: Dict[str, float] = field(default_factory=dict)
    # Mediana global de TODAS as gaps (horas) — fallback quando a fase não tem
    # ≥5 observações. None = sem histórico → cai em _QUEUE_FALLBACK_MIN.
    queue_global_median_h: Optional[float] = None

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

    # Q.164.C — catálogo canónico de fases de produção (FP_PRODUCAO=true), ordenado
    # por FP_SEQUENCIA. Cada item: {fase_id, sequence, fase_nome}. É o ÚLTIMO
    # fallback de rota no RoutingResolver: quando um modelo não tem rota nenhuma
    # (sem histórico of_fp >=2 obs, sem template ERP, sem curada Excel), assume-se
    # a sequência-padrão de produção da NELO com durações medianas REAIS por fase
    # (historical_durations_by_fase). Planeia o barco em vez de o deixar invisível.
    # Vazio = sem catálogo carregado (back-compat: cai em no_route como antes).
    phase_catalog: List[Dict[str, Any]] = field(default_factory=list)

    # Q.165.D — TEMPO-PADRÃO de mão-de-obra (TOUCH-TIME) por fase×classe-de-kayak,
    # de fases_producao.FP_VALOR_REF_K1/K2/K4 (horas). É o tier de TOPO de
    # median_duration_h: a mediana de of_fp é FLOW-TIME (fase aberta, inclui
    # secagem) e infla o makespan; o tempo-padrão do ERP é o trabalho real.
    # `phase_std_ref_hours[fase_id] = {"K1": h, "K2": h, "K4": h}` (só fases/classes
    # com valor). `model_kayak_class[model_id] = "K1"|"K2"|"K4"` (prefixo P_NOME).
    # Vazios = back-compat exacto (cai no cascade histórico).
    phase_std_ref_hours: Dict[str, Dict[str, float]] = field(default_factory=dict)
    model_kayak_class: Dict[str, str] = field(default_factory=dict)

    # Q.166.D — touch-time fallback por fase = p25 do flow-time de of_fp (horas).
    # Tier ABAIXO do FP_VALOR_REF e ACIMA dos tiers de flow-time (mediana/calibrado):
    # de-infla as fases/modelos sem tempo-padrão do ERP. Vazio = sem fallback.
    phase_p25_hours: Dict[str, float] = field(default_factory=dict)

    # historical error rate per fase_id (0.0-1.0)
    historical_error_rates: Dict[str, float] = field(default_factory=dict)

    # open orders available to schedule
    open_orders: List[Dict[str, Any]] = field(default_factory=list)

    # Q.173.L — fases de reparação efetivas para ESTE tenant (config
    # `planning`/`repair.phase_ids`; default = REPAIR_PHASE_IDS {14,76,77}).
    # Governa a prioridade no loader e a exclusão no CP-SAT global. NOTA: a
    # view BD v_of_em_producao.is_reparacao continua {14,76,77} hardcoded.
    repair_phase_ids: frozenset[str] = REPAIR_PHASE_IDS

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

    # Q.153.C1 — order_ids excluídos/adiados do plano (reversível). Carregado
    # de plan.plan_exclusion; as open_orders são filtradas em load(). Vazio =
    # nada excluído (comportamento legado intacto).
    excluded_order_ids: Set[str] = field(default_factory=set)

    # Q.140.F — preferência por sector → fase, por (employee_code, fase_id),
    # valor em [0,1]. Deriva do nível efectivo por sector (override manual >
    # derivado do histórico real > semente ERP), mapeado da fase para o seu
    # grupo de área e normalizado /3.0. É o sinal que o `_pick_workers` usa
    # para REORDENAR o pool apto por preferência (NUNCA alarga — axioma 5).
    # Vazio = sem preferência → ranking por skill_count (back-compat exacto).
    # NUNCA contém € (CoeficienteX): vem só de nível/qualidade/afinidade.
    sector_preferences: Dict[Tuple[str, str], float] = field(default_factory=dict)

    # Q.155.D — complexidade do barco (ICB) por modelo/produto (P_ID == op.model_id),
    # valor [0,1]. Barco mais complexo → sobe o peso da preferência no `_pick_workers`
    # (puxa os melhores operadores). Vazio = sem boost (back-compat). Dimensionless,
    # NUNCA € (vem de governance.boat_complexity: peças+tinta+fases reais).
    boat_model_complexity: Dict[str, float] = field(default_factory=dict)

    # Q.155.D — melhores operadores CURADOS por fase (phase_id → [employee_code,…]
    # ordenados por rank). É a "definição manual" da página Melhores por fase. O
    # decoder prefere-os (sobretudo nos barcos complexos). NUNCA alarga o pool apto
    # (axioma 5) — só REORDENA. Vazio = cai na preferência por sector (Q.140).
    phase_preferred_operators: Dict[str, List[str]] = field(default_factory=dict)

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
        plan_cap: Optional[int] = None,
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

        # Q.164.C — catálogo canónico de fases (sequência-padrão de produção). É o
        # último fallback de rota: modelo sem rota nenhuma → assume esta sequência
        # com durações medianas reais por fase (em vez de ficar unplanned).
        catalog_db = await _load_phase_catalog_db(session, tenant_id)
        if catalog_db:
            state.phase_catalog = catalog_db

        # Q.165.D — tempo-padrão (touch-time) do ERP por fase×classe + mapa
        # modelo→classe. Tier de topo de median_duration_h (de-infla o flow-time).
        std_ref_db = await _load_phase_std_ref_db(session, tenant_id)
        if std_ref_db:
            state.phase_std_ref_hours = std_ref_db
        model_class_db = await _load_model_kayak_class_db(session, tenant_id)
        if model_class_db:
            state.model_kayak_class = model_class_db
        # Q.166.D — touch-time fallback p25-flow por fase (de-infla fases/modelos
        # sem FP_VALOR_REF). Best-effort; vazio = só std_ref + tiers de flow.
        p25_db = await _load_phase_p25_durations_db(session, tenant_id)
        if p25_db:
            state.phase_p25_hours = p25_db

        # Q.160 — mediana REAL da fila inter-fase por fase (substitui o 5.2h
        # global hardcoded). Best-effort; vazio → o decoder cai no fallback
        # global (back-compat exacto). Também é o mapa de gargalos de WIP.
        q_by_phase, q_global = await _load_phase_queue_medians_db(session, tenant_id)
        if q_by_phase:
            state.queue_median_by_phase = q_by_phase
        if q_global is not None:
            state.queue_global_median_h = q_global

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

        # Q.158.B — gate DECLARADO (Entidade_Fase → hr.employee_skills.is_certified):
        # onde a NELO declarou QUEM PODE fazer a fase, essa é a verdade (o
        # histórico of_fp deixa de ser o gate e fica para o ranking). Inerte
        # até o mirror Q.158.A correr (is_certified default False → {}).
        qualified = await _load_qualified_db(session, tenant_id)
        if qualified:
            state.skill_matrix = _apply_qualification_gate(
                state.skill_matrix, qualified,
            )

        # Q.160 — restringe o pool a "operadores ativos" (E_ACTIVO + trabalho nos
        # últimos 2 meses, ~107). Filtro input-only, mais restritivo, com guarda
        # de não-vazio (Injeção mantém o histórico). Inerte se a view faltar.
        active_ops = await _load_active_operators_db(session, tenant_id)
        if active_ops:
            state.skill_matrix = _apply_active_operator_filter(
                state.skill_matrix, active_ops,
            )

        # Q.140.F — preferência por sector → fase (override manual > derivado).
        # Best-effort; vazio = ranking por skill_count (back-compat). Só
        # REORDENA o pool apto no decoder, nunca o alarga (axioma 5).
        if not state.sector_preferences:
            state.sector_preferences = await _load_sector_preferences_db(
                session, tenant_id,
            )

        # Q.155.D — ICB (complexidade) + melhores curados por fase. Best-effort:
        # tabelas ausentes / session None → {} (sem boost, back-compat exacto).
        # Alimentam "barco difícil ↔ melhores operadores" no `_pick_workers`.
        if not state.boat_model_complexity:
            state.boat_model_complexity = await _load_boat_complexity_db(
                session, tenant_id,
            )
        if not state.phase_preferred_operators:
            state.phase_preferred_operators = await _load_phase_preferred_operators_db(
                session, tenant_id,
            )

        if not state.open_orders:
            # Q.136.A — `planning.scope` decide boats_only (default) vs all.
            # Q.158 — o scope passa a usar a regra EXATA da NELO de "em produção"
            # (op aberta na fase atual). O `planning.staleness_months` (Q.158.G)
            # fica como guarda secundária OPCIONAL, default 0/OFF — superado pelo
            # EXISTS (que já exclui zombies). Lê-se do mesmo TenantConfigService.
            from sqlalchemy.exc import SQLAlchemyError
            scope = "boats_only"
            staleness_months: int | None = None
            # Q.174.F0.5 — default canónico: Cliente Fábrica fora do plano.
            excluded_client_ids: frozenset[int] = frozenset({19747})
            # Q.161.A — precedência do cap: arg explícito (request) > config
            # `planning.plan_cap` > None (⇒ default 200 em _load_open_orders_db).
            eff_plan_cap: int | None = plan_cap
            try:
                from src.core.services.tenant_config_service import (
                    TenantConfigService,
                )
                _planning = await TenantConfigService(
                    session, tenant_id
                ).get_category("planning")
                scope = str(_planning.get("scope") or "boats_only")
                _stale = _planning.get("staleness_months", 0)
                staleness_months = (
                    int(_stale) if _stale not in (None, "") else None
                )
                if eff_plan_cap is None:
                    _cfg_cap = _planning.get("plan_cap")
                    eff_plan_cap = (
                        int(_cfg_cap) if _cfg_cap not in (None, "") else None
                    )
                # Q.173.L — fases de reparação configuráveis por tenant
                # (lista de ints/strings); inválido/vazio ⇒ default.
                _rep = _planning.get("repair.phase_ids")
                if isinstance(_rep, (list, tuple)) and _rep:
                    state.repair_phase_ids = frozenset(
                        str(int(x)) for x in _rep
                    )
                # Q.174.F0.5 — clientes excluídos do plano. O canónico
                # Planeamento_Previsão exclui SEMPRE o Cliente Fábrica
                # (e_id=19747) de toda a seleção de barcos a planear
                # (WHERE o.of_e_id_enc <> 19747, corpo lido live); nós
                # planeávamos +90 OFs que a fábrica nunca planeia.
                _exc = _planning.get("excluded_client_ids")
                if isinstance(_exc, (list, tuple)):
                    excluded_client_ids = frozenset(int(x) for x in _exc)
                elif isinstance(_exc, str) and _exc.strip():
                    excluded_client_ids = frozenset(
                        int(t) for t in _exc.replace(";", ",").split(",")
                        if t.strip().lstrip("-").isdigit()
                    )
            except (
                SQLAlchemyError, ImportError, ValueError, AttributeError, TypeError,
            ) as exc:
                logger.debug(
                    "planning config indisponível (%s); scope=boats_only "
                    "staleness=off", exc,
                )
            state.open_orders = await _load_open_orders_db(
                session, tenant_id, scope=scope,
                staleness_months=staleness_months,
                plan_cap=eff_plan_cap,
                repair_phase_ids=state.repair_phase_ids,
                excluded_client_ids=excluded_client_ids,
            )

        # Curing/drying gaps (Sprint A D2): DB first, seed fallback
        state.phase_transition_gaps = await _load_phase_transition_gaps(
            session, tenant_id,
        )
        # Q.169.F — alias (from_id, to_id): sem isto a cura química era 0.0
        # em produção (lookups por phase_id contra mapa keyed por nome).
        state.phase_transition_gaps = alias_gaps_by_phase_id(
            state.phase_transition_gaps, state.phase_catalog,
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

        # Q.153.C1 — barcos excluídos/adiados do plano (reversível). Filtra as
        # open_orders aqui, no carregamento, para que cada replan honre as
        # exclusões correntes. Best-effort: tabela ausente / session None → set().
        state.excluded_order_ids = await _load_plan_exclusions_db(session, tenant_id)
        if state.excluded_order_ids and state.open_orders:
            before = len(state.open_orders)
            state.open_orders = [
                o for o in state.open_orders
                if str(o.get("order_id") or o.get("of_id") or "")
                not in state.excluded_order_ids
            ]
            logger.info(
                "Q.153.C1 exclusões: %d barcos excluídos do plano (%d→%d ordens)",
                len(state.excluded_order_ids), before, len(state.open_orders),
            )

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
            f"{len(state.queue_median_by_phase)} phase queue medians, "
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

    def queue_minutes_for(self, fase_id: Optional[str]) -> float:
        """Q.160 — fila inter-fase (minutos) ANTES de entrar nesta fase.

        Mediana REAL por fase de destino (factory_raw.of_fp), em vez do 5.2h
        global. Hierarquia de fallback:
          1. mediana da fase (`queue_median_by_phase`, n_obs >= 5),
          2. mediana global de todas as gaps (`queue_global_median_h`),
          3. `_QUEUE_FALLBACK_MIN` (5.2h — seed planning.queue_time.median_h).
        Keyed por phase_id (= OFFP_FP_ID), NUNCA por nome. Mediana, nunca média
        (a distribuição é assimétrica: ~5.2h vs p90 ~69h).
        """
        if fase_id is not None:
            h = self.queue_median_by_phase.get(str(fase_id))
            if h is not None:
                return float(h) * 60.0
        if self.queue_global_median_h is not None:
            return float(self.queue_global_median_h) * 60.0
        return _QUEUE_FALLBACK_MIN

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

    def boat_complexity(self, model_id: str) -> float:
        """Q.155.D — complexidade [0,1] do modelo de barco (P_ID), ou 0.0.

        0.0 = sem boost (back-compat). Função pura — segura no hot-path."""
        if not self.boat_model_complexity or not model_id:
            return 0.0
        return float(self.boat_model_complexity.get(str(model_id), 0.0))

    def preferred_rank_score(
        self, funcionario_id: str, fase_id: str,
    ) -> Optional[float]:
        """Q.155.D — score [0,1] do operador na lista CURADA da fase, ou None.

        rank 1 → 1.0; cada posição abaixo perde 0.05 (mínimo 0.5). É uma
        PREFERÊNCIA manual (página Melhores por fase): tem precedência sobre o
        sector (Q.140), mas NUNCA alarga o pool (o decoder já filtrou por
        `workers_for` — axioma 5). `None` = não curado → cai no sector/skill."""
        ranked = self.phase_preferred_operators.get(str(fase_id))
        if not ranked:
            return None
        try:
            idx = ranked.index(str(funcionario_id))
        except ValueError:
            return None
        return max(0.5, 1.0 - 0.05 * idx)

    def std_ref_duration_h(
        self,
        fase_id: str,
        modelo_id: str,
    ) -> Optional[float]:
        """Q.165.D — tempo-padrão de mão-de-obra (touch-time) do ERP em horas para
        (fase, modelo), via classe-de-kayak (FP_VALOR_REF_K1/K2/K4). É a VERDADE do
        trabalho real — substitui o flow-time da mediana de of_fp. `None` quando o
        modelo não é K1/K2/K4 ou a fase não tem valor de referência (cai no cascade
        histórico). Mapas vazios → None (back-compat exacto)."""
        cls = self.model_kayak_class.get(str(modelo_id))
        if not cls:
            return None
        ref = self.phase_std_ref_hours.get(str(fase_id), {}).get(cls)
        return float(ref) if ref and ref > 0 else None

    def planning_duration_h(
        self,
        fase_id: str,
        modelo_id: str,
        fallback_flow_h: float,
    ) -> float:
        """Q.166.D — duração de PLANEAMENTO (touch-time) em horas, consolidada:
          1. fase de ESTADO (Não Laminado/Pendente) → ~0 (1 min, é espera não trabalho);
          2. tempo-padrão do ERP FP_VALOR_REF por classe (`std_ref_duration_h`);
          3. p25-flow por fase (`phase_p25_hours`, aproxima touch-time);
          4. fallback (a duração de flow-time da rota — last resort).
        Degrau, não blend → determinístico. Mapas vazios → cai no fallback
        (back-compat exacto). É o trabalho REAL, não o flow-time (fase aberta)."""
        if str(fase_id) in STATUS_PHASE_IDS:
            return 1.0 / 60.0  # 1 minuto: estado/entrada, não consome capacidade
        std = self.std_ref_duration_h(fase_id, modelo_id)
        if std is not None:
            return std
        p25 = self.phase_p25_hours.get(str(fase_id))
        if p25 is not None and p25 > 0:
            return float(p25)
        return float(fallback_flow_h)

    def median_duration_h(
        self,
        fase_id: str,
        modelo_id: str,
        fallback_hours: float,
    ) -> float:
        key = (str(fase_id), str(modelo_id))
        # Q.165.D — TIER DE TOPO: tempo-padrão de mão-de-obra do ERP (touch-time).
        std = self.std_ref_duration_h(fase_id, modelo_id)
        if std is not None:
            return std
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

        Q.169.C — match EXATO do código canónico (como pair_assignment.
        prefers_pair), não substring: "LAMINAGEM" in "LAMINAGEM_INFUSAO"
        dava team_size=2 à Infusão enquanto prefers_pair dizia False —
        inconsistência que podia tornar ops de Infusão infeasible (sem
        downgrade soft) apesar do histórico 58% solo (docstring acima:
        "never required at all").
        """
        normalized = normalize_phase_code(phase_name) or ""
        pair_phases = {
            normalize_phase_code(p)
            for p in tuple(self.PAIR_REQUIRED_PHASES) + tuple(self.PAIR_PREFERRED_PHASES)
        }
        pair_required = normalized in pair_phases
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
        candidates = self.molds_for_model(modelo_id)
        if not candidates:
            return None
        # First non-maintenance mold, largest pocket count first (legacy: 1 molde).
        return max(candidates, key=lambda m: m.pocket_count)

    def molds_for_model(self, modelo_id: str) -> List["MoldInfo"]:
        """Q.165.C — TODOS os moldes não-em-manutenção compatíveis com o modelo
        (ordem determinística por molde_id). O decoder escolhe o earliest-free
        entre estes (paralelismo real) em vez de serializar tudo num só molde.
        Vazio = sem moldes (op manual). Lista, não um só (era o gargalo)."""
        candidates = self.molds_by_model.get(str(modelo_id), [])
        return sorted(
            (m for m in candidates if not m.em_manutencao),
            key=lambda m: str(m.molde_id),
        )



# ---------------------------------------------------------------------------
# Re-export dos loaders/extractors (saneamento 2026-06-04). Bottom-import para
# quebrar o ciclo: state_loaders importa as primitivas DESTE modulo, ja
# definidas acima. Compat 100% — `from src.plan.cpo.state import _load_*` mantem-se.
# ---------------------------------------------------------------------------
from src.plan.cpo.state_loaders import (
    _CALIBRATION_MIN_OBS,
    _DUR_CEIL_H,
    _DUR_FLOOR_H,
    _OFFP_DUR_H,
    _OFFP_DUR_OK,
    _OPEN_ORDERS_PLAN_CAP,
    _QUEUE_FALLBACK_MIN,
    _apply_active_operator_filter,
    _apply_qualification_gate,
    _extract_durations,
    _extract_error_rates,
    _extract_molds,
    _extract_skill_matrix,
    _load_active_operators_db,
    _load_boat_complexity_db,
    _load_confirmed_preference_rules,
    _load_historical_durations_routes_db,
    _load_molds_db,
    _load_model_kayak_class_db,
    _load_open_orders_db,
    _load_phase_calibration_db,
    _load_phase_catalog_db,
    _load_phase_config_db,
    _load_phase_p25_durations_db,
    _load_phase_std_ref_db,
    _load_phase_preferred_operators_db,
    _load_phase_queue_medians_db,
    _load_phase_transition_gaps,
    _load_plan_exclusions_db,
    _load_qualified_db,
    _load_route_templates_db,
    _load_sector_preferences_db,
    _load_skills_db,
    _safe_call,
)
