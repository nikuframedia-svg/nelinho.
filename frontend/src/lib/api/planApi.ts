/**
 * ProdPlan ONE — API: planeamento, ordens, CPO, schedule-preview, operações de operador.
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 */
import { request, filterParams } from './client';

// ═══════════════════════════════════════════════════════════════════════════════
// PLAN MODULE - Production Planning
// ═══════════════════════════════════════════════════════════════════════════════

// Scheduling
export const schedulingApi = {
  generate: (data: {
    orders: Array<Record<string, any>>;
    machines: Array<Record<string, any>>;
    operations: Array<Record<string, any>>;
    engine?: string;
    rule?: string;
    planning_weeks?: number;
  }) =>
    request<any>('/v1/plan/schedule/generate', { method: 'POST', body: JSON.stringify(data) }),
  
  get: (planningRunId: string) =>
    request<any>(`/v1/plan/schedule/${planningRunId}`),
  
  getOrderSchedule: (orderId: string) =>
    request<any>(`/v1/plan/schedule/order/${orderId}`),
  
  // Legacy methods for backward compatibility (deprecated)
  list: (params?: { status?: string }) =>
    request<any>(`/v1/plan/schedule?${new URLSearchParams(filterParams(params))}`),
  
  create: (data: any) =>
    request<any>('/v1/plan/schedule', { method: 'POST', body: JSON.stringify(data) }),
  
  run: (id: string) =>
    request<any>(`/v1/plan/schedule/${id}/run`, { method: 'POST' }),
  
  getTasks: (scheduleId: string) =>
    request<any>(`/v1/plan/schedule/${scheduleId}/tasks`),
};

// MRP
export const mrpApi = {
  calculate: (data: {
    orders: Array<Record<string, any>>;
    inventory?: Record<string, Record<string, any>>;
    bom_data?: Record<string, any>;
    planning_horizon_weeks?: number;
  }) =>
    request<any>('/v1/plan/mrp/calculate', { method: 'POST', body: JSON.stringify(data) }),
  
  getRequirements: (mrpRunId: string) =>
    request<any>(`/v1/plan/mrp/${mrpRunId}/requirements`),
  
  // Legacy methods for backward compatibility (may not exist in backend)
  list: () =>
    request<any>('/v1/plan/mrp/runs'),
  
  get: (id: string) =>
    request<any>(`/v1/plan/mrp/runs/${id}`),
  
  run: (data: any) =>
    request<any>('/v1/plan/mrp/run', { method: 'POST', body: JSON.stringify(data) }),
  
  getItems: (runId: string) =>
    request<any>(`/v1/plan/mrp/runs/${runId}/items`),
};

// Capacity
export const capacityApi = {
  analyze: (data: {
    machines: Array<Record<string, any>>;
    from_date?: string;
    to_date?: string;
    period_days?: number;
  }) =>
    request<any>('/v1/plan/capacity/analysis', { method: 'POST', body: JSON.stringify(data) }),
  
  getMachineAvailability: (machineId: string, params?: { from_date?: string; to_date?: string }) => {
    const queryParams = new URLSearchParams();
    if (params?.from_date) queryParams.set('from_date', params.from_date);
    if (params?.to_date) queryParams.set('to_date', params.to_date);
    const query = queryParams.toString();
    return request<any>(`/v1/plan/capacity/machines/${machineId}/availability${query ? `?${query}` : ''}`);
  },
  
  // Legacy methods for backward compatibility (may not exist in backend)
  getUtilization: (params?: { startDate?: string; endDate?: string }) =>
    request<any>(`/v1/plan/capacity/utilization?${new URLSearchParams(filterParams(params))}`),
  
  getBottlenecks: () =>
    request<any>('/v1/plan/capacity/bottlenecks'),
};

