"""Q.26.C.2 — custo de mão-de-obra de uma OF a partir do histórico real.

Para cada fase executada de uma ordem de fabrico (`OF_FP`) preça as horas
reais — o decorrido `OFFP_DATAINICIO → OFFP_DATAFIM` — pelo custo/hora de
cada operador que lá trabalhou (`OFFP_EQ`).

**Horas = decorrido limpo** (decisão do Luis): a doutrina do projecto é
usar tempo histórico real, não coeficientes standard (CLAUDE.md §1.7). O
decorrido só conta onde há operador atribuído — fases sem ninguém em
`OFFP_EQ` (ex.: Cura) caem fora do join e contribuem 0.

**Custo/hora = real por operador** (decisão do Luis, não média): vem de
`core.labor_rates.loaded_rate`, sincronizado do `E_CUSTOHORA` do ERP pelo
Q.26.C.1. Operador sem taxa entra com custo 0 e é contado em
`unpriced_operator_count` — o custo nunca é inventado.

O cálculo puro vive nas dataclasses + :func:`build_labor_lines`; o serviço
só faz I/O (adapter read-only + Postgres).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.nelo import services
from src.adapters.nelo.schemas import OrderLaborRow
from src.core.models.employee import Employee
from src.core.models.rates import LaborRate

_ZERO = Decimal("0")
_SECONDS_PER_HOUR = Decimal("3600")


@dataclass(frozen=True)
class LaborCostLine:
    """Uma fase executada de uma OF — horas reais × operadores precados."""

    operation_id: int
    phase_id: int
    phase_name: str
    is_return: bool                 # OFFP_RETURN — passagem de retrabalho
    hours: Decimal                  # decorrido DATAINICIO→DATAFIM, em horas
    operator_count: int             # operadores atribuídos à fase
    priced_operator_count: int      # operadores com taxa em core.labor_rates
    sum_operator_rate: Decimal      # Σ loaded_rate dos operadores precados
    has_hours: bool                 # False quando o decorrido não é positivo

    @property
    def line_cost(self) -> Decimal:
        """Custo da linha = horas × soma dos custos/hora dos operadores."""
        return self.hours * self.sum_operator_rate


@dataclass(frozen=True)
class LaborCostResult:
    """Custo de mão-de-obra de uma ordem de fabrico inteira."""

    work_order_id: int
    total_labor_cost: Decimal
    phase_count: int
    missing_hours_count: int        # fases sem decorrido válido
    unpriced_operator_count: int    # operadores sem taxa no ERP
    lines: tuple[LaborCostLine, ...]

    @classmethod
    def from_lines(
        cls, work_order_id: int, lines: Sequence[LaborCostLine]
    ) -> "LaborCostResult":
        """Agrega linhas num resultado — puro, sem BD (testável directo)."""
        lines = tuple(lines)
        total = sum((ln.line_cost for ln in lines), _ZERO)
        missing = sum(1 for ln in lines if not ln.has_hours)
        unpriced = sum(
            ln.operator_count - ln.priced_operator_count for ln in lines
        )
        return cls(
            work_order_id=work_order_id,
            total_labor_cost=total,
            phase_count=len(lines),
            missing_hours_count=missing,
            unpriced_operator_count=unpriced,
            lines=lines,
        )

    @property
    def is_complete(self) -> bool:
        """True quando há fases e todas tinham horas e operadores precados."""
        return (
            self.phase_count > 0
            and self.missing_hours_count == 0
            and self.unpriced_operator_count == 0
        )


def _elapsed_hours(
    start: Optional[datetime], end: Optional[datetime]
) -> tuple[Decimal, bool]:
    """Decorrido `start→end` em horas. Devolve (horas, válido).

    Datas em falta ou decorrido não-positivo (dado sujo) → (0, False).
    """
    if start is None or end is None:
        return _ZERO, False
    seconds = (end - start).total_seconds()
    if seconds <= 0:
        return _ZERO, False
    return Decimal(str(seconds)) / _SECONDS_PER_HOUR, True


def build_labor_lines(
    rows: Sequence[OrderLaborRow],
    rate_by_code: dict[str, Decimal],
) -> list[LaborCostLine]:
    """Agrupa as linhas adapter (uma por operador) por operação e preça-as.

    `rate_by_code` mapeia o código do operador (`str(E_ID)`) ao seu
    `loaded_rate`. Operador ausente do dict não soma custo — é contado
    como não-precado.
    """
    grouped: dict[int, list[OrderLaborRow]] = {}
    for r in rows:
        grouped.setdefault(r.operation_id, []).append(r)

    lines: list[LaborCostLine] = []
    for op_id, op_rows in grouped.items():
        first = op_rows[0]
        hours, has_hours = _elapsed_hours(first.start_at, first.end_at)
        sum_rate = _ZERO
        priced = 0
        for r in op_rows:
            rate = rate_by_code.get(str(r.operator_id))
            if rate is not None:
                sum_rate += rate
                priced += 1
        lines.append(
            LaborCostLine(
                operation_id=op_id,
                phase_id=first.phase_id,
                phase_name=first.phase_name,
                is_return=first.is_return,
                hours=hours,
                operator_count=len(op_rows),
                priced_operator_count=priced,
                sum_operator_rate=sum_rate,
                has_hours=has_hours,
            )
        )
    return lines


class LaborCostService:
    """Calcula o custo de mão-de-obra real de uma OF (Q.26.C.2)."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def labor_cost(
        self, work_order_id: int, as_of: Optional[date] = None
    ) -> LaborCostResult:
        """Custo de mão-de-obra da ordem de fabrico `work_order_id`.

        Lê as execuções de fase × operadores do ERP vivo (read-only) e
        preça-as com as taxas efectivas em `as_of` (hoje por omissão).
        """
        as_of = as_of or date.today()
        rows = await services.list_order_labor(work_order_id)
        codes = {str(r.operator_id) for r in rows}
        rate_by_code = await self._rates_by_code(codes, as_of)
        return LaborCostResult.from_lines(
            work_order_id, build_labor_lines(rows, rate_by_code)
        )

    async def _rates_by_code(
        self, codes: set[str], as_of: date
    ) -> dict[str, Decimal]:
        """Taxa horária (`loaded_rate`) efectiva em `as_of` por operador.

        As taxas são time-phased: para cada operador escolhe a linha de
        `effective_date` mais recente que não ultrapassa `as_of`.
        """
        if not codes:
            return {}
        stmt = (
            select(
                Employee.employee_code,
                LaborRate.effective_date,
                LaborRate.loaded_rate,
            )
            .join(LaborRate, LaborRate.employee_id == Employee.id)
            .where(
                Employee.tenant_id == self.tenant_id,
                LaborRate.tenant_id == self.tenant_id,
                Employee.employee_code.in_(codes),
                LaborRate.effective_date <= as_of,
            )
        )
        rows = (await self.session.execute(stmt)).all()
        latest: dict[str, tuple[date, Decimal]] = {}
        for code, effective_date, loaded_rate in rows:
            code = str(code)
            current = latest.get(code)
            if current is None or effective_date > current[0]:
                latest[code] = (effective_date, loaded_rate)
        return {code: rate for code, (_, rate) in latest.items()}
