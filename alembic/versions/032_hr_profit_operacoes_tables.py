"""Sprint Q.12 — HR + Profit OPERAÇÕES tables

Cobre os 9 modelos SQLAlchemy que existiam em ``src/hr/models/`` e
``src/profit/models/cost.py`` sem migration alembic correspondente
(descoberto na auditoria da camada OPERAÇÕES). Sem isto o serviço
estoura ao tocar em qualquer endpoint de allocations/payroll/COGS.

Tabelas criadas:
* hr.hr_allocations + enum allocation_status
* hr.shift_schedules + enum shift_type
* hr.skills
* hr.employee_skills
* hr.employee_productivity
* hr.monthly_payroll_summary
* profit.cost_calculations + enum calculation_status
* profit.pricing_recommendations + enum pricing_strategy
* profit.profit_scenarios

Revision ID: 032_hr_profit_operacoes
Revises: 031_improvement_suggestions
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '032_hr_profit_operacoes'
down_revision = '031_improvement_suggestions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS hr")
    op.execute("CREATE SCHEMA IF NOT EXISTS profit")

    op.create_table(
        'hr_allocations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.employees.id'), nullable=False, index=True),
        sa.Column('order_id', sa.String(50), nullable=False, index=True),
        sa.Column('operation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.operations.id'), nullable=False),
        sa.Column('allocation_date', sa.Date(), nullable=False, index=True),
        sa.Column('start_time', sa.Time(), nullable=True),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('allocated_hours', sa.Numeric(6, 2), nullable=False),
        sa.Column('actual_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('hourly_rate', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('estimated_cost', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('actual_cost', sa.Numeric(18, 8), nullable=True),
        sa.Column(
            'status',
            sa.Enum('PLANNED', 'CONFIRMED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED',
                    name='allocation_status'),
            nullable=False,
            server_default='PLANNED',
        ),
        sa.Column('skill_match', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_hr_allocations_tenant_date', 'tenant_id', 'allocation_date'),
        sa.Index('ix_hr_allocations_tenant_employee_date',
                 'tenant_id', 'employee_id', 'allocation_date'),
        schema='hr',
    )

    op.create_table(
        'shift_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.employees.id'), nullable=False, index=True),
        sa.Column('shift_date', sa.Date(), nullable=False, index=True),
        sa.Column(
            'shift_type',
            sa.Enum('DAY', 'EVENING', 'NIGHT', 'SPLIT', name='shift_type'),
            nullable=False,
            server_default='DAY',
        ),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('break_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('net_hours', sa.Numeric(4, 2), nullable=True),
        sa.Column('is_overtime', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('overtime_multiplier', sa.Numeric(3, 2), nullable=False, server_default='1.0'),
        sa.Column('is_confirmed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'employee_id', 'shift_date',
                            name='uq_shift_schedules_employee_date'),
        schema='hr',
    )

    op.create_table(
        'skills',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('skill_code', sa.String(50), nullable=False),
        sa.Column('skill_name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('requires_certification', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
        sa.Column('certification_validity_months', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'skill_code', name='uq_skills_tenant_code'),
        schema='hr',
    )

    op.create_table(
        'employee_skills',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.employees.id'), nullable=False, index=True),
        sa.Column('skill_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('hr.skills.id'), nullable=False),
        sa.Column('proficiency_level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_certified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('certification_date', sa.Date(), nullable=True),
        sa.Column('certification_expiry', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'employee_id', 'skill_id',
                            name='uq_employee_skills_emp_skill'),
        schema='hr',
    )

    op.create_table(
        'employee_productivity',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.employees.id'), nullable=False, index=True),
        sa.Column('order_id', sa.String(50), nullable=False, index=True),
        sa.Column('operation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.operations.id'), nullable=False),
        sa.Column('record_date', sa.Date(), nullable=False, index=True),
        sa.Column('standard_hours', sa.Numeric(8, 2), nullable=False, server_default='0'),
        sa.Column('actual_hours', sa.Numeric(8, 2), nullable=False, server_default='0'),
        sa.Column('standard_quantity', sa.Numeric(18, 6), nullable=False, server_default='0'),
        sa.Column('actual_quantity', sa.Numeric(18, 6), nullable=False, server_default='0'),
        sa.Column('good_quantity', sa.Numeric(18, 6), nullable=False, server_default='0'),
        sa.Column('efficiency_percent', sa.Numeric(6, 2), nullable=False, server_default='0'),
        sa.Column('quality_percent', sa.Numeric(6, 2), nullable=False, server_default='0'),
        sa.Column('bonus_eligible', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_employee_productivity_tenant_date', 'tenant_id', 'record_date'),
        schema='hr',
    )

    op.create_table(
        'monthly_payroll_summary',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('year_month', sa.Date(), nullable=False, index=True),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.employees.id'), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('regular_hours', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('overtime_hours', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('total_hours', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('regular_cost', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('overtime_cost', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('bonus_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('burden_cost', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('currency_code', sa.String(3), nullable=False, server_default='EUR'),
        sa.Column('employee_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_efficiency_percent', sa.Numeric(6, 2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_monthly_payroll_tenant_period', 'tenant_id', 'year_month'),
        schema='hr',
    )

    op.create_table(
        'cost_calculations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('order_id', sa.String(50), nullable=False, index=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.products.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(18, 6), nullable=False),
        sa.Column('calculation_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('material_cost', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('labor_cost', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('machine_cost', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('setup_cost', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('overhead_cost', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('scrap_cost', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('total_cogs', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('cogs_per_unit', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('breakdown_details', postgresql.JSONB(), nullable=True),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'CALCULATED', 'APPROVED', 'RECONCILED',
                    name='calculation_status'),
            nullable=False,
            server_default='PENDING',
        ),
        sa.Column('currency_code', sa.String(3), nullable=False, server_default='EUR'),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),
        sa.Column('calculated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('valid_from', sa.DateTime(), nullable=True),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('assumptions', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_cost_calculations_tenant_order', 'tenant_id', 'order_id'),
        schema='profit',
    )

    op.create_table(
        'pricing_recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('cost_calculation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('profit.cost_calculations.id'), nullable=False),
        sa.Column(
            'strategy',
            sa.Enum('cost_plus', 'dynamic', 'target_margin', 'competitive',
                    name='pricing_strategy'),
            nullable=False,
        ),
        sa.Column('base_markup_percent', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('base_price', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('dynamic_factors', postgresql.JSONB(), nullable=True),
        sa.Column('adjusted_price', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('gross_margin_percent', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('gross_profit_per_unit', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('is_recommended', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('valid_from', sa.DateTime(), nullable=True),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('currency_code', sa.String(3), nullable=False, server_default='EUR'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        schema='profit',
    )

    op.create_table(
        'profit_scenarios',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('scenario_name', sa.String(255), nullable=False),
        sa.Column('scenario_description', sa.Text(), nullable=True),
        sa.Column('base_order_id', sa.String(50), nullable=True),
        sa.Column('base_cost_calculation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('profit.cost_calculations.id'), nullable=True),
        sa.Column('cost_multipliers', postgresql.JSONB(), nullable=True),
        sa.Column('volume_multiplier', sa.Numeric(5, 2), nullable=False, server_default='1.0'),
        sa.Column('base_cogs_per_unit', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('scenario_cogs_per_unit', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('delta_percent', sa.Numeric(8, 2), nullable=False, server_default='0'),
        sa.Column('impact_analysis', postgresql.JSONB(), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('simulated_at', sa.DateTime(), nullable=False),
        sa.Column('simulated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        schema='profit',
    )


def downgrade() -> None:
    op.drop_table('profit_scenarios', schema='profit')
    op.drop_table('pricing_recommendations', schema='profit')
    op.drop_table('cost_calculations', schema='profit')
    op.drop_table('monthly_payroll_summary', schema='hr')
    op.drop_table('employee_productivity', schema='hr')
    op.drop_table('employee_skills', schema='hr')
    op.drop_table('skills', schema='hr')
    op.drop_table('shift_schedules', schema='hr')
    op.drop_table('hr_allocations', schema='hr')
    # Drop enums explicitly (they don't auto-drop with tables in postgres)
    op.execute("DROP TYPE IF EXISTS pricing_strategy")
    op.execute("DROP TYPE IF EXISTS calculation_status")
    op.execute("DROP TYPE IF EXISTS shift_type")
    op.execute("DROP TYPE IF EXISTS allocation_status")
