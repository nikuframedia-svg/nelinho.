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

Deduplication (Q.173.AR.1, alinhada com a constraint Q.138.I): no máximo
um alerta ATIVO por (tenant, code) — candidatos múltiplos do mesmo código
são agregados num só (`_aggregate_candidates`) e o persist salta quando já
existe um ativo. Resolver/acknowledgar o alerta liberta o código para o
scan seguinte voltar a emitir.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.alerts.models import (
    CODE_BOTTLENECK_FORMATION,
    CODE_DELIVERY_RISK,
    CODE_PLAN_LIVE_STALENESS,
    CODE_QUALITY_DEGRADATION,
    CODE_SKILLS_CONCENTRATION,
    STATUS_ACTIVE,
    CopilotAlert,
)
from src.plan.models.order import OrderStatus, ProductionOrder
from src.shared.decorators import record_rule_firing
from src.shared.time import local_today

logger = logging.getLogger(__name__)


# Thresholds — tuned to a first-useful pass, not calibrated
BOTTLENECK_DAYS_THRESHOLD = 10.0
QUALITY_EVENTS_THRESHOLD = 500
# Q.31.H — janela de risco de entrega: barco com transporte dentro de N dias
# (ou já passado) e ainda em produção dispara o alerta.
DELIVERY_RISK_WINDOW_DAYS = 3
# Q.173.AR — dias sem nenhum plano LIVE aprovado a partir dos quais o loop
# plan-vs-actual está cego (só aprende de LIVE); 2x = CRITICAL.
PLAN_LIVE_STALENESS_DAYS = 7
# Q.173.AR.1 — entidades guardadas no alerta agregado (amostra; o total
# vai em context.count).
_AGGREGATE_SAMPLE = 15


