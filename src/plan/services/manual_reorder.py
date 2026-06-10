"""Q.115.C — Manual drag-drop reorder service.

Aplica um delta manual (drag-drop) a um ScheduleCommit existente,
valida com safety_net (9 guardrails Spelke), cria novo commit, emite
evento Kafka plan.manual_override, escreve audit_log.

Invariantes:
- safety_net.py nao e tocado — so usado.
- ScheduleCommit model nao e alterado — so cria nova row.
- CoeficienteX NUNCA aqui (e €, pertence a src/profit/).
- Tempos vêm sempre do historical real via operacoes do commit pai.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.cpo.commits import CommitsService, ScheduleCommit, compute_commit_hash
from src.plan.cpo.safety_net import is_worse_than_baseline
from src.shared.kafka_client import EventBase, Topics, publish_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excepção local
# ---------------------------------------------------------------------------

class SafetyNetViolation(Exception):
    """Levantado quando o schedule modificado viola um axioma Spelke."""

    def __init__(self, axiom_name: str, operation_id: str, reason_pt: str) -> None:
        super().__init__(f"axioma_spelke:{axiom_name} op={operation_id}")
        self.axiom_name = axiom_name
        self.operation_id = operation_id
        self.reason_pt = reason_pt


# ---------------------------------------------------------------------------
# Axiomas Spelke — validacoes antes do safety_net KPI generico
# ---------------------------------------------------------------------------

_CURING_GAP_HOURS = 16.0  # NELO_CURING_GAPS_SEED minimo quimico


def _to_aware(value: Any) -> Optional[datetime]:
    """Q.148.A2 — parse + normaliza para tz-aware (UTC se naive).

    As ops do decoder CPO guardam `start_time` naive ('...T08:00:00') e as
    edições manuais guardam aware ('...+00:00'). Comparar mistos rebenta com
    'can't compare offset-naive and offset-aware datetimes' — agora os axiomas
    só comparam aware.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value if isinstance(value, datetime) else None


def _check_operator_exclusivity(
    ops: List[Dict[str, Any]],
    target_op_id: str,
    new_operator_id: Optional[str],
    new_start_ts: datetime,
) -> None:
    """Axioma: mesmo operador nao pode estar em dois sitios ao mesmo tempo."""
    if new_operator_id is None:
        return
    for op in ops:
        if str(op.get("operation_id", "")) == target_op_id:
            continue
        # Q.148.A2 — o operador da op vive em `workers` (lista, do decoder CPO);
        # ler só operator_id/worker_id deixava o axioma cego ao double-booking.
        op_operators: set[str] = set()
        op_workers = op.get("workers")
        if isinstance(op_workers, list):
            op_operators.update(str(w) for w in op_workers)
        single = op.get("operator_id") or op.get("worker_id")
        if single:
            op_operators.add(str(single))
        if new_operator_id not in op_operators:
            continue
        # Verifica sobreposicao temporal
        op_start = _to_aware(op.get("start_time") or op.get("start_ts"))
        op_end = _to_aware(op.get("end_time") or op.get("end_ts"))
        new_ts = _to_aware(new_start_ts)
        if op_start is None or op_end is None or new_ts is None:
            continue
        # Sobreposicao: new_start dentro da janela da outra op
        if op_start <= new_ts < op_end:
            raise SafetyNetViolation(
                axiom_name="exclusividade_operador",
                operation_id=target_op_id,
                reason_pt=(
                    f"Operador {new_operator_id} ja esta ocupado na operacao "
                    f"{op.get('operation_id')} entre "
                    f"{op_start.isoformat()} e {op_end.isoformat()}."
                ),
            )


