"""
F4.E — relatório "qualidade": bounds since/until têm de ser tz-aware.

``ReworkEntry.detected_at`` é ``DateTime(timezone=True)``; antes deste fix
``_gen_qualidade`` construía ``datetime.combine(...)`` NAIVE, o asyncpg
rebentava na comparação aware vs naive e o ``except Exception`` devolvia
``[]`` em silêncio — relatório de qualidade sempre vazio quando o
utilizador filtrava por datas.
"""

from __future__ import annotations

from datetime import date, timezone

import pytest

from src.reports.api import _gen_qualidade
from tests.conftest import TEST_TENANT_ID, FakeSession


@pytest.mark.asyncio
async def test_gen_qualidade_passes_tz_aware_bounds(monkeypatch):
    captured: dict = {}

    class _FakeQualitySvc:
        def __init__(self, session, tenant_id):
            pass

        async def group_by(self, *, group_by, since, until, top_n):
            captured["since"] = since
            captured["until"] = until
            return {"items": []}

    monkeypatch.setattr(
        "src.quality.services.dashboard_service.QualityDashboardService",
        _FakeQualitySvc,
    )

    rows = await _gen_qualidade(
        FakeSession(), TEST_TENANT_ID, date(2026, 6, 1), date(2026, 6, 10),
    )

    assert rows == []
    # O bug: tzinfo era None → comparação aware vs naive rebentava na BD.
    assert captured["since"].tzinfo == timezone.utc
    assert captured["until"].tzinfo == timezone.utc
    # Q.171.C preservado: until cobre o próprio dia (max.time()).
    assert captured["until"].date() == date(2026, 6, 10)
    assert captured["until"].hour == 23


@pytest.mark.asyncio
async def test_gen_qualidade_without_dates_passes_none(monkeypatch):
    captured: dict = {}

    class _FakeQualitySvc:
        def __init__(self, session, tenant_id):
            pass

        async def group_by(self, *, group_by, since, until, top_n):
            captured["since"] = since
            captured["until"] = until
            return {"items": []}

    monkeypatch.setattr(
        "src.quality.services.dashboard_service.QualityDashboardService",
        _FakeQualitySvc,
    )

    await _gen_qualidade(FakeSession(), TEST_TENANT_ID, None, None)
    assert captured["since"] is None
    assert captured["until"] is None
