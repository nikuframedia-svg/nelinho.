"""Q.164.A — property tests: load-balancing do operador no decoder.

O `_pick_workers` concentrava trabalho nos mesmos poucos operadores quando o
`earliest` da op era no futuro (upstream atrasado) → `availability` colapsava a
1.0 para TODOS → o desempate caía direto no id → top operador com 7049h e
makespan de 4,6 anos. O fix junta tiebreaks INFERIORES (idle-há-mais-tempo,
menor carga) ao sort key, SEM tocar no `combined` (regime normal inalterado).

Invariantes (axioma Spelke 5 intacto — só REORDENA o pool já apto):
* A — a penalização de carga VENCE o skill no regime degenerado: op no futuro →
  todos livres → availability=1 p/ todos → sem o fix o skill concentrava tudo no
  de topo (medido: 1 operador ~9000h). Com o fix, o menos carregado ganha.
* A2 — empate em availability → menor carga ganha (depois id, determinismo).
* B — end-to-end: N ordens numa fase com pool > team_size espalham a carga
  (max−min ops por operador ≤ 1) mesmo com earliests futuros escalonados.
* C — skill grande domina a penalização: com qw=1 e gap de skill > penalização,
  o de maior skill é escolhido (curado/qualidade não é atropelado por carga).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from uuid import uuid4

from hypothesis import given, settings, strategies as st

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.decoder_resources import _pick_workers
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation

_REF = datetime(2026, 5, 1, 8, 0, 0)
_FASE = "PHASE_X"


# ---------------------------------------------------------------------------
# Invariante A — a penalização de carga vence o skill no regime degenerado
# ---------------------------------------------------------------------------


def _state_skills(matrix: dict) -> FactoryState:
    state = FactoryState(tenant_id=uuid4())
    state.skill_matrix = matrix
    return state


@given(hi_load=st.floats(min_value=200.0, max_value=10000.0))
@settings(max_examples=120, deadline=None)
def test_load_penalty_overcomes_skill_in_degenerate_regime(hi_load):
    # Regime degenerado: ambos livres MUITO antes do earliest → availability=1 p/
    # os dois. w_hi é o mais versátil (skill_count=3) mas está SOBRECARREGADO;
    # w_lo tem menos skill (skill_count=1) e está livre. Com qw moderado (0.3) a
    # penalização de carga TEM de fazer w_lo ganhar — senão o skill concentrava
    # tudo no w_hi (o bug medido: makespan ~4,6 anos). É a falha que o tiebreak-
    # only NÃO apanhava (combined difere por skill, o tiebreak nunca disparava).
    state = _state_skills({_FASE: {"w_hi", "w_lo"}, "B": {"w_hi"}, "C": {"w_hi"}})
    free = {"w_hi": _REF - timedelta(hours=50), "w_lo": _REF - timedelta(hours=50)}
    wload = {"w_hi": hi_load, "w_lo": 0.0}
    picked = _pick_workers(
        {"w_hi", "w_lo"}, team_size=1, worker_free_at=free, earliest=_REF,
        state=state, quality_weight=0.3, fase_id=_FASE, worker_load_h=wload,
    )
    assert picked == ["w_lo"]  # menos carregado ganha apesar de menos skill


@given(loads=st.lists(st.integers(min_value=0, max_value=1000),
                      min_size=2, max_size=8, unique=True))
@settings(max_examples=150, deadline=None)
def test_least_loaded_wins_when_availability_ties(loads):
    # Todos livres (availability=1) + sem skill (state=None) → o `combined` fica
    # decidido pela penalização de carga: menor carga ganha; depois id. Cargas
    # inteiras (separação ≥1) p/ evitar diferenças sub-epsilon de float.
    pool = {f"w{i}" for i in range(len(loads))}
    free = {w: _REF - timedelta(hours=10) for w in pool}  # todos livres há 10h
    wload = {f"w{i}": float(loads[i]) for i in range(len(loads))}
    picked = _pick_workers(
        pool, team_size=1, worker_free_at=free, earliest=_REF,
        state=None, quality_weight=0.0, worker_load_h=wload,
    )
    expected_first = min(pool, key=lambda w: (wload[w], w))
    assert picked[0] == expected_first  # menos carregado ganha


# ---------------------------------------------------------------------------
# Invariante B — a carga espalha-se end-to-end (decode)
# ---------------------------------------------------------------------------


def _state_two_phase(test_pool: set[str]) -> FactoryState:
    state = FactoryState(tenant_id=uuid4())
    # GATE: 1 operador (serializa, escalona os earliests da fase TEST no futuro).
    # TEST: pool equi-skill > team_size (é aqui que a carga tem de espalhar).
    state.skill_matrix = {"GATE": {"gate"}, "PHASE_X": set(test_pool)}
    return state


@given(
    n_orders=st.integers(min_value=4, max_value=10),
    n_workers=st.integers(min_value=2, max_value=5),
)
@settings(max_examples=60, deadline=None)
def test_load_spreads_across_equally_eligible_workers(n_orders, n_workers):
    # N ordens, cada uma GATE(seq1, 1 op longo serializado) → TEST(seq2, op curto).
    # As GATE serializam no único operador "gate" → cada TEST_i arranca no futuro,
    # já com TODOS os operadores TEST livres (regime degenerado). Sem o fix, todas
    # as TEST iam para o mesmo operador (id mais baixo); com o fix, espalham.
    test_pool = {f"t{i}" for i in range(n_workers)}
    state = _state_two_phase(test_pool)
    horizon_start = _REF
    horizon_end = horizon_start + timedelta(days=400)  # folga: nada infeasible

    ops: list[SchedulingOperation] = []
    for i in range(n_orders):
        ops.append(SchedulingOperation(
            operation_id=f"G{i}", order_id=f"OF{i}", product_id="P",
            sequence=1, operation_code="GATE", duration_minutes=600.0,  # 10h
            machine_id=None, phase_id="GATE",
        ))
        ops.append(SchedulingOperation(
            operation_id=f"T{i}", order_id=f"OF{i}", product_id="P",
            sequence=2, operation_code="TEST", duration_minutes=60.0,  # 1h << 10h
            machine_id=None, phase_id="PHASE_X",
        ))
    machines = [SchedulingMachine(machine_id=f"M{i}", name=f"M{i}")
                for i in range(n_orders + 2)]
    chrom = Chromosome(permutation=list(range(len(ops))), quality_weight=0.0)

    result = decode(chrom, ops, machines, state, horizon_start, horizon_end)

    loads = Counter()
    for op in result["operations"]:
        if op["phase_id"] == "PHASE_X" and op["workers"]:
            loads[op["workers"][0]] += 1
    assert sum(loads.values()) == n_orders  # toda a fase TEST foi staffed
    counts = sorted(loads.values())
    # Espalha quase perfeitamente (divisão inteira): max − min ≤ 1.
    assert counts[-1] - counts[0] <= 1


# ---------------------------------------------------------------------------
# Invariante C — um gap de skill grande domina a penalização de carga
# ---------------------------------------------------------------------------


@given(
    busy_h=st.integers(min_value=1, max_value=200),
    master_load=st.floats(min_value=0.0, max_value=5000.0),
)
@settings(max_examples=150, deadline=None)
def test_large_skill_gap_dominates_load_penalty(busy_h, master_load):
    # w_master é MUITO mais versátil (skill_count=3 vs 1) e está ocupado + MUITO
    # carregado; w_novice está livre e sem carga. Com qw=1 (qualidade pura) o gap
    # de skill (~0.67) supera a penalização de carga (≤0.6) → o master ganha. Isto
    # garante que o load-balancing NÃO atropela a escolha de qualidade quando a
    # diferença de competência é grande (curado/Q.155.D fica protegido).
    state = _state_skills({
        _FASE: {"w_master", "w_novice"},
        "PHASE_B": {"w_master"},
        "PHASE_C": {"w_master"},
    })
    free = {"w_master": _REF + timedelta(hours=busy_h), "w_novice": _REF}
    wload = {"w_master": master_load, "w_novice": 0.0}
    picked = _pick_workers(
        {"w_master", "w_novice"}, team_size=1, worker_free_at=free, earliest=_REF,
        state=state, quality_weight=1.0, fase_id=_FASE, worker_load_h=wload,
    )
    assert picked == ["w_master"]  # skill grande manda sobre a penalização
