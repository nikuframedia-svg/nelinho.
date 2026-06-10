"""Q.115.C — Testes para POST /v1/plan/operations/reorder.

Cobre:
1. Happy path — reorder valido cria ScheduleCommit com delta correcto.
2. Property test Hypothesis (12 cenarios) — cada commit criado tem safety_net verde.
3. Axioma exclusividade_operador — 422 quando operador ocupado no mesmo slot.
4. Axioma precedencia_monotonica — 422 quando mover antes da dependencia.
5. Axioma skill_match — 422 quando operador sem skill da fase.
6. Axioma curing_gap — 422 quando gap de cura insuficiente.
7. Audit log — row criado com action_type="manual_reorder".
8. Kafka emit — mock + assert call.

Invariante propriedade: se 200, safety_net passou; se SafetyNetViolation, axiom_name preenchido.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from src.plan.services.manual_reorder import (
    SafetyNetViolation,
    _check_curing_gap,
    _check_operator_exclusivity,
    _check_precedence,
    _check_skill_match,
    apply_manual_reorder,
)

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
_BASE_TS = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fake session + ScheduleCommit stub
# ---------------------------------------------------------------------------

class _FakeCommit:
    """Simula ScheduleCommit suficiente para os testes."""

    def __init__(
        self,
        *,
        operations: List[Dict[str, Any]],
        kpis: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.id = uuid4()
        self.tenant_id = TENANT_ID
        self.commit_sha256 = "a" * 64
        self.operations = operations
        self.kpis = kpis or {}
        self.alternatives = []
        self.rejected_alternatives = []
        self.user_preference_signal = {}
        self.cpo_meta = {}
        self.trust_index = 0.0
        self.status = "DRAFT"
        self.created_at = _BASE_TS


def _make_op(
    op_id: str = "op-1",
    phase_id: str = "PINTURA",
    start_offset_h: int = 0,
    duration_h: int = 2,
    operator_id: Optional[str] = "op-A",
    depends_on: Optional[str] = None,
    curing_end_ts: Optional[str] = None,
) -> Dict[str, Any]:
    start = _BASE_TS + timedelta(hours=start_offset_h)
    end = start + timedelta(hours=duration_h)
    op: Dict[str, Any] = {
        "operation_id": op_id,
        "phase_id": phase_id,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "operator_id": operator_id,
    }
    if depends_on:
        op["depends_on"] = depends_on
    if curing_end_ts:
        op["curing_end_ts"] = curing_end_ts
    return op


class _FakeSession:
    """Sessao async falsa com suporte a add/flush/execute."""

    def __init__(self, parent_commit: Optional[_FakeCommit]) -> None:
        self._parent = parent_commit
        self.added: List[Any] = []
        self.audit_calls: List[Dict[str, Any]] = []

    async def execute(self, stmt):
        class _R:
            def __init__(self, row):
                self._row = row
            def scalar_one_or_none(self):
                return self._row
            def scalars(self):
                class _S:
                    def __init__(self, r):
                        self._r = r
                    def all(self):
                        return [self._r] if self._r else []
                return _S(self._row)
        return _R(self._parent)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        # Simula flush atribuindo created_at se nao existir
        for obj in self.added:
            if not hasattr(obj, "created_at") or obj.created_at is None:
                object.__setattr__(obj, "created_at", _BASE_TS)

    async def commit(self) -> None:
        # Q.171.A — o serviço persiste ANTES do Kafka emit.
        self.commit_calls = getattr(self, "commit_calls", 0) + 1


# ---------------------------------------------------------------------------
# Helpers de patch
# ---------------------------------------------------------------------------

def _patch_kafka():
    return patch(
        "src.plan.services.manual_reorder.publish_event",
        new_callable=AsyncMock,
        return_value=True,
    )


def _patch_audit():
    return patch(
        "src.plan.services.manual_reorder.audit_change",
        new_callable=AsyncMock,
    )


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_reorder():
    """Reorder valido cria commit com delta correcto."""
    ops = [
        _make_op("op-1", "PINTURA", start_offset_h=0, operator_id="worker-X"),
        _make_op("op-2", "MONTAGEM", start_offset_h=4, operator_id="worker-Y"),
    ]
    parent = _FakeCommit(operations=ops)
    session = _FakeSession(parent)

    new_ts = _BASE_TS + timedelta(hours=10)

    with _patch_kafka() as kafka_mock, _patch_audit() as audit_mock:
        result = await apply_manual_reorder(
            session=session,
            tenant_id=TENANT_ID,
            operation_id="op-1",
            new_phase="MONTAGEM",
            new_start_ts=new_ts,
            new_operator_id=None,
            author="operador-teste",
        )

    assert "commit_sha" in result
    assert len(result["commit_sha"]) == 64
    delta = result["delta_summary"]
    assert delta["moved_from"]["phase"] == "PINTURA"
    assert delta["moved_to"]["phase"] == "MONTAGEM"
    assert delta["moved_to"]["start_ts"] == new_ts.isoformat()
    assert "axiom_checks_passed" in delta
    assert len(session.added) == 1  # novo ScheduleCommit
    kafka_mock.assert_awaited_once()
    audit_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_reorder_recomputes_end_time_no_end_before_start():
    """Q.153.A1 — arrastar uma op para o futuro recalcula o end_time
    (preserva a duração real); nunca deixa end<start."""
    ops = [
        _make_op("op-1", "PINTURA", start_offset_h=0, duration_h=2,
                 operator_id="worker-X"),
        _make_op("op-2", "MONTAGEM", start_offset_h=4, operator_id="worker-Y"),
    ]
    parent = _FakeCommit(operations=ops)
    session = _FakeSession(parent)

    # Arrasta op-1 ~1 ano para a frente (o bug deixava end no passado).
    new_ts = _BASE_TS + timedelta(days=365)

    with _patch_kafka(), _patch_audit():
        await apply_manual_reorder(
            session=session,
            tenant_id=TENANT_ID,
            operation_id="op-1",
            new_phase="PINTURA",
            new_start_ts=new_ts,
            new_operator_id=None,
            author="operador-teste",
        )

    commit = session.added[0]
    moved = next(o for o in commit.operations if o["operation_id"] == "op-1")
    start = datetime.fromisoformat(moved["start_time"])
    end = datetime.fromisoformat(moved["end_time"])
    assert end > start, "end<=start após o drag — bug Q.153.A1"
    # Duração (2h) preservada.
    assert end == new_ts + timedelta(hours=2)


# ---------------------------------------------------------------------------
# 2. Property test Hypothesis — 12 cenarios minimos
# ---------------------------------------------------------------------------

@st.composite
def _valid_reorder_scenario(draw):
    """Gera cenario de reorder onde os axiomas nao sao violados."""
    n_ops = draw(st.integers(min_value=2, max_value=8))
    ops = []
    for i in range(n_ops):
        offset_h = draw(st.integers(min_value=i * 3, max_value=i * 3 + 2))
        ops.append(_make_op(
            op_id=f"op-{i}",
            phase_id=draw(st.sampled_from(["PINTURA", "MONTAGEM", "DESMOLDE"])),
            start_offset_h=offset_h,
            operator_id=f"worker-{i}",  # operadores distintos -> sem conflito
        ))
    # Reorder da op-0 para um slot livre (depois de todas as outras)
    new_start = _BASE_TS + timedelta(hours=n_ops * 3 + 5)
    return ops, "op-0", "MONTAGEM", new_start


@given(_valid_reorder_scenario())
@settings(
    max_examples=12,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=5000,
)
@pytest.mark.asyncio
async def test_property_valid_reorders_pass_safety_net(scenario):
    """Invariante: qualquer reorder que passe os axiomas Spelke cria commit valido."""
    ops, op_id, new_phase, new_ts = scenario

    parent = _FakeCommit(operations=ops)
    session = _FakeSession(parent)

    with _patch_kafka(), _patch_audit():
        result = await apply_manual_reorder(
            session=session,
            tenant_id=TENANT_ID,
            operation_id=op_id,
            new_phase=new_phase,
            new_start_ts=new_ts,
            new_operator_id=None,
        )

    # Post-condition: commit criado + delta correcto
    assert result["commit_sha"]
    assert result["delta_summary"]["moved_to"]["phase"] == new_phase
    assert "axiom_checks_passed" in result["delta_summary"]


# ---------------------------------------------------------------------------
# 3. Axioma exclusividade_operador
# ---------------------------------------------------------------------------

def test_axiom_exclusividade_operador():
    """Dois ops no mesmo slot com mesmo operador -> SafetyNetViolation."""
    t0 = _BASE_TS
    # op-1 ocupa operador X das 08h-10h
    # op-2 e movida para 09h com operador X -> conflito
    ops = [
        {
            "operation_id": "op-1",
            "phase_id": "PINTURA",
            "start_time": t0.isoformat(),
            "end_time": (t0 + timedelta(hours=2)).isoformat(),
            "operator_id": "worker-X",
        },
        {
            "operation_id": "op-2",
            "phase_id": "MONTAGEM",
            "start_time": (t0 + timedelta(hours=5)).isoformat(),
            "end_time": (t0 + timedelta(hours=7)).isoformat(),
            "operator_id": "worker-Y",
        },
    ]
    new_ts = t0 + timedelta(hours=1)  # dentro da janela de op-1

    with pytest.raises(SafetyNetViolation) as exc_info:
        _check_operator_exclusivity(ops, "op-2", "worker-X", new_ts)

    assert exc_info.value.axiom_name == "exclusividade_operador"
    assert "worker-X" in exc_info.value.reason_pt


# ---------------------------------------------------------------------------
# 4. Axioma precedencia_monotonica
# ---------------------------------------------------------------------------

def test_axiom_precedencia_monotonica():
    """Mover op para antes da sua dependencia -> SafetyNetViolation."""
    t0 = _BASE_TS
    ops = [
        {
            "operation_id": "op-A",
            "phase_id": "LAMINAGEM",
            "start_time": t0.isoformat(),
            "end_time": (t0 + timedelta(hours=4)).isoformat(),
            "operator_id": "worker-1",
        },
        {
            "operation_id": "op-B",
            "phase_id": "PINTURA",
            "start_time": (t0 + timedelta(hours=6)).isoformat(),
            "end_time": (t0 + timedelta(hours=8)).isoformat(),
            "operator_id": "worker-2",
            "depends_on": "op-A",
        },
    ]
    # Tentar mover op-B para antes do fim de op-A (t0+4h)
    bad_ts = t0 + timedelta(hours=2)

    with pytest.raises(SafetyNetViolation) as exc_info:
        _check_precedence(ops, "op-B", bad_ts)

    assert exc_info.value.axiom_name == "precedencia_monotonica"


def test_axiom_precedencia_ok():
    """Mover op para apos a dependencia nao levanta excep."""
    t0 = _BASE_TS
    ops = [
        {
            "operation_id": "op-A",
            "phase_id": "LAMINAGEM",
            "start_time": t0.isoformat(),
            "end_time": (t0 + timedelta(hours=4)).isoformat(),
        },
        {
            "operation_id": "op-B",
            "phase_id": "PINTURA",
            "start_time": (t0 + timedelta(hours=6)).isoformat(),
            "end_time": (t0 + timedelta(hours=8)).isoformat(),
            "depends_on": "op-A",
        },
    ]
    good_ts = t0 + timedelta(hours=5)
    _check_precedence(ops, "op-B", good_ts)  # sem excep


# ---------------------------------------------------------------------------
# 5. Axioma skill_match
# ---------------------------------------------------------------------------

def test_axiom_skill_match():
    """Operador sem skill da fase -> SafetyNetViolation."""
    ops = [_make_op("op-1", "LAMINAGEM")]
    state_skills = {"worker-Z": {"PINTURA", "MONTAGEM"}}  # sem LAMINAGEM

    with pytest.raises(SafetyNetViolation) as exc_info:
        _check_skill_match(ops, "op-1", "worker-Z", state_skills)

    assert exc_info.value.axiom_name == "skill_match"
    assert "LAMINAGEM" in exc_info.value.reason_pt


def test_axiom_skill_match_ok():
    """Operador COM skill da fase nao levanta excep."""
    ops = [_make_op("op-1", "PINTURA")]
    state_skills = {"worker-Z": {"PINTURA", "MONTAGEM"}}
    _check_skill_match(ops, "op-1", "worker-Z", state_skills)  # sem excep


# ---------------------------------------------------------------------------
# 6. Axioma curing_gap
# ---------------------------------------------------------------------------

def test_axiom_curing_gap():
    """Gap de cura < 16h -> SafetyNetViolation."""
    t0 = _BASE_TS
    curing_end = t0 + timedelta(hours=2)
    ops = [
        {
            "operation_id": "op-1",
            "phase_id": "PINTURA",
            "start_time": t0.isoformat(),
            "end_time": (t0 + timedelta(hours=1)).isoformat(),
            "curing_end_ts": curing_end.isoformat(),
        }
    ]
    # Tentar mover para 10h depois do curing_end (mas < 16h)
    bad_ts = curing_end + timedelta(hours=10)

    with pytest.raises(SafetyNetViolation) as exc_info:
        _check_curing_gap(ops, "op-1", bad_ts)

    assert exc_info.value.axiom_name == "curing_gap"
    assert "16" in exc_info.value.reason_pt


def test_axiom_curing_gap_ok():
    """Gap de cura >= 16h nao levanta excep."""
    t0 = _BASE_TS
    curing_end = t0 + timedelta(hours=2)
    ops = [
        {
            "operation_id": "op-1",
            "phase_id": "PINTURA",
            "start_time": t0.isoformat(),
            "end_time": (t0 + timedelta(hours=1)).isoformat(),
            "curing_end_ts": curing_end.isoformat(),
        }
    ]
    good_ts = curing_end + timedelta(hours=17)
    _check_curing_gap(ops, "op-1", good_ts)  # sem excep


# ---------------------------------------------------------------------------
# 7. Audit log
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_log_criado():
    """Confirma que audit_change e chamado com action='manual_reorder'."""
    ops = [_make_op("op-1", "PINTURA", operator_id="w-A")]
    parent = _FakeCommit(operations=ops)
    session = _FakeSession(parent)
    new_ts = _BASE_TS + timedelta(hours=8)

    with _patch_kafka(), _patch_audit() as audit_mock:
        await apply_manual_reorder(
            session=session,
            tenant_id=TENANT_ID,
            operation_id="op-1",
            new_phase="MONTAGEM",
            new_start_ts=new_ts,
            new_operator_id=None,
        )

    audit_mock.assert_awaited_once()
    call_kwargs = audit_mock.await_args.kwargs
    assert call_kwargs.get("action") == "manual_reorder"
    assert call_kwargs.get("tenant_id") == TENANT_ID


# ---------------------------------------------------------------------------
# 8. Kafka emit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kafka_emit():
    """Verifica que publish_event e chamado com payload correcto."""
    ops = [_make_op("op-1", "PINTURA", operator_id="w-B")]
    parent = _FakeCommit(operations=ops)
    session = _FakeSession(parent)
    new_ts = _BASE_TS + timedelta(hours=8)

    with _patch_kafka() as kafka_mock, _patch_audit():
        result = await apply_manual_reorder(
            session=session,
            tenant_id=TENANT_ID,
            operation_id="op-1",
            new_phase="DESMOLDE",
            new_start_ts=new_ts,
            new_operator_id=None,
        )

    kafka_mock.assert_awaited_once()
    # Verifica que o topic correcto e passado
    call_args = kafka_mock.await_args.args
    assert call_args[0] == "prodplan.plan.schedule_updated"
    event_payload = call_args[1].payload
    assert event_payload["operation_id"] == "op-1"
    assert event_payload["to_phase"] == "DESMOLDE"
    assert event_payload["commit_sha"] == result["commit_sha"]


# ---------------------------------------------------------------------------
# Extra: operacao nao encontrada -> ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_op_nao_encontrada():
    """Op inexistente levanta ValueError."""
    ops = [_make_op("op-1", "PINTURA")]
    parent = _FakeCommit(operations=ops)
    session = _FakeSession(parent)

    with _patch_kafka(), _patch_audit():
        with pytest.raises(ValueError, match="operacao_nao_encontrada"):
            await apply_manual_reorder(
                session=session,
                tenant_id=TENANT_ID,
                operation_id="op-inexistente",
                new_phase="MONTAGEM",
                new_start_ts=_BASE_TS + timedelta(hours=5),
                new_operator_id=None,
            )


# ---------------------------------------------------------------------------
# Extra: sem commit base -> ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sem_commit_base():
    """Sem ScheduleCommit base levanta ValueError."""
    session = _FakeSession(None)

    with _patch_kafka(), _patch_audit():
        with pytest.raises(ValueError, match="sem_commit_base"):
            await apply_manual_reorder(
                session=session,
                tenant_id=TENANT_ID,
                operation_id="op-1",
                new_phase="MONTAGEM",
                new_start_ts=_BASE_TS,
                new_operator_id=None,
            )


# ---------------------------------------------------------------------------
# Q.148.A1 — mudar o operador escreve o campo CANÓNICO `workers`
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a1_operator_change_writes_workers():
    """new_operator_id aplica-se em `workers` (não só operator_id) — senão a
    pessoa não muda (o decoder CPO usa `workers`), incl. no reapply do robô."""
    ops = [_make_op("op-1", "PINTURA", start_offset_h=0, operator_id="worker-X")]
    parent = _FakeCommit(operations=ops)
    session = _FakeSession(parent)

    with _patch_kafka(), _patch_audit():
        await apply_manual_reorder(
            session=session,
            tenant_id=TENANT_ID,
            operation_id="op-1",
            new_phase="PINTURA",
            new_start_ts=_BASE_TS,
            new_operator_id="worker-Z",
        )

    commit = session.added[0]
    op = next(o for o in commit.operations if o["operation_id"] == "op-1")
    assert op["workers"] == ["worker-Z"]  # campo canónico mudou
    assert op["operator_id"] == "worker-Z"  # consistente
    # o pai não foi mutado
    assert "workers" not in parent.operations[0] or parent.operations[0].get("workers") != ["worker-Z"]


# ---------------------------------------------------------------------------
# Q.148.A2 — exclusividade de operador lê `workers` (lista)
# ---------------------------------------------------------------------------

def test_a2_exclusivity_reads_workers_list():
    """O axioma apanha um operador já ocupado quando este vive em `workers`."""
    occupied = _make_op("op-2", "MONTAGEM", start_offset_h=0, duration_h=4)
    occupied.pop("operator_id", None)
    occupied["workers"] = ["worker-Z", "worker-Q"]  # op CPO: operador em `workers`
    target = _make_op("op-1", "PINTURA", start_offset_h=10)
    ops = [target, occupied]

    # worker-Z já está em op-2 entre 08:00–12:00; mover op-1 para 09:00 → conflito
    new_ts = _BASE_TS + timedelta(hours=1)
    with pytest.raises(SafetyNetViolation) as exc:
        _check_operator_exclusivity(ops, "op-1", "worker-Z", new_ts)
    assert exc.value.axiom_name == "exclusividade_operador"

    # operador livre (worker-LIVRE) → sem violação
    _check_operator_exclusivity(ops, "op-1", "worker-LIVRE", new_ts)


# ---------------------------------------------------------------------------
# Q.153.D1 — `reason` persiste no delta + user_preference_signal + audit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_d1_reason_persisted_keeps_manual_drag():
    """O motivo (do MoveBoatConfirm) fica no delta, no user_preference_signal e
    no audit, SEM mudar `tipo='manual_drag'` (o reapply do robô continua a
    apanhá-lo)."""
    ops = [_make_op("op-1", "PINTURA", operator_id="w-A")]
    parent = _FakeCommit(operations=ops)
    session = _FakeSession(parent)
    new_ts = _BASE_TS + timedelta(hours=8)
    motivo = "antecipar p/ libertar molde K1 7ML"

    with _patch_kafka(), _patch_audit() as audit_mock:
        await apply_manual_reorder(
            session=session,
            tenant_id=TENANT_ID,
            operation_id="op-1",
            new_phase="MONTAGEM",
            new_start_ts=new_ts,
            new_operator_id=None,
            reason=motivo,
        )

    commit = session.added[0]
    # delta mantém manual_drag (invariante do reapply Q.142) + ganha reason
    assert commit.delta["tipo"] == "manual_drag"
    assert commit.delta["reason"] == motivo
    # user_preference_signal uniforme com preview_apply (reason/weekday/hour)
    assert commit.user_preference_signal["reason"] == motivo
    assert "weekday" in commit.user_preference_signal
    assert "hour" in commit.user_preference_signal
    # audit_change recebe o reason no new_values
    call_kwargs = audit_mock.await_args.kwargs
    assert call_kwargs["new_values"]["reason"] == motivo


@pytest.mark.asyncio
async def test_d1_reason_optional_backcompat():
    """Sem reason (caminho legado da Timeline) → delta continua manual_drag,
    reason None, e não rebenta."""
    ops = [_make_op("op-1", "PINTURA", operator_id="w-A")]
    parent = _FakeCommit(operations=ops)
    session = _FakeSession(parent)

    with _patch_kafka(), _patch_audit():
        await apply_manual_reorder(
            session=session,
            tenant_id=TENANT_ID,
            operation_id="op-1",
            new_phase="MONTAGEM",
            new_start_ts=_BASE_TS + timedelta(hours=8),
            new_operator_id=None,
        )

    commit = session.added[0]
    assert commit.delta["tipo"] == "manual_drag"
    assert "reason" not in commit.delta  # não polui o delta quando ausente
    assert commit.user_preference_signal["reason"] is None
