"""Sprint Q.13.H — Bootstrap script row-builder unit tests.

`scripts/train_quality_risk_from_excel.py` reads the NELO Excel
directly and builds training rows in the same shape as the curated-
layer-driven `build_training_dataset`. These tests pin the row shape
without needing a 60MB Excel: synthetic in-memory inputs exercise the
joins + aggregates.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from train_quality_risk_from_excel import _norm  # noqa: E402


# ───────────────────────────────────────────────────────────────────────────
# `_norm` — Excel literal NULL handling
# ───────────────────────────────────────────────────────────────────────────


def test_norm_drops_string_null():
    assert _norm("NULL") is None
    assert _norm("null") is None
    assert _norm("Null") is None
    assert _norm(" NULL ") is None


def test_norm_passes_real_values_through():
    assert _norm(0) == 0
    assert _norm("real-value") == "real-value"
    assert _norm(3.14) == 3.14
    assert _norm(None) is None


# ───────────────────────────────────────────────────────────────────────────
# `build_rows` — main row assembler. Uses an in-memory fake workbook
# instead of openpyxl + a real Excel.
# ───────────────────────────────────────────────────────────────────────────


class _FakeSheet:
    """Tiny stand-in for openpyxl's read-only worksheet — only exposes
    `iter_rows(values_only=True)`."""

    def __init__(self, header: tuple, rows: List[tuple]) -> None:
        self._header = header
        self._rows = rows

    def iter_rows(self, values_only: bool = False):  # noqa: ARG002
        yield self._header
        for r in self._rows:
            yield r


class _FakeWorkbook:
    def __init__(self, sheets: Dict[str, _FakeSheet]) -> None:
        self._sheets = sheets

    def __getitem__(self, name: str) -> _FakeSheet:
        return self._sheets[name]


def _make_workbook() -> _FakeWorkbook:
    """3 orders × 4 phases × 1 mold + 2 errors. Just enough to
    exercise every join + aggregate."""
    return _FakeWorkbook({
        "FasesOrdemFabrico": _FakeSheet(
            (
                "FaseOf_Id", "FaseOf_OfId", "FaseOf_Inicio", "FaseOf_Fim",
                "FaseOf_DataPrevista", "FaseOf_Coeficiente",
                "FaseOf_CoeficienteX", "FaseOf_FaseId", "FaseOf_Peso",
                "FaseOf_Retorno", "FaseOf_Turno", "FaseOf_Sequencia",
                "MoldeOfId", "MoldeNome", "MoldeNumeroPocosId",
                "MoldeModeloId", "MoldeTamanhoId", "FaseOf_HorasPrevistas",
            ),
            [
                # of=A, Laminagem (fase=1) — error
                (1001, "A", None, "2026-01-01", "NULL", 1, 0, "1",
                 0, 0, 1, 1, "M-7", "MOLDE-7", 1, 42, 3, 8),
                # of=A, Pintura (fase=2) — clean
                (1002, "A", None, "2026-01-02", "NULL", 1, 0, "2",
                 0, 0, 1, 2, "M-7", "MOLDE-7", 1, 42, 3, 4),
                # of=B, Laminagem — clean
                (1003, "B", None, "2026-01-03", "NULL", 1, 0, "1",
                 0, 0, 1, 1, "M-7", "MOLDE-7", 1, 42, 3, 8),
                # of=C, Lixagem (fase=3) — error (the high-rework phase
                # we know from Plan v4 §3.3)
                (1004, "C", None, "2026-01-04", "NULL", 1, 0, "3",
                 0, 0, 1, 1, "NULL", "NULL", "NULL", "NULL", "NULL", 6),
            ],
        ),
        "OrdensFabrico": _FakeSheet(
            ("Of_Id", "Of_DataCriacao", "Of_DataAcabamento",
             "Of_ProdutoId", "Of_FaseId", "Of_DataTransporte"),
            [
                ("A", None, None, "20168", 12, None),
                ("B", None, None, "20169", 12, None),
                ("C", None, None, "20168", 12, None),
            ],
        ),
        "Moldes": _FakeSheet(
            ("MoldeId", "MoldeNome", "MoldeEstado", "MoldeModelo",
             "MoldeNumeroPocosId", "MoldeModeloId", "MoldeTamanhoId"),
            [("M-7", 7, 15, "K1", 2, 42, 3)],
        ),
        "FuncionariosFaseOrdemFabrico": _FakeSheet(
            ("FuncionarioFaseOf_FaseOfId", "FuncionarioFaseOf_FuncionarioId",
             "FuncionarioFaseOf_Chefe"),
            [
                # 1001 has 2 workers (pair)
                (1001, "w1", 1),
                (1001, "w2", 0),
                # 1002 has 1 worker
                (1002, "w1", 1),
                # 1003: 1 worker
                (1003, "w3", 1),
                # 1004: no rows -> defaults to 1 in the row builder
            ],
        ),
        "OrdemFabricoErros": _FakeSheet(
            ("Erro_Descricao", "Erro_OfId", "Erro_FaseAvaliacao",
             "OFCH_GRAVIDADE", "Erro_FaseOfAvaliacao", "Erro_FaseOfCulpada"),
            [
                ("Bolha", "A", "1", 1, 1001, 1001),
                ("Lixagem incompleta", "C", "3", 2, 1004, 1004),
            ],
        ),
    })


def test_load_dataset_round_trip():
    """Use the fake workbook to drive the same call chain `load_dataset`
    would invoke against a real Excel file."""
    from train_quality_risk_from_excel import (
        build_rows,
        read_errors,
        read_molds,
        read_orders,
        read_team_sizes,
    )

    wb = _make_workbook()
    order_to_modelo = read_orders(wb)
    mold_pockets = read_molds(wb)
    team_sizes = read_team_sizes(wb)
    error_keys = read_errors(wb)

    assert order_to_modelo == {"A": "20168", "B": "20169", "C": "20168"}
    assert mold_pockets == {"M-7": 2}
    assert team_sizes == {"1001": 2, "1002": 1, "1003": 1}
    assert error_keys == {("A", "1"), ("C", "3")}

    rows = build_rows(
        wb,
        order_to_modelo=order_to_modelo,
        mold_pockets=mold_pockets,
        team_sizes=team_sizes,
        error_keys=error_keys,
    )
    assert len(rows) == 4

    # Find the Laminagem rows (fase_id="1")
    lam = [r for r in rows if r["fase_id"] == "1"]
    assert len(lam) == 2
    # phase_error_rate for Laminagem: 1 error / 2 phases = 0.5
    assert lam[0]["phase_error_rate"] == pytest.approx(0.5)

    # Find the Lixagem row (fase_id="3")
    lix = [r for r in rows if r["fase_id"] == "3"]
    assert len(lix) == 1
    # phase_error_rate for Lixagem: 1/1 = 1.0
    assert lix[0]["phase_error_rate"] == pytest.approx(1.0)
    # No mold reference → fallback to default pocket_count = 1
    assert lix[0]["mold_pocket_count"] == 1
    # No worker rows for fase_of=1004 → team_size defaults to 1
    assert lix[0]["team_size"] == 1
    # Labelled positive (matches error key (C, 3))
    assert lix[0]["is_error"] == 1

    # Of A laminagem — pair team_size=2, mold pocket_count=2, IS_ERROR=1
    a_lam = next(r for r in lam if r["modelo_id"] == "20168")
    assert a_lam["team_size"] == 2
    assert a_lam["mold_pocket_count"] == 2
    assert a_lam["is_error"] == 1


def test_pipeline_drops_null_string_modelo():
    """Excel exports literal 'NULL' for missing fields. The trainer
    must coerce them to empty strings rather than ship the literal
    'NULL' as a categorical value (which would create a fake category
    in the encoded matrix)."""
    from train_quality_risk_from_excel import read_orders

    wb = _FakeWorkbook({
        "OrdensFabrico": _FakeSheet(
            ("Of_Id", "Of_DataCriacao", "Of_DataAcabamento",
             "Of_ProdutoId", "Of_FaseId", "Of_DataTransporte"),
            [
                ("A", None, None, "NULL", 12, None),  # missing produto
                ("B", None, None, "20169", 12, None),
                (None, None, None, "20170", 12, None),  # no Of_Id — skip
            ],
        ),
    })
    out = read_orders(wb)
    # Order A had NULL produto → coerced to empty string (not "NULL")
    assert out == {"A": "", "B": "20169"}


def test_team_sizes_aggregate_handles_missing_rows():
    from train_quality_risk_from_excel import read_team_sizes

    wb = _FakeWorkbook({
        "FuncionariosFaseOrdemFabrico": _FakeSheet(
            ("FuncionarioFaseOf_FaseOfId", "FuncionarioFaseOf_FuncionarioId",
             "FuncionarioFaseOf_Chefe"),
            [
                (None, "w-x", 1),  # missing FaseOfId — skip
                ("PHASE_X", "w-1", 1),
                ("PHASE_X", "w-2", 0),
                ("PHASE_X", "w-3", 0),
                ("PHASE_Y", "w-4", 1),
            ],
        ),
    })
    out = read_team_sizes(wb)
    assert out == {"PHASE_X": 3, "PHASE_Y": 1}
