/**
 * ProdPlan ONE — API: alocações, payroll, produtividade.
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 */
import { request, filterParams } from './client';
import type {
  AllocationCreateResponse,
  AllocationCreatedItem,
  LabourCostSummaryResponse,
  OrderAllocationsResponse,
  PayrollCalculateResponse,
} from '../../types/operacoes';

interface AllocationCreateRequest {
  requirements: Array<Record<string, unknown>>;
  employees: Array<Record<string, unknown>>;
  strategy?: 'skill_first' | 'cost_first' | 'balanced';
}

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

  // Q.31.D.2 — atribuição drag-drop de um operador a um barco para um dia.
  createDaily: (payload: {
    employee_id: string;
    order_id: string;
    allocation_date?: string;
    allocated_hours?: number;
  }) =>
    request<DailyAllocationResponse>('/v1/hr/allocations/daily', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

export interface DailyAllocationResponse {
  allocation_id: string;
  employee_id: string;
  order_id: string;
  operation_id: string;
  allocation_date: string;
  allocated_hours: number;
  status: string;
}

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

// ═══════════════════════════════════════════════════════════════════════════════
// SKILL MATRIX API — Q.18.ZIP.A.Onda7 (G. Workforce)
// ═══════════════════════════════════════════════════════════════════════════════
//
// Q.67.2.C — migração de fetch() directos em SkillMatrixDrawer.tsx para o
// fetch layer central (`request` injecta tenant/user/trace_id).

// Renamed to avoid clash with qualityApi.SkillMatrixRow re-exported via index.ts.
export interface WorkforceSkillMatrixRow {
  phase_id: string;
  phase_name?: string;
  can_do: boolean;
  nivel?: number | null;
  ops_count: number;
  last_used_at?: string | null;
}

export interface SkillMatrixResponse {
  phases?: WorkforceSkillMatrixRow[];
  total?: number;
}

export interface WorkforceEmployeeRow {
  employee_id?: string;
  id?: string;
  name?: string;
  job_title?: string;
}

export interface WorkforceEmployeesResponse {
  items?: WorkforceEmployeeRow[];
}

export const skillMatrixApi = {
  getEmployeeMatrix: (employeeId: string) =>
    request<SkillMatrixResponse>(
      `/v1/workforce/employees/${employeeId}/skill-matrix`,
    ),

  listEmployees: (limit = 200) =>
    request<WorkforceEmployeesResponse>(
      `/v1/workforce/employees?limit=${limit}`,
    ),
};

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
    
    // Q.61.32b — migrado de /api/allocations para /v1/workforce/allocations.
    return request<AllocationsResponse>(`/v1/workforce/allocations?${queryParams.toString()}`);
  },

  /**
   * Get aggregate statistics for all allocations (uses full database).
   * This is NOT paginated - returns totals from all 346,832 allocations.
   */
  stats: (): Promise<AllocationsStats> =>
    // Q.61.32b — migrado de /api/allocations/stats para /v1/workforce/allocations/stats.
    request<AllocationsStats>('/v1/workforce/allocations/stats'),
};

