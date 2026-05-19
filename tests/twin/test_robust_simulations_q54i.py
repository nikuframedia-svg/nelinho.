"""Q.54.I — simulações robustas.

As simulações Twin corriam o auto-solve CP-SAT (Q.53.C) mas eram frágeis:

1. Sem validação de input — aceitavam `capacity_increase_pct` negativo fora
   de gama, `NaN`/`inf`, não-numéricos.
2. `entity_type` desconhecido era ignorado em SILÊNCIO.
3. Estado-base copiado SHALLOW — dicts aninhados mutavam o baseline.

Estes testes verificam que cada um destes buracos está tapado. O solver
CP-SAT é mockado (monkeypatch de `_run_cpsat`) — Q.54.I não testa o solver.
"""

from __future__ import annotations

import copy
import math
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.twin.models import Scenario, ScenarioDelta, ScenarioStatus
from src.twin.service import (
    SUPPORTED_DELTA_ENTITY_TYPES,
    TwinService,
    TwinValidationError,
    validate_delta_patch,
)


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


# ─── Builders ─────────────────────────────────────────────────────────────


def _delta(*, scenario_id: UUID, entity_type: str, patch: dict, seq: int = 0) -> ScenarioDelta:
    return ScenarioDelta(
        id=uuid4(),
        tenant_id=TENANT,
        scenario_id=scenario_id,
        sequence=seq,
        entity_type=entity_type,
        entity_key="A",
        patch=patch,
    )


def _scenario(*, deltas=None, status=None) -> Scenario:
    s = Scenario(
        id=uuid4(),
        tenant_id=TENANT,
        title="cenario",
        description="d",
        status=(status or ScenarioStatus.DRAFT.value),
        baseline_state={
            "backlog_horas_theoretical": {"value": 100.0, "status": "WARNING"},
            "wip_theoretical": {"value": 280, "status": "OK"},
            "skills_at_risk_count": {"value": 5, "status": "WARNING"},
            "quality_errors_total": {"value": 40, "status": "WARNING"},
        },
    )
    s.deltas = list(deltas or [])
    return s


def _db(seeded):
    db = AsyncMock()

    async def _execute(stmt):
        ids = {s.id for s in seeded}
        try:
            params = stmt.compile().params
        except Exception:
            params = {}
        wanted_id = next((v for v in params.values() if v in ids), None)
        hits = [s for s in seeded if wanted_id is None or s.id == wanted_id]

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
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    return db


# ─── validate_delta_patch — unknown entity_type ───────────────────────────


class TestUnknownEntityType:
    def test_unknown_type_rejected_with_supported_list(self):
        with pytest.raises(TwinValidationError) as exc:
            validate_delta_patch("teletransporte", {"x": 1})
        msg = str(exc.value)
        assert "teletransporte" in msg
        # a mensagem lista os tipos suportados, em PT-PT
        assert "suportados" in msg
        for known in SUPPORTED_DELTA_ENTITY_TYPES:
            assert known in msg

    def test_all_supported_types_accepted(self):
        # Nenhum dos tipos suportados levanta erro com patch vazio.
        for et in SUPPORTED_DELTA_ENTITY_TYPES:
            validate_delta_patch(et, {})

    def test_apply_delta_to_state_raises_on_unknown_type(self):
        svc = TwinService(_db([]), TENANT)
        with pytest.raises(TwinValidationError, match="desconhecido"):
            svc._apply_delta_to_state(
                {"wip_theoretical": {"value": 10}},
                {"entity_type": "fase_magica", "patch": {}},
            )


# ─── validate_delta_patch — numeric input validation ──────────────────────


class TestNumericInputValidation:
    def test_negative_percentage_rejected(self):
        with pytest.raises(TwinValidationError, match="percentagem"):
            validate_delta_patch(
                "capacity_adjustment", {"capacity_increase_pct": -150}
            )

    def test_over_100_percentage_rejected(self):
        with pytest.raises(TwinValidationError, match="percentagem"):
            validate_delta_patch(
                "standard_time", {"reduction_pct": 250}
            )

    def test_nan_percentage_rejected(self):
        with pytest.raises(TwinValidationError, match="finito"):
            validate_delta_patch(
                "quality_improvement", {"error_reduction_pct": float("nan")}
            )

    def test_inf_percentage_rejected(self):
        with pytest.raises(TwinValidationError, match="finito"):
            validate_delta_patch(
                "capacity_adjustment", {"capacity_increase_pct": float("inf")}
            )

    def test_non_numeric_percentage_rejected(self):
        with pytest.raises(TwinValidationError, match="finito"):
            validate_delta_patch(
                "capacity_adjustment", {"capacity_increase_pct": "muito"}
            )

    def test_bool_is_not_a_valid_percentage(self):
        # bool é subclasse de int — `True` não é uma percentagem.
        with pytest.raises(TwinValidationError, match="finito"):
            validate_delta_patch(
                "standard_time", {"reduction_pct": True}
            )

    def test_valid_percentage_in_range_accepted(self):
        validate_delta_patch("capacity_adjustment", {"capacity_increase_pct": 15})
        validate_delta_patch("standard_time", {"reduction_pct": 0})
        validate_delta_patch("quality_improvement", {"error_reduction_pct": 100})
        validate_delta_patch("capacity_adjustment", {"capacity_increase_pct": -100})

    def test_negative_count_rejected(self):
        with pytest.raises(TwinValidationError, match="negativo"):
            validate_delta_patch("skills_training", {"phases_trained": -3})
        with pytest.raises(TwinValidationError, match="negativo"):
            validate_delta_patch("wip_policy", {"wip_limit": -1})

    def test_nan_count_rejected(self):
        with pytest.raises(TwinValidationError, match="finito"):
            validate_delta_patch("wip_policy", {"wip_limit": float("nan")})

    def test_valid_count_accepted(self):
        validate_delta_patch("skills_training", {"phases_trained": 2})
        validate_delta_patch("wip_policy", {"wip_limit": 0})

    def test_patch_without_known_keys_is_accepted(self):
        # Um patch sem as chaves numéricas conhecidas passa — não há nada
        # para validar (o `_apply_delta_to_state` simplesmente não faz nada).
        validate_delta_patch("capacity_adjustment", {"comentario": "teste"})


