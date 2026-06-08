"""Q.165.C — moldes em paralelo (earliest-free), não 1 molde por modelo.

Antes `_select_mold` devolvia UM molde por modelo (o de maior pocket) → todos os
barcos do modelo serializavam nesse molde, os outros parados. Agora escolhe o
molde LIVRE MAIS CEDO entre todos os do modelo. Cada molde continua exclusivo
(axioma 3). Sem mold_free_at (legacy) → comportamento antigo (back-compat).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from src.plan.cpo.state import FactoryState, MoldInfo
from src.plan.cpo.decoder_resources import _select_mold
from src.plan.engines.scheduling_adapter import SchedulingOperation

TENANT = UUID("11111111-1111-1111-1111-111111111111")
_REF = datetime(2026, 5, 1, 8, 0, 0)


def _state_two_molds() -> FactoryState:
    s = FactoryState(tenant_id=TENANT)
    s.molds_by_model = {
        "MOD": [
            MoldInfo(molde_id="A", modelo_id="MOD", pocket_count=1),
            MoldInfo(molde_id="B", modelo_id="MOD", pocket_count=1),
            MoldInfo(molde_id="C", modelo_id="MOD", pocket_count=1, em_manutencao=True),
        ],
    }
    return s


def _op() -> SchedulingOperation:
    return SchedulingOperation(
        operation_id="O1", order_id="OF1", product_id="P", sequence=1,
        operation_code="LAM", duration_minutes=60, machine_id=None,
        phase_id="1", model_id="MOD", mold_required=True,
    )


def test_molds_for_model_excludes_maintenance_sorted():
    s = _state_two_molds()
    molds = s.molds_for_model("MOD")
    assert [m.molde_id for m in molds] == ["A", "B"]  # C em manutenção fora; ordenado


def test_select_mold_picks_earliest_free():
    s = _state_two_molds()
    # A ocupado até +10h, B livre → escolhe B (earliest-free).
    mold_free_at = {"A": _REF + timedelta(hours=10)}
    chosen = _select_mold(_op(), s, mold_free_at=mold_free_at, earliest=_REF)
    assert chosen == "B"


def test_select_mold_legacy_without_free_at():
    # Sem mold_free_at → comportamento antigo (mold_for: maior pocket / 1º).
    s = _state_two_molds()
    chosen = _select_mold(_op(), s)
    assert chosen in {"A", "B"}  # não inventa; um molde válido não-manutenção


def test_select_mold_two_boats_use_different_molds():
    # 1º barco → A (ambos livres, tie por id); marca A ocupado; 2º barco → B.
    s = _state_two_molds()
    free: dict = {}
    c1 = _select_mold(_op(), s, mold_free_at=free, earliest=_REF)
    free[c1] = _REF + timedelta(hours=5)  # 1º molde ocupado
    c2 = _select_mold(_op(), s, mold_free_at=free, earliest=_REF)
    assert c1 == "A" and c2 == "B"  # paralelizam, não serializam no mesmo
