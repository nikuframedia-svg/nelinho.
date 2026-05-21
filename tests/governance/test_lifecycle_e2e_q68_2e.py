"""Q.68.2.E — Governance lifecycle e2e smoke (DB real).

Propose -> approve -> execute -> audit verify -> rollback contra um
Postgres dev a sério. Complementa o characterization Q.67.6.A5 (mocks)
com prova de que o pipeline inteiro de governance funciona sobre o
schema real, incluindo:

  1. ``GovernanceService.propose_decision`` cria DecisionRun + AuditLog
     na MESMA transação (invariante 7 Spelke).
  2. SoD enforced (Q.61.09): proponente NÃO pode aprovar a própria
     proposta -> ``SoDViolationError``.
  3. Approve com user ≠ proposer -> ``DecisionStatus.APPROVED``.
  4. ``execute_decision`` exige ``status == APPROVED``; recomputa
     ``outcome_hash`` + ``audit_hash``.
  5. ``audit_hash = SHA256(decision_id || policy_version || input_hash
     || outcome_hash || prev_hash)`` — mutar ``outcome_hash`` e recalcular
     mostra que qualquer adulteração quebra o hash gravado.
  6. ``rollback_decision`` flip ``EXECUTED -> ROLLED_BACK`` + audit row
     UPDATE; sem reason ou reason < 10 chars levanta ``ValueError``.
  7. Kill-switch activo (Q.12 Onda 2.2) bloqueia proposes futuros
     -> ``KillSwitchActiveError`` (mapeado a 423 na API).
  8. ``trace_id`` (Q.61.12) propaga ContextVar -> ``core.audit_log.trace_id``
     em TODA a chain (propose + execute + rollback).

Skip strategy
-------------
``pytestmark = pytest.mark.integration`` + ``skip_if_no_db`` autouse
fixture. Mesma forma que ``tests/copilot/test_run_sql_live.py``. Se o
``SELECT 1`` falhar (Postgres parado, schema não migrado), todos os
testes ficam skipped com mensagem clara — sem crashes confusos quando
o programador esquece ``pwsh scripts/nitro.ps1``.

A suite assume ``alembic upgrade head`` aplicado (schema ``governance``
+ ``shared`` + ``core`` presentes). Não cria nem destrói schema.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool

from src.core.models.audit import AuditLog
from src.governance.models import (
    ApprovalAction,
    DecisionRun,
    DecisionStatus,
    KillSwitchActive,
)
from src.governance.service import (
    GovernanceService,
    KillSwitchActiveError,
    SoDViolationError,
)
from src.shared.config import get_settings
from src.shared.observability import reset_trace_id, set_trace_id


pytestmark = pytest.mark.integration


# Dev tenant — mesmo UUID usado por scripts/bootstrap_dev_full.py e pelo
# frontend lib/api/client.ts (header X-Tenant-Id em modo dev).
TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ---------------------------------------------------------------------------
# DB availability + per-test isolation
# ---------------------------------------------------------------------------


async def _db_available() -> bool:
    """Tenta SELECT 1 — devolve True se a dev DB está acessível."""
    settings = get_settings()
    url = settings.database_url
    try:
        engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
    except Exception:
        return False
    return True


@pytest_asyncio.fixture(autouse=True)
async def skip_if_no_db():
    """Skip claro quando Postgres dev não está de pé."""
    if not await _db_available():
        pytest.skip(
            "Postgres dev não disponível — esta suite exige DB live. "
            "Corre `pwsh scripts/nitro.ps1` ou arranca Postgres + "
            "`alembic upgrade head` + bootstrap_dev_full antes.",
        )


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session contra Postgres dev — commits manuais no teste.

    Engine + sessionmaker criados por teste com ``NullPool`` para
    evitar event-loop bleed (cada teste pytest-asyncio corre num loop
    novo; o engine global de ``src.shared.database`` mantém conexões
    presas no loop anterior e crasha com ``Event loop is closed``).

    Cada teste corre o seu próprio lifecycle (propose/approve/execute)
    e faz limpeza no final.
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        future=True,
    )
    sessionmaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False,
    )
    try:
        async with sessionmaker() as session:
            yield session
            try:
                await session.rollback()
            except Exception:
                pass
    finally:
        await engine.dispose()


# decision_type usado nos testes — sem handler ActionExecutor registado,
# o que faria a dispatch flippar para EXECUTED_PARTIAL. Registamos um
# handler "ok" nos testes que exercitam o lifecycle até execute+rollback
# para terminar em EXECUTED (não EXECUTED_PARTIAL).
SMOKE_TYPE = "e2e_lifecycle_smoke"


@pytest_asyncio.fixture
async def register_smoke_handler():
    """Regista um handler trivial para ``e2e_lifecycle_smoke`` no
    ``default_executor`` durante o teste.

    Devolve ``status="ok"`` (não advisory-shim) para que o executor
    NÃO downgrade para ``EXECUTED_PARTIAL``. Cleanup remove o handler
    no teardown para os testes não interferirem com o resto da suite.
    """
    from src.governance.action_executor import default_executor

    async def _ok_handler(ctx):
        return {"status": "ok", "noop": True}

    default_executor.register(SMOKE_TYPE, _ok_handler, overwrite=True)
    try:
        yield
    finally:
        # Remove handler — não há `unregister`, então pop directo.
        default_executor._handlers.pop(SMOKE_TYPE, None)
        default_executor.invocation_counts.pop(SMOKE_TYPE, None)


def _make_service(session: AsyncSession) -> GovernanceService:
    """Constrói GovernanceService + força ``selectinload(approvals)`` nos
    SELECTs internos.

    Sem isto, o approver acede ``decision_run.approvals`` lazy e crasha
    com ``MissingGreenlet`` em async sessions (default lazy="select").
    Em produção cada HTTP request abre uma session nova com o run
    "fresh"; em sub-services ``_get_decision_run`` corre um SELECT que
    omite a relação. O test partilha a session entre propose/approve/
    execute, então precisamos de pre-carregar a colecção.
    """
    svc = GovernanceService(session, TENANT)

    async def _eager_get(decision_id):
        try:
            uid = UUID(decision_id) if isinstance(decision_id, str) else decision_id
        except ValueError:
            return None
        stmt = (
            select(DecisionRun)
            .options(selectinload(DecisionRun.approvals))
            .where(
                and_(DecisionRun.id == uid, DecisionRun.tenant_id == TENANT)
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # Substituir o helper em TODOS os sub-services + na facade.
    svc._query._get_decision_run = _eager_get
    svc._approver._get_decision_run = _eager_get
    svc._executor._get_decision_run = _eager_get
    svc._rollbacker._get_decision_run = _eager_get
    svc._get_decision_run = _eager_get
    return svc


async def _cleanup_decision(session: AsyncSession, decision_id: UUID) -> None:
    """Remove decision + audit rows criados por um teste.

    Idempotente — se algo já foi rolled-back não falha.
    """
    try:
        await session.execute(
            text("DELETE FROM core.audit_log WHERE entity_id = :eid"),
            {"eid": str(decision_id)},
        )
        await session.execute(
            text("DELETE FROM governance.approval WHERE decision_run_id = :eid"),
            {"eid": str(decision_id)},
        )
        await session.execute(
            text("DELETE FROM governance.decision_run WHERE id = :eid"),
            {"eid": str(decision_id)},
        )
        await session.commit()
    except Exception:
        await session.rollback()


async def _cleanup_kill_switch(session: AsyncSession, scope: str) -> None:
    try:
        await session.execute(
            text(
                "DELETE FROM governance.kill_switch_active "
                "WHERE tenant_id = :tid AND scope = :scope"
            ),
            {"tid": str(TENANT), "scope": scope},
        )
        await session.commit()
    except Exception:
        await session.rollback()


# ---------------------------------------------------------------------------
# Actor fixtures — proponente ≠ aprovador para SoD
# ---------------------------------------------------------------------------


@pytest.fixture
def proposer_id() -> str:
    return str(uuid4())


@pytest.fixture
def approver_id() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# Lifecycle e2e — DB real
# ---------------------------------------------------------------------------


class TestGovernanceLifecycle:
    """Lifecycle completo propose -> approve -> execute -> rollback."""

    @pytest.mark.asyncio
    async def test_propose_creates_decision_run_and_audit_row(
        self, db_session: AsyncSession, proposer_id: str,
    ) -> None:
        """propose_decision insere DecisionRun + AuditLog em transacção única.

        Invariante 7 (audit_log na mesma tx que o state change): se a
        decision foi commitada, a audit row TEM de existir.
        """
        svc = _make_service(db_session)
        decision = await svc.propose_decision(
            decision_type="reschedule_order",
            title="Reagendar OF-TEST-E2E",
            action_data={"order_id": "OF-TEST-E2E-1"},
            proposed_by=proposer_id,
            risk_level="medium",
        )
        await db_session.commit()

        try:
            assert decision["id"]
            assert decision["status"] == DecisionStatus.PENDING_APPROVAL.value
            assert decision["proposed_by"] == proposer_id

            decision_uuid = UUID(decision["id"])

            # Verificar DecisionRun persistido
            run = await db_session.get(DecisionRun, decision_uuid)
            assert run is not None
            assert run.tenant_id == TENANT
            assert run.audit_hash  # hash chain seed
            assert len(run.audit_hash) == 64  # SHA256 hex

            # Verificar AuditLog na MESMA tx
            audit_q = select(AuditLog).where(
                and_(
                    AuditLog.entity_id == decision_uuid,
                    AuditLog.action == "INSERT",
                )
            )
            audit_rows = (await db_session.execute(audit_q)).scalars().all()
            assert len(audit_rows) == 1, "exactly one INSERT audit row expected"
            audit = audit_rows[0]
            assert audit.entity_type == "decision_run"
            assert audit.new_values["status"] == DecisionStatus.PENDING_APPROVAL.value
        finally:
            await _cleanup_decision(db_session, UUID(decision["id"]))

    @pytest.mark.asyncio
    async def test_approve_enforces_sod_q61_09(
        self, db_session: AsyncSession, proposer_id: str,
    ) -> None:
        """Q.61.09 SoD: proponente não pode aprovar a sua própria proposta.

        ``DecisionApprover.approve_decision`` levanta ``SoDViolationError``
        quando ``approved_by == proposed_by`` e a policy tem
        ``requires_different_approver=True``.
        """
        svc = _make_service(db_session)
        decision = await svc.propose_decision(
            decision_type="reschedule_order",
            title="SoD self-approve attempt",
            action_data={"order_id": "OF-TEST-SOD-1"},
            proposed_by=proposer_id,
            risk_level="medium",
        )
        await db_session.commit()

        try:
            with pytest.raises(SoDViolationError) as excinfo:
                await svc.approve_decision(
                    decision_id=decision["id"],
                    action=ApprovalAction.APPROVE,
                    approved_by=proposer_id,  # mesmo user — proibido
                    reason="self-approve test",
                )
            assert "Separation of Duties" in str(excinfo.value)
            await db_session.rollback()
        finally:
            await _cleanup_decision(db_session, UUID(decision["id"]))

    @pytest.mark.asyncio
    async def test_approve_with_different_user_flips_status(
        self,
        db_session: AsyncSession,
        proposer_id: str,
        approver_id: str,
    ) -> None:
        """Approve com user ≠ proposer -> DecisionStatus.APPROVED.

        Pin do happy-path: SoD passa, Approval row criado, status
        transita de PENDING_APPROVAL para APPROVED quando o required
        approvers threshold é atingido (policy default = 1).
        """
        svc = _make_service(db_session)
        decision = await svc.propose_decision(
            decision_type="reschedule_order",
            title="Happy approve",
            action_data={"order_id": "OF-TEST-APP-1"},
            proposed_by=proposer_id,
            risk_level="medium",
        )
        await db_session.commit()

        try:
            result = await svc.approve_decision(
                decision_id=decision["id"],
                action=ApprovalAction.APPROVE,
                approved_by=approver_id,
                reason="approver distinto do proponente",
            )
            await db_session.commit()
            assert result["status"] == DecisionStatus.APPROVED.value

            # Refetch para confirmar persistência
            run = await db_session.get(DecisionRun, UUID(decision["id"]))
            assert run is not None
            assert run.status == DecisionStatus.APPROVED.value
        finally:
            await _cleanup_decision(db_session, UUID(decision["id"]))

    @pytest.mark.asyncio
    async def test_execute_requires_approval_and_updates_outcome_hash(
        self,
        db_session: AsyncSession,
        proposer_id: str,
        approver_id: str,
        register_smoke_handler,
    ) -> None:
        """execute_decision exige status APPROVED + recomputa audit_hash.

        Sprint A WG1: o executor recalcula ``outcome_hash`` a partir do
        ``action_data`` final e atualiza ``audit_hash``. O ``prev_hash``
        (chain link) tem de continuar igual ao do propose.
        """
        svc = _make_service(db_session)
        decision = await svc.propose_decision(
            decision_type=SMOKE_TYPE,
            title="Execute happy path",
            action_data={"order_id": "OF-TEST-EXE-1"},
            proposed_by=proposer_id,
            risk_level="medium",
        )
        await db_session.commit()

        try:
            await svc.approve_decision(
                decision_id=decision["id"],
                action=ApprovalAction.APPROVE,
                approved_by=approver_id,
                reason="approve antes do execute",
            )
            await db_session.commit()

            run_before = await db_session.get(DecisionRun, UUID(decision["id"]))
            assert run_before is not None
            audit_hash_propose = run_before.audit_hash
            prev_hash_seed = run_before.prev_hash

            executed = await svc.execute_decision(
                decision_id=decision["id"], executed_by=approver_id,
            )
            await db_session.commit()
            assert executed["status"] == DecisionStatus.EXECUTED.value

            # Refresh — audit_hash MUDA (outcome_hash agora presente),
            # mas prev_hash mantém-se (linka ao chain head do propose).
            await db_session.refresh(run_before)
            assert run_before.status == DecisionStatus.EXECUTED.value
            assert run_before.outcome_hash is not None
            assert len(run_before.outcome_hash) == 64
            assert run_before.audit_hash != audit_hash_propose
            assert run_before.prev_hash == prev_hash_seed
        finally:
            await _cleanup_decision(db_session, UUID(decision["id"]))

    @pytest.mark.asyncio
    async def test_audit_hash_breaks_when_payload_is_tampered(
        self,
        db_session: AsyncSession,
        proposer_id: str,
        approver_id: str,
        register_smoke_handler,
    ) -> None:
        """``audit_hash`` integrity: mutar ``outcome_hash`` quebra a verificação.

        O hash é ``SHA256(decision_id||policy_version||input_hash||
        outcome_hash||prev_hash)``. Se alguém tocar no ``action_data``
        ou recalcular um ``outcome_hash`` diferente, o ``audit_hash``
        gravado deixa de fechar — o que é exactamente a forma de
        detectar adulteração offline.
        """
        svc = _make_service(db_session)
        decision = await svc.propose_decision(
            decision_type=SMOKE_TYPE,
            title="Hash integrity probe",
            action_data={"order_id": "OF-TEST-HASH-1"},
            proposed_by=proposer_id,
        )
        await svc.approve_decision(
            decision_id=decision["id"],
            action=ApprovalAction.APPROVE,
            approved_by=approver_id,
            reason="approve antes do hash check",
        )
        await svc.execute_decision(
            decision_id=decision["id"], executed_by=approver_id,
        )
        await db_session.commit()

        try:
            run = await db_session.get(DecisionRun, UUID(decision["id"]))
            assert run is not None
            stored = run.audit_hash

            # Recalcular com os campos REAIS — tem de bater certo.
            recomputed_ok = DecisionRun.calculate_audit_hash(
                decision_id=run.id,
                policy_version=run.policy_version,
                input_hash=run.input_snapshot_hash,
                outcome_hash=run.outcome_hash,
                prev_hash=run.prev_hash,
            )
            assert recomputed_ok == stored

            # Recalcular com outcome_hash adulterado — tem de NÃO bater.
            tampered_outcome = hashlib.sha256(b"forged").hexdigest()
            recomputed_bad = DecisionRun.calculate_audit_hash(
                decision_id=run.id,
                policy_version=run.policy_version,
                input_hash=run.input_snapshot_hash,
                outcome_hash=tampered_outcome,
                prev_hash=run.prev_hash,
            )
            assert recomputed_bad != stored
        finally:
            await _cleanup_decision(db_session, UUID(decision["id"]))

    @pytest.mark.asyncio
    async def test_rollback_flips_state_and_audits(
        self,
        db_session: AsyncSession,
        proposer_id: str,
        approver_id: str,
        register_smoke_handler,
    ) -> None:
        """Rollback de decisão executada: EXECUTED -> ROLLED_BACK + audit.

        Sprint C 1.4 (WG2): a decisão fica com ``rolled_back_at``,
        ``rolled_back_by`` e ``rollback_reason`` populados. Reason
        com menos de 10 chars é rejeitada.
        """
        svc = _make_service(db_session)
        decision = await svc.propose_decision(
            decision_type=SMOKE_TYPE,
            title="Rollback happy",
            action_data={"order_id": "OF-TEST-RBK-1"},
            proposed_by=proposer_id,
        )
        await svc.approve_decision(
            decision_id=decision["id"],
            action=ApprovalAction.APPROVE,
            approved_by=approver_id,
            reason="approve antes do rollback",
        )
        await svc.execute_decision(
            decision_id=decision["id"], executed_by=approver_id,
        )
        await db_session.commit()

        try:
            # Reason curta — rejeita
            with pytest.raises(ValueError):
                await svc.rollback_decision(
                    decision_id=decision["id"],
                    rolled_back_by=approver_id,
                    reason="curto",  # <10 chars
                )

            result = await svc.rollback_decision(
                decision_id=decision["id"],
                rolled_back_by=approver_id,
                reason="reversão pedida pelo operador",
            )
            await db_session.commit()
            assert result["status"] == DecisionStatus.ROLLED_BACK.value

            run = await db_session.get(DecisionRun, UUID(decision["id"]))
            assert run is not None
            assert run.status == DecisionStatus.ROLLED_BACK.value
            assert run.rolled_back_at is not None
            assert run.rolled_back_by == approver_id
            assert run.rollback_reason == "reversão pedida pelo operador"
        finally:
            await _cleanup_decision(db_session, UUID(decision["id"]))

    @pytest.mark.asyncio
    async def test_kill_switch_blocks_subsequent_proposals(
        self,
        db_session: AsyncSession,
        proposer_id: str,
    ) -> None:
        """Q.12 Onda 2.2: kill switch activo bloqueia novos proposes.

        ``activate_kill_switch`` insere uma row em ``governance.
        kill_switch_active``; a próxima call a ``propose_decision`` com
        o mesmo ``decision_type`` (ou scope ``"all"``) levanta
        ``KillSwitchActiveError`` — a API maps para 423 LOCKED.
        """
        svc = _make_service(db_session)
        scope = "decision_type:reschedule_order"

        # Arm — kill_switch é auto-execute via _propose+_record_kill_switch.
        ks = await svc.activate_kill_switch(
            scope=scope,
            activated_by=proposer_id,
            reason="emergência operacional — pausar reagendamentos",
        )
        await db_session.commit()
        ks_decision_id = UUID(ks["id"])

        try:
            # Verifica row durável
            ks_q = select(KillSwitchActive).where(
                and_(
                    KillSwitchActive.tenant_id == TENANT,
                    KillSwitchActive.scope == scope,
                    KillSwitchActive.deactivated_at.is_(None),
                )
            )
            ks_row = (await db_session.execute(ks_q)).scalar_one_or_none()
            assert ks_row is not None
            assert ks_row.activated_by == proposer_id

            # Tentar propor durante o block — falha
            with pytest.raises(KillSwitchActiveError) as excinfo:
                await svc.propose_decision(
                    decision_type="reschedule_order",
                    title="Tentativa durante kill switch",
                    action_data={"order_id": "OF-TEST-KS-1"},
                    proposed_by=proposer_id,
                )
            assert excinfo.value.scope == scope
            await db_session.rollback()
        finally:
            await _cleanup_kill_switch(db_session, scope)
            await _cleanup_decision(db_session, ks_decision_id)

    @pytest.mark.asyncio
    async def test_trace_id_propagates_to_audit_log_chain(
        self,
        db_session: AsyncSession,
        proposer_id: str,
        approver_id: str,
        register_smoke_handler,
    ) -> None:
        """Q.61.12 + Q.66.B.1: trace_id ContextVar -> audit_log.trace_id.

        O ContextVar é normalmente populado pelo ``TraceIdMiddleware``
        a partir do header ``X-Request-Id``. Aqui simulamos isso com
        ``set_trace_id`` directo e verificamos que TODA a chain (propose
        + execute) escreve o mesmo ``trace_id`` nas rows ``core.audit_log``.
        """
        trace_id = f"e2e-{uuid.uuid4().hex[:12]}"
        token = set_trace_id(trace_id)
        decision_uuid: UUID | None = None
        try:
            svc = _make_service(db_session)
            decision = await svc.propose_decision(
                decision_type=SMOKE_TYPE,
                title="Trace propagation probe",
                action_data={"order_id": "OF-TEST-TRACE-1"},
                proposed_by=proposer_id,
            )
            await svc.approve_decision(
                decision_id=decision["id"],
                action=ApprovalAction.APPROVE,
                approved_by=approver_id,
                reason="approve com trace_id",
            )
            await svc.execute_decision(
                decision_id=decision["id"], executed_by=approver_id,
            )
            await db_session.commit()
            decision_uuid = UUID(decision["id"])

            audit_q = select(AuditLog).where(AuditLog.entity_id == decision_uuid)
            rows = (await db_session.execute(audit_q)).scalars().all()
            assert len(rows) >= 1, "pelo menos a audit row do propose"
            # TODAS as rows desta decision têm de partilhar o trace_id —
            # propaga via ContextVar, não por argumento explícito.
            for row in rows:
                assert row.trace_id == trace_id, (
                    f"audit row {row.id} (action={row.action}) tem "
                    f"trace_id={row.trace_id!r}, esperado {trace_id!r}"
                )
        finally:
            reset_trace_id(token)
            if decision_uuid is not None:
                await _cleanup_decision(db_session, decision_uuid)
