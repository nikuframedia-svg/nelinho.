/**
 * planeamentoApi — wrappers tipados extra para Planeamento (Q.52.G).
 *
 * `lib/api.ts` já cobre cpoCommitsApi (timeline/alternatives),
 * schedulePreviewApi (preview-delta/apply-move) e employeesApi. O que
 * falta — `POST /v1/plan/cpo/schedule` (replanear) e
 * `GET /v1/plan/priority-report` — vive aqui, via `apiFetch` (herda
 * circuit-breaker/retry/headers). `lib/api.ts` é partilhado: proibido
 * editar na Onda 1.
 *
 * A operação do CPO (1:1 com `_scheduled_to_dict` do decoder) é o que
 * alimenta a timeline arrastável de barcos.
 */

import { apiFetch } from '../../lib/api';

/** Operação agendada — shape exacto de src/plan/cpo/decoder.py. */
export interface CpoOperation {
  operation_id: string;
  order_id: string;
  phase_id: string | null;
  machine_id: string | null;
  workers: string[];
  mold_id: string | null;
  mold_batch_id: string | null;
  start_time: string; // ISO
  end_time: string; // ISO
  duration_minutes: number;
  setup_family: string | null;
}

export interface CpoScheduleResult {
  tenant_id: string;
  engine_used: string;
  status: string;
  solve_time_sec: number;
  makespan_hours: number;
  num_late_orders: number;
  setups: number;
  degraded: boolean;
  fallback_reason: string | null;
  operations: CpoOperation[];
  warnings: string[];
  // Q.131.H — ordens deixadas FORA do plano por não terem rota (sem histórico
  // nem template do ERP), e a fração de ordens planeadas. O frontend mostra um
  // aviso honesto em vez de as omitir silenciosamente.
  unplanned_orders: string[];
  orders_coverage: number;
  commit_sha256: string | null;
}

export interface PriorityReportItem {
  order_id: string;
  first_op_index: number;
  revenue_eur: number;
}

export interface PriorityReport {
  commit_sha256: string;
  items: PriorityReportItem[];
  alignment_pct: number;
  inversions: number;
  max_inversions: number;
}

// ─── Q.53.B — calendário da fábrica ──────────────────────────────────────
/** Um dia do calendário de trabalho — shape de `CalendarDayOut`. */
export interface CalendarDay {
  day: string; // ISO date
  is_working_day: boolean;
  shift_hours: number;
  label: string | null;
}

export interface CalendarResponse {
  items: CalendarDay[];
  working_days: number;
  non_working_days: number;
}

// ─── Q.53.B — datas por barco (start-by / suggest-shipment) ──────────────
/** Um passo do breakdown de lead time — `LeadTimeBreakdown.steps`. */
export interface LeadTimeStep {
  seq: number;
  phase_id: string | null;
  phase_name: string | null;
  work_hours: number;
  curing_gap_hours: number;
}

export interface LeadTimeBreakdown {
  total_hours: number;
  work_hours: number;
  curing_gap_hours: number;
  n_phases: number;
  steps: LeadTimeStep[];
}

/** Resposta de `GET /v1/plan/orders/{id}/start-by`. */
export interface StartByResult {
  order_id: string;
  hull: string | null;
  product_name?: string | null;
  product_type?: string | null;
  target_date: string | null;
  target_field: string | null;
  start_by: string | null;
  lead_time: LeadTimeBreakdown | null;
  feasible: boolean | null;
  reason: string;
}

/** Resposta de `GET /v1/plan/orders/{id}/suggest-shipment`. */
export interface SuggestShipmentResult {
  order_id: string;
  hull: string | null;
  product_name?: string | null;
  product_type?: string | null;
  start: string;
  suggested_shipment: string | null;
  lead_time: LeadTimeBreakdown | null;
  transport_date: string | null;
  meets_transport_date?: boolean | null;
  reason: string;
}

// ─── Q.53.B — aderência ao plano ─────────────────────────────────────────
/** Uma fase no relatório de aderência — `PlanAdherenceService` phase row. */
export interface AdherencePhase {
  phase_id: string;
  planned_ops: number;
  realised_ops: number;
  adherence_pct: number | null;
  defect_count: number;
  defect_rate_pct: number | null;
}

