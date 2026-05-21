/**
 * Q.61.27 — Query-key factories (TkDodo pattern).
 *
 * Antes do Q.61.27, os hooks TanStack Query usavam keys literais:
 *
 *   useQuery({ queryKey: ['decisions', 'list', filters], ... })
 *   queryClient.invalidateQueries({ queryKey: ['decisions'] })
 *
 * Inconvenientes:
 *   * keys typoadas viviam silenciosas (`['descisions']` nunca bate)
 *   * invalidacao em cascata exigia conhecer os literais de cada nivel
 *   * sem type-safety nas keys
 *
 * Q.61.27 instala factories por feature (TkDodo):
 *
 *   decisionKeys.all          -> ['decisions']
 *   decisionKeys.lists()      -> ['decisions', 'list']
 *   decisionKeys.list(filt)   -> ['decisions', 'list', filt]
 *   decisionKeys.detail(id)   -> ['decisions', 'detail', id]
 *
 * Hierarquia permite invalidacoes precisas:
 *   queryClient.invalidateQueries({ queryKey: decisionKeys.lists() })
 *   // invalida todas as lists, mantem detail no cache
 *
 * Estrategia:
 *   * Esta versao adiciona factories para 3 features que ja tem
 *     endpoint canonico no backend (decisions, causal/explain,
 *     audit-logs).
 *   * Touched-file pays: os 591 hooks existentes ficam ate alguem
 *     mexer no seu ficheiro. Codemod ts-morph e Q.61.27.1 follow-up.
 */

import type { UUID } from 'crypto';

// ─── decisions ──────────────────────────────────────────────────────────

export interface DecisionFilters {
  status?: string;
  page?: number;
  pageSize?: number;
}

export const decisionKeys = {
  all: ['decisions'] as const,
  lists: () => [...decisionKeys.all, 'list'] as const,
  list: (filters?: DecisionFilters) =>
    [...decisionKeys.lists(), filters ?? {}] as const,
  details: () => [...decisionKeys.all, 'detail'] as const,
  detail: (id: string | UUID) => [...decisionKeys.details(), id] as const,
  pending: () => [...decisionKeys.all, 'pending'] as const,
} as const;

// ─── audit-logs (Q.61.19) ───────────────────────────────────────────────

export interface AuditLogFilters {
  entityType?: string;
  entityId?: string;
  actorId?: string;
  action?: 'INSERT' | 'UPDATE' | 'DELETE';
  since?: string;
  until?: string;
  traceId?: string;
  page?: number;
  pageSize?: number;
}

export const auditLogKeys = {
  all: ['audit-logs'] as const,
  lists: () => [...auditLogKeys.all, 'list'] as const,
  list: (filters?: AuditLogFilters) =>
    [...auditLogKeys.lists(), filters ?? {}] as const,
} as const;

// ─── causal/explain (Q.61.25) ──────────────────────────────────────────

export const causalKeys = {
  all: ['causal'] as const,
  attribution: (target: string, sampleSize: number) =>
    [...causalKeys.all, 'attribution', target, sampleSize] as const,
  neloDag: (tauMax: number, alpha: number, sampleSize: number) =>
    [...causalKeys.all, 'nelo-dag', tauMax, alpha, sampleSize] as const,
  kpiSnapshot: () => [...causalKeys.all, 'kpis-snapshot-explained'] as const,
} as const;

// ─── governance rules (Q.17 YAML policy) ───────────────────────────────

export const ruleKeys = {
  all: ['yaml-policy-rules'] as const,
  lists: () => [...ruleKeys.all, 'list'] as const,
  list: (status?: string) => [...ruleKeys.lists(), status ?? 'any'] as const,
  details: () => [...ruleKeys.all, 'detail'] as const,
  detail: (id: string) => [...ruleKeys.details(), id] as const,
  firings: () => [...ruleKeys.all, 'firings'] as const,
} as const;

// ─── data product / semantic views (Q.67.2.C) ──────────────────────────

export const dataProductKeys = {
  all: ['dataProduct'] as const,
  semanticViews: () => [...dataProductKeys.all, 'semantic-views'] as const,
  semanticQuery: (viewId: string | null) =>
    [...dataProductKeys.all, 'semantic-query', viewId] as const,
} as const;

