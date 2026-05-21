/**
 * ProdPlan ONE — API: Factory Data Product / semantic views.
 *
 * Q.18.ZIP.A.Onda15 — O. Data Product. Allow-listed semantic queries
 * (read-only, anti-SQL-injection). Endpoints:
 *   GET /v1/factory/semantic            — lista todas as views allow-listed
 *   GET /v1/factory/semantic/{view_id}  — query individual com paginação
 *
 * Q.67.2.C — migração de `fetch()` directos em FactoryPulsePanels.tsx para o
 * fetch layer central (`request` injecta tenant/user/trace_id).
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 */
import { request } from './client';

export interface SemanticView {
  view_id: string;
  name: string;
  description?: string;
  fields?: string[];
  is_sensitive?: boolean;
  trust_score?: number | null;
  disclaimers?: string[];
}

export interface SemanticViewsResponse {
  views?: SemanticView[];
}

export interface SemanticQueryResponse {
  view_id?: string;
  rows?: Array<Record<string, unknown>>;
  row_count?: number;
  fields?: string[];
  trust_score?: number;
  disclaimers?: string[];
}

export const dataProductApi = {
  listSemanticViews: () =>
    request<SemanticViewsResponse>('/v1/factory/semantic'),

  querySemanticView: (viewId: string, limit = 15) =>
    request<SemanticQueryResponse>(
      `/v1/factory/semantic/${viewId}?limit=${limit}`,
    ),
};
