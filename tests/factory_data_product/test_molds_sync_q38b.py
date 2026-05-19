"""Q.38.B — Excel mold sync (`Folha_IA_extra.xlsx` → `plan.mold`).

The ERP mirror brings only ~91 molds; the full ~510 live in the Excel
`Moldes` sheet. These tests cover the pure transform (`_transform_molds`
reused) + the `plan.mold` mapping, and the end-to-end `EtlRunner`-backed
upsert against a recording fake session (no Postgres, no SQL Server).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.factory_data_product.etl.molds_sync import (
    curated_mold_to_plan_row,
    excel_rows_to_plan_molds,
    sync_molds_from_excel,
)
from src.plan.models.mold import Mold

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _raw_mold_row(**overrides) -> dict:
    """A RAW `Moldes` row in the shape `_transform_molds` expects."""
    payload = {
        "MoldeId": 70004,
        "MoldeNome": 1040136,
        "MoldeEstado": 15,
        "MoldeModelo": "K1 Vanquish II ML",
        "MoldeNumeroPocosId": 1,
        "MoldeModeloId": 42,
        "MoldeTamanhoId": 3,
    }
    payload.update(overrides)
    return {"sheet_name": "Moldes", "payload_json": payload}


# ── recording fake session (EtlRunner needs add + select) ──────────────


class _Result:
    def __init__(self, items):
        self._items = list(items)

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self._items)


class _RecordingSession:
    """Fake AsyncSession: records `add`-ed objects, serves `select`."""

    def __init__(self):
        self.added: list = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    async def execute(self, statement, *_a, **_kw):
        descs = list(getattr(statement, "column_descriptions", []) or [])
        if not descs:
            return _Result([])
        model = descs[0].get("entity")
        matches = [
            o for o in self.added if model is not None and isinstance(o, model)
        ]
        return _Result(matches)


# ── pure mapper ─────────────────────────────────────────────────────────


def test_curated_mold_to_plan_row_uses_molde_id_as_business_key():
    row = curated_mold_to_plan_row({
        "molde_id": "70004", "molde_nome": "K1 Vanquish II ML",
        "tipo": "K1 Vanquish II ML", "modelo_id": "42", "em_manutencao": False,
    })
    assert row["mold_code"] == "70004"
    assert row["name"] == "K1 Vanquish II ML"
    assert row["mold_type"] == "K1 Vanquish II ML"
    assert row["model_id"] == "42"
    assert row["active"] is True


def test_curated_mold_in_maintenance_is_inactive():
    """`em_manutencao=True` (estado 4) → mold is not active."""
    row = curated_mold_to_plan_row({"molde_id": "9", "em_manutencao": True})
    assert row["active"] is False


def test_curated_mold_without_id_is_dropped():
    assert curated_mold_to_plan_row({"molde_id": ""}) is None
    assert curated_mold_to_plan_row({"molde_id": None}) is None


def test_curated_mold_falls_back_to_id_when_name_missing():
    row = curated_mold_to_plan_row({"molde_id": "70004", "molde_nome": None})
    assert row["name"] == "70004"


def test_curated_mold_empty_modelo_id_is_sentinel():
    """`plan.mold.model_id` is NOT NULL — a missing curated modelo_id
    maps to the empty-string sentinel (applied insert-only later)."""
    row = curated_mold_to_plan_row({"molde_id": "70004", "modelo_id": None})
    assert row["model_id"] == ""


# ── Excel rows → plan.mold (transform reused) ──────────────────────────


def test_excel_rows_to_plan_molds_runs_curated_transform():
    """The curated step reuses `_transform_molds`, so a RAW Excel row
    flows all the way to a `plan.mold` column dict."""
    rows = excel_rows_to_plan_molds([
        _raw_mold_row(MoldeId=70004),
        _raw_mold_row(MoldeId=70009, MoldeNome="K1 Vanquish II XXL"),
    ])
    assert {r["mold_code"] for r in rows} == {"70004", "70009"}


def test_excel_rows_to_plan_molds_empty_input_is_clean():
    assert excel_rows_to_plan_molds([]) == []


# ── end-to-end sync ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_inserts_excel_molds(monkeypatch):
    """`sync_molds_from_excel` upserts the parsed Excel molds into
    `plan.mold` keyed by `mold_code`."""
    import src.factory_data_product.etl.molds_sync as mod

    monkeypatch.setattr(
        mod, "parse_excel_molds",
        lambda _path: [
            _raw_mold_row(MoldeId=70004),
            _raw_mold_row(MoldeId=70009),
            _raw_mold_row(MoldeId=70019),
        ],
    )
    session = _RecordingSession()
    result = await sync_molds_from_excel(
        session=session, tenant_id=TENANT, file_path="ignored.xlsx",
    )

    assert result.status == "ok"
    assert result.rows_read == 3
    assert result.rows_inserted == 3
    molds = [o for o in session.added if isinstance(o, Mold)]
    assert {m.mold_code for m in molds} == {"70004", "70009", "70019"}
    # NOT NULL model_id is seeded on insert.
    assert all(m.model_id is not None for m in molds)


@pytest.mark.asyncio
async def test_sync_is_idempotent(monkeypatch):
    """A second sync of the same molds inserts nothing new."""
    import src.factory_data_product.etl.molds_sync as mod

    monkeypatch.setattr(
        mod, "parse_excel_molds",
        lambda _path: [_raw_mold_row(MoldeId=70004)],
    )
    session = _RecordingSession()
    await sync_molds_from_excel(
        session=session, tenant_id=TENANT, file_path="ignored.xlsx",
    )
    result = await sync_molds_from_excel(
        session=session, tenant_id=TENANT, file_path="ignored.xlsx",
    )
    assert result.rows_inserted == 0
    assert result.rows_updated == 0
    molds = [o for o in session.added if isinstance(o, Mold)]
    assert len(molds) == 1  # no duplicate row


@pytest.mark.asyncio
async def test_sync_empty_sheet_is_clean(monkeypatch):
    """A workbook with no `Moldes` rows yields a clean zero-row run."""
    import src.factory_data_product.etl.molds_sync as mod

    monkeypatch.setattr(mod, "parse_excel_molds", lambda _path: [])
    session = _RecordingSession()
    result = await sync_molds_from_excel(
        session=session, tenant_id=TENANT, file_path="ignored.xlsx",
    )
    assert result.status == "ok"
    assert result.rows_read == 0
    assert result.rows_inserted == 0


def test_parse_excel_molds_reads_real_workbook():
    """The real `Folha_IA_extra.xlsx` `Moldes` sheet parses to ~510 rows.

    Skips when the workbook is not in the repo (it is large / may be
    git-ignored on a fresh clone)."""
    from pathlib import Path

    from src.factory_data_product.etl.molds_sync import parse_excel_molds

    excel = Path(__file__).resolve().parents[2] / "Folha_IA_extra.xlsx"
    if not excel.exists():
        pytest.skip("Folha_IA_extra.xlsx not present in repo")
    rows = parse_excel_molds(excel)
    # Volumetry config expects 510 (min 450, max 550).
    assert 450 <= len(rows) <= 550
    plan_rows = excel_rows_to_plan_molds(rows)
    assert 450 <= len(plan_rows) <= 550
