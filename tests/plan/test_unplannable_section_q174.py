"""Q.174.F5 — secção "não planeável" (plano parcial declarado).

Decisão do dono (2026-06-12): o plano publica o que é exequível e lista à
parte o que NÃO foi planeável — por op/ordem, com o RECURSO em falta e
sugestões acionáveis. Nunca silêncio, nunca plano falso (invariante #8).

Cobre: captura estruturada no decoder (molde em falta), passagem ao
result-dict (`unplannable`), kpis (`unplannable_count`/`viable`) e o
gerador de sugestões (operadores com histórico fora do pool / molde em
manutenção / horizonte / sem rota).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from src.plan.cpo import op_status
from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.commits import _extract_kpis
from src.plan.cpo.decoder import decode
from src.plan.cpo.state import FactoryState, MoldInfo
from src.plan.cpo.unplannable_suggestions import enrich_unplannable
from src.plan.engines.scheduling_adapter import (
    SchedulingMachine,
    SchedulingOperation,
)

_REF = datetime(2026, 6, 15, 8, 0, 0)


def _op(oid, order, fase="40", *, mold=False, model="M1"):
    return SchedulingOperation(
        operation_id=oid, order_id=order, product_id=model, sequence=1,
        operation_code=fase, duration_minutes=60, machine_id=None,
        phase_id=fase, team_size=1, mold_required=mold, model_id=model,
    )


def _decode(state, ops):
    return decode(
        Chromosome.identity(len(ops)),
        ops,
        [SchedulingMachine(machine_id="M1", name="M1")],
        state,
        horizon_start=_REF,
        horizon_end=_REF + timedelta(days=60),
    )


def test_molde_em_falta_produz_entrada_estruturada():
    state = FactoryState(tenant_id=uuid4())
    state.skill_matrix = {"40": {"w1"}}
    # modelo SEM moldes → op mold_required fica inviável COM razão.
    ops = [_op("A", "OF1", mold=True, model="SEM_MOLDE")]
    result = _decode(state, ops)

    assert result["infeasible_op_ids"] == ["A"]  # back-compat intacto
    unp = result["unplannable"]
    assert len(unp) == 1
    assert unp[0]["status"] == op_status.BLOCKED_MOLDE
    assert unp[0]["order_id"] == "OF1"
    assert unp[0]["missing"]["model_id"] == "SEM_MOLDE"


def test_plano_viavel_tem_unplannable_vazio():
    state = FactoryState(tenant_id=uuid4())
    state.skill_matrix = {"40": {"w1"}}
    result = _decode(state, [_op("A", "OF1")])
    assert result["unplannable"] == []
    kpis = _extract_kpis(result)
    assert kpis["viable"] is True and kpis["unplannable_count"] == 0


def test_kpis_contam_unplannable():
    kpis = _extract_kpis({
        "unplannable": [{"status": op_status.SEM_ROTA}] * 3,
    })
    assert kpis["unplannable_count"] == 3
    assert kpis["viable"] is False


def test_sugestao_operadores_historico_fora_do_pool():
    state = FactoryState(tenant_id=uuid4())
    state.skill_matrix = {"40": {"w1"}}
    # histórico pré-gates tem mais gente — candidatos a reativar/qualificar.
    state.skill_matrix_history = {"40": {"w1", "w7", "w9"}}
    entry = {
        "operation_id": "A", "order_id": "OF1", "phase_id": "40",
        "status": op_status.BLOCKED_OPERADORES,
        "missing": {"needed": 2, "pool_size": 1, "pair_required": True},
    }
    out = enrich_unplannable([entry], state)
    assert "w7" in out[0]["suggestion_pt"] or "w9" in out[0]["suggestion_pt"]
    assert out[0]["label_pt"] == "Sem operadores suficientes"


def test_sugestao_molde_em_manutencao():
    state = FactoryState(tenant_id=uuid4())
    state.molds_by_model = {
        "M9": [MoldInfo(molde_id="70449", modelo_id="M9", em_manutencao=True)],
    }
    entry = {
        "operation_id": "A", "order_id": "OF1", "phase_id": "1",
        "status": op_status.BLOCKED_MOLDE,
        "missing": {"model_id": "M9"},
    }
    out = enrich_unplannable([entry], state)
    assert "70449" in out[0]["suggestion_pt"]
    assert "manutenção" in out[0]["suggestion_pt"]


def test_sugestao_horizonte_calcula_dias():
    entry = {
        "operation_id": "A", "order_id": "OF1", "phase_id": "40",
        "status": op_status.BLOCKED_HORIZONTE,
        "missing": {
            "end_estimado": (_REF + timedelta(days=65)).isoformat(),
            "horizon_end": (_REF + timedelta(days=60)).isoformat(),
        },
    }
    out = enrich_unplannable([entry], FactoryState(tenant_id=uuid4()))
    assert "5 dia" in out[0]["suggestion_pt"]
    assert "OF1" in out[0]["suggestion_pt"]


def test_sugestao_sem_rota_estatica():
    entry = {
        "operation_id": None, "order_id": "OF9", "phase_id": None,
        "status": op_status.SEM_ROTA, "missing": {"reason": "sem_template"},
    }
    out = enrich_unplannable([entry], FactoryState(tenant_id=uuid4()))
    assert "rota" in out[0]["suggestion_pt"].lower()
    assert out[0]["label_pt"] == "Sem rota de produção"
