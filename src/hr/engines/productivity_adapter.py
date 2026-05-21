"""
ProdPlan ONE - Productivity Adapter
====================================

Adapter for productivity tracking from base- workforce_analytics.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass
class ProductionRecord:
    """Record of actual production."""
    employee_id: str
    operation_id: str
    order_id: str
    record_date: date
    
    standard_hours: Decimal
    actual_hours: Decimal
    
    standard_quantity: Decimal
    actual_quantity: Decimal
    good_quantity: Decimal
    
    @property
    def efficiency_percent(self) -> Decimal:
        """Calculate efficiency (standard / actual time)."""
        if self.actual_hours > 0:
            return (self.standard_hours / self.actual_hours * 100).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        return Decimal("0")
    
    @property
    def quality_percent(self) -> Decimal:
        """Calculate quality rate (good / actual quantity)."""
        if self.actual_quantity > 0:
            return (self.good_quantity / self.actual_quantity * 100).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        return Decimal("0")
    
    @property
    def oee_percent(self) -> Decimal:
        """Q.62.E.6 — `simplified_oee` por registo, NÃO o OEE factory-wide.

        Cálculo: `efficiency × quality / 100`. **Falta availability** —
        este property funciona ao nível de UMA `ProductionRecord` onde
        não há sinal de paragens/idle time per row. É um proxy útil
        para "este operador, neste registo, foi bom?", não um KPI
        executivo.

        Para o **OEE factory-wide canónico** (availability × performance ×
        quality), usar `src.profit.kpi_factory.KPIFactory.oee(date_from,
        date_to)` que delega para `OEEService.calculate()`.

        Os 2 nomes existem por design — semânticas distintas. Comparáveis
        com `worker_quality_score` vs `factory_defect_rate`: per-pessoa
        vs factory-wide são KPIs diferentes.
        """
        return (self.efficiency_percent * self.quality_percent / 100).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )


@dataclass
class ProductivitySummary:
    """Summary of productivity metrics."""
    employee_id: str
    period_start: date
    period_end: date
    
    total_standard_hours: Decimal
    total_actual_hours: Decimal
    total_standard_quantity: Decimal
    total_actual_quantity: Decimal
    total_good_quantity: Decimal
    
    records_count: int
    
    @property
    def avg_efficiency(self) -> Decimal:
        if self.total_actual_hours > 0:
            return (self.total_standard_hours / self.total_actual_hours * 100).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        return Decimal("0")
    
    @property
    def avg_quality(self) -> Decimal:
        if self.total_actual_quantity > 0:
            return (self.total_good_quantity / self.total_actual_quantity * 100).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        return Decimal("0")
    
    @property
    def bonus_eligible(self) -> bool:
        """Check if eligible for bonus (efficiency > 100% and quality > 98%)."""
        return self.avg_efficiency >= 100 and self.avg_quality >= 98
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "employee_id": self.employee_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_standard_hours": float(self.total_standard_hours),
            "total_actual_hours": float(self.total_actual_hours),
            "avg_efficiency_percent": float(self.avg_efficiency),
            "avg_quality_percent": float(self.avg_quality),
            "records_count": self.records_count,
            "bonus_eligible": self.bonus_eligible,
        }


class ProductivityAdapter:
    """
    Adapter for productivity metrics.
    
    Tracks and calculates employee productivity.
    """
    
    def __init__(self):
        self._records: Dict[str, List[ProductionRecord]] = {}
    
    def add_record(self, record: ProductionRecord) -> None:
        """Add production record."""
        if record.employee_id not in self._records:
            self._records[record.employee_id] = []
        self._records[record.employee_id].append(record)
    
    def get_employee_productivity(
        self,
        employee_id: str,
        from_date: date = None,
        to_date: date = None,
    ) -> ProductivitySummary:
        """Get productivity summary for an employee."""
        records = self._records.get(employee_id, [])
        
        # Filter by date
        if from_date:
            records = [r for r in records if r.record_date >= from_date]
        if to_date:
            records = [r for r in records if r.record_date <= to_date]
        
        if not records:
            return ProductivitySummary(
                employee_id=employee_id,
                period_start=from_date or date.today(),
                period_end=to_date or date.today(),
                total_standard_hours=Decimal("0"),
                total_actual_hours=Decimal("0"),
                total_standard_quantity=Decimal("0"),
                total_actual_quantity=Decimal("0"),
                total_good_quantity=Decimal("0"),
                records_count=0,
            )
        
        return ProductivitySummary(
            employee_id=employee_id,
            period_start=min(r.record_date for r in records),
            period_end=max(r.record_date for r in records),
            total_standard_hours=sum(r.standard_hours for r in records),
            total_actual_hours=sum(r.actual_hours for r in records),
            total_standard_quantity=sum(r.standard_quantity for r in records),
            total_actual_quantity=sum(r.actual_quantity for r in records),
            total_good_quantity=sum(r.good_quantity for r in records),
            records_count=len(records),
        )
    
    def get_team_productivity(
        self,
        employee_ids: List[str],
        from_date: date = None,
        to_date: date = None,
    ) -> Dict[str, Any]:
        """Get productivity for a team."""
        summaries = []
        
        for emp_id in employee_ids:
            summary = self.get_employee_productivity(emp_id, from_date, to_date)
            summaries.append(summary)
        
        # Calculate team averages
        if summaries:
            total_std = sum(s.total_standard_hours for s in summaries)
            total_act = sum(s.total_actual_hours for s in summaries)
            total_qty = sum(s.total_actual_quantity for s in summaries)
            total_good = sum(s.total_good_quantity for s in summaries)
            
            team_efficiency = (total_std / total_act * 100) if total_act > 0 else Decimal("0")
            team_quality = (total_good / total_qty * 100) if total_qty > 0 else Decimal("0")
        else:
            team_efficiency = Decimal("0")
            team_quality = Decimal("0")
        
        return {
            "team_size": len(employee_ids),
            "team_efficiency_percent": float(team_efficiency),
            "team_quality_percent": float(team_quality),
            "individual_summaries": [s.to_dict() for s in summaries],
        }
    
    def calculate_bonus(
        self,
        employee_id: str,
        base_salary: Decimal,
        efficiency_bonus_rate: Decimal = Decimal("0.05"),
        quality_bonus_rate: Decimal = Decimal("0.03"),
        from_date: date = None,
        to_date: date = None,
    ) -> Dict[str, Any]:
        """Calculate performance bonus for employee."""
        summary = self.get_employee_productivity(employee_id, from_date, to_date)
        
        efficiency_bonus = Decimal("0")
        quality_bonus = Decimal("0")
        
        # Efficiency bonus if > 100%
        if summary.avg_efficiency > 100:
            efficiency_bonus = base_salary * efficiency_bonus_rate
        
        # Quality bonus if > 98%
        if summary.avg_quality > 98:
            quality_bonus = base_salary * quality_bonus_rate
        
        total_bonus = efficiency_bonus + quality_bonus
        
        return {
            "employee_id": employee_id,
            "base_salary": float(base_salary),
            "efficiency_percent": float(summary.avg_efficiency),
            "quality_percent": float(summary.avg_quality),
            "efficiency_bonus": float(efficiency_bonus),
            "quality_bonus": float(quality_bonus),
            "total_bonus": float(total_bonus),
            "eligible": summary.bonus_eligible,
        }










