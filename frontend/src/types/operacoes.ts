/**
 * ProdPlan ONE — Tipos TypeScript da camada OPERAÇÕES.
 *
 * Sprint Q.12 — espelham os `response_model` Pydantic dos endpoints
 * `/v1/hr/*`, `/v1/supply/*` e `/v1/profit/*`. Substituem o `request<any>`
 * que tinha 0 type-safety: renomear um campo no backend não dava erro de
 * compilação no frontend.
 *
 * Mantemos snake_case nos campos para coincidir 1:1 com o JSON.
 */

// ─── HR ─────────────────────────────────────────────────────────────────────

export type AllocationStatus =
  | 'PLANNED'
  | 'CONFIRMED'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'CANCELLED';

export interface AllocationCreatedItem {
  allocation_id: string;
  employee_id: string;
  employee_name: string;
  order_id: string;
  operation_id: string;
  allocated_hours: number;
  hourly_rate: number;
  estimated_cost: number;
  skill_match: boolean;
}

export interface AllocationCreateResponse {
  allocations: AllocationCreatedItem[];
}

export interface EmployeeAvailabilityResponse {
  employee_id: string;
  from_date: string;
  to_date: string;
  total_capacity_hours: number;
  allocated_hours: number;
  available_hours: number;
  utilization_percent: number;
  allocations_count: number;
}

export interface OrderAllocationItem {
  id: string;
  employee_id: string;
  operation_id: string;
  allocated_hours: number;
  status: AllocationStatus;
}

export interface OrderAllocationsResponse {
  order_id: string;
  allocations: OrderAllocationItem[];
}

export interface EmployeePayrollSummary {
  employee_id: string;
  total_hours: number;
  regular_hours: number;
  overtime_hours: number;
  total_cost: number;
}

export interface PayrollCalculateResponse {
  year_month: string;
  employee_count: number;
  total_hours: number;
  regular_hours: number;
  overtime_hours: number;
  regular_cost: number;
  overtime_cost: number;
  burden_cost: number;
  total_cost: number;
  employee_summaries: EmployeePayrollSummary[];
}

export interface LabourCostSummaryResponse {
  from_date: string | null;
  to_date: string | null;
  order_id: string | null;
  employee_id: string | null;
  allocated_hours: number;
  actual_hours: number;
  estimated_cost: number;
  actual_cost: number;
  allocation_count: number;
}

// ─── Supply ─────────────────────────────────────────────────────────────────

export interface ForecastResponse {
  sku_id: string;
  forecast: Array<Record<string, unknown>>;
  method: string | null;
  quality: Record<string, unknown> | null;
  extra: Record<string, unknown> | null;
}

export interface InventoryMovementResponse {
  sku_id: string;
  on_hand_after: number;
  qty_opening: number;
  qty_closing: number;
  reference_id: string | null;
}

export interface CurrentInventoryResponse {
  sku_id: string;
  on_hand: number;
}

export interface ROPSkuResponse {
  sku_id: string;
  reorder_point: number;
  safety_stock: number;
  avg_daily_demand: number;
  lead_time_days: number;
  service_level: number;
  z_score: number;
}

export interface ABCBucket {
  count: number;
  skus: Array<Record<string, unknown>>;
}

export interface ABCDistributionResponse {
  distribution: { A: ABCBucket; B: ABCBucket; C: ABCBucket };
}

export interface MaterialResponse {
  id: string;
  sku_id: string;
  name: string;
  description: string | null;
  unit_of_measure: string;
  category: string | null;
  default_supplier_id: string | null;
  lead_time_days: number;
  min_stock_qty: number;
  reorder_qty: number;
  safety_stock_days: number | null;
  critical_flag: boolean;
  active: boolean;
}

export interface StockAdjustResponse {
  sku_id: string;
  on_hand_after: number;
  qty_opening: number;
  qty_closing: number;
  qty_delta: number;
  reason: string;
}

export interface ReconciliationResponse {
  id: string;
  sku_id: string;
  theoretical_qty: number;
  physical_qty: number;
  variance_qty: number;
  variance_pct: number | null;
  counted_at: string | null;
  counted_by: string | null;
  comments: string | null;
  resolved: boolean;
  resolved_at: string | null;
  resolved_by: string | null;
}

// ─── Profit ─────────────────────────────────────────────────────────────────

export type PricingStrategy =
  | 'cost_plus'
  | 'dynamic'
  | 'target_margin'
  | 'competitive';

export interface DynamicFactors {
  demand_pressure: number;
  inventory_factor: number;
  competitor_factor: number;
  seasonality_factor: number;
  combined: number;
}

export interface PricingOption {
  strategy: PricingStrategy;
  price: number;
  gross_margin_percent: number;
  gross_profit_per_unit: number;
  is_recommended: boolean;
  factors?: DynamicFactors;
}

export interface PricingResult {
  order_id: string;
  cogs_per_unit: number;
  options: PricingOption[];
  recommended_price: number;
  recommended_strategy: PricingStrategy;
  currency: string;
  valid_until: string;
}

/** Margem por ordem — backend manda strings (Decimal) para preservar precisão. */
export interface OrderMarginResponse {
  order_id: string;
  revenue_eur: string;
  cogs_eur: string;
  shipping_eur: string;
  margin_eur: string;
  margin_pct: string | null;
}
