/**
 * ProdPlan ONE — API: erros, retrabalho, DQA, skill-matrix, moldes.
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 */
import { request, filterParams } from './client';

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
    
    // Q.61.32c — migrado de /api/errors para /v1/quality/errors.
    return request<ErrorsResponse>(`/v1/quality/errors?${queryParams.toString()}`);
  },

  /**
   * Get aggregate statistics for all errors (uses full database).
   * This is NOT paginated - returns totals from all 89,836 errors.
   */
  stats: (): Promise<ErrorsStats> =>
    // Q.61.32c — migrado de /api/errors/stats para /v1/quality/errors/stats.
    request<ErrorsStats>('/v1/quality/errors/stats'),
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
  /** Fase onde o defeito ocorreu (QA01) — Q.30.D. */
  phase_id_causer?: string;
  /** Fase de retrabalho (QA02 auto-routing p/ "Pintura") — Q.30.D. */
  phase_id_rework?: string;
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

  // Q.18 fix-workforce — escala 1-3 derivada do quality score Laplace.
  levelSummary: (employeeId: string) =>
    request<{
      employee_id: string;
      quality_score: number;
      derived_level: 1 | 2 | 3;
      level_label: string;
      level_description: string;
      recommended_boats: string[];
      skills_apt: string[];
      per_phase_skills: Array<{
        phase_id: string;
        phase_name?: string;
        can_do: boolean;
        nivel?: number | null;
        ops_count: number;
        last_used_at?: string | null;
      }>;
    }>(
      `/v1/workforce/employees/${encodeURIComponent(employeeId)}/level-summary`,
    ),
};

// ═══════════════════════════════════════════════════════════════════════════════
// Q.31.B + Q.52.C — Moldes (família completa /v1/plan/molds/*)
// ═══════════════════════════════════════════════════════════════════════════════
//
// O router de moldes (src/plan/api/mold.py) está montado sob o prefixo
// `/v1/plan` — daí os caminhos `/v1/plan/molds/...`. Os endpoints devolvem
// dicts nus (sem `response_model`); os tipos abaixo derivam de `_mold_to_dict`
// e `_event_to_dict` no backend. Não existe `sync-usage` no backend hoje —
// quando alguma página precisar, ver gap Q.53.

export interface MoldHealthSummary {
  /** 0-100. Maior é mais saudável. */
  score_0_100: number;
  /** Semáforo: vermelho exige atenção, amarelo monitorizar, verde ok. */
  risk_category: 'red' | 'yellow' | 'green' | string;
  assessed_at: string | null;
  components: Record<string, unknown>;
}

export interface Mold {
  id: string;
  mold_code: string;
  model_id: string;
  name: string | null;
  pocket_count: number;
  expected_life_cycles: number | null;
  active: boolean;
  depreciated: boolean;
  /** Presente em GET /{id} e em /health-report; ausente em GET /molds/. */
  health?: MoldHealthSummary;
}

export interface MoldMaintenanceEvent {
  id: string;
  mold_id: string;
  maintenance_type: string;
  planned_date: string | null;
  started_at: string | null;
  completed_at: string | null;
  status: string;
  actual_duration_h: number | null;
  parts_cost_eur: number | null;
  labor_cost_eur: number | null;
  comments: string | null;
}

/** Resposta de POST /molds/{id}/recompute-health. */
export interface MoldHealthRecompute {
  score_0_100: number;
  risk_category: 'red' | 'yellow' | 'green' | string;
  components: Record<string, unknown>;
}

/** Resposta de POST /molds/propose-preventive. */
export interface MoldPreventiveProposal {
  events_proposed: number;
  events: MoldMaintenanceEvent[];
}

