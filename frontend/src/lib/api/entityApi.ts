/**
 * Q.116.A — Entity summary API (modelo / fase / cliente / encomenda).
 *
 * Tipos espelham os schemas Pydantic do backend.
 * Sem mocks — empty/error states explícitos nas sheets.
 */
import { apiFetch } from './client';

export type EntityKind = 'modelo' | 'fase' | 'cliente' | 'encomenda';

export interface PhaseInTemplate {
  seq: number;
  phase_id: string;
  phase_name: string | null;
  duration_p50_h: number | null;
  can_skip: boolean;
}

export interface RoutingTemplateOut {
  id: string;
  code: string;
  name: string;
  phase_count: number;
  phases: PhaseInTemplate[];
}

export interface ModeloSummary {
  model_id: string;
  model_name: string;
  product_type: string | null;
  routing_template: RoutingTemplateOut | null;
  active_orders_count: number;
  in_production_count: number;
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
};
