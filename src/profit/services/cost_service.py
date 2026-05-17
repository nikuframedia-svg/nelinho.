"""
ProdPlan ONE - Cost Service
============================

Business logic for COGS calculations.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.profit.models.cost import CostCalculation, CalculationStatus
from src.profit.calculators.cogs_calculator import COGSCalculator, COGSResult
from src.profit.calculators.scenario_simulator import ScenarioSimulator, CostMultipliers, ScenarioResult
from src.core.services.configuration_service import ConfigurationService
from src.profit.services.labor_cost_service import LaborCostResult, LaborCostService
from src.profit.services.material_cost_service import MaterialCostResult, MaterialCostService
from src.shared.kafka_client import publish_event, Topics
from src.shared.events import COGSCalculatedEvent

_logger = logging.getLogger(__name__)


def assemble_cogs_inputs(
    material: MaterialCostResult,
    labor: LaborCostResult,
    overhead_rate: Decimal,
) -> Dict[str, Any]:
    """Constrói os argumentos do COGSCalculator a partir das fontes reais.

    Q.26.F.1 — liga o COGS ponta-a-ponta: material vem do BOM real
    (Q.26.B), mão-de-obra do histórico OF_FP×OFFP_EQ (Q.26.C), overhead
    da taxa configurada (`core.overhead_rates`). Cada fase de mão-de-obra
    vira uma alocação `{horas, taxa}` — o calculador faz horas×taxa, que é
    exactamente o custo da linha. As `total_production_hours` (base do
    rateio de overhead) são as horas reais com decorrido válido.

    Função pura — sem BD, testável directo.
    """
    labor_allocations = [
        {
            "employee_id": f"fase:{ln.phase_id}",
            "employee_name": ln.phase_name,
            "hours": ln.hours,
            "rate": ln.sum_operator_rate,
        }
        for ln in labor.lines
    ]
    total_production_hours = sum(
        (ln.hours for ln in labor.lines if ln.has_hours), Decimal("0")
    )
    return {
        "bom_costs": dict(material.bom_costs),
        "labor_allocations": labor_allocations,
        "overhead_rate": overhead_rate,
        "total_production_hours": total_production_hours,
    }


def _per_unit(cost: Decimal, quantity: Decimal) -> Decimal:
    """Custo por unidade com guarda — Q.30.0.1.

    Uma `CostCalculation` persistida com `quantity=0` rebentava com
    `ZeroDivisionError` (HTTP 500) ao reconstruir o `COGSResult`.
    """
    return cost / quantity if quantity and quantity > 0 else Decimal("0")


def _reconstruct_base_result(calculation: CostCalculation) -> COGSResult:
    """Reconstrói o `COGSResult` de uma `CostCalculation` persistida.

    Partilhado por `simulate_scenario` e `run_sensitivity_analysis` —
    antes era um bloco duplicado byte-a-byte que dividia por
    `calculation.quantity` sem guarda (Q.30.0.1).
    """
    from src.profit.calculators.cogs_calculator import CostBreakdown, CostComponent

    q = calculation.quantity
    return COGSResult(
        order_id=calculation.order_id,
        product_id=str(calculation.product_id),
        quantity=q,
        total_cogs=calculation.total_cogs,
        cogs_per_unit=calculation.cogs_per_unit,
        breakdown=CostBreakdown(
            material=CostComponent("Material", calculation.material_cost, _per_unit(calculation.material_cost, q)),
            labor=CostComponent("Labor", calculation.labor_cost, _per_unit(calculation.labor_cost, q)),
            machine=CostComponent("Machine", calculation.machine_cost, _per_unit(calculation.machine_cost, q)),
            setup=CostComponent("Setup", calculation.setup_cost, _per_unit(calculation.setup_cost, q)),
            overhead=CostComponent("Overhead", calculation.overhead_cost, _per_unit(calculation.overhead_cost, q)),
            scrap=CostComponent("Scrap", calculation.scrap_cost, _per_unit(calculation.scrap_cost, q)),
        ),
        currency=calculation.currency_code,
    )


class CostService:
    """
    Service for COGS calculations.
    
    Orchestrates cost calculations and persistence.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
        self._calculator = COGSCalculator()
        self._simulator = ScenarioSimulator()
    
    async def calculate_cogs(
        self,
        order_id: str,
        product_id: UUID,
        quantity: Decimal,
        bom_costs: Dict[str, Decimal] = None,
        labor_allocations: List[Dict[str, Any]] = None,
        machine_usage: List[Dict[str, Any]] = None,
        setup_activities: List[Dict[str, Any]] = None,
        overhead_rate: Decimal = Decimal("0"),
        total_production_hours: Decimal = Decimal("0"),
        scrap_rate: Decimal = Decimal("0.02"),
        save: bool = True,
    ) -> COGSResult:
        """
        Calculate COGS for an order.
        
        Optionally saves to database.
        """
        result = self._calculator.calculate(
            order_id=order_id,
            product_id=str(product_id),
            quantity=quantity,
            bom_costs=bom_costs,
            labor_allocations=labor_allocations,
            machine_usage=machine_usage,
            setup_activities=setup_activities,
            overhead_rate=overhead_rate,
            total_production_hours=total_production_hours,
            scrap_rate=scrap_rate,
        )
        
        if save:
            await self._save_calculation(result, product_id)
        
        # Publish event
        await publish_event(
            Topics.COGS_CALCULATED,
            COGSCalculatedEvent(
                tenant_id=self.tenant_id,
                payload={
                    "order_id": order_id,
                    "total_cogs": float(result.total_cogs),
                    "cogs_per_unit": float(result.cogs_per_unit),
                    "breakdown": {
                        "material": float(result.breakdown.material.total),
                        "labor": float(result.breakdown.labor.total),
                        "machine": float(result.breakdown.machine.total),
                        "setup": float(result.breakdown.setup.total),
                        "overhead": float(result.breakdown.overhead.total),
                        "scrap": float(result.breakdown.scrap.total),
                    },
                    "currency": result.currency,
                },
            ),
        )
        
        return result

    async def calculate_cogs_from_sources(
        self,
        *,
        order_id: str,
        product_id: UUID,
        work_order_id: int,
        quantity: Decimal = Decimal("1"),
        save: bool = True,
    ) -> COGSResult:
        """Calcula o COGS de uma OF a partir das fontes de dados reais.

        Q.26.F.1 — liga o COGS ponta-a-ponta. Em vez de receber os custos
        por payload, puxa-os:

        * material — `MaterialCostService` (BOM real × custo standard);
        * mão-de-obra — `LaborCostService` (horas reais OF_FP × custo/hora);
        * overhead — `ConfigurationService.get_overhead_rate_value()`.

        `product_id` é o UUID de `core.products`; `work_order_id` é o
        `OF_ID` legado do ERP. Custo de máquina fica 0 (Q.26.E — depende
        do IoT). O resultado é persistido como qualquer COGS (`save`).
        """
        material = await MaterialCostService(
            self.session, self.tenant_id
        ).material_cost(product_id)
        labor = await LaborCostService(
            self.session, self.tenant_id
        ).labor_cost(work_order_id)
        overhead_rate = await ConfigurationService(
            self.session, self.tenant_id
        ).get_overhead_rate_value()

        inputs = assemble_cogs_inputs(material, labor, overhead_rate)
        return await self.calculate_cogs(
            order_id=order_id,
            product_id=product_id,
            quantity=quantity,
            bom_costs=inputs["bom_costs"],
            labor_allocations=inputs["labor_allocations"],
            overhead_rate=inputs["overhead_rate"],
            total_production_hours=inputs["total_production_hours"],
            save=save,
        )

    async def _save_calculation(
        self,
        result: COGSResult,
        product_id: UUID,
    ) -> CostCalculation:
        """Save COGS calculation to database."""
        # Get next version
        existing = await self.get_calculation(result.order_id)
        version = 1
        if existing:
            version = existing.calculation_version + 1
        
        calculation = CostCalculation(
            tenant_id=self.tenant_id,
            order_id=result.order_id,
            product_id=product_id,
            quantity=result.quantity,
            calculation_version=version,
            material_cost=result.breakdown.material.total,
            labor_cost=result.breakdown.labor.total,
            machine_cost=result.breakdown.machine.total,
            setup_cost=result.breakdown.setup.total,
            overhead_cost=result.breakdown.overhead.total,
            scrap_cost=result.breakdown.scrap.total,
            total_cogs=result.total_cogs,
            cogs_per_unit=result.cogs_per_unit,
            breakdown_details=result.breakdown.to_dict(),
            status=CalculationStatus.CALCULATED,
            currency_code=result.currency,
            calculated_at=datetime.utcnow(),
            assumptions=result.assumptions,
        )
        
        self.session.add(calculation)
        await self.session.flush()
        return calculation
    
    async def get_calculation(
        self,
        order_id: str,
        version: int = None,
    ) -> Optional[CostCalculation]:
        """Get COGS calculation for an order."""
        query = select(CostCalculation).where(
            and_(
                CostCalculation.order_id == order_id,
                CostCalculation.tenant_id == self.tenant_id,
            )
        )
        
        if version:
            query = query.where(CostCalculation.calculation_version == version)
        else:
            query = query.order_by(CostCalculation.calculation_version.desc())
        
        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none()
    
    async def list_calculations(
        self,
        status: CalculationStatus = None,
        from_date: datetime = None,
        to_date: datetime = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CostCalculation]:
        """List COGS calculations."""
        query = select(CostCalculation).where(
            CostCalculation.tenant_id == self.tenant_id
        )
        
        if status:
            query = query.where(CostCalculation.status == status)
        if from_date:
            query = query.where(CostCalculation.calculated_at >= from_date)
        if to_date:
            query = query.where(CostCalculation.calculated_at <= to_date)
        
        query = query.order_by(CostCalculation.calculated_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def simulate_scenario(
        self,
        base_order_id: str,
        multipliers: CostMultipliers = None,
        volume_multiplier: Decimal = Decimal("1.0"),
        scenario_name: str = "Custom Scenario",
    ) -> ScenarioResult:
        """Run scenario simulation on existing calculation."""
        # Get base calculation
        calculation = await self.get_calculation(base_order_id)
        if not calculation:
            raise ValueError(f"No calculation found for order {base_order_id}")
        
        # Reconstruct COGSResult for simulator (Q.30.0.1 — guarda quantity=0)
        base_result = _reconstruct_base_result(calculation)

        scenario = self._simulator.simulate(
            base_result=base_result,
            multipliers=multipliers,
            volume_multiplier=volume_multiplier,
            scenario_name=scenario_name,
        )

        try:
            from src.shared.kafka_client import EventBase as _EventBase

            await publish_event(
                Topics.SCENARIO_SIMULATED,
                _EventBase(
                    event_type="SCENARIO_SIMULATED",
                    tenant_id=self.tenant_id,
                    source_module="profit",
                    payload={
                        "base_order_id": base_order_id,
                        "scenario_name": scenario_name,
                        "volume_multiplier": float(volume_multiplier),
                        "base_cogs": float(calculation.total_cogs),
                        "scenario_cogs": float(getattr(scenario, "total_cogs", 0) or 0),
                        "delta_eur": float(getattr(scenario, "delta_eur", 0) or 0),
                        "delta_percent": float(getattr(scenario, "delta_percent", 0) or 0),
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover — best-effort
            _logger.warning("SCENARIO_SIMULATED publish failed: %s", exc)

        return scenario

    async def run_sensitivity_analysis(
        self,
        base_order_id: str,
        component: str,
        range_percent: List[int] = None,
    ) -> List[Dict[str, Any]]:
        """Run sensitivity analysis for a component."""
        calculation = await self.get_calculation(base_order_id)
        if not calculation:
            raise ValueError(f"No calculation found for order {base_order_id}")
        
        # Reconstruct COGSResult (Q.30.0.1 — guarda quantity=0)
        base_result = _reconstruct_base_result(calculation)

        variance = self._simulator.sensitivity_analysis(
            base_result=base_result,
            component=component,
            range_percent=range_percent,
        )

        try:
            from src.shared.kafka_client import EventBase as _EventBase

            await publish_event(
                Topics.COST_VARIANCE_CALCULATED,
                _EventBase(
                    event_type="COST_VARIANCE_CALCULATED",
                    tenant_id=self.tenant_id,
                    source_module="profit",
                    payload={
                        "base_order_id": base_order_id,
                        "component": component,
                        "range_percent": range_percent,
                        "base_cogs": float(calculation.total_cogs),
                        "variance_points": len(variance) if hasattr(variance, "__len__") else None,
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover — best-effort
            _logger.warning("COST_VARIANCE_CALCULATED publish failed: %s", exc)

        return variance










