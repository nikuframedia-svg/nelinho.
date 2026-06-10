"""
ProdPlan ONE - Allocation Service
==================================

Business logic for employee allocation.
"""

import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.hr.models.allocation import HRAllocation, AllocationStatus
from src.hr.engines.allocation_adapter import (
    AllocationAdapter,
    OperationRequirement,
    EmployeeAvailability,
    EmployeeSkill as EngineSkill,
    AllocationResult,
)
from src.core.models.rates import LaborRate
from src.plan.models.order import ProductionOrder
from src.plan.models.schedule import ProductionSchedule
from src.plan.services.operation_resolver import OperationResolver
from src.plan.services.phase_classification import (
    is_completed_phase,
    is_workable_phase,
)
from src.shared.kafka_client import publish_event, Topics
from src.shared.events import EmployeeAllocatedEvent, LaborCostCommittedEvent
from src.shared.time import local_today


class AllocationError(Exception):
    """Base — uma atribuição foi recusada por uma razão de negócio."""


class OrderNotAllocatableError(AllocationError):
    """Ordem inexistente ou já fora do chão de fábrica (→ HTTP 409)."""


class PhaseNotStartedError(AllocationError):
    """Ordem ainda não arrancou — fase 'Pendente'/'Não Laminado' (→ HTTP 422)."""


