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

export const planeamentoApi = {
  /** Corre o CPO v4 e persiste como Schedule-as-Code commit. */
  runSchedule: (data?: { horizon_days?: number; message?: string }) =>
    apiFetch<CpoScheduleResult>('/v1/plan/cpo/schedule', {
      method: 'POST',
      body: JSON.stringify({
        horizon_days: data?.horizon_days ?? 7,
        message: data?.message ?? 'Replaneamento via página Planeamento',
      }),
    }),

  /** Alinhamento receita ↔ ordem de prioridade do scheduler. */
  priorityReport: (commitSha?: string) =>
    apiFetch<PriorityReport>(
      `/v1/plan/priority-report${commitSha ? `?commit_sha=${encodeURIComponent(commitSha)}` : ''}`,
    ),
};