export const moldsApi = {
  /** Lista de moldes. `activeOnly` filtra os depreciados (default true). */
  list: (params?: { activeOnly?: boolean }) =>
    request<Mold[]>(`/v1/plan/molds/?${new URLSearchParams(filterParams(params))}`),

  /** Detalhe de um molde + última avaliação de saúde. */
  get: (moldId: string) =>
    request<Mold>(`/v1/plan/molds/${encodeURIComponent(moldId)}`),

  /** Criar um molde novo. */
  create: (payload: {
    mold_code: string;
    model_id: string;
    pocket_count?: number;
    expected_life_cycles?: number;
    name?: string;
  }) =>
    request<Mold>('/v1/plan/molds/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Calendário de manutenções planeadas numa janela (default próximos 30 dias). */
  calendar: (params?: { since?: string; until?: string }) =>
    request<MoldMaintenanceEvent[]>(
      `/v1/plan/molds/calendar?${new URLSearchParams(filterParams(params))}`,
    ),

  /** Moldes ordenados por risco — vermelhos primeiro. */
  healthReport: (params?: { limit?: number }) =>
    request<Mold[]>(
      `/v1/plan/molds/health-report?${new URLSearchParams(filterParams(params))}`,
    ),

  /** Recalcular o score de saúde de um molde. */
  recomputeHealth: (moldId: string) =>
    request<MoldHealthRecompute>(
      `/v1/plan/molds/${encodeURIComponent(moldId)}/recompute-health`,
      { method: 'POST' },
    ),

  /** Propor manutenção preventiva para os moldes em risco. */
  proposePreventive: (params?: { horizonDays?: number }) =>
    request<MoldPreventiveProposal>(
      `/v1/plan/molds/propose-preventive?${new URLSearchParams(filterParams(params))}`,
      { method: 'POST' },
    ),

  /** Emitir alertas MOLD_MAINT_DUE para os moldes que precisam de manutenção. */
  scanAlerts: () =>
    request<{ alerts_created: number }>('/v1/plan/molds/scan-alerts', {
      method: 'POST',
    }),

  /** Eventos de manutenção de um molde. */
  listMaintenance: (moldId: string) =>
    request<MoldMaintenanceEvent[]>(
      `/v1/plan/molds/${encodeURIComponent(moldId)}/maintenance`,
    ),
  /** Planear uma manutenção. */
  planMaintenance: (
    moldId: string,
    payload: { planned_date: string; maintenance_type?: string; comments?: string },
  ) =>
    request<MoldMaintenanceEvent>(
      `/v1/plan/molds/${encodeURIComponent(moldId)}/maintenance`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  /** Marcar uma manutenção planeada como iniciada. */
  startMaintenance: (eventId: string) =>
    request<MoldMaintenanceEvent>(
      `/v1/plan/molds/maintenance/${encodeURIComponent(eventId)}/start`,
      { method: 'POST' },
    ),
  /** Concluir uma manutenção em curso. */
  completeMaintenance: (
    eventId: string,
    payload: {
      actual_duration_h?: number;
      parts_cost_eur?: number;
      labor_cost_eur?: number;
      defects_fixed?: string[];
    },
  ) =>
    request<MoldMaintenanceEvent>(
      `/v1/plan/molds/maintenance/${encodeURIComponent(eventId)}/complete`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
};

// ═══════════════════════════════════════════════════════════════════════════════
// QUALITY RISK PREVIEW (Q.115.E — defensivo, endpoint pode não existir)
// ═══════════════════════════════════════════════════════════════════════════════

export interface QualityRiskPreview {
  operator_id: string;
  boat_id: string;
  phase_id: string;
  p_defect: number;
}

export const qualityRiskApi = {
  /** GET /v1/quality/risk-preview — defensivo: retorna null se 404. */
  riskPreview: (params: {
    operator_id: string;
    boat_id: string;
    phase_id: string;
  }) => {
    const qs = new URLSearchParams({
      operator_id: params.operator_id,
      boat_id: params.boat_id,
      phase_id: params.phase_id,
    });
    return request<QualityRiskPreview>(`/v1/quality/risk-preview?${qs.toString()}`);
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// RUNBOOK API (Q.115.H)
// ═══════════════════════════════════════════════════════════════════════════════

export interface Runbook {
  id: string;
  error_code: string;
  steps_md: string;
  source: string;
  confidence: number;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string | null;
}

export const runbookApi = {
  /** GET /v1/quality/runbook?error_code=... — lista runbooks do tenant. */
  list: (params?: { error_code?: string }) => {
    const qs = new URLSearchParams();
    if (params?.error_code) qs.set('error_code', params.error_code);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<Runbook[]>(`/v1/quality/runbook${suffix}`);
  },

  /** POST /v1/quality/runbook/{id}/approve */
  approve: (runbookId: string, payload: { approved_by: string; notes?: string }) =>
    request<Runbook>(`/v1/quality/runbook/${encodeURIComponent(runbookId)}/approve`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