export interface AdherenceReport {
  has_committed_plan: boolean;
  commit_sha: string | null;
  commit_created_at: string | null;
  summary: {
    total_planned_ops: number;
    total_realised_ops: number;
    adherence_pct: number | null;
    n_phases: number;
  };
  phases: AdherencePhase[];
}

// Q.62.D.2/D.3 — async polling contract.
export interface CpoScheduleEnqueueResponse {
  job_id: string;
  status_url: string;
  enqueued_at: string;
}

export type CpoJobState =
  | 'deferred'
  | 'in_progress'
  | 'complete'
  | 'failed'
  | 'not_found';

export interface CpoJobStatusResponse {
  job_id: string;
  state: CpoJobState;
  result: CpoScheduleResult | null;
  error: string | null;
  enqueued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface CpoJobApproveResponse {
  job_id: string;
  commit_sha256: string;
  previous_status: string;
  new_status: string;
  approved_at: string;
}

export const planeamentoApi = {
  /** Q.62.D.2 — corre o CPO v4 syncronamente (legacy, ainda bloqueia ate 30s).
   *  Mantido para tests + cases sem worker Arq. Frontend novo usa
   *  `runScheduleAsync` + `pollScheduleJob`.
   */
  runSchedule: (data?: { horizon_days?: number; message?: string }) =>
    apiFetch<CpoScheduleResult>('/v1/plan/cpo/schedule', {
      method: 'POST',
      body: JSON.stringify({
        horizon_days: data?.horizon_days ?? 7,
        message: data?.message ?? 'Replaneamento via página Planeamento',
      }),
    }),

  /** Q.62.D.2 — enfileira o CPO scheduler num Arq worker. Retorna 202
   *  + `job_id` imediato; cliente faz polling via `pollScheduleJob`. */
  runScheduleAsync: (data?: { horizon_days?: number; message?: string }) =>
    apiFetch<CpoScheduleEnqueueResponse>('/v1/plan/cpo/schedule/async', {
      method: 'POST',
      body: JSON.stringify({
        horizon_days: data?.horizon_days ?? 7,
        message: data?.message ?? 'Replaneamento (async)',
      }),
    }),

  /** Q.62.D.2 — polling do estado do Arq job. */
  pollScheduleJob: (jobId: string) =>
    apiFetch<CpoJobStatusResponse>(
      `/v1/plan/cpo/schedule/job/${encodeURIComponent(jobId)}`,
    ),

  /** Q.62.D.4 — promove o commit do job (DRAFT → LIVE). */
  approveScheduleJob: (jobId: string) =>
    apiFetch<CpoJobApproveResponse>(
      `/v1/plan/cpo/schedule/job/${encodeURIComponent(jobId)}/approve`,
      { method: 'PUT' },
    ),

  /** Alinhamento receita ↔ ordem de prioridade do scheduler. */
  priorityReport: (commitSha?: string) =>
    apiFetch<PriorityReport>(
      `/v1/plan/priority-report${commitSha ? `?commit_sha=${encodeURIComponent(commitSha)}` : ''}`,
    ),

  /** Calendário de trabalho da fábrica (dias úteis / fins-de-semana / feriados). */
  calendar: (params?: { from_date?: string; to_date?: string }) => {
    const qs = new URLSearchParams();
    if (params?.from_date) qs.set('from_date', params.from_date);
    if (params?.to_date) qs.set('to_date', params.to_date);
    const q = qs.toString();
    return apiFetch<CalendarResponse>(`/v1/plan/calendar${q ? `?${q}` : ''}`);
  },

  /** Data-limite de início para uma ordem chegar à data de transporte. */
  startBy: (orderId: string) =>
    apiFetch<StartByResult>(
      `/v1/plan/orders/${encodeURIComponent(orderId)}/start-by`,
    ),

  /** Data de expedição realista se a ordem começar hoje (ou em `start`). */
  suggestShipment: (orderId: string, start?: string) => {
    const q = start ? `?start=${encodeURIComponent(start)}` : '';
    return apiFetch<SuggestShipmentResult>(
      `/v1/plan/orders/${encodeURIComponent(orderId)}/suggest-shipment${q}`,
    );
  },

  /** Plano vs realizado por fase — aderência ao plano do CPO. */
  adherence: () => apiFetch<AdherenceReport>('/v1/plan/adherence'),
};
