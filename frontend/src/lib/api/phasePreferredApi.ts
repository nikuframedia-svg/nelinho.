/**
 * Q.155.B/C — "Melhores operadores por fase" (curado manual + sugestões).
 *
 * Sem mocks: bate em /v1/plan/phases/{id}/preferred-operators real. A curadoria
 * usa employee_code (= E_ID, a identidade do decoder do CPO).
 */
import { apiFetch } from './client';

export interface PhaseListItem {
  phase_id: string;
  phase_name: string;
}

export interface PreferredOperatorItem {
  employee_code: string;
  employee_name: string;
  rank: number;
  note: string | null;
  is_capable: boolean;
}

export interface PreferredSuggestionItem {
  employee_code: string;
  employee_name: string;
  score: number;
  sample_count: number;
  is_capable: boolean;
}

export interface PreferredOperatorsOut {
  phase_id: string;
  curated: PreferredOperatorItem[];
  suggestions: PreferredSuggestionItem[];
}

export interface PreferredOperatorIn {
  employee_code: string;
  note?: string | null;
}

export const phasePreferredApi = {
  listPhases: () => apiFetch<PhaseListItem[]>('/v1/plan/phases'),
  get: (phaseId: string) =>
    apiFetch<PreferredOperatorsOut>(
      `/v1/plan/phases/${encodeURIComponent(phaseId)}/preferred-operators`,
    ),
  put: (phaseId: string, operators: PreferredOperatorIn[]) =>
    apiFetch<PreferredOperatorsOut>(
      `/v1/plan/phases/${encodeURIComponent(phaseId)}/preferred-operators`,
      { method: 'PUT', body: JSON.stringify({ operators }) },
    ),
};
