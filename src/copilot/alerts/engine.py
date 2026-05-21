"""
ProdPlan ONE - Copilot Alerts Engine
=====================================

Runs a set of detectors over the Factory Data Product semantic layer
and emits `CopilotAlert` rows when conditions are met.

Detectors (Sprint C baseline):
- bottleneck_formation: get_bottlenecks() → alert per phase when
  backlog in days > BOTTLENECK_DAYS_THRESHOLD.
- skills_concentration: get_skills_risk(min_capable=2) → alert per phase
  that has fewer than 2 capable employees (SPOF risk).
- quality_degradation: get_quality() → alert when total quality events
  exceed QUALITY_EVENTS_THRESHOLD in the current window.
- delivery_risk: alert per ProductionOrder still IN_PROGRESS whose
  transport_date falls within DELIVERY_RISK_WINDOW_DAYS (or is already
  past). Reads production_orders directly — no semantic layer needed.

Deduplication: for each detector, scans the last
`ALERT_DEDUPE_WINDOW_MINUTES` of alerts and skips any that already match
`(code, entity_refs[0])`.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.alerts.models import (
    CODE_BOTTLENECK_FORMATION,
    CODE_DELIVERY_RISK,
    CODE_QUALITY_DEGRADATION,
    CODE_SKILLS_CONCENTRATION,
    STATUS_ACTIVE,
    CopilotAlert,
)
from src.plan.models.order import OrderStatus, ProductionOrder
from src.shared.decorators import record_rule_firing

logger = logging.getLogger(__name__)


# Thresholds — tuned to a first-useful pass, not calibrated
BOTTLENECK_DAYS_THRESHOLD = 10.0
QUALITY_EVENTS_THRESHOLD = 500
ALERT_DEDUPE_WINDOW_MINUTES = 60
# Q.31.H — janela de risco de entrega: barco com transporte dentro de N dias
# (ou já passado) e ainda em produção dispara o alerta.
DELIVERY_RISK_WINDOW_DAYS = 3


class AlertsEngine:
    """
    Run detectors against the semantic layer and persist `CopilotAlert` rows.

    Usage:
        engine = AlertsEngine(session=db, tenant_id=tid)
        summary = await engine.scan()
        # summary = {"created": N, "skipped_duplicate": M, "detectors_run": 4}
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        semantic_queries: Optional[Any] = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self._sq = semantic_queries  # Inject for tests; lazy-loaded otherwise

    # ------------------------------------------------------------------ #
    # Public                                                             #
    # ------------------------------------------------------------------ #

    async def scan(self) -> Dict[str, int]:
        """Run every detector. Returns a counters dict for observability."""
        created = 0
        skipped = 0

        for detector in (
            self._detect_bottleneck_formation,
            self._detect_skills_concentration,
            self._detect_quality_degradation,
            self._detect_delivery_risk,
        ):
            try:
                candidates = await detector()
            except Exception as e:
                logger.warning(
                    f"Detector {detector.__name__} failed: {e}", exc_info=True
                )
                continue

            for candidate in candidates:
                persisted = await self._persist_if_new(candidate)
                if persisted:
                    created += 1
                else:
                    skipped += 1

        if created or skipped:
            await self.session.flush()

        return {
            "created": created,
            "skipped_duplicate": skipped,
            "detectors_run": 4,
        }

    # ------------------------------------------------------------------ #
    # Detectors                                                          #
    # ------------------------------------------------------------------ #

    @record_rule_firing(
        rule_id="alerts.bottleneck_formation",
        extract_payload=lambda self: {"threshold_days": BOTTLENECK_DAYS_THRESHOLD},
        serialise_output=lambda candidates: {
            "candidate_count": len(candidates),
            "fase_ids": [c.get("context", {}).get("fase_id") for c in candidates],
        },
    )
    async def _detect_bottleneck_formation(self) -> List[Dict[str, Any]]:
        result = self._safe_query("get_bottlenecks")
        if not result or not result.get("rows"):
            return []

        candidates: List[Dict[str, Any]] = []
        for row in result["rows"]:
            backlog_dias = _coerce_float(row.get("backlog_dias"))
            if backlog_dias is None or backlog_dias < BOTTLENECK_DAYS_THRESHOLD:
                continue

            fase_id = str(row.get("fase_id") or row.get("id") or "")
            fase_nome = row.get("fase_nome") or row.get("nome") or fase_id
            if not fase_id:
                continue

            severity = "CRITICAL" if backlog_dias >= 2 * BOTTLENECK_DAYS_THRESHOLD else "WARN"
            candidates.append({
                "severity": severity,
                "code": CODE_BOTTLENECK_FORMATION,
                "title": f"Bottleneck na fase {fase_nome}",
                "message_pt": (
                    f"A fase '{fase_nome}' tem {backlog_dias:.1f} dias de backlog acumulado "
                    f"(limiar: {BOTTLENECK_DAYS_THRESHOLD:.0f} dias). Considera rever capacidade "
                    f"ou reprioritizar ordens em curso."
                ),
                "context": {
                    "fase_id": fase_id,
                    "fase_nome": fase_nome,
                    "backlog_dias": backlog_dias,
                    "backlog_horas": _coerce_float(row.get("backlog_horas")),
                },
                "entity_refs": [f"fase:{fase_id}"],
            })
        return candidates

    @record_rule_firing(
        rule_id="alerts.skills_concentration",
        extract_payload=lambda self: {"min_capable": 2},
        serialise_output=lambda candidates: {
            "candidate_count": len(candidates),
            "fase_ids": [c.get("context", {}).get("fase_id") for c in candidates],
        },
    )
    async def _detect_skills_concentration(self) -> List[Dict[str, Any]]:
        result = self._safe_query("get_skills_risk", min_capable=2)
        if not result or not result.get("rows"):
            return []

        candidates: List[Dict[str, Any]] = []
        for row in result["rows"]:
            fase_id = str(row.get("fase_id") or row.get("id") or "")
            fase_nome = row.get("fase_nome") or fase_id
            capable = row.get("num_funcionarios_aptos", row.get("capable_count", 0)) or 0
            if not fase_id:
                continue

            severity = "CRITICAL" if capable <= 1 else "WARN"
            candidates.append({
                "severity": severity,
                "code": CODE_SKILLS_CONCENTRATION,
                "title": f"SPOF na fase {fase_nome}",
                "message_pt": (
                    f"A fase '{fase_nome}' tem apenas {capable} funcionário(s) apto(s). "
                    f"Em caso de ausência, a fase pára. Considera cross-training."
                ),
                "context": {
                    "fase_id": fase_id,
                    "fase_nome": fase_nome,
                    "capable": capable,
                },
                "entity_refs": [f"fase:{fase_id}"],
            })
        return candidates

    @record_rule_firing(
        rule_id="alerts.quality_degradation",
        extract_payload=lambda self: {"threshold_events": QUALITY_EVENTS_THRESHOLD},
        serialise_output=lambda candidates: {
            "candidate_count": len(candidates),
            "total_errors": (
                candidates[0]["context"]["total_errors"] if candidates else 0
            ),
        },
    )
    async def _detect_quality_degradation(self) -> List[Dict[str, Any]]:
        """
        Baseline version: no week-over-week comparison (requires persisted
        historical quality windows). Emits one summary alert when total
        detected errors exceed QUALITY_EVENTS_THRESHOLD.
        """
        result = self._safe_query("get_quality")
        if not result or not result.get("rows"):
            return []

        total_errors = sum(
            (_coerce_int(r.get("total_erros")) or 0) for r in result["rows"]
        )
        if total_errors < QUALITY_EVENTS_THRESHOLD:
            return []

        top_types = [
            (r.get("erro_tipo") or r.get("tipo") or "?")
            for r in result["rows"][:3]
        ]

        return [{
            "severity": "WARN",
            "code": CODE_QUALITY_DEGRADATION,
            "title": "Volume de eventos de qualidade acima do limiar",
            "message_pt": (
                f"Foram detectados {total_errors} eventos de qualidade. "
                f"Tipos mais frequentes: {', '.join(top_types)}. "
                f"Revê auto-diagnóstico e prioriza inspeções."
            ),
            "context": {
                "total_errors": total_errors,
                "top_error_types": top_types,
                "threshold": QUALITY_EVENTS_THRESHOLD,
            },
            "entity_refs": ["quality:global"],
        }]

    @record_rule_firing(
        rule_id="alerts.delivery_risk",
        extract_payload=lambda self: {"window_days": DELIVERY_RISK_WINDOW_DAYS},
        serialise_output=lambda candidates: {
            "candidate_count": len(candidates),
            "hulls": [c.get("context", {}).get("hull") for c in candidates],
        },
    )
    async def _detect_delivery_risk(self) -> List[Dict[str, Any]]:
        """Barcos com transporte próximo/passado e ainda em produção.

        Q.31.H — substitui o stub. Não precisa do semantic layer: lê
        `production_orders` directamente (status IN_PROGRESS + transport_date
        dentro da janela). Um barco por concluir cuja expedição é amanhã é
        risco de entrega.
        """
        today = date.today()
        horizon = today + timedelta(days=DELIVERY_RISK_WINDOW_DAYS)
        stmt = select(ProductionOrder).where(
            and_(
                ProductionOrder.tenant_id == self.tenant_id,
                ProductionOrder.status == OrderStatus.IN_PROGRESS,
                ProductionOrder.transport_date.isnot(None),
                ProductionOrder.transport_date <= horizon,
            )
        )
        rows = list((await self.session.execute(stmt)).scalars().all())

        candidates: List[Dict[str, Any]] = []
        for o in rows:
            overdue = o.transport_date < today
            dias = (o.transport_date - today).days
            quando = (
                f"era esperado há {abs(dias)} dia(s)" if overdue
                else "é hoje" if dias == 0
                else f"é daqui a {dias} dia(s)"
            )
            candidates.append({
                "severity": "CRITICAL" if overdue else "WARN",
                "code": CODE_DELIVERY_RISK,
                "title": f"Risco de atraso — barco #{o.legacy_id}",
                "message_pt": (
                    f"O barco #{o.legacy_id} ({o.product_type or '?'}) tem transporte "
                    f"que {quando} mas ainda está em produção (fase "
                    f"'{o.current_phase_name}'). Confirma se chega a tempo da expedição."
                ),
                "context": {
                    "order_id": str(o.id),
                    "hull": o.legacy_id,
                    "transport_date": o.transport_date.isoformat(),
                    "current_phase": o.current_phase_name,
                    "overdue": overdue,
                },
                "entity_refs": [f"barco:{o.legacy_id}"],
            })
        return candidates

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #

    def _get_semantic_queries(self):
        """Lazy import SemanticQueriesInMemory (avoid heavy import at module load).

        FASE 3.6 (HIGH-50) — the previous version called
        ``SemanticQueriesInMemory()`` with no engine argument, hit the
        TypeError silently inside ``except Exception``, and returned None
        for every call. Net effect: every detector in this engine got an
        empty result, so no alerts ever fired. We now resolve the global
        IngestEngine singleton and pass it; if that fails (no factory
        ingestion ever ran) we log loudly instead of debug-whispering.
        """
        if self._sq is not None:
            return self._sq
        try:
            from src.factory_data_product.api.endpoints import get_engine
            from src.factory_data_product.services.semantic_queries_inmemory import (
                SemanticQueriesInMemory,
            )
            engine = get_engine()
            if engine is None:
                logger.warning(
                    "AlertsEngine.tenant=%s: factory IngestEngine unavailable — "
                    "alerts disabled until /v1/factory-data/ingest runs.",
                    self.tenant_id,
                )
                return None
            self._sq = SemanticQueriesInMemory(engine)
            return self._sq
        except Exception as e:
            logger.warning(
                "AlertsEngine.tenant=%s: SemanticQueriesInMemory unavailable (%s) — "
                "no alerts will be emitted this scan.",
                self.tenant_id, e,
            )
            return None

    def _safe_query(self, method_name: str, **kwargs) -> Optional[Dict[str, Any]]:
        # FASE 3.6 (HIGH-50) — pass tenant_id to the semantic helper so a
        # future tenant-aware variant can scope the curated lookup.
        # Today's in-memory engine still operates on a single global
        # `_curated_data` dict (the curated layer doesn't yet partition
        # by tenant). When multiple tenants share one process, an alert
        # raised for tenant A could carry data from tenant B's last
        # ingestion. We surface the risk in logs once per scan; the full
        # fix lands when the curated layer becomes tenant-keyed.
        sq = self._get_semantic_queries()
        if sq is None:
            return None
        kwargs.setdefault("tenant_id", self.tenant_id)
        try:
            fn = getattr(sq, method_name)
            try:
                result = fn(**kwargs)
            except TypeError:
                # Backwards compat: drop tenant_id when the method's
                # current signature doesn't accept it. Log once so the
                # tenant scope gap stays visible.
                kwargs.pop("tenant_id", None)
                logger.warning(
                    "AlertsEngine.tenant=%s: %s does not accept tenant_id; "
                    "result may include rows from other tenants.",
                    self.tenant_id, method_name,
                )
                result = fn(**kwargs)
            if result and result.get("status") != "BLOCKED":
                return result
        except Exception as e:
            logger.debug(f"Semantic query '{method_name}' failed: {e}")
        return None

    async def _persist_if_new(self, candidate: Dict[str, Any]) -> bool:
        """
        Returns True if inserted, False if skipped because a recent duplicate
        (same code + same primary entity_ref) already exists as active.
        """
        dedupe_key = candidate["entity_refs"][0] if candidate.get("entity_refs") else None
        if dedupe_key:
            since = datetime.now(timezone.utc) - timedelta(minutes=ALERT_DEDUPE_WINDOW_MINUTES)
            stmt = select(CopilotAlert.id).where(
                and_(
                    CopilotAlert.tenant_id == self.tenant_id,
                    CopilotAlert.code == candidate["code"],
                    CopilotAlert.status == STATUS_ACTIVE,
                    CopilotAlert.created_at >= since,
                )
            ).limit(50)
            existing = await self.session.execute(stmt)
            rows = existing.scalars().all()
            if rows:
                # Check entity_refs manually since JSONB contains queries vary by dialect
                dup_stmt = select(CopilotAlert).where(
                    CopilotAlert.id.in_(rows)
                )
                dups = await self.session.execute(dup_stmt)
                for alert in dups.scalars().all():
                    refs = alert.entity_refs or []
                    if refs and refs[0] == dedupe_key:
                        return False

        alert = CopilotAlert(
            id=uuid4(),
            tenant_id=self.tenant_id,
            severity=candidate["severity"],
            code=candidate["code"],
            title=candidate["title"],
            message_pt=candidate["message_pt"],
            context=candidate.get("context", {}),
            entity_refs=candidate.get("entity_refs", []),
            status=STATUS_ACTIVE,
        )
        # Q.66.B.3: CopilotAlert e ALERTA (notificacao para o utilizador),
        # nao state autoritativo — vive em copilot.alert, nao governance.
        self.session.add(alert)  # noqa: audit_coverage  # alert notification, not gov state
        return True


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
