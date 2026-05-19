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
import type {
  QualityScoreResult,
  SkillMatrixResult,
} from '../../lib/api';

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
  /** Sequência de routing NELO da fase actual — ordena as colunas Kanban. */
  phase_sequence: number | null;
  status: string;
  created_date: string | null;
  transport_date: string | null;
}

// ─── Plano optimizado do CPO (Q.54.D) ──────────────────────────────────────

/**
 * Ordem como aparece no commit optimizado do CPO. Estende o cartão cru
 * com a atribuição que o solver decidiu (`optimized_*`, `assigned_*`,
 * `scheduled_*`). `in_optimized_plan=false` → o solver não a colocou.
 */
export interface OptimizedOrderCard extends ActiveOrderCard {
  in_optimized_plan: boolean;
  optimized_phase: string | null;
  optimized_phase_sequence: number | null;
  assigned_employee_id: string | null;
  assigned_employee_name: string | null;
  assigned_machine_id: string | null;
  scheduled_start: string | null;
  scheduled_end: string | null;
}

/** KPIs do commit optimizado. */
export interface CommitKpis {
  setups?: number | null;
  status?: string | null;
  makespan_hours?: number | null;
  solve_time_sec?: number | null;
  avg_utilization?: number | null;
  num_late_orders?: number | null;
  throughput_eur_day?: number | null;
  safety_net_triggered?: boolean | null;
  throughput_eur_total?: number | null;
  total_tardiness_hours?: number | null;
  [k: string]: unknown;
}

export interface CommitOrdersResponse {
  commit_sha256: string;
  short_sha: string;
  kpis: CommitKpis;
  orders: OptimizedOrderCard[];
}

// ─── Perfis de operador em lote (Q.54.C) ───────────────────────────────────

/**
 * Perfil agregado de um operador devolvido pelo endpoint batch
 * `POST /v1/workforce/employees/profiles` — junta os 3 sinais numa só
 * chamada (substitui o fan-out de 3 pedidos × N operadores).
 */
export interface EmployeeProfile {
  employee_id: string;
  quality_score: QualityScoreResult | null;
  skill_matrix: SkillMatrixResult | null;
  qualification_metrics: QualificationMetrics | null;
}

export interface EmployeeProfilesResponse {
  profiles: EmployeeProfile[];
  requested: number;
  returned: number;
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

  /**
   * Plano optimizado do CPO — ordens com a atribuição do solver +
   * KPIs do commit (Q.54.D). `sha` aceita `latest`.
   */
  commitOrders: (sha: string = 'latest') =>
    apiFetch<CommitOrdersResponse>(
      `/v1/plan/cpo/commits/${encodeURIComponent(sha)}/orders`,
    ),

  /**
   * Perfis de operador em lote (Q.54.C) — quality-score + skill-matrix +
   * qualification-metrics agregados numa só chamada. Substitui o fan-out
   * de ~60 pedidos que congelava a página ao seleccionar um barco.
   */
  employeeProfiles: (employeeIds: string[]) =>
    apiFetch<EmployeeProfilesResponse>(
      '/v1/workforce/employees/profiles',
      {
        method: 'POST',
        body: JSON.stringify({ employee_ids: employeeIds }),
      },
    ),

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
