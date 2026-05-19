/**
 * custosApi — wrappers tipados para a página Custos (Q.53.I).
 *
 * Liga aos endpoints REAIS do módulo profit que ainda não têm wrapper
 * canónico em `lib/api.ts`:
 *   - GET  /v1/profit/cost-ledger        (Q.53.C — ledger consolidado)
 *   - GET  /v1/profit/margin-by-segment  (Q.53.C — margem por dimensão)
 *   - GET  /v1/profit/kpis/objectives    (Q.53.C — bandas-alvo do CEO)
 *   - POST /v1/profit/scenarios/simulate (simulador de cenários what-if)
 *
 * Usa o `apiFetch` exportado de `lib/api.ts` — NÃO faz `fetch` cru, para
 * passar pelo circuit breaker / headers / tenant. ZERO MOCKS: os tipos
 * derivam dos schemas do backend (`cost_ledger_service.py`,
 * `scenario_simulator.py`). Quando faltar cálculo, o backend devolve
 * `calculated=false` — nada é imputado.
 */

import { apiFetch } from '../../lib/api';

// ─── /cost-ledger — ledger de custos consolidado ───────────────────────────

/** Uma linha de centro de custo (os 6 componentes COGS). */
export interface CostCenterLine {
  cost_center: string;
  total_eur: number;
  share_pct: number | null;
}

/** Driver de custo — centro de custo ordenado por € gasto. */
export interface CostDriver {
  rank: number;
  cost_center: string;
  total_eur: number;
  share_pct: number | null;
}

/** Margem agregada por tipo de produto (K1, K2, K4…). */
export interface MarginByProduct {
  product_type: string;
  order_count: number;
  orders_with_revenue: number;
  total_cogs_eur: number;
  total_revenue_eur: number | null;
  margin_eur: number | null;
  margin_pct: number | null;
}

/** COGS detalhado de um barco. */
export interface BoatCostRow {
  order_id: string;
  hull: string;
  product_name: string | null;
  product_type: string | null;
  calculated: boolean;
  cogs_breakdown: Record<string, number> | null;
  total_cogs_eur: number | null;
  revenue_eur: number | null;
  margin_eur: number | null;
  margin_pct: number | null;
}

export interface CostLedgerSummary {
  orders_total: number;
  orders_calculated: number;
  orders_uncalculated: number;
  total_cogs_eur: number;
}

export interface CostLedger {
  date_from: string | null;
  date_to: string | null;
  summary: CostLedgerSummary;
  cost_by_center: CostCenterLine[];
  cost_drivers: CostDriver[];
  margin_by_product: MarginByProduct[];
  per_boat: BoatCostRow[];
  currency: string;
  source: string;
}

// ─── /margin-by-segment — margem por dimensão de negócio ───────────────────

export interface MarginSegment {
  erp_available?: boolean;
  dimension?: string;
  segments?: Array<{
    label?: string;
    revenue_eur?: number;
    cogs_eur?: number;
    margin_eur?: number;
    margin_pct?: number;
    order_count?: number;
    [k: string]: unknown;
  }>;
  [k: string]: unknown;
}

// ─── /kpis/objectives — bandas-alvo do CEO ─────────────────────────────────

export interface KpiObjectives {
  pp1_impact?: {
    accepted_decisions?: number;
    eur_saved?: number;
    window_days?: number;
    [k: string]: unknown;
  };
  objectives?: Array<{
    kpi?: string;
    label?: string;
    low?: number;
    target?: number;
    high?: number;
    unit?: string;
    [k: string]: unknown;
  }>;
  [k: string]: unknown;
}

// ─── /scenarios/simulate — simulador what-if ───────────────────────────────

export interface ScenarioSimulateRequest {
  base_order_id: string;
  scenario_name?: string;
  material_multiplier?: number;
  labor_multiplier?: number;
  machine_multiplier?: number;
  overhead_multiplier?: number;
  scrap_multiplier?: number;
  volume_multiplier?: number;
}

export interface ScenarioSimulateResult {
  scenario_name: string;
  scenario_description: string;
  base_cogs_per_unit: number;
  scenario_cogs_per_unit: number;
  delta_amount: number;
  delta_percent: number;
  multipliers: Record<string, number>;
  volume_multiplier: number;
  base_breakdown: Record<string, number>;
  scenario_breakdown: Record<string, number>;
  impact_analysis: Record<string, unknown>;
  recommendation: string;
}

export const custosApi = {
  /** Ledger de custos consolidado — COGS por centro de custo + por barco. */
  costLedger: (params?: { from?: string; to?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.from) qs.set('from', params.from);
    if (params?.to) qs.set('to', params.to);
    if (params?.limit !== undefined) qs.set('limit', String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return apiFetch<CostLedger>(`/v1/profit/cost-ledger${suffix}`);
  },

  /** Margem agregada por dimensão de negócio (país / agente). */
  marginBySegment: (dimension: 'country' | 'agent' = 'country') =>
    apiFetch<MarginSegment>(
      `/v1/profit/margin-by-segment?dimension=${encodeURIComponent(dimension)}`,
    ),

  /** Bandas-alvo do CEO + impacto-PP1 (€ poupado por sugestões aceites). */
  kpiObjectives: () =>
    apiFetch<KpiObjectives>('/v1/profit/kpis/objectives'),

  /** Simula um cenário what-if sobre o COGS de um barco base. */
  simulateScenario: (payload: ScenarioSimulateRequest) =>
    apiFetch<ScenarioSimulateResult>('/v1/profit/scenarios/simulate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
