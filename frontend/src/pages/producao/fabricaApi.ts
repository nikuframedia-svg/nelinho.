/**
 * fabricaApi — wrappers tipados para os endpoints da Fábrica que ainda
 * não vivem em `lib/api.ts` (factory-map snapshot/line-load,
 * orders/active, curing-validation).
 *
 * Q.52.F · Onda 1 · T1. Usa o `apiFetch` exportado de `lib/api.ts` —
 * NÃO faz `fetch` cru. Os tipos derivam dos schemas do backend
 * (`orders.py`, `factory_map.py`). As famílias já tipadas (allocations,
 * schedule preview, workforce employees) continuam a vir de `lib/api.ts`.
 *
 * Quando estes endpoints ganharem wrapper canónico (Onda 2 / Q.53),
 * este ficheiro reexporta-os e é apagado.
 */

import { apiFetch } from '../../lib/api';

// ─── Ordens activas (cartões de barco) ─────────────────────────────────────

export interface ActiveOrderCard {
  id: string;
  hull: string | null;
  /** Nome do modelo do barco (ex: "Vanquish 3"). */
  product_name: string | null;
  /** Código de classe do barco (K1/K2/K4/C1…). */
  product_type: string | null;
  /** Nome do cliente — `null` enquanto a sincronização ERP não landa (Q.53.I). */
  customer_name: string | null;
  /** Nome da fase actual (current_phase_name). */
  phase: string | null;
  status: string;
  created_date: string | null;
  transport_date: string | null;
}

// ─── Métricas de qualificação do operador (Q.53.E / Q.53.I) ───────────────

/**
 * Os 3 sinais de qualificação que o fit-score combina com o
 * quality-score: recência, versatilidade e produtividade.
 */
export interface QualificationMetrics {
  employee_id: string;
  /** Dias desde a última operação — `null` = sem histórico. */
  recency_days: number | null;
  /** Nº de fases distintas em que o operador é apto / já trabalhou. */
  versatility: number;
  /** Operações por dia ao longo do histórico — `null` = não calculável. */
  productivity: number | null;
  ops_total: number;
  scope: string | null;
}

// ─── Snapshot / line-load (gargalo por fase) ───────────────────────────────

export interface FactoryBottleneck {
  operation_id?: string | null;
  phase?: string | null;
  name?: string | null;
  load?: number | null;
  capacity?: number | null;
  score?: number | null;
  [k: string]: unknown;
}

export interface FabricaSnapshot {
  timestamp: string;
  boats: { total: number; in_progress: number; completed: number };
  phases: { bottlenecks: FactoryBottleneck[] };
  molds: { total: number };
}

// ─── Validação de cura (PARTIAL) ───────────────────────────────────────────

export interface CuringValidationResponse {
  /** Marcador de honestidade quando não há sensores. */
  status?: string;
  erp_available?: boolean;
  items?: Array<{
    of_id?: string;
    phase_id?: string;
    ok?: boolean;
    message?: string;
    [k: string]: unknown;
  }>;
  [k: string]: unknown;
}

export const fabricaApi = {
  /** Ordens em curso para as colunas Kanban (REAL). */
  activeOrders: (params?: { phase?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.phase) qs.set('phase', params.phase);
    qs.set('limit', String(params?.limit ?? 500));
    return apiFetch<ActiveOrderCard[]>(
      `/v1/plan/orders/active?${qs.toString()}`,
    );
  },

  /** Snapshot da fábrica — score de gargalo por fase (REAL). */
  snapshot: () => apiFetch<FabricaSnapshot>('/v1/factory-map/snapshot'),

  /** Validação de cura — coluna Cura (PARTIAL: degrada com honestidade). */
  curingValidation: () =>
    apiFetch<CuringValidationResponse>('/v1/plan/curing-validation'),

  /**
   * Métricas de qualificação de um operador (Q.53.E) — recência,
   * versatilidade e produtividade. Alimentam o fit-score da Fábrica.
   */
  qualificationMetrics: (employeeId: string) =>
    apiFetch<QualificationMetrics>(
      `/v1/workforce/employees/${encodeURIComponent(
        employeeId,
      )}/qualification-metrics`,
    ),
};