// Plan API - High-level planning interface
export const planApi = {
  // Get all schedules
  getSchedules: (params?: { limit?: number; status?: string }) =>
    request<any>(`/v1/plan/schedule?${new URLSearchParams(filterParams(params))}`),
  
  // Generate a new schedule
  generateSchedule: (params: { horizon_days?: number; engine?: string; rule?: string }) =>
    request<any>('/v1/plan/schedule/generate', { 
      method: 'POST', 
      body: JSON.stringify({
        orders: [],
        machines: [],
        operations: [],
        planning_weeks: Math.ceil((params.horizon_days || 14) / 7),
        engine: params.engine || 'genetic',
        rule: params.rule || 'SPT',
      })
    }),
  
  // Get a specific schedule
  getSchedule: (id: string) =>
    request<any>(`/v1/plan/schedule/${id}`),
  
  // Get tasks for a schedule
  getScheduleTasks: (scheduleId: string) =>
    request<any>(`/v1/plan/schedule/${scheduleId}/tasks`),
  
  // Capacity analysis
  getCapacityAnalysis: () =>
    request<any>('/v1/plan/capacity/analysis'),
  
  // MRP results
  getMRPResults: (params?: { limit?: number }) =>
    request<any>(`/v1/plan/mrp/results${params?.limit ? `?limit=${params.limit}` : ''}`),
  
  // Calculate MRP
  calculateMRP: (data: any) =>
    request<any>('/v1/plan/mrp/calculate', { method: 'POST', body: JSON.stringify(data) }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// ORDERS API - Paginated Production Orders (NEW)
// ═══════════════════════════════════════════════════════════════════════════════

export interface OrdersParams {
  page?: number;
  pageSize?: number;
  limit?: number;
  status?: 'ALL' | 'IN_PROGRESS' | 'COMPLETED';
  search?: string;
  productType?: 'K1' | 'K2' | 'K4' | 'C1' | 'C2' | 'C4' | 'Other' | 'ALL';
  sortBy?: 'createdDate' | 'productName' | 'status' | 'id';
  sortOrder?: 'asc' | 'desc';
}

export interface OrdersResponse {
  data: Order[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  hasNextPage: boolean;
  hasPreviousPage: boolean;
}

export interface Order {
  id: string;
  productId: string | null;
  productName: string;
  productType: string;
  currentPhaseId: string | null;
  currentPhaseName: string;
  createdDate: string | null;
  completedDate: string | null;
  transportDate: string | null;
  status: 'IN_PROGRESS' | 'COMPLETED';
}

export interface OrdersStats {
  total: number;
  inProgress: number;
  completed: number;
  withTransport: number;
  phaseDistribution: Array<{ phase: string; count: number }>;
  // Additional fields for compatibility
  byPriority?: Record<string, number>;
  byStatus?: Record<string, number>;
}

export const ordersApi = {
  /**
   * Fetch paginated orders from the backend.
   * Supports filtering, searching, and sorting.
   */
  list: (params: OrdersParams = {}): Promise<OrdersResponse> => {
    const queryParams = new URLSearchParams();
    
    if (params.page) queryParams.set('page', String(params.page));
    if (params.pageSize) queryParams.set('pageSize', String(params.pageSize));
    if (params.status && params.status !== 'ALL') queryParams.set('status', params.status);
    if (params.search) queryParams.set('search', params.search);
    if (params.productType && params.productType !== 'ALL') queryParams.set('productType', params.productType);
    if (params.sortBy) queryParams.set('sortBy', params.sortBy);
    if (params.sortOrder) queryParams.set('sortOrder', params.sortOrder);
    
    // Q.61.32a — migrado de /api/orders para /v1/plan/orders.
    return request<OrdersResponse>(`/v1/plan/orders?${queryParams.toString()}`);
  },

  /**
   * Get a single order by ID.
   */
  get: (id: string): Promise<Order> =>
    // Q.61.32a — migrado de /api/orders/{id} para /v1/plan/orders/{id}.
    request<Order>(`/v1/plan/orders/${id}`),

  /**
   * Get aggregate statistics for all orders (uses full database).
   * NOT paginated — totals over plan.production_orders, que o mirror Q.131.C
   * mantém como WIP REAL do ERP (factory_raw.ordemfabrico), não dados demo.
   */
  stats: (): Promise<OrdersStats> =>
    // Q.61.32a — migrado de /api/orders/stats para /v1/plan/orders/stats.
    request<OrdersStats>('/v1/plan/orders/stats'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// PREFERENCE RULES API (Sprint E.3) — Camada 1 learned rules review
// ═══════════════════════════════════════════════════════════════════════════════

export type PreferenceRuleStatus = 'detected' | 'confirmed' | 'rejected';
export type PreferenceRuleType =
  | 'temporal_block'
  | 'tradeoff_preference'
  | 'operator_affinity'
  | 'phase_threshold';

export interface PreferenceRule {
  id: string;
  type: PreferenceRuleType;
  description: string;
  predicate: Record<string, any>;
  confidence: number;
  status: PreferenceRuleStatus;
  detected_from_commits: string[];
  confirmed_at: string | null;
  confirmed_by: string | null;
  review_notes: string | null;
}

// ═══════════════════════════════════════════════════════════════════════════════
// WORKER OPERATIONS API (Sprint H.2) — operator tablet
// ═══════════════════════════════════════════════════════════════════════════════

export interface WorkerOperation {
  id: string;
  order_id: string;
  operation_sequence: number;
  product_id: string;
  quantity: number;
  machine_id: string | null;
  scheduled_start: string;
  scheduled_end: string;
  scheduled_duration_hours: number | null;
  status: string;
  actual_start: string | null;
  actual_end: string | null;
  /** Q.170.C — boost combinado (cliente+ordem+barco); badge "Acelerada" > 50. */
  effective_boost: number;
}

/** Estado de uma fase após iniciar/concluir — Q.30.A. */
export interface OperationState {
  id: string;
  order_id: string;
  operation_sequence: number;
  status: string;
  actual_start: string | null;
  actual_end: string | null;
  actual_quantity: number | null;
}

export const workerOperationsApi = {
  today: (employeeId: string, params?: { as_of?: string }) => {
    const qs = params?.as_of ? `?as_of=${params.as_of}` : '';
    return request<WorkerOperation[]>(
      `/v1/plan/schedule/worker/${employeeId}/operations-today${qs}`,
    );
  },
  /**
   * Q.157.E — operador inicia uma operação do plano LIVE (SCHEDULED→IN_PROGRESS).
   * `operationId` é o `id` da WorkerOperation (= operation_id do commit LIVE).
   */
  start: (operationId: string) =>
    request<OperationState>(
      `/v1/plan/schedule/operation/${operationId}/start`,
      { method: 'POST', body: JSON.stringify({}) },
    ),
  /** Q.157.E — operador conclui uma operação do plano LIVE (IN_PROGRESS→COMPLETED). */
  complete: (operationId: string, payload?: { actual_quantity?: number }) =>
    request<OperationState>(
      `/v1/plan/schedule/operation/${operationId}/complete`,
      { method: 'POST', body: JSON.stringify(payload ?? {}) },
    ),
};

// ═══════════════════════════════════════════════════════════════════════════════
// CPO COMMITS API (Sprint E.1) — Timeline + MAP-Elites alternatives + decide
// ═══════════════════════════════════════════════════════════════════════════════

export interface CpoCommit {
  id: string;
  tenant_id: string;
  parent_id: string | null;
  commit_sha256: string;
  short_sha: string;
  author: string;
  message: string;
  kpis: Record<string, any>;
  delta: Record<string, any>;
  alternatives: Array<Record<string, any>>;
  cpo_meta: Record<string, any>;
  trust_index: number;
  operations_count: number;
  // Q.133.A.2 — estado do plano (DRAFT|LIVE) + sinal de plano degradado, para o
  // grid rotular honestamente um plano não-aprovado/degradado.
  status?: string;
  safety_net_triggered?: boolean;
  created_at: string | null;
  operations?: Array<Record<string, any>> | null;
}

export interface CpoAlternativeEnriched {
  rank: number;
  fitness: number;
  generation: number;
  descriptor: Record<string, any>;
  vs_primary: Record<string, string | null>;
  trade_off_narrative: string;
}

export interface CpoAlternativesResponse {
  commit_sha256: string;
  primary_kpis: Record<string, any>;
  alternatives: CpoAlternativeEnriched[];
}

export type CpoRejectionCategory =
  | 'COST'
  | 'QUALITY'
  | 'CUSTOMER'
  | 'CAPACITY'
  | 'MOLD'
  | 'WORKFORCE'
  | 'OTHER';

export interface CpoDecideRequest {
  chosen_alt_idx?: number | null;
  rejected_alt_idxs?: number[];
  reason?: string | null;
  decided_by?: string;
  /** Sprint Q.5 — required by backend when rejected_alt_idxs is non-empty. */
  rejection_category?: CpoRejectionCategory | null;
}

export interface CpoDecideResponse {
  commit_sha256: string;
  rejected_alternatives: Array<Record<string, any>>;
  user_preference_signal: Record<string, any>;
}

// Sprint Q.13.A — Plan v4 §6.2 alternative worker pairs
export interface CpoWorkerPairItem {
  chefe_id: string;
  partner_id: string | null;
  score: number;  // 0-10, higher is better
}

export interface CpoWorkerPairsResponse {
  operation_id: string;
  phase_id: string | null;
  needs_pair: boolean;
  pairs: CpoWorkerPairItem[];
}

export const cpoCommitsApi = {
  list: (params?: { limit?: number; excludeDegenerate?: boolean }) => {
    const sp = new URLSearchParams();
    if (params?.limit) sp.set('limit', String(params.limit));
    // Q.162.B — salta planos degenerados; o /overall pede o último SAUDÁVEL.
    if (params?.excludeDegenerate) sp.set('exclude_degenerate', 'true');
    const qs = sp.toString() ? `?${sp.toString()}` : '';
    return request<CpoCommit[]>(`/v1/plan/cpo/commits${qs}`);
  },

  get: (sha: string, opts?: { include_operations?: boolean }) => {
    const qs = opts?.include_operations ? '?include_operations=true' : '';
    return request<CpoCommit>(`/v1/plan/cpo/commits/${sha}${qs}`);
  },

  alternatives: (sha: string, opts?: { n?: number }) => {
    const qs = opts?.n ? `?n=${opts.n}` : '';
    return request<CpoAlternativesResponse>(
      `/v1/plan/cpo/commits/${sha}/alternatives${qs}`,
    );
  },

  decide: (sha: string, body: CpoDecideRequest) =>
    request<CpoDecideResponse>(`/v1/plan/cpo/commits/${sha}/decide`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /**
   * Sprint Q.13.A — top-N alternative worker pairs for an op (§6.2).
   * Returns `needs_pair=false` + empty pairs[] for non-pair phases —
   * frontend renders single-worker UI in that case.
   */
  workerPairs: (operationId: string, opts?: { top_n?: number }) => {
    const qs = opts?.top_n ? `?top_n=${opts.top_n}` : '';
    return request<CpoWorkerPairsResponse>(
      `/v1/plan/cpo/operations/${encodeURIComponent(operationId)}/worker-pairs${qs}`,
    );
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// PLAN OPERATIONS REORDER API (Q.115.C) — drag-drop manual
// ═══════════════════════════════════════════════════════════════════════════════

export interface ReorderRequest {
  operation_id: string;
  new_phase: string;
  new_start_ts: string; // ISO 8601 com tz
  new_operator_id?: string | null;
  /** Q.153.D1 — motivo do ajuste (do MoveBoatConfirm); guardado no delta+audit. */
  reason?: string;
}

export interface ReorderResponse {
  commit_sha: string;
  delta_summary: Record<string, unknown>;
}

export const planOperationsApi = {
  /** POST /v1/plan/operations/reorder — valida axiomas Spelke, cria novo ScheduleCommit. */
  reorder: (body: ReorderRequest) =>
    request<ReorderResponse>('/v1/plan/operations/reorder', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// PLAN EXCLUSION API (Q.153.C — tirar/repor barco do plano, reversível)
// ═══════════════════════════════════════════════════════════════════════════════

export interface ExcludedBoat {
  order_id: string;
  reason?: string | null;
  excluded_by: string;
  excluded_at: string; // ISO
}

export const planExclusionApi = {
  /** POST /v1/plan/boats/{order_id}/exclude — exclui/adia (reversível, idempotente). */
  excludeBoat: (orderId: string, reason?: string) =>
    request<ExcludedBoat>(`/v1/plan/boats/${encodeURIComponent(orderId)}/exclude`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  /** DELETE /v1/plan/boats/{order_id}/exclude — repõe no plano (idempotente). */
  reincludeBoat: (orderId: string) =>
    request<{ order_id: string; reincluded: boolean }>(
      `/v1/plan/boats/${encodeURIComponent(orderId)}/exclude`,
      { method: 'DELETE' },
    ),
  /** GET /v1/plan/boats/excluded — lista os barcos actualmente excluídos. */
  listExcludedBoats: () => request<ExcludedBoat[]>('/v1/plan/boats/excluded'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// LEARNING AFFINITIES API (Q.115.G)
// ═══════════════════════════════════════════════════════════════════════════════

export interface AffinitySignal {
  operator_id: string;
  operator_name: string;
  phase_id: string;
  phase_name: string;
  score: number;
  sample_count: number;
  last_computed_at: string;
}

export const learningAffinitiesApi = {
  list: (params?: { phase_id?: string; operator_id?: string; top?: number }) => {
    const qs = new URLSearchParams();
    if (params?.phase_id) qs.set('phase_id', params.phase_id);
    if (params?.operator_id) qs.set('operator_id', params.operator_id);
    if (params?.top !== undefined) qs.set('top', String(params.top));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<AffinitySignal[]>(`/v1/learning/affinities${suffix}`);
  },
};

export const preferenceRulesApi = {
  list: (params?: {
    status?: PreferenceRuleStatus;
    type?: PreferenceRuleType;
    min_confidence?: number;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.type) qs.set('type', params.type);
    if (params?.min_confidence !== undefined) {
      qs.set('min_confidence', String(params.min_confidence));
    }
    if (params?.limit !== undefined) qs.set('limit', String(params.limit));
    if (params?.offset !== undefined) qs.set('offset', String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<PreferenceRule[]>(`/v1/governance/preference-rules${suffix}`);
  },

  get: (ruleId: string) =>
    request<PreferenceRule>(`/v1/governance/preference-rules/${ruleId}`),

  confirm: (ruleId: string, payload?: { review_notes?: string }) =>
    request<PreferenceRule>(
      `/v1/governance/preference-rules/${ruleId}/confirm`,
      { method: 'POST', body: JSON.stringify(payload ?? {}) },
    ),

  reject: (ruleId: string, payload: { reason: string }) =>
    request<PreferenceRule>(
      `/v1/governance/preference-rules/${ruleId}/reject`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),

  patch: (
    ruleId: string,
    payload: {
      description?: string;
      predicate?: Record<string, any>;
      confidence?: number;
    },
  ) =>
    request<PreferenceRule>(
      `/v1/governance/preference-rules/${ruleId}`,
      { method: 'PATCH', body: JSON.stringify(payload) },
    ),
};

// ═══════════════════════════════════════════════════════════════════════════════
// Q.118.H — OTD risk (ordens em risco de atraso) — GET /v1/plan/orders/otd-risk
// ═══════════════════════════════════════════════════════════════════════════════

export interface OtdRiskOrder {
  of_id: string;
  product_name: string | null;
  product_type: string | null;
  current_phase_name: string | null;
  transport_date: string | null;
  late_probability: number;
  risk_band: string;
}

export interface OtdRiskResponse {
  model_available: boolean;
  orders: OtdRiskOrder[];
  total_orders?: number;
  high_risk_count?: number;
  reason?: string;
}

export const otdRiskApi = {
  list: (topN = 50) =>
    request<OtdRiskResponse>(`/v1/plan/orders/otd-risk?top_n=${topN}`),
};

// ═══════════════════════════════════════════════════════════════════════════════
// SPRINT Q.4 — Schedule Preview-Delta (drag-and-drop side-effect calc)
// ═══════════════════════════════════════════════════════════════════════════════

export interface PreviewIssue {
  type: string;
  severity: 'conflict' | 'warning';
  message: string;
  related_ids: string[];
}

export interface PreviewDeltaResult {
  operation_id: string;
  base_commit_sha: string | null;
  fitness_before: number;
  fitness_after: number;
  fitness_delta: number;
  throughput_eur_before: number;
  throughput_eur_after: number;
  throughput_eur_delta: number;
  conflicts: PreviewIssue[];
  warnings: PreviewIssue[];
  pair_rule_violation: boolean;
}

export interface ApplyMoveResult {
  commit_sha: string;
  parent_sha: string | null;
  operation_id: string;
  applied_by: string;
  reason: string;
}

/**
 * Identifica a operação a mover: `operation_id` directo (id da operação no
 * commit) OU `order_id` (= nº de OF / `hull`), que o backend resolve para a
 * operação certa do barco. Pelo menos um tem de vir preenchido.
 */
interface MoveTarget {
  operation_id?: string;
  order_id?: string;
}

export const schedulePreviewApi = {
  /** Sub-second drag-and-drop side-effect preview. Never runs CPO. */
  previewDelta: (
    payload: MoveTarget & {
      new_phase_id?: string;
      new_worker_ids?: string[];
    },
  ) =>
    request<PreviewDeltaResult>('/v1/plan/schedule/preview-delta', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Persist the move as a new ScheduleCommit (child of latest). */
  applyMove: (
    payload: MoveTarget & {
      new_phase_id?: string;
      new_worker_ids?: string[];
      reason: string;
    },
  ) =>
    request<ApplyMoveResult>('/v1/plan/schedule/apply-move', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// Q.141 — Timeline actuals (o que ACONTECEU: passado real de of_fp)
// ═══════════════════════════════════════════════════════════════════════════════

export interface TimelineActualItem {
  id?: string;
  of_id?: string;
  barco_nome?: string | null;
  modelo_id?: string | null;
  phase_id?: string;
  phase_nome?: string;
  worker_id?: string | null;
  worker_nome?: string | null;
  start?: string;
  end?: string;
  duration_min?: number | null;
  /** Q.153.C0 — barco (boats-only Q.136) vs acessório/strap; null = desconhecido. */
  is_boat?: boolean | null;
  source: string;
}

export interface TimelineExpedition {
  of_id?: string;
  barco_nome?: string | null;
  modelo_id?: string | null;
  transport_date?: string;
  source: string;
}

export interface TimelineActualsResponse {
  from: string;
  to: string;
  granularity: 'raw' | 'day';
  group_by?: string | null;
  items: TimelineActualItem[];
  lanes: unknown[];
  expeditions: TimelineExpedition[];
  truncated: boolean;
}

export const timelineActualsApi = {
  /** O que aconteceu no intervalo (fases reais + expedições). Datas YYYY-MM-DD.
   * Q.163 — `boats_only` (default true no backend) filtra a barcos no SQL. */
  list: (params: {
    from: string;
    to: string;
    group_by?: string;
    granularity?: 'raw' | 'day' | 'auto';
    limit?: number;
    boats_only?: boolean;
  }) =>
    request<TimelineActualsResponse>(
      `/v1/plan/timeline/actuals?${new URLSearchParams(
        filterParams({ ...params, limit: params.limit?.toString() }),
      )}`,
    ),
};

// Q.163 — catálogo canónico de fases (factory_raw.fases_producao), ordenado por
// FP_SEQUENCIA. O /overall usa-o para ordenar a vista "Por Fase" pela ordem real
// de produção e rotular com o nome canónico.
export interface PhaseCatalogItem {
  phase_id: string;
  phase_name: string;
  sequence: number;
  is_production: boolean;
}

export const phasesCatalogApi = {
  list: () => request<PhaseCatalogItem[]>(`/v1/plan/phases/catalog`),
};

// ─── Q.173.AD — contexto de filtros do Gantt ─────────────────────────────────
//
// GET /v1/plan/filters-context → FiltersContextOut
// Um fetch leve que entrega todos os mapas necessários para os 12 filtros
// do /overall sem inchar o payload do plano (2,3 MB).

export interface FiltersContextOut {
  /** SHA do plano-base do contexto (pode ser null se sem plano). */
  commit_sha: string | null;
  /** código do produto → nome real (factory_raw.produto). */
  product_names: Record<string, string>;
  /** order_id → código do produto (OF_P_ID via ordemfabrico). */
  order_products: Record<string, string>;
  /** código do produto → disciplina/gama (P_TP_ID_DISCIPLINA). */
  product_gamas: Record<string, string>;
  /** fase_id → setor (AREA_GROUPS). */
  phase_sectors: Record<string, string>;
  /** order_id → boost efetivo (snapshot pré-solve). */
  orders_boost: Record<string, number>;
  /** order_id → promessa de transporte ISO (só quando real). */
  orders_due: Record<string, string>;
  /** order_ids afetados por previsão de ruturas de materiais. */
  orders_material_risk: string[];
  /** IDs das fases de reparação (config planning.repair.phase_ids). */
  repair_phase_ids: string[];
  /** true se orders_material_risk veio da cache TTL (pode estar desatualizado). */
  material_risk_stale: boolean;
}

export const filtersContextApi = {
  get: () => request<FiltersContextOut>('/v1/plan/filters-context'),
};

