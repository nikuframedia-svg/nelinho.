/**
 * ProdPlan ONE - API Client
 * =========================
 * 
 * Client functions for all backend endpoints.
 */

import { getErrorMessage } from './api-errors';
import { logToEndpoint } from './logger';
import { getCircuitBreaker } from './circuit-breaker';
import type {
  AllocationCreateResponse,
  AllocationCreatedItem,
  LabourCostSummaryResponse,
  OrderAllocationsResponse,
  PayrollCalculateResponse,
} from '../types/operacoes';

interface AllocationCreateRequest {
  requirements: Array<Record<string, unknown>>;
  employees: Array<Record<string, unknown>>;
  strategy?: 'skill_first' | 'cost_first' | 'balanced';
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Retry configuration
const MAX_RETRIES = 1; // Reduced from 3 to 1 to avoid flooding console
const RETRYABLE_STATUSES = [502, 504]; // Bad Gateway, Gateway Timeout (NOT 503 - often DB unavailable)
const INITIAL_RETRY_DELAY = 1000; // 1 second

// Retry configuration interface
interface RetryConfig {
  maxRetries?: number;
  retryableStatuses?: number[];
  initialDelay?: number;
}

/**
 * Get retry configuration for a specific endpoint
 * Some endpoints (like health checks) should not retry
 */
function getRetryConfig(endpoint: string): RetryConfig {
  // Health check endpoints should not retry
  if (endpoint === '/health' || endpoint === '/api/health' || endpoint.includes('/health')) {
    return { maxRetries: 0 };
  }
  
  // Database-dependent endpoints should not retry on 503
  // These will fail immediately if PostgreSQL is not running
  if (endpoint.includes('/v1/core/') || 
      endpoint.includes('/v1/plan/') || 
      endpoint.includes('/v1/profit/') ||
      endpoint.includes('/v1/hr/') ||
      endpoint.includes('/v1/supply/')) {
    return { maxRetries: 0 }; // No retry for DB-dependent endpoints
  }
  
  // Default configuration
  return {
    maxRetries: MAX_RETRIES,
    retryableStatuses: RETRYABLE_STATUSES,
    initialDelay: INITIAL_RETRY_DELAY,
  };
}

/**
 * Check if HTTP status is 404 (Not Found)
 * Used to identify when a feature/endpoint is not available
 */
function isNotFoundError(status: number): boolean {
  return status === 404;
}

// Helper to wait for a delay (exponential backoff)
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Helper to show retry toast (if ToastProvider is available)
let toastContext: { info: (msg: string) => string } | null = null;

export function setToastContext(context: { info: (msg: string) => string } | null) {
  toastContext = context;
}

/**
 * Convert a camelCase key to snake_case (employeeId → employee_id).
 *
 * Sprint Q.12 — antes do helper, FastAPI ignorava silenciosamente
 * params como `employeeId` porque esperava `employee_id`, e devolvia a
 * lista completa em vez de filtrada. A conversão fica num único sítio.
 */
const camelToSnake = (key: string): string =>
  key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);

/**
 * Filter out undefined/null values AND convert camelCase keys to
 * snake_case. Single conversion point for both query strings and
 * any other place that builds a backend-facing record.
 */
const filterParams = (params: Record<string, any> | undefined): Record<string, string> =>
  Object.fromEntries(
    Object.entries(params || {})
      .filter(([_, v]) => v !== undefined && v !== null)
      .map(([k, v]) => [camelToSnake(k), String(v)])
  );

