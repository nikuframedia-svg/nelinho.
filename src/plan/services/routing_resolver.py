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

from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingOperation

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
    # "history" | "standard" | "duration_model_p50"
    #   | "routing_template_p50" | "routing_template"
    source: str
    mold_required: bool = False


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
        4. If none: use the ERP-synced routing template pre-loaded into
           `FactoryState.routing_by_model`.
        """
        horizon_start = horizon_start or datetime.utcnow()
        order_id = str(order.get("of_id") or order.get("order_id") or "")
        modelo_id = str(order.get("modelo_id") or "")
        product_id = str(order.get("produto_id") or modelo_id)

        if not order_id:
            logger.warning("RoutingResolver: order without of_id — skipping")
            return []

        # 1. Try history for this specific order
        rows = self._history_for_order(order_id)
        if not rows:
            # 2. Fall back to any historical order of the same model
            rows = self._history_for_model(modelo_id)
        if not rows:
            # 3. Fall back to standard template (curated in-memory layer)
            rows = self._standard_template(modelo_id)
        if not rows:
            # 4. Fall back to the ERP-synced routing template in the DB
            rows = self._db_routing_template(modelo_id)

        if not rows:
            logger.info(
                f"RoutingResolver: no route found for order={order_id} model={modelo_id}"
            )
            return []

        due_date = _parse_datetime(order.get("data_entrega_prevista"))
        skills_by_phase = self.state.skill_matrix
        ops: List[SchedulingOperation] = []

        for row in rows:
            phase_name = row.fase_nome or row.fase_id
            team_size = self.state.team_size_for(row.fase_id, phase_name)
            required_skills = [row.fase_id] if row.fase_id in skills_by_phase else []

            op = SchedulingOperation(
                operation_id=f"{order_id}::{row.fase_id}",
                order_id=order_id,
                product_id=product_id,
                sequence=row.sequence,
                operation_code=phase_name,
                duration_minutes=max(1.0, row.duration_hours * 60.0),
                machine_id=None,  # left unset — decoder assigns from machine pool
                setup_family=phase_name,
                due_date=due_date,
                priority=1.0,
                predecessor_ops=[],
                required_skills=required_skills,
                alternative_machines=[],
                mold_id=None,
                mold_required=row.mold_required,
                model_id=modelo_id,
                team_size=team_size,
                phase_id=row.fase_id,
            )
            ops.append(op)

        return ops

    def resolve_many(
        self,
        orders: List[Dict[str, Any]],
        horizon_start: Optional[datetime] = None,
    ) -> List[SchedulingOperation]:
        """Convenience: concatenate routings for a list of orders."""
        all_ops: List[SchedulingOperation] = []
        for order in orders:
            all_ops.extend(self.resolve(order, horizon_start))
        return all_ops

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

    def _db_routing_template(self, modelo_id: str) -> List[RoutingRow]:
        """Routing from the ERP-synced templates pre-loaded into FactoryState.

        `FactoryState.load()` joins `plan.model_routing_assignment` to its
        primary template's phases and stores them in
        `state.routing_by_model`. This is the source that actually has
        data after an ERP sync — the curated in-memory `standards` layer
        is never populated (`transformer._transform_standards` is a no-op).

        Duration: the template's `duration_p50_h` when present; otherwise
        the duration predictor / fallback via
        `_predicted_or_fallback_duration`.
        """
        if not modelo_id:
            return []
        template = self.state.routing_by_model.get(modelo_id) or []
        rows: List[RoutingRow] = []
        for tr in template:
            if tr.duration_p50_h and tr.duration_p50_h > 0:
                duration_h = max(tr.duration_p50_h, 0.1)
                source = "routing_template_p50"
            else:
                duration_h, source = self._predicted_or_fallback_duration(
                    fase_id=tr.fase_id,
                    fase_nome=tr.fase_nome,
                    modelo_id=modelo_id,
                    fallback_h=1.0,
                    fallback_source="routing_template",
                )
            rows.append(RoutingRow(
                fase_id=tr.fase_id,
                fase_nome=tr.fase_nome,
                sequence=tr.seq,
                duration_hours=duration_h,
                source=source,
                mold_required=tr.requires_mold or _phase_uses_mold(tr.fase_nome),
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
