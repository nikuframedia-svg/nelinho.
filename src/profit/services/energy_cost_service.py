"""Custo de energia REAL por sensor/dia (Sprint Q.50 / F8).

Hoje o COGS factura energia com uma linha **standard** —
``MachineRate.energy_cost_per_hour`` × horas (ver
``src/profit/calculators/cogs_calculator.py``). Esse número nunca foi
confrontado com o consumo medido. Este serviço fecha esse buraco: lê os
sensores IoT trifásicos da ERP, integra a potência em **kWh real** e
multiplica pela **tarifa €/kWh** configurável → **€ real** de energia.

Fonte
-----
O reader Q.45.C ``src.adapters.nelo.services.list_iot_sensor_data``
(``IOT_SENSOR_DATA``, ~3.6 M linhas) — amostras de potência trifásica
``SD_POWER_1/2/3`` (watts) com data ``SD_DATE``.

Da potência ao kWh
------------------
Cada amostra traz a potência instantânea (W) das três fases. A energia
de um intervalo entre amostras consecutivas do mesmo sensor é
``potência_média_W × intervalo_h / 1000`` (kWh). O passo de integração é
a **mediana real do intervalo entre amostras** de cada sensor — não há
cadência inventada; quando um sensor só tem uma amostra não há intervalo
e a sua energia fica a zero (sem extrapolar).

Grão honesto
------------
``IOT_SENSOR_DATA`` não tem coluna de fase nem de barco — o mapeamento
sensor→fase vive noutra tabela (``IOT_SENSOR``) que este reader não
expõe. Por isso o grão honesto é **sensor × dia**; o total factory/dia é
o que se compara com a linha de energia standard do COGS.

Honestidade quando a ERP está desligada
----------------------------------------
O adapter levanta ``RuntimeError`` quando ``sqlserver_enabled=False``
(dev/sem credenciais). O serviço apanha-o e devolve um resultado vazio
explícito com ``erp_available=False`` e uma razão — nunca um número
inventado. ZERO MOCKS.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Awaitable, Callable
from uuid import UUID

from src.adapters.nelo.schemas import IotSensorDataRow
from src.adapters.nelo.services import list_iot_sensor_data

log = logging.getLogger(__name__)

# Tarifa €/kWh por omissão quando a config não está disponível. Espelha
# `cost.energy.tariff_eur_per_kwh` em config/yaml/system_defaults.yaml.
DEFAULT_TARIFF_EUR_PER_KWH = Decimal("0.18")

# A energia real só vive na ERP (`IOT_SENSOR_DATA`). Sem o adapter ligado
# não há nada para integrar — degrada para resultado vazio explícito.
ERP_OFFLINE_REASON = (
    "O consumo de energia real vive na tabela ERP IOT_SENSOR_DATA — "
    "o adapter SQL Server está desligado (sqlserver_enabled=False). "
    "Fica sem dados de sensor até ao sync ERP (F1)."
)

IotSensorFetcher = Callable[[date, date], Awaitable[list[IotSensorDataRow]]]


# ─── Result shapes ──────────────────────────────────────────────────────


@dataclass
class SensorDayEnergy:
    """Energia real medida por um sensor num dia.

    ``kwh`` é a potência trifásica integrada no intervalo mediano entre
    amostras; ``cost_eur`` é ``kwh × tarifa``. ``sample_count`` deixa ver
    quão densa foi a amostragem por trás do número.
    """

    sensor_id: int
    day: str
    kwh: float
    cost_eur: float
    sample_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "day": self.day,
            "kwh": self.kwh,
            "cost_eur": self.cost_eur,
            "sample_count": self.sample_count,
        }


@dataclass
class EnergyCostResult:
    """Custo de energia real agregado para a janela pedida."""

    erp_available: bool
    date_from: str
    date_to: str
    tariff_eur_per_kwh: float
    total_kwh: float
    total_cost_eur: float
    sample_count: int
    sensor_count: int
    rows: list[SensorDayEnergy] = field(default_factory=list)
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "erp_available": self.erp_available,
            "reason": self.reason,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "tariff_eur_per_kwh": self.tariff_eur_per_kwh,
            "total_kwh": self.total_kwh,
            "total_cost_eur": self.total_cost_eur,
            "sample_count": self.sample_count,
            "sensor_count": self.sensor_count,
            "items": [r.to_dict() for r in self.rows],
        }


# ─── Service ────────────────────────────────────────────────────────────


class EnergyCostService:
    """Serviço sem estado. Recebe a tarifa e (opcionalmente) um fetcher.

    A tarifa €/kWh deve vir da TenantConfig (``cost.energy.tariff_eur_per_kwh``)
    — usa :meth:`load_tariff` para a carregar com fallback honesto.
    """

    def __init__(
        self,
        tariff_eur_per_kwh: Decimal | float | None = None,
        sensor_fetcher: IotSensorFetcher | None = None,
    ) -> None:
        self.tariff_eur_per_kwh = (
            Decimal(str(tariff_eur_per_kwh))
            if tariff_eur_per_kwh is not None
            else DEFAULT_TARIFF_EUR_PER_KWH
        )
        self._sensors = sensor_fetcher or list_iot_sensor_data

    @staticmethod
    async def load_tariff(session: Any, tenant_id: UUID) -> Decimal:
        """Lê ``cost.energy.tariff_eur_per_kwh`` da TenantConfig.

        Cai na omissão (`DEFAULT_TARIFF_EUR_PER_KWH`) quando a config não
        está disponível — nunca rebenta o pedido por falta de uma chave.
        """
        try:
            from src.core.services.tenant_config_service import TenantConfigService

            svc = TenantConfigService(session, tenant_id)
            cfg = await svc.get_category("cost")
            return Decimal(str(cfg.get(
                "energy.tariff_eur_per_kwh", DEFAULT_TARIFF_EUR_PER_KWH,
            )))
        except Exception as exc:  # pragma: no cover — defensive
            log.warning("energy tariff config load failed: %s", exc)
            return DEFAULT_TARIFF_EUR_PER_KWH

    async def energy_cost(self, date_from: date, date_to: date) -> EnergyCostResult:
        """Custo de energia real medido na janela ``[date_from, date_to]``.

        Degrada para ``erp_available=False`` com uma razão quando o
        adapter ERP está desligado (``RuntimeError`` de ``get_engine``).
        """
        try:
            samples = await self._sensors(date_from, date_to)
        except RuntimeError as exc:
            log.info("energy cost: ERP adapter offline — %s", exc)
            return EnergyCostResult(
                erp_available=False,
                date_from=date_from.isoformat(),
                date_to=date_to.isoformat(),
                tariff_eur_per_kwh=float(self.tariff_eur_per_kwh),
                total_kwh=0.0,
                total_cost_eur=0.0,
                sample_count=0,
                sensor_count=0,
                reason=ERP_OFFLINE_REASON,
            )
        return self._aggregate(samples, date_from, date_to)

    # ─── Aggregation ───────────────────────────────────────────────────

    def _aggregate(
        self,
        samples: list[IotSensorDataRow],
        date_from: date,
        date_to: date,
    ) -> EnergyCostResult:
        """Integra potência → kWh → € por sensor×dia."""
        # Agrupa as amostras por sensor (a integração precisa da sequência
        # temporal completa de cada sensor para medir o intervalo).
        by_sensor: dict[int, list[IotSensorDataRow]] = {}
        for s in samples:
            by_sensor.setdefault(s.sensor_id, []).append(s)

        rows: list[SensorDayEnergy] = []
        for sensor_id, sensor_samples in by_sensor.items():
            rows.extend(self._sensor_rows(sensor_id, sensor_samples))

        rows.sort(key=lambda r: (r.day, r.sensor_id))
        total_kwh = round(sum(r.kwh for r in rows), 3)
        total_cost = round(sum(r.cost_eur for r in rows), 2)
        return EnergyCostResult(
            erp_available=True,
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            tariff_eur_per_kwh=float(self.tariff_eur_per_kwh),
            total_kwh=total_kwh,
            total_cost_eur=total_cost,
            sample_count=len(samples),
            sensor_count=len(by_sensor),
            rows=rows,
        )

    def _sensor_rows(
        self,
        sensor_id: int,
        sensor_samples: list[IotSensorDataRow],
    ) -> list[SensorDayEnergy]:
        """kWh/€ por dia para um único sensor.

        A energia de cada intervalo entre amostras consecutivas é
        ``potência_média_W × passo_h / 1000``. O passo é a mediana real
        do intervalo entre amostras do sensor (segundos → horas). Sem ≥2
        amostras não há intervalo mensurável e a energia fica a zero.
        """
        ordered = sorted(sensor_samples, key=lambda s: s.sampled_at)
        step_h = self._median_step_hours(ordered)

        kwh_by_day: dict[str, float] = {}
        count_by_day: dict[str, int] = {}
        for s in ordered:
            day = s.sampled_at.date().isoformat()
            count_by_day[day] = count_by_day.get(day, 0) + 1
            watts = self._total_power_watts(s)
            kwh_by_day[day] = kwh_by_day.get(day, 0.0) + watts * step_h / 1000.0

        tariff = float(self.tariff_eur_per_kwh)
        return [
            SensorDayEnergy(
                sensor_id=sensor_id,
                day=day,
                kwh=round(kwh_by_day[day], 3),
                cost_eur=round(kwh_by_day[day] * tariff, 2),
                sample_count=count_by_day[day],
            )
            for day in kwh_by_day
        ]

    @staticmethod
    def _total_power_watts(sample: IotSensorDataRow) -> float:
        """Soma das três fases de potência (W), tratando NULL como 0."""
        return float(
            (sample.power_1 or 0)
            + (sample.power_2 or 0)
            + (sample.power_3 or 0)
        )

    @staticmethod
    def _median_step_hours(ordered: list[IotSensorDataRow]) -> float:
        """Mediana do intervalo (horas) entre amostras consecutivas.

        Devolve 0.0 quando há menos de duas amostras — sem intervalo, sem
        energia integrada (não se extrapola uma cadência inventada)."""
        if len(ordered) < 2:
            return 0.0
        deltas_s = [
            (ordered[i].sampled_at - ordered[i - 1].sampled_at).total_seconds()
            for i in range(1, len(ordered))
        ]
        # Intervalos não-positivos (amostras duplicadas no mesmo instante)
        # não representam tempo decorrido — não entram na mediana.
        positive = [d for d in deltas_s if d > 0]
        if not positive:
            return 0.0
        return statistics.median(positive) / 3600.0
