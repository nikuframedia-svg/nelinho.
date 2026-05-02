"""Sprint Q.8 Fase 3 — RawToCurated `Modelos` transform tests.

The Excel sheet `Modelos` is actually the product catalogue (rows have
`Produto_*` prefixes). It carries 9 columns; we materialise all of them
so the planning layer doesn't have to re-query the Excel raw layer to
look up a product's mass / gel-coat quantities.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from src.factory_data_product.ingest.transformer import RawToCuratedTransformer


def _row(**overrides):
    payload = {
        "Produto_Id": 20168,
        "Produto_Nome": "K1 Vanquish L SCS",
        "Produto_PesoDesmolde": 8.5,
        "Produto_PesoAcabamento": 11.0,
        "Produto_QtdGelDeck": 0.9,
        "Produto_QtdGelCasco": 1.0,
        "Produto_NumeroPocosId": 1,
        "Produto_ModeloId": 3,
        "Produto_TamanhoId": 2,
    }
    payload.update(overrides)
    return {
        "sheet_name": "Modelos",
        "row_number": 2,
        "payload_json": payload,
    }


def test_full_modelo_row_persists_all_columns():
    ingestion_id = uuid4()
    result = RawToCuratedTransformer().transform([_row()], ingestion_id)

    assert len(result.models) == 1
    m = result.models[0]
    assert m["produto_id"] == "20168"
    assert m["produto_nome"] == "K1 Vanquish L SCS"
    assert m["modelo_id"] == "3"
    assert m["tamanho_id"] == "2"
    assert m["peso_desmolde_kg"] == Decimal("8.5")
    assert m["peso_acabamento_kg"] == Decimal("11.0")
    assert m["qtd_gel_deck"] == Decimal("0.9")
    assert m["qtd_gel_casco"] == Decimal("1.0")
    assert m["numero_pocos_id"] == "1"
    assert m["ingestion_id"] == ingestion_id


def test_duplicate_produto_id_collapses_with_warning():
    ingestion_id = uuid4()
    raw_rows = [
        _row(),
        _row(),  # exact duplicate
        _row(Produto_Nome="K1 Vanquish L SCS variant"),  # same id, drift on name
    ]

    result = RawToCuratedTransformer().transform(raw_rows, ingestion_id)

    assert len(result.models) == 1
    assert result.models[0]["produto_nome"] == "K1 Vanquish L SCS"  # first wins
    assert any("duplicate" in w for w in result.warnings)


def test_missing_produto_id_dropped():
    ingestion_id = uuid4()
    raw_rows = [
        _row(Produto_Id=None),
        _row(Produto_Id=""),
        _row(Produto_Id=20169, Produto_Nome="K1 Vanquish ML"),
    ]

    result = RawToCuratedTransformer().transform(raw_rows, ingestion_id)

    assert len(result.models) == 1
    assert result.models[0]["produto_id"] == "20169"


def test_partial_columns_tolerated():
    """Real ERP exports occasionally drop optional columns; nullable
    decimals should land as None rather than blow up."""
    ingestion_id = uuid4()
    raw_rows = [
        {
            "sheet_name": "Modelos",
            "row_number": 2,
            "payload_json": {
                "Produto_Id": 30000,
                "Produto_Nome": "Stripped row",
                # all numeric columns absent
            },
        },
    ]

    result = RawToCuratedTransformer().transform(raw_rows, ingestion_id)

    assert len(result.models) == 1
    m = result.models[0]
    assert m["peso_desmolde_kg"] is None
    assert m["qtd_gel_deck"] is None


def test_total_curated_includes_models():
    ingestion_id = uuid4()
    raw_rows = [_row(Produto_Id=i) for i in (20168, 20169, 20170)]

    result = RawToCuratedTransformer().transform(raw_rows, ingestion_id)

    assert result.total_curated == 3
