// ============================================================================
// PALANTIR-LEVEL TYPES — ExplainedValue & Trust-Based Data
// ============================================================================

/**
 * ExplainedValue — Every number in PP1 carries full context
 * "No number leaves the system without full metadata"
 */
export interface ExplainedValue {
  value: number | string | null;
  formatted_value: string;
  unit: string;
  semantic_label: string;
  semantic_kind: 'theoretical' | 'calculated' | 'estimated' | 'real';
  trust_index: number;
  coverage_pct: number;
  time_period?: {
    start: string;
    end: string;
    granularity: 'hour' | 'day' | 'week' | 'month' | 'quarter' | 'year';
  };
  scope?: {
    entity_type: string;
    entity_id?: string;
    filter_applied?: string;
  };
  lineage: {
    sources: DataSourceInfo[];
    transformations: string[];
    computation_timestamp: string;
  };
  explanation: {
    what: string;
    how: string;
    assumptions: string[];
    forbidden_claims: string[];
    how_to_improve: string[];
  };
}

export interface DataSourceInfo {
  schema: string;
  table: string;
  fields: string[];
  trust_index: number;
  coverage_pct: number;
  row_count?: number;
}

/**
 * TrustCell — Used in Trust Heatmap
 */
export interface TrustCell {
  entity: string;
  field: string;
  trust_index: number;
  coverage_pct: number;
  null_pct: number;
  zero_pct: number;
  impact: string[];
  blocked_metrics: string[];
  how_to_improve: string[];
}

/**
 * QuarantinedRow — Rows isolated for data quality issues
 */
export interface QuarantinedRow {
  id: string;
  entity: string;
  entity_id: string;
  reason: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  detected_at: string;
  impact: string[];
  suggestion?: string;
  can_auto_fix: boolean;
  raw_data: Record<string, unknown>;
}

/**
 * SchemaDrift — Detected changes in data schema
 */
export interface SchemaDrift {
  type: 'new_column' | 'missing_column' | 'type_change' | 'distribution_shift';
  entity: string;
  column: string;
  old_value?: string;
  new_value?: string;
  impact: 'critical' | 'warning' | 'info';
  affected_metrics: string[];
  suggestion: string;
}

/**
 * BlockedMetric — Metric that cannot be calculated
 */
export interface BlockedMetric {
  id: string;
  name: string;
  name_pt: string;
  reason: string;
  required_data: Array<{
    field: string;
    coverage: number;
    status: 'missing' | 'partial' | 'available';
  }>;
  how_to_unlock: string[];
  alternative?: {
    id: string;
    name: string;
    trust_index: number;
  };
}

/**
 * Ingestion — Data ingestion record
 */
export interface Ingestion {
  id: string;
  filename: string;
  timestamp: string;
  status: 'active' | 'superseded' | 'pending' | 'failed';
  quality_score: number;
  row_count: number;
  table_count: number;
  error_count: number;
  warning_count: number;
}

/**
 * RollbackImpact — Impact analysis for rollback operation
 */
export interface RollbackImpact {
  rows_lost: number;
  metrics_affected: number;
  data_age: string;
  decisions_affected: string[];
}

/**
 * MoldConflict — Mold scheduling conflict
 */
export interface MoldConflict {
  id: string;
  mold_id: string;
  date: string;
  severity: 'high' | 'medium' | 'low';
  orders: string[];
  estimated_delay_hours: number;
}

/**
 * ScenarioTemplate — Pre-defined simulation template
 */
export interface ScenarioTemplate {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: 'capacity' | 'workforce' | 'risk' | 'orders';
  deltas: Array<{
    type: string;
    [key: string]: unknown;
  }>;
}

/**
 * Runbook — Automation runbook
 */
export interface Runbook {
  id: string;
  name: string;
  description: string;
  trigger_type: 'manual' | 'scheduled' | 'event';
  steps: RunbookStep[];
  execution_count: number;
  last_executed?: string;
  category: string;
}

export interface RunbookStep {
  id: string;
  name: string;
  action_type: string;
  parameters: Record<string, unknown>;
  order: number;
}

/**
 * ApprovalStep — Step in approval chain
 */
export interface ApprovalStep {
  id: string;
  approver: {
    id: string;
    name: string;
    role: string;
    avatar: string;
  };
  status: 'pending' | 'approved' | 'rejected';
  comment?: string;
  decided_at?: string;
  can_approve: boolean;
}

/**
 * SoDConflict — Segregation of Duties conflict
 */
export interface SoDConflict {
  id: string;
  rule_name: string;
  description: string;
  severity: 'critical' | 'warning';
  conflicting_roles: string[];
}

/**
 * LLMTool — Tool available to the LLM Copilot
 */
export interface LLMTool {
  id: string;
  name: string;
  function_name: string;
  description: string;
  category: 'query' | 'action' | 'simulation' | 'admin';
  risk_level: 'high' | 'medium' | 'low';
  enabled: boolean;
  requires_approval: boolean;
  usage_count: number;
}

/**
 * TableCoverage — Coverage analysis for a table
 */
export interface TableCoverage {
  name: string;
  row_count: number;
  overall_coverage: number;
  fields: FieldCoverage[];
}

export interface FieldCoverage {
  name: string;
  coverage: number;
  null_pct: number;
  zero_pct: number;
  data_type: string;
}

/**
 * MetricHistoryPoint — Historical metric value
 */
export interface MetricHistoryPoint {
  date: string;
  value: number;
  unit: string;
  trust_index: number;
}

// ============================================================================
// ORIGINAL TYPES
// ============================================================================

