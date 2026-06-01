/**
 * Q.116.A — Entity summary API (modelo / fase / cliente / encomenda).
 *
 * Tipos espelham os schemas Pydantic do backend.
 * Sem mocks — empty/error states explícitos nas sheets.
 */
import { apiFetch } from './client';

export type EntityKind = 'modelo' | 'fase' | 'cliente' | 'encomenda' | 'operador';

export interface TopPhaseForOperator {
  phase_id: string;
  phase_name: string;
  score: number;
  sample_count: number;
}

export interface OperadorSummary {
  operator_id: string;
  operator_name: string;
  role: string | null;
  active: boolean;
  top_phases: TopPhaseForOperator[];
  total_phases_with_data: number;
}

export interface PhaseInTemplate {
  // id: row UUID para endpoint sequence (Q.116.B); ausente até Q.116.A.fix
  id?: string;
  seq: number;
  phase_id: string;
  phase_name: string | null;
  duration_p50_h: number | null;
  can_skip: boolean;
  // Q.116.B — posição alternativa
  is_flexible?: boolean;
  allowed_predecessors?: string[];
}

export interface RoutingTemplateOut {
  id: string;
  code: string;
  name: string;
  phase_count: number;
  phases: PhaseInTemplate[];
}

// Q.116.G — barco em produção (para lista no ModeloSheet)
export interface BoatInProduction {
  legacy_id: number;
  current_phase_name: string;
  customer_name: string | null;
  transport_date: string | null;
  effective_boost: number;
}

export interface ModeloSummary {
  model_id: string;
  model_name: string;
  product_type: string | null;
  routing_template: RoutingTemplateOut | null;
  active_orders_count: number;
  in_production_count: number;
  in_production_boats: BoatInProduction[];   // Q.116.G
  orders: OrderInList[];                      // Q.116.C — encomendas activas
  phase_drilldown: PhaseDrilldown[];          // Q.116.E — top operadores por fase
}

// Q.116.E — uma fase da rota do modelo + os seus top operadores
export interface PhaseDrilldown {
  phase_id: string;
  phase_name: string | null;
  seq: number;
  top_operators: OperatorScore[];
}

export interface OperatorScore {
  operator_id: string;
  operator_name: string;
  score: number;
  sample_count: number;
}

export interface BoatScore {
  boat_id: string;
  score: number;
  sample_count: number;
}

export interface CuringGap {
  from_phase: string;
  to_phase: string;
  hours: number;
}

export interface FaseSummary {
  phase_id: string;
  phase_name: string;
  top_operators: OperatorScore[];
  difficult_boats: BoatScore[];
  curing_gaps_in: CuringGap[];
  curing_gaps_out: CuringGap[];
}

export interface OrderInList {
  legacy_id: number;
  product_name: string;
  current_phase_name: string;
  transport_date: string | null;
  status: string;
}

export interface ClienteSummary {
  customer_id: string;
  customer_name: string;
  priority: number | null;
  active_orders_count: number;
  orders: OrderInList[];
}

export interface PhaseHistoryEntry {
  phase_name: string;
  start_at: string | null;
  end_at: string | null;
}

export interface EncomendaSummary {
  legacy_id: number;
  product_name: string;
  product_type: string | null;
  customer_name: string | null;
  status: string;
  current_phase_name: string;
  created_date: string | null;
  transport_date: string | null;
  completed_date: string | null;
  phase_history: PhaseHistoryEntry[];
  // Q.116.C — boost + transport_date override (Agent A)
  boost: number;
  boost_reason: string | null;
  transport_date_override: string | null;
  transport_date_effective: string | null;
  // Q.116.G — boost breakdown (do backend)
  client_boost: number;
  boat_boost: number;
  effective_boost: number;
}

// Q.116.C — boost + transport_date override mutations

export interface OrderBoostUpsert {
  boost: number;        // 0-100
  reason?: string | null;
}

export interface OrderBoostOut {
  work_order_id: number;
  boost: number;
  reason: string | null;
  updated_by: string;
  updated_at: string;
}

