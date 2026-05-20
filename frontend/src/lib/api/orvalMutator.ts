/**
 * Q.61.26 — mutator orval. Adapta a chamada gerada para usar o
 * `request<T>()` central do nelinho (tenant + trace_id automaticos).
 *
 * Orval (com client: 'react-query') emite chamadas como:
 *
 *     orvalRequest<T>(url, { ...options, method: 'GET' })
 *
 * Esta funcao re-encaixa em `request<T>(endpoint, options)` da
 * `lib/api/client.ts`.
 *
 * Q.61.42 — primeiro run do `gen:api` revelou que a assinatura era
 * (config) mas orval gera (url, options); corrigido aqui para a forma
 * actual.
 */
import { request } from './client';

interface OrvalRequestInit extends RequestInit {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  data?: unknown;
}

export async function orvalRequest<T>(
  url: string,
  options?: OrvalRequestInit,
): Promise<T> {
  const init: RequestInit = {
    method: options?.method ?? 'GET',
    headers: options?.headers,
    signal: options?.signal,
  };
  if (options?.data !== undefined) {
    init.body = JSON.stringify(options.data);
  }

  return await request<T>(url, init);
}

export default orvalRequest;
