/**
 * Q.61.26 — mutator orval. Adapta a chamada gerada para usar o
 * `request<T>()` central do nelinho (tenant + trace_id automaticos).
 *
 * Orval emite chamadas como:
 *   const data = await orvalRequest<T>({ url, method, params, data })
 *
 * Esta funcao re-encaixa em `request<T>(endpoint, options)` da
 * `lib/api/client.ts`.
 */
import { request } from './client';

interface OrvalRequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  params?: Record<string, string | number | boolean | undefined | null>;
  data?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export async function orvalRequest<T>(config: OrvalRequestConfig): Promise<T> {
  const query = config.params
    ? '?' +
      Object.entries(config.params)
        .filter(([_, v]) => v !== undefined && v !== null)
        .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
        .join('&')
    : '';
  const endpoint = `${config.url}${query}`;

  const init: RequestInit = {
    method: config.method,
    headers: config.headers,
    signal: config.signal,
  };
  if (config.data !== undefined) {
    init.body = JSON.stringify(config.data);
  }

  return await request<T>(endpoint, init);
}

export default orvalRequest;
