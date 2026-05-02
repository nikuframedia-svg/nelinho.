"""Sprint Q.8 Fase 2.5 — RawToCurated allocation transform tests.

The Excel sheet `FuncionariosFaseOrdemFabrico` carries 423K rows with the
historical worker × order-phase pairing. These tests pin down the
transform invariants:

* Composite key (fase_of_id, funcionario_id) is enforced — duplicate
  rows from a buggy ingest collapse to a single curated row with the
  duplicate count surfaced as a warning.
* `is_chefe` decoded from the Excel int (0/1) into a real bool.
* Rows with an incomplete composite key drop silently (the join target
  would be useless without both halves).
"""

from __future__ import annotations

from uuid import uuid4

from src.factory_data_product.ingest.transformer import RawToCuratedTransformer


def _row(fase_of_id, funcionario_id, chefe=0):
    return {
        "sheet_name": "FuncionariosFaseOrdemFabrico",
        "row_number": 2,
        "payload_json": {
            "FuncionarioFaseOf_FaseOfId": fase_of_id,
            "FuncionarioFaseOf_FuncionarioId": funcionario_id,
            "FuncionarioFaseOf_Chefe": chefe,
        },
    }


def test_basic_pair_allocation_chefe_decoded():
    ingestion_id = uuid4()
    raw_rows = [
        _row(2073059, 20917, chefe=1),
        _row(2073059, 24582, chefe=0),
    ]

    result = RawToCuratedTransformer().transform(raw_rows, ingestion_id)

    assert len(result.allocations) == 2
    chefe = next(a for a in result.allocations if a["is_chefe"])
    partner = next(a for a in result.allocations if not a["is_chefe"])
    assert chefe["funcionario_id"] == "20917"
    assert partner["funcionario_id"] == "24582"
    # Both share the fase_of_id — that's the join key into CuratedOrderPhase.
    assert chefe["fase_of_id"] == partner["fase_of_id"] == "2073059"
    assert chefe["ingestion_id"] == ingestion_id


def test_duplicate_composite_key_collapses_with_warning():
    ingestion_id = uuid4()
    raw_rows = [
        _row(2073066, 24582, chefe=1),
        _row(2073066, 24582, chefe=1),  # exact duplicate
        _row(2073066, 24582, chefe=0),  # same key, conflicting chefe — still drop
    ]

    result = RawToCuratedTransformer().transform(raw_rows, ingestion_id)

    assert len(result.allocations) == 1
    # First-write-wins; chefe=1 from the first row.
    assert result.allocations[0]["is_chefe"] is True
    # Operator must see the dedup happened.
    assert any("duplicate" in w for w in result.warnings)


def test_incomplete_composite_key_silently_dropped():
    ingestion_id = uuid4()
    raw_rows = [
        # missing FuncionarioId
        {
            "sheet_name": "FuncionariosFaseOrdemFabrico",
            "row_number": 2,
            "payload_json": {
                "FuncionarioFaseOf_FaseOfId": 9999,
                "FuncionarioFaseOf_Chefe": 1,
            },
        },
        # missing FaseOfId
        {
            "sheet_name": "FuncionariosFaseOrdemFabrico",
            "row_number": 3,
            "payload_json": {
                "FuncionarioFaseOf_FuncionarioId": 21000,
                "FuncionarioFaseOf_Chefe": 0,
            },
        },
        # full row — should still land
        _row(2073070, 24582, chefe=1),
    ]

    result = RawToCuratedTransformer().transform(raw_rows, ingestion_id)

    assert len(result.allocations) == 1
    assert result.allocations[0]["fase_of_id"] == "2073070"


def test_total_curated_includes_allocations():
    ingestion_id = uuid4()
    raw_rows = [
        _row(2073059, 20917, chefe=1),
        _row(2073059, 24582, chefe=0),
        _row(2073066, 20918, chefe=1),
    ]

    result = RawToCuratedTransformer().transform(raw_rows, ingestion_id)

    # `total_curated` was the bug surface — adding a list without
    # bumping the property leaves dashboards reporting 0.
    assert result.total_curated == 3
