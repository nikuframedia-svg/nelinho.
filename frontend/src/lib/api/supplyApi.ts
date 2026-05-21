/**
 * ProdPlan ONE — API: supply, transporte.
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 */
import { request } from './client';

// ═══════════════════════════════════════════════════════════════════════════════
// SUPPLY MODULE - Supply Chain Planning
// ═══════════════════════════════════════════════════════════════════════════════

export const supplyApi = {
  // List all inventory
  listInventory: (params?: { limit?: number }) =>
    request<any>(`/v1/supply/inventory${params?.limit ? `?limit=${params.limit}` : ''}`),
  
  // Get single inventory item
  getInventory: (skuId: string) =>
    request<any>(`/v1/supply/inventory/${skuId}`),
  
  recordMovement: (data: {
    sku_id: string;
    movement_type?: 'consume' | 'receive' | 'adjust';
    transaction_type?: 'consume' | 'receive' | 'adjust';
    quantity_change?: number;
    qty_change?: number;
    reference?: string;
  }) =>
    request<any>('/v1/supply/inventory/movement', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  // Forecasting
  // Q.67.2.B — `historical_data` aceita tanto `{date, quantity}` como `{ds, y}`
  // (Prophet style). O backend lida com ambas as shapes.
  forecast: (data: {
    sku_id: string;
    periods_ahead?: number;
    historical_data?: Array<{ date: string; quantity: number } | { ds: string; y: number }>;
  }) =>
    request<any>('/v1/supply/forecast', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  // Get forecasts
  getForecast: (params?: { horizon_weeks?: number }) =>
    request<any>(`/v1/supply/forecast${params?.horizon_weeks ? `?horizon_weeks=${params.horizon_weeks}` : ''}`),
  
  // ROP (Reorder Point) calculation
  calculateROP: (skuId: string, params: {
    avg_daily_demand: number;
    lead_time_days: number;
    lead_time_std_dev?: number;
    service_level?: number;
  }) => {
    const queryParams = new URLSearchParams();
    queryParams.set('avg_daily_demand', String(params.avg_daily_demand));
    queryParams.set('lead_time_days', String(params.lead_time_days));
    if (params.lead_time_std_dev !== undefined) {
      queryParams.set('lead_time_std_dev', String(params.lead_time_std_dev));
    }
    if (params.service_level !== undefined) {
      queryParams.set('service_level', String(params.service_level));
    }
    return request<any>(`/v1/supply/rop/${skuId}?${queryParams.toString()}`);
  },
  
  // ABC Analysis
  abcAnalysis: (data: {
    skus_list: Array<{ sku_id: string; value: number }>;
  }) =>
    request<{
      distribution: {
        A: { count: number; skus: Array<{ sku_id: string; value: number }> };
        B: { count: number; skus: Array<{ sku_id: string; value: number }> };
        C: { count: number; skus: Array<{ sku_id: string; value: number }> };
      };
    }>('/v1/supply/abc', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  // Additional methods for compatibility — payload tipado, response ainda
  // genérica (legacy; trocar por DTOs Pydantic é Q.68.4.E).
  generateForecast: (data: Record<string, unknown>) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>('/v1/supply/forecast', { method: 'POST', body: JSON.stringify(data) }),

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getROP: () => request<any>('/v1/supply/rop'),

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getABC: () => request<any>('/v1/supply/abc'),

  calculateABC: (data?: Record<string, unknown>) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<any>('/v1/supply/abc', { method: 'POST', body: JSON.stringify(data || {}) }),

  // ─────────────────────────────────────────────────────────────────────
  // Q.67.2.B — helpers para SupplyPanels (ForecastPanel, AbcPanel, ShortageAlertsPanel)
  // ─────────────────────────────────────────────────────────────────────

  /** ABC analysis tolerante à shape legada `{items: [{sku_id, annual_value}]}`
   *  do AbcPanel. Converte para `skus_list`, chama o backend e devolve um
   *  array plano `[{sku_id, total_value, cumulative_pct, abc_class}]` para
   *  consumo directo. */
  abcAnalysisFlat: async (input: {
    items: Array<{ sku_id: string; annual_value: number }>;
  }): Promise<{
    items: Array<{
      sku_id: string;
      total_value?: number;
      cumulative_pct?: number;
      abc_class?: 'A' | 'B' | 'C';
    }>;
  }> => {
    const data = await request<any>('/v1/supply/abc', {
      method: 'POST',
      body: JSON.stringify({
        skus_list: input.items.map((it) => ({
          sku_id: it.sku_id,
          value: it.annual_value,
        })),
      }),
    });
    const dist = data?.distribution ?? {};
    const out: Array<{
      sku_id: string;
      total_value?: number;
      cumulative_pct?: number;
      abc_class?: 'A' | 'B' | 'C';
    }> = [];
    for (const klass of ['A', 'B', 'C'] as const) {
      const bucket = dist[klass]?.skus ?? [];
      for (const sku of bucket) {
        out.push({
          sku_id: sku.sku_id,
          total_value: sku.total_value ?? sku.value,
          cumulative_pct: sku.cumulative_pct,
          abc_class: klass,
        });
      }
    }
    return { items: out };
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// Q.67.2.B — Shortage alerts (copilot.alerts filtered por source=shortage_detector)
// ═══════════════════════════════════════════════════════════════════════════════

export interface CopilotShortageAlert {
  id?: string;
  source?: string;
  severity?: string;
  message?: string;
  created_at?: string;
  payload?: Record<string, unknown>;
}

export const supplyAlertsApi = {
  listShortageAlerts: (limit = 20) =>
    request<{ items?: CopilotShortageAlert[] }>(
      `/v1/copilot/alerts?source=shortage_detector&limit=${limit}`,
    ),
};

// ═══════════════════════════════════════════════════════════════════════════════
// SPRINT Q.1 — Transport / Despacho (stub — endpoints land in Q.2)
// ═══════════════════════════════════════════════════════════════════════════════

export type TransportBatchStatus = 'OPEN' | 'FROZEN' | 'DISPATCHED';

export interface TransportBatch {
  id: string;
  code: string;
  transport_date: string;
  truck_capacity_units: number;
  priority: number;
  destination: string | null;
  status: TransportBatchStatus;
  assigned_orders_count?: number;
}

export interface TransportSuggestion {
  type:
    | 'advance_boat'
    | 'delay_boat'
    | 'swap_between_batches'
    | 'complete_truck'
    | 'regroup_by_client';
  what: string;
  why: string;
  if_accept: string;
  if_reject: string;
  alternative?: string;
  affected_order_ids?: string[];
  /** Only set when type === 'swap_between_batches'. Identifies the
   *  batch the affected orders should be swapped INTO. */
  target_batch_id?: string;
}

/**
 * Transport API stub — Sprint Q.2 fills these endpoints in. The shapes match
 * the planned backend (see `src/plan/services/transport_batch_service.py`)
 * so consumers can wire forms now and the actual fetches light up once Q.2
 * lands the FastAPI router.
 */
/** Q.31.E — documento de expedição. */
export interface TransportManifestBoat {
  order_id: string;
  hull: number;
  product_name: string;
  product_type: string;
  current_phase: string;
  status: string;
}
export interface TransportManifest {
  batch: {
    id: string;
    code: string;
    transport_date: string | null;
    destination: string | null;
    status: string;
    truck_capacity_units: number;
  };
  boats: TransportManifestBoat[];
  boat_count: number;
  generated_at: string;
}

export const transportApi = {
  listBatches: (params?: { from_date?: string; to_date?: string; status?: TransportBatchStatus }) => {
    const qs = new URLSearchParams();
    if (params?.from_date) qs.set('from_date', params.from_date);
    if (params?.to_date) qs.set('to_date', params.to_date);
    if (params?.status) qs.set('status', params.status);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<TransportBatch[]>(`/v1/plan/transport/batches${suffix}`);
  },

  createBatch: (payload: {
    code: string;
    transport_date: string;
    truck_capacity_units?: number;
    destination?: string;
    priority?: number;
  }) =>
    request<TransportBatch>('/v1/plan/transport/batches', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  assignOrder: (batchId: string, orderId: string) =>
    request<TransportBatch>(
      `/v1/plan/transport/batches/${encodeURIComponent(batchId)}/orders`,
      { method: 'POST', body: JSON.stringify({ order_id: orderId }) },
    ),

  removeOrder: (batchId: string, orderId: string) =>
    request<TransportBatch>(
      `/v1/plan/transport/batches/${encodeURIComponent(batchId)}/orders/${encodeURIComponent(orderId)}`,
      { method: 'DELETE' },
    ),

  freeze: (batchId: string) =>
    request<TransportBatch>(
      `/v1/plan/transport/batches/${encodeURIComponent(batchId)}/freeze`,
      { method: 'POST' },
    ),

  dispatch: (batchId: string) =>
    request<TransportBatch>(
      `/v1/plan/transport/batches/${encodeURIComponent(batchId)}/dispatch`,
      { method: 'POST' },
    ),

  suggestions: (batchId: string) =>
    request<TransportSuggestion[]>(
      `/v1/plan/transport/batches/${encodeURIComponent(batchId)}/suggestions`,
    ),

  /** Q.31.E — documento de expedição (manifesto / packing list). */
  manifest: (batchId: string) =>
    request<TransportManifest>(
      `/v1/plan/transport/batches/${encodeURIComponent(batchId)}/manifest`,
    ),

  /**
   * Sprint Q.9 Onda 3.3 — list the order ids currently assigned to a
   * batch so the DispatchPage can render real draggable cards instead
   * of the previous placeholder. Empty array is a valid response
   * (batch exists but has no assignments yet).
   */
  listOrders: (batchId: string) =>
    request<{ batch_id: string; orders: string[] }>(
      `/v1/plan/transport/batches/${encodeURIComponent(batchId)}/orders`,
    ),
};

