"""Q.68.4.E — `src/plan/services/mold_service.py` a 25%. Smoke tests
em `test_mold_smoke.py` cobrem helpers + ORM; faltam testes ao CRUD +
ciclo de vida de manutenção + alertas que o APScheduler dispara em
produção. Sem eles, qualquer regressão à `recompute_health` /
`emit_maintenance_alerts` passa silenciosa.

Testes:

* `create_mold()` — INSERT + UNIQUE check + counter seed.
* `create_mold()` duplicado levanta `ValueError`.
* `plan_maintenance()` → status='PLANNED' + audit row.
* `complete_maintenance()` zera `cycles_since_last_maint`.
* `start_maintenance()` muda status para IN_PROGRESS.
* `increment_cycle()` cria counter se não existir e incrementa.
* `emit_maintenance_alerts()` desligado (threshold=0) → 0 alertas.
* `emit_maintenance_alerts()` com threshold positivo + counter excede
  → cria 1 alerta + audit-skip noqa para counter.
* `propose_preventive_schedule()` ignora molds sem health ou em verde.

FakeSession (queue) + monkeypatch ao `MoldHealthCalculator.compute` e
ao `publish_event`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.plan.models.mold import (
    Mold,
    MoldHealth,
    MoldMaintenanceEvent,
    MoldUsageCounter,
)
from src.plan.services import mold_service as mold_mod
from src.plan.services.mold_health_calculator import (
    HealthComponents,
    HealthResult,
)
from src.plan.services.mold_service import (
    CODE_MOLD_MAINT_DUE,
    MoldNotFoundError,
    MoldService,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ─── Helpers ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _silence_kafka(monkeypatch: pytest.MonkeyPatch):
    """`emit_maintenance_alerts` e `recompute_health` publicam best-effort
    via `from src.shared.kafka_client import publish_event` — interceptar."""

    async def _ok(*_a, **_kw):
        return True

    monkeypatch.setattr("src.shared.kafka_client.publish_event", _ok)


def _build_service(session) -> MoldService:
    return MoldService(session=session, tenant_id=TENANT)


def _mold(mold_code: str = "M-1", model_id: str = "K1") -> Mold:
    return Mold(
        id=uuid4(),
        tenant_id=TENANT,
        mold_code=mold_code,
        model_id=model_id,
        pocket_count=1,
        active=True,
        depreciated=False,
    )


class _ScriptedMoldSession:
    """Session que devolve steps determinísticos por execute().

    Cada step é `(kind, payload)` onde `kind ∈ {"scalars_all", "scalar_one"}`.
    """

    def __init__(self, steps):
        self._steps = list(steps)
        self.added = []
        self.deleted = []
        self.flush_calls = 0

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        self.flush_calls += 1

    async def execute(self, _stmt, *_a, **_kw):
        if not self._steps:
            raise AssertionError("Unexpected extra execute() call")
        kind, payload = self._steps.pop(0)
        if kind == "scalars_all":
            class _R:
                def scalars(self_inner):
                    class _S:
                        def all(self_innermost):
                            return list(payload)
                    return _S()
            return _R()
        # scalar_one
        class _R2:
            def scalar_one_or_none(self_inner):
                return payload
        return _R2()


# ─── create_mold ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_mold_inserts_mold_audit_and_counter(fake_session):
    """`create_mold` faz INSERT do molde, da audit row, e do counter seed."""
    # `_find_by_code` precisa devolver None → queue um scalar None.
    fake_session.queue_scalar(None)
    svc = _build_service(fake_session)
    mold = await svc.create_mold(
        mold_code="MOLDE-123",
        model_id="K1-VANQUISH",
        pocket_count=2,
        expected_life_cycles=5000,
    )
    assert mold.mold_code == "MOLDE-123"
    assert mold.tenant_id == TENANT
    assert mold.active is True
    types_added = [type(o).__name__ for o in fake_session.added]
    assert "Mold" in types_added
    assert "MoldUsageCounter" in types_added
    assert "AuditLog" in types_added


@pytest.mark.asyncio
async def test_create_mold_duplicate_raises(fake_session):
    """Re-create com o mesmo `mold_code` → ValueError (UNIQUE check)."""
    existing = _mold("DUP-1")
    fake_session.queue_scalar(existing)
    svc = _build_service(fake_session)
    with pytest.raises(ValueError, match="DUP-1"):
        await svc.create_mold(mold_code="DUP-1", model_id="K1")


# ─── get_mold / list_molds ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_mold_not_found_raises(fake_session):
    fake_session.queue_scalar(None)
    svc = _build_service(fake_session)
    with pytest.raises(MoldNotFoundError):
        await svc.get_mold(uuid4())


@pytest.mark.asyncio
async def test_list_molds_active_only_filters(fake_session):
    """Não conseguimos inspeccionar o WHERE no FakeSession, mas podemos
    confirmar que devolve a lista enqueued e que a chamada não rebenta."""
    expected = [_mold("M-A"), _mold("M-B")]
    fake_session.queue_scalars(expected)
    svc = _build_service(fake_session)
    rows = await svc.list_molds(active_only=True)
    assert rows == expected


# ─── plan / start / complete maintenance ──────────────────────────────────


@pytest.mark.asyncio
async def test_plan_maintenance_creates_planned_event(fake_session):
    svc = _build_service(fake_session)
    mold_id = uuid4()
    when = date.today() + timedelta(days=7)
    event = await svc.plan_maintenance(
        mold_id=mold_id,
        planned_date=when,
        maintenance_type="preventive",
        comments="rotina semanal",
    )
    assert event.status == "PLANNED"
    assert event.planned_date == when
    assert event.maintenance_type == "preventive"
    audit_count = sum(1 for o in fake_session.added if type(o).__name__ == "AuditLog")
    assert audit_count == 1


@pytest.mark.asyncio
async def test_start_maintenance_flips_status_to_in_progress(fake_session):
    event = MoldMaintenanceEvent(
        id=uuid4(),
        tenant_id=TENANT,
        mold_id=uuid4(),
        maintenance_type="preventive",
        planned_date=date.today(),
        status="PLANNED",
    )
    fake_session.queue_scalar(event)
    svc = _build_service(fake_session)
    out = await svc.start_maintenance(event.id)
    assert out.status == "IN_PROGRESS"
    assert out.started_at is not None


@pytest.mark.asyncio
async def test_complete_maintenance_resets_counter(fake_session):
    event = MoldMaintenanceEvent(
        id=uuid4(),
        tenant_id=TENANT,
        mold_id=uuid4(),
        maintenance_type="preventive",
        planned_date=date.today(),
        status="IN_PROGRESS",
    )
    counter = MoldUsageCounter(
        id=uuid4(),
        tenant_id=TENANT,
        mold_id=event.mold_id,
        shot_count_total=500,
        cycles_since_last_maint=120,
        last_updated_at=datetime.now(timezone.utc),
    )
    # 1ª execute → event ; 2ª execute → counter
    fake_session.queue_scalar(event)
    fake_session.queue_scalar(counter)
    svc = _build_service(fake_session)
    out = await svc.complete_maintenance(
        event_id=event.id,
        actual_duration_h=Decimal("2.5"),
        parts_cost_eur=Decimal("50"),
        labor_cost_eur=Decimal("30"),
    )
    assert out.status == "COMPLETED"
    assert out.completed_at is not None
    # Counter zerado.
    assert counter.cycles_since_last_maint == 0
    # `shot_count_total` NÃO se zera — é total de vida do molde.
    assert counter.shot_count_total == 500


# ─── increment_cycle ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_increment_cycle_creates_counter_when_absent(fake_session):
    fake_session.queue_scalar(None)
    svc = _build_service(fake_session)
    counter = await svc.increment_cycle(mold_id=uuid4(), amount=3)
    assert counter.shot_count_total == 3
    assert counter.cycles_since_last_maint == 3
    assert any(isinstance(o, MoldUsageCounter) for o in fake_session.added)


@pytest.mark.asyncio
async def test_increment_cycle_adds_to_existing_counter(fake_session):
    counter = MoldUsageCounter(
        id=uuid4(),
        tenant_id=TENANT,
        mold_id=uuid4(),
        shot_count_total=10,
        cycles_since_last_maint=4,
        last_updated_at=datetime.now(timezone.utc),
    )
    fake_session.queue_scalar(counter)
    svc = _build_service(fake_session)
    out = await svc.increment_cycle(mold_id=counter.mold_id, amount=5)
    assert out.shot_count_total == 15
    assert out.cycles_since_last_maint == 9


# ─── emit_maintenance_alerts ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_emit_maintenance_alerts_disabled_when_threshold_zero(
    fake_session, monkeypatch: pytest.MonkeyPatch,
):
    """Q.8: NELO não tem política numérica — threshold=0 desliga o sinal
    sem afectar o resto da pipeline."""
    # Patch TenantConfigService.get para devolver 0.
    from src.core.services import tenant_config_service as tcs_mod

    async def _get_zero(self, *_a, **_kw):
        return 0

    monkeypatch.setattr(tcs_mod.TenantConfigService, "get", _get_zero)
    svc = _build_service(fake_session)
    n = await svc.emit_maintenance_alerts()
    assert n == 0
    # Nada adicionado à session.
    assert all(type(o).__name__ != "CopilotAlert" for o in fake_session.added)


@pytest.mark.asyncio
async def test_emit_maintenance_alerts_creates_alert_above_threshold(
    fake_session, monkeypatch: pytest.MonkeyPatch,
):
    """threshold=100, counter=150 → 1 alerta CRITICAL (>1.5×threshold)."""
    from src.core.services import tenant_config_service as tcs_mod

    async def _get_threshold(self, *_a, **_kw):
        return 100

    monkeypatch.setattr(tcs_mod.TenantConfigService, "get", _get_threshold)

    mold = _mold("RED-1")
    counter = MoldUsageCounter(
        id=uuid4(),
        tenant_id=TENANT,
        mold_id=mold.id,
        shot_count_total=200,
        cycles_since_last_maint=160,  # > 1.5*100 → CRITICAL
        last_updated_at=datetime.now(timezone.utc),
    )
    # 1ª execute: SELECT Mold + Counter (LEFT JOIN, retorna `.all()` com
    # tuples). 2ª execute: `_alert_exists_for_mold` → None.
    from types import SimpleNamespace

    class _JoinSession:
        def __init__(self):
            self.added = []
            self._step = 0
            self.flush_calls = 0

        def add(self, obj):
            self.added.append(obj)

        async def flush(self):
            self.flush_calls += 1

        async def execute(self, _stmt, *_a, **_kw):
            self._step += 1
            if self._step == 1:
                return SimpleNamespace(all=lambda: [(mold, counter)])
            # _alert_exists_for_mold → no existing
            return SimpleNamespace(scalar_one_or_none=lambda: None)

    sess = _JoinSession()
    svc = _build_service(sess)
    n = await svc.emit_maintenance_alerts()
    assert n == 1
    alerts = [o for o in sess.added if type(o).__name__ == "CopilotAlert"]
    assert len(alerts) == 1
    assert alerts[0].code == CODE_MOLD_MAINT_DUE
    assert alerts[0].severity == "CRITICAL"


# ─── propose_preventive_schedule ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_propose_preventive_schedule_ignores_non_red_molds():
    """`list_molds` devolve 1 verde; `latest_health` deve retornar verde →
    nenhum evento criado.

    Usa session custom porque o `FakeSession` queue-based partilha as
    duas filas (scalar + scalars) entre todas as execute calls — aqui
    queremos uma reposta determinística por step.
    """
    green = _mold("GREEN-1")
    health_green = MoldHealth(
        id=uuid4(),
        tenant_id=TENANT,
        mold_id=green.id,
        score_0_100=90,
        risk_category="green",
        assessed_at=datetime.now(timezone.utc),
        components={},
    )

    sess = _ScriptedMoldSession(steps=[
        ("scalars_all", [green]),    # list_molds
        ("scalar_one", health_green),  # latest_health
    ])
    svc = _build_service(sess)
    created = await svc.propose_preventive_schedule()
    assert created == []


@pytest.mark.asyncio
async def test_propose_preventive_schedule_creates_event_for_red_mold():
    """Red mold sem evento futuro → 1 evento criado (planned 3d)."""
    red = _mold("RED-1")
    health_red = MoldHealth(
        id=uuid4(),
        tenant_id=TENANT,
        mold_id=red.id,
        score_0_100=20,
        risk_category="red",
        assessed_at=datetime.now(timezone.utc),
        components={},
    )
    sess = _ScriptedMoldSession(steps=[
        ("scalars_all", [red]),         # list_molds
        ("scalar_one", health_red),      # latest_health
        ("scalar_one", None),            # existing planned event check
    ])
    svc = _build_service(sess)
    created = await svc.propose_preventive_schedule()
    assert len(created) == 1
    assert created[0].status == "PLANNED"
    assert created[0].maintenance_type == "preventive"
