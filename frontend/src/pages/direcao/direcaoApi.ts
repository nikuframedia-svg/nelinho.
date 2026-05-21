/**
 * direcaoApi — cliente das secções Q.53.C da página Direção.
 *
 * Liga aos endpoints reais do módulo profit:
 *   - GET /v1/profit/kpis/objectives        (bandas-alvo do CEO + pp1_impact)
 *   - GET /v1/profit/margin-by-segment      (margem por país / agente)
 *
 * ZERO MOCKS — apenas tipos e o wrapper `apiFetch`; sem dados embebidos.
 * Vive no território Q.53.K (pages/direcao/) — não toca em lib/api.ts.
 */

import { apiFetch } from '../../lib/api';

// ─── kpis/objectives — espelha ObjectivesService (Q.53.C) ─────────────────

/** Uma banda-alvo do CEO para um KPI. `direction` diz qual lado é bom. */
export interface ObjectiveBand {
  kpi: string;
  label: string;
  unit: string;
  direction: 'higher' | 'lower';
  low: number;
  target: number;
  high: number;
  source: 'seed_default' | 'tenant_config';
}

/** Impacto-PP1 — € poupado por sugestões aceites (decisões executadas). */
export interface Pp1Impact {
  window_days: number;
  accepted_decisions: number;
  decisions_with_eur: number;
  eur_saved: number;
  reason: string | null;
}

export interface KpiObjectivesResponse {
  kpis: ObjectiveBand[];
  pp1_impact: Pp1Impact;
  generated_at: string;
}

// ─── margin-by-segment — espelha MarginSegmentService (Q.53.C) ────────────

export interface MarginSegmentRow {
  segment: string;
  order_count: number;
  revenue_eur: number;
  cogs_eur: number;
  margin_eur: number;
  margin_pct: number | null;
}

export interface MarginSegmentTotal {
  order_count: number;
  revenue_eur: number;
  cogs_eur: number;
  margin_eur: number;
  margin_pct: number | null;
}

export interface MarginBySegmentResponse {
  dimension: 'country' | 'agent';
  segments: MarginSegmentRow[];
  total: MarginSegmentTotal;
  skipped_no_dimension?: number;
  /** false → ERP NELO offline; a página mostra empty state honesto. */
  erp_available: boolean;
  unavailable_reason: string | null;
}

// ─── cliente ──────────────────────────────────────────────────────────────

export const direcaoApi = {
  /** Bandas-alvo do CEO + impacto-PP1. `pp1_window_days` default 90. */
  objectives: (pp1WindowDays = 90) =>
    apiFetch<KpiObjectivesResponse>(
      `/v1/profit/kpis/objectives?pp1_window_days=${pp1WindowDays}`,
    ),

  /** Margem agregada por dimensão de negócio (country | agent). */
  marginBySegment: (dimension: 'country' | 'agent' = 'country') =>
    apiFetch<MarginBySegmentResponse>(
      `/v1/profit/margin-by-segment?dimension=${dimension}`,
    ),
};
