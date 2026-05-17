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
};

export default workforceApi;

