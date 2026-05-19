/**
 * Tipos da página Simulações — mapeiam o `ScenarioResponse` do twin.
 *
 * Sprint Q.52.M.
 */

export interface TwinScenario {
  id: string;
  title: string;
  description?: string | null;
  status?: string;
  created_at?: string | null;
  updated_at?: string | null;
  deltas?: Array<Record<string, unknown>>;
  simulation_result?: Record<string, unknown> | null;
  scenario_hash?: string | null;
}
