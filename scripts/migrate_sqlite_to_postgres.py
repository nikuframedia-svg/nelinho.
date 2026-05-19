#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL
=======================================

This script migrates orders and allocations from the legacy SQLite database
to the new PostgreSQL database.
"""

import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shared.database import async_session_factory, init_db
from src.plan.models.order import ProductionOrder, OrderStatus
from src.hr.models.legacy_allocation import LegacyAllocation
from src.shared.config import settings

# SQLite database path
SQLITE_DB_PATH = Path(__file__).parent.parent / "backend" / "prodplan.db"
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def get_sqlite_connection():
    """Get SQLite connection."""
    if not SQLITE_DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {SQLITE_DB_PATH}")
    
    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_orders_from_sqlite() -> List[Dict]:
    """Get all orders from SQLite."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            id, product_id, product_name, product_type,
            current_phase_id, current_phase_name,
            created_date, completed_date, transport_date, status
        FROM orders
        ORDER BY id
    """)
    
    orders = []
    for row in cursor.fetchall():
        orders.append({
            "legacy_id": row["id"],
            "product_id": row["product_id"],
            "product_name": row["product_name"] or "Unknown",
            "product_type": row["product_type"] or "Other",
            "current_phase_id": row["current_phase_id"],
            "current_phase_name": row["current_phase_name"] or "Unknown",
            "created_date": row["created_date"],
            "completed_date": row["completed_date"],
            "transport_date": row["transport_date"],
            "status": row["status"] or "IN_PROGRESS",
        })
    
    conn.close()
    return orders


def get_allocations_from_sqlite() -> List[Dict]:
    """Get all allocations from SQLite."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            id, order_id, phase_id, phase_name,
            employee_id, employee_name, is_leader,
            start_date, end_date
        FROM allocations
        ORDER BY id
    """)
    
    allocations = []
    for row in cursor.fetchall():
        allocations.append({
            "id": row["id"],
            "order_id": row["order_id"],
            "phase_id": row["phase_id"],
            "phase_name": row["phase_name"] or "Unknown",
            "employee_id": row["employee_id"],
            "employee_name": row["employee_name"] or "Unknown",
            "is_leader": bool(row["is_leader"]) if row["is_leader"] is not None else False,
            "start_date": row["start_date"],
            "end_date": row["end_date"],
        })
    
    conn.close()
    return allocations


async def migrate_orders(session: AsyncSession, tenant_id: UUID, orders: List[Dict], batch_size: int = 1000):
    """Migrate orders to PostgreSQL."""
    print(f"\n📦 Migrating {len(orders):,} orders...")
    
    # Check existing orders
    result = await session.execute(
        select(ProductionOrder).where(ProductionOrder.tenant_id == tenant_id)
    )
    existing_orders = {order.legacy_id for order in result.scalars().all()}
    
    new_orders = []
    skipped = 0
    
    for order_data in orders:
        legacy_id = order_data["legacy_id"]
        
        # Skip if already exists
        if legacy_id in existing_orders:
            skipped += 1
            continue
        
        # Parse dates
        created_date = None
        if order_data["created_date"]:
            try:
                created_date = datetime.fromisoformat(order_data["created_date"]).date()
            except:
                pass
        
        completed_date = None
        if order_data["completed_date"]:
            try:
                completed_date = datetime.fromisoformat(order_data["completed_date"]).date()
            except:
                pass
        
        transport_date = None
        if order_data["transport_date"]:
            try:
                transport_date = datetime.fromisoformat(order_data["transport_date"]).date()
            except:
                pass
        
        # Parse status — Q.54.B: o status do SQLite legacy estava preso em
        # IN_PROGRESS para todas as ordens, mesmo as "Entregue"/"Armazém".
        # Deriva-se da fase: uma ordem em fase terminal é COMPLETED. Um
        # CANCELLED explícito do legacy é respeitado.
        from src.plan.services.phase_classification import phase_status

        status = phase_status(order_data["current_phase_name"])
        if order_data["status"]:
            try:
                legacy_status = OrderStatus(order_data["status"])
                if legacy_status == OrderStatus.CANCELLED:
                    status = OrderStatus.CANCELLED
            except (ValueError, KeyError):
                pass
        
        order = ProductionOrder(
            tenant_id=tenant_id,
            legacy_id=legacy_id,
            product_id=order_data["product_id"],
            product_name=order_data["product_name"],
            product_type=order_data["product_type"],
            current_phase_id=order_data["current_phase_id"],
            current_phase_name=order_data["current_phase_name"],
            created_date=created_date,
            completed_date=completed_date,
            transport_date=transport_date,
            status=status,
        )
        
        new_orders.append(order)
        
        # Batch insert
        if len(new_orders) >= batch_size:
            session.add_all(new_orders)
            await session.flush()
            print(f"  ✓ Inserted {len(new_orders):,} orders (skipped {skipped:,})")
            new_orders = []
    
    # Insert remaining
    if new_orders:
        session.add_all(new_orders)
        await session.flush()
        print(f"  ✓ Inserted {len(new_orders):,} orders (skipped {skipped:,})")
    
    await session.commit()
    print(f"✅ Migrated {len(orders) - skipped:,} orders (skipped {skipped:,} duplicates)")


async def migrate_allocations(session: AsyncSession, tenant_id: UUID, allocations: List[Dict], batch_size: int = 1000):
    """Migrate allocations to PostgreSQL."""
    print(f"\n👥 Migrating {len(allocations):,} allocations...")
    
    # Check existing allocations (by employee_id, order_id, phase_name, start_date)
    result = await session.execute(
        select(LegacyAllocation).where(LegacyAllocation.tenant_id == tenant_id)
    )
    existing = {
        (a.employee_id, a.order_id, a.phase_name, a.start_date)
        for a in result.scalars().all()
    }
    
    new_allocations = []
    skipped = 0
    
    for alloc_data in allocations:
        # Create unique key
        start_date = None
        if alloc_data["start_date"]:
            try:
                start_date = datetime.fromisoformat(alloc_data["start_date"]).date()
            except:
                pass
        
        unique_key = (
            alloc_data["employee_id"],
            alloc_data["order_id"],
            alloc_data["phase_name"],
            start_date,
        )
        
        # Skip if already exists
        if unique_key in existing:
            skipped += 1
            continue
        
        # Parse dates
        end_date = None
        if alloc_data["end_date"]:
            try:
                end_date = datetime.fromisoformat(alloc_data["end_date"]).date()
            except:
                pass
        
        allocation = LegacyAllocation(
            tenant_id=tenant_id,
            order_id=alloc_data["order_id"],
            phase_id=alloc_data["phase_id"],
            phase_name=alloc_data["phase_name"],
            employee_id=alloc_data["employee_id"],
            employee_name=alloc_data["employee_name"],
            is_leader=alloc_data["is_leader"],
            start_date=start_date,
            end_date=end_date,
        )
        
        new_allocations.append(allocation)
        
        # Batch insert
        if len(new_allocations) >= batch_size:
            session.add_all(new_allocations)
            await session.flush()
            print(f"  ✓ Inserted {len(new_allocations):,} allocations (skipped {skipped:,})")
            new_allocations = []
    
    # Insert remaining
    if new_allocations:
        session.add_all(new_allocations)
        await session.flush()
        print(f"  ✓ Inserted {len(new_allocations):,} allocations (skipped {skipped:,})")
    
    await session.commit()
    print(f"✅ Migrated {len(allocations) - skipped:,} allocations (skipped {skipped:,} duplicates)")


async def main():
    """Main migration function."""
    print("🚀 Starting migration from SQLite to PostgreSQL...")
    print(f"   SQLite DB: {SQLITE_DB_PATH}")
    print(f"   PostgreSQL: {settings.database_url}")
    print(f"   Tenant ID: {DEFAULT_TENANT_ID}")
    
    # Check SQLite exists
    if not SQLITE_DB_PATH.exists():
        print(f"❌ SQLite database not found: {SQLITE_DB_PATH}")
        return
    
    # Initialize PostgreSQL (create schemas and tables)
    print("\n📊 Initializing PostgreSQL database...")
    async with async_session_factory() as session:
        # Create schemas if they don't exist
        await session.execute(text("CREATE SCHEMA IF NOT EXISTS plan"))
        await session.execute(text("CREATE SCHEMA IF NOT EXISTS hr"))
        await session.commit()
        print("✅ Schemas created/verified")
        
        # Create production_orders table
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS plan.production_orders (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL,
                legacy_id INTEGER NOT NULL UNIQUE,
                product_id INTEGER,
                product_name VARCHAR(255) NOT NULL,
                product_type VARCHAR(50),
                current_phase_id INTEGER,
                current_phase_name VARCHAR(255) NOT NULL,
                created_date DATE,
                completed_date DATE,
                transport_date DATE,
                status VARCHAR(20) NOT NULL DEFAULT 'IN_PROGRESS',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        
        # Create indexes
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_production_orders_tenant_id 
            ON plan.production_orders(tenant_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_production_orders_legacy_id 
            ON plan.production_orders(legacy_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_production_orders_created_date 
            ON plan.production_orders(created_date DESC)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_production_orders_status 
            ON plan.production_orders(status)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_production_orders_product_type 
            ON plan.production_orders(product_type)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_production_orders_current_phase 
            ON plan.production_orders(current_phase_name)
        """))
        
        # Create legacy_allocations table
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS hr.legacy_allocations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL,
                order_id INTEGER,
                phase_id INTEGER,
                phase_name VARCHAR(255) NOT NULL,
                employee_id INTEGER NOT NULL,
                employee_name VARCHAR(255) NOT NULL,
                is_leader BOOLEAN NOT NULL DEFAULT FALSE,
                start_date DATE,
                end_date DATE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        
        # Create indexes for allocations
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_legacy_allocations_tenant_id 
            ON hr.legacy_allocations(tenant_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_legacy_allocations_start_date 
            ON hr.legacy_allocations(start_date DESC)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_legacy_allocations_employee_id 
            ON hr.legacy_allocations(employee_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_legacy_allocations_phase_name 
            ON hr.legacy_allocations(phase_name)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_legacy_allocations_order_id 
            ON hr.legacy_allocations(order_id)
        """))
        
        await session.commit()
        print("✅ Tables created/verified")
    
    # Load data from SQLite
    print("\n📥 Loading data from SQLite...")
    orders = get_orders_from_sqlite()
    allocations = get_allocations_from_sqlite()
    print(f"   Found {len(orders):,} orders")
    print(f"   Found {len(allocations):,} allocations")
    
    # Migrate data
    async with async_session_factory() as session:
        await migrate_orders(session, DEFAULT_TENANT_ID, orders)
        await migrate_allocations(session, DEFAULT_TENANT_ID, allocations)
    
    print("\n✅ Migration completed successfully!")
    print(f"   Orders: {len(orders):,}")
    print(f"   Allocations: {len(allocations):,}")


if __name__ == "__main__":
    asyncio.run(main())
