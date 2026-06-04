"""Q.157.C — o job nocturno de reindex do RAG do copilot.

Dois bugs corrigidos no `_copilot_schema_reindex_job`:
  * usava `force=False` → `ingest_schema_docs` ACUMULA (duplica o índice a
    cada noite) em vez de fazer refresh canónico;
  * abria `async_session_factory()` (que NÃO faz commit no exit) e nunca
    commitava → os chunks eram flushed mas perdidos no fecho da sessão →
    `copilot_rag_chunk` ficava a 0 mesmo quando o job corria.

Estes testes travam ambos: o job tem de chamar `ingest_schema_docs(force=True)`
e fazer `session.commit()`.
"""

from __future__ import annotations

import pytest

from src.scheduling.jobs import copilot as copilot_job


class _FakeSession:
    def __init__(self, recorder: dict) -> None:
        self._rec = recorder

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    async def commit(self) -> None:
        self._rec["commits"] = self._rec.get("commits", 0) + 1


@pytest.mark.asyncio
async def test_reindex_job_uses_force_true_and_commits(monkeypatch):
    rec: dict = {}

    class _S:
        copilot_enabled = True

    monkeypatch.setattr("src.shared.config.get_settings", lambda: _S())
    monkeypatch.setattr(
        "src.shared.database.async_session_factory",
        lambda: _FakeSession(rec),
    )

    async def _fake_ingest(session, tenant_id, force=False):
        rec["force"] = force
        return 42

    monkeypatch.setattr("src.copilot.rag.ingest_schema_docs", _fake_ingest)

    await copilot_job._copilot_schema_reindex_job()

    assert rec.get("force") is True, "Q.157.C: reindex tem de usar force=True"
    assert rec.get("commits") == 1, "Q.157.C: a sessão tem de fazer commit"


@pytest.mark.asyncio
async def test_reindex_job_noop_when_copilot_disabled(monkeypatch):
    """Sem `copilot_enabled`, o job sai sem tocar na BD nem no RAG."""
    rec: dict = {}

    class _S:
        copilot_enabled = False

    monkeypatch.setattr("src.shared.config.get_settings", lambda: _S())

    async def _boom(*_a, **_k):  # pragma: no cover - não deve ser chamado
        raise AssertionError("ingest_schema_docs não devia correr (disabled)")

    monkeypatch.setattr("src.copilot.rag.ingest_schema_docs", _boom)

    assert await copilot_job._copilot_schema_reindex_job() is None
    assert "force" not in rec
