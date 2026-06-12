"""ProdPlan ONE — CP-SAT post-pass: atribuição CONCRETA de recursos (Q.166.B+C).

O `cpsat_scheduler` resolve só o TIMING com capacidades CUMULATIVE (anónimas). Este
post-pass percorre as ops pela ordem de start do CP-SAT e atribui ESTAÇÃO + OPERADORES
+ MOLDE concretos, usando o start do CP-SAT como PISO. Como as contagens cumulative já
cabem, existe sempre uma atribuição; o `max(piso, recurso_livre)` garante zero
double-booking (axiomas: estação/molde exclusivos, skill match, precedência+cura).

Q.166.C — CALENDÁRIO integrado aqui (não num re-pass à parte, que re-introduziria
conflitos): quando `state.calendar` existe, o TRABALHO é assente nas horas úteis
(`add_working_hours`, Seg-Sáb 1 turno) e a cura fica piso WALL-CLOCK (química 24/7).
Espelha o decoder (`decoder_resources.py:674-694`). Sem calendário → 24/7.

Reusa o load-balance Q.164.A (`_pick_workers`), o earliest-free molde Q.165.C
(`_select_mold`) e as estações por fase (`station_ids_for`). Determinístico.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from src.plan.cpo.decoder_helpers import ScheduledOp
from src.plan.cpo.decoder_resources import (
    _MIN_POOL_FOR_MATCHING,
    _pick_workers,
    _select_mold,
)
from src.plan.services.phase_workcenters import station_ids_for

logger = logging.getLogger(__name__)


def assign_concrete(
    operations: List[Any],          # List[SchedulingOperation]
    state: Any,                     # FactoryState
    horizon_start: datetime,
    starts_min: Dict[str, int],     # op_id → start (min desde horizon_start) do CP-SAT
) -> List[ScheduledOp]:
    """Atribui recursos concretos aos tempos do CP-SAT (start como piso). 24/7."""
    # ordem = start do CP-SAT, depois OF e sequência (determinístico).
    ordered = sorted(
        operations,
        key=lambda o: (
            starts_min.get(str(o.operation_id), 0),
            str(o.order_id),
            int(getattr(o, "sequence", 0) or 0),
        ),
    )

    # estações por fase (ids determinísticos), livres a partir de horizon_start.
    phase_stations: Dict[str, List[str]] = {}
    machine_free_at: Dict[str, datetime] = {}
    worker_free_at: Dict[str, datetime] = {}
    worker_load_h: Dict[str, float] = {}
    mold_free_at: Dict[str, datetime] = {}
    op_end_at: Dict[str, datetime] = {}

    def _stations_for(fase: str) -> List[str]:
        if fase not in phase_stations:
            n = 1
            nsf = getattr(state, "num_stations_for", None)
            if nsf is not None:
                try:
                    n = max(1, int(nsf(fase)))
                except Exception:  # pragma: no cover
                    n = 1
            ids = station_ids_for(fase, n)
            phase_stations[fase] = ids
            for sid in ids:
                machine_free_at.setdefault(sid, horizon_start)
        return phase_stations[fase]

    # mapa OF → ops ordenadas por sequência (para o piso de precedência+cura).
    by_order: Dict[str, List[Any]] = defaultdict(list)
    for o in operations:
        by_order[str(o.order_id)].append(o)
    for lst in by_order.values():
        lst.sort(key=lambda o: int(getattr(o, "sequence", 0) or 0))

    scheduled: List[ScheduledOp] = []
    calendar = getattr(state, "calendar", None)  # Q.166.C — Seg-Sáb 1 turno, ou None=24/7

    for op in ordered:
        oid = str(op.operation_id)
        fase = str(op.phase_id)
        team = max(1, int(getattr(op, "team_size", 1) or 1))
        dur = max(1.0, float(op.duration_minutes))

        # piso = start do CP-SAT.
        floor = horizon_start + timedelta(minutes=int(starts_min.get(oid, 0)))
        # piso de precedência+cura (defesa: o CP-SAT já o garante, mas reafirma).
        siblings = by_order[str(op.order_id)]
        for prev in siblings:
            prev_oid = str(prev.operation_id)
            if prev_oid == oid:
                continue
            prev_end = op_end_at.get(prev_oid)
            if prev_end is None:
                continue
            p_seq = int(getattr(prev, "sequence", 0) or 0)
            o_seq = int(getattr(op, "sequence", 0) or 0)
            if p_seq < o_seq:
                gap_h = 0.0
                mg = getattr(state, "min_gap_hours", None)
                if mg is not None:
                    try:
                        gap_h = float(mg(prev.phase_id, op.phase_id))
                    except Exception:  # pragma: no cover
                        gap_h = 0.0
                cand = prev_end + timedelta(hours=gap_h)
            elif p_seq == o_seq and prev_oid < oid:
                # Q.169.G — sequências empatadas serializam (um barco não está
                # em 2 fases): o solver chaina empates, mas o empurrão por
                # recursos aqui podia re-sobrepô-los.
                cand = prev_end
            else:
                continue
            if cand > floor:
                floor = cand

        # estação: a livre mais cedo entre as da fase.
        stations = _stations_for(fase)
        best_station = min(stations, key=lambda s: (machine_free_at[s], s))

        # operadores: pool apto, load-balanced (Q.164.A); start empurra se ocupados.
        pool = set()
        wf = getattr(state, "workers_for", None)
        if wf is not None:
            try:
                pool = set(wf(fase))
            except Exception:  # pragma: no cover
                pool = set()
        picked: List[str] = []
        if pool:
            # Q.174.F3 — paridade ICB com o decoder (Q.155.D): o boost
            # difícil↔curado estava ADORMECIDO no caminho CP-SAT (op_complexity
            # nunca era passado aqui — o vencedor de produção perdia o
            # matching). Mesma isenção de fases finas do decoder.
            op_complexity = 0.0
            _bc = getattr(state, "boat_complexity", None)
            if _bc is not None and len(pool) > _MIN_POOL_FOR_MATCHING:
                try:
                    op_complexity = _bc(str(getattr(op, "model_id", "") or ""))
                except Exception:  # pragma: no cover — defensivo
                    op_complexity = 0.0
            picked = _pick_workers(
                pool, team, worker_free_at, floor,
                state=state, quality_weight=0.3,
                fase_id=fase, worker_load_h=worker_load_h,
                op_complexity=op_complexity,
                # Q.174.F4 — disponibilidade: ausentes afundam no ranking.
                op_duration_h=dur / 60.0,
            )

        # molde: earliest-free entre os do modelo (Q.165.C).
        mold_chosen = _select_mold(
            op, state, mold_free_at=mold_free_at, earliest=floor,
        )

        # start = max(piso, estação, operadores, molde).
        cands = [floor, machine_free_at[best_station]]
        for w in picked:
            cands.append(worker_free_at.get(w, horizon_start))
        if mold_chosen:
            cands.append(mold_free_at.get(mold_chosen, horizon_start))
        start = max(cands)
        # Q.166.C — assenta o trabalho nas horas úteis (calendário); cura (acima) é
        # piso wall-clock. Sem calendário → 24/7. Espelha o decoder.
        if calendar is not None:
            start = calendar.add_working_hours(start, 0.0)

        # Q.174.F4 — garantia dura de disponibilidade (espelha o decoder):
        # fixpoint combinado push-de-ausência → re-snap de calendário.
        _abs_adj = getattr(state, "absence_adjusted_start", None)
        if (
            picked and _abs_adj is not None
            and getattr(state, "worker_absences", None)
        ):
            _dur_h = max(1.0, dur) / 60.0
            for _ in range(16):
                pushed = start
                for w in picked:
                    adj = _abs_adj(w, pushed, _dur_h)
                    if adj > pushed:
                        pushed = adj
                if pushed == start:
                    break
                start = (
                    calendar.add_working_hours(pushed, 0.0)
                    if calendar is not None else pushed
                )

        if calendar is not None:
            end = calendar.add_working_hours(start, dur / 60.0)
        else:
            end = start + timedelta(minutes=dur)

        scheduled.append(ScheduledOp(
            operation_id=oid,
            order_id=str(op.order_id),
            phase_id=fase,
            machine_id=best_station,
            workers=list(picked),
            mold_id=mold_chosen,
            start=start,
            end=end,
            duration_minutes=dur,
            mold_batch_id=None,
            setup_family=str(getattr(op, "setup_family", "") or ""),
        ))
        op_end_at[oid] = end
        machine_free_at[best_station] = end
        for w in picked:
            worker_free_at[w] = end
            worker_load_h[w] = worker_load_h.get(w, 0.0) + dur / 60.0
        if mold_chosen:
            # Q.174.F2 — cooldown canónico do molde (≈24h; Ocean ≈72h);
            # espelha o decoder. 0 = desligado.
            _cd_h = float(getattr(state, "mold_cooldown_hours", lambda _m: 0.0)(
                mold_chosen
            ) or 0.0)
            mold_free_at[mold_chosen] = (
                end + timedelta(hours=_cd_h) if _cd_h > 0 else end
            )

    return scheduled
