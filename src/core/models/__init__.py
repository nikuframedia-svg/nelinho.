# ProdPlan ONE - CORE Models
"""
CORE Module Models
==================

Database models for:
- Tenants (multi-tenancy)
- Products (master data)
- Machines (master data)
- Employees (master data)
- Operations (standard operations)
- BOM Items (bill of materials)
- Customers & Suppliers
- Rates (labor, machine, overhead)
- Audit Log
"""

from .tenant import Tenant
from .tenant_configuration import TenantConfiguration
from .product import Product
from .machine import Machine
from .employee import Employee
from .operation import Operation
from .bom import BOMItem
from .rates import LaborRate, MachineRate, OverheadRate
from .partner import Customer, Supplier
from .audit import AuditLog

__all__ = [
    "Tenant",
    "TenantConfiguration",
    "Product",
    "Machine",
    "Employee",
    "Operation",
    "BOMItem",
    "LaborRate",
    "MachineRate",
    "OverheadRate",
    "Customer",
    "Supplier",
    "AuditLog",
]










