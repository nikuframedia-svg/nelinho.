"""
ProdPlan ONE — Routing Resolver
================================

Turns a production order into a list of `SchedulingOperation` by consulting
(in priority order):

1. Historical execution via `CuratedOrderPhase` — use the real sequence
   the model actually followed last time, with the median historical
   `horas_reais` per (fase_id, modelo_id).
2. Template fallback via `FasesStandardModelos` — when no history exists
   for this model, use the standard route template with a 2x buffer on
   durations (NELO rule: standard times diverge from real by up to 25x).

Used by the CPO v4 scheduler (`/v1/plan/cpo/schedule`) and can be called
directly by integration tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.plan.cpo.state import NON_PRODUCTION_PHASE_IDS, FactoryState
from src.plan.engines.scheduling_adapter import SchedulingOperation
from src.plan.services.phase_workcenters import station_ids_for

logger = logging.getLogger(__name__)


try:
    from src.shared.metrics import bump_silent_fallback
except Exception:  # pragma: no cover — prometheus_client missing in some tests
    def bump_silent_fallback(module: str, reason: str) -> None:  # type: ignore[no-redef]
        return None


@dataclass
class RoutingRow:
    """A single phase in an order's route."""
    fase_id: str
    fase_nome: str
    sequence: int
    duration_hours: float
    source: str  # "history" | "history_db" | "db_template" | "standard" | "duration_model_p50"
    mold_required: bool = False


def _truncate_route_to_current(
    rows: List["RoutingRow"],
    current_fase_id: Optional[str],
    completed_fase_ids: Optional[set] = None,
) -> List["RoutingRow"]:
    """Q.136.B / Q.158 — corta a rota às fases AINDA por fazer.

    Lógica (por prioridade):

    1. Remove SEMPRE as fases em `completed_fase_ids` (= OFFP_DATAFIM IS NOT
       NULL no ERP). Isto é a fonte de verdade: trabalho já feito nunca volta
       ao plano, independentemente do apontador OF_FP_ID.

    2. Das fases restantes (por fazer), começa na 1ª por ordem de `sequence`.
       Se `current_fase_id` está nessas fases, usa-o como piso (inclusivo).
       Se `current_fase_id` não existe na rota (apontador inválido / estado
       pré-produção) — NÃO faz fallback para a rota completa; começa
       simplesmente na 1ª fase por fazer.

    3. Se `completed_fase_ids` é None ou vazio e `current_fase_id` está na
       rota, comportamento legado mantém-se (back-compat exacto com Q.136.B).

    A rota de entrada deve vir ordenada por `sequence` (o caller garante-o).
    """
    # Passo 1: filtrar fases já concluídas pelo histórico real
    done = set(str(f) for f in (completed_fase_ids or set()))
    todo_rows = [r for r in rows if str(r.fase_id) not in done]

    if not todo_rows:
        # Tudo concluído: nada a planear
        return []

    if not current_fase_id:
        # Sem apontador: tudo por fazer (após remover concluídas)
        return todo_rows

    # Passo 2: localizar o piso na sub-rota por-fazer
    cur_str = str(current_fase_id)
    cur_seqs = [r.sequence for r in todo_rows if str(r.fase_id) == cur_str]
    if cur_seqs:
        # Apontador válido e ainda por fazer: inclusivo
        cur_seq = min(cur_seqs)
        return [r for r in todo_rows if r.sequence >= cur_seq]

    # Passo 3: apontador inválido ou fase já concluída — começar da 1ª por fazer
    # (NÃO fallback para rota completa: evita re-planeamento de trabalho já feito)
    return todo_rows