// ═══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  retryCount = 0
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  
  // Get retry configuration for this endpoint
  const retryConfig = getRetryConfig(endpoint);
  const maxRetries = retryConfig.maxRetries ?? MAX_RETRIES;
  const retryableStatuses = retryConfig.retryableStatuses ?? RETRYABLE_STATUSES;
  const initialDelay = retryConfig.initialDelay ?? INITIAL_RETRY_DELAY;
  
  // Obter token de autenticação do localStorage
  const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
  // Q.18.AUTH — dev tenant default. Backend (Q.12 Onda 0.1) rejeita zero UUID
  // explicitamente (`Invalid tenant: zero UUID is reserved`). 000…001 é a
  // dev tenant seeded por scripts/bootstrap_dev_tenant.py. Ver plano Q.18.AUTH.
  const tenantId = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000001';
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  
  // Adicionar token se existir
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  // Adicionar tenant ID (requerido pelo backend)
  headers['X-Tenant-Id'] = tenantId;
  
  try {
    // Use circuit breaker to prevent cascading failures
    const circuitBreaker = getCircuitBreaker();
    let response: Response;
    
    try {
      response = await circuitBreaker.call(async () => {
        const fetchResponse = await fetch(url, {
          headers,
          ...options,
        });
        // Consider HTTP errors (5xx) as failures for circuit breaker
        if (!fetchResponse.ok && fetchResponse.status >= 500) {
          throw new Error(`HTTP ${fetchResponse.status}: ${fetchResponse.statusText}`);
        }
        return fetchResponse;
      });
    } catch (circuitError: any) {
      // Circuit breaker rejected (circuit is open)
      if (circuitError.message?.includes('Circuit breaker is open')) {
        const errorObj = new Error('Backend indisponível. Circuit breaker está aberto.');
        (errorObj as any).status = 503;
        throw errorObj;
      }
      // Re-throw network errors or HTTP 5xx errors
      throw circuitError;
    }

    if (!response.ok) {
      // 404 errors should not retry - feature may not be available
      if (isNotFoundError(response.status)) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.message || getErrorMessage({ status: 404, response: errorData } as any);
        const errorObj = new Error(errorMessage);
        (errorObj as any).status = 404;
        (errorObj as any).response = errorData;
        (errorObj as any).isFeatureNotAvailable = true; // Flag para identificar
        throw errorObj;
      }
      
      // Check if error is retryable and we haven't exceeded max retries
      if (retryableStatuses.includes(response.status) && retryCount < maxRetries) {
        const retryDelay = initialDelay * Math.pow(2, retryCount); // Exponential backoff
        
        // Show toast notification on first retry
        if (retryCount === 0 && toastContext) {
          toastContext.info(`Serviço temporariamente indisponível. Tentando reconectar em ${retryDelay / 1000}s...`);
        }
        
        // Wait before retrying
        await delay(retryDelay);
        
        // Retry the request
        return request<T>(endpoint, options, retryCount + 1);
      }
      
      // This is a final failure (not retryable or max retries exceeded)
      const isFinalFailure = !retryableStatuses.includes(response.status) || retryCount >= maxRetries;
      
      // Log only final failures
      if (isFinalFailure) {
        logToEndpoint('api.ts', 'response not ok', {
          status: response.status,
          statusText: response.statusText,
          url,
          retryCount,
        }, 'C');
      }
      
      const errorData = await response.json().catch(() => ({}));
      
      // Use Portuguese error messages
      const errorMessage = errorData.detail || errorData.message || getErrorMessage({ status: response.status, response: errorData } as any);
      const errorObj = new Error(errorMessage);
      (errorObj as any).status = response.status;
      (errorObj as any).response = errorData;
      
      // Log only final failures
      if (isFinalFailure) {
        logToEndpoint('api.ts', 'throwing error', {
          errorMessage,
          status: response.status,
          retryCount,
        }, 'C');
      }
      
      throw errorObj;
    }

    return await response.json();
  } catch (error: any) {
    // Network errors or other fetch failures - retry if applicable
    if (retryCount < maxRetries && !error.status) {
      const retryDelay = initialDelay * Math.pow(2, retryCount);
      
      // Show toast notification on first retry
      if (retryCount === 0 && toastContext) {
        toastContext.info(`Erro de ligação. Tentando reconectar em ${retryDelay / 1000}s...`);
      }
      
      await delay(retryDelay);
      return request<T>(endpoint, options, retryCount + 1);
    }
    
    // Log only final network errors (after all retries)
    if (retryCount >= maxRetries) {
      logToEndpoint('api.ts', 'network error after retries', {
        error: error.message,
        retryCount,
        url,
      }, 'C');
    }
    
    throw error;
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// CORE MODULE - Master Data
// ═══════════════════════════════════════════════════════════════════════════════

// Products
export const productsApi = {
  list: (params?: { limit?: number; offset?: number; status?: string }) =>
    request<any>(`/v1/core/products?${new URLSearchParams(filterParams(params))}`),
  
  get: (id: string) =>
    request<any>(`/v1/core/products/${id}`),
  
  create: (data: any) =>
    request<any>('/v1/core/products', { method: 'POST', body: JSON.stringify(data) }),
  
  update: (id: string, data: any) =>
    request<any>(`/v1/core/products/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  
  delete: (id: string) =>
    request<void>(`/v1/core/products/${id}`, { method: 'DELETE' }),
};

// Machines
export const machinesApi = {
  list: (params?: { limit?: number; offset?: number; status?: string }) =>
    request<any>(`/v1/core/machines?${new URLSearchParams(filterParams(params))}`),
  
  get: (id: string) =>
    request<any>(`/v1/core/machines/${id}`),
  
  create: (data: any) =>
    request<any>('/v1/core/machines', { method: 'POST', body: JSON.stringify(data) }),
  
  update: (id: string, data: any) =>
    request<any>(`/v1/core/machines/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  
  delete: (id: string) =>
    request<void>(`/v1/core/machines/${id}`, { method: 'DELETE' }),
};

// Employees
export const employeesApi = {
  list: (params?: { limit?: number; offset?: number; status?: string; department?: string }) =>
    request<any>(`/v1/core/employees?${new URLSearchParams(filterParams(params))}`),
  
  get: (id: string) =>
    request<any>(`/v1/core/employees/${id}`),
  
  create: (data: any) =>
    request<any>('/v1/core/employees', { method: 'POST', body: JSON.stringify(data) }),
  
  update: (id: string, data: any) =>
    request<any>(`/v1/core/employees/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  
  delete: (id: string) =>
    request<void>(`/v1/core/employees/${id}`, { method: 'DELETE' }),
};

// Operations
export const operationsApi = {
  list: (params?: { limit?: number; offset?: number }) =>
    request<any>(`/v1/core/operations?${new URLSearchParams(filterParams(params))}`),
  
  get: (id: string) =>
    request<any>(`/v1/core/operations/${id}`),
  
  create: (data: any) =>
    request<any>('/v1/core/operations', { method: 'POST', body: JSON.stringify(data) }),
  
  update: (id: string, data: any) =>
    request<any>(`/v1/core/operations/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  
  delete: (id: string) =>
    request<void>(`/v1/core/operations/${id}`, { method: 'DELETE' }),
};

// BOM
export const bomApi = {
  getByProduct: (productId: string) =>
    request<any>(`/v1/core/bom/products/${productId}`),
  
  get: (bomId: string) =>
    request<any>(`/v1/core/bom/${bomId}`),
  
  create: (data: any) =>
    request<any>('/v1/core/bom', { method: 'POST', body: JSON.stringify(data) }),
  
  update: (bomId: string, data: any) =>
    request<any>(`/v1/core/bom/${bomId}`, { method: 'PUT', body: JSON.stringify(data) }),
  
  delete: (bomId: string) =>
    request<void>(`/v1/core/bom/${bomId}`, { method: 'DELETE' }),
};

// Customers
export const customersApi = {
  list: (params?: { segment?: string; is_active?: boolean; price_tier?: string; limit?: number; offset?: number }) =>
    request<any>(`/v1/core/customers?${new URLSearchParams(filterParams(params))}`),
  
  get: (id: string) =>
    request<any>(`/v1/core/customers/${id}`),
  
  create: (data: any) =>
    request<any>('/v1/core/customers', { method: 'POST', body: JSON.stringify(data) }),
  
  update: (id: string, data: any) =>
    request<any>(`/v1/core/customers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  
  delete: (id: string) =>
    request<void>(`/v1/core/customers/${id}`, { method: 'DELETE' }),
};

// Suppliers
export const suppliersApi = {
  list: (params?: { material_category?: string; is_active?: boolean; is_preferred?: boolean; limit?: number; offset?: number }) =>
    request<any>(`/v1/core/suppliers?${new URLSearchParams(filterParams(params))}`),
  
  get: (id: string) =>
    request<any>(`/v1/core/suppliers/${id}`),
  
  create: (data: any) =>
    request<any>('/v1/core/suppliers', { method: 'POST', body: JSON.stringify(data) }),
  
  update: (id: string, data: any) =>
    request<any>(`/v1/core/suppliers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  
  delete: (id: string) =>
    request<void>(`/v1/core/suppliers/${id}`, { method: 'DELETE' }),
};

// Rates
export const ratesApi = {
  // Labor rates
  laborRates: {
    list: () => request<any>('/v1/core/rates/labor'),
    create: (data: any) => request<any>('/v1/core/rates/labor', { method: 'POST', body: JSON.stringify(data) }),
  },
  
  // Machine rates
  machineRates: {
    list: () => request<any>('/v1/core/rates/machine'),
    create: (data: any) => request<any>('/v1/core/rates/machine', { method: 'POST', body: JSON.stringify(data) }),
  },
  
  // Overhead rates
  overheadRates: {
    list: () => request<any>('/v1/core/rates/overhead'),
    create: (data: any) => request<any>('/v1/core/rates/overhead', { method: 'POST', body: JSON.stringify(data) }),
  },
};

// Tenants
export const tenantsApi = {
  list: () => request<any>('/v1/core/tenants'),
  get: (id: string) => request<any>(`/v1/core/tenants/${id}`),
  create: (data: any) => request<any>('/v1/core/tenants', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: any) => request<any>(`/v1/core/tenants/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  activate: (id: string) =>
    request<any>(`/v1/core/tenants/${id}/activate`, { method: 'POST' }),
  suspend: (id: string) =>
    request<any>(`/v1/core/tenants/${id}/suspend`, { method: 'POST' }),
  updateSubscription: (id: string, data: any) =>
    request<any>(`/v1/core/tenants/${id}/subscription`, { method: 'PATCH', body: JSON.stringify(data) }),
};

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
  
  create: (data: any) =>
    request<any>('/v1/profit/scenarios', { method: 'POST', body: JSON.stringify(data) }),
  
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
// HR MODULE - Human Resources
// ═══════════════════════════════════════════════════════════════════════════════

// Allocations
export const allocationsApi = {
  list: (params?: { scheduleId?: string; employeeId?: string; limit?: number }) =>
    request<OrderAllocationsResponse>(
      `/v1/hr/allocations?${new URLSearchParams(filterParams(params))}`,
    ),

  create: (data: AllocationCreateRequest) =>
    request<AllocationCreateResponse>('/v1/hr/allocations', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: Partial<AllocationCreatedItem>) =>
    request<AllocationCreatedItem>(`/v1/hr/allocations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    request<void>(`/v1/hr/allocations/${id}`, { method: 'DELETE' }),

  optimize: (scheduleId: string) =>
    request<AllocationCreateResponse>(
      `/v1/hr/allocations/optimize/${scheduleId}`,
      { method: 'POST' },
    ),
};

// Payroll
export const payrollApi = {
  calculate: (data: {
    year_month?: string; // ISO date string (YYYY-MM-DD)
    period?: string; // Alias for year_month
    burden_rate?: number;
    overtime_multiplier?: number;
  }) =>
    request<PayrollCalculateResponse>('/v1/hr/payroll/calculate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getMonthlyCost: (params?: { from_date?: string; to_date?: string }) => {
    const queryParams = new URLSearchParams();
    if (params?.from_date) queryParams.set('from_date', params.from_date);
    if (params?.to_date) queryParams.set('to_date', params.to_date);
    const query = queryParams.toString();
    return request<LabourCostSummaryResponse>(
      `/v1/hr/payroll/monthly-cost${query ? `?${query}` : ''}`,
    );
  },
  
  getEmployeePayroll: (employeeId: string, month: string, year: number) =>
    request<any>(`/v1/hr/payroll/employee/${employeeId}?month=${month}&year=${year}`),
  
  process: (data: { month: string; year: number }) =>
    request<any>('/v1/hr/payroll/process', { method: 'POST', body: JSON.stringify(data) }),
  
  // Get payroll by period
  getByPeriod: (period: string) =>
    request<any>(`/v1/hr/payroll/period/${period}`),
};

// Productivity
export const productivityApi = {
  list: (params?: { employeeId?: string; startDate?: string; endDate?: string; limit?: number }) =>
    request<any>(`/v1/hr/productivity/?${new URLSearchParams(filterParams(params))}`),
  
  getMetrics: (employeeId: string) =>
    request<any>(`/v1/hr/productivity/employee/${employeeId}`),
  
  record: (data: {
    employee_id: string;
    operation_id: string;
    order_id: string;
    record_date: string;
    standard_hours: number;
    actual_hours: number;
    standard_quantity: number;
    actual_quantity: number;
    good_quantity: number;
  }) =>
    request<any>('/v1/hr/productivity/record', { method: 'POST', body: JSON.stringify(data) }),
  
  getReport: (params: { startDate: string; endDate: string }) =>
    request<any>(`/v1/hr/productivity/report?${new URLSearchParams(filterParams(params))}`),
};

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
  forecast: (data: {
    sku_id: string;
    periods_ahead?: number;
    historical_data?: Array<{ date: string; quantity: number }>;
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
  
  // Additional methods for compatibility
  generateForecast: (data: any) =>
    request<any>('/v1/supply/forecast', { method: 'POST', body: JSON.stringify(data) }),
  
  getROP: () =>
    request<any>('/v1/supply/rop'),
  
  getABC: () =>
    request<any>('/v1/supply/abc'),
  
  calculateABC: (data?: any) =>
    request<any>('/v1/supply/abc', { method: 'POST', body: JSON.stringify(data || {}) }),
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
    
    return request<OrdersResponse>(`/api/orders?${queryParams.toString()}`);
  },
  
  /**
   * Get a single order by ID.
   */
  get: (id: string): Promise<Order> =>
    request<Order>(`/api/orders/${id}`),
  
  /**
   * Get aggregate statistics for all orders (uses full database).
   * This is NOT paginated - returns totals from all 27,380 orders.
   */
  stats: (): Promise<OrdersStats> =>
    request<OrdersStats>('/api/orders/stats'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// ERRORS API - Paginated Production Errors
// ═══════════════════════════════════════════════════════════════════════════════

export interface ErrorsParams {
  page?: number;
  pageSize?: number;
  severity?: 1 | 2 | 3;
  phase?: string;
  search?: string;
  sortBy?: 'id' | 'severity' | 'description' | 'orderId';
  sortOrder?: 'asc' | 'desc';
}

export interface ErrorsResponse {
  data: ProductionError[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  hasNextPage: boolean;
  hasPreviousPage: boolean;
}

export interface ProductionError {
  id: string;
  orderId: string | null;
  phaseName: string;
  evalPhaseName: string;
  description: string;
  severity: number;
  severityLabel: 'Minor' | 'Major' | 'Critical';
}

export interface ErrorsStats {
  total: number;
  bySeverity: {
    minor: number;
    major: number;
    critical: number;
  };
  ordersWithErrors: number;
  topDescriptions: Array<{ description: string; count: number }>;
  topPhases: Array<{ phase: string; count: number }>;
}

export const errorsApi = {
  /**
   * Fetch paginated errors from the backend.
   * Supports filtering by severity, phase, and search.
   */
  list: (params: ErrorsParams = {}): Promise<ErrorsResponse> => {
    const queryParams = new URLSearchParams();
    
    if (params.page) queryParams.set('page', String(params.page));
    if (params.pageSize) queryParams.set('pageSize', String(params.pageSize));
    if (params.severity) queryParams.set('severity', String(params.severity));
    if (params.phase) queryParams.set('phase', params.phase);
    if (params.search) queryParams.set('search', params.search);
    if (params.sortBy) queryParams.set('sortBy', params.sortBy);
    if (params.sortOrder) queryParams.set('sortOrder', params.sortOrder);
    
    return request<ErrorsResponse>(`/api/errors?${queryParams.toString()}`);
  },
  
  /**
   * Get aggregate statistics for all errors (uses full database).
   * This is NOT paginated - returns totals from all 89,836 errors.
   */
  stats: (): Promise<ErrorsStats> =>
    request<ErrorsStats>('/api/errors/stats'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// ALLOCATIONS API - Paginated Employee Allocations
// ═══════════════════════════════════════════════════════════════════════════════

export interface AllocationsParams {
  page?: number;
  pageSize?: number;
  limit?: number;
  employeeId?: number;
  phase?: string;
  isLeader?: boolean;
  search?: string;
  sortBy?: 'startDate' | 'employeeName' | 'phaseName' | 'id';
  sortOrder?: 'asc' | 'desc';
}

export interface AllocationsResponse {
  data: Allocation[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  hasNextPage: boolean;
  hasPreviousPage: boolean;
}

export interface Allocation {
  id: string;
  orderId: string | null;
  phaseId: string | null;
  phaseName: string;
  employeeId: string | null;
  employeeName: string;
  isLeader: boolean;
  startDate: string | null;
  endDate: string | null;
}

export interface AllocationsStats {
  total: number;
  asLeader: number;
  uniqueEmployees: number;
  uniqueOrders: number;
  avgPerEmployee: number;
  topPhases: Array<{ phase: string; count: number }>;
  topEmployees: Array<{ employee: string; count: number }>;
}

export const allocationsApiPaginated = {
  /**
   * Fetch paginated allocations from the backend.
   * Supports filtering by employee, phase, leader status, and search.
   */
  list: (params: AllocationsParams = {}): Promise<AllocationsResponse> => {
    const queryParams = new URLSearchParams();
    
    if (params.page) queryParams.set('page', String(params.page));
    if (params.pageSize) queryParams.set('pageSize', String(params.pageSize));
    if (params.employeeId) queryParams.set('employeeId', String(params.employeeId));
    if (params.phase) queryParams.set('phase', params.phase);
    if (params.isLeader !== undefined) queryParams.set('isLeader', String(params.isLeader));
    if (params.search) queryParams.set('search', params.search);
    if (params.sortBy) queryParams.set('sortBy', params.sortBy);
    if (params.sortOrder) queryParams.set('sortOrder', params.sortOrder);
    
    return request<AllocationsResponse>(`/api/allocations?${queryParams.toString()}`);
  },
  
  /**
   * Get aggregate statistics for all allocations (uses full database).
   * This is NOT paginated - returns totals from all 346,832 allocations.
   */
  stats: (): Promise<AllocationsStats> =>
    request<AllocationsStats>('/api/allocations/stats'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// HEALTH & UTILITY
// ═══════════════════════════════════════════════════════════════════════════════

export const healthApi = {
  check: () => request<any>('/health'),
  ready: () => request<any>('/health/ready'),
  live: () => request<any>('/health/live'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// COPILOT API
// ═══════════════════════════════════════════════════════════════════════════════

// Import types from separate file (import before using)
import type { CopilotAskRequest, CopilotResponse, DailyFeedbackResponse } from './copilot-types';

// Re-export types for external use
export type { CopilotAskRequest, CopilotResponse, DailyFeedbackResponse };

export const copilotApi = {
  ask: async (data: CopilotAskRequest) => {
    // Verificar se há token - se não houver, usar diretamente o endpoint dev
    const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
    
    if (!token) {
      // Sem token, usar diretamente endpoint dev (sem autenticação)
      // Criar request manual para endpoint dev com tenant_id correto
      const url = `${API_BASE}/api/copilot/ask-dev`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-Id': '00000000-0000-0000-0000-000000000001', // Tenant dev
        },
        body: JSON.stringify(data),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}`;
        const errorObj = new Error(errorMessage);
        (errorObj as any).status = response.status;
        throw errorObj;
      }
      
      return await response.json();
    }
    
    // Com token, tentar endpoint normal primeiro
    try {
      return await request<CopilotResponse>('/api/copilot/ask', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    } catch (error: any) {
      // Se erro de autenticação, tentar endpoint dev
      if (error.status === 401 || error.status === 403 || error.message?.includes('Not authenticated') || error.message?.includes('Unauthorized')) {
        // Criar request manual para endpoint dev com tenant_id correto
        const url = `${API_BASE}/api/copilot/ask-dev`;
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Tenant-Id': '00000000-0000-0000-0000-000000000001', // Tenant dev
          },
          body: JSON.stringify(data),
        });
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}`;
          const errorObj = new Error(errorMessage);
          (errorObj as any).status = response.status;
          throw errorObj;
        }
        
        return await response.json();
      }
      throw error;
    }
  },
  
  action: (data: { action_type: string; suggestion_id: string; payload: any }) =>
    request<any>('/api/copilot/action', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  getDailyFeedback: (date?: string) => {
    const endpoint = `/api/copilot/daily-feedback${date ? `?date=${date}` : ''}`;
    const devEndpoint = `/api/copilot/daily-feedback-dev${date ? `?date=${date}` : ''}`;
    
    return request<DailyFeedbackResponse>(endpoint).catch((error: any) => {
      // Se erro de autenticação, tentar endpoint dev (silenciar erro 401)
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        // Não logar erro 401 - é esperado e vamos usar dev endpoint
        return request<DailyFeedbackResponse>(devEndpoint);
      }
      throw error;
    });
  },
  
  getSuggestion: (id: string) =>
    request<CopilotResponse>(`/api/copilot/suggestions/${id}`),
  
  health: () =>
    request<any>('/api/copilot/health').catch((error: any) => {
      // Se erro 401, retornar resposta padrão (health pode funcionar sem auth)
      if (error.status === 401) {
        return {
          status: 'degraded',
          ollama: 'unknown',
          embeddings_model: 'unknown',
        };
      }
      throw error;
    }),
  
  getRecommendations: () => {
    const endpoint = '/api/copilot/recommendations';
    const devEndpoint = '/api/copilot/recommendations-dev';
    
    return request<any[]>(endpoint).catch((error: any) => {
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        return request<any[]>(devEndpoint);
      }
      throw error;
    });
  },
  
  explainRecommendations: (data: { recommendations: any[]; user_query?: string }) => {
    const endpoint = '/api/copilot/recommendations/explain';
    const devEndpoint = '/api/copilot/recommendations/explain-dev';
    
    return request<CopilotResponse>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    }).catch((error: any) => {
      // Se erro de autenticação, tentar endpoint dev (silenciar erro 401)
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        // Não logar erro 401 - é esperado e vamos usar dev endpoint
        return request<CopilotResponse>(devEndpoint, {
          method: 'POST',
          body: JSON.stringify(data),
        });
      }
      throw error;
    });
  },
  
  getInsights: (date?: string) => {
    const endpoint = `/api/copilot/insights${date ? `?date=${date}` : ''}`;
    const devEndpoint = `/api/copilot/insights-dev${date ? `?date=${date}` : ''}`;
    
    return request<any>(endpoint).catch((error: any) => {
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        return request<any>(devEndpoint);
      }
      throw error;
    });
  },
  
  // Conversations API
  createConversation: (title?: string) => {
    // Se não houver token, rejeitar imediatamente (sem fazer chamada)
    const token = typeof window !== 'undefined' ? (localStorage.getItem('auth_token') || localStorage.getItem('token')) : null;
    if (!token) {
      const error = new Error('Authentication required');
      (error as any).status = 401;
      return Promise.reject(error);
    }
    
    return request<{ id: string; title: string; created_at: string }>('/api/copilot/conversations', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }).catch((error: any) => {
      // Se erro 401, re-throw para que o componente possa tratar (criar conversa sem BD)
      throw error;
    });
  },
  
  listConversations: (params?: { limit?: number; offset?: number; archived?: boolean }) => {
    // Se não houver token, retornar imediatamente array vazio (sem fazer chamada)
    const token = typeof window !== 'undefined' ? (localStorage.getItem('auth_token') || localStorage.getItem('token')) : null;
    if (!token) {
      return Promise.resolve([]);
    }
    
    const queryParams = new URLSearchParams();
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    if (params?.archived !== undefined) queryParams.set('archived', String(params.archived));
    return request<Array<{
      id: string;
      title: string;
      created_at: string;
      last_message_at: string | null;
      is_archived: boolean;
    }>>(`/api/copilot/conversations?${queryParams.toString()}`).catch((error: any) => {
      // Se erro 401, retornar array vazio (conversas requerem auth, mas não são críticas)
      if (error.status === 401 || error.status === 403) {
        return [];
      }
      throw error;
    });
  },
  
  getConversationMessages: (conversationId: string, params?: { limit?: number; offset?: number }) => {
    const queryParams = new URLSearchParams();
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    return request<Array<{
      id: string;
      role: 'user' | 'copilot';
      content_text: string;
      content_structured: any | null;
      created_at: string;
    }>>(`/api/copilot/conversations/${conversationId}/messages?${queryParams.toString()}`).catch((error: any) => {
      // Se erro 401, retornar array vazio
      if (error.status === 401) {
        return [];
      }
      throw error;
    });
  },
  
  sendMessage: (conversationId: string, data: CopilotAskRequest) =>
    request<CopilotResponse>(`/api/copilot/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify(data),
    }).catch((error: any) => {
      // Se erro 401, re-throw para que o componente possa usar endpoint normal
      throw error;
    }),
  
  renameConversation: (conversationId: string, title: string) =>
    request<{ id: string; title: string }>(`/api/copilot/conversations/${conversationId}/rename`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),
  
  archiveConversation: (conversationId: string) =>
    request<{ id: string; is_archived: boolean }>(`/api/copilot/conversations/${conversationId}/archive`, {
      method: 'POST',
    }),
  
  // Actions API
  listActions: (params?: { limit?: number; offset?: number; status?: string }) => {
    const queryParams = new URLSearchParams();
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    if (params?.status) queryParams.set('status', params.status);
    return request<Array<{
      transaction_id: string;
      action_type: string;
      user_id: string;
      plan_id: string | null;
      before_state: Record<string, any>;
      after_state: Record<string, any>;
      status: 'executed' | 'failed' | 'rolled_back';
      executed_at: string;
      rollback_until: string | null;
    }>>(`/api/copilot/actions?${queryParams.toString()}`).catch((error: any) => {
      // Se erro 404, endpoint pode não existir ainda, retornar array vazio
      if (error.status === 404) {
        return [];
      }
      throw error;
    });
  },
  
  rollbackAction: (transactionId: string) =>
    request<{ transaction_id: string; status: string; message: string }>(`/api/copilot/actions/${transactionId}/rollback`, {
      method: 'POST',
    }),
  
  // RAG API
  ingestRAG: (sourceType: string, sourceId: string, text: string, metadata?: Record<string, any>) =>
    request<{ status: string; chunks_created: number; source_type: string; source_id: string }>(
      '/api/copilot/rag/ingest',
      {
        method: 'POST',
        body: JSON.stringify({
          source_type: sourceType,
          source_id: sourceId,
          text: text,
          metadata: metadata || {},
        }),
      }
    ),
  
  // Sandbox API
  executeSandbox: (data: {
    action_type: string;
    target?: string;
    params?: Record<string, any>;
    capture_state?: string[];
  }) =>
    request<{
      success: boolean;
      before_state: Record<string, any>;
      after_state: Record<string, any>;
      deltas: Record<string, any>;
      actual_impact: Record<string, any>;
      message: string;
    }>('/api/copilot/sandbox', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// DECISIONS MODULE - Decision Intelligence Platform
// ═══════════════════════════════════════════════════════════════════════════════

export interface DecisionRun {
  id: string;
  title: string;
  action_type: string;
  target: string;
  status: 'PROPOSED' | 'APPROVED' | 'EXECUTED' | 'ROLLED_BACK' | 'REJECTED';
  sandbox_result?: Record<string, any>;
  before_state: Record<string, any>;
  after_state?: Record<string, any>;
  proposed_by: string;
  proposed_at: string;
  executed_at?: string;
  rolled_back_at?: string;
  approvals: Array<{
    approver_id: string;
    status: 'PENDING' | 'APPROVED' | 'REJECTED';
    comment?: string;
    approved_at?: string;
  }>;
}

export interface DecisionListResponse {
  total: number;
  page: number;
  page_size: number;
  items: DecisionRun[];
}

export interface DecisionProposalRequest {
  title: string;
  action_type: string;
  target: string;
  sandbox_result?: Record<string, any>;
  before_state: Record<string, any>;
  after_state?: Record<string, any>;
  required_approver_roles?: string[];
  required_approver_ids?: string[];
}

export interface ApprovalRequest {
  status: 'APPROVED' | 'REJECTED';
  comment?: string;
}

export const decisionsApi = {
  list: (params?: { status?: string; page?: number; page_size?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status_filter', params.status);
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString());
    return request<DecisionListResponse>(`/v1/decisions?${searchParams.toString()}`);
  },
  
  get: (id: string) =>
    request<DecisionRun>(`/v1/decisions/${id}`),
  
  propose: (data: DecisionProposalRequest) =>
    request<DecisionRun>('/v1/decisions/propose', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  approve: (id: string, data: ApprovalRequest) =>
    request<DecisionRun>(`/v1/decisions/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  execute: (id: string) =>
    request<DecisionRun>(`/v1/decisions/${id}/execute`, {
      method: 'POST',
    }),
  
  rollback: (id: string) =>
    request<DecisionRun>(`/v1/decisions/${id}/rollback`, {
      method: 'POST',
    }),
  
  getAuditTrail: (id: string) =>
    request<Array<{
      timestamp: string;
      event: string;
      by: string;
      details: Record<string, any>;
    }>>(`/v1/decisions/${id}/audit`),

  /**
   * Sprint Q.9 Onda 3.4 — bulk approve / reject in one round trip.
   * Per-item: SoD violation on one decision does NOT abort the rest;
   * the response carries `{ok, failed, results}`. Plan v4 §8 WG04.
   */
  bulkAct: (
    items: Array<{
      decision_id: string;
      action: 'approve' | 'reject' | 'request_changes';
      reason?: string;
    }>,
  ) =>
    request<{
      ok: number;
      failed: number;
      results: Array<{
        decision_id: string;
        status: 'ok' | 'error';
        error?: string;
      }>;
    }>(`/v1/governance/decisions/bulk`, {
      method: 'POST',
      body: JSON.stringify({ items }),
    }),

  /**
   * Sprint Q.13.C C.3.2 — modify the action_data payload BEFORE
   * approving. Plan v4 §8 WG05: "modificar antes de aprovar". Reason
   * is mandatory (≥10 chars) so the audit trail explains the edit.
   */
  modifyPayload: (
    decisionId: string,
    body: { patch: Record<string, unknown>; reason: string },
  ) =>
    request<DecisionRun>(
      `/v1/governance/decisions/${encodeURIComponent(decisionId)}/payload`,
      { method: 'PATCH', body: JSON.stringify(body) },
    ),
};

export const apiInfo = () => request<any>('/');

// ═══════════════════════════════════════════════════════════════════════════════
// EXPLAINABILITY API (C20)
// ═══════════════════════════════════════════════════════════════════════════════

export const explainApi = {
  getMetric: (metricId: string) => 
    request<any>(`/v1/explain/metric/${metricId}`),
  
  getCatalog: () => 
    request<any>('/v1/explain/catalog'),
  
  getBlockedMetrics: () => 
    request<any>('/v1/explain/blocked'),
  
  computeValue: (data: { metric_id: string; params?: Record<string, any> }) => 
    request<any>('/v1/explain/compute', { 
      method: 'POST', 
      body: JSON.stringify(data) 
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// DIGITAL TWIN API (C30)
// ═══════════════════════════════════════════════════════════════════════════════

export const twinApi = {
  createScenario: (data: { title: string; description?: string }) => 
    request<any>('/v1/twin/scenarios', { 
      method: 'POST', 
      body: JSON.stringify(data) 
    }),
  
  getScenario: (scenarioId: string) => 
    request<any>(`/v1/twin/scenarios/${scenarioId}`),
  
  listScenarios: () => 
    request<any>('/v1/twin/scenarios'),
  
  applyDelta: (scenarioId: string, delta: any) => 
    request<any>(`/v1/twin/scenarios/${scenarioId}/apply-delta`, { 
      method: 'POST', 
      body: JSON.stringify(delta) 
    }),
  
  simulate: (scenarioId: string) => 
    request<any>(`/v1/twin/scenarios/${scenarioId}/simulate`, { 
      method: 'POST' 
    }),
  
  solve: (scenarioId: string) => 
    request<any>(`/v1/twin/scenarios/${scenarioId}/solve`, { 
      method: 'POST' 
    }),
  
  compare: (scenarioId: string, baselineId?: string) => {
    const queryParams = baselineId ? `?baseline_id=${baselineId}` : '';
    return request<any>(`/v1/twin/scenarios/${scenarioId}/compare${queryParams}`);
  },
  
  deleteScenario: (scenarioId: string) =>
    request<void>(`/v1/twin/scenarios/${scenarioId}`, { method: 'DELETE' }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// FACTORY DATA PRODUCT API (C10)
// ═══════════════════════════════════════════════════════════════════════════════

export const factoryApi = {
  getActiveRun: () => 
    request<any>('/v1/factory/meta/active-run'),
  
  getSemanticView: (viewId: string, params?: Record<string, any>) => {
    const queryParams = params ? `?${new URLSearchParams(filterParams(params))}` : '';
    return request<any>(`/v1/factory/semantic/${viewId}${queryParams}`);
  },
  
  getSnapshot: (params?: { run_id?: string }) => {
    const queryParams = params?.run_id ? `?run_id=${params.run_id}` : '';
    return request<any>(`/v1/factory/snapshot${queryParams}`);
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// SANDBOX API
// ═══════════════════════════════════════════════════════════════════════════════

export const sandboxApi = {
  createScenario: (data: any) => 
    request<any>('/v1/sandbox/scenarios', { 
      method: 'POST', 
      body: JSON.stringify(data) 
    }),
  
  getScenario: (scenarioId: string) => 
    request<any>(`/v1/sandbox/scenarios/${scenarioId}`),
  
  listScenarios: () => 
    request<any>('/v1/sandbox/scenarios'),
  
  applySuggestion: (scenarioId: string, suggestionId: string) => 
    request<any>(`/v1/sandbox/scenarios/${scenarioId}/apply-suggestion`, {
      method: 'POST',
      body: JSON.stringify({ suggestion_id: suggestionId }),
    }),
  
  simulate: (scenarioId: string) => 
    request<any>(`/v1/sandbox/scenarios/${scenarioId}/simulate`, { 
      method: 'POST' 
    }),
  
  getExecPack: (scenarioId: string) => 
    request<any>(`/v1/sandbox/scenarios/${scenarioId}/exec-pack`),
  
  publish: (scenarioId: string) => 
    request<any>(`/v1/sandbox/scenarios/${scenarioId}/publish`, { 
      method: 'POST' 
    }),
  
  deleteScenario: (scenarioId: string) =>
    request<void>(`/v1/sandbox/scenarios/${scenarioId}`, { method: 'DELETE' }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// IMPROVE (SUGGESTIONS) API
// ═══════════════════════════════════════════════════════════════════════════════

export const improveApi = {
  listSuggestions: (params?: { status?: string; domain?: string }) => {
    const queryParams = new URLSearchParams(filterParams(params));
    return request<any>(`/v1/improve/suggestions?${queryParams}`);
  },
  
  getSuggestion: (suggestionId: string) => 
    request<any>(`/v1/improve/suggestions/${suggestionId}`),
  
  generateSuggestions: (data: { scope?: string; limit?: number }) => 
    request<any>('/v1/improve/suggestions/generate', { 
      method: 'POST', 
      body: JSON.stringify(data) 
    }),
  
  approveSuggestion: (suggestionId: string) => 
    request<any>(`/v1/improve/suggestions/${suggestionId}/approve`, { 
      method: 'POST' 
    }),
  
  rejectSuggestion: (suggestionId: string, reason?: string) => 
    request<any>(`/v1/improve/suggestions/${suggestionId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  
  getActionsCatalog: () => 
    request<any>('/v1/improve/actions'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// CAPABILITIES API (Feature Gating)
// ═══════════════════════════════════════════════════════════════════════════════

export const capabilitiesApi = {
  get: () => 
    request<any>('/v1/capabilities'),
  
  getModules: () => 
    request<any>('/v1/capabilities/modules'),
  
  getFeatures: () => 
    request<any>('/v1/capabilities/features'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// CATALOG API (API Discovery)
// ═══════════════════════════════════════════════════════════════════════════════

export const catalogApi = {
  get: () => 
    request<any>('/v1/catalog'),
  
  getSummary: () => 
    request<any>('/v1/catalog/summary'),
  
  getEndpoints: () => 
    request<any>('/v1/catalog/endpoints'),
  
  getViews: () => 
    request<any>('/v1/catalog/views'),
  
  getMetrics: () => 
    request<any>('/v1/catalog/metrics'),
  
  getBlockedMetrics: () => 
    request<any>('/v1/catalog/blocked-metrics'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// KPI REGISTRY API
// ═══════════════════════════════════════════════════════════════════════════════

export const kpiRegistryApi = {
  list: () => 
    request<any>('/v1/kpi/registry'),
  
  get: (kpiId: string) => 
    request<any>(`/v1/kpi/registry/${kpiId}`),
  
  explain: (kpiId: string) => 
    request<any>(`/v1/kpi/registry/${kpiId}/explain`),
  
  getBlocked: () => 
    request<any>('/v1/kpi/blocked'),
  
  calculate: (data: { kpi_id: string; scope?: any; period?: any }) => 
    request<any>('/v1/kpi/calculate', { 
      method: 'POST', 
      body: JSON.stringify(data) 
    }),
  
  getDomains: () =>
    request<any>('/v1/kpi/domains'),

  getTrustGuide: () =>
    request<any>('/v1/kpi/trust-index-guide'),
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
}

export const workerOperationsApi = {
  today: (employeeId: string, params?: { as_of?: string }) => {
    const qs = params?.as_of ? `?as_of=${params.as_of}` : '';
    return request<WorkerOperation[]>(
      `/v1/plan/schedule/worker/${employeeId}/operations-today${qs}`,
    );
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// QUALITY REWORK API (Sprint H.2) — tablet issue report
// ═══════════════════════════════════════════════════════════════════════════════

export interface ReworkCreatePayload {
  of_id: string;
  error_code: string;
  detected_at?: string;
  error_description?: string;
  root_cause_category?: string;
  causer_employee_id?: string;
  cost_estimate_eur?: number;
  hours_lost?: number;
  notes?: string;
}

export const qualityReworkApi = {
  create: (payload: ReworkCreatePayload) =>
    request<any>('/v1/quality/rework', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
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
  list: (params?: { limit?: number }) => {
    const qs = params?.limit ? `?limit=${params.limit}` : '';
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
// SPRINT R.1 — Learning visibility (Aprendizagem panel)
// ═══════════════════════════════════════════════════════════════════════════════

export interface LearningPairStats {
  total_commits_with_rejection: number;
  total_pairs: number;
  eligible_for_dpo: number;
  by_category: Record<string, number>;
  by_weekday: Record<string, number>;
  last_30d: { commits: number; pairs: number; eligible: number };
  last_90d: { commits: number; pairs: number; eligible: number };
  abl_pairs_today: number;
  min_reason_len: number;
}

export interface LearningRuleStats {
  total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  last_detector_run_at: string | null;
  rules_re_emitted_count: number;
}

export interface LearningWeightStats {
  status: string;
  current_weights: Record<string, number>;
  default_weights: Record<string, number>;
  multipliers: Record<string, number>;
  pairs_used: number;
  commits_scanned: number;
  trained_at: string | null;
  blend_learned_pct: number;
  min_pairs_threshold: number;
  reason: string | null;
}

// Sprint R.4 — weight history (Camada 2 audit modal)
export interface LearningWeightExplanation {
  kpi: string;
  label: string;
  delta_pct: number;
  direction: 'up' | 'down' | 'stable' | string;
  dominant_category: string | null;
  pairs_used: number;
  human_text: string;
}

export interface LearningWeightHistoryEntry {
  trained_at: string | null;
  valid_from: string | null;
  status: string | null;
  weights: Record<string, number>;
  multipliers: Record<string, number>;
  pairs_used: number;
  explanations: LearningWeightExplanation[];
  warnings: Array<Record<string, any>>;
}

export interface LearningWeightHistoryResponse {
  entries: LearningWeightHistoryEntry[];
}

export const learningApi = {
  pairs: (params?: { window_days?: number; min_reason_len?: number }) => {
    const qs = new URLSearchParams();
    if (params?.window_days !== undefined) qs.set('window_days', String(params.window_days));
    if (params?.min_reason_len !== undefined) qs.set('min_reason_len', String(params.min_reason_len));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<LearningPairStats>(`/v1/governance/learning/pairs${suffix}`);
  },
  rules: () => request<LearningRuleStats>('/v1/governance/learning/rules'),
  weights: () => request<LearningWeightStats>('/v1/governance/learning/weights'),
  weightHistory: (limit: number = 12) =>
    request<LearningWeightHistoryResponse>(
      `/v1/governance/learning/weights/history?limit=${limit}`,
    ),
  // Sprint R.5.3 — adapter management
  adapter: () =>
    request<LearningAdapterState>('/v1/governance/learning/adapter'),
  promoteAdapter: (
    version: string,
    payload: {
      reason: string;
      decided_by?: string;
      intent_match_rate?: number;
      safety_violations_count?: number;
    },
  ) =>
    request<LearningAdapterState>(
      `/v1/governance/learning/adapter/promote/${encodeURIComponent(version)}`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  rollbackAdapter: (payload: { reason: string; decided_by?: string }) =>
    request<LearningAdapterState>(
      '/v1/governance/learning/adapter/rollback',
      { method: 'POST', body: JSON.stringify(payload) },
    ),
};

export interface LearningAdapterState {
  active_version: string | null;
  promoted_at: string | null;
  promoted_by: string | null;
  reason: string | null;
  intent_match_rate: number | null;
  safety_violations_count: number | null;
  has_previous: boolean;
}

// ═══════════════════════════════════════════════════════════════════════════════
// SPRINT Q.7 — Diagnostics dashboard (per-module health + infra pings)
// ═══════════════════════════════════════════════════════════════════════════════

export type ModuleHealthStatus = 'green' | 'yellow' | 'red';

export interface DiagnosticsModule {
  module: string;
  src_files: number;
  test_files: number;
  routes: number;
  todo_count: number;
  import_errors: string[];
  import_error_count: number;
  health: ModuleHealthStatus;
}

export interface DiagnosticsModulesResponse {
  modules: DiagnosticsModule[];
  summary: {
    total: number;
    green: number;
    yellow: number;
    red: number;
    total_routes: number;
    total_import_errors: number;
    total_todos: number;
  };
  module_catalogue: string[];
}

export interface InfraComponent {
  component: string;
  healthy: boolean;
  detail: string;
  latency_ms: number | null;
}

export interface InfrastructureResponse {
  items: InfraComponent[];
  summary: {
    total: number;
    healthy: number;
    unhealthy: number;
  };
}

export interface DiagnosticsFullResponse {
  modules: DiagnosticsModule[];
  modules_summary: { total: number; green: number; yellow: number; red: number };
  infrastructure: InfrastructureResponse;
  trust_index: {
    composite?: number;
    components?: Record<string, number | null>;
    effective_gates?: Record<string, boolean>;
    error?: string;
    source?: string;
  };
  commits: {
    commits_last_7_days?: number;
    latest_commit_sha?: string | null;
    latest_commit_at?: string | null;
    error?: string;
    source?: string;
  };
}

export const diagnosticsApi = {
  modules: () => request<DiagnosticsModulesResponse>('/v1/diagnostics/modules'),
  infrastructure: () => request<InfrastructureResponse>('/v1/diagnostics/infrastructure'),
  full: () => request<DiagnosticsFullResponse>('/v1/diagnostics/full'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// SPRINT Q.1 — DQA Trust Index v2
// ═══════════════════════════════════════════════════════════════════════════════

export type TrustScope = 'factory' | 'order' | 'phase';

export interface TrustIndexV2Components {
  completeness: number;
  validity: number;
  freshness: number;
  consistency: number;
  provenance: number;
  anomaly: number;
  evidence: number;
  causal_coherence: number | null;
  /** Legacy alias when the API returns include_legacy_keys=true. */
  timeliness?: number;
}

export interface TrustIndexV2Weights {
  completeness: number;
  validity: number;
  freshness: number;
  consistency: number;
  provenance: number;
  anomaly: number;
  evidence: number;
}

export interface TrustIndexV2EffectiveGates {
  solver_suggestion_only: boolean;
  use_p90_durations: boolean;
  auto_reorder: boolean;
  auto_commit: boolean;
  quality_disposition: boolean;
}

export interface TrustIndexV2Response {
  scope: TrustScope;
  scope_id: string | null;
  composite: number;
  components: TrustIndexV2Components;
  weights: TrustIndexV2Weights;
  effective_gates: TrustIndexV2EffectiveGates;
}

export const dqaApi = {
  trustIndex: (params?: {
    scope?: TrustScope;
    scope_id?: string;
    order_id?: string;
    phase_id?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.scope) qs.set('scope', params.scope);
    if (params?.scope_id) qs.set('scope_id', params.scope_id);
    if (params?.order_id) qs.set('order_id', params.order_id);
    if (params?.phase_id) qs.set('phase_id', params.phase_id);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<TrustIndexV2Response>(`/v1/dqa/trust-index${suffix}`);
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// SPRINT Q.1 — Tenant Configuration (ConfigStore)
// ═══════════════════════════════════════════════════════════════════════════════

export type ConfigDataType =
  | 'int'
  | 'float'
  | 'bool'
  | 'string'
  | 'json'
  | 'duration'
  | 'currency';

export interface ConfigEntry {
  id: string;
  category: string;
  key: string;
  value: unknown;
  data_type: ConfigDataType;
  valid_from: string;
  valid_to: string | null;
  last_modified_by: string | null;
  last_modified_at: string;
}

export interface ConfigCategoryValues {
  category: string;
  values: Record<string, unknown>;
}

export interface ConfigBulkEntry {
  category: string;
  key: string;
  value: unknown;
  data_type: ConfigDataType;
}

export const configApi = {
  /** Latest active value for one key. 404 if never set. */
  get: (category: string, key: string) =>
    request<ConfigEntry>(`/v1/config/${encodeURIComponent(category)}/${encodeURIComponent(key)}`),

  /** All active values in a category as `{key: value}`. */
  listCategory: (category: string) =>
    request<ConfigCategoryValues>(`/v1/config/${encodeURIComponent(category)}`),

  /** Full audit history (oldest → newest, including soft-deleted). */
  history: (category: string, key: string) =>
    request<ConfigEntry[]>(
      `/v1/config/${encodeURIComponent(category)}/${encodeURIComponent(key)}/history`,
    ),

  /** Set or override a single key. */
  set: (
    category: string,
    key: string,
    payload: { value: unknown; data_type: ConfigDataType },
  ) =>
    request<ConfigEntry>(
      `/v1/config/${encodeURIComponent(category)}/${encodeURIComponent(key)}`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),

  /** Apply many overrides atomically (one audit row per entry). */
  bulkSet: (entries: ConfigBulkEntry[]) =>
    request<ConfigEntry[]>('/v1/config/bulk', {
      method: 'PATCH',
      body: JSON.stringify({ entries }),
    }),

  /** Revert a config row by id; creates a new audit row pointing at the reverted value. */
  rollback: (configId: string) =>
    request<ConfigEntry>(`/v1/config/rollback/${encodeURIComponent(configId)}`, {
      method: 'POST',
    }),

  /** Sprint Q.6 — list every category that has at least one seeded default. */
  listCategories: () =>
    request<{ categories: Array<{ category: string; default_keys: number }>; total: number }>(
      '/v1/config/categories',
    ),

  /** Sprint Q.6 — reset a key to its seeded default value. 404 if no seed exists. */
  resetToDefault: (category: string, key: string) =>
    request<ConfigEntry>(
      `/v1/config/${encodeURIComponent(category)}/${encodeURIComponent(key)}/reset-to-default`,
      { method: 'POST' },
    ),

  /** Snapshot the entire tenant config (read-only). */
  exportSnapshot: () => request<Record<string, unknown>>('/v1/config/snapshot/export'),

  /** Replace the tenant config with the supplied snapshot. */
  importSnapshot: (snapshot: Record<string, unknown>) =>
    request<{ written: number }>('/v1/config/snapshot/import', {
      method: 'POST',
      body: JSON.stringify(snapshot),
    }),
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

export const schedulePreviewApi = {
  /** Sub-second drag-and-drop side-effect preview. Never runs CPO. */
  previewDelta: (payload: {
    operation_id: string;
    new_phase_id?: string;
    new_worker_ids?: string[];
  }) =>
    request<PreviewDeltaResult>('/v1/plan/schedule/preview-delta', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Persist the move as a new ScheduleCommit (child of latest). */
  applyMove: (payload: {
    operation_id: string;
    new_phase_id?: string;
    new_worker_ids?: string[];
    reason: string;
  }) =>
    request<ApplyMoveResult>('/v1/plan/schedule/apply-move', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// SPRINT Q.3 — Workforce Employees extras (GC01-GC10)
// ═══════════════════════════════════════════════════════════════════════════════

export interface QualityScoreResult {
  employee_id: string;
  score: number;
  defects: number;
  operations: number;
  defect_rate: number;
  method: 'laplace_smoothed' | 'default_no_history';
}

export interface QualityScoreOverrideResult {
  employee_id: string;
  ml_score: number;
  override_score: number;
  reason: string;
  preference_rule_logged: boolean;
}

export interface SkillMatrixRow {
  phase_id: string;
  phase_name: string | null;
  can_do: boolean;
  nivel: number | null;
  ops_count: number;
  last_used_at: string | null;
}

export interface SkillMatrixResult {
  employee_id: string;
  phases: SkillMatrixRow[];
  total: number;
}

export interface OperationHistoryRow {
  schedule_id: string;
  order_id: string;
  scheduled_start_date: string;
  scheduled_end_date: string;
  status: string;
  operation_sequence: number;
  actual_duration_hours: number | null;
}

export interface OperationHistoryResult {
  employee_id: string;
  operations: OperationHistoryRow[];
  limit: number;
  offset: number;
  returned: number;
}

export const workforceEmployeesApi = {
  qualityScore: (employeeId: string) =>
    request<QualityScoreResult>(
      `/v1/workforce/employees/${encodeURIComponent(employeeId)}/quality-score`,
    ),

  overrideQualityScore: (
    employeeId: string,
    payload: { score: number; reason: string },
  ) =>
    request<QualityScoreOverrideResult>(
      `/v1/workforce/employees/${encodeURIComponent(employeeId)}/quality-score`,
      { method: 'PATCH', body: JSON.stringify(payload) },
    ),

  skillMatrix: (employeeId: string) =>
    request<SkillMatrixResult>(
      `/v1/workforce/employees/${encodeURIComponent(employeeId)}/skill-matrix`,
    ),

  toggleSkill: (
    employeeId: string,
    payload: {
      phase_id: string;
      can_do: boolean;
      nivel?: number;
      reason?: string;
    },
  ) =>
    request<{ employee_id: string; phase_id: string; can_do: boolean }>(
      `/v1/workforce/employees/${encodeURIComponent(employeeId)}/skills`,
      { method: 'PATCH', body: JSON.stringify(payload) },
    ),

  history: (employeeId: string, params?: { limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set('limit', String(params.limit));
    if (params?.offset !== undefined) qs.set('offset', String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<OperationHistoryResult>(
      `/v1/workforce/employees/${encodeURIComponent(employeeId)}/history${suffix}`,
    );
  },

  softDelete: (employeeId: string, payload: { reason?: string }) =>
    request<{ employee_id: string; status: string; reason?: string }>(
      `/v1/workforce/employees/${encodeURIComponent(employeeId)}/soft-delete`,
      { method: 'POST', body: JSON.stringify(payload) },
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
}

/**
 * Transport API stub — Sprint Q.2 fills these endpoints in. The shapes match
 * the planned backend (see `src/plan/services/transport_batch_service.py`)
 * so consumers can wire forms now and the actual fetches light up once Q.2
 * lands the FastAPI router.
 */
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

// ═══════════════════════════════════════════════════════════════════════════════
// Q.17.C — YAML POLICY (NL → tenant_rules + lifecycle)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Shape of a tenant rule as returned by the API.
 * Mirrors `RuleProposalService.serialize_rule` (src/governance/yaml_policy/service.py).
 */
export interface YamlPolicyRule {
  id: string;
  rule_id: string;
  description: string;
  status: 'proposed' | 'approved' | 'active' | 'suspended' | 'rolled_back' | 'rejected';
  event_type: string;
  payload: {
    id: string;
    description: string;
    when: { event: string; conditions: Array<{ field: string; op: string; value: unknown }> };
    then: Array<{ action: string; params: Record<string, unknown> }>;
    constraints?: { axioms_required?: string[] };
    safety?: { max_fires_per_day?: number; expires?: string };
    [key: string]: unknown;
  };
  proposed_by_user_id: string | null;
  approved_by_user_id: string | null;
  proposed_at: string | null;
  approved_at: string | null;
  activated_at: string | null;
  suspended_at: string | null;
  fire_count: number;
  last_fired_at: string | null;
  nl_source: string | null;
}

export interface YamlPolicyRevision {
  id: string;
  action: 'proposed' | 'approved' | 'rejected' | 'modified' | 'suspended' | 'rolled_back' | 'reactivated';
  actor_user_id: string | null;
  reason: string | null;
  created_at: string | null;
}

export const yamlPolicyApi = {
  /** NL → LLM → validated rule, persisted as status=proposed. */
  propose: (nlText: string) =>
    request<{ rule: YamlPolicyRule }>(
      '/v1/governance/yaml-policy/rules/propose',
      { method: 'POST', body: JSON.stringify({ nl_text: nlText }) },
    ),

  list: (params?: { status?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status_filter', params.status);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    const tail = qs.toString();
    return request<{ rules: YamlPolicyRule[]; total: number }>(
      `/v1/governance/yaml-policy/rules${tail ? `?${tail}` : ''}`,
    );
  },

  get: (ruleId: string) =>
    request<{ rule: YamlPolicyRule; revisions: YamlPolicyRevision[] }>(
      `/v1/governance/yaml-policy/rules/${encodeURIComponent(ruleId)}`,
    ),

  approve: (ruleId: string, reason?: string) =>
    request<{ rule: YamlPolicyRule }>(
      `/v1/governance/yaml-policy/rules/${encodeURIComponent(ruleId)}/approve`,
      { method: 'POST', body: JSON.stringify({ reason: reason ?? null }) },
    ),

  reject: (ruleId: string, reason: string) =>
    request<{ rule: YamlPolicyRule }>(
      `/v1/governance/yaml-policy/rules/${encodeURIComponent(ruleId)}/reject`,
      { method: 'POST', body: JSON.stringify({ reason }) },
    ),

  suspend: (ruleId: string, reason?: string) =>
    request<{ rule: YamlPolicyRule }>(
      `/v1/governance/yaml-policy/rules/${encodeURIComponent(ruleId)}/suspend`,
      { method: 'POST', body: JSON.stringify({ reason: reason ?? null }) },
    ),

  rollback: (ruleId: string, reason: string) =>
    request<{ rule: YamlPolicyRule }>(
      `/v1/governance/yaml-policy/rules/${encodeURIComponent(ruleId)}/rollback`,
      { method: 'POST', body: JSON.stringify({ reason }) },
    ),
};
