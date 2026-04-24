/**
 * ProdPlan ONE - API Client
 * =========================
 * 
 * Client functions for all backend endpoints.
 */

import { getErrorMessage } from './api-errors';
import { logToEndpoint } from './logger';
import { getCircuitBreaker } from './circuit-breaker';

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
 * Filter out undefined and null values from params object
 * Prevents URLSearchParams from converting undefined to string "undefined"
 */
const filterParams = (params: Record<string, any> | undefined): Record<string, string> => 
  Object.fromEntries(
    Object.entries(params || {}).filter(([_, v]) => v !== undefined && v !== null)
  ) as Record<string, string>;

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
  const tenantId = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000000';
  
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
    request<any>(`/v1/core/products?${new URLSearchParams(params as any)}`),
  
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
    request<any>(`/v1/core/machines?${new URLSearchParams(params as any)}`),
  
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
    request<any>(`/v1/core/employees?${new URLSearchParams(params as any)}`),
  
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
    request<any>(`/v1/core/operations?${new URLSearchParams(params as any)}`),
  
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
    request<any>(`/v1/core/customers?${new URLSearchParams(params as any)}`),
  
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
    request<any>(`/v1/core/suppliers?${new URLSearchParams(params as any)}`),
  
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
    request<any>(`/v1/plan/capacity/utilization?${new URLSearchParams(params as any)}`),
  
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
    request<any>(`/v1/hr/allocations?${new URLSearchParams(params as any)}`),
  
  create: (data: any) =>
    request<any>('/v1/hr/allocations', { method: 'POST', body: JSON.stringify(data) }),
  
  update: (id: string, data: any) =>
    request<any>(`/v1/hr/allocations/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  
  delete: (id: string) =>
    request<void>(`/v1/hr/allocations/${id}`, { method: 'DELETE' }),
  
  optimize: (scheduleId: string) =>
    request<any>(`/v1/hr/allocations/optimize/${scheduleId}`, { method: 'POST' }),
};

// Payroll
export const payrollApi = {
  calculate: (data: {
    year_month?: string; // ISO date string (YYYY-MM-DD)
    period?: string; // Alias for year_month
    burden_rate?: number;
    overtime_multiplier?: number;
  }) =>
    request<any>('/v1/hr/payroll/calculate', { method: 'POST', body: JSON.stringify(data) }),
  
  getMonthlyCost: (params?: { from_date?: string; to_date?: string }) => {
    const queryParams = new URLSearchParams();
    if (params?.from_date) queryParams.set('from_date', params.from_date);
    if (params?.to_date) queryParams.set('to_date', params.to_date);
    const query = queryParams.toString();
    return request<any>(`/v1/hr/payroll/monthly-cost${query ? `?${query}` : ''}`);
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
    request<any>(`/v1/hr/productivity/report?${new URLSearchParams(params)}`),
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

export interface CpoDecideRequest {
  chosen_alt_idx?: number | null;
  rejected_alt_idxs?: number[];
  reason?: string | null;
  decided_by?: string;
}

export interface CpoDecideResponse {
  commit_sha256: string;
  rejected_alternatives: Array<Record<string, any>>;
  user_preference_signal: Record<string, any>;
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
