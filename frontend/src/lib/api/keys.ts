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