def _aggregate_candidates(
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Q.173.AR.1 — colapsa candidatos do MESMO código num único alerta.

    A BD garante (Q.138.I) no máximo 1 alerta ativo por (tenant, code);
    um detector que emita 1 candidato por barco (delivery_risk: 167 em
    2026-06-12) tem de chegar ao persist já agregado — senão o flush
    rebenta na constraint. Severidade = a pior; entity_refs = amostra;
    context = contagem + amostras dos contextos individuais.
    """
    by_code: Dict[str, List[Dict[str, Any]]] = {}
    for c in candidates:
        by_code.setdefault(str(c.get("code")), []).append(c)

    out: List[Dict[str, Any]] = []
    for code, group in by_code.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        worst = next(
            (c for c in group if c.get("severity") == "CRITICAL"), group[0],
        )
        refs: List[str] = []
        for c in group:
            for ref in c.get("entity_refs") or []:
                if ref not in refs:
                    refs.append(ref)
        n_critical = sum(1 for c in group if c.get("severity") == "CRITICAL")
        out.append({
            "severity": worst["severity"],
            "code": code,
            "title": f"{worst['title']} (+{len(group) - 1} casos)",
            "message_pt": (
                f"{worst['message_pt']} Há {len(group)} casos ativos deste "
                f"alerta ({n_critical} críticos) — ver contexto para a amostra."
            ),
            "context": {
                "count": len(group),
                "count_critical": n_critical,
                "sample": [c.get("context", {}) for c in group[:5]],
            },
            "entity_refs": refs[:_AGGREGATE_SAMPLE],
        })
    return out


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
        # Q.173.M — thresholds EFETIVOS: a categoria 'alertas' da config de
        # tenant existia seeded mas nunca era lida (auditoria 2026-06-11:
        # mudar o knob não mudava nada). `scan()` carrega-os; chamadas
        # diretas aos detectors (testes) usam os defaults = constantes.
        self.bottleneck_days_threshold: float = BOTTLENECK_DAYS_THRESHOLD
        self.quality_events_threshold: int = QUALITY_EVENTS_THRESHOLD
        self.delivery_risk_window_days: int = DELIVERY_RISK_WINDOW_DAYS
        self.plan_live_staleness_days: int = PLAN_LIVE_STALENESS_DAYS

    # ------------------------------------------------------------------ #
    # Public                                                             #
    # ------------------------------------------------------------------ #

    async def scan(self) -> Dict[str, int]:
        """Run every detector. Returns a counters dict for observability."""
        await self._load_thresholds()
        created = 0
        skipped = 0

        detectors = (
            self._detect_bottleneck_formation,
            self._detect_skills_concentration,
            self._detect_quality_degradation,
            self._detect_delivery_risk,
            self._detect_plan_live_staleness,
        )
        for detector in detectors:
            try:
                candidates = await detector()
            except Exception as e:
                logger.warning(
                    f"Detector {detector.__name__} failed: {e}", exc_info=True
                )
                continue

            for candidate in _aggregate_candidates(candidates):
                persisted = await self._persist_if_new(candidate)
                if persisted:
                    created += 1
                    # Q.174.F8 — 3º evento DSL real: bottleneck novo dispara
                    # `wip_threshold` (regras tipo "WIP da Laminagem acima do
                    # limiar → criar decisão"). Só em alertas NOVOS (não a
                    # cada scan) e best-effort.
                    if candidate.get("code") == CODE_BOTTLENECK_FORMATION:
                        await self._emit_wip_threshold(candidate)
                else:
                    skipped += 1

        if created or skipped:
            await self.session.flush()

        return {
            "created": created,
            "skipped_duplicate": skipped,
            "detectors_run": len(detectors),
        }

    async def _emit_wip_threshold(self, candidate: Dict[str, Any]) -> None:
        """Q.174.F8 — emite o evento DSL `wip_threshold` quando um bottleneck
        NOVO é persistido (payload alinhado com a whitelist do rule_schema:
        phase_id/wip_count/threshold/as_of_date). Best-effort."""
        try:
            from src.governance.yaml_policy import EventType as _ET
            from src.governance.yaml_policy.runtime import get_engine as _yp
            from src.shared.time import utc_now_naive as _now

            ctx = candidate.get("context") or {}
            await _yp().on_event(
                _ET.WIP_THRESHOLD,
                {
                    "phase_id": str(ctx.get("fase_id") or ""),
                    "wip_count": float(ctx.get("backlog_dias") or 0.0),
                    "threshold": float(self.bottleneck_days_threshold),
                    "as_of_date": _now().date().isoformat(),
                },
                tenant_id=self.tenant_id,
                session=self.session,
            )
        except Exception as exc:  # pragma: no cover — motor de regras off
            logger.debug("wip_threshold rules skipped: %s", exc)

    async def _load_thresholds(self) -> None:
        """Q.173.M — lê os thresholds da categoria 'alertas' (best-effort).

        Sem config / erro → defaults (constantes do módulo). Mudar o knob
        em Configurações passa a mudar de facto o comportamento dos
        detectors — antes as keys eram seeded e ignoradas.
        """
        try:
            from src.core.services.tenant_config_service import (
                TenantConfigService,
            )
            cfg = await TenantConfigService(
                self.session, self.tenant_id,
            ).get_category("alertas")
        except (SQLAlchemyError, ImportError, ValueError, TypeError) as exc:
            logger.debug("alertas config indisponível (%s); defaults", exc)
            return

        def _num(key: str, fallback: float) -> float:
            try:
                return float(cfg[key]) if key in cfg else float(fallback)
            except (TypeError, ValueError):
                return float(fallback)

        self.bottleneck_days_threshold = _num(
            "bottleneck.days_threshold", BOTTLENECK_DAYS_THRESHOLD,
        )
        self.quality_events_threshold = int(_num(
            "quality.events_threshold", QUALITY_EVENTS_THRESHOLD,
        ))
        self.delivery_risk_window_days = int(_num(
            "delivery_risk.window_days", DELIVERY_RISK_WINDOW_DAYS,
        ))
        self.plan_live_staleness_days = int(_num(
            "plan_live.staleness_days", PLAN_LIVE_STALENESS_DAYS,
        ))

    # ------------------------------------------------------------------ #
    # Detectors                                                          #
    # ------------------------------------------------------------------ #

    @record_rule_firing(
        rule_id="alerts.bottleneck_formation",
        extract_payload=lambda self: {"threshold_days": self.bottleneck_days_threshold},
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
            if backlog_dias is None or backlog_dias < self.bottleneck_days_threshold:
                continue

            fase_id = str(row.get("fase_id") or row.get("id") or "")
            fase_nome = row.get("fase_nome") or row.get("nome") or fase_id
            if not fase_id:
                continue

            severity = "CRITICAL" if backlog_dias >= 2 * self.bottleneck_days_threshold else "WARN"
            candidates.append({
                "severity": severity,
                "code": CODE_BOTTLENECK_FORMATION,
                "title": f"Bottleneck na fase {fase_nome}",
                "message_pt": (
                    f"A fase '{fase_nome}' tem {backlog_dias:.1f} dias de backlog acumulado "
                    f"(limiar: {self.bottleneck_days_threshold:.0f} dias). Considera rever capacidade "
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
        extract_payload=lambda self: {"threshold_events": self.quality_events_threshold},
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
        if total_errors < self.quality_events_threshold:
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
                "threshold": self.quality_events_threshold,
            },
            "entity_refs": ["quality:global"],
        }]

    @record_rule_firing(
        rule_id="alerts.delivery_risk",
        extract_payload=lambda self: {"window_days": self.delivery_risk_window_days},
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
        today = local_today()
        horizon = today + timedelta(days=self.delivery_risk_window_days)
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

    async def _detect_plan_live_staleness(self) -> List[Dict[str, Any]]:
        """Q.173.AR — nenhum plano LIVE aprovado há N dias.

        O loop plan-vs-actual (Q.131-134) calibra o CPO comparando o plano
        LIVE com a execução real — só aprende de commits LIVE. Com a fábrica
        a viver de DRAFTs (auditoria 2026-06-11: 154 DRAFT vs 2 LIVE, último
        2026-06-02), o modelo de desvio fica silenciosamente cego. Lê
        `plan_schedule_commits` diretamente; enquanto houver um alerta ATIVO
        deste código não re-emite (o scan corre de 15 em 15 min — sem spam).
        """
        from sqlalchemy import func

        from src.plan.cpo.commits import ScheduleCommit

        existing = await self.session.execute(
            select(CopilotAlert.id).where(
                and_(
                    CopilotAlert.tenant_id == self.tenant_id,
                    CopilotAlert.code == CODE_PLAN_LIVE_STALENESS,
                    CopilotAlert.status == STATUS_ACTIVE,
                )
            ).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return []

        last_live = (
            await self.session.execute(
                select(func.max(ScheduleCommit.created_at)).where(
                    and_(
                        ScheduleCommit.tenant_id == self.tenant_id,
                        ScheduleCommit.status == "LIVE",
                    )
                )
            )
        ).scalar()

        threshold = max(1, int(self.plan_live_staleness_days))
        # created_at é naive-UTC (padrão do modelo) — comparar naive com naive.
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

        async def _count_drafts_since(cutoff) -> int:
            stmt = select(func.count()).select_from(ScheduleCommit).where(
                and_(
                    ScheduleCommit.tenant_id == self.tenant_id,
                    ScheduleCommit.status == "DRAFT",
                )
            )
            if cutoff is not None:
                stmt = stmt.where(ScheduleCommit.created_at > cutoff)
            return int((await self.session.execute(stmt)).scalar() or 0)

        if last_live is None:
            drafts = await _count_drafts_since(None)
            if drafts == 0:
                return []  # instalação sem planos — nada a alertar
            dias: Optional[int] = None
            quando = "nunca"
        else:
            last_naive = (
                last_live.replace(tzinfo=None) if last_live.tzinfo else last_live
            )
            dias = (now_naive - last_naive).days
            if dias < threshold:
                return []
            drafts = await _count_drafts_since(last_naive)
            quando = f"há {dias} dia(s) ({last_naive.date().isoformat()})"

        severity = "CRITICAL" if (dias is None or dias >= 2 * threshold) else "WARN"
        return [{
            "severity": severity,
            "code": CODE_PLAN_LIVE_STALENESS,
            "title": "Sem plano LIVE — calibração do CPO parada",
            "message_pt": (
                f"O último plano aprovado (LIVE) foi {quando}; desde então há "
                f"{drafts} rascunho(s) por aprovar. O loop plano-vs-real só "
                "aprende de planos LIVE — sem aprovação, o CPO não recalibra "
                "os desvios. Aprova um plano no Planeamento (botão 'Aprovar "
                "plano') ou ajusta o limiar em Configurações → Alertas."
            ),
            "context": {
                "last_live_at": (
                    last_live.isoformat() if last_live is not None else None
                ),
                "days_without_live": dias,
                "drafts_since_live": drafts,
                "threshold_days": threshold,
            },
            "entity_refs": ["plan:live-staleness"],
        }]

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
        Returns True if inserted, False if an ACTIVE alert with the same code
        already exists.

        Q.173.AR.1 — alinhado com a constraint Q.138.I da BD (unique partial
        index (tenant_id, code) WHERE status='active'): existe NO MÁXIMO um
        alerta ativo por código. O dedup antigo (janela de 60 min + match por
        entity_ref) violava a constraint sempre que um detector emitia >1
        candidato do mesmo código — combinado com o bug aware/naive da janela,
        o scan inteiro rebentava e NENHUM alerta novo nasceu desde 2026-06-01.
        Candidatos múltiplos do mesmo código são agregados a montante
        (`_aggregate_candidates`).
        """
        stmt = select(CopilotAlert.id).where(
            and_(
                CopilotAlert.tenant_id == self.tenant_id,
                CopilotAlert.code == candidate["code"],
                CopilotAlert.status == STATUS_ACTIVE,
            )
        ).limit(1)
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
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