// ─── workforce / skill matrix (Q.67.2.C) ───────────────────────────────

export const workforceKeys = {
  all: ['workforce'] as const,
  employees: (limit?: number) =>
    [...workforceKeys.all, 'employees', limit ?? null] as const,
  skillMatrix: (employeeId: string | null) =>
    [...workforceKeys.all, 'skill-matrix', employeeId] as const,
} as const;

// ─── profit (Q.67.2.A) ──────────────────────────────────────────────────
//
// Cobre os panels de ProfitPanels.tsx (Onda 10/J): dashboard € hoje,
// COGS breakdown por order, margem dado preço de venda.

export const profitKeys = {
  all: ['profit'] as const,
  dashboard: () => [...profitKeys.all, 'dashboard'] as const,
  cogsOrder: (orderId: string) => [...profitKeys.all, 'cogs-order', orderId] as const,
  margin: (orderId: string, sellingPrice: number) =>
    [...profitKeys.all, 'margin', orderId, sellingPrice] as const,
} as const;

// ─── twin (Q.67.2.A) ────────────────────────────────────────────────────
//
// Digital Twin sandbox (Onda 17/Q): scenarios CRUD + compare.

export const twinKeys = {
  all: ['twin'] as const,
  scenarios: () => [...twinKeys.all, 'scenarios'] as const,
  compare: (scenarioId: string | null) =>
    [...twinKeys.all, 'compare', scenarioId ?? 'none'] as const,
} as const;

// ─── ops (Q.67.2.A) ─────────────────────────────────────────────────────
//
// Painéis admin/ops: health, rate-limit (copilot/diagnose), auth/me.

export const opsKeys = {
  all: ['ops'] as const,
  healthReady: () => [...opsKeys.all, 'health-ready'] as const,
  healthLive: () => [...opsKeys.all, 'health-live'] as const,
  copilotDiagnose: () => [...opsKeys.all, 'copilot-diagnose'] as const,
  authMe: () => [...opsKeys.all, 'auth-me'] as const,
} as const;

// ─── ML registry (Q.67.2.B) ────────────────────────────────────────────
//
// Suporta MlRegistryPanel (Onda 16/P): lista de modelos, versões e
// versão activa por modelo.

export const mlKeys = {
  all: ['ml'] as const,
  models: () => [...mlKeys.all, 'models'] as const,
  versions: (modelName: string | null | undefined) =>
    [...mlKeys.all, 'versions', modelName ?? ''] as const,
  active: (modelName: string | null | undefined) =>
    [...mlKeys.all, 'active', modelName ?? ''] as const,
} as const;

// ─── Supply panels (Q.67.2.B) ──────────────────────────────────────────
//
// SupplyPanels (Onda 9/I): ROP calc + shortage alerts (copilot/alerts
// filtered por source=shortage_detector). Forecast e ABC são mutations.

export interface SupplyRopFilters {
  skuId: string;
  avgDailyDemand: number;
  leadTimeDays: number;
  leadTimeStdDev: number;
  serviceLevel: number;
}

export const supplyKeys = {
  all: ['supply'] as const,
  rop: (filters: SupplyRopFilters) =>
    [
      ...supplyKeys.all,
      'rop',
      filters.skuId,
      filters.avgDailyDemand,
      filters.leadTimeDays,
      filters.leadTimeStdDev,
      filters.serviceLevel,
    ] as const,
  shortageAlerts: () =>
    [...supplyKeys.all, 'copilot-alerts', 'shortage'] as const,
} as const;

// ─── Reports admin (Q.67.2.B) ──────────────────────────────────────────
//
// ReportsAdminPanel (Onda 18/R): 3 mutations (schedule, email, retention).
// As lists ainda não existem como GET — keys preparam o terreno.

export const reportsKeys = {
  all: ['reports'] as const,
  schedules: () => [...reportsKeys.all, 'schedules'] as const,
  emails: () => [...reportsKeys.all, 'emails'] as const,
  retentions: () => [...reportsKeys.all, 'retentions'] as const,
} as const;
