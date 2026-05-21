"""
Q.67.3.D — Coverage tests for `src/factory_data_product/models/curated.py`.

The curated models are SQLAlchemy ORM rows: instantiation, attribute access
and defaults are the only behaviour we can exercise without a live database.
These tests pin those shapes (column presence, defaults, mixin attachment,
table-args metadata) so that an accidental rename / type drift surfaces
immediately.

All tests run offline — no engine, no session, no Postgres required.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.factory_data_product.models.curated import (
    CuratedAllocation,
    CuratedCostReference,
    CuratedModelo,
    CuratedMold,
    CuratedMoldUsage,
    CuratedOrder,
    CuratedOrderPhase,
    CuratedPhaseCapacity,
    CuratedQualityEvent,
    CuratedSkillMatrix,
    QuarantineMixin,
)


# ---------------------------------------------------------------------------
# QuarantineMixin — every curated row carries the same four fields
# ---------------------------------------------------------------------------


def test_quarantine_mixin_applied_to_every_curated_model():
    """All eight curated models must inherit `QuarantineMixin`. The mixin is
    how a bad row is preserved without leaking into queries; losing it on a
    new table would silently bypass the data-quality net."""
    curated_models = [
        CuratedOrder,
        CuratedOrderPhase,
        CuratedPhaseCapacity,
        CuratedMold,
        CuratedMoldUsage,
        CuratedQualityEvent,
        CuratedSkillMatrix,
        CuratedCostReference,
        CuratedAllocation,
        CuratedModelo,
    ]
    for model in curated_models:
        assert issubclass(model, QuarantineMixin), (
            f"{model.__name__} must inherit QuarantineMixin"
        )
        # The mixin exposes four mapped columns on the ORM class.
        for attr in (
            "is_quarantined", "quarantine_reason",
            "quarantine_code", "quarantined_at",
        ):
            assert hasattr(model, attr), f"{model.__name__} missing {attr}"


# ---------------------------------------------------------------------------
# CuratedOrder — schema, defaults, business key
# ---------------------------------------------------------------------------


def test_curated_order_instantiation_and_defaults():
    """`CuratedOrder()` should accept the canonical happy-path kwargs and
    fall back to sensible defaults for the optional fields."""
    ingestion = uuid4()
    order = CuratedOrder(
        ingestion_id=ingestion,
        of_id="OF-12345",
        produto_id="PROD-1",
        produto_nome="K1 Vanquish",
        modelo_id="MOD-1",
        data_entrada=date(2026, 1, 1),
        quantidade=1,
        estado="OPEN",
    )
    assert order.of_id == "OF-12345"
    assert order.ingestion_id == ingestion
    assert order.produto_nome == "K1 Vanquish"
    # Optional fields default to None until set explicitly.
    assert order.data_conclusao is None
    assert order.quantidade_produzida is None
    # Quarantine mixin defaults — unset on a fresh instance, populated by
    # Base.metadata on flush. The class attribute should still be present.
    assert hasattr(order, "is_quarantined")
    assert hasattr(order, "quarantine_reason")


def test_curated_order_table_args_carry_business_key_guard():
    """Onda 5.5 guard: `of_id <> ''` must be in the table's CHECK constraints
    so that a transformer regression cannot insert empty business keys."""
    # __table_args__ is a tuple ending in the schema dict.
    args = CuratedOrder.__table_args__
    assert isinstance(args, tuple)
    assert args[-1] == {"schema": "factory_curated"}
    check_names = [
        getattr(c, "name", None) for c in args
        if hasattr(c, "name")
    ]
    # SQLAlchemy auto-prefixes CHECK names with `ck_<tablename>_` — use a
    # substring assertion so a naming-convention tweak doesn't break the
    # invariant the test is actually pinning.
    assert any(
        "ck_curated_order_of_id_nonempty" in (n or "") for n in check_names
    )
    # Uniqueness on (ingestion_id, of_id) is what stops dupes per ingest.
    assert "uq_curated_order_ingestion_of_id" in check_names


# ---------------------------------------------------------------------------
# CuratedOrderPhase — composite business key, hours columns
# ---------------------------------------------------------------------------


def test_curated_order_phase_carries_hours_and_dates():
    """The order-phase row holds the per-fase timing the projection/backlog
    code reads — `horas_previstas`, `horas_reais`, `horas_finais`."""
    phase = CuratedOrderPhase(
        ingestion_id=uuid4(),
        of_id="OF-12345",
        fase_id="FASE-7",
        fase_nome="Laminagem",
        horas_previstas=Decimal("8.50"),
        horas_reais=Decimal("9.25"),
        horas_finais=Decimal("9.25"),
        estado="OPEN",
        data_inicio=date(2026, 1, 2),
        ordem=1,
        molde_id="MOLD-3",
    )
    assert phase.of_id == "OF-12345"
    assert phase.fase_id == "FASE-7"
    assert phase.fase_nome == "Laminagem"
    assert phase.horas_previstas == Decimal("8.50")
    assert phase.horas_reais == Decimal("9.25")
    assert phase.data_fim is None  # phase still open
    assert phase.molde_id == "MOLD-3"


def test_curated_order_phase_unique_constraint_on_ingestion_of_fase():
    """Composite uniqueness `(ingestion_id, of_id, fase_id)` is what guards
    against duplicate phase rows per ingest run — pin the constraint name."""
    args = CuratedOrderPhase.__table_args__
    assert args[-1] == {"schema": "factory_curated"}
    names = [getattr(c, "name", None) for c in args if hasattr(c, "name")]
    assert "uq_curated_order_phase_ingestion_of_fase" in names
    # CHECK names are auto-prefixed `ck_<tablename>_...`; substring match
    # is the stable assertion.
    assert any(
        "ck_curated_order_phase_of_id_nonempty" in (n or "") for n in names
    )
    assert any(
        "ck_curated_order_phase_fase_id_nonempty" in (n or "") for n in names
    )


# ---------------------------------------------------------------------------
# CuratedMold + CuratedPhaseCapacity — defaults and shape
# ---------------------------------------------------------------------------


def test_curated_mold_em_manutencao_defaults_false():
    """A freshly-instantiated mold is NOT in maintenance. The factory map
    snapshot's `molds_summary` relies on this boolean: a `None` here would
    poison the active/maintenance count."""
    mold = CuratedMold(
        ingestion_id=uuid4(),
        molde_id="MOLD-001",
        molde_nome="Casco K1",
    )
    # `em_manutencao` is mapped with default=False at the column level —
    # the ORM only populates it on flush, but the column default exists.
    column = CuratedMold.__table__.c.em_manutencao
    assert column.default.arg is False
    assert column.nullable is False


def test_curated_phase_capacity_holds_capacity_in_hours():
    """`capacidade_horas` is what `bottlenecks_from_db` divides backlog by."""
    cap = CuratedPhaseCapacity(
        ingestion_id=uuid4(),
        fase_id="FASE-7",
        fase_nome="Laminagem",
        periodo=date(2026, 1, 1),
        periodo_tipo="month",
        capacidade_horas=Decimal("176.00"),
        funcionarios_count=12,
    )
    assert cap.fase_id == "FASE-7"
    assert cap.capacidade_horas == Decimal("176.00")
    assert cap.funcionarios_count == 12


# ---------------------------------------------------------------------------
# CuratedQualityEvent + CuratedSkillMatrix — PII / quality rows
# ---------------------------------------------------------------------------


def test_curated_quality_event_quantidade_defaults_to_one():
    """Each row of `quality_event` is one non-conformance unless otherwise
    stated. The `quantidade` column carries default=1 — the in-memory
    semantic `get_quality` falls back to that for `e.get("quantidade", 1)`."""
    column = CuratedQualityEvent.__table__.c.quantidade
    assert column.default.arg == 1
    assert column.nullable is False
    # Smoke: instantiate with the required keys.
    evt = CuratedQualityEvent(
        ingestion_id=uuid4(),
        of_id="OF-1",
        erro_tipo="DENT",
    )
    assert evt.erro_tipo == "DENT"
    assert evt.fase_id is None


def test_curated_skill_matrix_apto_defaults_false():
    """`apto` defaulting to False means an empty skill row does NOT count
    as a capable employee — `get_skills_risk` filters on `s.get("apto")`,
    so a `None` would silently inflate capability."""
    column = CuratedSkillMatrix.__table__.c.apto
    assert column.default.arg is False
    assert column.nullable is False
    skill = CuratedSkillMatrix(
        ingestion_id=uuid4(),
        funcionario_id="EMP-42",
        fase_id="FASE-7",
        nivel=3,
    )
    assert skill.funcionario_id == "EMP-42"
    assert skill.fase_id == "FASE-7"
    assert skill.nivel == 3


# ---------------------------------------------------------------------------
# CuratedAllocation + CuratedModelo — newer Q.8 tables
# ---------------------------------------------------------------------------


def test_curated_allocation_is_chefe_defaults_false_and_composite_index():
    """`CuratedAllocation` mirrors the historical pair-rate sheet. The
    `is_chefe` column defaults to False; the composite index on
    (fase_of_id, funcionario_id) is what makes the worker-history lookup
    cheap."""
    column = CuratedAllocation.__table__.c.is_chefe
    assert column.default.arg is False
    assert column.nullable is False

    args = CuratedAllocation.__table_args__
    assert args[-1] == {"schema": "factory_curated"}
    names = [getattr(c, "name", None) for c in args if hasattr(c, "name")]
    assert "ix_curated_allocation_composite" in names


def test_curated_modelo_holds_optional_physical_attributes():
    """`CuratedModelo` (the product / catalogue row) carries optional
    physical attributes used by planners and quality. Defaults are all
    NULL — nothing here is required beyond the business key."""
    modelo = CuratedModelo(
        ingestion_id=uuid4(),
        produto_id="PROD-1",
        produto_nome="K1 Vanquish",
        modelo_id="MOD-1",
        tamanho_id="L",
        peso_desmolde_kg=Decimal("12.500"),
    )
    assert modelo.produto_id == "PROD-1"
    assert modelo.peso_desmolde_kg == Decimal("12.500")
    # Unset optional attributes default to None.
    assert modelo.qtd_gel_deck is None
    assert modelo.qtd_gel_casco is None
    assert modelo.numero_pocos_id is None


# ---------------------------------------------------------------------------
# CuratedCostReference + CuratedMoldUsage — sanity smoke
# ---------------------------------------------------------------------------


def test_curated_cost_reference_currency_defaults_to_eur():
    """The cost reference table is deprecated but its `moeda` column still
    defaults to "EUR" — a foreign currency leaking in would mis-cost €/h."""
    column = CuratedCostReference.__table__.c.moeda
    assert column.default.arg == "EUR"
    assert column.nullable is False

    cost = CuratedCostReference(
        ingestion_id=uuid4(),
        centro_custo="CC-1",
        valor_hora_eur=Decimal("15.50"),
    )
    assert cost.centro_custo == "CC-1"
    assert cost.valor_hora_eur == Decimal("15.50")


def test_curated_mold_usage_holds_composite_business_key():
    """`CuratedMoldUsage` carries (molde_id, of_id) as the link; `fase_id`
    is optional because some legacy rows lack it."""
    usage = CuratedMoldUsage(
        ingestion_id=uuid4(),
        molde_id="MOLD-001",
        of_id="OF-12345",
        fase_id=None,
        data_uso=date(2026, 1, 5),
    )
    assert usage.molde_id == "MOLD-001"
    assert usage.of_id == "OF-12345"
    assert usage.fase_id is None
    # Table indexed on molde_id and of_id separately for both lookup
    # directions.
    args = CuratedMoldUsage.__table_args__
    assert args[-1] == {"schema": "factory_curated"}
    names = [getattr(c, "name", None) for c in args if hasattr(c, "name")]
    assert "ix_curated_mold_usage_molde" in names
    assert "ix_curated_mold_usage_of" in names