class AllocationService:
    """
    Service for employee allocation.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
        self._adapter = AllocationAdapter()
    
    async def allocate_employees(
        self,
        requirements: List[Dict[str, Any]],
        employees: List[Dict[str, Any]],
        strategy: str = "skill_first",
    ) -> List[Dict[str, Any]]:
        """
        Allocate employees to operations.

        Sprint Q.12 — corre dentro de transação aninhada que faz lock
        explícito sobre as alocações existentes dos employees envolvidos.
        Sem isto, dois alocadores concorrentes podiam atribuir o mesmo
        funcionário 8h+8h ao mesmo dia (16h impossíveis).

        Args:
            requirements: List of operation requirements
            employees: List of available employees with skills and availability
            strategy: Allocation strategy

        Returns:
            List of allocations
        """
        # Lock existing allocations for involved employees to prevent
        # double-booking under concurrent calls. Keep the lock for the
        # whole transaction so the read used by the adapter and the
        # subsequent INSERTs see a consistent view.
        emp_uuids: List[UUID] = []
        for emp in employees:
            raw = str(emp.get("employee_id", ""))
            if self._is_uuid(raw):
                emp_uuids.append(UUID(raw))

        async with self.session.begin_nested():
            if emp_uuids:
                lock_stmt = (
                    select(HRAllocation.id)
                    .where(
                        and_(
                            HRAllocation.tenant_id == self.tenant_id,
                            HRAllocation.employee_id.in_(emp_uuids),
                            HRAllocation.allocation_date == local_today(),
                        )
                    )
                    .with_for_update()
                )
                await self.session.execute(lock_stmt)

            return await self._do_allocate(requirements, employees, strategy)

    async def _do_allocate(
        self,
        requirements: List[Dict[str, Any]],
        employees: List[Dict[str, Any]],
        strategy: str,
    ) -> List[Dict[str, Any]]:
        # Setup adapter
        for emp in employees:
            emp_id = str(emp.get("employee_id", ""))
            
            # Add employee
            skills = [
                EngineSkill(
                    employee_id=emp_id,
                    skill_code=s.get("skill_code", ""),
                    proficiency_level=int(s.get("proficiency_level", 1)),
                )
                for s in emp.get("skills", [])
            ]
            
            self._adapter.add_employee(
                employee_id=emp_id,
                employee_name=emp.get("employee_name", ""),
                skills=skills,
                hourly_rate=Decimal(str(emp.get("hourly_rate", 10))),
            )
            
            # Add availability
            for avail in emp.get("availability", []):
                avail_date = avail.get("date")
                if isinstance(avail_date, str):
                    avail_date = date.fromisoformat(avail_date)
                
                self._adapter.add_availability(
                    emp_id,
                    EmployeeAvailability(
                        employee_id=emp_id,
                        date=avail_date,
                        available_from=datetime.combine(avail_date, time(8, 0)),
                        available_until=datetime.combine(avail_date, time(17, 0)),
                        already_allocated_hours=Decimal(str(avail.get("already_allocated", 0))),
                    ),
                )
        
        # Build requirements
        reqs = []
        for req in requirements:
            req_date = req.get("scheduled_date")
            if isinstance(req_date, str):
                req_date = date.fromisoformat(req_date)
            
            reqs.append(OperationRequirement(
                operation_id=str(req.get("operation_id", "")),
                order_id=str(req.get("order_id", "")),
                required_hours=Decimal(str(req.get("required_hours", 0))),
                required_skill_codes=req.get("required_skills", []),
                scheduled_date=req_date,
                priority=int(req.get("priority", 1)),
            ))
        
        # Run allocation
        results = self._adapter.allocate(reqs, strategy)
        
        # Save to database
        allocations = []
        total_cost = Decimal("0")
        
        for result in results:
            emp_uuid = self._safe_uuid(result.employee_id)
            op_uuid = self._safe_uuid(result.operation_id)
            if emp_uuid is None or op_uuid is None:
                # Linha do adapter sem identificador válido — skip em vez
                # de gravar `null` na tabela (FK constraint estoiraria
                # de qualquer maneira no flush).
                continue
            allocation = HRAllocation(
                tenant_id=self.tenant_id,
                employee_id=emp_uuid,
                order_id=result.order_id,
                operation_id=op_uuid,
                allocation_date=local_today(),
                allocated_hours=result.allocated_hours,
                hourly_rate=result.hourly_rate,
                estimated_cost=result.estimated_cost,
                status=AllocationStatus.PLANNED,
                skill_match=result.skill_match,
            )
            
            self.session.add(allocation)
            total_cost += result.estimated_cost
            
            allocations.append({
                "allocation_id": str(allocation.id),
                "employee_id": result.employee_id,
                "employee_name": result.employee_name,
                "order_id": result.order_id,
                "operation_id": result.operation_id,
                "allocated_hours": float(result.allocated_hours),
                "hourly_rate": float(result.hourly_rate),
                "estimated_cost": float(result.estimated_cost),
                "skill_match": result.skill_match,
            })
            
            # Publish event
            await self._publish_best_effort(
                Topics.EMPLOYEE_ALLOCATED,
                EmployeeAllocatedEvent(
                    tenant_id=self.tenant_id,
                    payload={
                        "employee_id": result.employee_id,
                        "employee_name": result.employee_name,
                        "order_id": result.order_id,
                        "operation_id": result.operation_id,
                        "allocated_hours": float(result.allocated_hours),
                        "estimated_cost": float(result.estimated_cost),
                    },
                ),
            )
        
        await self.session.flush()
        
        # Publish aggregate event
        orders = set(a["order_id"] for a in allocations)
        for order_id in orders:
            order_allocations = [a for a in allocations if a["order_id"] == order_id]
            order_cost = sum(a["estimated_cost"] for a in order_allocations)
            order_hours = sum(a["allocated_hours"] for a in order_allocations)
            
            await self._publish_best_effort(
                Topics.LABOR_COST_COMMITTED,
                LaborCostCommittedEvent(
                    tenant_id=self.tenant_id,
                    payload={
                        "order_id": order_id,
                        "total_labor_cost": order_cost,
                        "total_hours": order_hours,
                        "employees_assigned": len(order_allocations),
                        "currency": "EUR",
                    },
                ),
            )
        
        return allocations
    
    async def create_single_allocation(
        self,
        employee_id: UUID,
        order_id: str,
        allocation_date: date,
        allocated_hours: Decimal = Decimal("8"),
    ) -> HRAllocation:
        """Q.31.D.2 / Q.55.B — atribui um operador a um barco para um dia.

        O frontend arrasta operador → barco. `HRAllocation.operation_id`
        é FK obrigatória para `core.operations`; resolvemo-la assim:

        * se houver uma `ProductionSchedule` a cobrir o dia, usamos a
          sua operação (a fase agendada mais precisa);
        * senão, resolvemos a operação de routing a partir da FASE
          ACTUAL da ordem (`OperationResolver`) — não exigimos um
          schedule sintético, que raramente cobre hoje.

        Recusa de negócio (Q.55.B):
        * ordem inexistente ou em fase terminal → `OrderNotAllocatableError`
          (a API → 409);
        * ordem ainda não arrancada (fase "Pendente") → `PhaseNotStartedError`
          (a API → 422) — não há operação de trabalho a que atribuir.

        O custo é informativo: `hourly_rate` vem de `core.labor_rates`
        (linha efectiva mais recente até `allocation_date`); operador
        sem taxa entra a 0 — o custo nunca é inventado.
        """
        order = await self._load_order(order_id)
        if order is None:
            raise OrderNotAllocatableError(
                f"Ordem {order_id} não existe — não é possível atribuir."
            )
        phase = order.current_phase_name
        if is_completed_phase(phase):
            raise OrderNotAllocatableError(
                f"Ordem {order_id} já saiu do chão de fábrica "
                f"(fase '{phase}') — não é possível atribuir."
            )
        if not is_workable_phase(phase):
            raise PhaseNotStartedError(
                f"Ordem {order_id} ainda não arrancou (fase '{phase}') — "
                f"não há operação de trabalho a que atribuir um operador."
            )

        # `operation_id`: schedule a cobrir o dia dá a fase exacta; sem
        # ele, resolve-se a operação de routing pela fase actual.
        schedule = await self._resolve_schedule(order_id, allocation_date)
        if schedule is not None:
            operation_id = schedule.operation_id
        else:
            operation = await OperationResolver(
                self.session, self.tenant_id
            ).resolve_phase_operation(phase)
            operation_id = operation.id

        rate = await self._employee_rate(employee_id, allocation_date)
        estimated_cost = allocated_hours * rate

        allocation = HRAllocation(
            tenant_id=self.tenant_id,
            employee_id=employee_id,
            order_id=order_id,
            operation_id=operation_id,
            allocation_date=allocation_date,
            allocated_hours=allocated_hours,
            hourly_rate=rate,
            estimated_cost=estimated_cost,
            status=AllocationStatus.PLANNED,
            skill_match=True,
        )
        self.session.add(allocation)

        await self._publish_best_effort(
            Topics.EMPLOYEE_ALLOCATED,
            EmployeeAllocatedEvent(
                tenant_id=self.tenant_id,
                payload={
                    "employee_id": str(employee_id),
                    "order_id": order_id,
                    "operation_id": str(operation_id),
                    "allocated_hours": float(allocated_hours),
                    "estimated_cost": float(estimated_cost),
                },
            ),
        )

        await self.session.flush()
        return allocation

    async def _load_order(self, order_id: str) -> Optional[ProductionOrder]:
        """Carrega a `ProductionOrder` por id.

        Aceita o `id` UUID (o que o frontend manda) e também o
        `legacy_id` numérico (a chave que o histórico ERP usa). Sem
        match → `None`.
        """
        conditions = []
        parsed = self._safe_uuid(order_id)
        if parsed is not None:
            conditions.append(ProductionOrder.id == parsed)
        if order_id.isdigit():
            conditions.append(ProductionOrder.legacy_id == int(order_id))
        if not conditions:
            return None
        stmt = select(ProductionOrder).where(
            ProductionOrder.tenant_id == self.tenant_id,
            or_(*conditions),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _resolve_schedule(
        self, order_id: str, allocation_date: date
    ) -> Optional[ProductionSchedule]:
        """A fase agendada para `order_id` que cobre `allocation_date`.

        Escolhe a de menor `operation_sequence` — a próxima operação na
        ordem de routing. Sem linha → `None`.
        """
        stmt = (
            select(ProductionSchedule)
            .where(
                ProductionSchedule.tenant_id == self.tenant_id,
                ProductionSchedule.order_id == order_id,
                ProductionSchedule.scheduled_start_date <= allocation_date,
                ProductionSchedule.scheduled_end_date >= allocation_date,
            )
            .order_by(ProductionSchedule.operation_sequence)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def _employee_rate(
        self, employee_id: UUID, as_of: date
    ) -> Decimal:
        """`loaded_rate` efectivo do operador em `as_of`, ou 0 se ausente."""
        stmt = (
            select(LaborRate.loaded_rate)
            .where(
                LaborRate.tenant_id == self.tenant_id,
                LaborRate.employee_id == employee_id,
                LaborRate.effective_date <= as_of,
            )
            .order_by(LaborRate.effective_date.desc())
        )
        result = await self.session.execute(stmt)
        rate = result.scalars().first()
        return rate if rate is not None else Decimal("0")

    async def get_allocations(
        self,
        order_id: str = None,
        employee_id: UUID = None,
        status: AllocationStatus = None,
        from_date: date = None,
        to_date: date = None,
    ) -> List[HRAllocation]:
        """Get allocations with filtering."""
        query = select(HRAllocation).where(
            HRAllocation.tenant_id == self.tenant_id
        )
        
        if order_id:
            query = query.where(HRAllocation.order_id == order_id)
        if employee_id:
            query = query.where(HRAllocation.employee_id == employee_id)
        if status:
            query = query.where(HRAllocation.status == status)
        if from_date:
            query = query.where(HRAllocation.allocation_date >= from_date)
        if to_date:
            query = query.where(HRAllocation.allocation_date <= to_date)
        
        query = query.order_by(HRAllocation.allocation_date)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_allocation_status(
        self,
        allocation_id: UUID,
        status: AllocationStatus,
        actual_hours: Decimal = None,
    ) -> Optional[HRAllocation]:
        """Update allocation status with actuals."""
        result = await self.session.execute(
            select(HRAllocation).where(
                and_(
                    HRAllocation.id == allocation_id,
                    HRAllocation.tenant_id == self.tenant_id,
                )
            )
        )
        allocation = result.scalar_one_or_none()
        
        if not allocation:
            return None
        
        allocation.status = status
        if actual_hours is not None:
            allocation.actual_hours = actual_hours
            allocation.actual_cost = actual_hours * allocation.hourly_rate
        
        await self.session.flush()
        return allocation
    
    async def get_employee_availability(
        self,
        employee_id: UUID,
        from_date: date = None,
        to_date: date = None,
        weekly_capacity_hours: Decimal = Decimal("40"),
    ) -> Dict[str, Any]:
        """Get employee availability considering existing allocations."""
        from_date = from_date or local_today()
        to_date = to_date or from_date + timedelta(weeks=4)

        # Get existing allocations
        allocations = await self.get_allocations(
            employee_id=employee_id,
            from_date=from_date,
            to_date=to_date,
        )
        
        # Calculate daily capacity
        days = (to_date - from_date).days + 1
        weeks = Decimal(str(days / 7))
        total_capacity = weekly_capacity_hours * weeks
        
        allocated = sum(a.allocated_hours for a in allocations)
        available = total_capacity - allocated
        
        return {
            "employee_id": str(employee_id),
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "total_capacity_hours": float(total_capacity),
            "allocated_hours": float(allocated),
            "available_hours": float(max(Decimal("0"), available)),
            "utilization_percent": float(allocated / total_capacity * 100) if total_capacity > 0 else 0,
            "allocations_count": len(allocations),
        }
    
    async def _publish_best_effort(self, topic, event) -> None:
        """Publica um evento sem deixar uma falha do bus rebentar a atribuição.

        Q.55.E.1 — a `HRAllocation` já está na transacção da BD: é a fonte
        de verdade. Um Kafka offline (dev) ou em outage (prod) não pode
        reverter uma atribuição confirmada — o evento é só uma notificação
        a jusante. A falha fica registada para reconciliação posterior.
        """
        try:
            await publish_event(topic, event)
        except Exception as exc:
            logger.warning(
                "publish_event(%s) falhou (best-effort, ignorado): %s",
                topic, exc,
            )

    def _is_uuid(self, value: str) -> bool:
        try:
            UUID(value)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _safe_uuid(value) -> Optional[UUID]:
        """Convert to UUID or return None — no exception leaks."""
        if value is None:
            return None
        try:
            return UUID(str(value))
        except (ValueError, TypeError, AttributeError):
            return None










