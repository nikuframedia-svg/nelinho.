"""Q.32.A.1 — regressão do bug tz-aware vs TIMESTAMP WITHOUT TIME ZONE.

O detector/adaptive/dpo e o `AlertsEngine` filtravam `created_at >=
datetime.now(timezone.utc) - timedelta(...)`. Esse `since` tz-aware rebenta
no asyncpg porque a coluna é `TIMESTAMP WITHOUT TIME ZONE`. O bug escapou
porque os testes usam FakeSession (sem a coerção estrita do asyncpg).

Estes testes capturam o `select` que cada módulo constrói e afirmam que
qualquer datetime nos bind params é **naive** — apanham a regressão sem
precisar de um Postgres real.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from tests.conftest import FakeSession


class _RecordingSession(FakeSession):
    """FakeSession que guarda os statements passados a `execute`."""

    def __init__(self) -> None:
        super().__init__()
        self.statements: list = []

    async def execute(self, stmt):  # type: ignore[override]
        self.statements.append(stmt)
        return await super().execute(stmt)


def _bound_datetimes(stmt) -> list[datetime]:
    """Datetimes que aparecem como bind params do statement compilado."""
    compiled = stmt.compile()
    return [v for v in compiled.params.values() if isinstance(v, datetime)]


def _assert_all_naive(stmt) -> None:
    dts = _bound_datetimes(stmt)
    assert dts, "esperava pelo menos um datetime nos bind params"
    for d in dts:
        assert d.tzinfo is None, f"datetime tz-aware no query: {d!r}"


@pytest.mark.asyncio
async def test_preference_rule_detector_uses_naive_since():
    from src.governance.preference_learning import PreferenceRuleDetector

    session = _RecordingSession()
    detector = PreferenceRuleDetector(session, uuid4())
    await detector._fetch_commits_with_rejections(30)

    assert session.statements, "o detector não executou nenhum select"
    _assert_all_naive(session.statements[-1])


@pytest.mark.asyncio
async def test_adaptive_fitness_weights_uses_naive_since():
    from src.governance.preference_learning import AdaptiveFitnessWeights

    session = _RecordingSession()
    retainer = AdaptiveFitnessWeights(session, uuid4())
    await retainer._fetch_commits_with_rejections(30)

    assert session.statements, "o retrain não executou nenhum select"
    _assert_all_naive(session.statements[-1])


@pytest.mark.asyncio
async def test_dpo_dataset_builder_uses_naive_since():
    from src.governance.preference_learning import DPODatasetBuilder

    session = _RecordingSession()
    builder = DPODatasetBuilder(session, uuid4())
    await builder._collect(window_days=90)

    assert session.statements, "o dpo builder não executou nenhum select"
    _assert_all_naive(session.statements[0])


@pytest.mark.asyncio
async def test_alerts_engine_dedupe_uses_naive_since():
    from src.copilot.alerts.engine import AlertsEngine

    session = _RecordingSession()
    engine = AlertsEngine(session=session, tenant_id=uuid4())
    candidate = {
        "code": "TEST_CODE",
        "severity": "INFO",
        "title": "t",
        "message_pt": "m",
        "context": {},
        "entity_refs": ["entity:1"],  # não-vazio → dispara o select com `since`
    }
    # Só interessa o select de dedupe; a construção do CopilotAlert a seguir
    # pode falhar conforme o shape do candidate — o statement já foi gravado.
    try:
        await engine._persist_if_new(candidate)
    except Exception:
        pass

    assert session.statements, "o dedupe não executou nenhum select"
    _assert_all_naive(session.statements[0])
