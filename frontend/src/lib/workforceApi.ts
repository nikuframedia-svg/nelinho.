/**
 * Workforce API Client
 * ====================
 * 
 * Client for the Workforce Operations System API endpoints.
 * Provides type-safe methods for:
 * - Dependency graph
 * - Cascade impact analysis
 * - Workforce simulation
 * - Training recommendations
 * - Scenario comparison
 */

import type {
  DependencyGraph,
  CascadeImpact,
  SimulationResult,
  TrainingRecommendation,
  ScenarioComparison,
  WorkforceDelta,
} from '../components/workforce/types';
import { apiFetch } from './api';

// Q.21.A — todo o tráfego passa pelo `apiFetch` (api.ts). O `fetch` directo
// anterior não enviava header `X-Tenant-Id` nenhum, pelo que estes endpoints
// `/v1/workforce/*` falhavam o `require_tenant_header` do backend.

// ── Q.140 — Níveis por sector ───────────────────────────────────────────────

export interface SectorLevelScale {
  min: number;
  max: number;
  best: number;
  step: number;
  convention: string;
}

export interface SectorList {
  sectors: string[];
  level_scale: SectorLevelScale;
}

export interface SectorRankingRow {
  rank: number;
  employee_id: string;
  employee_name: string | null;
  employee_code: string;
  effective_level: number | null;
  derived_level: number | null;
  erp_level: number | null;
  override_level: number | null;
  source: string;
  ops_total: number;
  defects: number;
  recency_days: number | null;
}

export interface SectorRanking {
  area_group: string;
  level_scale: SectorLevelScale;
  ranking: SectorRankingRow[];
  total: number;
}

export interface SectorLevel {
  area_group: string;
  apt: boolean;
  derived_level: number | null;
  erp_level: number | null;
  override_level: number | null;
  effective_level: number | null;
  source: string;
  ops_total: number;
  defects: number;
  recency_days: number | null;
}

export interface EmployeeSectorLevels {
  employee_id: string;
  employee_name: string | null;
  employee_code: string | null;
  level_scale: SectorLevelScale;
  sectors: SectorLevel[];
}

// Q.159 — operadores ativos (E_ACTIVO + últimos 2 meses, ~107) + quebra por área.
export interface OperatorsAreaCount {
  area: string;
  ops: number;
}

export interface OperatorsSummary {
  count: number;
  window_days: number;
  by_area: OperatorsAreaCount[];
}

/**
 * Workforce API client
 */
export const workforceApi = {
  /**
   * Get the complete dependency graph
   *
   * Returns nodes (phases, employees) and edges (aptitudes).
   */
  async getDependencyGraph(): Promise<DependencyGraph> {
    return apiFetch<DependencyGraph>('/v1/workforce/dependency-graph');
  },

  /**
   * Get cascade impact for a phase
   *
   * Shows how workforce issues ripple through:
   * 1. Workforce level
   * 2. Production level
   * 3. Downstream phases
   * 4. Economic impact
   */
  async getCascadeImpact(phaseId: string): Promise<CascadeImpact> {
    return apiFetch<CascadeImpact>(
      `/v1/workforce/cascade-impact/${encodeURIComponent(phaseId)}`,
    );
  },

  /**
   * Simulate workforce changes
   *
   * @param deltas - List of changes to simulate
   * @returns Before/after comparison with impact metrics
   */
  async simulate(deltas: WorkforceDelta[]): Promise<SimulationResult> {
    return apiFetch<SimulationResult>('/v1/workforce/simulate', {
      method: 'POST',
      body: JSON.stringify(deltas),
    });
  },

  /**
   * Get training recommendations
   *
   * Returns recommendations ordered by impact:
   * 1. SPOF elimination
   * 2. Risk reduction
   * 3. Employee proximity
   */
  async getTrainingRecommendations(limit: number = 10): Promise<TrainingRecommendation[]> {
    return apiFetch<TrainingRecommendation[]>(
      `/v1/workforce/training-recommendations?limit=${limit}`,
    );
  },

  /**
   * Compare multiple scenarios
   *
   * Returns side-by-side comparison with:
   * - SPOF count
   * - Risk score
   * - Backlog at risk
   * - Estimated cost
   * - Payback period
   */
  async compareScenarios(scenarioIds: string[]): Promise<ScenarioComparison> {
    return apiFetch<ScenarioComparison>('/v1/workforce/scenarios/compare', {
      method: 'POST',
      body: JSON.stringify(scenarioIds),
    });
  },

  // ── Q.140 — Níveis por sector + ranking por sector ──────────────────────

  /** Lista os 7 grupos de área (sectores) + a escala (3=melhor). */
  async listSectors(): Promise<SectorList> {
    return apiFetch<SectorList>('/v1/workforce/sectors');
  },

  /** Ranking inverso de um sector: colaboradores aptos ordenados por preferência. */
  async getSectorRanking(areaGroup: string, limit = 100): Promise<SectorRanking> {
    const qs = `area_group=${encodeURIComponent(areaGroup)}&limit=${limit}`;
    return apiFetch<SectorRanking>(`/v1/workforce/sectors/ranking?${qs}`);
  },

  /** Os 7 sectores de UM colaborador, cada um com nível efectivo independente. */
  async getEmployeeSectorLevels(employeeId: string): Promise<EmployeeSectorLevels> {
    return apiFetch<EmployeeSectorLevels>(
      `/v1/workforce/employees/${encodeURIComponent(employeeId)}/sector-levels`,
    );
  },

  /** Atribui manualmente o nível de um colaborador num sector (override). */
  async setSectorLevel(
    employeeId: string,
    areaGroup: string,
    nivel: number,
    reason?: string,
  ): Promise<{ employee_id: string; area_group: string; nivel: number }> {
    return apiFetch(
      `/v1/workforce/employees/${encodeURIComponent(employeeId)}/sector-level`,
      {
        method: 'PATCH',
        body: JSON.stringify({ area_group: areaGroup, nivel, reason }),
      },
    );
  },

  // ── Q.159 — Operadores ativos (contagem + quebra por área) ──────────────

  /** Contagem de "operadores ativos" (E_ACTIVO + últimos 2 meses, ~107) + áreas. */
  async getOperatorsSummary(): Promise<OperatorsSummary> {
    return apiFetch<OperatorsSummary>('/v1/workforce/operators/summary');
  },
};

export default workforceApi;

