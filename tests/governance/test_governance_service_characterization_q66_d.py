"""Q.66.D.1b — Characterization tests para GovernanceService.

**Pattern Feathers (Working Effectively with Legacy Code):** antes de
decompor o god-file `src/governance/service.py` (1669L) em Fase 7
(Q.66.D.3), pinamos o behaviour observavel ACTUAL como snapshots. Estes
testes NAO assertam "o que devia acontecer" — assertam "o que acontece
hoje". Se a Fase 7 partir alguma destas assercoes sem decisao deliberada,
e regressao.

Cobertura (por metodo publico):
  * propose_decision: happy path + EventOutbox + AuditLog + sem publish
    sincrono.
  * propose_decision: kill switch active -> KillSwitchActiveError.
  * propose_decision_with_deferred_kafka: nao escreve EventOutbox,
    devolve evento ao caller.
  * approve_decision: happy path + AuditLog + status flip.
  * approve_decision: SoD violation, duplicate vote, decisao nao encontrada.
  * reject_decision (via approve_decision REJECT): status -> REJECTED + AuditLog.
  * arm_kill_switch / activate_kill_switch: cria DecisionRun + KillSwitchActive.
  * is_kill_switch_active: scope match (all + decision_type:foo).
  * get_audit_pack: hash chain verification + timeline.
  * _auto_approval_allowed: trust_index gate (None, below, above).
  * get_pending_approvals: exclui proposer + ja votados.
  * get_policy / list_policies: returns DEFAULT_POLICIES.
  * bulk_act: mistura sucesso + erro nao aborta batch.
  * modify_payload: invalida descendants + re-hash.

Nao-testavel em FakeSession (excluido com razao):
  * `execute_decision`: chama `default_executor.dispatch` que importa
    src.governance.action_executor (acopla a dispatchers reais).
    Coberto por test_service.py::TestExecuteDecision com fakes parciais.
  * `_lock_chain_for_tenant`: faz dialect-check em `self.db.bind.dialect`;
    FakeSession nao tem `.bind`, so o early-return skippa.
  * `get_timeline` com `_aware()`: depende de wall-clock; assertamos
    apenas shape, nao valores.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID, uuid4

import pytest

from src.governance.models import (
    Approval,
    ApprovalAction,
    AutonomyLevel,
    DecisionRun,
    DecisionStatus,
    KillSwitchActive,
)
from src.governance.service import (
    GovernanceService,
    KillSwitchActiveError,
    SoDViolationError,
)


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers — replicam o factory de test_service.py mas locais para o teste
# nao depender da assinatura interna do irmao file.
# ---------------------------------------------------------------------------

def _make_run(
    *,
    tenant_id: UUID,
    status: str = DecisionStatus.PENDING_APPROVAL.value,
    decision_type: str = "scenario_publish",
    proposed_by: str = "alice",
    approvals: Optional[List[Approval]] = None,
    risk_level: str = "medium",
    audit_hash: str = "abcd1234",
    prev_hash: Optional[str] = None,
    outcome_hash: Optional[str] = None,
    input_snapshot_hash: str = "deadbeef",
    action_data: Optional[dict] = None,
) -> DecisionRun:
    run = DecisionRun(
        id=uuid4(),
        tenant_id=tenant_id,
        decision_type=decision_type,
        title=f"Test {decision_type}",
        description="characterization",
        status=status,
        policy_version="1.0.0",
        autonomy_level=AutonomyLevel.L2.value,
        action_data=action_data or {"foo": "bar"},
        expected_impact=None,
        risk_level=risk_level,
        scenario_id=None,
        evidence_refs=[],
        input_snapshot_hash=input_snapshot_hash,
        prev_hash=prev_hash,
        audit_hash=audit_hash,
        proposed_by=proposed_by,
        proposed_at=datetime.now(timezone.utc),
        outcome_hash=outcome_hash,
    )
    run.approvals = list(approvals or [])
    return run


def _make_approval(
    *,
    tenant_id: UUID,
    decision_run_id: UUID,
    action: str = ApprovalAction.APPROVE.value,
    approved_by: str = "bob",
    reason: str = "ok",
) -> Approval:
    return Approval(
        id=uuid4(),
        tenant_id=tenant_id,
        decision_run_id=decision_run_id,
        action=action,
        approved_by=approved_by,
        reason=reason,
        approved_at=datetime.now(timezone.utc),
    )


def _names_of(added: List[Any]) -> set[str]:
    return {type(o).__name__ for o in added}


# ===========================================================================
# 1. PROPOSE — happy path side-effects (DecisionRun + AuditLog + EventOutbox)
# ===========================================================================


async def test_propose_decision_creates_decision_run_audit_log_and_outbox(
    fake_session, tenant_id,
):
    """SNAPSHOT: propose adiciona 3 rows ao session: DecisionRun, AuditLog
    (Q.66.B.3) e EventOutbox (Q.61.11). Esta combinacao e o contracto."""
    fake_session.queue_scalar(None)  # is_kill_switch_active -> None
    fake_session.queue_scalar(None)  # _get_last_decision_hash -> None
    svc = GovernanceService(fake_session, tenant_id)

    result = await svc.propose_decision(
        decision_type="scenario_publish",
        title="Publicar v2",
        action_data={"scenario_id": "abc"},
        proposed_by="alice",
        risk_level="medium",
    )

    added_types = _names_of(fake_session.added)
    assert "DecisionRun" in added_types
    assert "AuditLog" in added_types  # Q.66.B.3
    assert "EventOutbox" in added_types  # Q.61.11

    # AuditLog tem o snapshot certo.
    from src.core.models.audit import AuditLog
    audit_rows = [o for o in fake_session.added if isinstance(o, AuditLog)]
    assert len(audit_rows) == 1
    audit = audit_rows[0]
    assert audit.entity_type == "decision_run"
    assert audit.action == "INSERT"
    assert audit.new_values["decision_type"] == "scenario_publish"
    assert audit.new_values["status"] == DecisionStatus.PENDING_APPROVAL.value
    assert audit.new_values["risk_level"] == "medium"
    assert audit.reason == "propor decisão"

    assert result["proposed_by"] == "alice"
    assert result["status"] == DecisionStatus.PENDING_APPROVAL.value
    assert result["prev_hash"] is None
    assert len(result["audit_hash"]) == 64
    assert fake_session.flush_calls >= 1


async def test_propose_decision_input_hash_is_stable(
    fake_session, tenant_id, monkeypatch,
):
    """SNAPSHOT: input_snapshot_hash e SHA-256 hex de
    `{decision_type, action_data, expected_impact, scenario_id}` ordenado.
    """
    import hashlib
    import json

    fake_session.queue_scalar(None)
    fake_session.queue_scalar(None)
    svc = GovernanceService(fake_session, tenant_id)

    action_data = {"k": "v"}
    expected_impact = {"euro": 100.0}

    result = await svc.propose_decision(
        decision_type="data_repair",
        title="Repair",
        action_data=action_data,
        proposed_by="alice",
        expected_impact=expected_impact,
    )

    expected = {
        "decision_type": "data_repair",
        "action_data": action_data,
        "expected_impact": expected_impact,
        "scenario_id": None,
    }
    want = hashlib.sha256(
        json.dumps(expected, sort_keys=True, default=str).encode()
    ).hexdigest()

    assert result["input_snapshot_hash"] == want


async def test_propose_decision_raises_when_kill_switch_active(
    fake_session, tenant_id,
):
    """SNAPSHOT: is_kill_switch_active devolvendo row -> propose levanta
    KillSwitchActiveError com scope+decision_id+reason."""
    active_decision_id = uuid4()
    ks_row = KillSwitchActive(
        tenant_id=tenant_id,
        scope="all",
        decision_id=active_decision_id,
        activated_at=datetime.now(timezone.utc),
        activated_by="admin",
        reason="incident #42",
    )
    fake_session.queue_scalar(ks_row)  # is_kill_switch_active
    svc = GovernanceService(fake_session, tenant_id)

    with pytest.raises(KillSwitchActiveError) as exc:
        await svc.propose_decision(
            decision_type="scenario_publish",
            title="blocked",
            action_data={},
            proposed_by="alice",
        )
    assert exc.value.scope == "all"
    assert exc.value.decision_id == active_decision_id
    assert exc.value.reason == "incident #42"


async def test_propose_kill_switch_type_bypasses_self_check(
    fake_session, tenant_id,
):
    """SNAPSHOT: decision_type='kill_switch' SALTA a verificacao de
    kill switch active (admin pode empilhar)."""
    fake_session.queue_scalar(None)  # last_hash
    svc = GovernanceService(fake_session, tenant_id)

    result = await svc.propose_decision(
        decision_type="kill_switch",
        title="EMERGENCY",
        action_data={"scope": "all"},
        proposed_by="alice",
    )
    # kill_switch policy: requires_approval=False -> PROPOSED
    assert result["status"] == DecisionStatus.PROPOSED.value


async def test_propose_decision_does_not_publish_kafka_synchronously(
    fake_session, tenant_id, monkeypatch,
):
    """SNAPSHOT Q.61.11: propose NUNCA chama publish_event sincronamente.
    Usa outbox pattern."""
    publish_calls: list = []

    async def _spy(*args, **kwargs):
        publish_calls.append(args)
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", _spy, raising=True,
    )

    fake_session.queue_scalar(None)
    fake_session.queue_scalar(None)
    svc = GovernanceService(fake_session, tenant_id)

    await svc.propose_decision(
        decision_type="scenario_publish",
        title="t",
        action_data={},
        proposed_by="alice",
    )
    assert publish_calls == []


async def test_propose_with_deferred_kafka_returns_event_without_outbox(
    fake_session, tenant_id,
):
    """SNAPSHOT Q.12 Onda 2.3: deferred=True devolve (dict, event) sem
    escrever EventOutbox. Caller publica apos o seu outer commit."""
    from src.shared.outbox_models import EventOutbox

    fake_session.queue_scalar(None)
    fake_session.queue_scalar(None)
    svc = GovernanceService(fake_session, tenant_id)

    decision, event = await svc.propose_decision_with_deferred_kafka(
        decision_type="scenario_publish",
        title="deferred",
        action_data={"a": 1},
        proposed_by="alice",
    )

    assert decision["proposed_by"] == "alice"
    assert event is not None
    assert event.event_type == "DECISION_PROPOSED"
    assert event.payload["decision_id"] == decision["id"]

    outboxes = [o for o in fake_session.added if isinstance(o, EventOutbox)]
    assert outboxes == [], "deferred mode nao escreve EventOutbox"


# ===========================================================================
# 2. APPROVE — happy path + AuditLog + SoD + duplicate
# ===========================================================================


async def test_approve_decision_creates_approval_and_audit_log(
    fake_session, tenant_id, monkeypatch,
):
    """SNAPSHOT Q.66.B.3: approve adiciona Approval + AuditLog."""
    run = _make_run(tenant_id=tenant_id, proposed_by="alice")
    fake_session.queue_scalar(run)
    svc = GovernanceService(fake_session, tenant_id)

    # Silenciar publish_event para nao saltar para Kafka real.
    async def _noop(*a, **k):
        return True
    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", _noop, raising=True,
    )

    result = await svc.approve_decision(
        decision_id=str(run.id),
        action=ApprovalAction.APPROVE,
        approved_by="bob",
        reason="lgtm",
        approver_role="reviewer",
    )

    added_types = _names_of(fake_session.added)
    assert "Approval" in added_types
    assert "AuditLog" in added_types

    from src.core.models.audit import AuditLog
    audit_rows = [o for o in fake_session.added if isinstance(o, AuditLog)]
    assert len(audit_rows) == 1
    audit = audit_rows[0]
    assert audit.entity_type == "approval"
    assert audit.action == "INSERT"
    assert audit.new_values["decision_run_id"] == str(run.id)
    assert audit.new_values["action"] == "approve"
    assert audit.new_values["approver_role"] == "reviewer"
    assert audit.reason == "aprovação: approve"

    assert result["status"] == DecisionStatus.APPROVED.value
    assert result["approved_at"] is not None


async def test_approve_decision_sod_violation_raises(fake_session, tenant_id):
    """SNAPSHOT: scenario_publish tem requires_different_approver=True ->
    proposer != approver enforced."""
    run = _make_run(
        tenant_id=tenant_id,
        decision_type="scenario_publish",
        proposed_by="alice",
    )
    fake_session.queue_scalar(run)
    svc = GovernanceService(fake_session, tenant_id)

    with pytest.raises(SoDViolationError, match="Separation of Duties"):
        await svc.approve_decision(
            decision_id=str(run.id),
            action=ApprovalAction.APPROVE,
            approved_by="alice",
            reason="self-approve",
        )


async def test_approve_decision_duplicate_vote_raises(fake_session, tenant_id):
    """SNAPSHOT: mesmo approver nao pode votar duas vezes."""
    prior = _make_approval(
        tenant_id=tenant_id,
        decision_run_id=uuid4(),
        approved_by="bob",
    )
    run = _make_run(
        tenant_id=tenant_id,
        proposed_by="alice",
        approvals=[prior],
    )
    fake_session.queue_scalar(run)
    svc = GovernanceService(fake_session, tenant_id)

    with pytest.raises(ValueError, match="already voted"):
        await svc.approve_decision(
            decision_id=str(run.id),
            action=ApprovalAction.APPROVE,
            approved_by="bob",
            reason="dup",
        )


async def test_approve_decision_not_found_raises(fake_session, tenant_id):
    fake_session.queue_scalar(None)
    svc = GovernanceService(fake_session, tenant_id)
    with pytest.raises(ValueError, match="not found"):
        await svc.approve_decision(
            decision_id=str(uuid4()),
            action=ApprovalAction.APPROVE,
            approved_by="bob",
            reason="x",
        )


async def test_reject_decision_flips_status_to_rejected(
    fake_session, tenant_id, monkeypatch,
):
    """SNAPSHOT: ApprovalAction.REJECT -> status=REJECTED + AuditLog."""
    run = _make_run(tenant_id=tenant_id, proposed_by="alice")
    fake_session.queue_scalar(run)
    svc = GovernanceService(fake_session, tenant_id)

    async def _noop(*a, **k):
        return True
    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", _noop, raising=True,
    )

    result = await svc.approve_decision(
        decision_id=str(run.id),
        action=ApprovalAction.REJECT,
        approved_by="bob",
        reason="not now",
        rejection_category="COST",
    )

    assert result["status"] == DecisionStatus.REJECTED.value

    from src.core.models.audit import AuditLog
    audit_rows = [o for o in fake_session.added if isinstance(o, AuditLog)]
    assert len(audit_rows) == 1
    assert audit_rows[0].new_values["rejection_category"] == "COST"
    assert audit_rows[0].reason == "aprovação: reject"


# ===========================================================================
# 3. KILL SWITCH — activate + is_active scope semantics
# ===========================================================================


async def test_activate_kill_switch_creates_decision_and_active_row(
    fake_session, tenant_id, monkeypatch,
):
    """SNAPSHOT Q.12 Onda 2.2: activate adiciona DecisionRun (EXECUTED) +
    KillSwitchActive + AuditLog. activate_kill_switch nao requer approval."""
    fake_session.queue_scalar(None)  # _get_last_decision_hash
    fake_session.queue_scalar(None)  # _record_kill_switch_active SELECT existing

    svc = GovernanceService(fake_session, tenant_id)

    async def _lookup_from_added(decision_id):
        target = str(decision_id)
        for obj in fake_session.added:
            if isinstance(obj, DecisionRun) and str(obj.id) == target:
                return obj
        return None
    monkeypatch.setattr(svc, "_get_decision_run", _lookup_from_added)

    result = await svc.activate_kill_switch(
        scope="pricing",
        activated_by="alice",
        reason="incident #42",
    )

    runs = [o for o in fake_session.added if isinstance(o, DecisionRun)]
    assert len(runs) == 1
    assert runs[0].decision_type == "kill_switch"
    assert runs[0].status == DecisionStatus.EXECUTED.value
    assert runs[0].executed_by == "alice"

    ks_rows = [o for o in fake_session.added if isinstance(o, KillSwitchActive)]
    assert len(ks_rows) == 1
    assert ks_rows[0].scope == "pricing"
    assert ks_rows[0].activated_by == "alice"
    assert ks_rows[0].reason == "incident #42"

    assert result is not None
    assert result["status"] == DecisionStatus.EXECUTED.value


async def test_is_kill_switch_active_matches_all_scope(fake_session, tenant_id):
    """SNAPSHOT: scope='all' bate em qualquer decision_type."""
    row = KillSwitchActive(
        tenant_id=tenant_id, scope="all", decision_id=uuid4(),
        activated_at=datetime.now(timezone.utc),
        activated_by="admin", reason="x",
    )
    fake_session.queue_scalar(row)
    svc = GovernanceService(fake_session, tenant_id)

    got = await svc.is_kill_switch_active(decision_type="scenario_publish")
    assert got is row


async def test_is_kill_switch_active_returns_none_when_no_match(
    fake_session, tenant_id,
):
    """SNAPSHOT: scope nao bate -> None."""
    fake_session.queue_scalar(None)
    svc = GovernanceService(fake_session, tenant_id)
    got = await svc.is_kill_switch_active(decision_type="scenario_publish")
    assert got is None


async def test_is_kill_switch_active_filters_non_kill_switch_rows(
    fake_session, tenant_id,
):
    """SNAPSHOT defensivo: se FakeSession devolver objecto que nao e
    KillSwitchActive, devolve None (nao crasha)."""
    fake_session.queue_scalar("not a kill switch row")
    svc = GovernanceService(fake_session, tenant_id)
    got = await svc.is_kill_switch_active(decision_type="x")
    assert got is None


# ===========================================================================
# 4. AUDIT PACK — hash chain verification + timeline
# ===========================================================================


async def test_get_audit_pack_returns_timeline_and_verification(
    fake_session, tenant_id,
):
    """SNAPSHOT: get_audit_pack devolve {decision, verification, timeline,
    evidence}. timeline ordena proposed -> approvals -> executed -> rolled_back.
    """
    approval = _make_approval(
        tenant_id=tenant_id, decision_run_id=uuid4(),
        action=ApprovalAction.APPROVE.value, approved_by="bob",
    )
    run = _make_run(
        tenant_id=tenant_id,
        status=DecisionStatus.EXECUTED.value,
        proposed_by="alice",
        approvals=[approval],
    )
    run.executed_at = datetime.now(timezone.utc)
    run.executed_by = "carol"

    # Recompute audit_hash to be valid (genesis: prev_hash=None).
    run.audit_hash = DecisionRun.calculate_audit_hash(
        decision_id=run.id,
        policy_version=run.policy_version,
        input_hash=run.input_snapshot_hash,
        outcome_hash=run.outcome_hash,
        prev_hash=run.prev_hash,
    )

    fake_session.queue_scalar(run)  # _get_decision_run
    svc = GovernanceService(fake_session, tenant_id)

    pack = await svc.get_audit_pack(str(run.id))

    assert "decision" in pack
    assert "verification" in pack
    assert "timeline" in pack
    assert "evidence" in pack
    # Genesis chain — valid.
    assert pack["verification"]["hash_chain_valid"] is True
    assert pack["verification"]["hash_chain_depth"] == 1
    assert pack["verification"]["hash_chain_break_at"] is None
    assert pack["verification"]["audit_hash"] == run.audit_hash

    events = [e["event"] for e in pack["timeline"]]
    assert "proposed" in events
    assert "approval_approve" in events
    assert "executed" in events


async def test_get_audit_pack_detects_chain_break(fake_session, tenant_id):
    """SNAPSHOT Q.12 Onda 1.2: se audit_hash gravado != recomputado,
    hash_chain_break_at e o id da decisao."""
    run = _make_run(tenant_id=tenant_id)
    # Audit_hash deliberadamente inconsistente.
    run.audit_hash = "00" * 32
    fake_session.queue_scalar(run)
    svc = GovernanceService(fake_session, tenant_id)

    pack = await svc.get_audit_pack(str(run.id))
    assert pack["verification"]["hash_chain_valid"] is False
    assert pack["verification"]["hash_chain_break_at"] == str(run.id)


async def test_get_audit_pack_raises_when_not_found(fake_session, tenant_id):
    fake_session.queue_scalar(None)
    svc = GovernanceService(fake_session, tenant_id)
    with pytest.raises(ValueError, match="not found"):
        await svc.get_audit_pack(str(uuid4()))


# ===========================================================================
# 5. AUTO-APPROVAL (Q.66.A.3 — trust_index obrigatorio)
# ===========================================================================


async def test_auto_approval_disallowed_without_trust_index(
    fake_session, tenant_id,
):
    """SNAPSHOT Q.66.A.3: trust_index=None -> False (silence nao e consent)."""
    svc = GovernanceService(fake_session, tenant_id)
    ok = await svc._auto_approval_allowed(
        decision_type="data_repair",
        risk_level="low",
        trust_index=None,
    )
    assert ok is False


async def test_auto_approval_disallowed_when_trust_below_threshold(
    fake_session, tenant_id,
):
    """SNAPSHOT: trust_index < 0.75 -> False, sem ler TenantConfig."""
    svc = GovernanceService(fake_session, tenant_id)
    ok = await svc._auto_approval_allowed(
        decision_type="data_repair",
        risk_level="low",
        trust_index=0.70,
    )
    assert ok is False


async def test_auto_approval_allowed_when_enabled_and_ceiling_met(
    fake_session, tenant_id, monkeypatch,
):
    """SNAPSHOT: trust_index >= 0.75 + TenantConfig enabled + risk <= ceiling
    -> True."""

    class _FakeConfig:
        def __init__(self, *a, **k):
            pass

        async def get(self, category, key, default=None):
            if key.endswith(".enabled"):
                return True
            if key.endswith(".risk_ceiling"):
                return "HIGH"
            return default

    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        _FakeConfig, raising=True,
    )

    svc = GovernanceService(fake_session, tenant_id)
    ok = await svc._auto_approval_allowed(
        decision_type="data_repair",
        risk_level="medium",
        trust_index=0.85,
    )
    assert ok is True


async def test_auto_approval_disallowed_when_risk_above_ceiling(
    fake_session, tenant_id, monkeypatch,
):
    """SNAPSHOT: risk_level=critical > ceiling=low -> False mesmo com
    trust_index alto."""

    class _FakeConfig:
        def __init__(self, *a, **k):
            pass

        async def get(self, category, key, default=None):
            if key.endswith(".enabled"):
                return True
            if key.endswith(".risk_ceiling"):
                return "LOW"
            return default

    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        _FakeConfig, raising=True,
    )

    svc = GovernanceService(fake_session, tenant_id)
    ok = await svc._auto_approval_allowed(
        decision_type="data_repair",
        risk_level="critical",
        trust_index=0.90,
    )
    assert ok is False


# ===========================================================================
# 6. PENDING APPROVALS — exclui proposer + ja votados
# ===========================================================================


async def test_get_pending_approvals_excludes_already_voted(
    fake_session, tenant_id,
):
    """SNAPSHOT: get_pending_approvals filtra runs onde `user` ja votou."""
    voted_run = _make_run(
        tenant_id=tenant_id,
        proposed_by="alice",
        approvals=[_make_approval(
            tenant_id=tenant_id, decision_run_id=uuid4(),
            approved_by="bob",
        )],
    )
    fresh_run = _make_run(tenant_id=tenant_id, proposed_by="alice")

    fake_session.queue_scalars([voted_run, fresh_run])
    svc = GovernanceService(fake_session, tenant_id)

    pending = await svc.get_pending_approvals(user="bob")
    assert len(pending) == 1
    assert pending[0]["id"] == str(fresh_run.id)


# ===========================================================================
# 7. POLICY — leitura de DEFAULT_POLICIES
# ===========================================================================


async def test_get_policy_returns_default_for_known_type(fake_session, tenant_id):
    """SNAPSHOT: get_policy(scenario_publish) retorna policy default.

    Marcado async so para herdar o `pytestmark = pytest.mark.asyncio`
    sem colidir com pytest-asyncio (mesmo nao sendo IO-bound).
    """
    svc = GovernanceService(fake_session, tenant_id)
    policy = svc.get_policy("scenario_publish")
    assert policy is not None
    assert policy["requires_approval"] is True
    assert policy["requires_different_approver"] is True


async def test_get_policy_returns_none_for_unknown_type(fake_session, tenant_id):
    """SNAPSHOT: tipo desconhecido devolve None (caller usa default policy
    dentro de propose_decision)."""
    svc = GovernanceService(fake_session, tenant_id)
    assert svc.get_policy("totally_unknown_type") is None


async def test_list_policies_returns_all_defaults(fake_session, tenant_id):
    """SNAPSHOT: list_policies devolve as 6 policies default."""
    svc = GovernanceService(fake_session, tenant_id)
    policies = svc.list_policies()
    types = {p["decision_type"] for p in policies}
    assert "scenario_publish" in types
    assert "kill_switch" in types
    assert "data_repair" in types
    assert "standard_time_update" in types
    assert "capacity_adjustment" in types
    assert "model_promotion" in types


# ===========================================================================
# 8. BULK ACT — sucesso parcial nao aborta batch
# ===========================================================================


async def test_bulk_act_records_per_item_errors_without_aborting(
    fake_session, tenant_id, monkeypatch,
):
    """SNAPSHOT M.2: bulk_act aplica items independentes — 1 falha nao
    cancela os outros. Resultado per-item tem `status: ok|error`."""

    async def _noop(*a, **k):
        return True
    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", _noop, raising=True,
    )

    good = _make_run(tenant_id=tenant_id, proposed_by="alice")
    bad = _make_run(tenant_id=tenant_id, proposed_by="alice")  # SoD: bob != alice OK
    # Item 1: vai correr aprove -> queue retorna good run.
    # Item 2: action invalida -> ValueError antes do session lookup.
    fake_session.queue_scalar(good)

    svc = GovernanceService(fake_session, tenant_id)

    results = await svc.bulk_act(
        items=[
            {"decision_id": str(good.id), "action": "approve", "reason": "ok"},
            {"decision_id": str(bad.id), "action": "garbage_action"},
        ],
        approved_by="bob",
    )

    assert len(results) == 2
    assert results[0]["status"] == "ok"
    assert results[0]["new_status"] == DecisionStatus.APPROVED.value
    assert results[1]["status"] == "error"
    assert "error" in results[1]


# ===========================================================================
# 9. MODIFY PAYLOAD — re-hash + chain invalidation
# ===========================================================================


async def test_modify_payload_rehashes_and_records_history(
    fake_session, tenant_id,
):
    """SNAPSHOT M.4: modify_payload muta action_data, re-hasheia audit_hash
    e mete entrada em __modifications__."""
    run = _make_run(
        tenant_id=tenant_id,
        status=DecisionStatus.PROPOSED.value,
        action_data={"x": 1},
    )
    old_audit_hash = run.audit_hash
    fake_session.queue_scalar(run)  # _get_decision_run

    svc = GovernanceService(fake_session, tenant_id)
    result = await svc.modify_payload(
        decision_id=str(run.id),
        patch={"y": 2},
        modified_by="alice",
        reason="ajuste antes de aprovar — adiciona y",
    )

    assert result["action_data"]["y"] == 2
    assert result["action_data"]["x"] == 1  # merge, nao replace
    history = result["action_data"]["__modifications__"]
    assert len(history) == 1
    assert history[0]["modified_by"] == "alice"
    assert history[0]["reason"].startswith("ajuste antes de aprovar")
    assert "before_hash" in history[0]
    assert "after_hash" in history[0]

    assert result["audit_hash"] != old_audit_hash


async def test_modify_payload_rejects_short_reason(fake_session, tenant_id):
    """SNAPSHOT: reason com < 10 chars -> ValueError."""
    svc = GovernanceService(fake_session, tenant_id)
    with pytest.raises(ValueError, match="min 10 characters"):
        await svc.modify_payload(
            decision_id=str(uuid4()),
            patch={"x": 1},
            modified_by="alice",
            reason="curto",
        )


async def test_modify_payload_rejects_wrong_status(fake_session, tenant_id):
    """SNAPSHOT: so PROPOSED/PENDING_APPROVAL podem ser modificadas."""
    run = _make_run(
        tenant_id=tenant_id,
        status=DecisionStatus.EXECUTED.value,
    )
    fake_session.queue_scalar(run)
    svc = GovernanceService(fake_session, tenant_id)
    with pytest.raises(ValueError, match="not editable"):
        await svc.modify_payload(
            decision_id=str(run.id),
            patch={"x": 1},
            modified_by="alice",
            reason="razao com mais de dez caracteres",
        )


# ===========================================================================
# 10. AUDIT TIMELINE — cross-decision events
# ===========================================================================


async def test_get_audit_timeline_emits_event_per_lifecycle_step(
    fake_session, tenant_id,
):
    """SNAPSHOT M.6: get_audit_timeline emite evento por proposed/approval/
    executed/rolled_back. Ordena newest-first por timestamp ISO."""
    run = _make_run(tenant_id=tenant_id, proposed_by="alice")
    run.executed_at = datetime.now(timezone.utc)
    run.executed_by = "bob"
    run.approvals = [_make_approval(
        tenant_id=tenant_id, decision_run_id=run.id,
        approved_by="bob", action=ApprovalAction.APPROVE.value,
    )]

    fake_session.queue_scalars([run])
    svc = GovernanceService(fake_session, tenant_id)

    events = await svc.get_audit_timeline(limit=10)

    event_kinds = {e["event"] for e in events}
    assert "proposed" in event_kinds
    assert "approval_approve" in event_kinds
    assert "executed" in event_kinds
