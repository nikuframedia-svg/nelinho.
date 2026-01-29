"""
ProdPlan ONE - Scenario Simulator
==================================

What-if analysis for cost sensitivity and margin projections.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from .cogs_calculator import COGSResult, CostBreakdown


@dataclass
class CostMultipliers:
    """Multipliers for cost components."""
    material: Decimal = Decimal("1.0")
    labor: Decimal = Decimal("1.0")
    machine: Decimal = Decimal("1.0")
    overhead: Decimal = Decimal("1.0")
    scrap: Decimal = Decimal("1.0")
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "material": float(self.material),
            "labor": float(self.labor),
            "machine": float(self.machine),
            "overhead": float(self.overhead),
            "scrap": float(self.scrap),
        }


@dataclass
class ScenarioResult:
    """Result of scenario simulation."""
    scenario_name: str
    scenario_description: str
    
    base_cogs_per_unit: Decimal
    scenario_cogs_per_unit: Decimal
    delta_amount: Decimal
    delta_percent: Decimal
    
    multipliers: CostMultipliers
    volume_multiplier: Decimal
    
    base_breakdown: Dict[str, float]
    scenario_breakdown: Dict[str, float]
    
    impact_analysis: Dict[str, Any]
    recommendation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "scenario_description": self.scenario_description,
            "base_cogs_per_unit": float(self.base_cogs_per_unit),
            "scenario_cogs_per_unit": float(self.scenario_cogs_per_unit),
            "delta_amount": float(self.delta_amount),
            "delta_percent": float(self.delta_percent),
            "multipliers": self.multipliers.to_dict(),
            "volume_multiplier": float(self.volume_multiplier),
            "base_breakdown": self.base_breakdown,
            "scenario_breakdown": self.scenario_breakdown,
            "impact_analysis": self.impact_analysis,
            "recommendation": self.recommendation,
        }


class ScenarioSimulator:
    """
    Scenario Simulator.
    
    Performs what-if analysis on COGS calculations.
    """
    
    # Predefined scenarios
    SCENARIOS = {
        "steel_increase_10": {
            "name": "Steel Price +10%",
            "description": "Simulate 10% increase in steel prices",
            "multipliers": CostMultipliers(material=Decimal("1.10")),
        },
        "steel_increase_20": {
            "name": "Steel Price +20%",
            "description": "Simulate 20% increase in steel prices",
            "multipliers": CostMultipliers(material=Decimal("1.20")),
        },
        "labor_increase_15": {
            "name": "Labor Cost +15%",
            "description": "Simulate 15% increase in labor costs",
            "multipliers": CostMultipliers(labor=Decimal("1.15")),
        },
        "energy_increase_25": {
            "name": "Energy Cost +25%",
            "description": "Simulate 25% increase in energy (machine) costs",
            "multipliers": CostMultipliers(machine=Decimal("1.25")),
        },
        "volume_double": {
            "name": "Double Volume",
            "description": "Simulate impact of doubling production volume",
            "multipliers": CostMultipliers(),
            "volume_multiplier": Decimal("2.0"),
        },
        "efficiency_improvement": {
            "name": "10% Efficiency Improvement",
            "description": "Simulate 10% improvement in labor and machine efficiency",
            "multipliers": CostMultipliers(
                labor=Decimal("0.90"),
                machine=Decimal("0.90"),
            ),
        },
        "scrap_reduction": {
            "name": "Scrap Reduction 50%",
            "description": "Simulate 50% reduction in scrap rate",
            "multipliers": CostMultipliers(scrap=Decimal("0.50")),
        },
        "worst_case": {
            "name": "Worst Case",
            "description": "All costs increase 15%",
            "multipliers": CostMultipliers(
                material=Decimal("1.15"),
                labor=Decimal("1.15"),
                machine=Decimal("1.15"),
                overhead=Decimal("1.15"),
                scrap=Decimal("1.15"),
            ),
        },
    }
    
    def simulate(
        self,
        base_result: COGSResult,
        multipliers: CostMultipliers = None,
        volume_multiplier: Decimal = Decimal("1.0"),
        scenario_name: str = "Custom Scenario",
        scenario_description: str = "",
    ) -> ScenarioResult:
        """
        Simulate scenario with cost multipliers.
        
        Args:
            base_result: Base COGS calculation result
            multipliers: Cost component multipliers
            volume_multiplier: Volume change factor
            scenario_name: Name of the scenario
            scenario_description: Description
        
        Returns:
            ScenarioResult with comparison
        """
        multipliers = multipliers or CostMultipliers()
        volume_multiplier = Decimal(str(volume_multiplier))
        
        # Extract base breakdown
        base = base_result.breakdown
        base_cogs = base_result.cogs_per_unit
        
        # Apply multipliers
        new_material = base.material.total * multipliers.material
        new_labor = base.labor.total * multipliers.labor
        new_machine = base.machine.total * multipliers.machine
        new_overhead = base.overhead.total * multipliers.overhead
        new_scrap = base.scrap.total * multipliers.scrap
        
        # Setup doesn't usually scale with simple multipliers
        new_setup = base.setup.total
        
        # If volume changes, fixed costs spread differently
        new_quantity = base_result.quantity * volume_multiplier
        
        # Recalculate per-unit
        new_total = (
            new_material + new_labor + new_machine +
            new_setup + new_overhead + new_scrap
        )
        
        # For volume scenarios, setup is fixed so per-unit changes
        if volume_multiplier != Decimal("1.0"):
            # Setup per unit decreases with volume
            setup_per_unit = base.setup.total / new_quantity
            material_per_unit = new_material / new_quantity
            labor_per_unit = new_labor / new_quantity
            machine_per_unit = new_machine / new_quantity
            overhead_per_unit = new_overhead / new_quantity
            scrap_per_unit = new_scrap / new_quantity
            
            new_cogs_per_unit = (
                material_per_unit + labor_per_unit + machine_per_unit +
                setup_per_unit + overhead_per_unit + scrap_per_unit
            )
        else:
            new_cogs_per_unit = new_total / base_result.quantity
        
        new_cogs_per_unit = new_cogs_per_unit.quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        
        # Calculate delta
        delta_amount = new_cogs_per_unit - base_cogs
        delta_percent = (delta_amount / base_cogs * 100) if base_cogs > 0 else Decimal("0")
        delta_percent = delta_percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Build breakdowns
        base_breakdown = {
            "material": float(base.material.per_unit),
            "labor": float(base.labor.per_unit),
            "machine": float(base.machine.per_unit),
            "setup": float(base.setup.per_unit),
            "overhead": float(base.overhead.per_unit),
            "scrap": float(base.scrap.per_unit),
        }
        
        if volume_multiplier != Decimal("1.0"):
            scenario_breakdown = {
                "material": float(material_per_unit),
                "labor": float(labor_per_unit),
                "machine": float(machine_per_unit),
                "setup": float(setup_per_unit),
                "overhead": float(overhead_per_unit),
                "scrap": float(scrap_per_unit),
            }
        else:
            scenario_breakdown = {
                "material": float((new_material / base_result.quantity)),
                "labor": float((new_labor / base_result.quantity)),
                "machine": float((new_machine / base_result.quantity)),
                "setup": float((new_setup / base_result.quantity)),
                "overhead": float((new_overhead / base_result.quantity)),
                "scrap": float((new_scrap / base_result.quantity)),
            }
        
        # Impact analysis
        impact = self._analyze_impact(
            base_breakdown, scenario_breakdown, delta_percent
        )
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            delta_percent, multipliers, volume_multiplier
        )
        
        return ScenarioResult(
            scenario_name=scenario_name,
            scenario_description=scenario_description,
            base_cogs_per_unit=base_cogs,
            scenario_cogs_per_unit=new_cogs_per_unit,
            delta_amount=delta_amount,
            delta_percent=delta_percent,
            multipliers=multipliers,
            volume_multiplier=volume_multiplier,
            base_breakdown=base_breakdown,
            scenario_breakdown=scenario_breakdown,
            impact_analysis=impact,
            recommendation=recommendation,
        )
    
    def run_predefined_scenario(
        self,
        base_result: COGSResult,
        scenario_key: str,
    ) -> ScenarioResult:
        """Run a predefined scenario."""
        if scenario_key not in self.SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario_key}")
        
        scenario_def = self.SCENARIOS[scenario_key]
        
        return self.simulate(
            base_result=base_result,
            multipliers=scenario_def.get("multipliers", CostMultipliers()),
            volume_multiplier=Decimal(str(scenario_def.get("volume_multiplier", "1.0"))),
            scenario_name=scenario_def["name"],
            scenario_description=scenario_def["description"],
        )
    
    def run_all_scenarios(
        self,
        base_result: COGSResult,
    ) -> List[ScenarioResult]:
        """Run all predefined scenarios."""
        results = []
        for key in self.SCENARIOS:
            results.append(self.run_predefined_scenario(base_result, key))
        return results
    
    def sensitivity_analysis(
        self,
        base_result: COGSResult,
        component: str,
        range_percent: List[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run sensitivity analysis for a single component.
        
        Args:
            base_result: Base COGS result
            component: Component to vary (material, labor, machine, etc.)
            range_percent: Percent changes to simulate
        
        Returns:
            List of scenario results
        """
        range_percent = range_percent or [-20, -10, 0, 10, 20, 30]
        results = []
        
        for pct in range_percent:
            multiplier = Decimal(str(1 + pct / 100))
            
            mult = CostMultipliers()
            setattr(mult, component, multiplier)
            
            scenario = self.simulate(
                base_result=base_result,
                multipliers=mult,
                scenario_name=f"{component.title()} {pct:+d}%",
                scenario_description=f"Simulate {pct:+d}% change in {component} cost",
            )
            
            results.append({
                "percent_change": pct,
                "cogs_per_unit": float(scenario.scenario_cogs_per_unit),
                "delta_percent": float(scenario.delta_percent),
            })
        
        return results
    
    def _analyze_impact(
        self,
        base: Dict[str, float],
        scenario: Dict[str, float],
        total_delta_percent: Decimal,
    ) -> Dict[str, Any]:
        """Analyze impact by component."""
        contributions = {}
        
        base_total = sum(base.values())
        
        for component in base:
            base_val = base[component]
            scen_val = scenario[component]
            delta = scen_val - base_val
            
            contributions[component] = {
                "base": base_val,
                "scenario": scen_val,
                "delta": delta,
                "contribution_percent": (delta / base_total * 100) if base_total > 0 else 0,
            }
        
        # Find most significant contributor
        max_contributor = max(
            contributions.keys(),
            key=lambda k: abs(contributions[k]["delta"]),
        )
        
        return {
            "components": contributions,
            "primary_driver": max_contributor,
            "total_delta_percent": float(total_delta_percent),
        }
    
    def _generate_recommendation(
        self,
        delta_percent: Decimal,
        multipliers: CostMultipliers,
        volume_multiplier: Decimal,
    ) -> str:
        """Generate recommendation based on scenario."""
        if delta_percent > 10:
            severity = "significant cost increase"
            action = "Consider hedging strategies or price adjustments"
        elif delta_percent > 5:
            severity = "moderate cost increase"
            action = "Monitor closely and review supplier contracts"
        elif delta_percent > 0:
            severity = "minor cost increase"
            action = "Absorb or pass through gradually"
        elif delta_percent < -5:
            severity = "cost reduction opportunity"
            action = "Potential for margin improvement or competitive pricing"
        else:
            severity = "minimal impact"
            action = "No immediate action required"
        
        if volume_multiplier > Decimal("1.5"):
            action += ". Volume increase shows economies of scale benefit."
        
        return f"This scenario shows a {severity} ({float(delta_percent):+.1f}%). {action}"










