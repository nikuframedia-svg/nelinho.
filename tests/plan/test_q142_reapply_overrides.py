"""Q.142.C/D — o robô re-planeia automaticamente MAS os drag-drops manuais
aguentam-se ao replan.

Cobre:
1. `_reduce_overrides` (Q.142.C) — last-wins por operation_id; op sem id ignorada.
2. `reapply_manual_overrides` (Q.142.D) — orquestração: sucesso → commit;
   `ValueError` (ordem expedida) → skip; `SafetyNetViolation` (axioma deixou de
   bater com o novo WIP) → rejeitado + alerta. Best-effort (não rebenta).
3. Enforcement Spelke REAL através do re-apply (herdado de apply_manual_reorder):
   override válido cria commit; override que viola precedência é rejeitado.

Invariante: `reapply_manual_overrides` NUNCA persiste um plano que viole um
axioma — só aplica os que passam, descarta os que não passam.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from hypothesis import given, settings, strategies as st

from src.plan.cpo.commits import _reduce_overrides
from src.plan.services import manual_reorder as mr
from src.plan.services.manual_reorder import (
    SafetyNetViolation,
    reapply_manual_overrides,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
_BASE_TS = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 1. Q.142.C — _reduce_overrides (lógica pura, last-wins)
# ---------------------------------------------------------------------------

class _Row:
    """Linha mínima com `.delta` (como um ScheduleCommit)."""

    def __init__(self, delta: Optional[Dict[str, Any]]) -> None:
        self.delta = delta


def test_reduce_overrides_last_wins():
    """Dois drags do mesmo op (ordem asc) → fica o último."""
    rows = [
        _Row({"tipo": "manual_drag", "operation_id": "501171::5",
              "to_phase": "PINTURA", "to_ts": "2026-06-01T10:00:00", "new_operator_id": "w-1"}),
        _Row({"tipo": "manual_drag", "operation_id": "999::2",
              "to_phase": "MONTAGEM", "to_ts": "2026-06-01T12:00:00", "new_operator_id": None}),
        _Row({"tipo": "manual_drag", "operation_id": "501171::5",   # repete o 1º op
              "to_phase": "DESMOLDE", "to_ts": "2026-06-01T14:00:00", "new_operator_id": "w-2"}),
    ]
    out = _reduce_overrides(rows)
    by_op = {o["operation_id"]: o for o in out}
    assert len(out) == 2
    assert by_op["501171::5"]["to_phase"] == "DESMOLDE"      # last-wins
    assert by_op["501171::5"]["new_operator_id"] == "w-2"
    assert by_op["999::2"]["to_phase"] == "MONTAGEM"


def test_reduce_overrides_skips_op_without_id():
    """Delta sem operation_id é ignorado (não dá KeyError nem entrada vazia)."""
    rows = [
        _Row({"tipo": "manual_drag", "to_phase": "PINTURA"}),  # sem operation_id
        _Row(None),                                            # delta vazio
        _Row({"tipo": "manual_drag", "operation_id": "1::1", "to_phase": "X", "to_ts": "t"}),
    ]
    out = _reduce_overrides(rows)
    assert [o["operation_id"] for o in out] == ["1::1"]


@given(
    drags=st.lists(
        st.fixed_dictionaries({
            "operation_id": st.sampled_from(["a::1", "b::2", "c::3"]),
            "to_phase": st.sampled_from(["PINTURA", "MONTAGEM", "DESMOLDE"]),
        }),
        max_size=25,
    )
)
@settings(max_examples=50, deadline=2000)
def test_property_reduce_overrides_unique_and_last_wins(drags):
    """Invariante (Q.142.C): sobre N drags (ordem asc), o resultado tem
    operation_id ÚNICO e, por op, reflete o ÚLTIMO drag desse op (last-wins)."""
    rows = [_Row({"tipo": "manual_drag", "to_ts": "t", **d}) for d in drags]
    out = _reduce_overrides(rows)

    ids = [o["operation_id"] for o in out]
    assert len(ids) == len(set(ids))  # nunca dois overrides para o mesmo op

    last_phase: Dict[str, str] = {}
    for d in drags:
        last_phase[d["operation_id"]] = d["to_phase"]
    for o in out:
        assert o["to_phase"] == last_phase[o["operation_id"]]  # last-wins


# ---------------------------------------------------------------------------
# 2. Q.142.D — orquestração do reapply (apply_manual_reorder mockado)
# ---------------------------------------------------------------------------

class _FakeSession:
    """Conta commits/rollbacks; o resto é mockado."""

    def __init__(self) -> None:
        self.committed = 0
        self.rolledback = 0

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolledback += 1


@pytest.mark.asyncio
async def test_reapply_orchestration_mixed(monkeypatch):
    """3 overrides: 1 OK → commit; 1 ordem-expedida (ValueError) → skip;
    1 viola axioma (SafetyNetViolation) → rejeitado + alerta."""
    overrides = [
        {"operation_id": "OK::1", "to_phase": "PINTURA", "to_ts": _BASE_TS.isoformat(), "new_operator_id": None},
        {"operation_id": "GONE::2", "to_phase": "MONTAGEM", "to_ts": _BASE_TS.isoformat(), "new_operator_id": None},
        {"operation_id": "BAD::3", "to_phase": "DESMOLDE", "to_ts": _BASE_TS.isoformat(), "new_operator_id": None},
    ]

    async def fake_active(self):  # método de CommitsService
        return overrides

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.active_manual_overrides", fake_active,
    )

    async def fake_apply(*, operation_id, **kwargs):
        if operation_id == "GONE::2":
            raise ValueError(f"operacao_nao_encontrada: {operation_id!r}")
        if operation_id == "BAD::3":
            raise SafetyNetViolation("precedencia_monotonica", operation_id, "viola precedência")
        return {"commit_sha": "a" * 64}

    monkeypatch.setattr(mr, "apply_manual_reorder", fake_apply)

    alerts: List[str] = []

    async def fake_alert(session, tenant_id, operation_id, reason_pt):
        alerts.append(operation_id)

    monkeypatch.setattr(mr, "_emit_override_invalid_alert", fake_alert)

    session = _FakeSession()
    stats = await reapply_manual_overrides(session, TENANT)

    assert stats == {"reapplied": 1, "skipped": 1, "rejected": 1}
    assert session.committed == 1      # só o OK::1
    assert session.rolledback == 2     # GONE::2 + BAD::3
    assert alerts == ["BAD::3"]        # só o axioma violado gera alerta


@pytest.mark.asyncio
async def test_reapply_invalid_timestamp_skips(monkeypatch):
    """to_ts não-parseável → skip (não chama apply_manual_reorder, não rebenta)."""
    async def fake_active(self):
        return [{"operation_id": "X::1", "to_phase": "P", "to_ts": "lixo", "new_operator_id": None}]

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.active_manual_overrides", fake_active,
    )
    apply_spy = AsyncMock()
    monkeypatch.setattr(mr, "apply_manual_reorder", apply_spy)

    stats = await reapply_manual_overrides(_FakeSession(), TENANT)
    assert stats == {"reapplied": 0, "skipped": 1, "rejected": 0}
    apply_spy.assert_not_awaited()


# ---------------------------------------------------------------------------
# 3. Enforcement Spelke REAL através do re-apply (precedência)
# ---------------------------------------------------------------------------

class _FakeCommit:
    def __init__(self, operations: List[Dict[str, Any]]) -> None:
        self.id = uuid4()
        self.tenant_id = TENANT
        self.commit_sha256 = "a" * 64
        self.operations = operations
        self.kpis = {}
        self.alternatives = []
        self.rejected_alternatives = []
        self.user_preference_signal = {}
        self.cpo_meta = {}
        self.trust_index = 0.0
        self.status = "DRAFT"
        self.created_at = _BASE_TS


class _RealishSession:
    """Serve get_latest() (último commit adicionado ou o parent) + add/flush/commit."""

    def __init__(self, parent: _FakeCommit) -> None:
        self._parent = parent
        self.added: List[Any] = []
        self.committed = 0
        self.rolledback = 0

    async def execute(self, stmt):
        latest = self.added[-1] if self.added else self._parent

        class _R:
            def scalar_one_or_none(_self):
                return latest

            def scalars(_self):
                class _S:
                    def all(_s):
                        return [latest] if latest else []
                return _S()

            def first(_self):
                return None
        return _R()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for o in self.added:
            if getattr(o, "created_at", None) is None:
                object.__setattr__(o, "created_at", _BASE_TS)

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolledback += 1


@pytest.mark.asyncio
async def test_reapply_real_axiom_enforcement(monkeypatch):
    """Através do re-apply REAL: um move válido cria commit; um move que viola
    precedência é rejeitado (alerta) — nunca persiste plano que viole o axioma."""
    # op-A (LAMINAGEM 08-12h) → op-B (PINTURA 14-16h) depende de op-A.
    ops = [
        {"operation_id": "ord::A", "phase_id": "LAMINAGEM",
         "start_time": _BASE_TS.isoformat(),
         "end_time": (_BASE_TS + timedelta(hours=4)).isoformat(), "operator_id": "w-1"},
        {"operation_id": "ord::B", "phase_id": "PINTURA",
         "start_time": (_BASE_TS + timedelta(hours=6)).isoformat(),
         "end_time": (_BASE_TS + timedelta(hours=8)).isoformat(),
         "operator_id": "w-2", "depends_on": "ord::A"},
    ]
    # Override 1 (válido): mover op-B para mais tarde (depois de op-A).
    # Override 2 (inválido): mover op-B para ANTES do fim de op-A → precedência.
    overrides = [
        {"operation_id": "ord::B", "to_phase": "PINTURA",
         "to_ts": (_BASE_TS + timedelta(hours=20)).isoformat(), "new_operator_id": None},
    ]
    bad = [
        {"operation_id": "ord::B", "to_phase": "PINTURA",
         "to_ts": (_BASE_TS + timedelta(hours=1)).isoformat(), "new_operator_id": None},
    ]

    alerts: List[str] = []

    async def fake_alert(session, tenant_id, operation_id, reason_pt):
        alerts.append(operation_id)

    monkeypatch.setattr(mr, "_emit_override_invalid_alert", fake_alert)

    # --- caso válido ---
    async def active_ok(self):
        return overrides

    monkeypatch.setattr("src.plan.cpo.commits.CommitsService.active_manual_overrides", active_ok)
    with patch.object(mr, "publish_event", new=AsyncMock()), \
            patch.object(mr, "audit_change", new=AsyncMock()):
        s_ok = _RealishSession(_FakeCommit(ops))
        stats_ok = await reapply_manual_overrides(s_ok, TENANT)
    assert stats_ok["reapplied"] == 1 and stats_ok["rejected"] == 0
    assert len(s_ok.added) == 1          # commit real criado
    assert s_ok.committed == 1
    assert alerts == []                   # nada rejeitado

    # --- caso que viola precedência ---
    async def active_bad(self):
        return bad

    monkeypatch.setattr("src.plan.cpo.commits.CommitsService.active_manual_overrides", active_bad)
    with patch.object(mr, "publish_event", new=AsyncMock()), \
            patch.object(mr, "audit_change", new=AsyncMock()):
        s_bad = _RealishSession(_FakeCommit(ops))
        stats_bad = await reapply_manual_overrides(s_bad, TENANT)
    assert stats_bad["rejected"] == 1 and stats_bad["reapplied"] == 0
    assert len(s_bad.added) == 0          # NENHUM commit que viole o axioma
    assert alerts == ["ord::B"]           # humano alertado


# ---------------------------------------------------------------------------
# Q.149.C.1 — o OPERADOR sobrevive ao replan (guarda anti-regressão Q.148)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reapply_operator_survives_replan(monkeypatch):
    """Depois do reapply, a op leva o operador novo no campo CANÓNICO `workers`
    (o que o grid e o decoder CPO lêem). Sem isto a pessoa que o humano escolheu
    desaparece no replano seguinte — era o bug Q.148 (escrevia só operator_id).

    Este teste FALHA se alguém reverter o Q.148 e passa no código actual.
    """
    ops = [
        {"operation_id": "ord::B", "phase_id": "PINTURA",
         "start_time": _BASE_TS.isoformat(),
         "end_time": (_BASE_TS + timedelta(hours=2)).isoformat(),
         "workers": ["w-old"], "operator_id": "w-old"},
    ]
    overrides = [
        {"operation_id": "ord::B", "to_phase": "PINTURA",
         "to_ts": (_BASE_TS + timedelta(hours=10)).isoformat(), "new_operator_id": "w-9"},
    ]

    async def active(self):
        return overrides

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.active_manual_overrides", active,
    )

    with patch.object(mr, "publish_event", new=AsyncMock()), \
            patch.object(mr, "audit_change", new=AsyncMock()):
        session = _RealishSession(_FakeCommit(ops))
        stats = await reapply_manual_overrides(session, TENANT)

    assert stats["reapplied"] == 1 and stats["rejected"] == 0
    assert len(session.added) == 1
    commit = session.added[0]
    op = next(o for o in commit.operations if o["operation_id"] == "ord::B")
    assert op["workers"] == ["w-9"]       # campo canónico — a pessoa MUDOU
    assert op["operator_id"] == "w-9"     # consistente
    assert ops[0]["workers"] == ["w-old"]  # o parent não foi mutado


@pytest.mark.asyncio
async def test_reapply_exclusivity_chained(monkeypatch):
    """Dois overrides pondo o MESMO operador em janelas sobrepostas: o 1º aplica,
    o 2º é rejeitado pela exclusividade — provando que o reapply encadeia (lê o
    `workers` do commit que acabou de criar) e não deixa double-booking."""
    ops = [
        {"operation_id": "ord::A", "phase_id": "PINTURA",
         "start_time": _BASE_TS.isoformat(),
         "end_time": (_BASE_TS + timedelta(hours=4)).isoformat(),
         "workers": ["w-a"], "operator_id": "w-a"},
        {"operation_id": "ord::B", "phase_id": "MONTAGEM",
         "start_time": (_BASE_TS + timedelta(hours=12)).isoformat(),
         "end_time": (_BASE_TS + timedelta(hours=14)).isoformat(),
         "workers": ["w-b"], "operator_id": "w-b"},
    ]
    overrides = [
        # 1) ord::A passa a w-9 (mantém 08:00–12:00)
        {"operation_id": "ord::A", "to_phase": "PINTURA",
         "to_ts": _BASE_TS.isoformat(), "new_operator_id": "w-9"},
        # 2) ord::B passa a w-9 às 09:00 → dentro da janela de ord::A → conflito
        {"operation_id": "ord::B", "to_phase": "MONTAGEM",
         "to_ts": (_BASE_TS + timedelta(hours=1)).isoformat(), "new_operator_id": "w-9"},
    ]

    async def active(self):
        return overrides

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.active_manual_overrides", active,
    )
    alerts: List[str] = []

    async def fake_alert(session, tenant_id, operation_id, reason_pt):
        alerts.append(operation_id)

    monkeypatch.setattr(mr, "_emit_override_invalid_alert", fake_alert)

    with patch.object(mr, "publish_event", new=AsyncMock()), \
            patch.object(mr, "audit_change", new=AsyncMock()):
        session = _RealishSession(_FakeCommit(ops))
        stats = await reapply_manual_overrides(session, TENANT)

    assert stats["reapplied"] == 1       # ord::A
    assert stats["rejected"] == 1        # ord::B (double-booking)
    assert alerts == ["ord::B"]
    op_a = next(
        o for o in session.added[-1].operations if o["operation_id"] == "ord::A"
    )
    assert op_a["workers"] == ["w-9"]
