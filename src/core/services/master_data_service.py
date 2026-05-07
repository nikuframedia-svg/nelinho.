"""
ProdPlan ONE - Master Data Service
====================================

Business logic for master data management (products, machines, employees, operations).
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, TypeVar, Generic, Type
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.audit import AuditLog
from src.core.models.product import Product, ProductType, ProductStatus
from src.core.models.machine import Machine, MachineStatus
from src.core.models.employee import Employee, EmploymentStatus
from src.core.models.operation import Operation
from src.core.models.bom import BOMItem
from src.core.models.partner import Customer, Supplier
from src.shared.database import TenantBase
from src.shared.kafka_client import publish_event, Topics
from src.shared.events import MasterDataLoadedEvent


def _entity_snapshot(entity: Any) -> Dict[str, Any]:
    """Best-effort serialisation of an ORM row for the audit log.

    Returns a dict of column-name → JSON-friendly value. UUIDs/Decimals/dates
    become strings so the JSONB cast in AuditLog never trips up.
    """
    if entity is None:
        return {}
    table = getattr(entity, "__table__", None)
    if table is None:
        return {}
    out: Dict[str, Any] = {}
    for col in table.columns:
        try:
            v = getattr(entity, col.name)
        except Exception:
            continue
        if v is None or isinstance(v, (str, int, float, bool)):
            out[col.name] = v
        else:
            out[col.name] = str(v)
    return out

T = TypeVar("T", bound=TenantBase)


class BaseCRUDService(Generic[T]):
    """Base CRUD service for tenant-scoped entities."""
    
    def __init__(self, session: AsyncSession, tenant_id: UUID, model_class: Type[T]):
        self.session = session
        self.tenant_id = tenant_id
        self.model_class = model_class
    
    async def get(self, entity_id: UUID) -> Optional[T]:
        """Get entity by ID."""
        result = await self.session.execute(
            select(self.model_class).where(
                and_(
                    self.model_class.id == entity_id,
                    self.model_class.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        **filters,
    ) -> List[T]:
        """List entities with filtering."""
        query = select(self.model_class).where(
            self.model_class.tenant_id == self.tenant_id
        )
        
        for field, value in filters.items():
            if hasattr(self.model_class, field) and value is not None:
                query = query.where(getattr(self.model_class, field) == value)
        
        query = query.limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create(self, entity: T) -> T:
        """Create entity."""
        entity.tenant_id = self.tenant_id
        self.session.add(entity)
        await self.session.flush()
        return entity
    
    async def delete(self, entity_id: UUID) -> bool:
        """Delete entity."""
        entity = await self.get(entity_id)
        if entity:
            await self.session.delete(entity)
            await self.session.flush()
            return True
        return False


class MasterDataService:
    """
    Service for all master data operations.

    Provides typed accessors for each entity type.

    Sprint S7 / Π11: ``actor_id`` is now passed in so every CRUD operation
    can leave an audit row. None means "no human actor" (system seed/import).
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        actor_id: Optional[UUID] = None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.actor_id = actor_id

    async def _audit(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: UUID,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Append a row to ``core.audit_log`` describing this CRUD op.

        Best-effort: a failure here MUST NOT mask the underlying business
        operation (audit row is added to the same transaction; if the
        transaction commits, the audit lands; if it rolls back, the audit
        is rolled back too — which is the right semantic).
        """
        self.session.add(
            AuditLog(
                tenant_id=self.tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                old_values=before,
                new_values=after,
                actor_id=self.actor_id,
                reason=reason,
            )
        )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # PRODUCTS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def create_product(
        self,
        product_code: str,
        product_name: str,
        product_type: ProductType = ProductType.FINISHED_GOOD,
        category: Optional[str] = None,
        lead_time_days: int = 7,
        standard_cost: Optional[Decimal] = None,
    ) -> Product:
        """Create a new product."""
        product = Product(
            tenant_id=self.tenant_id,
            product_code=product_code.upper(),
            product_name=product_name,
            product_type=product_type,
            category=category,
            lead_time_days=lead_time_days,
            standard_cost=standard_cost,
            status=ProductStatus.ACTIVE,
        )

        self.session.add(product)
        await self.session.flush()
        await self._audit(
            action="CREATE",
            entity_type="product",
            entity_id=product.id,
            after=_entity_snapshot(product),
        )
        return product
    
    async def get_product(self, product_id: UUID) -> Optional[Product]:
        """Get product by ID."""
        result = await self.session.execute(
            select(Product).where(
                and_(
                    Product.id == product_id,
                    Product.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_product_by_code(self, product_code: str) -> Optional[Product]:
        """Get product by code."""
        result = await self.session.execute(
            select(Product).where(
                and_(
                    Product.product_code == product_code.upper(),
                    Product.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_products(
        self,
        product_type: Optional[ProductType] = None,
        status: Optional[ProductStatus] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Product]:
        """List products with filtering."""
        query = select(Product).where(Product.tenant_id == self.tenant_id)
        
        if product_type:
            query = query.where(Product.product_type == product_type)
        if status:
            query = query.where(Product.status == status)
        if category:
            query = query.where(Product.category == category)
        
        query = query.order_by(Product.product_code).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # MACHINES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def create_machine(
        self,
        machine_code: str,
        machine_name: str,
        location: Optional[str] = None,
        capacity_units_per_hour: Optional[int] = None,
        available_hours_per_day: Decimal = Decimal("8.0"),
    ) -> Machine:
        """Create a new machine."""
        machine = Machine(
            tenant_id=self.tenant_id,
            machine_code=machine_code.upper(),
            machine_name=machine_name,
            location=location,
            capacity_units_per_hour=capacity_units_per_hour,
            available_hours_per_day=available_hours_per_day,
            status=MachineStatus.ACTIVE,
        )
        
        self.session.add(machine)
        await self.session.flush()
        return machine
    
    async def get_machine(self, machine_id: UUID) -> Optional[Machine]:
        """Get machine by ID."""
        result = await self.session.execute(
            select(Machine).where(
                and_(
                    Machine.id == machine_id,
                    Machine.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_machines(
        self,
        status: Optional[MachineStatus] = None,
        location: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Machine]:
        """List machines with filtering."""
        query = select(Machine).where(Machine.tenant_id == self.tenant_id)
        
        if status:
            query = query.where(Machine.status == status)
        if location:
            query = query.where(Machine.location == location)
        
        query = query.order_by(Machine.machine_code).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # EMPLOYEES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def create_employee(
        self,
        employee_code: str,
        employee_name: str,
        hire_date: date,
        department: Optional[str] = None,
        base_monthly_salary: Decimal = Decimal("0"),
        burden_rate: Decimal = Decimal("0.32"),
    ) -> Employee:
        """Create a new employee."""
        employee = Employee(
            tenant_id=self.tenant_id,
            employee_code=employee_code.upper(),
            employee_name=employee_name,
            hire_date=hire_date,
            department=department,
            base_monthly_salary=base_monthly_salary,
            burden_rate=burden_rate,
            status=EmploymentStatus.ACTIVE,
        )
        
        self.session.add(employee)
        await self.session.flush()
        return employee
    
    async def get_employee(self, employee_id: UUID) -> Optional[Employee]:
        """Get employee by ID."""
        result = await self.session.execute(
            select(Employee).where(
                and_(
                    Employee.id == employee_id,
                    Employee.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_employees(
        self,
        status: Optional[EmploymentStatus] = None,
        department: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Employee]:
        """List employees with filtering."""
        query = select(Employee).where(Employee.tenant_id == self.tenant_id)
        
        if status:
            query = query.where(Employee.status == status)
        if department:
            query = query.where(Employee.department == department)
        
        query = query.order_by(Employee.employee_name).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def create_operation(
        self,
        operation_code: str,
        operation_name: str,
        machine_id: Optional[UUID] = None,
        std_time_minutes: Decimal = Decimal("0"),
        setup_time_minutes: Decimal = Decimal("0"),
        skills_required: Optional[list] = None,
    ) -> Operation:
        """Create a new operation."""
        operation = Operation(
            tenant_id=self.tenant_id,
            operation_code=operation_code.upper(),
            operation_name=operation_name,
            machine_id=machine_id,
            std_time_minutes=std_time_minutes,
            std_time_hours=std_time_minutes / 60,
            setup_time_minutes=setup_time_minutes,
            skills_required={"skills": skills_required or []},
        )
        
        self.session.add(operation)
        await self.session.flush()
        return operation
    
    async def get_operation(self, operation_id: UUID) -> Optional[Operation]:
        """Get operation by ID."""
        result = await self.session.execute(
            select(Operation).where(
                and_(
                    Operation.id == operation_id,
                    Operation.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_operations(
        self,
        machine_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Operation]:
        """List operations with filtering."""
        query = select(Operation).where(Operation.tenant_id == self.tenant_id)
        
        if machine_id:
            query = query.where(Operation.machine_id == machine_id)
        
        query = query.order_by(Operation.operation_code).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # BOM
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def add_bom_item(
        self,
        parent_product_id: UUID,
        component_product_id: UUID,
        quantity_per: Decimal,
        sequence: int = 0,
        scrap_factor: Decimal = Decimal("1.0"),
    ) -> BOMItem:
        """Add BOM item."""
        bom_item = BOMItem(
            tenant_id=self.tenant_id,
            parent_product_id=parent_product_id,
            component_product_id=component_product_id,
            quantity_per=quantity_per,
            sequence=sequence,
            scrap_factor=scrap_factor,
        )
        
        self.session.add(bom_item)
        await self.session.flush()
        return bom_item
    
    async def get_bom(self, parent_product_id: UUID) -> List[BOMItem]:
        """Get BOM for a product."""
        result = await self.session.execute(
            select(BOMItem).where(
                and_(
                    BOMItem.parent_product_id == parent_product_id,
                    BOMItem.tenant_id == self.tenant_id,
                )
            ).order_by(BOMItem.sequence)
        )
        return list(result.scalars().all())
    
    async def get_bom_item(self, bom_id: UUID) -> Optional[BOMItem]:
        """Get BOM item by ID."""
        result = await self.session.execute(
            select(BOMItem).where(
                and_(
                    BOMItem.id == bom_id,
                    BOMItem.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def delete_bom_item(self, bom_id: UUID) -> bool:
        """Delete BOM item."""
        bom_item = await self.get_bom_item(bom_id)
        if bom_item:
            await self.session.delete(bom_item)
            await self.session.flush()
            return True
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # CUSTOMERS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def create_customer(
        self,
        customer_code: str,
        customer_name: str,
        segment: str = "RETAIL",
        payment_terms: str = "NET30",
        price_tier: str = "STANDARD",
        credit_limit: Optional[Decimal] = None,
        contact_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
        address_line1: Optional[str] = None,
        address_line2: Optional[str] = None,
        city: Optional[str] = None,
        postal_code: Optional[str] = None,
        country: Optional[str] = None,
        is_active: bool = True,
        notes: Optional[str] = None,
    ) -> Customer:
        """Create a new customer."""
        from src.core.models.partner import CustomerSegment, PaymentTerms, PriceTier
        
        customer = Customer(
            tenant_id=self.tenant_id,
            customer_code=customer_code.upper(),
            customer_name=customer_name,
            segment=CustomerSegment(segment),
            payment_terms=PaymentTerms(payment_terms),
            price_tier=PriceTier(price_tier),
            credit_limit=credit_limit,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            postal_code=postal_code,
            country=country,
            is_active=is_active,
            notes=notes,
        )
        
        self.session.add(customer)
        await self.session.flush()
        return customer
    
    async def get_customer(self, customer_id: UUID) -> Optional[Customer]:
        """Get customer by ID."""
        result = await self.session.execute(
            select(Customer).where(
                and_(
                    Customer.id == customer_id,
                    Customer.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_customers(
        self,
        segment: Optional[str] = None,
        is_active: Optional[bool] = None,
        price_tier: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Customer]:
        """List customers with filtering."""
        from src.core.models.partner import CustomerSegment, PriceTier
        
        query = select(Customer).where(Customer.tenant_id == self.tenant_id)
        
        if segment:
            query = query.where(Customer.segment == CustomerSegment(segment))
        if is_active is not None:
            query = query.where(Customer.is_active == is_active)
        if price_tier:
            query = query.where(Customer.price_tier == PriceTier(price_tier))
        
        query = query.order_by(Customer.customer_code).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_customer(
        self,
        customer_id: UUID,
        **updates,
    ) -> Optional[Customer]:
        """Update customer."""
        from src.core.models.partner import CustomerSegment, PaymentTerms, PriceTier
        
        customer = await self.get_customer(customer_id)
        if not customer:
            return None
        
        for key, value in updates.items():
            if value is not None and hasattr(customer, key):
                if key == "segment" and isinstance(value, str):
                    setattr(customer, key, CustomerSegment(value))
                elif key == "payment_terms" and isinstance(value, str):
                    setattr(customer, key, PaymentTerms(value))
                elif key == "price_tier" and isinstance(value, str):
                    setattr(customer, key, PriceTier(value))
                else:
                    setattr(customer, key, value)
        
        await self.session.flush()
        return customer
    
    async def delete_customer(self, customer_id: UUID) -> bool:
        """Soft delete customer (set is_active=False)."""
        customer = await self.get_customer(customer_id)
        if customer:
            customer.is_active = False
            await self.session.flush()
            return True
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SUPPLIERS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def create_supplier(
        self,
        supplier_code: str,
        supplier_name: str,
        material_category: str = "OTHER",
        lead_time_days: int = 7,
        payment_terms: str = "NET30",
        contact_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
        address_line1: Optional[str] = None,
        address_line2: Optional[str] = None,
        city: Optional[str] = None,
        postal_code: Optional[str] = None,
        country: Optional[str] = None,
        quality_rating: Optional[int] = None,
        is_active: bool = True,
        is_preferred: bool = False,
        notes: Optional[str] = None,
    ) -> Supplier:
        """Create a new supplier."""
        from src.core.models.partner import MaterialCategory, PaymentTerms
        
        supplier = Supplier(
            tenant_id=self.tenant_id,
            supplier_code=supplier_code.upper(),
            supplier_name=supplier_name,
            material_category=MaterialCategory(material_category),
            lead_time_days=lead_time_days,
            payment_terms=PaymentTerms(payment_terms),
            contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            postal_code=postal_code,
            country=country,
            quality_rating=quality_rating,
            is_active=is_active,
            is_preferred=is_preferred,
            notes=notes,
        )
        
        self.session.add(supplier)
        await self.session.flush()
        return supplier
    
    async def get_supplier(self, supplier_id: UUID) -> Optional[Supplier]:
        """Get supplier by ID."""
        result = await self.session.execute(
            select(Supplier).where(
                and_(
                    Supplier.id == supplier_id,
                    Supplier.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_suppliers(
        self,
        material_category: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_preferred: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Supplier]:
        """List suppliers with filtering."""
        from src.core.models.partner import MaterialCategory
        
        query = select(Supplier).where(Supplier.tenant_id == self.tenant_id)
        
        if material_category:
            query = query.where(Supplier.material_category == MaterialCategory(material_category))
        if is_active is not None:
            query = query.where(Supplier.is_active == is_active)
        if is_preferred is not None:
            query = query.where(Supplier.is_preferred == is_preferred)
        
        query = query.order_by(Supplier.supplier_code).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_supplier(
        self,
        supplier_id: UUID,
        **updates,
    ) -> Optional[Supplier]:
        """Update supplier."""
        from src.core.models.partner import MaterialCategory, PaymentTerms
        
        supplier = await self.get_supplier(supplier_id)
        if not supplier:
            return None
        
        for key, value in updates.items():
            if value is not None and hasattr(supplier, key):
                if key == "material_category" and isinstance(value, str):
                    setattr(supplier, key, MaterialCategory(value))
                elif key == "payment_terms" and isinstance(value, str):
                    setattr(supplier, key, PaymentTerms(value))
                else:
                    setattr(supplier, key, value)
        
        await self.session.flush()
        return supplier
    
    async def delete_supplier(self, supplier_id: UUID) -> bool:
        """Soft delete supplier (set is_active=False)."""
        supplier = await self.get_supplier(supplier_id)
        if supplier:
            supplier.is_active = False
            await self.session.flush()
            return True
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # UPDATE/DELETE METHODS FOR EXISTING ENTITIES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def update_product(
        self,
        product_id: UUID,
        **updates,
    ) -> Optional[Product]:
        """Update product."""
        product = await self.get_product(product_id)
        if not product:
            return None

        before = _entity_snapshot(product)
        for key, value in updates.items():
            if value is not None and hasattr(product, key):
                setattr(product, key, value)

        await self.session.flush()
        await self._audit(
            action="UPDATE",
            entity_type="product",
            entity_id=product.id,
            before=before,
            after=_entity_snapshot(product),
        )
        return product

    async def delete_product(self, product_id: UUID) -> bool:
        """Delete product."""
        product = await self.get_product(product_id)
        if product:
            before = _entity_snapshot(product)
            entity_id = product.id
            await self.session.delete(product)
            await self.session.flush()
            await self._audit(
                action="DELETE",
                entity_type="product",
                entity_id=entity_id,
                before=before,
            )
            return True
        return False
    
    async def update_machine(
        self,
        machine_id: UUID,
        **updates,
    ) -> Optional[Machine]:
        """Update machine."""
        machine = await self.get_machine(machine_id)
        if not machine:
            return None
        
        for key, value in updates.items():
            if value is not None and hasattr(machine, key):
                setattr(machine, key, value)
        
        await self.session.flush()
        return machine
    
    async def delete_machine(self, machine_id: UUID) -> bool:
        """Delete machine."""
        machine = await self.get_machine(machine_id)
        if machine:
            await self.session.delete(machine)
            await self.session.flush()
            return True
        return False
    
    async def update_employee(
        self,
        employee_id: UUID,
        **updates,
    ) -> Optional[Employee]:
        """Update employee."""
        employee = await self.get_employee(employee_id)
        if not employee:
            return None
        
        for key, value in updates.items():
            if value is not None and hasattr(employee, key):
                setattr(employee, key, value)
        
        await self.session.flush()
        return employee
    
    async def delete_employee(self, employee_id: UUID) -> bool:
        """Delete employee."""
        employee = await self.get_employee(employee_id)
        if employee:
            await self.session.delete(employee)
            await self.session.flush()
            return True
        return False
    
    async def update_operation(
        self,
        operation_id: UUID,
        **updates,
    ) -> Optional[Operation]:
        """Update operation."""
        operation = await self.get_operation(operation_id)
        if not operation:
            return None
        
        for key, value in updates.items():
            if value is not None and hasattr(operation, key):
                if key == "skills_required" and isinstance(value, list):
                    operation.skills_required = {"skills": value}
                elif key == "std_time_minutes" and value is not None:
                    operation.std_time_minutes = value
                    operation.std_time_hours = value / 60
                else:
                    setattr(operation, key, value)
        
        await self.session.flush()
        return operation
    
    async def delete_operation(self, operation_id: UUID) -> bool:
        """Delete operation."""
        operation = await self.get_operation(operation_id)
        if operation:
            await self.session.delete(operation)
            await self.session.flush()
            return True
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # BULK OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def sync_master_data(self, entity_type: str, count: int) -> None:
        """Publish event after master data sync."""
        await publish_event(
            Topics.MASTER_DATA_LOADED,
            MasterDataLoadedEvent(
                tenant_id=self.tenant_id,
                payload={
                    "entity_type": entity_type,
                    "count": count,
                    "sync_type": "incremental",
                },
            ),
        )



