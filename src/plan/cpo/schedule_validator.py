"""Q.169.B — validador ESTRUTURAL universal de schedules.

A matriz de paridade (agent_docs/axiom_parity_matrix.md) mostrou que os
axiomas 1-6 são garantidos "by construction" no decoder, mas NADA os
verifica no schedule final que vai para o ScheduleCommit — qualquer
engine novo (CP-SAT global), o reapply do robô ou um apply-move manual
podem persistir um plano que viola molde/cura/double-booking sem ninguém
dar por isso. O safety_net é (por design) um gate de KPIs (axioma 7) —
esta é a peça complementar: validação de ESTRUTURA, independente de
engine e de baseline, no caminho de escrita.

Contrato (sobre ``schedule["operations"]`` — o dict serializado pelo
decoder em ``decoder_helpers._scheduled_to_dict``):

ERROS (recusam o commit — violação física/química inequívoca):
  * ordem com fases sobrepostas no tempo (um barco não está em 2 fases);
  * gap de cura química violado entre fases consecutivas da mesma ordem
    (16 transições — precisa de ``state`` para nomes+gaps);
  * mesmo molde em 2 batches sobrepostos (axioma 3; ops do MESMO
    ``mold_batch_id`` são UM batch — podem coexistir);
  * operador em 2 ops sobrepostas (double-booking);
  * operador fora do pool de competências da fase (axioma 5 — só quando
    ``state`` tem pool para a fase).

WARNINGS (não bloqueiam — política/observabilidade):
  * fase par-preferida (Laminagem) com 1 só operador (downgrade soft do
    Sprint Q.8 é política aceite — mas fica visível);
  * mesma estação (machine_id ≠ MANUAL) com ops sobrepostas (capacity>1
    é legítima nalguns requests → não dá para afirmar erro sem o state);
  * ops sem timestamps parseáveis (ficam fora dos checks).

Stateless por omissão (qualquer caller pode validar qualquer commit);
com ``state`` (FactoryState) liga também cura/skills/pares.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from itertools import pairwise
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Tolerância para arredondamentos de serialização (ISO sem micros, etc.).
_TOL = timedelta(seconds=60)

# Pool partilhado sem exclusividade (legacy) — nunca valida overlap.
_UNBOUNDED_MACHINES = {"", "MANUAL"}

_MAX_MESSAGES = 50


@dataclass
class ValidationReport:
    """Resultado do validador — erros recusam, warnings observam."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checks_run: List[str] = field(default_factory=list)
    ops_total: int = 0
    ops_validated: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_meta(self) -> Dict[str, Any]:
        """Resumo para o cpo_meta (não entra no hash)."""
        return {
            "ok": self.ok,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "checks_run": list(self.checks_run),
            "ops_validated": self.ops_validated,
            "ops_total": self.ops_total,
            "messages": (self.errors + self.warnings)[:_MAX_MESSAGES],
        }


class ScheduleValidationError(ValueError):
    """Schedule estruturalmente inválido — NUNCA deve ser persistido."""

    def __init__(self, report: ValidationReport):
        self.report = report
        preview = "; ".join(report.errors[:5])
        more = f" (+{len(report.errors) - 5})" if len(report.errors) > 5 else ""
        super().__init__(
            f"schedule inválido: {len(report.errors)} violações estruturais — "
            f"{preview}{more}"
        )


@dataclass
class _Op:
    operation_id: str
    order_id: str
    phase_id: str
    start: datetime
    end: datetime
    workers: Tuple[str, ...]
    mold_id: Optional[str]
    mold_batch_id: Optional[str]
    machine_id: Optional[str]


def _parse_ops(
    operations: List[Dict[str, Any]], report: ValidationReport,
) -> List[_Op]:
    out: List[_Op] = []
    bad = 0
    for raw in operations:
        try:
            start = datetime.fromisoformat(str(raw["start_time"]))
            end = datetime.fromisoformat(str(raw["end_time"]))
        except (KeyError, TypeError, ValueError):
            bad += 1
            continue
        # naive/aware mistos rebentariam as comparações — normaliza a naive
        # (domínio de planeamento é naive-consistente até F2-tz).
        if start.tzinfo is not None:
            start = start.replace(tzinfo=None)
        if end.tzinfo is not None:
            end = end.replace(tzinfo=None)
        out.append(_Op(
            operation_id=str(raw.get("operation_id") or ""),
            order_id=str(raw.get("order_id") or ""),
            phase_id=str(raw.get("phase_id") or ""),
            start=start,
            end=end,
            workers=tuple(str(w) for w in (raw.get("workers") or []) if w),
            mold_id=(str(raw["mold_id"]) if raw.get("mold_id") else None),
            mold_batch_id=(
                str(raw["mold_batch_id"]) if raw.get("mold_batch_id") else None
            ),
            machine_id=(str(raw["machine_id"]) if raw.get("machine_id") else None),
        ))
    if bad:
        report.warnings.append(
            f"{bad} ops sem timestamps parseáveis — fora da validação"
        )
    return out


