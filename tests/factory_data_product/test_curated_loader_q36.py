"""Q.36.C — testes das funções puras do `curated_loader`.

Verifica o contrato de chaves entre as 3 tabelas curadas e a marcação
mold-typed que o `MoldDetector` exige. As funções de transformação são
puras (sem DB, sem ERP) — testáveis directamente. O `load_curated`
end-to-end precisa de Postgres real e corre no passo de integração.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from src.adapters.nelo.schemas import ChecklistRow, OperationCrewRow, OperationRow
from src.explain.diagnostics.erro_tree import _MOLD_TYPED_ERROR_KEYWORDS
from src.factory_data_product.etl.curated_loader import (
    checklist_to_quality_events,
    crew_to_allocations,
    operations_to_order_phases,
)

INGESTION = uuid4()


def _op(**kw) -> OperationRow:
    base = dict(
        operation_id=88, work_order_id=5000, phase_id=18, phase_name="Laminagem",
        start_at=datetime(2025, 6, 1, 8, 0), end_at=datetime(2025, 6, 1, 14, 0),
        expected_at=None, standard_time_hours=6.0, temperature=21.0, humidity=55.0,
        is_return=False, severe_return=False, product_id=900,
        operation_mold_id=777, mold_work_order_id=None,
    )
    base.update(kw)
    return OperationRow(**base)


def _crew(**kw) -> OperationCrewRow:
    base = dict(
        operation_id=88, work_order_id=5000, phase_id=18,
        operator_id=42, is_chefe=False,
    )
    base.update(kw)
    return OperationCrewRow(**base)


def _chk(**kw) -> ChecklistRow:
    base = dict(
        checklist_id=1, work_order_id=5000, operation_id=88, phase_id=18,
        phase_name="Laminagem", description="Risco na pintura", description_en=None,
        severity=2, mold_repair=False, blame_chefe=False, blame_operation_id=None,
        resolved=False, state=1, verified_at=datetime(2025, 6, 1, 10, 0),
        updated_at=None, detected_at=datetime(2025, 6, 1, 10, 0),
        operation_mold_id=777,
    )
    base.update(kw)
    return ChecklistRow(**base)


# ── order_phase de OF_FP ──────────────────────────────────────────────────


def test_order_phase_fase_of_id_is_of_fase_composite():
    """fase_of_id = "of_id::fase_id" — chave estável que sobrevive ao
    colapso de reworks e liga à CuratedAllocation."""
    rows = operations_to_order_phases(
        [_op(work_order_id=5000, phase_id=18)], INGESTION,
    )
    assert rows[0]["fase_of_id"] == "5000::18"


def test_order_phase_collapses_rework_passes():
    """Uma OF que passa 2× pela mesma fase (retrabalho) → UMA linha,
    horas somadas, sem violar uq_(ingestion, of_id, fase_id)."""
    rows = operations_to_order_phases([
        _op(operation_id=88, start_at=datetime(2025, 6, 1, 8, 0),
            end_at=datetime(2025, 6, 1, 14, 0)),   # 6h
        _op(operation_id=99, start_at=datetime(2025, 6, 3, 8, 0),
            end_at=datetime(2025, 6, 3, 11, 0)),   # 3h, rework
    ], INGESTION)
    assert len(rows) == 1
    assert float(rows[0]["horas_reais"]) == 9.0
    assert rows[0]["fase_of_id"] == "5000::18"


def test_order_phase_derives_horas_reais_from_dates():
    """6h entre OFFP_DATAINICIO e OFFP_DATAFIM."""
    rows = operations_to_order_phases([
        _op(start_at=datetime(2025, 6, 1, 8, 0), end_at=datetime(2025, 6, 1, 14, 0)),
    ], INGESTION)
    assert float(rows[0]["horas_reais"]) == 6.0


def test_order_phase_horas_reais_none_when_negative_interval():
    """Datas invertidas (dado sujo) → None, não horas negativas."""
    rows = operations_to_order_phases([
        _op(start_at=datetime(2025, 6, 1, 14, 0), end_at=datetime(2025, 6, 1, 8, 0)),
    ], INGESTION)
    assert rows[0]["horas_reais"] is None


def test_order_phase_business_keys_never_empty():
    """Linhas sem of_id ou fase_id ficam de fora — business key NOT NULL."""
    rows = operations_to_order_phases([_op(work_order_id=0)], INGESTION)
    assert rows == []


def test_order_phase_carries_mold():
    rows = operations_to_order_phases([_op(operation_mold_id=777)], INGESTION)
    assert rows[0]["molde_id"] == "777"


# ── allocation de OFFP_EQ ─────────────────────────────────────────────────


def test_allocation_fase_of_id_matches_order_phase():
    """A consistência de chaves: order_phase.fase_of_id == allocation.fase_of_id."""
    op_rows = operations_to_order_phases(
        [_op(work_order_id=5000, phase_id=18)], INGESTION,
    )
    alloc_rows = crew_to_allocations(
        [_crew(work_order_id=5000, phase_id=18)], INGESTION,
    )
    assert op_rows[0]["fase_of_id"] == alloc_rows[0]["fase_of_id"] == "5000::18"


def test_allocation_carries_chefe_flag():
    rows = crew_to_allocations([_crew(is_chefe=True)], INGESTION)
    assert rows[0]["is_chefe"] is True


def test_allocation_skips_rows_without_operator():
    rows = crew_to_allocations([_crew(operator_id=0)], INGESTION)
    assert rows == []


def test_allocation_dedupes_operator_across_rework_passes():
    """O mesmo operador em 2 operações do mesmo (of, fase) → UMA linha;
    is_chefe fica True se foi chefe nalguma passagem."""
    rows = crew_to_allocations([
        _crew(operation_id=88, operator_id=42, is_chefe=False),
        _crew(operation_id=99, operator_id=42, is_chefe=True),
    ], INGESTION)
    assert len(rows) == 1
    assert rows[0]["is_chefe"] is True


def test_allocation_skips_rows_without_phase():
    rows = crew_to_allocations([_crew(phase_id=0)], INGESTION)
    assert rows == []


# ── quality_event de OF_CHECKLIST ─────────────────────────────────────────


def test_quality_event_of_fase_keys_match_order_phase():
    """(of_id, fase_id) é idêntico entre order_phase e quality_event."""
    op_rows = operations_to_order_phases(
        [_op(work_order_id=5000, phase_id=18)], INGESTION,
    )
    q_rows = checklist_to_quality_events(
        [_chk(work_order_id=5000, phase_id=18)], INGESTION,
    )
    assert op_rows[0]["of_id"] == q_rows[0]["of_id"] == "5000"
    assert op_rows[0]["fase_id"] == q_rows[0]["fase_id"] == "18"


def test_quality_event_business_key_never_empty():
    """Linhas sem of_id ficam de fora."""
    rows = checklist_to_quality_events([_chk(work_order_id=0)], INGESTION)
    assert rows == []


def test_quality_event_mold_repair_flag_yields_mold_typed_erro_tipo():
    """OFCH_MOLDE_REPARAR + texto sem keyword → erro_tipo ganha a tag."""
    rows = checklist_to_quality_events(
        [_chk(mold_repair=True, description="Defeito qualquer")], INGESTION,
    )
    erro = rows[0]["erro_tipo"].lower()
    assert any(kw in erro for kw in _MOLD_TYPED_ERROR_KEYWORDS)


def test_quality_event_mold_keyword_text_kept_verbatim():
    """Texto que já tem keyword mold-typed mantém-se tal e qual."""
    rows = checklist_to_quality_events(
        [_chk(description="Interior enrugado no casco")], INGESTION,
    )
    assert rows[0]["erro_tipo"] == "Interior enrugado no casco"
    assert "interior enrugado" in rows[0]["erro_tipo"].lower()


def test_quality_event_non_mold_defect_not_tagged():
    """Defeito de pintura não ganha keyword de molde."""
    rows = checklist_to_quality_events(
        [_chk(description="Risco na pintura", mold_repair=False)], INGESTION,
    )
    erro = rows[0]["erro_tipo"].lower()
    assert not any(kw in erro for kw in _MOLD_TYPED_ERROR_KEYWORDS)


def test_quality_event_data_evento_from_detected_at():
    rows = checklist_to_quality_events(
        [_chk(detected_at=datetime(2025, 3, 4, 9, 0))], INGESTION,
    )
    assert rows[0]["data_evento"].year == 2025
    assert rows[0]["data_evento"].month == 3


def test_all_rows_share_ingestion_id():
    """As 3 tabelas partilham o mesmo ingestion_id (FK → ingestion_run)."""
    op_rows = operations_to_order_phases([_op()], INGESTION)
    alloc_rows = crew_to_allocations([_crew()], INGESTION)
    q_rows = checklist_to_quality_events([_chk()], INGESTION)
    assert op_rows[0]["ingestion_id"] == INGESTION
    assert alloc_rows[0]["ingestion_id"] == INGESTION
    assert q_rows[0]["ingestion_id"] == INGESTION
