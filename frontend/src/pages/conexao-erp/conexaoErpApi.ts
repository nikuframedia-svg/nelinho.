/**
 * conexaoErpApi — wrapper local da página Conexão ERP (Q.53.L).
 *
 * `GET /v1/diagnostics/erp-connection` (Q.53.F) responde "a ERP NELO
 * está ligada e os dados estão frescos?". O `diagnosticsApi` partilhado
 * (`lib/api.ts`, off-limits) não tem este endpoint, por isso o wrapper
 * vive aqui — passa pelo `apiFetch` partilhado (X-Tenant-Id, retry,
 * circuit-breaker).
 *
 * O endpoint é best-effort: uma ERP morta ou um `core.etl_run` em falta
 * dão uma resposta degradada-mas-shaped, nunca um 500.
 */

import { apiFetch } from '../../lib/api';

/** Estado de uma mirror (tabela espelhada da ERP) na última sync. */
export interface ErpMirror {
  source: string;
  /** "ok" · "error" · "never_synced" · outros estados do core.etl_run. */
  status: string;
  last_run_at: string | null;
  finished_at: string | null;
  rows_read: number;
  rows_inserted: number;
  rows_updated: number;
  rows_skipped: number;
  error: string | null;
}

/** Resposta de GET /v1/diagnostics/erp-connection. */
export interface ErpConnection {
  enabled: boolean;
  /** URL de ligação mascarado — sem credenciais. */
  url_masked: string | null;
  connected: boolean;
  detail: string | null;
  latency_ms: number | null;
  mirrors: ErpMirror[];
  last_sync_at: string | null;
  lag_seconds: number | null;
  lag_human: string | null;
  total_rows_last_sync: number;
  sync_history_error: string | null;
  sampled_at: string;
}

export const conexaoErpApi = {
  /** Estado vivo da integração com a ERP NELO. */
  connection: (): Promise<ErpConnection> =>
    apiFetch<ErpConnection>('/v1/diagnostics/erp-connection'),
};
