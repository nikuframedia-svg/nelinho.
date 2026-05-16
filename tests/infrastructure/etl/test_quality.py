"""Q.20.E — quality mirror tests.

Pure builders (`_build_catalog`, `_build_rework`, helpers) run with no DB.
The end-to-end mirror runs against a live Postgres (marked ``integration``)
and also asserts incremental idempotency.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.infrastructure.erp.etl.quality import (
    _as_datetime,
    _build_catalog,
    _build_rework,
    _error_code,
    _is_nok,
    mirror_quality,
)


# ── pure helpers ──────────────────────────────────────────────────────────


def test_error_code_is_stable_and_normalised():
    assert _error_code("Molde com deformações") == _error_code(
        "  molde   COM deformações "
    )
    assert _error_code("a") != _error_code("b")


def test_is_nok():
    assert _is_nok("NOK") is True
    assert _is_nok("nok") is True
    assert _is_nok("OK") is False


def test_as_datetime_is_tz_aware():
    assert _as_datetime(date(2025, 1, 1)).tzinfo is not None
    assert _as_datetime(datetime(2025, 1, 1)).tzinfo is not None
    assert _as_datetime("not a date") is None


# ── catalogue builder ─────────────────────────────────────────────────────


def test_build_catalog_worst_gravidade_wins():
    probs = [
        {"descricao": "Molde baço", "gravidade": 1, "fase_culpada_id": "LAM"},
        {"descricao": "Molde baço", "gravidade": 3, "fase_culpada_id": "LAM"},
    ]
    catalog = _build_catalog(probs, [])
    assert len(catalog) == 1
    assert catalog[0]["severity_hint"] == "high"   # gravidade 3 wins
    assert catalog[0]["mold_related"] is True


def test_build_catalog_includes_checklist_items():
    catalog = _build_catalog([], [{"item": "Fuga de resina", "fase_id": "LAM"}])
    assert len(catalog) == 1
    assert catalog[0]["error_code"].startswith("CHK-")


# ── rework builder ────────────────────────────────────────────────────────


def test_build_rework_deterministic_id_for_idempotency():
    prob = {
        "prob_id": "P-1", "of_id": "OF-9", "descricao": "x",
        "data_registo": date(2025, 3, 1), "gravidade": 2,
    }
    first = _build_rework([prob], [], {})
    second = _build_rework([prob], [], {})
    assert first[0]["id"] == second[0]["id"]   # same ERP key → same uuid5


def test_build_rework_resolves_causer_and_skips_bad_rows():
    from uuid import uuid4

    emp_id = uuid4()
    probs = [
        {"prob_id": "P-1", "of_id": "OF-1", "descricao": "d",
         "data_registo": date(2025, 1, 1), "entidade_culpada_id": "E1"},
        # no of_id → skipped
        {"prob_id": "P-2", "of_id": None, "descricao": "d",
         "data_registo": date(2025, 1, 1)},
    ]
    rows = _build_rework(probs, [], {"E1": emp_id})
    assert len(rows) == 1
    assert rows[0]["causer_employee_id"] == emp_id


# ── integration ───────────────────────────────────────────────────────────


class _FakeAdapter:
    def __init__(self) -> None:
        self.since_seen = None

    async def fetch_quality_problems(self, *, since=None, **_kw):
        self.since_seen = since
        return [
            {"prob_id": "QP-1", "of_id": "OF-100", "descricao": "Molde baço",
             "gravidade": 3, "data_registo": date(2025, 2, 1),
             "fase_culpada_id": "LAM", "fase_avaliacao_id": "ACAB",
             "entidade_culpada_id": "QE-1", "chefe_id": None, "modelo_id": "K1"},
            {"prob_id": "QP-2", "of_id": "OF-101", "descricao": "Risco na pintura",
             "gravidade": 1, "data_registo": date(2025, 2, 2),
             "fase_culpada_id": "PINT", "fase_avaliacao_id": "PINT",
             "entidade_culpada_id": "UNKNOWN", "chefe_id": None, "modelo_id": "K2"},
        ]

    async def fetch_checklists(self, *, since=None, **_kw):
        return [
            {"checklist_id": "CK-1", "of_id": "OF-100", "fase_id": "LAM",
             "item": "Fuga de resina", "resultado": "NOK",
             "data_registo": date(2025, 2, 1)},
            {"checklist_id": "CK-2", "of_id": "OF-100", "fase_id": "LAM",
             "item": "Acabamento", "resultado": "OK",
             "data_registo": date(2025, 2, 1)},
        ]


@pytest.mark.integration
async def test_mirror_quality_end_to_end_and_idempotent():
    from datetime import date as _date
    from uuid import UUID

    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from src.core.models.employee import Employee
    from src.quality.models.rework import ErrorCatalog, ReworkEntry
    from src.shared.config import settings

    tenant = UUID("00000000-0000-0000-0000-000000000001")
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            session.add(Employee(tenant_id=tenant, employee_code="QE-1",
                                 employee_name="Causer", hire_date=_date(2020, 1, 1)))
            await session.flush()

            adapter = _FakeAdapter()
            first = await mirror_quality(
                session=session, tenant_id=tenant, adapter=adapter,
                since=_date(2025, 1, 1),
            )
            assert first.status == "ok"
            assert adapter.since_seen == _date(2025, 1, 1)   # window forwarded
            # 2 probs + 1 NOK checklist → 3 rework rows.
            assert first.rows_inserted >= 3

            rework = (await session.execute(
                select(ReworkEntry).where(
                    ReworkEntry.tenant_id == tenant,
                    ReworkEntry.of_id.in_(["OF-100", "OF-101"]),
                )
            )).scalars().all()
            assert len(rework) == 3
            # QP-1's causer resolved; QP-2's unknown operator → NULL.
            by_of = {r.of_id: r for r in rework if r.context.get("source") == "erp_offp_probs"}
            assert by_of["OF-100"].causer_employee_id is not None
            assert by_of["OF-101"].causer_employee_id is None

            catalog = await session.scalar(
                select(func.count()).select_from(ErrorCatalog).where(
                    ErrorCatalog.tenant_id == tenant
                )
            )
            assert catalog >= 3   # 2 prob descriptions + 1 checklist item

            # Re-run the SAME window — deterministic ids → no new rows.
            second = await mirror_quality(
                session=session, tenant_id=tenant, adapter=_FakeAdapter(),
                since=_date(2025, 1, 1),
            )
            assert second.rows_inserted == 0

            await session.rollback()
    finally:
        await engine.dispose()
