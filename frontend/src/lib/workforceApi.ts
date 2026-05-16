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

const ROOT = '/v1/workforce';

/**
 * Workforce API client — routes through apiFetch (circuit breaker + retry +
 * tenant/user headers).
 */
export const workforceApi = {
  /**
   * Get the complete dependency graph
   *
   * Returns nodes (phases, employees) and edges (aptitudes).
   */
  async getDependencyGraph(): Promise<DependencyGraph> {
    return apiFetch<DependencyGraph>(`${ROOT}/dependency-graph`);
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
    return apiFetch<CascadeImpact>(`${ROOT}/cascade-impact/${encodeURIComponent(phaseId)}`);
  },

  /**
   * Simulate workforce changes
   * 
   * @param deltas - List of changes to simulate
   * @returns Before/after comparison with impact metrics
   */
  async simulate(deltas: WorkforceDelta[]): Promise<SimulationResult> {
    return apiFetch<SimulationResult>(`${ROOT}/simulate`, {
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
      `${ROOT}/training-recommendations?limit=${limit}`
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
    return apiFetch<ScenarioComparison>(`${ROOT}/scenarios/compare`, {
      method: 'POST',
      body: JSON.stringify(scenarioIds),
    });
  },
};

export default workforceApi;