# ─── apply_delta — rejects bad input before persisting ────────────────────


class TestApplyDeltaValidation:
    @pytest.mark.asyncio
    async def test_apply_delta_rejects_unknown_entity_type(self):
        sc = _scenario()
        svc = TwinService(_db([sc]), TENANT)
        with pytest.raises(TwinValidationError, match="desconhecido"):
            await svc.apply_delta(
                scenario_id=sc.id,
                entity_type="coisa_estranha",
                entity_key="A",
                patch={},
            )

    @pytest.mark.asyncio
    async def test_apply_delta_rejects_nan(self):
        sc = _scenario()
        svc = TwinService(_db([sc]), TENANT)
        with pytest.raises(TwinValidationError, match="finito"):
            await svc.apply_delta(
                scenario_id=sc.id,
                entity_type="capacity_adjustment",
                entity_key="A",
                patch={"capacity_increase_pct": float("inf")},
            )

    @pytest.mark.asyncio
    async def test_apply_delta_accepts_valid_delta(self):
        sc = _scenario()
        svc = TwinService(_db([sc]), TENANT)
        delta = await svc.apply_delta(
            scenario_id=sc.id,
            entity_type="capacity_adjustment",
            entity_key="A",
            patch={"capacity_increase_pct": 20},
        )
        assert delta.entity_type == "capacity_adjustment"


# ─── simulate — validates deltas + does not mutate baseline ───────────────


class TestSimulateRobustness:
    @pytest.mark.asyncio
    async def test_simulate_rejects_cloned_unknown_delta(self):
        # Um delta clonado entra pelo construtor sem passar por apply_delta.
        sc = _scenario()
        sc.deltas = [_delta(scenario_id=sc.id, entity_type="invalido", patch={})]
        svc = TwinService(_db([sc]), TENANT)
        with pytest.raises(TwinValidationError, match="desconhecido"):
            await svc.simulate(sc.id)
        # cenário NÃO fica ERROR — é erro de input, fica DRAFT
        assert sc.status == ScenarioStatus.DRAFT.value

    @pytest.mark.asyncio
    async def test_simulate_does_not_mutate_baseline_state(self):
        sc = _scenario()
        sc.deltas = [
            _delta(
                scenario_id=sc.id,
                entity_type="capacity_adjustment",
                patch={"capacity_increase_pct": 50},
            )
        ]
        baseline_before = copy.deepcopy(sc.baseline_state)
        svc = TwinService(_db([sc]), TENANT)
        result = await svc.simulate(sc.id)

        # O baseline_state original NÃO foi tocado (deep copy real).
        assert sc.baseline_state == baseline_before
        assert sc.baseline_state["backlog_horas_theoretical"]["value"] == 100.0
        # O "before" do resultado é o baseline; o "after" mudou.
        assert result["before"]["backlog_horas_theoretical"]["value"] == 100.0
        assert result["after"]["backlog_horas_theoretical"]["value"] == 50.0
        # before e after são objectos independentes
        assert result["before"] is not result["after"]
        assert (
            result["before"]["backlog_horas_theoretical"]
            is not result["after"]["backlog_horas_theoretical"]
        )

    @pytest.mark.asyncio
    async def test_simulate_valid_delta_still_works(self):
        sc = _scenario()
        sc.deltas = [
            _delta(
                scenario_id=sc.id,
                entity_type="quality_improvement",
                patch={"error_reduction_pct": 25},
            )
        ]
        svc = TwinService(_db([sc]), TENANT)
        result = await svc.simulate(sc.id)
        assert result["after"]["quality_errors_total"]["value"] == 30.0  # 40 * 0.75
        assert sc.status == ScenarioStatus.SIMULATED.value


