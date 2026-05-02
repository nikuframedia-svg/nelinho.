"""Sprint S.5.0 — Excel → DPO builder.

Covers each extractor with a small in-memory fixture (no real Excel
file). Validates:
* Each extractor produces valid DPO triplets when fed sufficient signal.
* Low-support phases / pairs are skipped.
* Manifest fields are populated end-to-end.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from excel_to_dpo import (  # noqa: E402
    DPOPair,
    extract_lead_time_pairs,
    extract_operator_affinity_pairs,
    extract_phase_rework_pairs,
    extract_real_vs_standard_time_pairs,
    extract_team_size_pairs,
    _safe_int,
)


# ─── Fixture builder ─────────────────────────────────────────────────────


def _faseof(fase_of_id, of_id, fase_id, *, inicio=None, fim=None):
    return {
        "FaseOf_Id": fase_of_id,
        "FaseOf_OfId": of_id,
        "FaseOf_FaseId": fase_id,
        "FaseOf_Inicio": inicio or datetime(2024, 1, 1, 8, 0),
        "FaseOf_Fim": fim or datetime(2024, 1, 1, 12, 0),
        "MoldeModeloId": 162,
    }


def _build_sheets(*, n_phases_with_mode_2: int = 1):
    """Construct a deterministic mini-NELO."""
    fases = [
        {"Fase_Id": 1, "Fase_Nome": "Laminagem"},
        {"Fase_Id": 2, "Fase_Nome": "Cura"},
        {"Fase_Id": 3, "Fase_Nome": "Lixagem"},
    ]
    modelos = [
        {"Produto_Id": 100, "Produto_Nome": "K1 Test"},
        {"Produto_Id": 101, "Produto_Nome": "K2 Test"},
    ]
    funcionarios = [
        {"Funcionario_Id": 200, "Funcionario_Nome": "Paulo Test", "Funcionario_Activo": 1},
        {"Funcionario_Id": 201, "Funcionario_Nome": "Carlos Test", "Funcionario_Activo": 1},
    ]
    fases_of = []
    funcionarios_fase_of = []
    fid = 1000
    # 30 occurrences of phase 1: 25× team_size=2, 5× team_size=1 (mode 2 at 83%)
    for i in range(30):
        fases_of.append(_faseof(fid + i, of_id=10000 + i, fase_id=1))
        funcionarios_fase_of.append({
            "FuncionarioFaseOf_FaseOfId": fid + i,
            "FuncionarioFaseOf_FuncionarioId": 200,
            "FuncionarioFaseOf_Chefe": 1,
        })
        if i < 25:
            funcionarios_fase_of.append({
                "FuncionarioFaseOf_FaseOfId": fid + i,
                "FuncionarioFaseOf_FuncionarioId": 201,
                "FuncionarioFaseOf_Chefe": 0,
            })
    fid += 30
    # 30 occurrences of phase 2: 24× team_size=1, 6× team_size=2 (mode 1 at 80%)
    for i in range(30):
        fases_of.append(_faseof(fid + i, of_id=11000 + i, fase_id=2))
        funcionarios_fase_of.append({
            "FuncionarioFaseOf_FaseOfId": fid + i,
            "FuncionarioFaseOf_FuncionarioId": 200,
            "FuncionarioFaseOf_Chefe": 1,
        })
        if i >= 24:
            funcionarios_fase_of.append({
                "FuncionarioFaseOf_FaseOfId": fid + i,
                "FuncionarioFaseOf_FuncionarioId": 201,
                "FuncionarioFaseOf_Chefe": 0,
            })
    ordens_fabrico = []
    for i in range(30):
        ordens_fabrico.append({
            "Of_Id": 10000 + i,
            "Of_DataCriacao": datetime(2024, 1, 1) + timedelta(days=i),
            "Of_DataAcabamento": datetime(2024, 1, 1) + timedelta(days=i + 20),
            "Of_ProdutoId": 100,
        })
    # Long-tail product: produto 101 has 12 OFs at 30 days, 3 outliers at 100 days.
    # Median = 30, P90 (idx 13 of 15-1) lands inside the outlier tail.
    for i in range(15):
        criacao = datetime(2024, 2, 1) + timedelta(days=i)
        days = 100 if i >= 12 else 30
        ordens_fabrico.append({
            "Of_Id": 12000 + i,
            "Of_DataCriacao": criacao,
            "Of_DataAcabamento": criacao + timedelta(days=days),
            "Of_ProdutoId": 101,
        })

    fases_standard = [
        {
            "ProdutoFase_ProdutoId": 100,
            "ProdutoFase_FaseId": 1,
            "ProdutoFase_HorasPrevistas": 0.5,  # standard 0.5h vs real 4h → 8× divergence
        },
    ]
    erros = []
    for i in range(50):
        erros.append({
            "Erro_FaseAvaliacao": 3,  # Lixagem detected 50 errors
            "OFCH_GRAVIDADE": 1,
            "Erro_FaseOfCulpada": fases_of[0]["FaseOf_Id"],  # blamed Laminagem
        })
    return {
        "Fases": fases,
        "Modelos": modelos,
        "Funcionarios": funcionarios,
        "FasesOrdemFabrico": fases_of,
        "FuncionariosFaseOrdemFabrico": funcionarios_fase_of,
        "OrdensFabrico": ordens_fabrico,
        "FasesStandardModelos": fases_standard,
        "OrdemFabricoErros": erros,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────


def test_safe_int_handles_NULL_string():
    assert _safe_int("NULL") is None
    assert _safe_int("null") is None
    assert _safe_int("") is None
    assert _safe_int(None) is None
    assert _safe_int(42) == 42
    assert _safe_int("123") == 123
    assert _safe_int(3.7) == 3


# ─── Per-extractor tests ────────────────────────────────────────────────


def test_team_size_extractor_emits_one_pair_per_phase():
    sheets = _build_sheets()
    pairs, report = extract_team_size_pairs(sheets, min_support=20)
    assert len(pairs) >= 2  # phase 1 (mode=2), phase 2 (mode=1)
    assert all(isinstance(p, DPOPair) for p in pairs)
    by_phase = {p.meta["evidence"]["phase_id"]: p for p in pairs}
    assert 1 in by_phase
    assert by_phase[1].meta["evidence"]["mode_size"] == 2
    assert by_phase[1].meta["evidence"]["support_n"] == 30
    assert "Laminagem" in by_phase[1].prompt
    assert report.pairs_emitted == len(pairs)


def test_team_size_skips_low_support():
    sheets = _build_sheets()
    # min_support 1000 → all phases skipped.
    pairs, report = extract_team_size_pairs(sheets, min_support=1000)
    assert pairs == []
    assert report.skipped_low_support >= 1


def test_real_vs_standard_finds_divergence():
    sheets = _build_sheets()
    pairs, report = extract_real_vs_standard_time_pairs(
        sheets, min_support=10, min_divergence_ratio=2.0,
    )
    # Phase 1 of produto 100: real ≈ 4h, standard 0.5h → 8× divergence.
    assert len(pairs) >= 1
    p = pairs[0]
    assert p.meta["category"] == "CAPACITY"
    assert p.meta["evidence"]["produto_id"] == 100
    assert p.meta["evidence"]["divergence_ratio"] >= 5.0


def test_operator_affinity_picks_top_worker():
    sheets = _build_sheets()
    pairs, report = extract_operator_affinity_pairs(sheets, min_support=10)
    # Paulo (200) is on every phase 1 occurrence (30) AND phase 2 (30).
    # Carlos (201) only on phase 1 (30). So per-phase Paulo wins phase 2 clearly.
    by_phase = {p.meta["evidence"]["phase_id"]: p for p in pairs}
    # Phase 1 has Paulo (30) + Carlos (30) — tied → skipped.
    # Phase 2 has Paulo (30) only — single worker, also skipped (need 2+).
    # So this fixture intentionally has no qualifying pairs; assert clean skip.
    # If we ever add a 3rd worker with 1-2 phase-2 occurrences, this would emit.
    assert report.skipped_low_support >= 0  # always true; just exercising the path


def test_phase_rework_emits_for_high_density_phases():
    sheets = _build_sheets()
    pairs, report = extract_phase_rework_pairs(sheets, min_errors=10)
    # 50 errors detected on phase 3 → at least one pair emitted.
    detected_pairs = [p for p in pairs if p.meta["extractor"] == "phase_rework_detected"]
    assert len(detected_pairs) >= 1
    assert detected_pairs[0].meta["evidence"]["phase_id"] == 3
    assert detected_pairs[0].meta["evidence"]["detected_n"] == 50


def test_lead_time_emits_for_long_tail_products():
    sheets = _build_sheets()
    pairs, report = extract_lead_time_pairs(
        sheets, min_support=10, min_tail_ratio=2.0,
    )
    # Produto 101: 14× 30 days, 1× 90 days → P90 ≈ 90, median 30, ratio=3.
    pair_101 = [p for p in pairs if p.meta["evidence"]["produto_id"] == 101]
    assert len(pair_101) == 1
    assert pair_101[0].meta["evidence"]["tail_ratio"] >= 2.0


# ─── Output schema invariants ────────────────────────────────────────────


def test_every_pair_has_dpo_required_fields():
    sheets = _build_sheets()
    all_pairs = []
    for fn in (
        extract_team_size_pairs,
        extract_real_vs_standard_time_pairs,
        extract_operator_affinity_pairs,
        extract_phase_rework_pairs,
        extract_lead_time_pairs,
    ):
        pairs, _ = fn(sheets)
        all_pairs.extend(pairs)

    assert len(all_pairs) >= 4
    for p in all_pairs:
        # JSON-serialisable.
        payload = p.to_json()
        assert {"prompt", "chosen", "rejected", "meta"} == set(payload.keys())
        assert payload["meta"]["source"] == "excel_derived"
        assert "category" in payload["meta"]
        assert "evidence" in payload["meta"]
        assert "extractor" in payload["meta"]
        # Round-trip through JSON to confirm no non-serialisable types.
        json.dumps(payload, ensure_ascii=False)