export interface TransportDateUpsert {
  transport_date: string | null;   // ISO datetime, null = clear override
  reason?: string | null;
}

export interface WorkOrderOverrideOut {
  work_order_id: number;
  transport_date_override: string | null;
  reason: string | null;
  updated_by: string;
  updated_at: string;
}

// Q.135.3.4 — Configuração de fase (CPO overrides)

export interface PhaseConfigOverrides {
  team_size_override: number | null;
  num_stations_override: number | null;
  allowed_worker_ids: string[] | null;
  note: string | null;
}

export interface PhaseConfigBaselines {
  capable_worker_ids: string[];
  affinity_worker_ids: string[];
  suggested_stations: number;
  team_size_default: number;
  expected_duration_h: number | null;
  canonical_rank: number | null;
  typical_prev_phase: string | null;
  typical_next_phase: string | null;
}

export interface PhaseConfigOut {
  phase_id: string;
  overrides: PhaseConfigOverrides;
  baselines: PhaseConfigBaselines;
}

export interface PhaseConfigPut {
  team_size_override?: number | null;
  num_stations_override?: number | null;
  allowed_worker_ids?: string[] | null;
  note?: string | null;
}

export const entityApi = {
  modelo: (id: string) =>
    apiFetch<ModeloSummary>(`/v1/entity/modelo/${encodeURIComponent(id)}`),
  fase: (id: string) =>
    apiFetch<FaseSummary>(`/v1/entity/fase/${encodeURIComponent(id)}`),
  cliente: (id: string) =>
    apiFetch<ClienteSummary>(`/v1/entity/cliente/${encodeURIComponent(id)}`),
  encomenda: (id: string | number) =>
    apiFetch<EncomendaSummary>(`/v1/entity/encomenda/${id}`),
  operador: (id: string) =>
    apiFetch<OperadorSummary>(`/v1/entity/operador/${encodeURIComponent(id)}`),
  upsertOrderBoost: (workOrderId: number, body: OrderBoostUpsert) =>
    apiFetch<OrderBoostOut>(`/v1/plan/order-boost/${workOrderId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  upsertTransportDate: (workOrderId: number, body: TransportDateUpsert) =>
    apiFetch<WorkOrderOverrideOut>(`/v1/plan/work-orders/${workOrderId}/transport-date`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // Q.116.B — routing template admin
  updateTemplateSequence: (templateId: string, body: UpdateSequenceBody) =>
    apiFetch<unknown>(`/v1/plan/routing-templates/${templateId}/sequence`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  setPhaseFlexible: (templateId: string, phaseRowId: string, body: SetFlexibleBody) =>
    apiFetch<unknown>(`/v1/plan/routing-templates/${templateId}/phases/${phaseRowId}/flexible`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // Q.116.D — boat boost
  upsertBoatBoost: (boatId: string, body: BoatBoostUpsert) =>
    apiFetch<BoatBoostOut>(`/v1/plan/boat-boost/${encodeURIComponent(boatId)}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // Q.135.3.4 — configuração de fase (CPO overrides)
  phaseConfig: {
    get: (phaseId: string) =>
      apiFetch<PhaseConfigOut>(`/v1/plan/phases/${encodeURIComponent(phaseId)}/config`),
    put: (phaseId: string, body: PhaseConfigPut) =>
      apiFetch<PhaseConfigOut>(`/v1/plan/phases/${encodeURIComponent(phaseId)}/config`, {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
  },
};

// Q.116.B — routing template admin

export interface UpdateSequenceBody {
  phase_order: string[];   // UUIDs das phase rows na nova ordem
}

export interface SetFlexibleBody {
  is_flexible: boolean;
  allowed_predecessors: string[];   // phase_ids alternativos
}

// Q.116.D — boat boost

export interface BoatBoostUpsert {
  boost: number;       // 0-100
  reason?: string | null;
}

export interface BoatBoostOut {
  boat_id: string;
  boost: number;
  reason: string | null;
  updated_by: string;
  updated_at: string;
}
