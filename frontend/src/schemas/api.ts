/**
 * API Schemas - Zod Validation
 * ============================
 * 
 * Zod schemas matching backend contracts for runtime validation.
 * Ensures frontend receives data in expected format.
 * 
 * Source Contracts:
 * - src/explain/models/explained_value.py
 * - src/factory_data_product/models/semantic.py
 * - src/twin/models.py
 * - src/copilot/schemas.py
 */

import { z } from 'zod';

// ═══════════════════════════════════════════════════════════════════════════════
// TRUST & EXPLAINABILITY SCHEMAS
// Source: src/explain/models/explained_value.py
// ═══════════════════════════════════════════════════════════════════════════════

export const TrustInfoSchema = z.object({
  index_0_100: z.number().min(0).max(100),
  coverage_pct: z.number().min(0).max(100),
  warnings: z.array(z.string()).optional(),
  blocking_reasons: z.array(z.string()).optional(),
});

export type TrustInfo = z.infer<typeof TrustInfoSchema>;

export const LineageSchema = z.object({
  source: z.string(),
  transformation: z.string().optional(),
  timestamp: z.string().optional(),
  query: z.string().optional(),
});

export type Lineage = z.infer<typeof LineageSchema>;

export const ExplainedValueSchema = z.object({
  metric_id: z.string(),
  value: z.union([z.number(), z.null()]),
  display: z.string().optional(),
  unit: z.string(),
  explanation: z.object({
    short: z.string(),
    long: z.string().optional(),
    factors: z.array(z.object({
      name: z.string(),
      contribution: z.number().optional(),
      description: z.string().optional(),
    })).optional(),
  }),
  trust: TrustInfoSchema,
  suggestions: z.array(z.string()).optional(),
  forbidden_claims: z.array(z.string()).optional(),
  lineage: LineageSchema.optional(),
  period: z.string().optional(),
  scope: z.string().optional(),
  semantics: z.enum(['theoretical', 'observed', 'imputed', 'calculated']).optional(),
});

export type ExplainedValue = z.infer<typeof ExplainedValueSchema>;

// ═══════════════════════════════════════════════════════════════════════════════
// SEMANTIC QUERY RESPONSE SCHEMAS
// Source: src/factory_data_product/models/semantic.py
// ═══════════════════════════════════════════════════════════════════════════════

export const SemanticResponseSchema = z.object({
  data: z.record(z.string(), z.any()),
  data_confidence: z.number().min(0).max(100),
  trust_status: z.enum(['OK', 'WARNING', 'DEGRADED', 'BLOCKED']).optional(),
  semantic_label: z.string().optional(),
  metadata: z.record(z.string(), z.any()).optional(),
  warnings: z.array(z.string()).optional(),
});

export type SemanticResponse = z.infer<typeof SemanticResponseSchema>;

export const WIPDataSchema = z.object({
  open_orders: z.number(),
  open_phases_total: z.number(),
  total_horas_previstas: z.number().optional(),
  message: z.string().optional(),
});

export type WIPData = z.infer<typeof WIPDataSchema>;

export const BacklogDataSchema = z.object({
  total_horas_previstas: z.number(),
  total_phases_pending: z.number(),
  oldest_order_age_days: z.number().optional(),
  avg_horas_per_order: z.number().optional(),
  message: z.string().optional(),
});

export type BacklogData = z.infer<typeof BacklogDataSchema>;

export const BottleneckSchema = z.object({
  fase_id: z.number(),
  fase_nome: z.string(),
  pending_phases_count: z.number(),
  total_horas_previstas: z.number().optional(),
  bottleneck_score: z.number().optional(),
});

export type Bottleneck = z.infer<typeof BottleneckSchema>;

export const QualityErrorSchema = z.object({
  error_type: z.string(),
  count: z.number(),
  percentage: z.number(),
});

export type QualityError = z.infer<typeof QualityErrorSchema>;

export const QualityDataSchema = z.object({
  total_errors: z.number(),
  by_type: z.array(QualityErrorSchema).optional(),
  by_phase: z.array(z.object({
    fase_nome: z.string(),
    count: z.number(),
  })).optional(),
});

export type QualityData = z.infer<typeof QualityDataSchema>;

// ═══════════════════════════════════════════════════════════════════════════════
// TWIN / SANDBOX SCHEMAS
// Source: src/twin/models.py
// ═══════════════════════════════════════════════════════════════════════════════

