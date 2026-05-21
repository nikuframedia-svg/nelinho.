"""Q.67.6.A1 - Characterization tests para TwinService.

**Pattern Feathers (Working Effectively with Legacy Code):** antes de
decompor o god-file `src/twin/service.py` (1192L) em Fase B (Q.67.6.B1),
pinamos o behaviour observavel ACTUAL como snapshots. Estes testes NAO
assertam "o que devia acontecer" - assertam "o que acontece hoje". Se a
decomposicao partir alguma destas assercoes sem decisao deliberada, e
regressao.

Cobertura (por funcao publica + metodos publicos):

Funcoes modulo-nivel:
  * validate_delta_patch: entity_type unknown raise; percentagens fora de
    [-100, 100] raise; NaN/inf raise; bool raise; happy path noop.
  * _is_finite_number: bool rejeitado, NaN/inf rejeitado, int/float ok.

TwinService:
  * __init__: guarda db e tenant_id.
  * create_scenario: flush + commit + refresh + add + return Scenario.
  * create_scenario com base_scenario_id: clona deltas.
  * get_scenario: scalar_one_or_none.
  * list_scenarios: query + scalars().all().
  * delete_scenario: True quando existe, False quando nao.
  * apply_delta: cria delta com sequence+1, reset status to DRAFT.
  * apply_delta: raise se scenario nao existe.
  * apply_delta: raise se status nao DRAFT/SIMULATED.
  * apply_delta: TwinValidationError se entity_type unknown.
  * _apply_delta_to_state: capacity_adjustment, standard_time,
    skills_training, quality_improvement, wip_policy.
  * _apply_delta_to_state: entity_type unknown raise.
  * _calculate_kpi_deltas: extrai diffs, filtra _metadata, descarta inf.
  * _extract_value: dict com value, int/float, None, bool, NaN, BLOCKED.
  * _calculate_state_hash: deterministico, ignora _metadata.
  * _calculate_scenario_hash: deterministico, depende de baseline+deltas.
  * _calculate_result_hash: ""  quando falta after, hash quando ok.
  * _extract_scheduling_input: None quando ausente, tuple quando ok.
  * scenario_to_dict: shape estavel.
  * get_audit_hashes: 4 hashes + short forms + algorithm.

Nao-testavel sem stack pesado (excluido com razao):
  * simulate, solve, _run_cpsat: chamam SchedulingAdapter / Factory
    Data Product semantic layer / asyncio.to_thread. Cobertos por
    test_service.py + test_auto_solver_q53c.py + test_baseline_real_q56b.py.
  * _governance_baseline_metrics, _create_baseline_state: importam
    src.plan.* / src.quality.* / src.factory_data_product.*. Cobertos por
    test_baseline_real_q56b.py.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.twin.models import Scenario, ScenarioDelta, ScenarioStatus
from src.twin.service import (
    SUPPORTED_DELTA_ENTITY_TYPES,
    TwinService,
    TwinValidationError,
    _is_finite_number,
    validate_delta_patch,
)


# pytest.ini ja tem `asyncio_mode = auto` - nao precisamos de marker global.

TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scenario(
    *,
    tenant_id: UUID = TENANT,
    status: str = ScenarioStatus.DRAFT.value,
    baseline: Optional[Dict[str, Any]] = None,
    deltas: Optional[List[ScenarioDelta]] = None,
) -> Scenario:
    s = Scenario(
        id=uuid4(),
        tenant_id=tenant_id,
        title="t",
        description="d",
        status=status,
        baseline_state=baseline if baseline is not None else {
            "wip_theoretical": {"value": 100, "status": "OK"},
            "backlog_horas_theoretical": {"value": 200.0, "status": "OK"},
            "skills_at_risk_count": {"value": 5, "status": "OK"},
            "quality_errors_total": {"value": 50, "status": "OK"},
        },
    )
    s.deltas = list(deltas or [])
    return s


def _make_delta(
    *,
    sequence: int = 0,
    entity_type: str = "capacity_adjustment",
    entity_key: str = "factory",
    patch: Optional[Dict[str, Any]] = None,
) -> ScenarioDelta:
    return ScenarioDelta(
        id=uuid4(),
        tenant_id=TENANT,
        scenario_id=uuid4(),
        sequence=sequence,
        entity_type=entity_type,
        entity_key=entity_key,
        patch=patch if patch is not None else {"capacity_increase_pct": 10},
        description=None,
        applied_by=None,
    )


def _stub_db(seeded: List[Scenario]):
    """session.execute() stub que filtra por tenant + id como SQLAlchemy."""
    db = AsyncMock()

    async def _execute(stmt):
        try:
            params = stmt.compile().params
        except Exception:
            params = {}

        wanted_tenant = None
        wanted_id = None
        wanted_status = None
        for v in params.values():
            if isinstance(v, UUID):
                if wanted_tenant is None:
                    wanted_tenant = v
                else:
                    wanted_id = v
            elif isinstance(v, str):
                wanted_status = v

        ids = {s.id for s in seeded}
        if wanted_tenant in ids:
            wanted_id, wanted_tenant = wanted_tenant, wanted_id

        hits = [
            s for s in seeded
            if (wanted_tenant is None or s.tenant_id == wanted_tenant)
            and (wanted_id is None or s.id == wanted_id)
            and (wanted_status is None or s.status == wanted_status)
        ]

        class _Result:
            def scalar_one_or_none(self_):
                return hits[0] if hits else None

            def scalars(self_):
                class _S:
                    def all(_self):
                        return list(hits)
                return _S()

        return _Result()

    db.execute = _execute
    db.add = lambda obj: None
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ===========================================================================
# Funcoes modulo-nivel
# ===========================================================================

def test_is_finite_number_rejects_bool_q67_a1():
    """`bool` e subclasse de int, mas nao e uma metrica - rejeitado."""
    assert _is_finite_number(True) is False
    assert _is_finite_number(False) is False


def test_is_finite_number_rejects_nan_inf_q67_a1():
    assert _is_finite_number(float("nan")) is False
    assert _is_finite_number(float("inf")) is False
    assert _is_finite_number(float("-inf")) is False


def test_is_finite_number_accepts_int_float_q67_a1():
    assert _is_finite_number(0) is True
    assert _is_finite_number(-50) is True
    assert _is_finite_number(3.14) is True


def test_validate_delta_patch_unknown_entity_type_raises_q67_a1():
    with pytest.raises(TwinValidationError, match="entity_type desconhecido"):
        validate_delta_patch("not_a_real_type", {"foo": 1})


def test_validate_delta_patch_percentage_out_of_range_raises_q67_a1():
    with pytest.raises(TwinValidationError, match="percentagem entre"):
        validate_delta_patch("capacity_adjustment", {"capacity_increase_pct": 150})
    with pytest.raises(TwinValidationError, match="percentagem entre"):
        validate_delta_patch("standard_time", {"reduction_pct": -200})


def test_validate_delta_patch_nan_raises_q67_a1():
    # PT-PT source: "tem de ser um número finito" - usamos substring sem
    # diacriticos para evitar lidar com encoding entre OS.
    with pytest.raises(TwinValidationError, match="finito"):
        validate_delta_patch(
            "quality_improvement", {"error_reduction_pct": float("nan")}
        )


def test_validate_delta_patch_negative_count_raises_q67_a1():
    with pytest.raises(TwinValidationError, match="negativo"):
        validate_delta_patch("skills_training", {"phases_trained": -5})
    with pytest.raises(TwinValidationError, match="negativo"):
        validate_delta_patch("wip_policy", {"wip_limit": -1})


def test_validate_delta_patch_happy_path_q67_a1():
    """Passa silenciosamente quando tudo esta em ordem."""
    validate_delta_patch("capacity_adjustment", {"capacity_increase_pct": 10})
    validate_delta_patch("scheduling_input", {"operations": [], "machines": []})
    validate_delta_patch("skills_training", {"phases_trained": 3})


def test_supported_delta_entity_types_snapshot_q67_a1():
    """Pin o conjunto de entity_types suportados. Adicionar um e mudanca
    intencional - este teste falha e forca o autor a actualizar."""
    assert SUPPORTED_DELTA_ENTITY_TYPES == (
        "capacity_adjustment",
        "standard_time",
        "skills_training",
        "quality_improvement",
        "wip_policy",
        "scheduling_input",
    )


# ===========================================================================
# TwinService - construtor
# ===========================================================================

def test_init_stores_db_and_tenant_q67_a1():
    db = AsyncMock()
    svc = TwinService(db, TENANT)
    assert svc.db is db
    assert svc.tenant_id == TENANT


# ===========================================================================
# get_scenario / list_scenarios / delete_scenario
# ===========================================================================

async def test_get_scenario_returns_match_q67_a1():
    sc = _make_scenario()
    db = _stub_db([sc])
    svc = TwinService(db, TENANT)
    result = await svc.get_scenario(sc.id)
    assert result is sc


async def test_get_scenario_returns_none_when_missing_q67_a1():
    db = _stub_db([])
    svc = TwinService(db, TENANT)
    result = await svc.get_scenario(uuid4())
    assert result is None


async def test_list_scenarios_returns_list_q67_a1():
    sc1 = _make_scenario()
    sc2 = _make_scenario()
    db = _stub_db([sc1, sc2])
    svc = TwinService(db, TENANT)
    result = await svc.list_scenarios()
    assert isinstance(result, list)
    assert len(result) == 2


async def test_delete_scenario_returns_true_when_exists_q67_a1():
    sc = _make_scenario()
    db = _stub_db([sc])
    svc = TwinService(db, TENANT)
    result = await svc.delete_scenario(sc.id)
    assert result is True
    db.delete.assert_awaited_once()
    db.commit.assert_awaited()


async def test_delete_scenario_returns_false_when_missing_q67_a1():
    db = _stub_db([])
    svc = TwinService(db, TENANT)
    result = await svc.delete_scenario(uuid4())
    assert result is False
    db.delete.assert_not_called()


# ===========================================================================
# apply_delta
# ===========================================================================

async def test_apply_delta_raises_when_scenario_missing_q67_a1():
    db = _stub_db([])
    svc = TwinService(db, TENANT)
    with pytest.raises(ValueError, match="not found"):
        await svc.apply_delta(
            uuid4(), "capacity_adjustment", "factory",
            {"capacity_increase_pct": 10}
        )


async def test_apply_delta_raises_when_wrong_status_q67_a1():
    sc = _make_scenario(status=ScenarioStatus.PUBLISHED.value)
    db = _stub_db([sc])
    svc = TwinService(db, TENANT)
    with pytest.raises(ValueError, match="Cannot apply delta"):
        await svc.apply_delta(
            sc.id, "capacity_adjustment", "factory",
            {"capacity_increase_pct": 10}
        )


async def test_apply_delta_validates_patch_q67_a1():
    """validate_delta_patch corre ANTES de persistir - patch invalido raise."""
    sc = _make_scenario()
    db = _stub_db([sc])
    svc = TwinService(db, TENANT)
    with pytest.raises(TwinValidationError):
        await svc.apply_delta(
            sc.id, "not_a_real_type", "factory", {"foo": 1}
        )


async def test_apply_delta_resets_status_to_draft_q67_a1():
    """Aplicar delta sobre SIMULATED limpa simulation_result + scenario_hash
    e volta a DRAFT."""
    sc = _make_scenario(status=ScenarioStatus.SIMULATED.value)
    sc.simulation_result = {"before": {}, "after": {}}
    sc.scenario_hash = "old_hash"
    db = _stub_db([sc])
    svc = TwinService(db, TENANT)
    await svc.apply_delta(
        sc.id, "capacity_adjustment", "factory",
        {"capacity_increase_pct": 10}
    )
    assert sc.status == ScenarioStatus.DRAFT.value
    assert sc.simulation_result is None
    assert sc.scenario_hash is None


# ===========================================================================
# _apply_delta_to_state - aplicacao por entity_type
# ===========================================================================

def test_apply_delta_capacity_adjustment_reduces_backlog_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    state = {"backlog_horas_theoretical": {"value": 100.0, "status": "OK"}}
    result = svc._apply_delta_to_state(state, {
        "entity_type": "capacity_adjustment",
        "patch": {"capacity_increase_pct": 20},
    })
    assert result["backlog_horas_theoretical"]["value"] == pytest.approx(80.0)
    # Snapshot: nao muta o input (deepcopy)
    assert state["backlog_horas_theoretical"]["value"] == 100.0


def test_apply_delta_standard_time_reduces_backlog_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    state = {"backlog_horas_theoretical": {"value": 200.0, "status": "OK"}}
    result = svc._apply_delta_to_state(state, {
        "entity_type": "standard_time",
        "patch": {"reduction_pct": 10},
    })
    assert result["backlog_horas_theoretical"]["value"] == pytest.approx(180.0)


def test_apply_delta_skills_training_reduces_at_risk_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    state = {"skills_at_risk_count": {"value": 10, "status": "OK"}}
    result = svc._apply_delta_to_state(state, {
        "entity_type": "skills_training",
        "patch": {"phases_trained": 3},
    })
    assert result["skills_at_risk_count"]["value"] == 7


def test_apply_delta_skills_training_floors_at_zero_q67_a1():
    """phases_trained > current value -> 0, nunca negativo."""
    svc = TwinService(AsyncMock(), TENANT)
    state = {"skills_at_risk_count": {"value": 2, "status": "OK"}}
    result = svc._apply_delta_to_state(state, {
        "entity_type": "skills_training",
        "patch": {"phases_trained": 50},
    })
    assert result["skills_at_risk_count"]["value"] == 0


def test_apply_delta_quality_improvement_reduces_errors_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    state = {"quality_errors_total": {"value": 100, "status": "OK"}}
    result = svc._apply_delta_to_state(state, {
        "entity_type": "quality_improvement",
        "patch": {"error_reduction_pct": 25},
    })
    assert result["quality_errors_total"]["value"] == pytest.approx(75.0)


def test_apply_delta_wip_policy_caps_wip_q67_a1():
    """wip_limit aplica min(current, limit) - so reduz."""
    svc = TwinService(AsyncMock(), TENANT)
    state = {"wip_theoretical": {"value": 100, "status": "OK"}}
    # limit abaixo de current
    result_lower = svc._apply_delta_to_state(state, {
        "entity_type": "wip_policy",
        "patch": {"wip_limit": 50},
    })
    assert result_lower["wip_theoretical"]["value"] == 50
    # limit acima de current - nao altera (min)
    result_higher = svc._apply_delta_to_state(state, {
        "entity_type": "wip_policy",
        "patch": {"wip_limit": 200},
    })
    assert result_higher["wip_theoretical"]["value"] == 100


def test_apply_delta_unknown_entity_type_raises_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    with pytest.raises(TwinValidationError, match="entity_type desconhecido"):
        svc._apply_delta_to_state({}, {
            "entity_type": "not_a_real_type",
            "patch": {},
        })


# ===========================================================================
# _extract_value - normalizacao numerica
# ===========================================================================

def test_extract_value_from_dict_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    assert svc._extract_value({"value": 42, "status": "OK"}) == 42.0
    assert svc._extract_value({"value": 3.14, "status": "OK"}) == pytest.approx(3.14)


def test_extract_value_from_dict_with_blocked_returns_none_q67_a1():
    """status=BLOCKED esconde o value mesmo que seja numerico."""
    svc = TwinService(AsyncMock(), TENANT)
    assert svc._extract_value({"value": 0.85, "status": "BLOCKED"}) is None


def test_extract_value_rejects_bool_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    assert svc._extract_value(True) is None
    assert svc._extract_value({"value": True, "status": "OK"}) is None


def test_extract_value_rejects_nan_inf_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    assert svc._extract_value(float("nan")) is None
    assert svc._extract_value({"value": float("inf"), "status": "OK"}) is None


def test_extract_value_handles_raw_number_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    assert svc._extract_value(42) == 42.0
    assert svc._extract_value(None) is None


# ===========================================================================
# _calculate_kpi_deltas
# ===========================================================================

def test_calculate_kpi_deltas_pins_diff_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    before = {"wip": {"value": 100, "status": "OK"}}
    after = {"wip": {"value": 80, "status": "OK"}}
    result = svc._calculate_kpi_deltas(before, after)
    assert result == {"wip_change": -20.0}


def test_calculate_kpi_deltas_skips_metadata_q67_a1():
    """Chaves com prefixo `_` sao ignoradas (e.g. `_metadata`)."""
    svc = TwinService(AsyncMock(), TENANT)
    before = {"_metadata": {"value": "foo"}, "wip": {"value": 10, "status": "OK"}}
    after = {"_metadata": {"value": "bar"}, "wip": {"value": 5, "status": "OK"}}
    result = svc._calculate_kpi_deltas(before, after)
    assert "_metadata_change" not in result
    assert result["wip_change"] == -5.0


def test_calculate_kpi_deltas_drops_non_finite_q67_a1():
    """Diferenca nao-finita (inf/NaN) e descartada do resumo."""
    svc = TwinService(AsyncMock(), TENANT)
    before = {"wip": {"value": float("inf"), "status": "OK"}}
    after = {"wip": {"value": 100, "status": "OK"}}
    result = svc._calculate_kpi_deltas(before, after)
    # _extract_value devolve None para inf, por isso o par e ignorado
    assert "wip_change" not in result


# ===========================================================================
# Hashing - reproducibilidade
# ===========================================================================

def test_calculate_state_hash_is_deterministic_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    state = {"wip": {"value": 10}, "backlog": {"value": 5}}
    h1 = svc._calculate_state_hash(state)
    h2 = svc._calculate_state_hash(dict(state))
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_calculate_state_hash_ignores_metadata_q67_a1():
    """Chaves `_*` + `generated_at` + `computed_at` nao afectam o hash."""
    svc = TwinService(AsyncMock(), TENANT)
    state_a = {"wip": {"value": 10}, "_metadata": {"a": 1}}
    state_b = {"wip": {"value": 10}, "_metadata": {"a": 2}, "generated_at": "now"}
    assert svc._calculate_state_hash(state_a) == svc._calculate_state_hash(state_b)


def test_calculate_state_hash_changes_with_value_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    h1 = svc._calculate_state_hash({"wip": {"value": 10}})
    h2 = svc._calculate_state_hash({"wip": {"value": 11}})
    assert h1 != h2


def test_calculate_scenario_hash_depends_on_deltas_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    sc1 = _make_scenario(deltas=[])
    sc2 = _make_scenario(deltas=[_make_delta()])
    # Same baseline_state structure but diff deltas -> diff hash.
    sc2.baseline_state = sc1.baseline_state
    assert svc._calculate_scenario_hash(sc1) != svc._calculate_scenario_hash(sc2)


def test_calculate_result_hash_empty_when_no_after_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    assert svc._calculate_result_hash({}) == ""
    assert svc._calculate_result_hash({"before": {}}) == ""


def test_calculate_result_hash_hashes_after_state_q67_a1():
    svc = TwinService(AsyncMock(), TENANT)
    result = svc._calculate_result_hash({"after": {"wip": {"value": 5}}})
    assert len(result) == 64


# ===========================================================================
# _extract_scheduling_input
# ===========================================================================

def test_extract_scheduling_input_none_when_no_delta_q67_a1():
    sc = _make_scenario(deltas=[])
    assert TwinService._extract_scheduling_input(sc) is None


def test_extract_scheduling_input_none_when_other_types_q67_a1():
    sc = _make_scenario(deltas=[_make_delta(entity_type="capacity_adjustment")])
    assert TwinService._extract_scheduling_input(sc) is None


def test_extract_scheduling_input_returns_tuple_q67_a1():
    operations = [{"operation_id": "op1", "order_id": "o1", "duration_minutes": 60}]
    machines = [{"machine_id": "m1"}]
    sc = _make_scenario(deltas=[_make_delta(
        entity_type="scheduling_input",
        patch={"operations": operations, "machines": machines},
    )])
    result = TwinService._extract_scheduling_input(sc)
    assert result is not None
    ops, machs = result
    assert ops == operations
    assert machs == machines


def test_extract_scheduling_input_last_wins_q67_a1():
    """Multiplos scheduling_input deltas - o de maior sequence ganha."""
    early = _make_delta(
        sequence=0,
        entity_type="scheduling_input",
        patch={"operations": [{"id": "old"}], "machines": [{"id": "m_old"}]},
    )
    late = _make_delta(
        sequence=1,
        entity_type="scheduling_input",
        patch={"operations": [{"id": "new"}], "machines": [{"id": "m_new"}]},
    )
    sc = _make_scenario(deltas=[early, late])
    ops, _ = TwinService._extract_scheduling_input(sc)
    assert ops == [{"id": "new"}]


# ===========================================================================
# scenario_to_dict / get_audit_hashes - serializacao
# ===========================================================================

def test_scenario_to_dict_shape_q67_a1():
    sc = _make_scenario()
    sc.created_at = None
    sc.updated_at = None
    sc.simulated_at = None
    result = TwinService.scenario_to_dict(sc)
    expected_keys = {
        "id", "tenant_id", "title", "description", "status",
        "base_scenario_id", "baseline_state", "simulation_result",
        "scenario_hash", "created_by", "created_at", "updated_at",
        "simulated_at", "deltas",
    }
    assert set(result.keys()) == expected_keys
    assert result["id"] == str(sc.id)
    assert result["tenant_id"] == str(sc.tenant_id)
    assert result["deltas"] == []


def test_scenario_to_dict_serializes_deltas_q67_a1():
    delta = _make_delta(sequence=2, entity_key="phase_42")
    delta.created_at = None
    sc = _make_scenario(deltas=[delta])
    sc.created_at = None
    sc.updated_at = None
    sc.simulated_at = None
    result = TwinService.scenario_to_dict(sc)
    assert len(result["deltas"]) == 1
    d = result["deltas"][0]
    assert d["sequence"] == 2
    assert d["entity_key"] == "phase_42"
    assert d["entity_type"] == "capacity_adjustment"


def test_get_audit_hashes_returns_4_hashes_q67_a1():
    sc = _make_scenario()
    svc = TwinService(AsyncMock(), TENANT)
    result = svc.get_audit_hashes(sc)
    # 4 hashes esperados + algorithm + is_reproducible
    assert "baseline_hash" in result
    assert "baseline_hash_full" in result
    assert "deltas_hash" in result
    assert "deltas_hash_full" in result
    assert "scenario_hash" in result
    assert "scenario_hash_full" in result
    assert "result_hash" in result
    assert result["algorithm"] == "sha256"
    assert result["is_reproducible"] is True
    # Short forms tem 16 chars; full tem 64
    assert len(result["baseline_hash"]) == 16
    assert len(result["baseline_hash_full"]) == 64


def test_get_audit_hashes_result_hash_none_without_simulation_q67_a1():
    sc = _make_scenario()
    sc.simulation_result = None
    svc = TwinService(AsyncMock(), TENANT)
    result = svc.get_audit_hashes(sc)
    assert result["result_hash"] is None
    assert result["result_hash_full"] is None