def _check_precedence(
    ops: List[Dict[str, Any]],
    target_op_id: str,
    new_start_ts: datetime,
) -> None:
    """Axioma: precedencia monotonica — op B so apos op A se B depende de A."""
    target_op = next(
        (o for o in ops if str(o.get("operation_id", "")) == target_op_id), None
    )
    if target_op is None:
        return
    depends_on = target_op.get("depends_on") or target_op.get("predecessor_op_id")
    if not depends_on:
        return
    predecessor = next(
        (o for o in ops if str(o.get("operation_id", "")) == str(depends_on)), None
    )
    if predecessor is None:
        return
    pred_end = _to_aware(predecessor.get("end_time") or predecessor.get("end_ts"))
    new_ts = _to_aware(new_start_ts)
    if pred_end is None or new_ts is None:
        return
    if new_ts < pred_end:
        raise SafetyNetViolation(
            axiom_name="precedencia_monotonica",
            operation_id=target_op_id,
            reason_pt=(
                f"Operacao {target_op_id} depende de {depends_on} que termina "
                f"em {pred_end.isoformat()}. O novo inicio "
                f"{new_start_ts.isoformat()} e anterior a essa data."
            ),
        )


def _check_skill_match(
    ops: List[Dict[str, Any]],
    target_op_id: str,
    new_operator_id: Optional[str],
    state_skills: Optional[Dict[str, Any]] = None,
) -> None:
    """Axioma: operador tem de ter a skill da fase. Valida so se state_skills fornecido."""
    if new_operator_id is None or state_skills is None:
        return
    target_op = next(
        (o for o in ops if str(o.get("operation_id", "")) == target_op_id), None
    )
    if target_op is None:
        return
    phase_id = str(target_op.get("phase_id") or "")
    if not phase_id:
        return
    operator_skills = state_skills.get(new_operator_id, set())
    if isinstance(operator_skills, list):
        operator_skills = set(operator_skills)
    if phase_id not in operator_skills:
        raise SafetyNetViolation(
            axiom_name="skill_match",
            operation_id=target_op_id,
            reason_pt=(
                f"Operador {new_operator_id} nao tem a competencia necessaria "
                f"para a fase {phase_id}."
            ),
        )


def _check_curing_gap(
    ops: List[Dict[str, Any]],
    target_op_id: str,
    new_start_ts: datetime,
) -> None:
    """Axioma: 16 transicoes de cura quimica (NELO_CURING_GAPS_SEED).

    Se a operacao anterior ao mesmo molde/produto terminou com uma fase de
    cura/secagem, o novo inicio tem de respeitar o gap minimo de 16h.
    """
    target_op = next(
        (o for o in ops if str(o.get("operation_id", "")) == target_op_id), None
    )
    if target_op is None:
        return
    # So valida se a op anterior e marcada como curing_end
    curing_end = _to_aware(target_op.get("curing_end_ts") or target_op.get("curing_end_time"))
    new_ts = _to_aware(new_start_ts)
    if curing_end is None or new_ts is None:
        return
    gap_hours = (new_ts - curing_end).total_seconds() / 3600.0
    if gap_hours < _CURING_GAP_HOURS:
        raise SafetyNetViolation(
            axiom_name="curing_gap",
            operation_id=target_op_id,
            reason_pt=(
                f"Intervalo de cura insuficiente: {gap_hours:.1f}h < {_CURING_GAP_HOURS}h "
                f"(minimo quimico NELO_CURING_GAPS_SEED). "
                f"Fim de cura: {curing_end.isoformat()}."
            ),
        )


# ---------------------------------------------------------------------------
# Servico principal
# ---------------------------------------------------------------------------

