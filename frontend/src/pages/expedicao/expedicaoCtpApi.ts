/**
 * expedicaoCtpApi — cliente do Capable-to-Promise (Q.53.B).
 *
 * Liga ao endpoint real:
 *   - POST /v1/plan/ctp   (CapableToPromiseService.evaluate)
 *
 * Dado um camião (data + capacidade) devolve os barcos que encaixam
 * (data viável, capacidade, materiais, molde) divididos em
 * committable / at-risk / rejected.
 *
 * ZERO MOCKS — apenas tipos e o wrapper `apiFetch`. Território Q.53.K
 * (pages/expedicao/) — não toca em lib/api.ts.
 */

import { apiFetch } from '../../lib/api';

// ─── pedido ───────────────────────────────────────────────────────────────

export interface CtpRequest {
  /** Data de partida do camião (ISO YYYY-MM-DD). */
  truck_date: string;
  /** Slots livres no camião (1–100). */
  truck_capacity: number;
  /** Quando a produção pode começar (ISO; default no backend = hoje). */
  start_from?: string;
  /** Restringir a estas ordens (default: todas em curso). */
  order_ids?: string[];
}

// ─── resposta — espelha CapableToPromiseService.evaluate ──────────────────

/** Um barco avaliado pelo CTP. */
export interface CtpBoat {
  order_id: string;
  hull: string | null;
  product_name: string | null;
  product_type: string | null;
  /** Data sugerida de expedição (ISO) — null se não houver lead-time. */
  suggested_shipment: string | null;
  lead_time: number | null;
  date_feasible: boolean;
  materials_ok: boolean;
  missing_materials: string[];
  /** Presente só nos at-risk — razão da degradação. */
  risk?: string;
}

export interface CtpSummary {
  n_evaluated: number;
  n_committable: number;
  n_at_risk: number;
  n_rejected: number;
}

export interface CtpResponse {
  truck_date: string;
  truck_capacity: number;
  slots_used: number;
  slots_free: number;
  /** Barcos que encaixam — data viável, capacidade e materiais OK. */
  committable: CtpBoat[];
  /** Encaixam na data mas têm falta de material — decisão do planeador. */
  at_risk: CtpBoat[];
  /** Não chegam a tempo para a data do camião. */
  rejected: CtpBoat[];
  summary: CtpSummary;
}

// ─── cliente ──────────────────────────────────────────────────────────────

export const expedicaoCtpApi = {
  /** Avalia que barcos encaixam num camião/data. */
  evaluate: (body: CtpRequest) =>
    apiFetch<CtpResponse>('/v1/plan/ctp', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};