# ─── _calculate_kpi_deltas / _extract_value — non-finite guards ───────────


class TestKpiDeltaEdgeCases:
    def test_extract_value_rejects_nan(self):
        svc = TwinService(_db([]), TENANT)
        assert svc._extract_value({"value": float("nan")}) is None
        assert svc._extract_value(float("inf")) is None

    def test_extract_value_rejects_bool(self):
        svc = TwinService(_db([]), TENANT)
        assert svc._extract_value(True) is None
        assert svc._extract_value({"value": False}) is None

    def test_extract_value_accepts_finite_number(self):
        svc = TwinService(_db([]), TENANT)
        assert svc._extract_value({"value": 12.5}) == 12.5
        assert svc._extract_value(7) == 7.0

    def test_kpi_deltas_skip_non_finite_change(self):
        svc = TwinService(_db([]), TENANT)
        # `after` tem um inf — o delta desse KPI é descartado, não propagado.
        before = {"a": {"value": 10.0}, "b": {"value": 5.0}}
        after = {"a": {"value": float("inf")}, "b": {"value": 8.0}}
        deltas = svc._calculate_kpi_deltas(before, after)
        assert "a_change" not in deltas  # inf descartado
        assert deltas["b_change"] == 3.0

    def test_kpi_deltas_all_finite(self):
        svc = TwinService(_db([]), TENANT)
        before = {"x": {"value": 100.0}}
        after = {"x": {"value": 70.0}}
        deltas = svc._calculate_kpi_deltas(before, after)
        assert deltas["x_change"] == -30.0
        assert math.isfinite(deltas["x_change"])


# ─── solve — deep copy + validation ───────────────────────────────────────


class TestSolveRobustness:
    @pytest.mark.asyncio
    async def test_solve_rejects_unknown_delta(self):
        sc = _scenario()
        sc.deltas = [_delta(scenario_id=sc.id, entity_type="xpto", patch={})]
        svc = TwinService(_db([sc]), TENANT)
        with pytest.raises(TwinValidationError, match="desconhecido"):
            await svc.solve(sc.id)

    @pytest.mark.asyncio
    async def test_solve_does_not_mutate_baseline(self):
        sc = _scenario()
        sc.deltas = [
            _delta(
                scenario_id=sc.id,
                entity_type="standard_time",
                patch={"reduction_pct": 30},
            )
        ]
        baseline_before = copy.deepcopy(sc.baseline_state)
        svc = TwinService(_db([sc]), TENANT)
        out = await svc.solve(sc.id)
        assert out["status"] == "INSUFFICIENT_DATA"
        # baseline intacto
        assert sc.baseline_state == baseline_before
        # mas a projecção aplicou o delta
        assert out["projected_kpis"]["backlog_horas_theoretical"]["value"] == 70.0


# ─── Endpoints — TwinValidationError mapeia para HTTP 422 ─────────────────


class TestApiReturns422:
    def _client(self, service):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.twin.api import (
            get_current_user,
            get_tenant_id,
            get_twin_service,
            router as twin_router,
        )

        app = FastAPI()
        app.include_router(twin_router)
        app.dependency_overrides[get_twin_service] = lambda: service
        app.dependency_overrides[get_tenant_id] = lambda: TENANT
        app.dependency_overrides[get_current_user] = lambda: "tester"
        return TestClient(app)

    def test_apply_delta_invalid_returns_422(self):
        service = AsyncMock()
        service.apply_delta = AsyncMock(
            side_effect=TwinValidationError("entity_type desconhecido: 'x'.")
        )
        client = self._client(service)
        resp = client.post(
            f"/v1/twin/scenarios/{uuid4()}/apply-delta",
            json={"entity_type": "x", "entity_key": "A", "patch": {}},
        )
        assert resp.status_code == 422, resp.text
        assert "desconhecido" in resp.json()["detail"]

    def test_simulate_invalid_delta_returns_422(self):
        service = AsyncMock()
        service.simulate = AsyncMock(
            side_effect=TwinValidationError("capacity_adjustment.capacity_increase_pct tem de ser finito")
        )
        client = self._client(service)
        resp = client.post(f"/v1/twin/scenarios/{uuid4()}/simulate")
        assert resp.status_code == 422, resp.text

    def test_simulate_not_found_still_404(self):
        # Um ValueError "normal" (cenário não existe) continua a dar 404 —
        # só TwinValidationError é que vira 422.
        service = AsyncMock()
        service.simulate = AsyncMock(side_effect=ValueError("Scenario X not found"))
        client = self._client(service)
        resp = client.post(f"/v1/twin/scenarios/{uuid4()}/simulate")
        assert resp.status_code == 404

    def test_solve_invalid_delta_returns_422(self):
        service = AsyncMock()
        service.solve = AsyncMock(
            side_effect=TwinValidationError("entity_type desconhecido")
        )
        client = self._client(service)
        resp = client.post(f"/v1/twin/scenarios/{uuid4()}/solve", json={})
        assert resp.status_code == 422, resp.text