class RoutingResolver:
    """
    Resolve production routings from the Factory Data Product curated layer.

    Constructor takes a loaded `FactoryState` (kept as a thin wrapper so
    tests can inject a fixture state without a live session).

    FASE 0.3 (DEVA-02): when `duration_predictor` is supplied (a trained
    `DurationModel` from `src/ml/models_domain/duration.py`), the standard
    template fallback uses `predictor.predict(...).p50_hours` instead of
    the legacy `horas_standard * 2.0` buffer. Without the predictor the
    behaviour is unchanged (silent fallback by design).
    """

    def __init__(
        self,
        state: FactoryState,
        duration_predictor: Optional[Any] = None,
    ):
        self.state = state
        self.duration_predictor = duration_predictor
        # FASE 1B.3 (CRIT-13) — set to True the first time `_semantic_engine`
        # falls back to None during this resolver's lifetime. The caller
        # (cpo.api) reads this and emits a CopilotAlert(
        # code=ROUTING_ENGINE_UNAVAILABLE) so the operator knows the
        # schedule was built on standard 2× templates instead of history.
        self.engine_unavailable: bool = False
        # Q.126.E — per-resolver tally of how many resolved ops fell back to
        # the 2x synthetic buffer (RoutingRow.source == "standard") vs total.
        # The scheduler reads `fallback_fraction` after `resolve_many` and, if
        # it crosses the threshold, emits a CopilotAlert + marks the plan
        # `degraded` (soft-warn: the plan is still returned). "history",
        # "history_db" and "duration_model_p50" are all REAL-ish sources.
        self.resolved_ops: int = 0
        self.fallback_ops: int = 0
        # Q.131.H — honestidade: ordens que NÃO conseguem rota (sem histórico,
        # sem template do ERP, sem standard) são registadas aqui em vez de
        # serem saltadas em silêncio. O scheduler lê isto, emite alerta, e
        # devolve `unplanned_orders` + `orders_coverage` ao frontend. Cada
        # entry: {order_id, modelo_id, reason}. Contadores por-instância.
        self.unplanned: List[Dict[str, str]] = []
        self.planned_order_ids: set[str] = set()
        self.total_orders: int = 0

    def resolve(
        self,
        order: Dict[str, Any],
        horizon_start: Optional[datetime] = None,
    ) -> List[SchedulingOperation]:
        """
        Turn an order dict into SchedulingOperations.

        `order` is expected to have: `of_id` (or `order_id`), `modelo_id`,
        `data_entrega_prevista` (due date, optional).

        Order of resolution:
        1. Look up historical phases for this specific `of_id`.
        2. If none: look up historical phases for any order of the same
           `modelo_id` (template-of-templates).
        3. If none: use `FasesStandardModelos` template with 2x buffer.
        """
        horizon_start = horizon_start or datetime.utcnow()
        order_id = str(order.get("of_id") or order.get("order_id") or "")
        modelo_id = str(order.get("modelo_id") or "")
        product_id = str(order.get("produto_id") or modelo_id)

        if not order_id:
            logger.warning("RoutingResolver: order without of_id — skipping")
            self.unplanned.append({
                "order_id": "(sem of_id)",
                "modelo_id": modelo_id,
                "reason": "missing_of_id",
            })
            return []

        # Q.161.E — REPARAÇÃO: a fase atual (14/76/77) é uma fase de reparação. A
        # rota normal já está feita (o barco voltou) e a fase de reparação não está
        # nela → bypassa a resolução de rota normal e planeia a ÚNICA operação
        # aberta da fase de reparação (espelha o /OrdemFabrico/ReparacoesBarcos da
        # NELO; sem rota forward — não existe). Duração REAL de
        # `historical_durations_by_fase` (mediana de of_fp); sem duração real →
        # honesto: fica unplanned (nunca um número fabricado, invariante #8).
        if order.get("is_reparacao") and order.get("current_fase_id"):
            repair_row = self._repair_row(str(order.get("current_fase_id")))
            if repair_row is None:
                self.unplanned.append({
                    "order_id": order_id,
                    "modelo_id": modelo_id,
                    "reason": "repair_no_real_duration",
                })
                return []
            rows = [repair_row]
        else:
            # 1. Try history for this specific order
            rows = self._history_for_order(order_id)
            if not rows:
                # 2. Fall back to any historical order of the same model
                rows = self._history_for_model(modelo_id)
            if not rows:
                # 2.5 Q.126.B — real route reconstructed from factory_raw.of_fp
                # (ERP vivo), pre-loaded into FactoryState. This is the path that
                # fires in production, where the in-memory curated layer is empty.
                rows = self._history_for_model_db(modelo_id)
            if not rows:
                # 2.7 Q.131.G — routing master do ERP (PRODUTO_FASE) com duração
                # p50 minerada de of_fp. Recupera modelos sem ≥2 obs por fase no
                # histórico per-order, ainda com dados REAIS (não o buffer 2×).
                rows = self._template_for_model_db(modelo_id)
            if not rows:
                # 3. Fall back to standard template
                rows = self._standard_template(modelo_id)

            if not rows:
                # 3.5 Q.164.C — último fallback REAL: a sequência canónica de
                # produção (factory_raw.fases_producao) com durações medianas por
                # fase (historical_durations_by_fase). Planeia o barco com a
                # rota-padrão da NELO em vez de o deixar invisível (no_route). É o
                # caso de modelos novos/raros sem >=2 obs por fase em of_fp.
                rows = self._canonical_route()

            if not rows:
                logger.info(
                    f"RoutingResolver: no route found for order={order_id} model={modelo_id}"
                )
                # Q.131.H — não saltar em silêncio: registar a ordem sem rota.
                self.unplanned.append({
                    "order_id": order_id,
                    "modelo_id": modelo_id,
                    "reason": "no_route",
                })
                return []

            # Q.136.B / Q.158 — planear a partir da FASE ATUAL: o barco está a
            # meio, descarta fases já feitas. Usa completed_fase_ids
            # (OFFP_DATAFIM reais) como verdade primária; current_fase_id como
            # piso secundário.
            completed_fase_ids: set = set(order.get("completed_fase_ids") or [])
            rows = _truncate_route_to_current(
                rows, order.get("current_fase_id"), completed_fase_ids
            )

        # Q.131.H — ordem efectivamente planeada (≥1 operação).
        self.planned_order_ids.add(order_id)
        due_date = _parse_datetime(order.get("data_entrega_prevista"))
        skills_by_phase = self.state.skill_matrix
        ops: List[SchedulingOperation] = []

        # Q.126.E — tally real vs 2x-buffer ops for the noisy-fallback signal.
        self.resolved_ops += len(rows)
        self.fallback_ops += sum(1 for r in rows if r.source == "standard")

        # Q.133.B — work-center da fase: N estações paralelas (concorrência real).
        # Vazio → machine_id=None (decoder usa o pool "MANUAL", back-compat).
        phase_stations = getattr(self.state, "phase_stations", {}) or {}

        # Q.165.D/Q.166.D — duração de PLANEAMENTO (touch-time): tempo-padrão ERP
        # (FP_VALOR_REF) → p25-flow → fallback flow; fases de estado → ~0. SUBSTITUI a
        # duração da rota (mediana de of_fp = FLOW-TIME, inclui secagem → inflava o
        # makespan ~5×). É o trabalho REAL. `planning_duration_h` consolida o cascade.
        plan_dur = getattr(self.state, "planning_duration_h", None)

        for row in rows:
            phase_name = row.fase_nome or row.fase_id
            team_size = self.state.team_size_for(row.fase_id, phase_name)
            required_skills = [row.fase_id] if row.fase_id in skills_by_phase else []
            stations = (
                station_ids_for(row.fase_id, phase_stations[row.fase_id])
                if row.fase_id in phase_stations else []
            )
            # Q.166.D — duração de planeamento (touch-time) com precedência sobre o
            # flow-time da rota; fallback = flow-time da própria rota.
            dur_h = row.duration_hours
            if plan_dur is not None:
                dur_h = plan_dur(row.fase_id, modelo_id, row.duration_hours)

            op = SchedulingOperation(
                operation_id=f"{order_id}::{row.fase_id}",
                order_id=order_id,
                product_id=product_id,
                sequence=row.sequence,
                operation_code=phase_name,
                duration_minutes=max(1.0, dur_h * 60.0),
                machine_id=stations[0] if stations else None,  # estação da fase
                setup_family=phase_name,
                due_date=due_date,
                priority=1.0,
                predecessor_ops=[],
                required_skills=required_skills,
                alternative_machines=stations[1:],
                mold_id=None,
                mold_required=row.mold_required,
                model_id=modelo_id,
                team_size=team_size,
                phase_id=row.fase_id,
            )
            ops.append(op)

        return ops

    def _repair_row(self, fase_id: str) -> Optional["RoutingRow"]:
        """Q.161.E — uma RoutingRow para a operação de reparação aberta (fase
        14/76/77). Duração = mediana REAL da fase em `historical_durations_by_fase`
        (de factory_raw.of_fp); reparações não usam molde. Devolve None se não há
        duração real para a fase (não fabricar — invariante #8)."""
        dur = self.state.historical_durations_by_fase.get(str(fase_id))
        if not dur or dur <= 0:
            return None
        return RoutingRow(
            fase_id=str(fase_id),
            fase_nome=f"Reparação (fase {fase_id})",
            sequence=0,
            duration_hours=float(dur),
            source="repair_db",   # fonte REAL (não conta como fallback "standard")
            mold_required=False,
        )

    # Q.166.D — limiar de frequência: a rota canónica só inclui fases por onde uma
    # fração mínima de barcos REALMENTE passou (de of_fp). Sem isto, fases raras/
    # especiais (ex. Acabamento 3: só ~36 barcos de sempre) eram metidas em CENTENAS
    # de barcos sem rota → gargalo fantasma. 0.15 = >=15% dos barcos.
    _CANONICAL_MIN_BOAT_FRACTION = 0.15

    def _canonical_route(self) -> List["RoutingRow"]:
        """Q.164.C/Q.166.D — rota-padrão da NELO: catálogo canónico de fases COMUNS
        (`state.phase_catalog` filtrado por `boat_fraction` >= limiar, ordenado por
        FP_SEQUENCIA) com duração mediana REAL por fase. Último fallback p/ modelos
        sem rota nenhuma — planeia o barco em vez de o deixar invisível, mas SÓ pelas
        fases que a maioria dos barcos faz (não as raras/especiais).

        Fases sem mediana real são SALTADAS (invariante #8: não fabricar duração).
        Devolve [] se não há catálogo nem medianas (back-compat → no_route)."""
        catalog = getattr(self.state, "phase_catalog", None) or []
        if not catalog:
            return []
        dur_by_fase = getattr(self.state, "historical_durations_by_fase", {}) or {}
        rows: List[RoutingRow] = []
        for item in catalog:
            fase_id = str(item.get("fase_id") or "")
            if not fase_id:
                continue
            # Q.166.D — só fases COMUNS (a maioria dos barcos passa). boat_fraction
            # ausente (catálogo legacy sem a coluna) → não filtra (back-compat).
            frac = item.get("boat_fraction")
            if frac is not None and float(frac) < self._CANONICAL_MIN_BOAT_FRACTION:
                continue
            dur = dur_by_fase.get(fase_id)
            if not dur or dur <= 0:
                continue  # sem duração real → não inventar (invariante #8)
            fase_nome = str(item.get("fase_nome") or fase_id)
            rows.append(RoutingRow(
                fase_id=fase_id,
                fase_nome=fase_nome,
                sequence=int(item.get("sequence") or 0),
                duration_hours=float(dur),
                source="canonical_catalog",  # fonte REAL (não conta como "standard")
                mold_required=_phase_uses_mold(fase_nome),
            ))
        rows.sort(key=lambda r: r.sequence)  # defensivo: por FP_SEQUENCIA
        return rows

    def resolve_many(
        self,
        orders: List[Dict[str, Any]],
        horizon_start: Optional[datetime] = None,
    ) -> List[SchedulingOperation]:
        """Convenience: concatenate routings for a list of orders."""
        self.total_orders = len(orders)
        all_ops: List[SchedulingOperation] = []
        for order in orders:
            all_ops.extend(self.resolve(order, horizon_start))
        return all_ops

    @property
    def fallback_fraction(self) -> float:
        """Q.126.E — share of resolved ops that fell back to the 2x synthetic
        buffer (`source == "standard"`). 0.0 when nothing resolved. Read by
        the scheduler to decide whether to mark the plan `degraded`."""
        if self.resolved_ops <= 0:
            return 0.0
        return self.fallback_ops / self.resolved_ops

    @property
    def unplanned_count(self) -> int:
        """Q.131.H — nº de ordens sem rota (não planeadas). Lido pelo scheduler
        para emitir o alerta ORDERS_WITHOUT_ROUTING e preencher a resposta."""
        return len(self.unplanned)

    @property
    def orders_coverage(self) -> float:
        """Q.131.H — fração de ordens efectivamente planeadas (≥1 operação)
        sobre o total submetido a `resolve_many`. 1.0 quando nada foi pedido."""
        if self.total_orders <= 0:
            return 1.0
        return len(self.planned_order_ids) / self.total_orders

    # ------------------------------------------------------------------ #
    # Sources of routing data                                            #
    # ------------------------------------------------------------------ #

    def _history_for_order(self, order_id: str) -> List[RoutingRow]:
        """Return route from CuratedOrderPhase rows for this order_id."""
        phases = self._curated_phases()
        rows: List[RoutingRow] = []
        for p in phases:
            if str(getattr(p, "of_id", "")) != order_id:
                continue
            fase_id = str(getattr(p, "fase_id", ""))
            fase_nome = str(getattr(p, "fase_nome", "") or fase_id)
            sequence = int(getattr(p, "ordem", 0) or 0)
            real = getattr(p, "horas_reais", None) or getattr(p, "horas_finais", None) or 0
            duration = float(real) if real else 1.0
            rows.append(RoutingRow(
                fase_id=fase_id,
                fase_nome=fase_nome,
                sequence=sequence,
                duration_hours=max(duration, 0.1),
                source="history",
                mold_required=_phase_uses_mold(fase_nome),
            ))
        rows.sort(key=lambda r: r.sequence)
        return rows

    def _history_for_model(self, modelo_id: str) -> List[RoutingRow]:
        """Median duration per fase for orders of this model."""
        if not modelo_id:
            return []
        # Use pre-computed medians + phase names from curated_data
        phases = self._curated_phases()
        orders_of_model = self._orders_of_model(modelo_id)
        if not orders_of_model:
            return []

        # Aggregate: first order of this model gives the sequence; use
        # historical durations for each (fase_id, modelo_id).
        first_order_id = orders_of_model[0]
        template_rows: List[RoutingRow] = []
        for p in phases:
            if str(getattr(p, "of_id", "")) != first_order_id:
                continue
            fase_id = str(getattr(p, "fase_id", ""))
            fase_nome = str(getattr(p, "fase_nome", "") or fase_id)
            sequence = int(getattr(p, "ordem", 0) or 0)
            fallback_h = float(getattr(p, "horas_standard", 1.0) or 1.0)
            duration = self.state.median_duration_h(fase_id, modelo_id, fallback_h)
            template_rows.append(RoutingRow(
                fase_id=fase_id,
                fase_nome=fase_nome,
                sequence=sequence,
                duration_hours=duration,
                source="history",
                mold_required=_phase_uses_mold(fase_nome),
            ))
        template_rows.sort(key=lambda r: r.sequence)
        return template_rows

    def _history_for_model_db(self, modelo_id: str) -> List[RoutingRow]:
        """Q.126.B — real route from `factory_raw.of_fp`, pre-loaded into
        `FactoryState.historical_routes_by_model` (ordered production phases +
        median real `horas_reais`). Used when the in-memory curated layer is
        empty (the production reality) so the CPO plans on REAL history
        instead of the 2x synthetic buffer. Returns `[]` when no DB route was
        loaded for this model, so the caller falls to the standard template."""
        if not modelo_id:
            return []
        steps = (getattr(self.state, "historical_routes_by_model", {}) or {}).get(
            modelo_id
        ) or []
        rows: List[RoutingRow] = []
        for st in steps:
            fase_nome = str(st.get("fase_nome") or st.get("fase_id") or "")
            rows.append(RoutingRow(
                fase_id=str(st.get("fase_id", "")),
                fase_nome=fase_nome,
                sequence=int(st.get("sequence", 0) or 0),
                duration_hours=max(float(st.get("duration_hours", 1.0) or 1.0), 0.1),
                source="history_db",
                mold_required=_phase_uses_mold(fase_nome),
            ))
        rows.sort(key=lambda r: r.sequence)
        return rows

    def _template_for_model_db(self, modelo_id: str) -> List[RoutingRow]:
        """Q.131.G — real route from the ERP routing master (PRODUTO_FASE),
        pre-loaded into `FactoryState.template_routes_by_model` keyed by OF_P_ID.
        Per-phase duration = the mined `duration_p50_h` when present, else the
        cross-model median (`historical_durations_by_fase`). If ANY phase has
        NEITHER, the whole order is abandoned here (returns []) so it falls
        through to the (empty) standard template and is reported as unplanned —
        we never invent a duration (Spelke/zero-mock). source="db_template"
        (real route + real duration → NOT counted as synthetic fallback)."""
        if not modelo_id:
            return []
        steps = (getattr(self.state, "template_routes_by_model", {}) or {}).get(
            modelo_id
        ) or []
        if not steps:
            return []
        by_fase = getattr(self.state, "historical_durations_by_fase", {}) or {}
        rows: List[RoutingRow] = []
        for st in steps:
            fase_id = str(st.get("fase_id", ""))
            # Defesa-em-profundidade (Slice E): fases terminais (FP_PRODUCAO=false)
            # nunca entram no schedule mesmo que a SQL de carregamento as deixe passar.
            if fase_id in NON_PRODUCTION_PHASE_IDS:
                continue
            fase_nome = str(st.get("fase_nome") or fase_id)
            p50 = st.get("duration_p50_h")
            if p50 is not None and float(p50) > 0:
                duration = float(p50)
            else:
                fase_median = by_fase.get(fase_id)
                if not fase_median or float(fase_median) <= 0:
                    # Fase sem duração real (nem p50 nem mediana-por-fase): não
                    # inventamos — a ordem inteira fica por planear (Q.131.H).
                    return []
                duration = float(fase_median)
            rows.append(RoutingRow(
                fase_id=fase_id,
                fase_nome=fase_nome,
                sequence=int(st.get("sequence", 0) or 0),
                duration_hours=max(duration, 0.1),
                source="db_template",
                mold_required=_phase_uses_mold(fase_nome),
            ))
        rows.sort(key=lambda r: r.sequence)
        return rows

    def _standard_template(self, modelo_id: str) -> List[RoutingRow]:
        """Use FasesStandardModelos (standard template).

        FASE 0.3 (DEVA-02): when `self.duration_predictor` is wired the
        per-phase duration comes from `DurationModel.predict(...).p50_hours`.
        Otherwise the legacy `horas_standard * 2.0` buffer is used (NELO
        rule: standard times diverge from real by up to 25×).
        """
        standards = self._curated_standards()
        rows: List[RoutingRow] = []
        for s in standards:
            if modelo_id and str(getattr(s, "modelo_id", "")) != modelo_id:
                continue
            fase_id = str(getattr(s, "fase_id", ""))
            fase_nome = str(getattr(s, "fase_nome", "") or fase_id)
            sequence = int(getattr(s, "ordem", 0) or 0)
            std_h = float(getattr(s, "horas_standard", 1.0) or 1.0)

            duration_h, source = self._predicted_or_fallback_duration(
                fase_id=fase_id,
                fase_nome=fase_nome,
                modelo_id=modelo_id,
                fallback_h=std_h * 2.0,
                fallback_source="standard",
            )

            rows.append(RoutingRow(
                fase_id=fase_id,
                fase_nome=fase_nome,
                sequence=sequence,
                duration_hours=duration_h,
                source=source,
                mold_required=_phase_uses_mold(fase_nome),
            ))
        rows.sort(key=lambda r: r.sequence)
        return rows

    def _predicted_or_fallback_duration(
        self,
        *,
        fase_id: str,
        fase_nome: str,
        modelo_id: str,
        fallback_h: float,
        fallback_source: str,
    ) -> tuple[float, str]:
        """Use the active `DurationModel` if wired; else the fallback.

        Returns ``(duration_hours, source_label)`` where the label is
        ``"duration_model_p50"`` when the prediction succeeded, or the
        passed-in ``fallback_source`` otherwise. Any predictor exception
        is caught and downgraded to the fallback so a misconfigured ML
        artifact never breaks scheduling.
        """
        if self.duration_predictor is None:
            return max(fallback_h, 0.1), fallback_source
        try:
            team_size = self.state.team_size_for(fase_id, fase_nome)
            features = {
                "modelo_id": modelo_id or "",
                "fase_id": fase_id or "",
                "team_size": team_size,
                "mold_pocket_count": 0,
                "is_rework": 0,
                "queue_depth": 0,
            }
            prediction = self.duration_predictor.predict(features)
            p50 = float(prediction.get("p50_hours", 0.0) or 0.0)
            if p50 <= 0.0:
                return max(fallback_h, 0.1), fallback_source
            return max(p50, 0.1), "duration_model_p50"
        except Exception as exc:
            logger.warning(
                "DurationModel predict failed for fase=%s modelo=%s — using %s fallback (%s)",
                fase_id, modelo_id, fallback_source, exc,
            )
            return max(fallback_h, 0.1), fallback_source

    # ------------------------------------------------------------------ #
    # Curated-data access (best-effort, tolerant to missing data)        #
    # ------------------------------------------------------------------ #

    def _semantic_engine(self) -> Any:
        """Return the live `IngestEngine` singleton — the in-memory store
        whose `_curated_data` and `_active_ingestion_id` attributes
        `_curated_phases` / `_curated_standards` consume.

        Sprint Q.7 Fase 3 fix: the previous version called
        `SemanticQueriesInMemory()` (which requires an `engine: IngestEngine`
        positional argument), got TypeError, was silenced by the bare
        `except Exception`, and routing always returned empty curated
        data. Now we pull the same singleton the factory_data_product
        endpoints use, so the fallback "no curated layer" only triggers
        when the engine truly hasn't ingested anything yet.
        """
        try:
            from src.factory_data_product.api.endpoints import get_engine
            engine = get_engine()
            if engine is None:
                self.engine_unavailable = True
                bump_silent_fallback("routing_resolver", "engine_none")
            return engine
        except Exception:
            self.engine_unavailable = True
            bump_silent_fallback("routing_resolver", "engine_exception")
            return None

    def _curated_phases(self) -> List[Any]:
        engine = self._semantic_engine()
        if engine is None:
            # Sprint Q.8 Fase 1 — was a silent empty list. Now the operator
            # SEES that routing has nothing to resolve from history (the
            # caller will fall back to FasesStandardModelos templates with
            # 2× buffers, which can produce wildly wrong durations).
            logger.warning(
                "RoutingResolver: curated semantic engine unavailable — "
                "falling back to standards. Tenant=%s",
                getattr(self.state, "tenant_id", "?"),
            )
            return []
        active = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active, {}) if active else {}
        rows = scope.get("order_phases") or scope.get("CuratedOrderPhase") or []
        if not rows:
            logger.warning(
                "RoutingResolver: curated order_phases empty for tenant=%s "
                "ingestion=%s — falling back to standards",
                getattr(self.state, "tenant_id", "?"),
                active,
            )
        return rows

    def _curated_standards(self) -> List[Any]:
        engine = self._semantic_engine()
        if engine is None:
            return []
        active = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active, {}) if active else {}
        return scope.get("standards") or scope.get("FasesStandardModelos") or []

    def _orders_of_model(self, modelo_id: str) -> List[str]:
        engine = self._semantic_engine()
        if engine is None:
            return []
        active = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active, {}) if active else {}
        orders = scope.get("orders") or scope.get("CuratedOrder") or []
        return [
            str(getattr(o, "of_id", ""))
            for o in orders
            if str(getattr(o, "modelo_id", "")) == modelo_id
        ]


def _phase_uses_mold(phase_name: str) -> bool:
    """Heuristic: NELO phases that require a mold."""
    key = (phase_name or "").upper().replace(" ", "_")
    return any(tag in key for tag in ("LAMINAGEM", "PREP._MOLDE", "PREP_MOLDE", "DESMOLDE", "PINTURA_GEL_COAT"))


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
