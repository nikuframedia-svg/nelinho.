"""Q.173.O.1 — get_session/get_session_context comitam depois de flush.

Bug provado live 2026-06-11: POST /v1/config devolvia 201 e a linha NUNCA
chegava à BD. Causa: `TenantConfigService.set()` faz `flush()` (precisa do
id), o flush esvazia `session.dirty/new/deleted`, e a condição antiga do
`get_session` ("only commit if there are pending changes") ficava falsa →
a transação morria em rollback silencioso no close. O mesmo padrão matava
o PATCH /v1/plan/phase-gaps (cura) — coerente com a tabela
plan.phase_transition_gap estar a 0 desde sempre (auditoria 2026-06-11).

A regra nova: houve transação → commit. Estes testes prendem-na com um
fake de sessão que reproduz o estado pós-flush.
"""
from __future__ import annotations

import pytest

import src.shared.database as db


class _PostFlushSession:
    """Sessão no estado pós-flush: sets vazios, transação aberta."""

    def __init__(self, in_tx: bool = True) -> None:
        self.dirty: set = set()
        self.new: set = set()
        self.deleted: set = set()
        self._in_tx = in_tx
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def in_transaction(self) -> bool:
        return self._in_tx

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_get_session_comita_apos_flush(monkeypatch):
    fake = _PostFlushSession(in_tx=True)
    monkeypatch.setattr(db, "async_session_factory", lambda: fake)

    agen = db.get_session()
    session = await agen.__anext__()
    assert session is fake
    # endpoint fez flush() — dirty/new/deleted vazios, transação aberta
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()

    assert fake.commits == 1, (
        "pós-flush a sessão TEM de comitar — a condição dirty/new/deleted "
        "deixava a escrita morrer em rollback (bug 201-sem-linha, Q.173.O.1)"
    )
    assert fake.rollbacks == 0
    assert fake.closed


@pytest.mark.asyncio
async def test_get_session_excecao_faz_rollback(monkeypatch):
    fake = _PostFlushSession(in_tx=True)
    monkeypatch.setattr(db, "async_session_factory", lambda: fake)

    agen = db.get_session()
    await agen.__anext__()
    with pytest.raises(RuntimeError):
        await agen.athrow(RuntimeError("endpoint rebentou"))

    assert fake.commits == 0
    assert fake.rollbacks == 1
    assert fake.closed


@pytest.mark.asyncio
async def test_get_session_context_comita_apos_flush(monkeypatch):
    fake = _PostFlushSession(in_tx=True)
    monkeypatch.setattr(db, "async_session_factory", lambda: fake)

    async with db.get_session_context() as session:
        assert session is fake  # job fez flush(); sets vazios

    assert fake.commits == 1
    assert fake.rollbacks == 0