export const DeltaSchema = z.object({
  entity_type: z.string(),
  entity_key: z.string(),
  patch: z.record(z.string(), z.any()),
  applied_at: z.string().optional(),
});

export type Delta = z.infer<typeof DeltaSchema>;

export const ScenarioSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string().optional(),
  status: z.enum(['draft', 'simulated', 'compared', 'published']),
  deltas: z.array(DeltaSchema).optional(),
  created_at: z.string(),
  updated_at: z.string().optional(),
  created_by: z.string().optional(),
  reproducibility_hash: z.string().optional(),
});

export type Scenario = z.infer<typeof ScenarioSchema>;

export const MetricValueSchema = z.object({
  value: z.union([z.number(), z.null()]),
  status: z.enum(['OK', 'WARNING', 'BLOCKED', 'DEGRADED']).optional(),
  trust_index: z.number().optional(),
  semantic_label: z.string().optional(),
  reason: z.string().optional(),
});

export type MetricValue = z.infer<typeof MetricValueSchema>;

export const SimulationResultSchema = z.object({
  scenario_id: z.string(),
  status: z.string(),
  kpis: z.record(z.string(), z.union([MetricValueSchema, z.number(), z.null()])),
  comparison: z.record(z.string(), z.object({
    baseline: z.number().optional(),
    simulated: z.number().optional(),
    delta: z.number().optional(),
  })).optional(),
  impact: z.record(z.string(), z.any()).optional(),
  blocked_metrics: z.array(z.string()).optional(),
  message: z.string().optional(),
  simulated_at: z.string().optional(),
  reproducibility_hash: z.string().optional(),
});

export type SimulationResult = z.infer<typeof SimulationResultSchema>;

// ═══════════════════════════════════════════════════════════════════════════════
// COPILOT SCHEMAS
// Source: src/copilot/schemas.py
// ═══════════════════════════════════════════════════════════════════════════════

export const CitationSchema = z.object({
  source_type: z.enum(['semantic_query', 'explain_api', 'entity_lookup', 'calculation']),
  source_ref: z.string(),
  confidence: z.number().min(0).max(1),
  snippet: z.string().optional(),
});

export type Citation = z.infer<typeof CitationSchema>;

export const CopilotResponseSchema = z.object({
  message: z.string(),
  citations: z.array(CitationSchema).optional(),
  suggested_actions: z.array(z.object({
    action_type: z.string(),
    description: z.string(),
    params: z.record(z.string(), z.any()).optional(),
  })).optional(),
  warnings: z.array(z.string()).optional(),
  confidence: z.number().min(0).max(1).optional(),
  requires_sandbox: z.boolean().optional(),
});

export type CopilotResponse = z.infer<typeof CopilotResponseSchema>;

// ═══════════════════════════════════════════════════════════════════════════════
// GOVERNANCE SCHEMAS
// ═══════════════════════════════════════════════════════════════════════════════

export const DecisionRunSchema = z.object({
  id: z.string(),
  action_type: z.string(),
  status: z.enum(['PROPOSED', 'APPROVED', 'EXECUTED', 'REJECTED', 'ROLLED_BACK', 'KILLED']),
  created_at: z.string(),
  created_by: z.string(),
  approved_by: z.string().optional(),
  executed_at: z.string().optional(),
  audit_hash: z.string(),
  input_snapshot_hash: z.string(),
  params: z.record(z.string(), z.any()).optional(),
});

export type DecisionRun = z.infer<typeof DecisionRunSchema>;

// ═══════════════════════════════════════════════════════════════════════════════
// CAPABILITIES SCHEMA
// ═══════════════════════════════════════════════════════════════════════════════

export const CapabilitiesResponseSchema = z.object({
  modules: z.array(z.string()),
  features: z.array(z.string()),
  version: z.string(),
  blocked_metrics: z.array(z.string()).optional(),
  allowed_metrics: z.array(z.string()).optional(),
  trust_index: z.record(z.string(), z.number()).optional(),
  data_product_status: z.enum(['OK', 'WARNING', 'DEGRADED', 'BLOCKED']).optional(),
  last_ingestion: z.string().optional(),
});

export type CapabilitiesResponse = z.infer<typeof CapabilitiesResponseSchema>;

