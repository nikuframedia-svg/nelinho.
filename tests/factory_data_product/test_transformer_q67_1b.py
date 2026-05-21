"""Q.67.1.B — pin do mapping `MoldeEstado → em_manutencao`.

O dicionário completo de `MoldeEstado` no ERP NELO ainda não está
confirmado pelo Luis (issue Q.68.B). Por agora o transformer só
reconhece `estado=4` como "em manutenção". Estes testes ancoram esse
comportamento para que qualquer expansão futura do mapping (ex.: novos
estados 6, 7…) seja uma decisão deliberada e não um drift acidental.

Quando o Luis confirmar o dicionário completo, expandir
`_transform_molds` e adicionar casos a este ficheiro.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from src.factory_data_product.ingest.transformer import RawToCuratedTransformer


def _mold_row(estado: Any) -> dict:
    return {
        "sheet_name": "Moldes",
        "row_number": 2,
        "payload_json": {
            "MoldeId": "M-7",
            "MoldeNome": "K1 Vanquish L",
            "MoldeEstado": estado,
            "MoldeModelo": "K1 Vanquish L",
            "MoldeNumeroPocosId": 2,
            "MoldeModeloId": 42,
            "MoldeTamanhoId": 3,
        },
    }


def _transform_single(estado: Any) -> dict:
    ingestion_id = uuid4()
    result = RawToCuratedTransformer().transform([_mold_row(estado)], ingestion_id)
    assert len(result.molds) == 1, f"expected one mold for estado={estado!r}"
    return result.molds[0]


def test_estado_4_int_marks_em_manutencao_true():
    """Estado=4 (int) é o único valor confirmado como "manutenção"."""
    mold = _transform_single(4)
    assert mold["em_manutencao"] is True
    assert mold["estado"] == "4"


def test_estado_4_string_marks_em_manutencao_true():
    """Excel pode trazer o estado como string; comportamento idêntico ao int."""
    mold = _transform_single("4")
    assert mold["em_manutencao"] is True
    assert mold["estado"] == "4"


@pytest.mark.parametrize("estado", [1, 2, 3, 5])
def test_other_known_states_marked_em_manutencao_false(estado: int):
    """Estados não-4 nunca podem ser interpretados como manutenção sem
    confirmação explícita do Luis (issue Q.68.B)."""
    mold = _transform_single(estado)
    assert mold["em_manutencao"] is False
    assert mold["estado"] == str(estado)


def test_estado_none_marks_em_manutencao_false():
    """Estado ausente é não-manutenção (default seguro: molde disponível
    aparece em planeamento; pior caso é planearmos sobre um molde
    realmente partido, mas isso é um sintoma de dados em falta, não um
    bug do transformer)."""
    mold = _transform_single(None)
    assert mold["em_manutencao"] is False
    assert mold["estado"] is None


def test_estado_4_with_whitespace_still_matches():
    """`_safe_str` faz strip; um espaço extra no Excel não deve derrubar
    a derivação."""
    mold = _transform_single("  4  ")
    assert mold["em_manutencao"] is True


def test_estado_unknown_string_marks_em_manutencao_false():
    """Strings desconhecidas (ex.: "manutencao") NÃO contam como estado=4
    até o Luis confirmar a expansão do mapping."""
    mold = _transform_single("manutencao")
    assert mold["em_manutencao"] is False
