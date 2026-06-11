"""
ProdPlan ONE - CORE API Schemas
================================

Pydantic schemas for request/response validation.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from src.core.models.tenant import TenantStatus, SubscriptionLevel
from src.core.models.product import ProductType, ProductStatus
from src.core.models.machine import MachineStatus, MachineType
from src.core.models.employee import EmploymentStatus, EmploymentType
from src.core.models.partner import CustomerSegment, PaymentTerms, PriceTier, MaterialCategory


# ═══════════════════════════════════════════════════════════════════════════════
# TENANT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class TenantCreate(BaseModel):
    """Create tenant request.

    Sprint S8 / Π10: ``subscription_level`` is no longer accepted from the
    request body. Mass-assigning it would let any caller create themselves
    an ENTERPRISE tenant on signup. Tier upgrades go through a separate
    admin-only endpoint (``PATCH /tenants/{id}/subscription``).
    """
    tenant_name: str = Field(..., min_length=1, max_length=255)
    tenant_code: str = Field(..., min_length=2, max_length=50)
    contact_email: Optional[str] = None
    currency_code: str = Field(default="EUR", max_length=3)
    timezone: str = Field(default="UTC", max_length=50)


class TenantUpdate(BaseModel):
    """Update tenant request."""
    tenant_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = None
    currency_code: Optional[str] = Field(None, max_length=3)
    timezone: Optional[str] = Field(None, max_length=50)


class TenantResponse(BaseModel):
    """Tenant response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    tenant_name: str
    tenant_code: str
    status: TenantStatus
    subscription_level: SubscriptionLevel
    contact_email: Optional[str]
    currency_code: str
    timezone: str
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class ProductCreate(BaseModel):
    """Create product request."""
    product_code: str = Field(..., min_length=1, max_length=50)
    product_name: str = Field(..., min_length=1, max_length=255)
    product_type: ProductType = ProductType.FINISHED_GOOD
    category: Optional[str] = Field(None, max_length=100)
    lead_time_days: int = Field(default=7, ge=0)
    standard_cost: Optional[Decimal] = Field(None, ge=0)


class ProductUpdate(BaseModel):
    """Update product request."""
    product_name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    lead_time_days: Optional[int] = Field(None, ge=0)
    standard_cost: Optional[Decimal] = Field(None, ge=0)
    status: Optional[ProductStatus] = None


class ProductResponse(BaseModel):
    """Product response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    product_code: str
    product_name: str
    product_type: ProductType
    category: Optional[str]
    status: ProductStatus
    lead_time_days: int
    standard_cost: Optional[Decimal]
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# MACHINE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class MachineCreate(BaseModel):
    """Create machine request."""
    machine_code: str = Field(..., min_length=1, max_length=50)
    machine_name: str = Field(..., min_length=1, max_length=255)
    machine_type: MachineType = MachineType.OTHER
    location: Optional[str] = Field(None, max_length=100)
    capacity_units_per_hour: Optional[int] = Field(None, ge=0)
    available_hours_per_day: Decimal = Field(default=Decimal("8.0"), ge=0)


class MachineUpdate(BaseModel):
    """Update machine request."""
    machine_name: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=100)
    capacity_units_per_hour: Optional[int] = Field(None, ge=0)
    status: Optional[MachineStatus] = None


class MachineResponse(BaseModel):
    """Machine response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    machine_code: str
    machine_name: str
    machine_type: MachineType
    status: MachineStatus
    location: Optional[str]
    capacity_units_per_hour: Optional[int]
    available_hours_per_day: Decimal
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# EMPLOYEE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class EmployeeCreate(BaseModel):
    """Create employee request."""
    employee_code: str = Field(..., min_length=1, max_length=50)
    employee_name: str = Field(..., min_length=1, max_length=255)
    hire_date: date
    department: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    base_monthly_salary: Decimal = Field(default=Decimal("0"), ge=0)
    burden_rate: Decimal = Field(default=Decimal("0.32"), ge=0, le=1)


