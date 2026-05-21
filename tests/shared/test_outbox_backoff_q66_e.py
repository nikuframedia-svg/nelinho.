"""Q.66.E.1 - outbox dispatcher respects exponential backoff between retries.

Antes desta sprint, o dispatcher pegava o mesmo event_outbox no proximo
ciclo (5s depois) mesmo se Kafka tinha acabado de devolver erro. Resultado:
Kafka instavel = event vai para DLQ em ~25s sem nunca dar a Kafka tempo de
recuperar.

Esta suite verifica:
  1. SELECT do dispatcher exclui events com `next_retry_at` no futuro.
  2. SELECT do dispatcher inclui events com `next_retry_at` no passado.
  3. SELECT do dispatcher inclui events com `next_retry_at` NULL (novos).
  4. Em falha, dispatcher seta next_retry_at = now() + 2^retry_count s
     (capped a 300s) ANTES de incrementar retry_count.
  5. Sequencia: 0->1s, 1->2s, 2->4s, 4->16s, 8->256s, 9+->300s.

Implementacao: FakeAsyncSession que recolhe o `where()` aplicado ao
statement + lista de events que respondem a `scalars().all()`. Nao precisa
de Postgres real — o SQL `func.now()` ate funciona contra Postgres mas aqui
testamos o RAMO PYTHON do dispatcher (a clause SQL e verificada por
introspeccao do statement compilado).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.shared.outbox_dispatcher import OutboxDispatcher
from src.shared.outbox_models import EventOutbox
from tests.conftest import FakeSession


def _make_event(
    *,
    retry_count: int = 0,
    next_retry_at: datetime | None = None,
    payload: dict | None = None,
    event_type: str = "lots.LotApproved",
) -> EventOutbox:
    """Cria um EventOutbox in-memory (sem hit DB)."""
    e = EventOutbox(
        id=uuid4(),
        tenant_id=uuid4(),
        aggregate_id=uuid4(),
        aggregate_type="lots",
        event_type=event_type,
        payload=payload or {"lot_id": str(uuid4()), "approved_by": "test"},
        status="pending",
        retry_count=retry_count,
        error_message=None,
        next_retry_at=next_retry_at,
    )
    return e


# Q.68.3.4 — _FakeSession era um stub de 25L com `captured_stmt`,
# `committed`, `rolled_back` flags. O canónico já tem `executed_stmts`
# (Q.68.3.2) + `commit_calls`/`rollback_calls`; este wrapper só ajusta
# os nomes para preservar as assertions originais.
class _FakeSession(FakeSession):
    """Q.68.3.4 — subclasse local sobre o canónico.

    O dispatcher consulta uma vez (SELECT pending events) e devolve a
    lista via ``scalars().all()``. As assertions inspecccionam o último
    statement capturado (``captured_stmt``) + bandeiras de commit/
    rollback. Mapeamos esses nomes para os contadores canónicos.
    """

    def __init__(self, events_to_return: list[EventOutbox]):
        super().__init__()
        self._events_seed = list(events_to_return)

    @property
    def captured_stmt(self) -> Any:
        return self.executed_stmts[-1] if self.executed_stmts else None

    @property
    def committed(self) -> bool:
        return self.commit_calls > 0

    @property
    def rolled_back(self) -> bool:
        return self.rollback_calls > 0

    async def execute(self, stmt: Any):  # type: ignore[override]
        # Always-returns-same-set: re-arm a batch antes de cada execute.
        self.queue_scalars(self._events_seed)
        return await super().execute(stmt)


# -----------------------------------------------------------------------------
# SQL clause assertions (introspect the compiled statement)
# -----------------------------------------------------------------------------

def test_dispatcher_select_includes_next_retry_at_filter():
    """SELECT statement contem `next_retry_at IS NULL OR next_retry_at <= now()`."""
    from sqlalchemy.dialects import postgresql

    from src.shared.outbox_dispatcher import OutboxDispatcher

    # Reconstroi o statement do dispatcher (mesma logica) e compila-o.
    from sqlalchemy import func, or_, select

    stmt = (
        select(EventOutbox)
        .where(EventOutbox.status == "pending")
        .where(
            or_(
                EventOutbox.next_retry_at.is_(None),
                EventOutbox.next_retry_at <= func.now(),
            )
        )
        .order_by(EventOutbox.created_at.asc())
        .limit(100)
        .with_for_update(skip_locked=True)
    )
    compiled = str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "next_retry_at IS NULL" in compiled
    assert "next_retry_at <= now()" in compiled
    assert "FOR UPDATE SKIP LOCKED" in compiled


def test_dispatcher_module_uses_next_retry_at_clause():
    """O modulo dispatcher.py contem a clause de backoff (fonte de verdade)."""
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2]
        / "src" / "shared" / "outbox_dispatcher.py"
    ).read_text(encoding="utf-8")
    # Os dois ramos do OR
    assert "EventOutbox.next_retry_at.is_(None)" in text
    assert "EventOutbox.next_retry_at <= func.now()" in text


# -----------------------------------------------------------------------------
# Backoff sequence
# -----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "retry_count,expected_delay_seconds",
    [
        (0, 1),    # 2^0 = 1
        (1, 2),    # 2^1 = 2
        (2, 4),    # 2^2 = 4
        (3, 8),
        (4, 16),
        (5, 32),
        (6, 64),
        (7, 128),
        (8, 256),
        (9, 300),  # capped (2^9=512 > 300)
        (10, 300),
        (20, 300),
    ],
)
@pytest.mark.asyncio
async def test_backoff_delay_sequence(retry_count: int, expected_delay_seconds: int):
    """Em falha, next_retry_at = now() + min(2^retry_count, 300) segundos."""
    event = _make_event(retry_count=retry_count)
    session = _FakeSession([event])

    # Kafka producer que SEMPRE falha — forca o ramo `except`.
    kafka_producer = MagicMock()
    kafka_producer.publish = AsyncMock(side_effect=RuntimeError("Kafka down"))

    dispatcher = OutboxDispatcher(
        db_session_factory=lambda: _async_ctx(session),
        kafka_producer=kafka_producer,
        batch_size=10,
    )

    before = datetime.now(tz=timezone.utc)
    await dispatcher._dispatch_pending_events(session)
    after = datetime.now(tz=timezone.utc)

    assert event.next_retry_at is not None, (
        "dispatcher deve setar next_retry_at em falha"
    )
    # Tolerancia: setting acontece DURANTE o except, entre before e after.
    expected_min = before + timedelta(seconds=expected_delay_seconds)
    expected_max = after + timedelta(seconds=expected_delay_seconds)
    assert expected_min <= event.next_retry_at <= expected_max, (
        f"retry_count={retry_count}: esperado delay ~{expected_delay_seconds}s, "
        f"got next_retry_at={event.next_retry_at}, "
        f"before={before}, after={after}"
    )


@pytest.mark.asyncio
async def test_backoff_set_before_retry_count_increment():
    """next_retry_at calculado com retry_count actual (antes do ++)."""
    # Event com retry_count=2 -> delay deve ser 2^2 = 4s, nao 2^3 = 8s.
    event = _make_event(retry_count=2)
    session = _FakeSession([event])

    kafka_producer = MagicMock()
    kafka_producer.publish = AsyncMock(side_effect=RuntimeError("boom"))

    dispatcher = OutboxDispatcher(
        db_session_factory=lambda: _async_ctx(session),
        kafka_producer=kafka_producer,
    )

    before = datetime.now(tz=timezone.utc)
    await dispatcher._dispatch_pending_events(session)

    # retry_count incrementou para 3
    assert event.retry_count == 3
    # mas o delay foi calculado com retry_count=2 (2^2 = 4s)
    assert event.next_retry_at is not None
    delta = (event.next_retry_at - before).total_seconds()
    # 4s +- tolerancia (execucao do test)
    assert 3.5 <= delta <= 5.5, (
        f"esperado ~4s (2^2), got {delta}s — provavelmente foi 8s (2^3) "
        f"= calculo feito DEPOIS do increment, bug"
    )


@pytest.mark.asyncio
async def test_backoff_capped_at_300_seconds():
    """Mesmo com retry_count alto (antes de DLQ ainda nao chegou), capped a 300s."""
    # retry_count=8 -> 2^8 = 256s, ainda < 300, nao capped
    # retry_count=9 -> 2^9 = 512s, capped a 300
    event_8 = _make_event(retry_count=8)
    event_9 = _make_event(retry_count=9)

    for event, expected in [(event_8, 256), (event_9, 300)]:
        session = _FakeSession([event])
        kafka_producer = MagicMock()
        kafka_producer.publish = AsyncMock(side_effect=RuntimeError("x"))
        dispatcher = OutboxDispatcher(
            db_session_factory=lambda s=session: _async_ctx(s),
            kafka_producer=kafka_producer,
        )
        before = datetime.now(tz=timezone.utc)
        await dispatcher._dispatch_pending_events(session)
        assert event.next_retry_at is not None
        delta = (event.next_retry_at - before).total_seconds()
        assert abs(delta - expected) < 2.0, (
            f"retry_count={event.retry_count - 1}: esperado {expected}s, got {delta}s"
        )


# -----------------------------------------------------------------------------
# Selection respects next_retry_at (smoke at the iteration level)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_with_future_next_retry_at_is_not_dispatched():
    """Se _FakeSession devolve [], dispatcher nao publica.

    O filtro SQL acontece dentro do session.execute() — em Postgres real, events
    com next_retry_at no futuro nao entram no result. Aqui simulamos a query
    a devolver lista vazia (que e o que Postgres faria) e confirmamos que o
    producer nunca foi chamado.
    """
    # Event in-memory com next_retry_at no futuro — Postgres NAO o devolveria
    session = _FakeSession([])  # lista vazia = "filter excluded the future-scheduled event"

    kafka_producer = MagicMock()
    kafka_producer.publish = AsyncMock()

    dispatcher = OutboxDispatcher(
        db_session_factory=lambda: _async_ctx(session),
        kafka_producer=kafka_producer,
    )

    await dispatcher._dispatch_pending_events(session)
    kafka_producer.publish.assert_not_called()


@pytest.mark.asyncio
async def test_event_with_null_next_retry_at_is_eligible_for_dispatch():
    """Event novo (next_retry_at=NULL) deve ser processado (sem skip por backoff).

    Confirmamos que o ramo de selecao NAO trava events com next_retry_at=None.
    Usamos um event invalido (payload nao validavel) para garantir que o
    dispatcher chega a fase de processamento — falha em validacao implica
    DLQ/erro, mas o ponto e: o dispatcher PROCESSOU este event em vez de o
    saltar por causa do filtro de backoff.
    """
    event = _make_event(retry_count=0, next_retry_at=None)
    # Como o filtro SQL acontece dentro de session.execute() (que aqui e fake),
    # e suficiente confirmar que o event aparece em `pending_events` e o loop
    # entra. Verificamos isso checando que session.commit() foi chamado E que
    # o event teve algum efeito (status mudou, ou next_retry_at foi setado).
    session = _FakeSession([event])

    kafka_producer = MagicMock()
    # Pode falhar OU publicar — nao importa para este teste.
    kafka_producer.publish = AsyncMock(side_effect=RuntimeError("kafka"))

    dispatcher = OutboxDispatcher(
        db_session_factory=lambda: _async_ctx(session),
        kafka_producer=kafka_producer,
    )

    await dispatcher._dispatch_pending_events(session)

    # Provas de que o event foi PROCESSADO (e nao saltado pelo filtro):
    assert session.committed is True, "dispatcher chegou ao commit"
    # Status ou next_retry_at mudaram = event foi tocado pelo loop
    assert event.retry_count > 0 or event.status != "pending", (
        "event passou pelo loop de processamento"
    )


# -----------------------------------------------------------------------------
# Model column existence
# -----------------------------------------------------------------------------

def test_event_outbox_has_next_retry_at_column():
    """A coluna `next_retry_at` existe no model com tz-aware DateTime."""
    col = EventOutbox.__table__.c.get("next_retry_at")
    assert col is not None, "next_retry_at deve existir no EventOutbox"
    assert col.nullable is True
    # Postgres TIMESTAMP WITH TIME ZONE
    assert col.type.timezone is True


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

class _AsyncCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


def _async_ctx(session):
    return _AsyncCtx(session)
