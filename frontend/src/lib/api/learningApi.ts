/**
 * Q.115.V — API de aprendizagem: plan-vs-actual + afinidades.
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts.
 */
import { request } from './client';

// ─── Plan-vs-Actual (Q.115.V) ───────────────────────────────────────────────

export interface DeltaByPhase {
  phase_id: string;
  phase_name: string;
  avg_delta_duration_min: number;
  avg_delta_quality: number | null;
  sample_n: number;
}

export interface DeltaByModel {
  modelo_id: string;
  avg_delta_duration_min: number;
  avg_delta_quality: number | null;
  sample_n: number;
}

export interface PlanVsActualReport {
  tenant_id: string;
  days: number;
  /** 100 × (1 - mean(|delta_duration| / planned_duration)) */
  plan_accuracy_pct: number;
  deltas_by_phase: DeltaByPhase[];
  deltas_by_model: DeltaByModel[];
  sample_size: number;
  computed_at: string;
}

export const learningApi = {
  /**
   * GET /v1/learning/plan-vs-actual?days=N
   *
   * Devolve sample_size=0 + listas vazias quando não há dados
   * (dev sem SQLSERVER_ENABLED). NÃO renderiza ainda — Q.115.O liga mais tarde.
   */
  planVsActual: ({ days }: { days: number }) =>
    request<PlanVsActualReport>(
      `/v1/learning/plan-vs-actual?days=${encodeURIComponent(days)}`,
    ),
};