// Core Types
export interface Tenant {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface Product {
  id: string;
  tenant_id: string;
  name: string;
  description?: string;
  unit_of_measure: string;
  cost: number;
  price: number;
  created_at: string;
  updated_at: string;
}

export interface Machine {
  id: string;
  tenant_id: string;
  name: string;
  description?: string;
  capacity: number;
  cost_per_hour: number;
  created_at: string;
  updated_at: string;
}

export interface Employee {
  id: string;
  tenant_id: string;
  name: string;
  role: string;
  hourly_rate: number;
  created_at: string;
  updated_at: string;
}

export interface Operation {
  id: string;
  tenant_id: string;
  name: string;
  description?: string;
  standard_time: number;
  machine_id?: string;
  created_at: string;
  updated_at: string;
}

// Plan Types
export interface Schedule {
  id: string;
  tenant_id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: 'pending' | 'generated' | 'executed';
  tasks: ScheduleTask[];
  created_at: string;
  updated_at: string;
}

export interface ScheduleTask {
  id: string;
  schedule_id: string;
  product_id: string;
  machine_id?: string;
  employee_id?: string;
  start_time?: string;
  end_time?: string;
  quantity: number;
  status: string;
}

export interface MRPRun {
  id: string;
  tenant_id: string;
  run_date: string;
  status: string;
  items: MRPItem[];
}

export interface MRPItem {
  id: string;
  mrp_run_id: string;
  item_id: string;
  item_type: 'purchase_order' | 'production_order';
  quantity: number;
  start_date?: string;
  due_date?: string;
}

// Profit Types
export interface COGSResult {
  product_id: string;
  quantity: number;
  total_cogs: number;
  components: {
    direct_material_cost: number;
    direct_labor_cost: number;
    manufacturing_overhead_machine: number;
    manufacturing_overhead_other: number;
    packaging_cost: number;
    quality_control_cost: number;
  };
}

export interface PricingResult {
  product_id: string;
  quantity: number;
  base_cogs: number;
  markup_percentage: number;
  calculated_price: number;
  pricing_strategy: string;
}

export interface ScenarioResult {
  product_id: string;
  quantity: number;
  original_cogs: number;
  simulated_cogs: number;
  original_components: Record<string, number>;
  simulated_components: Record<string, number>;
  scenario_changes: Record<string, number>;
}

// HR Types
export interface EmployeeAllocation {
  id: string;
  tenant_id: string;
  employee_id: string;
  operation_id: string;
  allocated_hours: number;
  start_time: string;
  end_time: string;
}

export interface ProductivityMetric {
  id: string;
  tenant_id: string;
  employee_id: string;
  metric_name: string;
  metric_value: number;
  recorded_date: string;
}

export interface PayrollResult {
  employee_id: string;
  start_date: string;
  end_date: string;
  total_hours_worked: number;
  hourly_rate: number;
  gross_pay: number;
  tax_deductions: number;
  other_deductions: number;
  net_pay: number;
}

// Dashboard Types
export interface DashboardMetrics {
  totalRevenue: number;
  revenueGrowth: number;
  totalOrders: number;
  ordersGrowth: number;
  avgCOGS: number;
  cogsChange: number;
  employeeCount: number;
  productivityIndex: number;
}

export interface ChartDataPoint {
  name: string;
  value: number;
  value2?: number;
  label?: string;
  [key: string]: string | number | undefined;
}

// BOM Types
export interface BOMItem {
  id: string;
  parent_product_id: string;
  component_product_id: string;
  quantity_per: number;
  unit_of_measure: string;
  sequence: number;
  operation_id?: string;
  scrap_factor: number;
  effective_from?: string;
  effective_to?: string;
  bom_version: number;
  position_ref?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

// Customer Types
export interface Customer {
  id: string;
  tenant_id: string;
  customer_code: string;
  customer_name: string;
  segment: 'RETAIL' | 'WHOLESALE' | 'BULK' | 'OEM' | 'DISTRIBUTOR';
  payment_terms: 'PREPAID' | 'NET15' | 'NET30' | 'NET45' | 'NET60' | 'NET90';
  price_tier: 'ECONOMY' | 'STANDARD' | 'PREMIUM' | 'VIP';
  credit_limit?: number;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  postal_code?: string;
  country?: string;
  is_active: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
}

// Supplier Types
export interface Supplier {
  id: string;
  tenant_id: string;
  supplier_code: string;
  supplier_name: string;
  material_category: 'STEEL' | 'WOOD' | 'PACKAGING' | 'CONSUMABLES' | 'COMPONENTS' | 'OTHER';
  lead_time_days: number;
  payment_terms: 'PREPAID' | 'NET15' | 'NET30' | 'NET45' | 'NET60' | 'NET90';
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  postal_code?: string;
  country?: string;
  quality_rating?: number;
  is_active: boolean;
  is_preferred: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
}

// Rate Types
export interface LaborRate {
  id: string;
  employee_id: string;
  base_hourly_rate: number;
  burden_rate: number;
  loaded_rate: number;
  effective_date: string;
  valid_until?: string;
  currency_code: string;
}

export interface MachineRate {
  id: string;
  machine_id: string;
  depreciation_rate: number;
  energy_cost_per_hour: number;
  maintenance_cost_per_hour: number;
  total_rate: number;
  effective_date: string;
  valid_until?: string;
  currency_code: string;
}

export interface OverheadRate {
  id: string;
  year_month: string;
  total_monthly_overhead: number;
  total_available_hours: number;
  calculated_rate: number;
  currency_code: string;
}

