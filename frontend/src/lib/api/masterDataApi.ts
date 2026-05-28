/**
 * ProdPlan ONE — API: master data (produtos, máquinas, operações, BOM, clientes, fornecedores).
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 */
import { request, filterParams } from './client';

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

// ─── Q.115.X5 — cancel / retire / deactivate ─────────────────────────────────

export interface CancelActionResponse {
  audit_trace_id: string;
  status: 'cancelled' | 'retired' | 'deactivated';
  decision_id?: string;
}

export interface WorkOrderItem {
  of_id: string;
  modelo: string;
  cliente: string;
  fase_actual: string;
  status: string;
}

export interface EncomendasItem {
  encomenda_id: string;
  cliente: string;
  data: string;
  total_eur: number;
}

export interface BoatItem {
  boat_id: string;
  modelo_nome: string;
  retired_at: string | null;
}

export interface EmployeeItem {
  employee_id: string;
  nome: string;
  role: string;
  active: boolean;
}

export interface DeactivateResponse extends CancelActionResponse {
  warning_ops_planeadas?: number;
}

export const cancelActionsApi = {
  // Ordens de fabrico activas (top-20)
  listWorkOrders: () =>
    request<WorkOrderItem[]>('/v1/work-orders?status=active&limit=20'),

  cancelWorkOrder: (ofId: string, reason: string) =>
    request<CancelActionResponse>(`/v1/work-orders/${ofId}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  // Encomendas activas (top-20)
  listEncomendas: () =>
    request<EncomendasItem[]>('/v1/encomendas?status=active&limit=20'),

  cancelEncomenda: (id: string, reason: string) =>
    request<CancelActionResponse>(`/v1/encomendas/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  // Barcos/modelos
  listBoats: (showRetired: boolean) =>
    request<BoatItem[]>(`/v1/master-data/boats?show_retired=${showRetired}&limit=20`),

  retireBoat: (boatId: string, reason: string) =>
    request<CancelActionResponse>(`/v1/master-data/boats/${boatId}/retire`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  // Operadores
  listEmployees: (showInactive: boolean) =>
    request<EmployeeItem[]>(`/v1/master-data/employees?show_inactive=${showInactive}&limit=20`),

  deactivateEmployee: (employeeId: string, reason: string) =>
    request<DeactivateResponse>(`/v1/master-data/employees/${employeeId}/deactivate`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
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

