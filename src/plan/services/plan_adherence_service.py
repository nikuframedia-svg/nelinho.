"""
ProdPlan ONE — Aderência ao plano (plano vs realizado) — Sprint Q.44
====================================================================

F13. O plano digital já existe — `ScheduleCommit` (`src/plan/cpo/commits.py`)
persiste-o imutável, hash-chained, com KPIs e operações. O ERP MAR-KAYAKS é
read-only: não há (nem deve haver) write-back para `PLANEAMENTO_DIARIO`.

O que falta não é gerar o plano — é **medir se foi cumprido**. Este módulo
compara as operações planeadas de um `ScheduleCommit` com o que o `OF_FP`
real registou que aconteceu, devolvendo:

- % de aderência ao plano (operações planeadas que foram de facto executadas
  dentro da tolerância de horas),
- desvios por fase (deriva média de início/fim, em horas),
- operações em falta (planeadas mas sem execução real correspondente),
- operações não planeadas (executadas mas ausentes do commit).

Honestidade de degradação
-------------------------
Em dev `sqlserver_enabled=False`, logo o reader `list_operations` não devolve
dados reais. O `compare_adherence` aqui é **lógica pura** e testável; quem o
chama (o endpoint em `src/plan/api/`) é responsável por apanhar a
indisponibilidade do ERP e devolver `status="sem_execucao_real"` em vez de um
número inventado. Esta separação mantém o serviço unit-testável sem I/O.

A chave de junção plano↔realizado é `(order_id, phase_id)`: o `operation_id`
de um `ScheduleCommit` é uma string gerada pelo CPO, enquanto o `OFFP_ID` do
`OF_FP` é o id real — não casam. A ordem de fabrico + fase é o par estável
partilhado pelas duas fontes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Tolerância por omissão: uma operação conta como "aderente" se o seu início
# real cair dentro desta janela face ao início planeado. 8 h = um turno; a
# fábrica não trabalha ao minuto, e a deriva sub-turno não é incumprimento.
DEFAULT_TOLERANCE_HOURS: float = 8.0


# =============================================================================
# Tipos de execução real (forma mínima — desacoplado do OperationRow do ERP)
# =============================================================================

@dataclass(frozen=True)
class RealizedOperation:
    """Uma operação que o `OF_FP` registou que aconteceu de facto.

    Forma mínima: só os campos de que a comparação precisa. O endpoint
    converte cada `OperationRow` do reader `list_operations` para isto, o
    que mantém este serviço independente do schema do adapter ERP.
    """

    work_order_id: str
    phase_id: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


# =============================================================================
# Resultado da comparação
# =============================================================================

@dataclass
class PhaseDeviation:
    """Deriva agregada de uma fase entre plano e realizado."""

    phase_id: str
    planned_count: int = 0
    matched_count: int = 0
    start_drift_hours: List[float] = field(default_factory=list)
    end_drift_hours: List[float] = field(default_factory=list)

    @property
    def avg_start_drift_hours(self) -> Optional[float]:
        if not self.start_drift_hours:
            return None
        return round(sum(self.start_drift_hours) / len(self.start_drift_hours), 2)

    @property
    def avg_end_drift_hours(self) -> Optional[float]:
        if not self.end_drift_hours:
            return None
        return round(sum(self.end_drift_hours) / len(self.end_drift_hours), 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "planned_count": self.planned_count,
            "matched_count": self.matched_count,
            "avg_start_drift_hours": self.avg_start_drift_hours,
            "avg_end_drift_hours": self.avg_end_drift_hours,
        }


@dataclass
class AdherenceResult:
    """Resultado completo da comparação plano vs realizado."""

    planned_total: int
    realized_total: int
    matched_total: int
    within_tolerance_total: int
    missing: List[Dict[str, str]]      # planeadas sem execução real
    unplanned: List[Dict[str, str]]    # executadas mas fora do commit
    phase_deviations: List[PhaseDeviation]
    tolerance_hours: float

    @property
    def adherence_pct(self) -> float:
        """% de operações planeadas executadas dentro da tolerância de horas.

        Base = operações planeadas. Uma operação sem execução real, ou
        executada muito longe da hora planeada, não conta como aderente.
        """
        if self.planned_total == 0:
            return 0.0
        return round(100.0 * self.within_tolerance_total / self.planned_total, 2)

    @property
    def match_pct(self) -> float:
        """% de operações planeadas que têm *alguma* execução real (deriva
        à parte). Mede cobertura; `adherence_pct` mede cumprimento."""
        if self.planned_total == 0:
            return 0.0
        return round(100.0 * self.matched_total / self.planned_total, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "planned_total": self.planned_total,
            "realized_total": self.realized_total,
            "matched_total": self.matched_total,
            "within_tolerance_total": self.within_tolerance_total,
            "adherence_pct": self.adherence_pct,
            "match_pct": self.match_pct,
            "tolerance_hours": self.tolerance_hours,
            "missing": self.missing,
            "unplanned": self.unplanned,
            "phase_deviations": [pd.to_dict() for pd in self.phase_deviations],
        }


# =============================================================================
# Comparação — lógica pura, sem I/O
# =============================================================================

def _parse_dt(value: Any) -> Optional[datetime]:
    """Aceita ISO-string (do JSONB do commit) ou datetime (do reader)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _key(order_id: Any, phase_id: Any) -> Tuple[str, str]:
    """Chave de junção estável (work order, fase) como par de strings."""
    return (str(order_id or ""), str(phase_id or ""))


