"""
ProdPlan ONE — Validação ambiental da cura (F12) — Sprint Q.49
===============================================================

A cura é química. Os 16 gaps de cura em `src/plan/cpo/state.py`
(`NELO_CURING_GAPS_SEED`) são um seed validado — mas hoje o sistema confia
no RELÓGIO: garante que decorre tempo suficiente entre fases, nunca verifica
se esse tempo decorreu nas condições ambientais certas. Resina que cura
abaixo de 18 °C ou acima de 70 % de humidade não cura bem, e o defeito só
aparece fases adiante.

Este módulo é uma **validação retrospectiva** — dado um período, cruza as
operações de cura/desmolde já executadas com as leituras reais de
temperatura/humidade da tabela ERP `TH`, e sinaliza as que decorreram com
temperatura ou humidade fora do intervalo aceitável.

NÃO é uma constraint do scheduler
---------------------------------
No momento em que o plano é gerado não se conhece o sensor do futuro. Isto
é diagnóstico *a posteriori*, não previsão. O scheduler e os 7 axiomas
Spelke ficam intactos — este serviço só lê.

Honestidade de degradação
-------------------------
`validate_curing_window` aqui é **lógica pura** e testável sem I/O. Quem o
chama (o endpoint em `src/plan/api/`) é responsável por ler os readers ERP
ao vivo (`list_operations`, `list_temperature_humidity`) e, quando o ERP
está desligado (`sqlserver_enabled=False`), devolver uma resposta explícita
"sem dados de sensor" — NUNCA um número de conformidade inventado.

Cruzamento operação ↔ leitura
-----------------------------
A chave é a **janela temporal**: uma leitura de `TH` pertence a uma operação
de cura se o seu `measured_at` cair dentro de `[start_at, end_at]` da
operação. Quando a operação tem fase declarada no sensor (`phase_id`) usa-se
também a fase como filtro adicional; quando o sensor não tem fase, só a
janela temporal manda — a fábrica tem poucas sondas e uma serve várias
fases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Intervalo ambiental aceitável — defaults documentados (logic-as-data).
# ---------------------------------------------------------------------------
# Estes valores são o ponto de partida. O endpoint sobrepõe-nos por tenant
# via `TenantConfigService` (categoria `quality`), portanto NÃO são uma
# constante de cálculo enterrada — são o fallback honesto quando o tenant
# não definiu política própria. Faixa típica de cura de resina epóxi.
DEFAULT_TEMP_MIN_C: float = 18.0
DEFAULT_TEMP_MAX_C: float = 28.0
DEFAULT_HUMIDITY_MIN_PCT: float = 35.0
DEFAULT_HUMIDITY_MAX_PCT: float = 70.0

# Fases (códigos normalizados) tratadas como cura/desmolde para a validação.
DEFAULT_CURING_PHASE_CODES: tuple[str, ...] = ("CURA", "DESMOLDE")


# =============================================================================
# Tipos de entrada (forma mínima — desacoplado dos schemas do adapter ERP)
# =============================================================================

@dataclass(frozen=True)
class CuringOperation:
    """Uma operação de cura ou desmolde já executada.

    Forma mínima: só os campos que a validação precisa. O endpoint converte
    cada `OperationRow` do reader `list_operations` para isto, o que mantém
    este serviço independente do schema do adapter ERP.
    """

    operation_id: str
    work_order_id: str
    phase_code: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


@dataclass(frozen=True)
class SensorReading:
    """Uma leitura ambiental da tabela ERP `TH`.

    O endpoint converte cada `TempHumidityRow` do reader
    `list_temperature_humidity` para isto. `humidity` é opcional porque
    `TH_HUM` é nullable na ERP.
    """

    measured_at: datetime
    temperature: float
    humidity: Optional[float] = None
    phase_id: Optional[int] = None


@dataclass(frozen=True)
class EnvironmentRange:
    """Intervalo ambiental aceitável para a cura — configurável por tenant."""

    temp_min_c: float = DEFAULT_TEMP_MIN_C
    temp_max_c: float = DEFAULT_TEMP_MAX_C
    humidity_min_pct: float = DEFAULT_HUMIDITY_MIN_PCT
    humidity_max_pct: float = DEFAULT_HUMIDITY_MAX_PCT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "temp_min_c": self.temp_min_c,
            "temp_max_c": self.temp_max_c,
            "humidity_min_pct": self.humidity_min_pct,
            "humidity_max_pct": self.humidity_max_pct,
        }


# =============================================================================
# Resultado da validação
# =============================================================================

@dataclass
class OperationVerdict:
    """Veredicto ambiental de uma operação de cura.

    `status`:
      * ``conforme``    — todas as leituras dentro do intervalo;
      * ``fora_range``  — pelo menos uma leitura fora do intervalo;
      * ``sem_leituras`` — não há leituras de `TH` na janela da operação
        (não se pode afirmar conformidade — nem incumprimento).
    """

    operation_id: str
    work_order_id: str
    phase_code: str
    reading_count: int = 0
    temp_min_observed: Optional[float] = None
    temp_max_observed: Optional[float] = None
    humidity_min_observed: Optional[float] = None
    humidity_max_observed: Optional[float] = None
    breaches: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.reading_count == 0:
            return "sem_leituras"
        return "fora_range" if self.breaches else "conforme"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "work_order_id": self.work_order_id,
            "phase_code": self.phase_code,
            "status": self.status,
            "reading_count": self.reading_count,
            "temp_min_observed": self.temp_min_observed,
            "temp_max_observed": self.temp_max_observed,
            "humidity_min_observed": self.humidity_min_observed,
            "humidity_max_observed": self.humidity_max_observed,
            "breaches": self.breaches,
        }


@dataclass
class CuringValidationResult:
    """Resultado completo da validação ambiental de um período."""

    verdicts: List[OperationVerdict]
    environment_range: EnvironmentRange

    @property
    def operations_total(self) -> int:
        return len(self.verdicts)

    @property
    def conforme_total(self) -> int:
        return sum(1 for v in self.verdicts if v.status == "conforme")

    @property
    def fora_range_total(self) -> int:
        return sum(1 for v in self.verdicts if v.status == "fora_range")

    @property
    def sem_leituras_total(self) -> int:
        return sum(1 for v in self.verdicts if v.status == "sem_leituras")

    @property
    def conformity_pct(self) -> Optional[float]:
        """% de operações conformes, sobre as que TÊM leituras.

        Operações sem leituras não entram no denominador — não há evidência
        para as classificar. Devolve None se nenhuma operação tem leituras
        (não se inventa 100 %).
        """
        evaluated = self.conforme_total + self.fora_range_total
        if evaluated == 0:
            return None
        return round(100.0 * self.conforme_total / evaluated, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "operations_total": self.operations_total,
            "conforme_total": self.conforme_total,
            "fora_range_total": self.fora_range_total,
            "sem_leituras_total": self.sem_leituras_total,
            "conformity_pct": self.conformity_pct,
            "environment_range": self.environment_range.to_dict(),
            "verdicts": [v.to_dict() for v in self.verdicts],
        }


# =============================================================================
# Validação — lógica pura, sem I/O
# =============================================================================

def _readings_in_window(
    operation: CuringOperation,
    readings: List[SensorReading],
) -> List[SensorReading]:
    """Leituras de `TH` cujo `measured_at` cai dentro de `[start_at, end_at]`.

    Sem janela completa (falta `start_at` ou `end_at`) não se consegue
    cruzar — devolve lista vazia, e a operação fica `sem_leituras`.
    """
    if operation.start_at is None or operation.end_at is None:
        return []
    lo, hi = operation.start_at, operation.end_at
    if hi < lo:
        lo, hi = hi, lo
    return [r for r in readings if lo <= r.measured_at <= hi]


def _verdict_for(
    operation: CuringOperation,
    readings: List[SensorReading],
    env: EnvironmentRange,
) -> OperationVerdict:
    """Veredicto ambiental de uma operação contra as suas leituras."""
    window = _readings_in_window(operation, readings)

    verdict = OperationVerdict(
        operation_id=operation.operation_id,
        work_order_id=operation.work_order_id,
        phase_code=operation.phase_code,
        reading_count=len(window),
    )
    if not window:
        return verdict

    temps = [r.temperature for r in window]
    hums = [r.humidity for r in window if r.humidity is not None]

    verdict.temp_min_observed = round(min(temps), 2)
    verdict.temp_max_observed = round(max(temps), 2)
    if hums:
        verdict.humidity_min_observed = round(min(hums), 2)
        verdict.humidity_max_observed = round(max(hums), 2)

    if verdict.temp_min_observed < env.temp_min_c:
        verdict.breaches.append(
            f"temperatura mínima {verdict.temp_min_observed} °C abaixo de "
            f"{env.temp_min_c} °C"
        )
    if verdict.temp_max_observed > env.temp_max_c:
        verdict.breaches.append(
            f"temperatura máxima {verdict.temp_max_observed} °C acima de "
            f"{env.temp_max_c} °C"
        )
    if verdict.humidity_min_observed is not None and (
        verdict.humidity_min_observed < env.humidity_min_pct
    ):
        verdict.breaches.append(
            f"humidade mínima {verdict.humidity_min_observed} % abaixo de "
            f"{env.humidity_min_pct} %"
        )
    if verdict.humidity_max_observed is not None and (
        verdict.humidity_max_observed > env.humidity_max_pct
    ):
        verdict.breaches.append(
            f"humidade máxima {verdict.humidity_max_observed} % acima de "
            f"{env.humidity_max_pct} %"
        )
    return verdict


def validate_curing_window(
    operations: List[CuringOperation],
    readings: List[SensorReading],
    *,
    environment_range: Optional[EnvironmentRange] = None,
) -> CuringValidationResult:
    """Valida um conjunto de operações de cura contra leituras de `TH`.

    `operations` são as operações de cura/desmolde já executadas (o endpoint
    converte-as de `OperationRow`). `readings` são as leituras ambientais do
    período (de `TempHumidityRow`). `environment_range` é o intervalo
    aceitável — quando omitido usa-se o default documentado.

    Cada operação recebe um `OperationVerdict`. A junção é por janela
    temporal: uma leitura conta para uma operação se o seu `measured_at`
    cair entre `start_at` e `end_at` dessa operação.
    """
    env = environment_range or EnvironmentRange()
    verdicts = [_verdict_for(op, readings, env) for op in operations]
    return CuringValidationResult(verdicts=verdicts, environment_range=env)


# =============================================================================
# Conversores dos schemas do adapter ERP (tolerantes a duck-typing)
# =============================================================================

def curing_operations_from_rows(
    rows: List[Any],
    curing_phase_codes: tuple[str, ...] = DEFAULT_CURING_PHASE_CODES,
) -> List[CuringOperation]:
    """Filtra `OperationRow`s do reader `list_operations`, ficando só com as
    operações de cura/desmolde, e converte-as para `CuringOperation`.

    A fase é normalizada com `normalize_phase_code` (o mesmo do CPO) para
    casar "Cura" / "CURA" / "cura". `curing_phase_codes` é configurável —
    o endpoint passa a lista do tenant.
    """
    from src.plan.cpo.state import normalize_phase_code

    wanted = {normalize_phase_code(c) for c in curing_phase_codes}
    out: List[CuringOperation] = []
    for r in rows:
        phase_code = normalize_phase_code(getattr(r, "phase_name", "") or "")
        if phase_code not in wanted:
            continue
        out.append(
            CuringOperation(
                operation_id=str(getattr(r, "operation_id", "") or ""),
                work_order_id=str(getattr(r, "work_order_id", "") or ""),
                phase_code=phase_code,
                start_at=getattr(r, "start_at", None),
                end_at=getattr(r, "end_at", None),
            )
        )
    return out


def sensor_readings_from_rows(rows: List[Any]) -> List[SensorReading]:
    """Converte `TempHumidityRow`s do reader `list_temperature_humidity` em
    `SensorReading`s. Tolera qualquer objecto com os atributos `measured_at`,
    `temperature`, `humidity`, `phase_id`.
    """
    out: List[SensorReading] = []
    for r in rows:
        measured_at = getattr(r, "measured_at", None)
        temperature = getattr(r, "temperature", None)
        if measured_at is None or temperature is None:
            continue
        out.append(
            SensorReading(
                measured_at=measured_at,
                temperature=float(temperature),
                humidity=getattr(r, "humidity", None),
                phase_id=getattr(r, "phase_id", None),
            )
        )
    return out
