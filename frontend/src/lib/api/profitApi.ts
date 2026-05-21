/**
 * ProdPlan ONE — API: profit, pricing, dashboards de profit/CEO, OEE, ML.
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 */
import { request, filterParams } from './client';

// ═══════════════════════════════════════════════════════════════════════════════
// PROFIT MODULE - Cost & Pricing
// ═══════════════════════════════════════════════════════════════════════════════

// KPIs
export const kpisApi = {
  getSnapshot: () => request<any>('/v1/profit/kpis/snapshot'),
  getSnapshotDev: () => request<any>('/v1/profit/kpis/snapshot-dev'),
  getSnapshotExplained: () => request<any>('/v1/profit/kpis/snapshot-explained'),
  getOtdHeatmap: (weeks: number = 12) => request<any>(`/v1/profit/kpis/otd-heatmap?weeks=${weeks}`),
};

// COGS
export const cogsApi = {
  calculate: (data: {
    order_id: string;
    product_id?: string;
    quantity?: number;
    bom_costs?: Record<string, any>;
    labor_allocations?: Array<Record<string, any>>;
    machine_usage?: Array<Record<string, any>>;
    setup_activities?: Array<Record<string, any>>;
    overhead_rate?: number;
    total_production_hours?: number;
    scrap_rate?: number;
  }) =>
    request<any>('/v1/profit/cogs/calculate', { method: 'POST', body: JSON.stringify(data) }),
  
  getOrderCOGS: (orderId: string) =>
    request<any>(`/v1/profit/cogs/orders/${orderId}`),
  
  getOrderMargin: (orderId: string, sellingPrice: number) =>
    request<any>(`/v1/profit/cogs/orders/${orderId}/margin?selling_price=${sellingPrice}`),
  
  // Legacy methods for backward compatibility (may not exist in backend)
  getBreakdown: (productId: string) =>
    request<any>(`/v1/profit/cogs/breakdown/${productId}`),
  
  list: () =>
    request<any>('/v1/profit/cogs/analyses'),
};

// Pricing
export const pricingApi = {
  recommend: (data: { 
    order_id: string;
    base_markup_percent?: number;
    target_margin_percent?: number;
    demand_pressure?: number;
    inventory_factor?: number;
    competitor_factor?: number;
    seasonality_factor?: number;
  }) =>
    request<any>('/v1/profit/pricing/recommend', { method: 'POST', body: JSON.stringify(data) }),
  
  simulate: (data: {
    order_id: string;
    prices: number[];
    quantity?: number;
  }) =>
    request<any>('/v1/profit/pricing/simulate', { method: 'POST', body: JSON.stringify(data) }),
  
  // Legacy alias for backward compatibility
  calculate: (data: { product_id: string; strategy: string; target_margin?: number }) =>
    request<any>('/v1/profit/pricing/recommend', { method: 'POST', body: JSON.stringify(data) }),
  
  getStrategies: () =>
    request<any>('/v1/profit/pricing/strategies'),
  
  updatePrice: (productId: string, price: number) =>
    request<any>(`/v1/profit/pricing/products/${productId}`, { method: 'PATCH', body: JSON.stringify({ price }) }),
  
  // List pricing configurations
  list: () =>
    request<any>('/v1/profit/pricing'),
};