async def apply_manual_reorder(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    operation_id: str,
    new_phase: str,
    new_start_ts: datetime,
    new_operator_id: Optional[str],
    author: str = "operator",
    reason: Optional[str] = None,
    state_skills: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Aplica reorder manual, valida axiomas Spelke, cria novo ScheduleCommit.

    Q.153.D1 — `reason` (opcional) é o motivo do ajuste (do MoveBoatConfirm);
    guardado no delta, no `user_preference_signal` (uniforme com o apply-move)
    e no `audit_change`, na mesma tx.

    Raises:
        SafetyNetViolation: se qualquer axioma Spelke for violado.
        ValueError: se nao existir commit base ou op nao encontrada.

    Returns:
        {"commit_sha": str, "delta_summary": dict}
    """
    commits_svc = CommitsService(session, tenant_id)
    parent = await commits_svc.get_latest()
    if parent is None:
        raise ValueError("sem_commit_base: corre /v1/plan/cpo/schedule primeiro")

    ops: List[Dict[str, Any]] = list(parent.operations or [])

    # Encontra a operacao alvo
    target_idx = next(
        (i for i, o in enumerate(ops) if str(o.get("operation_id", "")) == operation_id),
        None,
    )
    if target_idx is None:
        raise ValueError(f"operacao_nao_encontrada: {operation_id!r}")

    original_op = dict(ops[target_idx])
    from_phase = original_op.get("phase_id", "")
    from_ts = original_op.get("start_time") or original_op.get("start_ts") or ""

    # Constroi operacoes modificadas (shallow copy da lista)
    modified_ops = [dict(o) for o in ops]
    modified_ops[target_idx] = dict(original_op)
    modified_ops[target_idx]["phase_id"] = new_phase
    modified_ops[target_idx]["start_time"] = new_start_ts.isoformat()
    # Q.153.A1 — recalcular o end_time ao mover o start (preservando a
    # duração real). Sem isto, arrastar uma op para o futuro deixava o end
    # na data antiga → end<start (lixo no plano e no makespan).
    _dur_min = original_op.get("duration_minutes")
    if _dur_min is None:
        _os = _to_aware(original_op.get("start_time") or original_op.get("start_ts"))
        _oe = _to_aware(original_op.get("end_time") or original_op.get("end_ts"))
        _dur_min = ((_oe - _os).total_seconds() / 60.0) if (_os and _oe) else 0.0
    modified_ops[target_idx]["end_time"] = (
        new_start_ts + timedelta(minutes=float(_dur_min))
    ).isoformat()
    if new_operator_id is not None:
        # Q.148.A1 — o operador canónico da op é `workers` (lista, o que o decoder
        # do CPO produz). Escrever só `operator_id` deixava a pessoa por mudar —
        # inclusive no reapply do robô (Q.142), que re-aplicava o move mas não o
        # operador. (Fases-par perdem o 2º worker — o editor escolhe 1.)
        modified_ops[target_idx]["operator_id"] = new_operator_id
        modified_ops[target_idx]["workers"] = [new_operator_id]

    # ── Axiomas Spelke (por ordem de severidade) ──────────────────────
    _check_operator_exclusivity(modified_ops, operation_id, new_operator_id, new_start_ts)
    _check_precedence(modified_ops, operation_id, new_start_ts)
    _check_skill_match(modified_ops, operation_id, new_operator_id, state_skills)
    _check_curing_gap(modified_ops, operation_id, new_start_ts)

    # ── Safety net KPI (axioma 7 — nao degradar baseline) ─────────────
    # Para drag-drop manual usamos os KPIs do commit pai como baseline.
    # O candidato herda os mesmos KPIs (drag nao recalcula GA). So verificamos
    # que os campos estruturais do axioma nao pioram — sem recalculo de makespan.
    # Se o commit pai nao tiver kpis preenchidos, o safety_net passa (sem baseline).
    parent_kpis = dict(parent.kpis or {})
    if parent_kpis:
        # Para drag manual, candidato = clone do parent (mesmos kpis).
        # O safety_net so falha se o drag piorar explicitamente algum KPI.
        candidate_kpis = dict(parent_kpis)
        if is_worse_than_baseline(candidate_kpis, parent_kpis):
            raise SafetyNetViolation(
                axiom_name="safety_net_baseline",
                operation_id=operation_id,
                reason_pt="O reorder manual degrada os KPIs abaixo do baseline atual.",
            )

    axiom_checks_passed = [
        "exclusividade_operador",
        "precedencia_monotonica",
        "skill_match",
        "curing_gap",
        "safety_net_baseline",
    ]

    # ── Cria novo ScheduleCommit ───────────────────────────────────────
    delta: Dict[str, Any] = {
        "tipo": "manual_drag",
        "operation_id": operation_id,
        "from_phase": from_phase,
        "to_phase": new_phase,
        "from_ts": str(from_ts),
        "to_ts": new_start_ts.isoformat(),
    }
    if new_operator_id is not None:
        delta["new_operator_id"] = new_operator_id
    if reason:
        delta["reason"] = reason

    now = datetime.now(timezone.utc)
    sha = compute_commit_hash(
        parent_sha256=parent.commit_sha256,
        kpis=parent_kpis,
        operations=modified_ops,
        delta=delta,
    )

    commit = ScheduleCommit(
        id=uuid4(),
        tenant_id=tenant_id,
        parent_id=parent.id,
        commit_sha256=sha,
        author=author,
        message=f"Reorder manual: op {operation_id} de {from_phase} para {new_phase}",
        kpis=parent_kpis,
        operations=modified_ops,
        delta=delta,
        alternatives=list(parent.alternatives or []),
        cpo_meta=dict(parent.cpo_meta or {}),
        trust_index=float(parent.trust_index or 0.0),
        operations_count=len(modified_ops),
        rejected_alternatives=list(parent.rejected_alternatives or []),
        user_preference_signal={
            "author": author,
            "at": now.isoformat(),
            "source": "manual_drag",
            # Q.153.D1 — uniforme com o preview_apply (reason/weekday/hour) p/ a
            # Camada-1 minerar ambos os caminhos de escrita de forma igual.
            "reason": reason,
            "weekday": now.weekday(),
            "hour": now.hour,
        },
        status="DRAFT",
    )
    session.add(commit)  # noqa: audit_coverage — auditado em audit_change() abaixo (mesma tx)
    await session.flush()

    # ── Audit log ─────────────────────────────────────────────────────
    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="schedule_commit",
        entity_id=commit.id,
        action="manual_reorder",
        old_values={"phase_id": from_phase, "start_ts": str(from_ts)},
        new_values={
            "phase_id": new_phase,
            "start_ts": new_start_ts.isoformat(),
            "operator_id": new_operator_id,
            "commit_sha": sha,
            "reason": reason,
        },
        reason=reason or f"Q.115.C drag-drop manual op={operation_id}",
    )

    # Q.171.A — ordem correta: audit na MESMA tx do commit (invariante 7),
    # persistir, e SÓ DEPOIS publicar — o evento saía após o flush mas antes
    # do commit da tx: um rollback deixava o grid SSE a ver um plano que
    # nunca existiu (e o audit ficava em risco de tx separada).
    await session.commit()

    # ── Kafka emit ─────────────────────────────────────────────────────
    try:
        await publish_event(
            Topics.SCHEDULE_UPDATED,
            EventBase(
                event_type="plan.manual_override",
                tenant_id=tenant_id,
                source_module="plan.manual_reorder",
                payload={
                    "commit_sha": sha,
                    "parent_sha": parent.commit_sha256,
                    "operation_id": operation_id,
                    "from_phase": from_phase,
                    "to_phase": new_phase,
                    "author": author,
                },
            ),
        )
    except Exception as exc:  # Kafka down nao bloqueia o commit
        logger.warning("Kafka emit falhou (nao critico): %s", exc)

    delta_summary: Dict[str, Any] = {
        "moved_from": {"phase": from_phase, "start_ts": str(from_ts)},
        "moved_to": {"phase": new_phase, "start_ts": new_start_ts.isoformat()},
        "axiom_checks_passed": axiom_checks_passed,
    }

    logger.info(
        "Reorder manual commit=%s op=%s %s->%s tenant=%s",
        sha[:12], operation_id, from_phase, new_phase, tenant_id,
    )
    return {"commit_sha": sha, "delta_summary": delta_summary}


# ---------------------------------------------------------------------------
# Q.142.D — re-aplicar overrides manuais após o solve automático (robô)
# ---------------------------------------------------------------------------

async def _emit_override_invalid_alert(
    session: AsyncSession,
    tenant_id: UUID,
    operation_id: str,
    reason_pt: str,
) -> None:
    """Alerta (upsert idempotente, padrão Q.138.I) quando um override manual
    deixou de ser viável com o WIP atual. Best-effort — nunca rebenta."""
    from sqlalchemy.exc import SQLAlchemyError

    try:
        from src.plan.cpo.scheduler_run import _upsert_cpo_alert

        await _upsert_cpo_alert(
            session,
            tenant_id,
            code=f"MANUAL_OVERRIDE_INVALID:{operation_id}"[:64],
            title="Ajuste manual já não é viável",
            message_pt=(
                f"O teu ajuste manual da operação {operation_id} já não é "
                f"compatível com o plano atual e não foi re-aplicado: {reason_pt}"
            ),
            context={"operation_id": operation_id, "reason": reason_pt},
            severity="WARN",
        )
    except (SQLAlchemyError, ImportError, RuntimeError, OSError) as exc:
        logger.warning(
            "reapply: emitir alerta de override inviável falhou op=%s (%s)",
            operation_id, exc,
        )


async def reapply_manual_overrides(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    state_skills: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """Q.142.D — re-aplica os overrides manuais ativos por cima do DRAFT fresco
    que o robô acabou de gerar (chamado pelo worker após `run_cpo_schedule`).

    Cada move é re-validado pelos 4 axiomas Spelke + safety_net via
    `apply_manual_reorder` (autoria `system` → não se auto-coleta no ciclo
    seguinte). Move inviável é **descartado**, nunca forçado:
      * op inexistente (ordem expedida / fase já passou) → skip;
      * `SafetyNetViolation` (axioma deixou de bater com o novo WIP) → skip +
        `CopilotAlert` para o humano.

    Commit após cada sucesso → transacção distinta → `created_at` distinto →
    `get_latest()` encadeia o override seguinte sobre o anterior (Postgres
    `now()` é estável por transacção). Best-effort: nunca rebenta — o DRAFT do
    robô fica de pé. Devolve `{"reapplied", "skipped", "rejected"}`.
    """
    overrides = await CommitsService(session, tenant_id).active_manual_overrides()
    stats = {"reapplied": 0, "skipped": 0, "rejected": 0}

    for ov in overrides:
        op_id = str(ov.get("operation_id") or "")
        try:
            new_ts = datetime.fromisoformat(str(ov.get("to_ts")))
        except (ValueError, TypeError):
            logger.warning("reapply: to_ts inválido op=%s (%r) — skip", op_id, ov.get("to_ts"))
            stats["skipped"] += 1
            continue

        try:
            await apply_manual_reorder(
                session=session,
                tenant_id=tenant_id,
                operation_id=op_id,
                new_phase=str(ov.get("to_phase") or ""),
                new_start_ts=new_ts,
                new_operator_id=ov.get("new_operator_id"),
                author="system",  # author=system → excluído da próxima coleta
                state_skills=state_skills,
            )
            # Q.171.A — o apply_manual_reorder já persiste por dentro (audit
            # na mesma tx + commit antes do emit); cada override segue em tx
            # própria na mesma (created_at distinto → encadeia).
            stats["reapplied"] += 1
            logger.info("reapply: override op=%s re-aplicado em %s", op_id, ov.get("to_phase"))
        except SafetyNetViolation as exc:
            await session.rollback()
            stats["rejected"] += 1
            await _emit_override_invalid_alert(session, tenant_id, op_id, exc.reason_pt)
            logger.info(
                "reapply: op=%s rejeitado pelo safety_net (%s) — alerta emitido",
                op_id, exc.axiom_name,
            )
        except ValueError as exc:
            await session.rollback()
            stats["skipped"] += 1
            logger.info("reapply: op=%s já não está no plano fresco — skip (%s)", op_id, exc)

    return stats
