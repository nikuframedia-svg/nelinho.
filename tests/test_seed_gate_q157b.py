"""Q.157.B — gate do seed `upsert_suggestions` (decisões PROPOSED hardcoded).

Por defeito a landing /decisoes vive do auto_propose real (Q.157.A); as 3
"suggestions" só são semeadas sob a flag SEED_FAKE_SUGGESTIONS=1, e bases já
semeadas são limpas (purge só pelos títulos-seed exatos).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seed_nelo_demo.py"
_spec = importlib.util.spec_from_file_location("seed_nelo_demo", _PATH)
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)


def test_fake_suggestions_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SEED_FAKE_SUGGESTIONS", raising=False)
    assert seed.fake_suggestions_enabled() is False


def test_fake_suggestions_enabled_with_flag(monkeypatch):
    monkeypatch.setenv("SEED_FAKE_SUGGESTIONS", "1")
    assert seed.fake_suggestions_enabled() is True


@pytest.mark.asyncio
async def test_purge_deletes_only_seed_titles():
    captured: dict = {}

    class _FakeResult:
        rowcount = 3

    class _FakeSession:
        async def execute(self, stmt):
            captured["stmt"] = stmt
            return _FakeResult()

    removed = await seed.purge_fake_suggestions(_FakeSession())
    assert removed == 3
    # É um DELETE sobre shared.decision_runs filtrado pelos títulos-seed.
    sql = str(captured["stmt"]).lower()
    assert sql.startswith("delete")
    assert "decision_runs" in sql
