/**
 * Q.155.E — Índice de Complexidade do Barco (ICB) para os badges da UI.
 * Sem mocks: lê /v1/plan/boat-complexity real (governance.boat_complexity).
 */
import { apiFetch } from './client';

export interface BoatComplexityItem {
  product_id: string;
  product_name: string;
  complexity_score: number; // [0,1]
  rank: number;
  n_components: number;
  paint_kg_per_of: number;
  n_distinct_phases: number;
}

export const boatComplexityApi = {
  list: () => apiFetch<BoatComplexityItem[]>('/v1/plan/boat-complexity'),
};
