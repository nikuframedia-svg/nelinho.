/**
 * Q.61.25 — helper centralizado para os panels causais.
 *
 * Antes do Q.61.25 cada um dos 9 panels (AttributionPanel, ErroTreePanel,
 * InvestigatePanel, MillPanel, NeloDagPanel, PoetiqPanel,
 * ReichenbachPanel, WhyKpiPanel, ...) fazia `fetch(BASE + path, {
 * headers: TENANT })` directamente — exactamente o que Q.61.07 marca
 * em `lint:mocks` como `warn`.
 *
 * Este helper:
 *   * usa `request<T>()` de `lib/api/client` (apiFetch central)
 *   * tenant + user + trace_id (Q.61.12) injectados automaticamente
 *   * devolve `null` em 4xx em vez de lancar — preserva o contrato
 *     `enabled: false` dos panels (que esperam `null` quando o
 *     endpoint nao bate)
 */
import { request } from './client';

/**
 * GET genérico para um endpoint causal/explain.
 *
 * Em caso de 4xx devolve `null` (vs `useQuery` lança). Preserva o
 * contrato pre-Q.61.25 dos panels: `if (!r.ok) return null;`.
 */
export async function causalGet<T = unknown>(path: string): Promise<T | null> {
  try {
    return await request<T>(path, { method: 'GET' });
  } catch (err) {
    // request() lança "HTTP NNN: ..." para 4xx/5xx. Para os panels
    // (modo enabled:false + retry:0), reduzir 4xx a `null` evita
    // mostrar erro vermelho num panel que so foi clicado uma vez.
    const msg = err instanceof Error ? err.message : String(err);
    if (/HTTP 4\d\d/.test(msg)) return null;
    throw err;
  }
}

/**
 * POST com body JSON. Usado por panels que enviam params no body.
 */
export async function causalPost<T = unknown>(
  path: string,
  body: Record<string, unknown> | undefined,
): Promise<T | null> {
  try {
    return await request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (/HTTP 4\d\d/.test(msg)) return null;
    throw err;
  }
}