// ═══════════════════════════════════════════════════════════════════════════════
// EXPLAIN API SCHEMAS
// ═══════════════════════════════════════════════════════════════════════════════

export const ExplainedMetricSchema = z.object({
  metric_id: z.string(),
  metric_name: z.string(),
  value: z.union([z.number(), z.null()]),
  unit: z.string(),
  explanation: z.string(),
  factors: z.array(z.object({
    name: z.string(),
    contribution: z.number().optional(),
    description: z.string().optional(),
  })).optional(),
  suggestions: z.array(z.object({
    title: z.string(),
    description: z.string(),
    difficulty: z.enum(['easy', 'medium', 'hard']).optional(),
  })).optional(),
  citations: z.array(z.object({
    source: z.string(),
    reference: z.string(),
    confidence: z.number().optional(),
  })).optional(),
  computed_at: z.string(),
  trust_index: z.number().min(0).max(1).optional(),
  forbidden_claims: z.array(z.string()).optional(),
  is_blocked: z.boolean().optional(),
  blocked_reason: z.string().optional(),
});

export type ExplainedMetric = z.infer<typeof ExplainedMetricSchema>;

// ═══════════════════════════════════════════════════════════════════════════════
// VALIDATION HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

export class ValidationError extends Error {
  issues: z.ZodError['issues'];
  
  constructor(
    message: string,
    issues: z.ZodError['issues']
  ) {
    super(message);
    this.name = 'ValidationError';
    this.issues = issues;
  }
}

/**
 * Validate response against schema
 * Throws ValidationError if invalid
 */
export function validateResponse<T>(
  data: unknown,
  schema: z.ZodSchema<T>,
  context?: string
): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    console.error(`Validation failed${context ? ` for ${context}` : ''}:`, result.error.issues);
    throw new ValidationError(
      `Invalid response${context ? ` from ${context}` : ''}: ${result.error.message}`,
      result.error.issues
    );
  }
  return result.data;
}

/**
 * Validate response and return null on failure (soft validation)
 */
export function validateResponseSoft<T>(
  data: unknown,
  schema: z.ZodSchema<T>,
  context?: string
): T | null {
  const result = schema.safeParse(data);
  if (!result.success) {
    console.warn(`Validation warning${context ? ` for ${context}` : ''}:`, result.error.issues);
    return null;
  }
  return result.data;
}

/**
 * Check if value matches schema (type guard)
 */
export function isValid<T>(
  data: unknown,
  schema: z.ZodSchema<T>
): data is T {
  return schema.safeParse(data).success;
}

// ═══════════════════════════════════════════════════════════════════════════════
// OPERAÇÕES — Zod schemas (Sprint Q.12)
// Espelham os response_model Pydantic em src/hr e src/supply.
// ═══════════════════════════════════════════════════════════════════════════════

export const AllocationStatusSchema = z.enum([
  'PLANNED',
  'CONFIRMED',
  'IN_PROGRESS',
  'COMPLETED',
  'CANCELLED',
]);

export const PricingStrategySchema = z.enum([
  'cost_plus',
  'dynamic',
  'target_margin',
  'competitive',
]);

export const OrderAllocationItemSchema = z.object({
  id: z.string(),
  employee_id: z.string(),
  operation_id: z.string(),
  allocated_hours: z.number(),
  status: AllocationStatusSchema,
});

export const OrderAllocationsResponseSchema = z.object({
  order_id: z.string(),
  allocations: z.array(OrderAllocationItemSchema),
});

export const EmployeePayrollSummarySchema = z.object({
  employee_id: z.string(),
  total_hours: z.number(),
  regular_hours: z.number(),
  overtime_hours: z.number(),
  total_cost: z.number(),
});

export const PayrollCalculateResponseSchema = z.object({
  year_month: z.string(),
  employee_count: z.number().int(),
  total_hours: z.number(),
  regular_hours: z.number(),
  overtime_hours: z.number(),
  regular_cost: z.number(),
  overtime_cost: z.number(),
  burden_cost: z.number(),
  total_cost: z.number(),
  employee_summaries: z.array(EmployeePayrollSummarySchema),
});

export const ROPSkuResponseSchema = z.object({
  sku_id: z.string(),
  reorder_point: z.number(),
  safety_stock: z.number(),
  avg_daily_demand: z.number(),
  lead_time_days: z.number().int().nonnegative(),
  service_level: z.number(),
  z_score: z.number(),
});