def _phase_name_map(state: Any) -> Dict[str, str]:
    """fase_id → fase_nome, das rotas que o state já carrega (canónica +
    templates + histórico). Best-effort: ids sem nome ficam fora do check
    de cura (o gap é keyed por NOME normalizado)."""
    names: Dict[str, str] = {}
    for step in (getattr(state, "phase_catalog", None) or []):
        fid = str(step.get("fase_id") or "")
        nome = step.get("fase_nome")
        if fid and nome:
            names.setdefault(fid, str(nome))
    for source in (
        getattr(state, "template_routes_by_model", None) or {},
        getattr(state, "historical_routes_by_model", None) or {},
    ):
        for steps in source.values():
            for step in steps or []:
                if isinstance(step, dict):
                    fid = str(step.get("fase_id") or "")
                    nome = step.get("fase_nome")
                else:
                    fid = str(getattr(step, "fase_id", "") or "")
                    nome = getattr(step, "fase_nome", None)
                if fid and nome:
                    names.setdefault(fid, str(nome))
    return names


def _overlaps(a_start: datetime, a_end: datetime,
              b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end - _TOL and b_start < a_end - _TOL


def _check_order_sequence(
    ops: List[_Op], report: ValidationReport, state: Any,
) -> None:
    """Um barco não está em 2 fases ao mesmo tempo + gaps de cura."""
    report.checks_run.append("ordem_sem_sobreposicao")
    gaps: Dict[Tuple[str, str], float] = (
        getattr(state, "phase_transition_gaps", None) or {} if state else {}
    )
    names = _phase_name_map(state) if state and gaps else {}
    if gaps:
        report.checks_run.append("cura_quimica")

    normalize = None
    if gaps:
        from src.plan.cpo.state import normalize_phase_code
        normalize = normalize_phase_code

    by_order: Dict[str, List[_Op]] = {}
    for op in ops:
        if op.order_id:
            by_order.setdefault(op.order_id, []).append(op)

    for order_id, order_ops in by_order.items():
        order_ops.sort(key=lambda o: (o.start, o.end, o.operation_id))
        for prev, curr in pairwise(order_ops):
            if _overlaps(prev.start, prev.end, curr.start, curr.end):
                report.errors.append(
                    f"ordem {order_id}: fases {prev.phase_id} e "
                    f"{curr.phase_id} sobrepostas no tempo (um barco não "
                    f"está em 2 fases)"
                )
                continue
            if not gaps or normalize is None:
                continue
            a = normalize(names.get(prev.phase_id, prev.phase_id))
            b = normalize(names.get(curr.phase_id, curr.phase_id))
            gap_h = float(gaps.get((a, b), 0.0))
            if gap_h > 0.0:
                required = prev.end + timedelta(hours=gap_h)
                if curr.start < required - _TOL:
                    report.errors.append(
                        f"ordem {order_id}: cura química violada "
                        f"{a}→{b} (mín {gap_h}h; começa "
                        f"{(required - curr.start).total_seconds() / 3600.0:.1f}h cedo)"
                    )


def _check_mold_exclusive(ops: List[_Op], report: ValidationReport) -> None:
    """Axioma 3 — um molde físico, um batch de cada vez."""
    report.checks_run.append("molde_exclusivo")
    by_mold: Dict[str, List[_Op]] = {}
    for op in ops:
        if op.mold_id:
            by_mold.setdefault(op.mold_id, []).append(op)

    for mold_id, mold_ops in by_mold.items():
        # ops do mesmo batch são UM uso do molde (intervalo agregado)
        intervals: Dict[str, Tuple[datetime, datetime]] = {}
        singles: List[Tuple[datetime, datetime, str]] = []
        for op in mold_ops:
            if op.mold_batch_id:
                cur = intervals.get(op.mold_batch_id)
                intervals[op.mold_batch_id] = (
                    (min(cur[0], op.start), max(cur[1], op.end))
                    if cur else (op.start, op.end)
                )
            else:
                singles.append((op.start, op.end, op.operation_id))
        merged = [
            (s, e, f"batch:{bid}") for bid, (s, e) in intervals.items()
        ] + singles
        merged.sort()
        for (s1, e1, id1), (s2, e2, id2) in pairwise(merged):
            if _overlaps(s1, e1, s2, e2):
                report.errors.append(
                    f"molde {mold_id}: {id1} e {id2} sobrepostos "
                    f"(axioma 3 — molde exclusivo)"
                )


def _check_worker_double_booking(ops: List[_Op], report: ValidationReport) -> None:
    report.checks_run.append("operador_sem_double_booking")
    by_worker: Dict[str, List[_Op]] = {}
    for op in ops:
        for w in op.workers:
            by_worker.setdefault(w, []).append(op)

    for worker, w_ops in by_worker.items():
        w_ops.sort(key=lambda o: (o.start, o.end, o.operation_id))
        for prev, curr in pairwise(w_ops):
            if _overlaps(prev.start, prev.end, curr.start, curr.end):
                report.errors.append(
                    f"operador {worker}: {prev.operation_id} e "
                    f"{curr.operation_id} sobrepostos (double-booking)"
                )


def _check_absences(ops: List[_Op], report: ValidationReport, state: Any) -> None:
    """Q.174.F4 — axioma novo: nenhum operador trabalha DENTRO de uma janela
    de ausência (ENT_MOV MET=2 + overrides locais). Só corre quando o state
    traz ``worker_absences`` (vazio = sem check, back-compat)."""
    absences = getattr(state, "worker_absences", None) if state else None
    if not absences:
        return
    report.checks_run.append("operador_disponivel")
    for op in ops:
        for w in op.workers:
            for ini, fim in absences.get(str(w), ()):  # ordenadas
                if fim <= op.start:
                    continue
                if ini >= op.end:
                    break
                report.errors.append(
                    f"op {op.operation_id}: operador {w} AUSENTE em "
                    f"[{ini.isoformat()} .. {fim.isoformat()}) mas alocado "
                    f"[{op.start.isoformat()} .. {op.end.isoformat()}) "
                    f"(disponibilidade — Q.174.F4)"
                )
                break


def _check_skills(ops: List[_Op], report: ValidationReport, state: Any) -> None:
    """Axioma 5 — operador atribuído pertence ao pool da fase (só quando o
    state tem pool para essa fase; pool vazio = fase manual, sem check)."""
    if state is None or not getattr(state, "skill_matrix", None):
        return
    report.checks_run.append("skill_match")
    for op in ops:
        if not op.workers or not op.phase_id:
            continue
        pool = state.workers_for(op.phase_id)
        if not pool:
            continue
        foreign = [w for w in op.workers if w not in pool]
        if foreign:
            report.errors.append(
                f"op {op.operation_id}: operador(es) {', '.join(foreign)} "
                f"fora do pool de competências da fase {op.phase_id} "
                f"(axioma 5)"
            )


def _check_pairs(ops: List[_Op], report: ValidationReport, state: Any) -> None:
    """Axioma 4 — par preferido com 1 operador = WARNING (política soft Q.8)."""
    if state is None:
        return
    pair_phases = tuple(getattr(state, "PAIR_PREFERRED_PHASES", ()) or ())
    if not pair_phases:
        return
    report.checks_run.append("par_laminagem")
    names = _phase_name_map(state)
    from src.plan.cpo.state import normalize_phase_code

    # Q.169.C — match EXATO (como pair_assignment.prefers_pair): substring
    # apanharia LAMINAGEM_INFUSAO, que é solo por política (58% histórico).
    preferred = {normalize_phase_code(p) for p in pair_phases}
    solo = 0
    for op in ops:
        if len(op.workers) != 1:
            continue
        nome = normalize_phase_code(names.get(op.phase_id, op.phase_id)) or ""
        if nome in preferred:
            solo += 1
    if solo:
        report.warnings.append(
            f"{solo} ops em fase par-preferida (Laminagem) com 1 só operador "
            f"(downgrade soft Q.8 — verificar pool)"
        )


def _check_machine_overlap(ops: List[_Op], report: ValidationReport) -> None:
    """Estações com ops sobrepostas = WARNING (capacity>1 pode ser legítima)."""
    report.checks_run.append("estacao_overlap")
    by_machine: Dict[str, List[_Op]] = {}
    for op in ops:
        m = (op.machine_id or "").strip()
        if m and m.upper() not in _UNBOUNDED_MACHINES:
            by_machine.setdefault(m, []).append(op)

    flagged = 0
    for machine, m_ops in by_machine.items():
        m_ops.sort(key=lambda o: (o.start, o.end, o.operation_id))
        for prev, curr in pairwise(m_ops):
            if _overlaps(prev.start, prev.end, curr.start, curr.end):
                flagged += 1
                if flagged <= 5:
                    report.warnings.append(
                        f"estação {machine}: {prev.operation_id} e "
                        f"{curr.operation_id} sobrepostos (verificar capacity)"
                    )
    if flagged > 5:
        report.warnings.append(
            f"estações: +{flagged - 5} sobreposições adicionais"
        )


def validate_schedule(
    schedule: Dict[str, Any],
    state: Any = None,
) -> ValidationReport:
    """Valida a ESTRUTURA de um schedule (qualquer engine, qualquer caminho).

    Stateless por omissão; com ``state`` (FactoryState) liga também cura
    química, skill match e par-preferido. Devolve sempre um relatório —
    quem persiste decide (``CommitsService`` recusa ``errors``)."""
    report = ValidationReport()
    operations = list(schedule.get("operations") or [])
    report.ops_total = len(operations)
    ops = _parse_ops(operations, report)
    report.ops_validated = len(ops)
    if not ops:
        return report

    _check_order_sequence(ops, report, state)
    _check_mold_exclusive(ops, report)
    _check_worker_double_booking(ops, report)
    _check_absences(ops, report, state)  # Q.174.F4 — disponibilidade
    _check_skills(ops, report, state)
    _check_pairs(ops, report, state)
    _check_machine_overlap(ops, report)

    if report.errors:
        logger.warning(
            "validate_schedule: %d erros estruturais, %d warnings (%d ops)",
            len(report.errors), len(report.warnings), report.ops_validated,
        )
    return report