def _hours_between(a: Optional[datetime], b: Optional[datetime]) -> Optional[float]:
    """`a - b` em horas; None se faltar qualquer dos lados."""
    if a is None or b is None:
        return None
    return (a - b).total_seconds() / 3600.0


def compare_adherence(
    planned_operations: List[Dict[str, Any]],
    realized_operations: List[RealizedOperation],
    *,
    tolerance_hours: float = DEFAULT_TOLERANCE_HOURS,
) -> AdherenceResult:
    """Compara operações planeadas (de um `ScheduleCommit`) com a execução real.

    `planned_operations` é `ScheduleCommit.operations` — cada dict tem
    `order_id`, `phase_id`, `start_time`, `end_time` (ISO strings).
    `realized_operations` é a execução real do `OF_FP`, já convertida para
    `RealizedOperation`.

    A junção é por `(order_id, phase_id)`. Quando há mais do que uma
    operação real para o mesmo par (fase repetível, retrabalho), escolhe-se
    a de início mais cedo — é a execução que o plano pretendia.
    """
    tol = max(0.0, float(tolerance_hours))

    # Index das execuções reais por (work_order, fase). Em caso de repetição
    # fica a de start_at mais cedo (a primeira passagem pela fase).
    realized_by_key: Dict[Tuple[str, str], RealizedOperation] = {}
    for ro in realized_operations:
        k = _key(ro.work_order_id, ro.phase_id)
        existing = realized_by_key.get(k)
        if existing is None:
            realized_by_key[k] = ro
            continue
        if ro.start_at is not None and (
            existing.start_at is None or ro.start_at < existing.start_at
        ):
            realized_by_key[k] = ro

    matched_keys: set[Tuple[str, str]] = set()
    matched_total = 0
    within_tolerance_total = 0
    missing: List[Dict[str, str]] = []
    deviations: Dict[str, PhaseDeviation] = {}

    for op in planned_operations:
        order_id = str(op.get("order_id") or "")
        phase_id = str(op.get("phase_id") or "")
        k = (order_id, phase_id)

        dev = deviations.setdefault(phase_id, PhaseDeviation(phase_id=phase_id))
        dev.planned_count += 1

        real = realized_by_key.get(k)
        if real is None:
            missing.append({"order_id": order_id, "phase_id": phase_id})
            continue

        matched_keys.add(k)
        matched_total += 1
        dev.matched_count += 1

        planned_start = _parse_dt(op.get("start_time"))
        planned_end = _parse_dt(op.get("end_time"))
        start_drift = _hours_between(real.start_at, planned_start)
        end_drift = _hours_between(real.end_at, planned_end)
        if start_drift is not None:
            dev.start_drift_hours.append(round(start_drift, 2))
        if end_drift is not None:
            dev.end_drift_hours.append(round(end_drift, 2))

        # Aderente = início real dentro da tolerância do início planeado.
        # Sem hora de início real ou planeada não se pode afirmar deriva;
        # nesse caso a operação conta como executada mas não como aderente,
        # para não inflar a métrica sem evidência.
        if start_drift is not None and abs(start_drift) <= tol:
            within_tolerance_total += 1

    unplanned: List[Dict[str, str]] = [
        {"order_id": ro.work_order_id, "phase_id": ro.phase_id}
        for k, ro in realized_by_key.items()
        if k not in matched_keys
    ]

    phase_deviations = sorted(deviations.values(), key=lambda d: d.phase_id)

    return AdherenceResult(
        planned_total=len(planned_operations),
        realized_total=len(realized_by_key),
        matched_total=matched_total,
        within_tolerance_total=within_tolerance_total,
        missing=missing,
        unplanned=unplanned,
        phase_deviations=phase_deviations,
        tolerance_hours=tol,
    )


def realized_from_operation_rows(rows: List[Any]) -> List[RealizedOperation]:
    """Converte `OperationRow`s do reader `list_operations` em
    `RealizedOperation`s. Tolera qualquer objecto com os atributos
    `work_order_id`, `phase_id`, `start_at`, `end_at`.
    """
    out: List[RealizedOperation] = []
    for r in rows:
        out.append(
            RealizedOperation(
                work_order_id=str(getattr(r, "work_order_id", "") or ""),
                phase_id=str(getattr(r, "phase_id", "") or ""),
                start_at=getattr(r, "start_at", None),
                end_at=getattr(r, "end_at", None),
            )
        )
    return out
