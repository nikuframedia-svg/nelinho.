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

const API_ROOT = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = `${API_ROOT}/v1/workforce`;

/**
 * Helper to handle API responses
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API Error: ${response.status} - ${errorText}`);
  }
  return response.json();
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
    const response = await fetch(`${API_BASE}/dependency-graph`);
    return handleResponse<DependencyGraph>(response);
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
    const response = await fetch(`${API_BASE}/cascade-impact/${encodeURIComponent(phaseId)}`);
    return handleResponse<CascadeImpact>(response);
  },

  /**
   * Simulate workforce changes
   * 
   * @param deltas - List of changes to simulate
   * @returns Before/after comparison with impact metrics
   */
  async simulate(deltas: WorkforceDelta[]): Promise<SimulationResult> {
    const response = await fetch(`${API_BASE}/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(deltas),
    });
    return handleResponse<SimulationResult>(response);
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
    const response = await fetch(`${API_BASE}/training-recommendations?limit=${limit}`);
    return handleResponse<TrainingRecommendation[]>(response);
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
    const response = await fetch(`${API_BASE}/scenarios/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(scenarioIds),
    });
    return handleResponse<ScenarioComparison>(response);
  },
};

export default workforceApi;

