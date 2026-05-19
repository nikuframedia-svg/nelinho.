"""
Q.37.B — testes do DRY_RUN real via Digital Twin.

Cobertura:
  * `extract_twin_delta` — funções puras DAMP (cada caso lê como spec).
  * `run_dry_run` — com `TwinService` substituído por um fake AsyncMock,
    sem Postgres real (regra do worktree: só testes unitários).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.copilot.dry_run import (
    TWIN_SUPPORTED_ENTITY_TYPES,
    extract_twin_delta,
    run_dry_run,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
USER = UUID("00000000-0000-0000-0000-000000000001")


# ─────────────────────────────────────────────────────────────────────
# extract_twin_delta — funções puras
# ─────────────────────────────────────────────────────────────────────

def test_extract_twin_delta_valido_devolve_delta_normalizado():
    payload = {
        "twin_delta": {
            "entity_type": "capacity_adjustment",
            "entity_key": "fase-laminagem",
            "patch": {"capacity_increase_pct": 10},
            "description": "subir 10% capacidade",
        }
    }
    delta = extract_twin_delta(payload)
    assert delta == {
        "entity_type": "capacity_adjustment",
        "entity_key": "fase-laminagem",
        "patch": {"capacity_increase_pct": 10},
        "description": "subir 10% capacidade",
    }


def test_extract_twin_delta_sem_twin_delta_devolve_none():
    assert extract_twin_delta({}) is None
    assert extract_twin_delta({"twin_delta": None}) is None
    assert extract_twin_delta({"twin_delta": "nao-e-dict"}) is None


def test_extract_twin_delta_patch_vazio_devolve_none():
    payload = {
        "twin_delta": {"entity_type": "wip_policy", "patch": {}}
    }
    assert extract_twin_delta(payload) is None


def test_extract_twin_delta_entity_type_nao_simulavel_devolve_none():
    payload = {
        "twin_delta": {
            "entity_type": "inventar_kpi",
            "patch": {"x": 1},
        }
    }
    assert extract_twin_delta(payload) is None


def test_extract_twin_delta_entity_key_default_para_entity_type():
    payload = {
        "twin_delta": {
            "entity_type": "quality_improvement",
            "patch": {"error_reduction_pct": 5},
        }
    }
    delta = extract_twin_delta(payload)
    assert delta is not None
    assert delta["entity_key"] == "quality_improvement"


def test_todas_entity_types_suportadas_sao_aceites():
    for et in TWIN_SUPPORTED_ENTITY_TYPES:
        delta = extract_twin_delta(
            {"twin_delta": {"entity_type": et, "patch": {"x": 1}}}
        )
        assert delta is not None, et


# ─────────────────────────────────────────────────────────────────────
# run_dry_run — Twin fake
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_dry_run_sem_delta_devolve_insufficient_input():
    """Sem twin_delta mapeável: honesto, não fabrica resultado."""
    result = await run_dry_run(
        payload={"title": "qualquer coisa"},
        tenant_id=TENANT,
        session=AsyncMock(),
        user_id=USER,
    )
    assert result["status"] == "insufficient_input"
    assert result["action_type"] == "DRY_RUN"
    assert "supported_entity_types" in result
    # Não há before/after fabricados.
    assert "after" not in result


@pytest.mark.asyncio
async def test_run_dry_run_com_delta_simula_via_twin(monkeypatch):
    """Com delta válido: cria cenário, aplica delta, simula, compara."""
    scenario = SimpleNamespace(id=uuid4(), scenario_hash="abc123hash")

    fake_twin = AsyncMock()
    fake_twin.create_scenario.return_value = scenario
    fake_twin.apply_delta.return_value = SimpleNamespace(id=uuid4())
    fake_twin.simulate.return_value = {
        "before": {"backlog_horas_theoretical": {"value": 100}},
        "after": {"backlog_horas_theoretical": {"value": 90}},
        "delta_summary": {"backlog_horas_theoretical_change": -10},
    }
    fake_twin.compare.return_value = {
        "comparison": {
            "backlog_horas_theoretical": {
                "baseline": 100, "scenario": 90, "delta": -10,
            }
        }
    }

    def _fake_ctor(db, tenant_id):
        return fake_twin

    monkeypatch.setattr("src.twin.service.TwinService", _fake_ctor)

    result = await run_dry_run(
        payload={
            "twin_delta": {
                "entity_type": "capacity_adjustment",
                "entity_key": "fase-laminagem",
                "patch": {"capacity_increase_pct": 10},
            }
        },
        tenant_id=TENANT,
        session=AsyncMock(),
        user_id=USER,
    )

    assert result["status"] == "simulated"
    assert result["scenario_hash"] == "abc123hash"
    assert result["before"] == {"backlog_horas_theoretical": {"value": 100}}
    assert result["after"] == {"backlog_horas_theoretical": {"value": 90}}
    assert result["delta_summary"]["backlog_horas_theoretical_change"] == -10
    assert result["applied_delta"]["entity_type"] == "capacity_adjustment"
    # O cenário foi mesmo criado/simulado/comparado.
    fake_twin.create_scenario.assert_awaited_once()
    fake_twin.apply_delta.assert_awaited_once()
    fake_twin.simulate.assert_awaited_once()
    fake_twin.compare.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_dry_run_value_error_do_twin_e_insufficient_input(monkeypatch):
    """ValueError do Twin (delta inválido) → insufficient_input, não 500."""
    fake_twin = AsyncMock()
    fake_twin.create_scenario.side_effect = ValueError("baseline em falta")

    monkeypatch.setattr(
        "src.twin.service.TwinService", lambda db, tenant_id: fake_twin
    )

    result = await run_dry_run(
        payload={
            "twin_delta": {
                "entity_type": "wip_policy",
                "patch": {"wip_limit": 5},
            }
        },
        tenant_id=TENANT,
        session=AsyncMock(),
        user_id=USER,
    )
    assert result["status"] == "insufficient_input"
    assert "baseline em falta" in result["message"]


@pytest.mark.asyncio
async def test_run_dry_run_erro_inesperado_devolve_status_error(monkeypatch):
    """Erro inesperado do Twin → status='error' explícito, não eco."""
    fake_twin = AsyncMock()
    fake_twin.create_scenario.side_effect = RuntimeError("twin offline")

    monkeypatch.setattr(
        "src.twin.service.TwinService", lambda db, tenant_id: fake_twin
    )

    result = await run_dry_run(
        payload={
            "twin_delta": {
                "entity_type": "standard_time",
                "patch": {"reduction_pct": 8},
            }
        },
        tenant_id=TENANT,
        session=AsyncMock(),
        user_id=USER,
    )
    assert result["status"] == "error"
    assert "twin offline" in result["message"]
