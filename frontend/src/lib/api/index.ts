/**
 * ProdPlan ONE — API client (barril).
 * ===================================
 *
 * 'lib/api' resolve para este index. A infra partilhada vive em ./client.ts;
 * os objectos de API por endpoint vivem nos ficheiros de domínio abaixo.
 * Os ~126 imports de 'lib/api' espalhados pelo frontend não mudam.
 */
export { apiFetch, getApiBase, setToastContext } from './client';

export * from './masterDataApi';
export * from './planApi';
export * from './profitApi';
export * from './workforceApi';
export * from './supplyApi';
export * from './qualityApi';
export * from './copilotApi';
export * from './governanceApi';
export * from './platformApi';
export * from './dataProductApi';
export * from './opsApi';
// learningApi (plan-vs-actual Q.115.V) — re-exportado com nome distinto
// para evitar conflito com learningApi de governanceApi (governance/learning)
export {
  type DeltaByPhase,
  type DeltaByModel,
  type PlanVsActualReport,
  learningApi as learningPlanApi,
} from './learningApi';
// runbookApi (Q.115.H) — já re-exportado via export * from './qualityApi' acima
