"""Q.169.F — a cura química estava MORTA em produção (id vs nome).

Descoberta da prova live F2.F: o validate_schedule (Q.169.B), no primeiro
dia em serviço, RECUSOU um plano do robô com 330 violações LAMINAGEM→CURA
(gap real 0.4h = fila mediana Q.160, em vez dos 15h de química). Causa de
raiz: o mapa de gaps é keyed por NOME normalizado ("LAMINAGEM","CURA") mas
TODOS os caminhos de produção (decoder, CP-SAT, postpass) chamam
`min_gap_hours(phase_id, phase_id)` com ids numéricos do ERP ("1","2") →
0.0 sempre. Os testes nunca apanharam porque usam tokens consistentes.

O alias nome→id (via phase_catalog) fecha o buraco para todos os callers.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from src.plan.cpo.state import FactoryState, alias_gaps_by_phase_id
from src.plan.engines import cpsat_scheduler as cs
from src.plan.engines.cpsat_scheduler import CPSATConfig, CPSATScheduler
from src.plan.engines.scheduling_adapter import SchedulingOperation

_CATALOG = [
    {"fase_id": "1", "fase_nome": "Laminagem", "sequence": 1},
    {"fase_id": "2", "fase_nome": "Cura", "sequence": 2},
    {"fase_id": "66", "fase_nome": "Acabamento - Envernizamento", "sequence": 30},
    {"fase_id": "40", "fase_nome": "Lixagem água", "sequence": 31},
]


class TestAliasGapsByPhaseId:
    def test_name_keyed_gap_gains_id_keys(self):
        gaps = alias_gaps_by_phase_id(
            {("LAMINAGEM", "CURA"): 15.0}, _CATALOG,
        )
        assert gaps[("LAMINAGEM", "CURA")] == 15.0  # original mantém-se
        assert gaps[("1", "2")] == 15.0             # alias por id do ERP

    def test_synonym_enverniz_resolves_to_real_phase(self):
        """O seed diz ACABAMENTO_ENVERNIZ; a fase real (FP_ID=66) chama-se
        "Acabamento - Envernizamento" — sinónimo explícito cobre o drift."""
        gaps = alias_gaps_by_phase_id(
            {("ACABAMENTO_ENVERNIZ", "LIXAGEM_AGUA"): 18.0}, _CATALOG,
        )
        assert gaps[("66", "40")] == 18.0

    def test_unmatched_name_stays_name_only(self):
        gaps = alias_gaps_by_phase_id(
            {("FASE_INEXISTENTE", "CURA"): 9.0}, _CATALOG,
        )
        assert ("FASE_INEXISTENTE", "CURA") in gaps
        assert len([k for k in gaps if k[0].isdigit()]) == 0

    def test_empty_inputs_are_safe(self):
        assert alias_gaps_by_phase_id({}, _CATALOG) == {}
        assert alias_gaps_by_phase_id({("A", "B"): 1.0}, []) == {("A", "B"): 1.0}


class TestMinGapHoursByErpId:
    def test_lookup_by_numeric_id_returns_real_gap(self):
        """O lookup que TODOS os caminhos de produção fazem — era 0.0."""
        state = FactoryState(tenant_id=uuid4())
        state.phase_catalog = _CATALOG
        state.phase_transition_gaps = alias_gaps_by_phase_id(
            {("LAMINAGEM", "CURA"): 15.0}, state.phase_catalog,
        )
        assert state.min_gap_hours("1", "2") == 15.0
        assert state.min_gap_hours("Laminagem", "Cura") == 15.0  # nome continua
        assert state.min_gap_hours("2", "1") == 0.0  # direção inversa sem gap


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_cpsat_enforces_curing_with_erp_numeric_ids():
    """Reprodução EXATA do cenário live: ops com phase_id numérico ("1","2")
    e gaps keyed por nome — sem o alias o CP-SAT punha a Cura 0.4h depois
    da Laminagem; com o alias respeita as 15h."""
    state = FactoryState(tenant_id=uuid4())
    state.phase_catalog = _CATALOG
    state.phase_transition_gaps = alias_gaps_by_phase_id(
        {("LAMINAGEM", "CURA"): 15.0}, state.phase_catalog,
    )
    state.phase_stations = {"1": 1, "2": 1}
    state.skill_matrix = {"1": {"w1"}}

    ops = [
        SchedulingOperation(
            operation_id="O1", order_id="OF-1", product_id="P", sequence=1,
            operation_code="Laminagem", duration_minutes=60, machine_id=None,
            phase_id="1", team_size=1,
        ),
        SchedulingOperation(
            operation_id="O2", order_id="OF-1", product_id="P", sequence=2,
            operation_code="Cura", duration_minutes=60, machine_id=None,
            phase_id="2", team_size=1,
        ),
    ]
    res = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, datetime(2026, 6, 1),
    )
    assert res.available and res.status in ("OPTIMAL", "FEASIBLE")
    assert res.starts_min["O2"] >= res.ends_min["O1"] + 15 * 60, (
        "cura química (15h) tem de valer com ids numéricos do ERP"
    )
