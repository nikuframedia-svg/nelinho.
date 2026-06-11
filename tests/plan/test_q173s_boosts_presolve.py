"""Q.173.S — boosts pré-solve influenciam a ORDEM do plano.

A auditoria 2026-06-11 provou que os boosts (prioridade de cliente/ordem/
barco) eram recolhidos PÓS-solve em scheduler_run e serviam só de badge no
frontend — nenhum call-site de produção passava `boost_inputs` ao decode
(o suporte existia desde Q.116.D, decoder_resources reordena o
priority_order). Agora o snapshot é recolhido antes do solve e propaga por
engine.schedule → GreedyPipeline/decode (caminhos greedy + GA).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import (
    SchedulingMachine,
    SchedulingOperation,
)

_H0 = datetime(2026, 6, 1, 0, 0, 0)
_HE = _H0 + timedelta(days=30)


def _state() -> FactoryState:
    s = FactoryState(tenant_id=uuid4())
    s.phase_stations = {"A": 1}          # 1 estação → as ordens competem
    s.skill_matrix = {"A": {"w1"}}       # 1 operador qualificado
    return s


def _ops() -> list[SchedulingOperation]:
    return [
        SchedulingOperation(
            operation_id="OF1-A", order_id="1001", product_id="P", sequence=1,
            operation_code="A", duration_minutes=120, machine_id=None,
            phase_id="A", team_size=1,
        ),
        SchedulingOperation(
            operation_id="OF2-A", order_id="1002", product_id="P", sequence=1,
            operation_code="A", duration_minutes=120, machine_id=None,
            phase_id="A", team_size=1,
        ),
    ]


def _machines() -> list[SchedulingMachine]:
    return [SchedulingMachine(machine_id="M1", name="M1")]


def _starts(result) -> dict[str, str]:
    return {
        str(op["order_id"]): str(op.get("start_time") or op.get("start"))
        for op in result["operations"]
    }


def _engine() -> CPOv4Engine:
    cfg = CPOConfig(
        use_cpsat_global=False, generations=1, time_limit_sec=0,
        population_size=4, seed=42,
    )
    return CPOv4Engine(_state(), config=cfg)


def test_boost_reordena_o_plano() -> None:
    """Sem boost a OF1 (identidade) vai primeiro; com boost na OF2 é a
    OF2 que arranca primeiro — o boost mudou o plano, não só o badge."""
    sem_boost = _engine().schedule(_ops(), _machines(), _H0, _HE)
    com_boost = _engine().schedule(
        _ops(), _machines(), _H0, _HE, boost_inputs={"1002": 100},
    )

    s0 = _starts(sem_boost)
    s1 = _starts(com_boost)
    assert s0["1001"] <= s0["1002"], "sem boost, a identidade põe a OF1 primeiro"
    assert s1["1002"] < s1["1001"], (
        "com boost 100 na OF2, ela tem de arrancar ANTES da OF1 "
        f"(got OF1={s1['1001']} OF2={s1['1002']})"
    )


def test_sem_boost_e_determinista_back_compat() -> None:
    a = _engine().schedule(_ops(), _machines(), _H0, _HE)
    b = _engine().schedule(_ops(), _machines(), _H0, _HE, boost_inputs=None)
    assert _starts(a) == _starts(b)
