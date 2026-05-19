/**
 * qualidadeApi — tipos e fetchers das tabs Predições / Mapa do casco /
 * Aderência / ROI da página Qualidade (Q.53.H).
 *
 * Liga aos endpoints REAIS servidos por Q.53.A / Q.44.B:
 *   GET /v1/quality/defect-risk   → DefectRiskService  (ML QualityRiskModel)
 *   GET /v1/quality/defect-zones  → DefectZoneService  (agregação por zona)
 *   GET /v1/quality/roi-actions   → ROIService         (€ poupado vs investido)
 *   GET /v1/plan/adherence        → plan_adherence     (plano vs realizado)
 *
 * Tipos copiados fielmente do shape dos dicts devolvidos pelos serviços
 * Pydantic/SQLAlchemy do backend. ZERO MOCKS — todos os fetchers passam
 * pelo `apiFetch` (circuit breaker + tenant header). Os endpoints podem
 * degradar com honestidade (`model_available=false`, `status=...`); os
 * tipos modelam essa degradação para a UI a mostrar um empty state real.
 */

import { apiFetch } from '../../lib/api';

// ─── /v1/quality/defect-risk ─────────────────────────────────────────────

export type RiskBand = 'alto' | 'medio' | 'baixo';

export interface DefectRiskOrder {
  of_id: string;
  product_name: string | null;
  product_type: string | null;
  current_phase_id: string | null;
  current_phase_name: string | null;
  defect_probability: number;
  risk_band: RiskBand;
  features: Record<string, unknown>;
}

export interface DefectRiskResponse {
  model_available: boolean;
  /** Razão legível quando `model_available` é false. */
  reason?: string;
  total_orders?: number;
  high_risk_count?: number;
  orders: DefectRiskOrder[];
}

export function fetchDefectRisk(topN = 50): Promise<DefectRiskResponse> {
  return apiFetch<DefectRiskResponse>(
    `/v1/quality/defect-risk?top_n=${topN}`,
  );
}

// ─── /v1/quality/defect-zones ────────────────────────────────────────────

/** Zonas canónicas do casco — espelha HULL_ZONES no backend. */
export const HULL_ZONE_IDS = [
  'casco',
  'conves',
  'cockpit',
  'interior',
  'acabamento',
  'molde',
  'montagem',
  'outro',
] as const;
export type HullZoneId = (typeof HULL_ZONE_IDS)[number];

export interface DefectZone {
  zone: HullZoneId;
  events: number;
  cost_eur: number;
  hours_lost: number;
  share_pct: number;
}

export interface DefectZonesResponse {
  window: { from: string; to: string };
  total_events: number;
  zones: DefectZone[];
}

export function fetchDefectZones(): Promise<DefectZonesResponse> {
  return apiFetch<DefectZonesResponse>('/v1/quality/defect-zones');
}

// ─── /v1/quality/roi-actions ─────────────────────────────────────────────

export interface RoiAction {
  error_code: string;
  events: number;
  saved_eur: number;
  invested_eur: number;
  net_eur: number;
  roi_ratio: number | null;
  action_basis: 'fixed_corrective_action' | 'reaction_effort';
  preventive_action_hint: string | null;
}

export interface RoiActionsResponse {
  window: { from: string; to: string };
  labour_rate_eur_per_hour: number;
  total_saved_eur: number;
  total_invested_eur: number;
  actions: RoiAction[];
}

export function fetchRoiActions(topN = 25): Promise<RoiActionsResponse> {
  return apiFetch<RoiActionsResponse>(
    `/v1/quality/roi-actions?top_n=${topN}`,
  );
}

// ─── /v1/plan/adherence ──────────────────────────────────────────────────

export interface PhaseDeviation {
  phase_id: string;
  planned_count: number;
  matched_count: number;
  avg_start_drift_hours: number | null;
  avg_end_drift_hours: number | null;
}

/**
 * O endpoint degrada com honestidade via `status`:
 *  - `status="sem_plano_temporal"` — commit sem operações com horas
 *  - `status="sem_execucao_real"`  — ERP MAR-KAYAKS desligado
 *  - `status="ok"`                 → comparação completa (AdherenceResult)
 */
export interface AdherenceResponse {
  commit_sha256: string;
  short_sha: string;
  planned_total: number;
  status: 'ok' | 'sem_plano_temporal' | 'sem_execucao_real';
  detail?: string;
  window?: { from: string; to: string };
  // Campos presentes só na comparação completa (`status==="ok"`).
  realized_total?: number;
  matched_total?: number;
  within_tolerance_total?: number;
  adherence_pct?: number;
  /** % de operações planeadas com alguma execução real (cobertura). */
  match_pct?: number;
  tolerance_hours?: number;
  missing?: Array<{ order_id: string; phase_id: string }>;
  unplanned?: Array<{ order_id: string; phase_id: string }>;
  phase_deviations?: PhaseDeviation[];
}

/**
 * Devolve a resposta de aderência. O endpoint dá 404 quando não há nenhum
 * `ScheduleCommit`; nesse caso devolvemos `null` para a UI mostrar o empty
 * state de "ainda não há plano", em vez de propagar o erro.
 */
export async function fetchAdherence(): Promise<AdherenceResponse | null> {
  try {
    return await apiFetch<AdherenceResponse>('/v1/plan/adherence');
  } catch (err) {
    // 404 = sem commit de plano. Outros erros são re-lançados para o
    // React Query os mostrar como erro genuíno.
    const msg = err instanceof Error ? err.message : '';
    if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
      return null;
    }
    throw err;
  }
}