// Scenarios
export const scenariosApi = {
  list: () =>
    request<any>('/v1/profit/scenarios'),
  
  get: (id: string) =>
    request<any>(`/v1/profit/scenarios/${id}`),
  
  create: (data: Record<string, unknown>) =>
    request<unknown>('/v1/profit/scenarios', { method: 'POST', body: JSON.stringify(data) }),
  
  run: (id: string) =>
    request<any>(`/v1/profit/scenarios/${id}/run`, { method: 'POST' }),
  
  delete: (id: string) =>
    request<void>(`/v1/profit/scenarios/${id}`, { method: 'DELETE' }),
  
  simulate: (data: {
    base_order_id: string;
    scenario_name?: string;
    material_multiplier?: number;
    labor_multiplier?: number;
    machine_multiplier?: number;
    overhead_multiplier?: number;
    scrap_multiplier?: number;
    volume_multiplier?: number;
  }) =>
    request<any>('/v1/profit/scenarios/simulate', { method: 'POST', body: JSON.stringify(data) }),
  
  sensitivity: (data: {
    base_order_id: string;
    component: string; // 'material', 'labor', 'machine', etc.
    range_percent?: number[];
  }) =>
    request<any>('/v1/profit/scenarios/sensitivity', { method: 'POST', body: JSON.stringify(data) }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// PROFIT DASHBOARD API (Sprint H.3) — €/dia + targets + trend
// ═══════════════════════════════════════════════════════════════════════════════

export interface ProfitDashboardResponse {
  date: string;
  throughput_eur: {
    today: number;
    mtd: number;
    ytd: number;
    target_min: number;
    target_max: number;
    on_target: 'below' | 'on' | 'above';
  };
  trend_14d: Array<{ date: string; throughput_eur: number }>;
  top_skus: Array<Record<string, any>>;
  currency: string;
  source: string;
}

export const profitDashboardApi = {
  get: (params?: { as_of?: string }) => {
    const qs = params?.as_of ? `?as_of=${params.as_of}` : '';
    return request<ProfitDashboardResponse>(`/v1/profit/dashboard${qs}`);
  },
};

// ─── Q.31.A — drill-down de lucro (margem por barco) ─────────────────────

export interface OrderMarginRow {
  order_id: string;
  hull: string;
  product_name: string;
  product_type: string;
  status: string;
  calculated: boolean;
  revenue_eur: number | null;
  total_cogs: number | null;
  margin_eur: number | null;
  margin_pct: number | null;
}

export interface OrderMarginsResponse {
  count: number;
  items: OrderMarginRow[];
}

export interface MarginSummaryResponse {
  days: number;
  order_count: number;
  avg_margin_eur: number | null;
  median_margin_eur: number | null;
  negative_count: number;
}

export const profitApi = {
  orderMargins: (params?: { date_from?: string; date_to?: string; limit?: number }) =>
    request<OrderMarginsResponse>(
      `/v1/profit/orders/margins?${new URLSearchParams(filterParams(params))}`,
    ),

  marginSummary: (days = 30) =>
    request<MarginSummaryResponse>(`/v1/profit/orders/margin-summary?days=${days}`),
};

// ═══════════════════════════════════════════════════════════════════════════════
// SPRINT Q.5 — CEO dashboard tiles (OTD / Backlog / Alerts / FPY / Expeditions)
// ═══════════════════════════════════════════════════════════════════════════════

export interface OTDByClient {
  client_name: string;
  on_time: number;
  late: number;
  total: number;
  otd_pct: number;
}

export interface OTDResponse {
  window_days: number;
  on_time: number;
  late: number;
  total: number;
  otd_pct: number;
  by_client: OTDByClient[];
}

export interface BacklogClientRow {
  client_name: string;
  pending_orders: number;
  pending_value_eur: number;
  earliest_deadline: string | null;
}

export interface BacklogResponse {
  items: BacklogClientRow[];
  count: number;
}

export interface ActiveAlert {
  id: string;
  code: string;
  severity: 'INFO' | 'WARN' | 'CRITICAL';
  title: string;
  message_pt: string;
  status: string;
  created_at: string | null;
  context: Record<string, unknown>;
}

export interface ActiveAlertsResponse {
  items: ActiveAlert[];
  count: number;
  by_severity: Record<'INFO' | 'WARN' | 'CRITICAL', number>;
}

export interface FPYResponse {
  window_days: number;
  orders_total: number;
  orders_with_rework: number;
  first_pass_yield_pct: number;
}

export interface ExpeditionRow {
  batch_id: string;
  code: string;
  transport_date: string;
  truck_capacity_units: number;
  assigned_orders: number;
  status: string;
  destination: string | null;
  risk: 'ok' | 'near_capacity' | 'over_capacity';
}

export interface ExpeditionsResponse {
  horizon_days: number;
  items: ExpeditionRow[];
  count: number;
}

export const ceoDashboardApi = {
  otd: (params?: { window_days?: number }) => {
    const qs = params?.window_days ? `?window_days=${params.window_days}` : '';
    return request<OTDResponse>(`/v1/profit/otd${qs}`);
  },

  backlogByClient: (params?: { limit?: number }) => {
    const qs = params?.limit ? `?limit=${params.limit}` : '';
    return request<BacklogResponse>(`/v1/profit/backlog-by-client${qs}`);
  },

  activeAlerts: (params?: { severity?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.severity) qs.set('severity', params.severity);
    if (params?.limit !== undefined) qs.set('limit', String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<ActiveAlertsResponse>(`/v1/profit/dashboard/active-alerts${suffix}`);
  },

  firstPassYield: (params?: { window_days?: number }) => {
    const qs = params?.window_days ? `?window_days=${params.window_days}` : '';
    return request<FPYResponse>(`/v1/quality/first-pass-yield${qs}`);
  },

  expeditionsNextNDays: (params?: { horizon_days?: number }) => {
    const qs = params?.horizon_days ? `?horizon_days=${params.horizon_days}` : '';
    return request<ExpeditionsResponse>(`/v1/plan/transport/expeditions/next-n-days${qs}`);
  },
};


// ═══════════════════════════════════════════════════════════════════════════════
// Q.52.C — OEE (/v1/profit/oee) — consolidação de fetch cru
// ═══════════════════════════════════════════════════════════════════════════════
//
// Várias páginas (qualidade, direcao) chamavam `/v1/profit/oee` com `fetch`
// directo, saltando o circuit breaker / retry / headers do `apiFetch`. Este
// wrapper é a forma única de pedir OEE. As páginas adoptam-no depois — Q.52.C
// não toca nas páginas.

export interface OEEComponent {
  group_value: string;
  /** Componentes 0-1: disponibilidade × desempenho × qualidade = oee. */
  availability: number;
  performance: number;
  quality: number;
  oee: number;
  sample_size: number;
  sample_excluded: number;
}

export interface OEEResponse {
  date_from: string;
  date_to: string;
  group_by: 'none' | 'phase' | 'shift' | 'product_type' | 'mold';
  overall: OEEComponent;
  breakdown: OEEComponent[];
}

export const profitOeeApi = {
  /** OEE das operações NELO vivas, opcionalmente agrupado. */
  get: (params?: {
    date_from?: string;
    date_to?: string;
    group_by?: 'phase' | 'shift' | 'product_type' | 'mold';
  }) =>
    request<OEEResponse>(
      `/v1/profit/oee?${new URLSearchParams(filterParams(params))}`,
    ),
};