class EmployeeUpdate(BaseModel):
    """Update employee request.

    Sprint Q.3 — `notes` accepts a free-text field. The EmployeesPage UI uses
    it to encode the experience tier as `[tier:JUNIOR|MID|SENIOR|CUSTOM]`
    until a dedicated `experience_tier` column is added.
    """
    employee_name: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    base_monthly_salary: Optional[Decimal] = Field(None, ge=0)
    status: Optional[EmploymentStatus] = None
    notes: Optional[str] = Field(None, max_length=2000)


class EmployeeResponse(BaseModel):
    """Employee response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    employee_code: str
    employee_name: str
    status: EmploymentStatus
    department: Optional[str]
    job_title: Optional[str]
    hire_date: date
    base_monthly_salary: Decimal
    burden_rate: Decimal
    hourly_loaded_rate: Decimal
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# OPERATION SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class OperationCreate(BaseModel):
    """Create operation request."""
    operation_code: str = Field(..., min_length=1, max_length=50)
    operation_name: str = Field(..., min_length=1, max_length=255)
    machine_id: Optional[UUID] = None
    std_time_minutes: Decimal = Field(default=Decimal("0"), ge=0)
    setup_time_minutes: Decimal = Field(default=Decimal("0"), ge=0)
    skills_required: Optional[List[str]] = None


class OperationUpdate(BaseModel):
    """Update operation request."""
    operation_name: Optional[str] = Field(None, max_length=255)
    machine_id: Optional[UUID] = None
    std_time_minutes: Optional[Decimal] = Field(None, ge=0)
    setup_time_minutes: Optional[Decimal] = Field(None, ge=0)
    skills_required: Optional[List[str]] = None


class OperationResponse(BaseModel):
    """Operation response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    operation_code: str
    operation_name: str
    machine_id: Optional[UUID]
    std_time_minutes: Decimal
    std_time_hours: Decimal
    setup_time_minutes: Decimal
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# BOM SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class BOMItemCreate(BaseModel):
    """Create BOM item request.

    F4.E — `quantity_per` é gt=0 (não ge=0): uma linha BOM com 0 unidades
    multiplica a explosão (plan/engines/bom_adapter) para zero em silêncio.
    Linha sem consumo apaga-se, não se zera.
    """
    parent_product_id: UUID
    component_product_id: UUID
    quantity_per: Decimal = Field(..., gt=0)
    unit_of_measure: str = Field(default="UN", max_length=10)
    sequence: int = Field(default=0, ge=0)
    operation_id: Optional[UUID] = None
    scrap_factor: Decimal = Field(default=Decimal("1.0"), ge=1.0)
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    bom_version: int = Field(default=1, ge=1)
    position_ref: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)


class BOMItemUpdate(BaseModel):
    """Update BOM item request. `quantity_per` gt=0 — ver BOMItemCreate."""
    quantity_per: Optional[Decimal] = Field(None, gt=0)
    unit_of_measure: Optional[str] = Field(None, max_length=10)
    sequence: Optional[int] = Field(None, ge=0)
    operation_id: Optional[UUID] = None
    scrap_factor: Optional[Decimal] = Field(None, ge=1.0)
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    bom_version: Optional[int] = Field(None, ge=1)
    position_ref: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)


