"""Q.115.D — Auto-propose listener: cria Decision(status=PROPOSED) a partir de eventos Kafka.

Tópicos consumidos:
  - orders.created       → nova OF criada (ERP sync 5min)
  - config.updated       → config alterada (replan_hook delega para cá)
  - quality.defect_logged → defeito registado num barco
  - plan.manual_override → drag-drop manual (Q.115.C)

Fluxo por evento:
  1. Debounce 30s (mesma chave → timer reset)
  2. Rate-limit: max 1 Decision por chave por 5 min
  3. Corre CPO engine (modo propose-only, sem write_gate)
  4. Cria Decision(status=PROPOSED, source=auto_propose)
  5. Audit log (mesma tx que INSERT)
  6. Retorna Decision criada (ou None se rate-limited / CPO falhou)

Invariantes:
- NUNCA executa (status=PROPOSED apenas) — Q.17 requires_human_approval
- CoeficienteX NUNCA aqui (pertence a src/profit/)
- Tenant isolation em cada chave
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.services.debouncer import Debouncer
from src.plan.services.rate_limiter import RateLimiter
from src.shared.models.governance import DecisionStatus, SharedDecisionRun

logger = logging.getLogger(__name__)

# UUID de sistema (sem utilizador humano a propor)
_SYSTEM_ACTOR = UUID("00000000-0000-0000-0000-000000000002")

# Tópicos que este serviço sabe tratar
HANDLED_TOPICS = frozenset({
    "orders.created",
    "config.updated",
    "quality.defect_logged",
    "plan.manual_override",
})


def _debounce_key(topic: str, payload: Dict[str, Any]) -> str:
    """Calcula a chave de debounce + rate-limit a partir do tópico e payload.

    Garante tenant isolation: tenant_id é sempre prefixo da chave.
    """
    tenant_id = str(payload.get("tenant_id", "unknown"))

    if topic == "orders.created":
        of_id = str(payload.get("of_id") or payload.get("order_id") or "")
        return f"{tenant_id}:orders.created:{of_id}"

    if topic == "config.updated":
        config_key = str(payload.get("config_key") or payload.get("config_type") or "")
        return f"{tenant_id}:config.updated:{config_key}"

    if topic == "quality.defect_logged":
        boat_id = str(payload.get("boat_id") or payload.get("of_id") or "")
        return f"{tenant_id}:quality.defect_logged:{boat_id}"

    if topic == "plan.manual_override":
        commit_sha = str(payload.get("commit_sha") or "")
        return f"{tenant_id}:plan.manual_override:{commit_sha}"

    return f"{tenant_id}:{topic}:unknown"


class AutoProposeService:
    """Listener Kafka que cria Decisions propostas automaticamente."""

    def __init__(
        self,
        session_factory,
        rate_limiter: Optional[RateLimiter] = None,
        debouncer: Optional[Debouncer] = None,
        cpo_engine_runner=None,
    ) -> None:
        """
        Args:
            session_factory: callable assíncrono que devolve AsyncSession
                (ex: `async_session_factory` de shared.database).
            rate_limiter: instância de RateLimiter; se None, cria uma nova.
            debouncer: instância de Debouncer; se None, cria uma nova.
            cpo_engine_runner: callable async(tenant_id, payload) → dict com
                kpis + operations. Se None, usa _noop_cpo_runner.
        """
        self._session_factory = session_factory
        self._rate_limiter = rate_limiter or RateLimiter()
        self._debouncer = debouncer or Debouncer()
        self._cpo_runner = cpo_engine_runner or _noop_cpo_runner

    async def handle_event(
        self,
        topic: str,
        payload: Dict[str, Any],
    ) -> None:
        """Entrada pública do listener Kafka.

        Passo 1: debounce. O callback real (_execute_after_debounce) só é
        invocado depois de 30s de silêncio para esta chave.
        """
        if topic not in HANDLED_TOPICS:
            logger.debug("auto_propose: tópico ignorado: %s", topic)
            return

        key = _debounce_key(topic, payload)
        await self._debouncer.debounce(
            key=key,
            payload={"topic": topic, "payload": payload},
            callback=self._execute_after_debounce,
        )

    async def _execute_after_debounce(
        self,
        key: str,
        data: Dict[str, Any],
    ) -> Optional[SharedDecisionRun]:
        """Invocado pelo Debouncer após 30s de silêncio."""
        topic: str = data["topic"]
        payload: Dict[str, Any] = data["payload"]

        # Passo 2: rate-limit
        if not self._rate_limiter.is_allowed(key):
            return None

        # Passo 3: CPO engine (propose-only)
        tenant_id_raw = payload.get("tenant_id")
        try:
            tenant_id = UUID(str(tenant_id_raw))
        except (TypeError, ValueError):
            logger.warning(
                "auto_propose: tenant_id inválido no payload do tópico %s: %s",
                topic,
                tenant_id_raw,
            )
            return None

        try:
            cpo_result = await self._cpo_runner(tenant_id=tenant_id, payload=payload)
        except Exception as exc:
            logger.warning(
                "auto_propose: CPO engine falhou para chave=%s: %s — Decision NÃO criada",
                key,
                exc,
            )
            return None

        # Passo 4+5: criar Decision + audit_log na mesma tx
        decision = await self._persist_decision(
            tenant_id=tenant_id,
            topic=topic,
            payload=payload,
            cpo_result=cpo_result,
        )

        if decision is not None:
            # Passo 2b: registar no rate-limiter só após sucesso
            self._rate_limiter.record(key)
            logger.info(
                "auto_propose: Decision criada id=%s chave=%s tópico=%s",
                decision.id,
                key,
                topic,
            )

        return decision

    async def _persist_decision(
        self,
        *,
        tenant_id: UUID,
        topic: str,
        payload: Dict[str, Any],
        cpo_result: Dict[str, Any],
    ) -> Optional[SharedDecisionRun]:
        """Cria SharedDecisionRun + audit_log na mesma transacção.

        Delega no helper partilhado ``propose_decision_row`` (Q.157.A) para não
        duplicar o INSERT+audit+SSE entre este listener Kafka e o
        ``auto_propose_signals_job`` in-process.
        """
        return await propose_decision_row(
            self._session_factory,
            tenant_id=tenant_id,
            title=_decision_title(topic, payload),
            action_type="AUTO_PROPOSE_SCHEDULE",
            target=_decision_target(topic, payload),
            sandbox_result=cpo_result,
            after_state={"commit_sha": cpo_result.get("commit_sha") or ""},
            audit_reason=f"Q.115.D auto_propose tópico={topic}",
            audit_extra={"source": "auto_propose", "trigger_topic": topic},
            sse_extra={"source": "auto_propose", "trigger_topic": topic},
        )


# ---------------------------------------------------------------------------
# Q.157.A — helper partilhado de persistência de decisões propostas
# ---------------------------------------------------------------------------

async def propose_decision_row(
    session_factory,
    *,
    tenant_id: UUID,
    title: str,
    action_type: str,
    target: str,
    sandbox_result: Dict[str, Any],
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    audit_reason: str = "",
    audit_extra: Optional[Dict[str, Any]] = None,
    sse_extra: Optional[Dict[str, Any]] = None,
) -> SharedDecisionRun:
    """INSERT ``SharedDecisionRun(status=PROPOSED)`` + ``audit_change`` na MESMA
    tx + publish SSE ``DECISION_PROPOSED`` (best-effort).

    Extraído de ``AutoProposeService._persist_decision`` (Q.157.A) para ser
    reutilizado pelo ``auto_propose_signals_job``. Invariantes preservadas:
    - **Q.17**: ``status`` sempre ``PROPOSED``, ``proposed_by=_SYSTEM_ACTOR``
      (≠ aprovador humano → SoD passa). Nunca executa.
    - **Audit trail (#7)**: o ``audit_change`` corre na mesma sessão/tx do INSERT.
    """
    now = datetime.now(timezone.utc)
    decision = SharedDecisionRun(
        tenant_id=tenant_id,
        title=title,
        action_type=action_type,
        target=target,
        status=DecisionStatus.PROPOSED.value,
        sandbox_result=sandbox_result,
        before_state=before_state or {},
        after_state=after_state if after_state is not None else {},
        proposed_by=_SYSTEM_ACTOR,
        proposed_at=now,
    )

    async with session_factory() as session:
        session.add(decision)
        await session.flush()

        await audit_change(
            session,
            tenant_id=tenant_id,
            entity_type="decision_run",
            entity_id=decision.id,
            action="INSERT",
            new_values={
                "title": title,
                "action_type": action_type,
                "status": DecisionStatus.PROPOSED.value,
                **(audit_extra or {}),
            },
            actor_id=_SYSTEM_ACTOR,
            reason=audit_reason or f"auto_propose {action_type}",
        )
        await session.commit()

    # Q.153 — publicar DECISION_PROPOSED no canal realtime (SSE) para a página
    # /decisoes refletir a nova proposta sem esperar o poll de 5s. Best-effort:
    # a decisão e o audit já estão committados; uma falha de publish não os desfaz.
    await _publish_decision_proposed(tenant_id, decision, sse_extra)
    return decision


async def _publish_decision_proposed(
    tenant_id: UUID,
    decision: SharedDecisionRun,
    sse_extra: Optional[Dict[str, Any]],
) -> None:
    """Publica DECISION_PROPOSED (best-effort; falha não desfaz a decisão)."""
    try:
        from src.shared.kafka_client import EventBase, Topics, publish_event

        await publish_event(
            Topics.DECISION_PROPOSED,
            EventBase(
                event_type="DECISION_PROPOSED",
                tenant_id=tenant_id,
                source_module="plan.services.auto_propose",
                payload={
                    "decision_id": str(decision.id),
                    "action_type": decision.action_type,
                    "title": decision.title,
                    **(sse_extra or {}),
                },
            ),
        )
    except Exception as exc:  # pragma: no cover - best-effort
        logger.warning(
            "DECISION_PROPOSED publish failed for %s: %s — decisão na mesma criada",
            decision.id, exc,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decision_title(topic: str, payload: Dict[str, Any]) -> str:
    if topic == "orders.created":
        of_id = payload.get("of_id") or payload.get("order_id") or "?"
        return f"Replaneamento automático — nova OF {of_id}"
    if topic == "config.updated":
        key = payload.get("config_key") or payload.get("config_type") or "?"
        return f"Replaneamento automático — config alterada: {key}"
    if topic == "quality.defect_logged":
        boat = payload.get("boat_id") or payload.get("of_id") or "?"
        return f"Replaneamento automático — defeito registado barco {boat}"
    if topic == "plan.manual_override":
        sha = (payload.get("commit_sha") or "")[:8]
        return f"Replaneamento automático — override manual {sha}"
    return f"Replaneamento automático — {topic}"


def _decision_target(topic: str, payload: Dict[str, Any]) -> str:
    if topic == "orders.created":
        return str(payload.get("of_id") or payload.get("order_id") or "unknown")
    if topic == "config.updated":
        return str(payload.get("config_key") or payload.get("config_type") or "unknown")
    if topic == "quality.defect_logged":
        return str(payload.get("boat_id") or payload.get("of_id") or "unknown")
    if topic == "plan.manual_override":
        return str(payload.get("commit_sha") or "unknown")
    return "unknown"


async def _noop_cpo_runner(
    tenant_id: UUID,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Runner CPO de fallback (stub). Devolve kpis vazios + sha fictício.

    Em produção, substituir por chamada real ao CPOv4Engine em modo propose-only.
    """
    return {
        "commit_sha": str(uuid4()),
        "kpis": {},
        "operations": [],
        "propose_only": True,
    }
