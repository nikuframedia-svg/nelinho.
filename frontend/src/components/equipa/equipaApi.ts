/**
 * equipaApi — wrappers locais da página Equipa.
 *
 * O `lib/api.ts` é ficheiro partilhado (off-limits neste sub-sprint),
 * por isso os endpoints específicos da Equipa que ainda não têm wrapper
 * — ou cujo wrapper partilhado ficou desactualizado — vivem aqui. Todos
 * passam pelo `apiFetch` partilhado: header X-Tenant-Id, retry,
 * circuit-breaker — não há `fetch` cru.
 *
 * Endpoints:
 *   - GET   /v1/workforce/risks/spof                       — SPOFs
 *   - POST  /v1/workforce/simulate/absence                 — simular ausência
 *   - GET   /v1/workforce/employees/{id}/level-summary     — níveis por área
 *   - PATCH /v1/workforce/employees/{id}/skills            — toggle/nivel skill
 *
 * Q.53.L: o `levelSummary` de `lib/api.ts` está preso à escala antiga
 * (`derived_level: 1|2|3` int, sem `per_area_levels`). A escala mudou
 * (Q.53.E) para 3=melhor, 1=pior, meios-níveis 1.0–3.0, por grupo de
 * área. Este wrapper devolve a forma nova.
 *
 * Sprints Q.52.H · Q.53.L.
 */

import { apiFetch } from '../../lib/api';
import type {
  TrainingRecommendation,
  SimulationResult,
} from '../workforce/types';

// ─── Tipos da escala nova (espelha src/workforce/levels.py) ─────────────────

/** Meio-nível válido da escala invertida (3.0 = melhor, 1.0 = pior). */
export type LevelStep = 1.0 | 1.5 | 2.0 | 2.5 | 3.0;

export interface LevelScale {
  min: number;
  max: number;
  step: number;
  best: number;
  convention: string;
}

export interface PerAreaLevel {
  area_group: string;
  /** Nível float (1.0–3.0) do operador nesse grupo de área. */
  level: number;
  /** Quantas fases aptas alimentam este nível de área. */
  phases_apt: number;
}

export interface PerPhaseSkill {
  phase_id: string;
  phase_name?: string | null;
  can_do: boolean;
  nivel?: number | null;
  ops_count: number;
  last_used_at?: string | null;
}

export interface QualificationMetrics {
  recency_days: number | null;
  versatility: number;
  productivity: number | null;
  ops_total: number;
  scope: string | null;
}

/** Resposta de GET /v1/workforce/employees/{id}/level-summary (Q.53.E). */
export interface LevelSummary {
  employee_id: string;
  quality_score: number;
  /** Nível global derivado — float 1.0–3.0, 3.0 = melhor. */
  derived_level: number;
  level_scale: LevelScale;
  level_label: string;
  level_description: string;
  recommended_boats: string[];
  skills_apt: string[];
  per_phase_skills: PerPhaseSkill[];
  /** Nível por grupo de área (~7 grupos). */
  per_area_levels: PerAreaLevel[];
  qualification_metrics: QualificationMetrics;
}

export interface SkillTogglePayload {
  phase_id: string;
  can_do: boolean;
  /** Nível na escala invertida — aceita float 1.0–3.0 (clamped no backend). */
  nivel?: number;
  reason?: string;
}

export const equipaApi = {
  /** SPOFs — alias de training-recommendations filtrado a spof_eliminated. */
  spofs: (limit = 10): Promise<TrainingRecommendation[]> =>
    apiFetch<TrainingRecommendation[]>(
      `/v1/workforce/risks/spof?limit=${limit}`,
    ),

  /** Simular ausência de um operador (wrapper sobre /simulate). */
  simulateAbsence: (employeeId: string): Promise<SimulationResult> =>
    apiFetch<SimulationResult>('/v1/workforce/simulate/absence', {
      method: 'POST',
      body: JSON.stringify({ employee_id: employeeId }),
    }),

  /** Resumo de níveis por grupo de área — escala 3=melhor (Q.53.E). */
  levelSummary: (employeeId: string): Promise<LevelSummary> =>
    apiFetch<LevelSummary>(
      `/v1/workforce/employees/${encodeURIComponent(employeeId)}/level-summary`,
    ),

  /** Toggle de skill / ajuste de nível por fase (PATCH aceita float). */
  toggleSkill: (
    employeeId: string,
    payload: SkillTogglePayload,
  ): Promise<{ employee_id: string; phase_id: string; can_do: boolean }> =>
    apiFetch(
      `/v1/workforce/employees/${encodeURIComponent(employeeId)}/skills`,
      { method: 'PATCH', body: JSON.stringify(payload) },
    ),
};