class BOMItemResponse(BaseModel):
    """BOM item response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    parent_product_id: UUID
    component_product_id: UUID
    quantity_per: Decimal
    unit_of_measure: str
    sequence: int
    operation_id: Optional[UUID]
    scrap_factor: Decimal
    effective_from: Optional[date]
    effective_to: Optional[date]
    bom_version: int
    position_ref: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMER SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class CustomerCreate(BaseModel):
    """Create customer request."""
    customer_code: str = Field(..., min_length=1, max_length=50)
    customer_name: str = Field(..., min_length=1, max_length=255)
    segment: CustomerSegment = CustomerSegment.RETAIL
    payment_terms: PaymentTerms = PaymentTerms.NET30
    price_tier: PriceTier = PriceTier.STANDARD
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    is_active: bool = Field(default=True)
    notes: Optional[str] = None


class CustomerUpdate(BaseModel):
    """Update customer request."""
    customer_name: Optional[str] = Field(None, max_length=255)
    segment: Optional[CustomerSegment] = None
    payment_terms: Optional[PaymentTerms] = None
    price_tier: Optional[PriceTier] = None
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class CustomerResponse(BaseModel):
    """Customer response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    customer_code: str
    customer_name: str
    segment: CustomerSegment
    payment_terms: PaymentTerms
    price_tier: PriceTier
    credit_limit: Optional[Decimal]
    contact_name: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    country: Optional[str]
    is_active: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIER SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class SupplierCreate(BaseModel):
    """Create supplier request."""
    supplier_code: str = Field(..., min_length=1, max_length=50)
    supplier_name: str = Field(..., min_length=1, max_length=255)
    material_category: MaterialCategory = MaterialCategory.OTHER
    lead_time_days: int = Field(default=7, ge=0)
    payment_terms: PaymentTerms = PaymentTerms.NET30
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    quality_rating: Optional[int] = Field(None, ge=1, le=5)
    is_active: bool = Field(default=True)
    is_preferred: bool = Field(default=False)
    notes: Optional[str] = None


class SupplierUpdate(BaseModel):
    """Update supplier request."""
    supplier_name: Optional[str] = Field(None, max_length=255)
    material_category: Optional[MaterialCategory] = None
    lead_time_days: Optional[int] = Field(None, ge=0)
    payment_terms: Optional[PaymentTerms] = None
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    quality_rating: Optional[int] = Field(None, ge=1, le=5)
    is_active: Optional[bool] = None
    is_preferred: Optional[bool] = None
    notes: Optional[str] = None


class SupplierResponse(BaseModel):
    """Supplier response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    supplier_code: str
    supplier_name: str
    material_category: MaterialCategory
    lead_time_days: int
    payment_terms: PaymentTerms
    contact_name: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    country: Optional[str]
    quality_rating: Optional[int]
    is_active: bool
    is_preferred: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# RATE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class LaborRateCreate(BaseModel):
    """Create labor rate request."""
    employee_id: UUID
    base_hourly_rate: Decimal = Field(..., ge=0)
    burden_rate: Decimal = Field(default=Decimal("0.32"), ge=0, le=1)
    effective_date: date
    valid_until: Optional[date] = None


class LaborRateResponse(BaseModel):
    """Labor rate response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    employee_id: UUID
    base_hourly_rate: Decimal
    burden_rate: Decimal
    loaded_rate: Decimal
    effective_date: date
    valid_until: Optional[date]
    currency_code: str


class MachineRateCreate(BaseModel):
    """Create machine rate request."""
    machine_id: UUID
    depreciation_rate: Decimal = Field(default=Decimal("0"), ge=0)
    energy_cost_per_hour: Decimal = Field(default=Decimal("0"), ge=0)
    maintenance_cost_per_hour: Decimal = Field(default=Decimal("0"), ge=0)
    effective_date: date
    valid_until: Optional[date] = None


class MachineRateResponse(BaseModel):
    """Machine rate response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    machine_id: UUID
    depreciation_rate: Decimal
    energy_cost_per_hour: Decimal
    maintenance_cost_per_hour: Decimal
    total_rate: Decimal
    effective_date: date
    valid_until: Optional[date]
    currency_code: str


class OverheadRateCreate(BaseModel):
    """Create overhead rate request."""
    year_month: date
    rent_amount: Decimal = Field(default=Decimal("0"), ge=0)
    utilities_amount: Decimal = Field(default=Decimal("0"), ge=0)
    management_amount: Decimal = Field(default=Decimal("0"), ge=0)
    other_overhead_amount: Decimal = Field(default=Decimal("0"), ge=0)
    total_available_hours: int = Field(..., gt=0)


class OverheadRateResponse(BaseModel):
    """Overhead rate response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    year_month: date
    total_monthly_overhead: Decimal
    total_available_hours: int
    calculated_rate: Decimal
    currency_code: str


# ═══════════════════════════════════════════════════════════════════════════════
# COMMON SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class PaginatedResponse(BaseModel):
    """Paginated list response."""
    items: List
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None



