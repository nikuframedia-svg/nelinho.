/**
 * ligacoesApi — wrappers locais da página Ligações (Q.53.L).
 *
 * Endpoints do RealtimeBridge:
 *   - GET /v1/realtime/health    — estado do bridge (saúde, subscritores)
 *   - GET /v1/realtime/channels  — canais disponíveis × tópicos Kafka
 *
 * O stream SSE ao vivo (`/v1/realtime/events`) é consumido pelo hook
 * partilhado `useRealtimeEvents` — `EventSource` não passa pelo
 * `apiFetch`, mas estes dois GET passam.
 */

import { apiFetch } from '../../lib/api';

/** Resposta de GET /v1/realtime/health (snapshot do RealtimeBridge). */
export interface RealtimeHealth {
  healthy: boolean;
  started: boolean;
  subscribers: number;
  total_topics: number;
}

/**
 * Resposta de GET /v1/realtime/channels.
 * Mapa `nome do canal → tópicos Kafka cobertos`.
 */
export type RealtimeChannels = Record<string, string[]>;

export const ligacoesApi = {
  health: (): Promise<RealtimeHealth> =>
    apiFetch<RealtimeHealth>('/v1/realtime/health'),

  channels: (): Promise<RealtimeChannels> =>
    apiFetch<RealtimeChannels>('/v1/realtime/channels'),
};
