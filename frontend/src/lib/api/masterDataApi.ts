/**
 * ProdPlan ONE — API: master data (produtos, máquinas, operações, BOM, clientes, fornecedores).
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 *
 * Q.68.4.D — `: any` substituído por `unknown` (response) ou `Record<string, unknown>`
 * (payload). Shapes Pydantic concretas ficam em DTOs por endpoint quando necessárias.
 */
import { request, filterParams } from './client';

// Payload genérico para POST/PATCH/PUT — backend valida via Pydantic, o frontend só envia JSON.
type Payload = Record<string, unknown>;
// Resposta genérica — pages downstream ainda dependem de acesso dinâmico (.filter, .length).
// `any` aqui é dívida explícita; trocar por DTOs Pydantic é Q.68.4.E (ficheiro-a-ficheiro).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ApiResponse = any;

// ═══════════════════════════════════════════════════════════════════════════════
// CORE MODULE - Master Data
// ═══════════════════════════════════════════════════════════════════════════════

// Products
export const productsApi = {
  list: (params?: { limit?: number; offset?: number; status?: string }) =>
    request<ApiResponse>(`/v1/core/products?${new URLSearchParams(filterParams(params))}`),

  get: (id: string) =>
    request<ApiResponse>(`/v1/core/products/${id}`),

  create: (data: Payload) =>
    request<ApiResponse>('/v1/core/products', { method: 'POST', body: JSON.stringify(data) }),

  update: (id: string, data: Payload) =>
    request<ApiResponse>(`/v1/core/products/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  delete: (id: string) =>
    request<void>(`/v1/core/products/${id}`, { method: 'DELETE' }),
};

// Machines
export const machinesApi = {
  list: (params?: { limit?: number; offset?: number; status?: string }) =>
    request<ApiResponse>(`/v1/core/machines?${new URLSearchParams(filterParams(params))}`),

  get: (id: string) =>
    request<ApiResponse>(`/v1/core/machines/${id}`),

  create: (data: Payload) =>
    request<ApiResponse>('/v1/core/machines', { method: 'POST', body: JSON.stringify(data) }),

  update: (id: string, data: Payload) =>
    request<ApiResponse>(`/v1/core/machines/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  delete: (id: string) =>
    request<void>(`/v1/core/machines/${id}`, { method: 'DELETE' }),
};

// Employees
export const employeesApi = {
  list: (params?: { limit?: number; offset?: number; status?: string; department?: string }) =>
    request<ApiResponse>(`/v1/core/employees?${new URLSearchParams(filterParams(params))}`),

  get: (id: string) =>
    request<ApiResponse>(`/v1/core/employees/${id}`),

  create: (data: Payload) =>
    request<ApiResponse>('/v1/core/employees', { method: 'POST', body: JSON.stringify(data) }),

  update: (id: string, data: Payload) =>
    request<ApiResponse>(`/v1/core/employees/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  delete: (id: string) =>
    request<void>(`/v1/core/employees/${id}`, { method: 'DELETE' }),
};

// Operations
export const operationsApi = {
  list: (params?: { limit?: number; offset?: number }) =>
    request<ApiResponse>(`/v1/core/operations?${new URLSearchParams(filterParams(params))}`),

  get: (id: string) =>
    request<ApiResponse>(`/v1/core/operations/${id}`),

  create: (data: Payload) =>
    request<ApiResponse>('/v1/core/operations', { method: 'POST', body: JSON.stringify(data) }),

  update: (id: string, data: Payload) =>
    request<ApiResponse>(`/v1/core/operations/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  delete: (id: string) =>
    request<void>(`/v1/core/operations/${id}`, { method: 'DELETE' }),
};

// BOM
export const bomApi = {
  getByProduct: (productId: string) =>
    request<ApiResponse>(`/v1/core/bom/products/${productId}`),

  get: (bomId: string) =>
    request<ApiResponse>(`/v1/core/bom/${bomId}`),

  create: (data: Payload) =>
    request<ApiResponse>('/v1/core/bom', { method: 'POST', body: JSON.stringify(data) }),

  update: (bomId: string, data: Payload) =>
    request<ApiResponse>(`/v1/core/bom/${bomId}`, { method: 'PUT', body: JSON.stringify(data) }),

  delete: (bomId: string) =>
    request<void>(`/v1/core/bom/${bomId}`, { method: 'DELETE' }),
};

// Customers
export const customersApi = {
  list: (params?: { segment?: string; is_active?: boolean; price_tier?: string; limit?: number; offset?: number }) =>
    request<ApiResponse>(`/v1/core/customers?${new URLSearchParams(filterParams(params))}`),

  get: (id: string) =>
    request<ApiResponse>(`/v1/core/customers/${id}`),

  create: (data: Payload) =>
    request<ApiResponse>('/v1/core/customers', { method: 'POST', body: JSON.stringify(data) }),

  update: (id: string, data: Payload) =>
    request<ApiResponse>(`/v1/core/customers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  delete: (id: string) =>
    request<void>(`/v1/core/customers/${id}`, { method: 'DELETE' }),
};

// Suppliers
export const suppliersApi = {
  list: (params?: { material_category?: string; is_active?: boolean; is_preferred?: boolean; limit?: number; offset?: number }) =>
    request<ApiResponse>(`/v1/core/suppliers?${new URLSearchParams(filterParams(params))}`),

  get: (id: string) =>
    request<ApiResponse>(`/v1/core/suppliers/${id}`),

  create: (data: Payload) =>
    request<ApiResponse>('/v1/core/suppliers', { method: 'POST', body: JSON.stringify(data) }),

  update: (id: string, data: Payload) =>
    request<ApiResponse>(`/v1/core/suppliers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  delete: (id: string) =>
    request<void>(`/v1/core/suppliers/${id}`, { method: 'DELETE' }),
};

// Rates
export const ratesApi = {
  // Labor rates
  laborRates: {
    list: () => request<ApiResponse>('/v1/core/rates/labor'),
    create: (data: Payload) => request<ApiResponse>('/v1/core/rates/labor', { method: 'POST', body: JSON.stringify(data) }),
  },

  // Machine rates
  machineRates: {
    list: () => request<ApiResponse>('/v1/core/rates/machine'),
    create: (data: Payload) => request<ApiResponse>('/v1/core/rates/machine', { method: 'POST', body: JSON.stringify(data) }),
  },

  // Overhead rates
  overheadRates: {
    list: () => request<ApiResponse>('/v1/core/rates/overhead'),
    create: (data: Payload) => request<ApiResponse>('/v1/core/rates/overhead', { method: 'POST', body: JSON.stringify(data) }),
  },
};

// Tenants
export const tenantsApi = {
  list: () => request<ApiResponse>('/v1/core/tenants'),
  get: (id: string) => request<ApiResponse>(`/v1/core/tenants/${id}`),
  create: (data: Payload) => request<ApiResponse>('/v1/core/tenants', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Payload) => request<ApiResponse>(`/v1/core/tenants/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  activate: (id: string) =>
    request<ApiResponse>(`/v1/core/tenants/${id}/activate`, { method: 'POST' }),
  suspend: (id: string) =>
    request<ApiResponse>(`/v1/core/tenants/${id}/suspend`, { method: 'POST' }),
  updateSubscription: (id: string, data: Payload | string) =>
    request<ApiResponse>(`/v1/core/tenants/${id}/subscription`, {
      method: 'PATCH',
      body: typeof data === 'string' ? JSON.stringify({ level: data }) : JSON.stringify(data),
    }),
};
