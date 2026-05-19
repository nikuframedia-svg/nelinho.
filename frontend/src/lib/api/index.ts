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
