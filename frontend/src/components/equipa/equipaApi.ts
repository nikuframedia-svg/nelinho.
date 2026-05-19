/**
 * equipaApi — wrappers locais da página Equipa (Q.52.H).
 *
 * O `lib/api.ts` é ficheiro partilhado (off-limits na Onda 1), por isso
 * os endpoints específicos da Equipa que ainda não têm wrapper vivem aqui.
 * Todos passam pelo `apiFetch` partilhado — header X-Tenant-Id, retry,
 * circuit-breaker — não há `fetch` cru.
 *
 * Endpoints:
 *   - GET  /v1/workforce/risks/spof          — SPOFs detectados
 *   - POST /v1/workforce/simulate/absence    — simular ausência de 1 operador
 *
 * Sprint Q.52.H.
 */

import { apiFetch } from '../../lib/api';
import type {
  TrainingRecommendation,
  SimulationResult,
} from '../workforce/types';

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
};
