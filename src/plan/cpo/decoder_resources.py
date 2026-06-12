"""
ProdPlan ONE — CPO v4 Heuristic Decoder: resource selection (Q.67.6.B3 split).

Resource-selection helpers extracted from `decoder.py` so the façade stays
under 200L. These are the building blocks the per-op loop uses to:

- gate ops on precedence (`_precedences_met`)
- compute the earliest feasible start considering queue/curing/post-Desmolde
  gaps (`_earliest_start`)
- pick workers blending availability and skill (`_pick_workers`)
- sanitise the chromosome's permutation (`_sanitise_permutation`)
- pick the machine honouring routing variants A/B (`_select_machine`)
- pick the worker batch with pair-preferred soft downgrade (`_select_workers`)
- pick the mould for the op (`_select_mold`)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Mapping, Optional, Tuple

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder_helpers import (
    ScheduledOp,
    _is_desmolde,
    _last_on_machine_has_different_family,
)
from src.plan.cpo.pair_assignment import prefers_pair, requires_pair
from src.plan.cpo.state import NO_LABOR_PHASE_IDS, FactoryState
from src.plan.engines.scheduling_adapter import SchedulingOperation

logger = logging.getLogger(__name__)


@dataclass
class SchedulingLoopResult:
    """Output of the main scheduling loop (`_run_scheduling_loop`).

    Bundles every piece of state the KPI accumulators need so the façade
    `decode()` stays orchestration-only.
    """
    scheduled: List[ScheduledOp]
    infeasible: List[str]
    warnings: List[str]
    setups: int
    routing_variants_applied: int
    backwards_shifts: int


def _precedences_met(
    op: SchedulingOperation,
    order_to_ops: Dict[str, List[SchedulingOperation]],
    op_end_at: Dict[str, datetime],
) -> bool:
    # Q.116.B — fase com posição alternativa: requer que PELO MENOS UM
    # sibling cujo phase_id ∈ allowed_predecessors já tenha terminado.
    # Não gate na sequência intra-encomenda nem nos predecessor_ops
    # explícitos — o caminho legacy não se aplica.
    if op.is_flexible and op.allowed_predecessors:
        allowed = set(op.allowed_predecessors)
        siblings = order_to_ops[op.order_id]
        for prev in siblings:
            if prev.operation_id == op.operation_id:
                continue
            if prev.phase_id in allowed and prev.operation_id in op_end_at:
                return True
        return False
    # Intra-order precedence
    siblings = order_to_ops[op.order_id]
    for prev in siblings:
        if prev.operation_id == op.operation_id:
            continue
        # Q.169.G — sequências EMPATADAS serializam por operation_id (um
        # barco não está em 2 fases ao mesmo tempo): a rota real dá à
        # Laminagem (1) e à Infusão (67) a MESMA sequência e às reparações
        # sequence=0 → o decoder tratava-as como paralelas. Apanhado live
        # pelo validate_schedule (fases sobrepostas na mesma OF).
        before = prev.sequence < op.sequence or (
            prev.sequence == op.sequence
            and str(prev.operation_id) < str(op.operation_id)
        )
        if before and prev.operation_id not in op_end_at:
            return False
    # Explicit predecessors
    for pid in op.predecessor_ops:
        if pid not in op_end_at:
            return False
    return True


def _earliest_start(
    op: SchedulingOperation,
    order_to_ops: Dict[str, List[SchedulingOperation]],
    op_end_at: Dict[str, datetime],
    default: datetime,
    *,
    queue_gap: Optional[timedelta] = None,
    post_desmolde_extra: Optional[timedelta] = None,
    op_by_id: Optional[Dict[str, SchedulingOperation]] = None,
    state: Optional[FactoryState] = None,
) -> Optional[datetime]:
    """Earliest start honouring precedences, queue time (PL22),
    post-Desmolde buffer (PL21) and curing/drying constraints (§3.8).

    Gap stack applied to every predecessor:
    1. `base_gap = max(queue_gap, state.min_gap_hours(pred→curr))` —
       the curing gap is a physical minimum; queue_gap is the idle
       default. We take whichever is larger, they don't stack.
    2. `+ post_desmolde_extra` if predecessor is Desmolde (PL21 stacks
       on top as a QC-absorption buffer).
    """
    earliest = default
    q_gap = queue_gap or timedelta()
    pd_extra = post_desmolde_extra or timedelta()

    def _phase_of(o: Optional[SchedulingOperation]) -> Optional[str]:
        if o is None:
            return None
        return getattr(o, "phase_name", None) or (o.phase_id or None)

    curr_phase = _phase_of(op)

    def _with_gaps(end: datetime, pred_op: Optional[SchedulingOperation]) -> datetime:
        curing_h = 0.0
        if state is not None and pred_op is not None:
            curing_h = state.min_gap_hours(_phase_of(pred_op), curr_phase)
        curing_gap = timedelta(hours=curing_h) if curing_h > 0 else timedelta()
        # Q.160 — fila inter-fase POR FASE (mediana real de of_fp) em vez do 5.2h
        # global. `q_gap` (vindo do engine) é o sinal on/off + fallback legacy:
        # quando a fila está ON (>0) e há `state`, usa a mediana da fase de
        # DESTINO (`op.phase_id`), que já traz o seu próprio fallback global →
        # _QUEUE_FALLBACK_MIN. Cura (física) continua a ser o piso (max abaixo).
        if q_gap > timedelta() and state is not None:
            q_eff = timedelta(
                minutes=state.queue_minutes_for(getattr(op, "phase_id", None))
            )
        else:
            q_eff = q_gap
        # Curing gap (physical) dominates queue gap (soft queue) — take max
        base_gap = q_eff if q_eff >= curing_gap else curing_gap
        shifted = end + base_gap
        if pred_op is not None and _is_desmolde(pred_op):
            shifted += pd_extra
        return shifted

    siblings = order_to_ops[op.order_id]

    # Q.116.B — fase com posição alternativa: predecessor real é o MÁXIMO
    # end_at entre os siblings cujo phase_id ∈ allowed_predecessors e que
    # já tenham completado. Se nenhum completou, o op não pode arrancar
    # ainda — devolvemos None (Q.153.A1) para o loop o deixar pending e
    # retentar numa passagem seguinte; se nunca ficar pronto, o ramo de
    # deadlock marca-o infeasible SEM o agendar (em vez de o agendar a
    # +10 anos, que poluía makespan/datas com lixo end<start).
    if op.is_flexible and op.allowed_predecessors:
        allowed = set(op.allowed_predecessors)
        chosen_pred: Optional[SchedulingOperation] = None
        chosen_end: Optional[datetime] = None
        for prev in siblings:
            if prev.operation_id == op.operation_id:
                continue
            if prev.phase_id not in allowed:
                continue
            end = op_end_at.get(prev.operation_id)
            if end is None:
                continue
            if chosen_end is None or end > chosen_end:
                chosen_end = end
                chosen_pred = prev
        if chosen_end is None:
            # Nenhum allowed_predecessor completou — não pode arrancar agora.
            return None
        candidate = _with_gaps(chosen_end, chosen_pred)
        if candidate > earliest:
            earliest = candidate
        # Predecessores explícitos continuam a ser honrados se existirem.
        for pid in op.predecessor_ops:
            end = op_end_at.get(pid)
            if end is None:
                continue
            pred_op = op_by_id.get(pid) if op_by_id else None
            candidate = _with_gaps(end, pred_op)
            if candidate > earliest:
                earliest = candidate
        return earliest

    for prev in siblings:
        if prev.sequence < op.sequence:
            end = op_end_at.get(prev.operation_id)
            if end is None:
                continue
            candidate = _with_gaps(end, prev)
            if candidate > earliest:
                earliest = candidate
        elif (
            prev.sequence == op.sequence
            and str(prev.operation_id) < str(op.operation_id)
        ):
            # Q.169.G — empate de sequência: serializa sem gaps (é o mesmo
            # barco a mudar de mãos, não uma transição química da rota).
            end = op_end_at.get(prev.operation_id)
            if end is not None and end > earliest:
                earliest = end
    for pid in op.predecessor_ops:
        end = op_end_at.get(pid)
        if end is None:
            continue
        pred_op = op_by_id.get(pid) if op_by_id else None
        candidate = _with_gaps(end, pred_op)
        if candidate > earliest:
            earliest = candidate
    return earliest


# Q.155.D — "barco difícil ↔ melhores operadores". Ligado por defeito.
# Constantes nomeadas (sem magic numbers): a complexidade [0,1] do barco sobe o
# peso da preferência (`_COMPLEXITY_SKILL_BOOST`); fases finas (pool ≤ limiar)
# ficam ISENTAS — não há "top-5" real para escolher (validado contra o ERP).
_COMPLEXITY_SKILL_BOOST = 0.5
_MIN_POOL_FOR_MATCHING = 6
# Bónus aditivo (proporcional à complexidade) que GARANTE que o operador CURADO
# domina nos barcos difíceis — senão empatava com qualquer max-skill e o
# desempate por id roubava-lhe o lugar. Barco simples (complexity~0) → sem bónus.
_CURATED_COMPLEXITY_BONUS = 1.0
# Q.164.A — penalização de carga acumulada (load-balancing). Subtraída do
# `combined` (NÃO via availability, que pesa só 1-qw e desaparecia em qw alto):
# proporcional à fração de carga [0,1] do operador no pool. Dimensionada para
# DOMINAR a dispersão típica de skill no regime degenerado (qw≈0.3 → skill
# contribui ≤0.3), espalhando o trabalho; deixa intacto o boost de curado
# (Q.155.D, até 1.0) nos barcos difíceis. Sem `worker_load_h` (chamadas legacy)
# → load_frac=0 → penalização nula → `combined` byte-idêntico. Medido: sem isto
# o makespan fica ~39000h (1 operador com ~9000h); o decoder concentrava porque
# `availability` colapsa a 1.0 quando a op é no futuro e o skill ganhava sempre.
_LOAD_BALANCE_PENALTY = 0.6


def _pick_workers(
    pool: set,
    team_size: int,
    worker_free_at: Dict[str, datetime],
    earliest: datetime,
    *,
    state: Optional[FactoryState] = None,
    quality_weight: float = 0.0,
    fase_id: Optional[str] = None,
    op_complexity: float = 0.0,
    worker_load_h: Optional[Dict[str, float]] = None,
    op_duration_h: float = 0.0,
) -> List[str]:
    """Pick N workers from the pool by blending availability and experience.

    Sprint A D3+D5 — the scoring:

        skill_score       = min(1, state.skill_count(w) / skill_scale)
        availability      = 1 / (1 + hours_until_free)     # 1 ⇒ free now
        combined          = skill_score * quality_weight
                          + availability * (1 - quality_weight)

    * `quality_weight = 0` (legacy) → pure availability ranking, matches
      the pre-fix first-fit behaviour so old tests are unaffected.
    * `quality_weight = 1` → pick the most experienced workers in the
      pool regardless of when they're free (good for high-stakes ops).
    * Anything in between (the chromosome default is 0.3) blends both.

    Q.140.G — quando `fase_id` é dado e `state.preference_score_for(w, fase_id)`
    tem valor (nível por sector: override manual > derivado real), esse valor
    SUBSTITUI o `skill_count` como `skill_score` desse worker. Assim a ordem de
    preferência por sector que o Luis atribui passa a mandar na escolha. É só
    uma REORDENAÇÃO do `pool` (que já vem filtrado por `workers_for` — axioma 5
    intacto); sem preferência cai no `skill_count` (back-compat exacto). É um
    [0,1] de nível/qualidade, NUNCA € (CoeficienteX).

    Q.164.A — load-balancing (axioma-safe). O `combined` leva uma penalização
    proporcional à FRAÇÃO de carga cumulativa do operador no pool
    (``_LOAD_BALANCE_PENALTY * load_frac``). Tem de ser no `combined` (e NÃO via
    `availability`, que pesa 1-qw e some em qw alto) porque o problema é: quando o
    `earliest` da op é no futuro, TODOS os operadores já estão livres →
    `availability` colapsa a 1.0 para todos → o `combined` fica decidido pelo
    SKILL → os mesmos poucos de topo levam tudo (medido: 1 operador com ~9000h;
    makespan ~4,6 anos). A penalização empurra o trabalho para os menos
    carregados, espalhando-o pelo pool JÁ apto (não expande — axioma 5 intacto).
    Deixa o boost de curado (Q.155.D) ganhar nos barcos difíceis (penalização <
    bónus). `worker_load_h=None` → load_frac=0 → `combined` byte-idêntico
    (back-compat exacto p/ chamadas unitárias e qw=0 legacy).

    Ties are broken deterministically by worker id so schedules are
    reproducible across runs.
    """
    if not pool:
        return []
    # Q.164.A — mapa de carga cumulativa (horas) + máximo do pool para normalizar
    # a fração [0,1]. None/vazio → load_frac=0 (penalização inerte, legacy).
    wload = worker_load_h or {}
    _max_load = max(wload.values(), default=0.0)

    qw = max(0.0, min(1.0, float(quality_weight)))
    # Q.155.D — barco mais complexo → maior peso da preferência (puxa os
    # melhores/curados). op_complexity=0 (fase fina isenta ou sem ICB) → qw_eff=qw
    # (back-compat exacto). Só REORDENA o pool já apto; team_size e pool intactos.
    qw_eff = min(1.0, qw + max(0.0, float(op_complexity)) * _COMPLEXITY_SKILL_BOOST)

    # Pre-compute per-worker skill score once; scale normalises against
    # the busiest worker in the pool so the score stays in [0, 1].
    skill_scores: Dict[str, float] = {}
    if state is not None and qw_eff > 0.0:
        raw_counts = {w: float(state.skill_count(w)) for w in pool}
        max_count = max(raw_counts.values(), default=1.0)
        if max_count <= 0:
            max_count = 1.0
        skill_scores = {w: c / max_count for w, c in raw_counts.items()}

    # Q.155.D — acessores opt-in (defensivo p/ stubs de teste sem estes métodos).
    _pref_rank = getattr(state, "preferred_rank_score", None) if state else None
    _pref_sector = getattr(state, "preference_score_for", None) if state else None

    # Q.174.F4 — disponibilidade real: o ranking vê o operador AUSENTE
    # (ENT_MOV/override) como "livre só depois da ausência" — quem está cá
    # ganha naturalmente. Guard p/ stubs de teste sem o método.
    _abs_adj = getattr(state, "absence_adjusted_start", None) if state else None

    def _score(worker: str) -> Tuple[float, str]:
        free_at = worker_free_at.get(worker, earliest)
        if _abs_adj is not None and op_duration_h > 0.0:
            abs_free = _abs_adj(worker, earliest, op_duration_h)
            if abs_free > free_at:
                free_at = abs_free
        hours_until_free = max(0.0, (free_at - earliest).total_seconds() / 3600.0)
        availability = 1.0 / (1.0 + hours_until_free)
        # Preferência: curados (página Melhores por fase, Q.155.D) têm precedência;
        # senão a preferência por sector (Q.140.G); senão o skill_count.
        rank_score = None
        pref = None
        if qw_eff > 0.0 and fase_id is not None:
            if _pref_rank is not None:
                rank_score = _pref_rank(worker, fase_id)
            pref = rank_score
            if pref is None and _pref_sector is not None:
                pref = _pref_sector(worker, fase_id)
        skill = pref if pref is not None else skill_scores.get(worker, 0.0)
        combined = skill * qw_eff + availability * (1.0 - qw_eff)
        # Q.155.D — barco difícil → o operador CURADO domina, proporcional à
        # complexidade (garante que ganha o empate; barco simples → sem efeito).
        if rank_score is not None:
            combined += float(op_complexity) * _CURATED_COMPLEXITY_BONUS
        # Q.164.A — load-balancing: penaliza o `combined` pela fração de carga
        # cumulativa do operador (0 = menos carregado do pool, 1 = mais). Domina a
        # dispersão de skill no regime degenerado → espalha o trabalho; inerte sem
        # worker_load_h (legacy). Mantém-se ABAIXO do boost de curado (Q.155.D).
        if _max_load > 0.0:
            combined -= _LOAD_BALANCE_PENALTY * (wload.get(worker, 0.0) / _max_load)
        # Return negative because `sorted(..., reverse=False)` + negation
        # gives us "highest combined first" with worker-id as a stable tie-break.
        return (-combined, worker)

    candidates = sorted(pool, key=_score)
    return candidates[:team_size]


def _sanitise_permutation(
    chromosome: Chromosome,
    operations: List[SchedulingOperation],
    *,
    effective_boost: Optional[Dict[str, int]] = None,
) -> List[SchedulingOperation]:
    """FASE 1A.3 (CRIT-10) — validate the chromosome's permutation up front
    and surface anomalies via WARN. The previous list comprehension silently
    dropped out-of-bounds indices and accepted duplicates, masking GA bugs.

    Build `priority_order`: each in-range index at most once, in chromosome
    order. Anything left over is appended in natural index order so every op
    is scheduled exactly once.

    Q.116.D — quando `effective_boost` é passado (map order_id → boost
    int), o priority_order é re-ordenado por boost DESC com tiebreak
    estável na posição original. Não viola axiomas Spelke — só altera a
    ORDEM DE TENTATIVA no while-loop; precedências e gaps continuam
    enforced no `_earliest_start`.
    """
    op_by_index = list(operations)
    n = len(op_by_index)
    perm = list(chromosome.permutation)
    out_of_range = [i for i in perm if not (0 <= i < n)]
    duplicates = len(perm) - len(set(perm))
    missing = n - len({i for i in perm if 0 <= i < n})
    if out_of_range or duplicates or missing or len(perm) != n:
        logger.warning(
            "decoder: malformed chromosome permutation "
            "(n=%d, perm_len=%d, out_of_range=%d, duplicates=%d, missing=%d) — "
            "deduplicating and appending missing ops in natural order",
            n, len(perm), len(out_of_range), duplicates, missing,
        )

    priority_order: List[SchedulingOperation] = []
    seen_idx: set = set()
    for i in perm:
        if 0 <= i < n and i not in seen_idx:
            priority_order.append(op_by_index[i])
            seen_idx.add(i)
    for i in range(n):
        if i not in seen_idx:
            priority_order.append(op_by_index[i])
            seen_idx.add(i)

    if effective_boost:
        # Q.116.D — pré-ordena por boost DESC (preserva posição relativa
        # original como tiebreak, mantém determinismo).
        indexed = list(enumerate(priority_order))
        indexed.sort(
            key=lambda iop: (-effective_boost.get(iop[1].order_id, 0), iop[0])
        )
        priority_order = [op for _, op in indexed]

    return priority_order


def _select_machine(
    op: SchedulingOperation,
    chromosome: Chromosome,
    machine_free_at: Dict[str, datetime],
    machine_ids: List[str],
    earliest_pred_end: datetime,
) -> Tuple[str, bool]:
    """Pick the machine for `op`, returning `(machine_id, used_variant_b)`.

    Sprint A C1 — when the chromosome routes the op to variant "B" and the
    op has alternative_machines, invert the priority so the alt machine is
    tried first. This is what actually lets the GA optimise routing A/B.
    """
    op_variant = chromosome.routing_variant(op.operation_id)
    primary_first = [op.machine_id] if op.machine_id else []
    alt_pool = [alt for alt in op.alternative_machines if alt not in primary_first]
    if op_variant == "B" and alt_pool:
        ordered_candidates = alt_pool + primary_first
    else:
        ordered_candidates = primary_first + alt_pool

    candidate_machines = [m for m in ordered_candidates if m in machine_free_at]
    if not candidate_machines:
        # Fall back to any machine (manual-style)
        candidate_machines = list(machine_ids)

    best_machine = min(
        candidate_machines,
        key=lambda m: (
            max(machine_free_at[m], earliest_pred_end),
            candidate_machines.index(m),
        ),
    )
    used_variant_b = op_variant == "B" and best_machine in alt_pool
    return best_machine, used_variant_b


def _select_workers(
    op: SchedulingOperation,
    batch_peers: List[SchedulingOperation],
    state: FactoryState,
    chromosome: Chromosome,
    worker_free_at: Dict[str, datetime],
    earliest_pred_end: datetime,
    warnings: List[str],
    worker_load_h: Optional[Dict[str, float]] = None,
) -> Optional[Tuple[List[List[str]], int]]:
    """Pick workers for the batch. Returns `(batch_workers, team_size)` or
    `None` if the batch can't be staffed.

    Handles three cases:
    1. No skill matrix mapping → schedule as manual (empty worker lists).
    2. Pair-preferred phase, pool too thin → soft downgrade to solo with
       a warning (Sprint Q.8, CEO confirmation 2026-04-26).
    3. Hard pair-required phase, pool too thin → return None (infeasible).
    """
    pool = state.workers_for(str(op.phase_id)) if op.phase_id else set()
    team_size = max(1, int(op.team_size))
    total_workers_needed = team_size * len(batch_peers)

    if not pool and team_size > 0:
        # NEW-2: log a warning because this is a SILENT risk — we may be
        # scheduling a phase where nobody in the skill matrix can actually
        # perform it. If the tenant has a skill_matrix and this phase_id
        # simply isn't mapped, that's a config bug.
        skill_matrix = getattr(state, "skill_matrix", None)
        # Q.167.I — fases sem mão-de-obra (estado/espera + Cura) têm pool vazio
        # por DESIGN; não é gap de skill-seed → não poluir com avisos.
        is_no_labor = op.phase_id is not None and str(op.phase_id) in NO_LABOR_PHASE_IDS
        if skill_matrix and op.phase_id and not is_no_labor:
            warnings.append(
                f"No workers in skill_matrix for phase {op.phase_id!r} "
                f"(op {op.operation_id}); scheduled as manual."
            )
            logger.warning(
                "Phase %r has no eligible workers in skill_matrix — "
                "op %s scheduled as manual; verify skill seed.",
                op.phase_id, op.operation_id,
            )
        return [[] for _ in batch_peers], team_size

    # Q.155.D — complexidade do barco desta op (0 = sem boost). Fases finas
    # (pool ≤ limiar) ficam ISENTAS: não há "top-5" real e já estão saturadas.
    op_complexity = 0.0
    _bc = getattr(state, "boat_complexity", None)
    if _bc is not None and len(pool) > _MIN_POOL_FOR_MATCHING:
        op_complexity = _bc(str(getattr(op, "model_id", "") or ""))

    picked = _pick_workers(
        pool, total_workers_needed, worker_free_at, earliest_pred_end,
        state=state,
        quality_weight=float(getattr(chromosome, "quality_weight", 0.0) or 0.0),
        fase_id=str(op.phase_id) if op.phase_id else None,
        op_complexity=op_complexity,
        worker_load_h=worker_load_h,  # Q.164.A — load-balancing tiebreak
        # Q.174.F4 — disponibilidade: ausentes afundam no ranking.
        op_duration_h=max(0.0, float(op.duration_minutes or 0)) / 60.0,
    )
    if len(picked) < total_workers_needed:
        # Sprint Q.8 — pair-preferred phases accept a solo downgrade.
        soft_pair = (
            team_size > 1
            and prefers_pair(op, state)
            and not requires_pair(op, state)
        )
        can_downgrade = soft_pair and len(picked) >= len(batch_peers)
        if not can_downgrade:
            return None
        warnings.append(
            f"Pair-preferred phase {op.phase_id!r} "
            f"(op {op.operation_id}) staffed solo — "
            f"pool too thin for {total_workers_needed} workers."
        )
        team_size = 1
        total_workers_needed = team_size * len(batch_peers)
        picked = picked[:total_workers_needed]

    batch_workers = [
        picked[i * team_size : (i + 1) * team_size]
        for i in range(len(batch_peers))
    ]
    return batch_workers, team_size


def _select_mold(
    op: SchedulingOperation,
    state: FactoryState,
    mold_free_at: Optional[Dict[str, datetime]] = None,
    earliest: Optional[datetime] = None,
) -> Optional[str]:
    """Return the chosen mould id (or None when not required / unavailable).

    Q.165.C — escolhe o molde LIVRE MAIS CEDO entre TODOS os moldes do modelo
    (`molds_for_model`), em vez de serializar tudo num só (o gargalo: 1 molde por
    modelo → todos os barcos do modelo em fila). Cada molde físico continua
    serializado (axioma 3 — exclusividade por molde). Sem `mold_free_at` (chamada
    legacy) → cai no `mold_for` de sempre (back-compat exacto). Tie-break por id
    (determinismo). Caller trata `op.mold_required and result is None` como infeasible.
    """
    mold_chosen: Optional[str] = op.mold_id
    if op.mold_required and not mold_chosen and op.model_id:
        if mold_free_at is not None:
            molds = state.molds_for_model(op.model_id)
            if molds:
                ref = earliest or datetime.min  # noqa: DTZ901 — piso p/ tempos CPO naive
                best = min(
                    molds,
                    key=lambda m: (mold_free_at.get(str(m.molde_id), ref), str(m.molde_id)),
                )
                mold_chosen = best.molde_id
        else:
            mold_info = state.mold_for(op.model_id)
            mold_chosen = mold_info.molde_id if mold_info else None
    return mold_chosen


def _run_scheduling_loop(
    *,
    chromosome: Chromosome,
    priority_order: List[SchedulingOperation],
    order_to_ops: Dict[str, List[SchedulingOperation]],
    op_by_id: Dict[str, SchedulingOperation],
    mold_batches: Dict[str, str],
    batch_members: Mapping[str, List[SchedulingOperation]],
    machine_ids: List[str],
    state: FactoryState,
    horizon_start: datetime,
    horizon_end: datetime,
    queue_gap: timedelta,
    post_desmolde_extra: timedelta,
    is_backward: bool,
    target_starts: Dict[str, datetime],
) -> SchedulingLoopResult:
    """Main pass: walk `priority_order`, schedule every op into the timelines.

    This is the body of `decode()`'s while-loop, lifted into a dedicated
    function so the façade stays under 200L. Behaviour is byte-identical to
    the Q.67.6.A monolith — Sprint I.4 mould batching, Sprint A C1/D4
    routing-variant/backwards, Q.53.B calendar snap, Sprint Q.8 pair-preferred
    soft downgrade, and the soft-horizon warning are all preserved.
    """
    machine_free_at: Dict[str, datetime] = {mid: horizon_start for mid in machine_ids}
    worker_free_at: Dict[str, datetime] = {}
    # Q.164.A — carga cumulativa (horas) por operador, alimenta o tiebreak de
    # load-balancing do `_pick_workers` para o trabalho espalhar pelo pool apto.
    worker_load_h: Dict[str, float] = {}
    mold_free_at: Dict[str, datetime] = {}
    op_end_at: Dict[str, datetime] = {}
    scheduled: List[ScheduledOp] = []
    infeasible: List[str] = []
    warnings: List[str] = []
    setups = 0
    routing_variants_applied = 0
    backwards_shifts = 0
    max_op_start = horizon_end - timedelta(minutes=1)  # leave room for duration

    pending = list(priority_order)
    loop_guard = 0
    max_loops = len(pending) * 10 + 10  # prevent infinite loop on bad data

    while pending and loop_guard < max_loops:
        loop_guard += 1
        progress = False
        new_pending: List[SchedulingOperation] = []

        for op in pending:
            if not _precedences_met(op, order_to_ops, op_end_at):
                new_pending.append(op)
                continue

            # Sprint I.4 — if this op is in a mould batch, schedule the WHOLE
            # batch right now. Wait for peers otherwise.
            batch_id = mold_batches.get(op.operation_id)
            batch_peers: List[SchedulingOperation] = [op]
            if batch_id:
                peers = batch_members.get(batch_id, [])
                if any(not _precedences_met(p, order_to_ops, op_end_at) for p in peers):
                    new_pending.append(op)
                    continue
                already_done = {s.operation_id for s in scheduled}
                peers = [p for p in peers if p.operation_id not in already_done]
                if not peers:
                    continue
                batch_peers = peers

            earliest_candidates = [
                _earliest_start(
                    p, order_to_ops, op_end_at, horizon_start,
                    queue_gap=queue_gap, post_desmolde_extra=post_desmolde_extra,
                    op_by_id=op_by_id, state=state,
                )
                for p in batch_peers
            ]
            # Q.153.A1 — fase flexível cujo allowed_predecessor ainda não
            # completou devolve None: deixa pending e retenta na próxima
            # passagem (em vez de agendar a +10 anos). Se nunca ficar pronto,
            # o ramo de deadlock (não-progresso) marca-o infeasible.
            if any(c is None for c in earliest_candidates):
                new_pending.append(op)
                continue
            earliest_pred_end = max(earliest_candidates)

            best_machine, used_variant_b = _select_machine(
                op, chromosome, machine_free_at, machine_ids, earliest_pred_end,
            )
            if used_variant_b:
                routing_variants_applied += 1

            staffing = _select_workers(
                op, batch_peers, state, chromosome,
                worker_free_at, earliest_pred_end, warnings,
                worker_load_h=worker_load_h,  # Q.164.A
            )
            if staffing is None:
                for p in batch_peers:
                    infeasible.append(p.operation_id)
                continue
            batch_workers, _team_size = staffing

            mold_chosen = _select_mold(
                op, state, mold_free_at=mold_free_at, earliest=earliest_pred_end,
            )
            if op.mold_required and not mold_chosen:
                for p in batch_peers:
                    infeasible.append(p.operation_id)
                continue

            # Start time = max of (pred end, machine free, workers free, mold free).
            candidates = [earliest_pred_end, machine_free_at[best_machine]]
            for slot in batch_workers:
                for w in slot:
                    candidates.append(worker_free_at.get(w, horizon_start))
            if mold_chosen:
                candidates.append(mold_free_at.get(mold_chosen, horizon_start))
            earliest_feasible = max(candidates)

            # Sprint A D4 — backwards: shift to the latest common target.
            start = earliest_feasible
            if is_backward:
                peer_targets = [
                    target_starts[p.operation_id]
                    for p in batch_peers
                    if p.operation_id in target_starts
                ]
                if peer_targets:
                    batch_target = min(max(peer_targets), max_op_start)
                    if batch_target > earliest_feasible:
                        start = batch_target
                        backwards_shifts += len(batch_peers)

            # Q.53.B — calendar snap into working shift.
            calendar = getattr(state, "calendar", None)
            if calendar is not None:
                start = calendar.add_working_hours(start, 0.0)

            # Q.174.F4 — GARANTIA dura de disponibilidade: nenhum operador
            # escolhido trabalha DENTRO de uma janela de ausência (ENT_MOV +
            # overrides). Fixpoint COMBINADO com o snap de calendário (o push
            # de ausência acaba à meia-noite → re-snap para as 08:00; o snap
            # pode aterrar noutro dia de ausência → novo push). Monótono e
            # limitado (o start só avança; bound de segurança 16).
            _abs_adj = getattr(state, "absence_adjusted_start", None)
            if _abs_adj is not None and getattr(state, "worker_absences", None):
                _dur_h = max(
                    1.0, max(float(p.duration_minutes) for p in batch_peers)
                ) / 60.0
                for _ in range(16):
                    pushed = start
                    for slot in batch_workers:
                        for w in slot:
                            adj = _abs_adj(w, pushed, _dur_h)
                            if adj > pushed:
                                pushed = adj
                    if pushed == start:
                        break
                    start = (
                        calendar.add_working_hours(pushed, 0.0)
                        if calendar is not None else pushed
                    )

            peer_duration_min = [
                max(1.0, float(p.duration_minutes)) for p in batch_peers
            ]
            if calendar is not None:
                batch_end = calendar.add_working_hours(
                    start, max(peer_duration_min) / 60.0,
                )
            else:
                batch_end = start + timedelta(minutes=max(peer_duration_min))

            for peer, slot_workers, peer_dur in zip(
                batch_peers, batch_workers, peer_duration_min
            ):
                if calendar is not None:
                    peer_end = calendar.add_working_hours(start, peer_dur / 60.0)
                else:
                    peer_end = start + timedelta(minutes=peer_dur)
                if peer_end > horizon_end:
                    infeasible.append(peer.operation_id)
                    warnings.append(
                        f"Op {peer.operation_id} exceeds horizon "
                        f"({peer_end.isoformat()} > {horizon_end.isoformat()})"
                    )
                    # still schedule it (soft horizon) — track via warning
                scheduled.append(ScheduledOp(
                    operation_id=peer.operation_id,
                    order_id=peer.order_id,
                    phase_id=peer.phase_id,
                    machine_id=best_machine,
                    workers=list(slot_workers),
                    mold_id=mold_chosen,
                    start=start,
                    end=peer_end,
                    duration_minutes=peer_dur,
                    mold_batch_id=batch_id,
                    setup_family=getattr(peer, "setup_family", "") or "",
                ))
                op_end_at[peer.operation_id] = peer_end
                # Q.164.A — debita a CADA operador a duração da SUA op (não o
                # batch_end), para o tiebreak de load-balancing usar horas reais.
                # Q.165.A — o operador liberta-se no FIM DA SUA op (peer_end), não
                # no batch_end (peer mais longo do lote). Para ops single (a maioria)
                # peer_end == batch_end; em mold-batches multi-pocket o operador do
                # barco mais curto fica livre mais cedo. A estação/molde continuam
                # ocupados até batch_end (ocupação física); precedência/cura referem
                # op_end_at (intactas). Capacidade≥0, monótono, sem double-booking.
                for w in slot_workers:
                    worker_load_h[w] = worker_load_h.get(w, 0.0) + peer_dur / 60.0
                    worker_free_at[w] = peer_end

            # Setup detection — counted once per batch.
            if _last_on_machine_has_different_family(
                best_machine, op, scheduled, batch_size=len(batch_peers),
            ):
                setups += 1

            machine_free_at[best_machine] = batch_end
            # Q.165.A — worker_free_at já foi posto por peer (peer_end) no loop
            # acima; a estação e o molde ocupam a janela física (batch_end).
            if mold_chosen:
                # Q.174.F2 — cooldown canónico: o molde NÃO é reutilizável no
                # fim da op (cura no molde + preparação; Plano_Planeia bloqueia
                # os turnos seguintes ≈24h, Ocean ≈72h). 0 = desligado.
                _cd_h = state.mold_cooldown_hours(mold_chosen)
                mold_free_at[mold_chosen] = (
                    batch_end + timedelta(hours=_cd_h) if _cd_h > 0 else batch_end
                )
            progress = True

        pending = new_pending
        if not progress:
            for op in pending:
                infeasible.append(op.operation_id)
            warnings.append(
                f"Precedence deadlock: {len(pending)} ops unresolvable"
            )
            break

    return SchedulingLoopResult(
        scheduled=scheduled,
        infeasible=infeasible,
        warnings=warnings,
        setups=setups,
        routing_variants_applied=routing_variants_applied,
        backwards_shifts=backwards_shifts,
    )
