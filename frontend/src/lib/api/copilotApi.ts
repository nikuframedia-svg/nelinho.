/**
 * ProdPlan ONE — API: copiloto, explain, twin.
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 *
 * Q.68.4.D — `: any` substituído por `unknown`/`Record<string, unknown>`.
 * Erros caught são tipados como `unknown` e destructurados via type guard local.
 */
import { request, API_BASE } from './client';

// Estrutura do erro propagado por request() — `Error` com campos extra anexados.
type ApiError = Error & { status?: number; response?: unknown; message?: string };

// Type guard para errors apanhados em .catch — TS marca-os como `unknown` quando
// `useUnknownInCatchVariables` está activo via `strict`. Aqui só lemos status/message.
function asApiError(err: unknown): ApiError {
  return err as ApiError;
}

// Resposta genérica — endpoints sem DTO concreto ainda; UI faz cast local.
// Components downstream consomem campos dinâmicos (insights.recommendations[i].now, etc).
// Trocar por DTOs Pydantic é Q.68.4.E (ficheiro-a-ficheiro). `any` aqui é dívida explícita.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ApiResponse = any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ApiResponseList = any[];

// ═══════════════════════════════════════════════════════════════════════════════
// COPILOT API
// ═══════════════════════════════════════════════════════════════════════════════

// Import types from separate file (import before using)
import type { CopilotAskRequest, CopilotResponse, DailyFeedbackResponse } from '../copilot-types';

// Re-export types for external use
export type { CopilotAskRequest, CopilotResponse, DailyFeedbackResponse };

export const copilotApi = {
  ask: async (data: CopilotAskRequest) => {
    // Verificar se há token - se não houver, usar diretamente o endpoint dev
    const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
    
    if (!token) {
      // Sem token, usar diretamente endpoint dev (sem autenticação)
      // Criar request manual para endpoint dev com tenant_id correto
      const url = `${API_BASE}/api/copilot/ask-dev`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-Id': '00000000-0000-0000-0000-000000000001', // Tenant dev
        },
        body: JSON.stringify(data),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}`;
        const errorObj = new Error(errorMessage) as ApiError;
        errorObj.status = response.status;
        throw errorObj;
      }

      return await response.json();
    }

    // Com token, tentar endpoint normal primeiro
    try {
      return await request<CopilotResponse>('/api/copilot/ask', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    } catch (rawError: unknown) {
      const error = asApiError(rawError);
      // Se erro de autenticação, tentar endpoint dev
      if (error.status === 401 || error.status === 403 || error.message?.includes('Not authenticated') || error.message?.includes('Unauthorized')) {
        // Criar request manual para endpoint dev com tenant_id correto
        const url = `${API_BASE}/api/copilot/ask-dev`;
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Tenant-Id': '00000000-0000-0000-0000-000000000001', // Tenant dev
          },
          body: JSON.stringify(data),
        });
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}`;
          const errorObj = new Error(errorMessage) as ApiError;
          errorObj.status = response.status;
          throw errorObj;
        }

        return await response.json();
      }
      throw error;
    }
  },

  action: (data: { action_type: string; suggestion_id: string; payload: Record<string, unknown> }) =>
    request<ApiResponse>('/api/copilot/action', {
      method: 'POST',
      body: JSON.stringify(data),
    }).catch((rawError: unknown) => {
      const error = asApiError(rawError);
      // Q.55.C.2 — sem sessão iniciada o /action devolve 401 "Not
      // authenticated"; cai para o endpoint dev, tal como o getDailyFeedback.
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        return request<ApiResponse>('/api/copilot/action-dev', {
          method: 'POST',
          body: JSON.stringify(data),
        });
      }
      throw error;
    }),

  getDailyFeedback: (date?: string) => {
    const endpoint = `/api/copilot/daily-feedback${date ? `?date=${date}` : ''}`;
    const devEndpoint = `/api/copilot/daily-feedback-dev${date ? `?date=${date}` : ''}`;

    return request<DailyFeedbackResponse>(endpoint).catch((rawError: unknown) => {
      const error = asApiError(rawError);
      // Se erro de autenticação, tentar endpoint dev (silenciar erro 401)
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        // Não logar erro 401 - é esperado e vamos usar dev endpoint
        return request<DailyFeedbackResponse>(devEndpoint);
      }
      throw error;
    });
  },

  getSuggestion: (id: string) =>
    request<CopilotResponse>(`/api/copilot/suggestions/${id}`),

  health: () =>
    request<ApiResponse>('/api/copilot/health').catch((rawError: unknown) => {
      const error = asApiError(rawError);
      // Se erro 401, retornar resposta padrão (health pode funcionar sem auth)
      if (error.status === 401) {
        return {
          status: 'degraded',
          ollama: 'unknown',
          embeddings_model: 'unknown',
        };
      }
      throw error;
    }),

  getRecommendations: () => {
    const endpoint = '/api/copilot/recommendations';
    const devEndpoint = '/api/copilot/recommendations-dev';

    return request<ApiResponseList>(endpoint).catch((rawError: unknown) => {
      const error = asApiError(rawError);
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        return request<ApiResponseList>(devEndpoint);
      }
      throw error;
    });
  },

  explainRecommendations: (data: { recommendations: ApiResponseList; user_query?: string }) => {
    const endpoint = '/api/copilot/recommendations/explain';
    const devEndpoint = '/api/copilot/recommendations/explain-dev';

    return request<CopilotResponse>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    }).catch((rawError: unknown) => {
      const error = asApiError(rawError);
      // Se erro de autenticação, tentar endpoint dev (silenciar erro 401)
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        // Não logar erro 401 - é esperado e vamos usar dev endpoint
        return request<CopilotResponse>(devEndpoint, {
          method: 'POST',
          body: JSON.stringify(data),
        });
      }
      throw error;
    });
  },

  getInsights: (date?: string) => {
    const endpoint = `/api/copilot/insights${date ? `?date=${date}` : ''}`;
    const devEndpoint = `/api/copilot/insights-dev${date ? `?date=${date}` : ''}`;

    return request<ApiResponse>(endpoint).catch((rawError: unknown) => {
      const error = asApiError(rawError);
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        return request<ApiResponse>(devEndpoint);
      }
      throw error;
    });
  },

  // Conversations API
  createConversation: (title?: string) => {
    // Se não houver token, rejeitar imediatamente (sem fazer chamada)
    const token = typeof window !== 'undefined' ? (localStorage.getItem('auth_token') || localStorage.getItem('token')) : null;
    if (!token) {
      const error = new Error('Authentication required') as ApiError;
      error.status = 401;
      return Promise.reject(error);
    }

    return request<{ id: string; title: string; created_at: string }>('/api/copilot/conversations', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }).catch((rawError: unknown) => {
      // Se erro 401, re-throw para que o componente possa tratar (criar conversa sem BD)
      throw rawError;
    });
  },
  
  listConversations: (params?: { limit?: number; offset?: number; archived?: boolean }) => {
    // Se não houver token, retornar imediatamente array vazio (sem fazer chamada)
    const token = typeof window !== 'undefined' ? (localStorage.getItem('auth_token') || localStorage.getItem('token')) : null;
    if (!token) {
      return Promise.resolve([]);
    }
    
    const queryParams = new URLSearchParams();
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    if (params?.archived !== undefined) queryParams.set('archived', String(params.archived));
    return request<Array<{
      id: string;
      title: string;
      created_at: string;
      last_message_at: string | null;
      is_archived: boolean;
    }>>(`/api/copilot/conversations?${queryParams.toString()}`).catch((rawError: unknown) => {
      const error = asApiError(rawError);
      // Se erro 401, retornar array vazio (conversas requerem auth, mas não são críticas)
      if (error.status === 401 || error.status === 403) {
        return [];
      }
      throw error;
    });
  },

  getConversationMessages: (conversationId: string, params?: { limit?: number; offset?: number }) => {
    const queryParams = new URLSearchParams();
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    return request<Array<{
      id: string;
      role: 'user' | 'copilot';
      content_text: string;
      content_structured: ApiResponse | null;
      created_at: string;
    }>>(`/api/copilot/conversations/${conversationId}/messages?${queryParams.toString()}`).catch((rawError: unknown) => {
      const error = asApiError(rawError);
      // Se erro 401, retornar array vazio
      if (error.status === 401) {
        return [];
      }
      throw error;
    });
  },

  sendMessage: (conversationId: string, data: CopilotAskRequest) =>
    request<CopilotResponse>(`/api/copilot/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify(data),
    }).catch((rawError: unknown) => {
      // Se erro 401, re-throw para que o componente possa usar endpoint normal
      throw rawError;
    }),
  
  renameConversation: (conversationId: string, title: string) =>
    request<{ id: string; title: string }>(`/api/copilot/conversations/${conversationId}/rename`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),
  
  archiveConversation: (conversationId: string) =>
    request<{ id: string; is_archived: boolean }>(`/api/copilot/conversations/${conversationId}/archive`, {
      method: 'POST',
    }),
  
  // Actions API
  listActions: (params?: { limit?: number; offset?: number; status?: string }) => {
    const queryParams = new URLSearchParams();
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    if (params?.status) queryParams.set('status', params.status);
    return request<Array<{
      transaction_id: string;
      action_type: string;
      user_id: string;
      plan_id: string | null;
      before_state: Record<string, unknown>;
      after_state: Record<string, unknown>;
      status: 'executed' | 'failed' | 'rolled_back';
      executed_at: string;
      rollback_until: string | null;
    }>>(`/api/copilot/actions?${queryParams.toString()}`).catch((rawError: unknown) => {
      const error = asApiError(rawError);
      // Se erro 404, endpoint pode não existir ainda, retornar array vazio
      if (error.status === 404) {
        return [];
      }
      throw error;
    });
  },
  
  rollbackAction: (transactionId: string) =>
    request<{ transaction_id: string; status: string; message: string }>(`/api/copilot/actions/${transactionId}/rollback`, {
      method: 'POST',
    }),
  
  // RAG API
  ingestRAG: (sourceType: string, sourceId: string, text: string, metadata?: Record<string, unknown>) =>
    request<{ status: string; chunks_created: number; source_type: string; source_id: string }>(
      '/api/copilot/rag/ingest',
      {
        method: 'POST',
        body: JSON.stringify({
          source_type: sourceType,
          source_id: sourceId,
          text: text,
          metadata: metadata || {},
        }),
      }
    ),

  // Sandbox API
  executeSandbox: (data: {
    action_type: string;
    target?: string;
    params?: Record<string, unknown>;
    capture_state?: string[];
  }) =>
    request<{
      success: boolean;
      before_state: Record<string, unknown>;
      after_state: Record<string, unknown>;
      deltas: Record<string, unknown>;
      actual_impact: Record<string, unknown>;
      message: string;
    }>('/api/copilot/sandbox', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// EXPLAINABILITY API (C20)
// ═══════════════════════════════════════════════════════════════════════════════

export const explainApi = {
  getMetric: (metricId: string) =>
    request<ApiResponse>(`/v1/explain/metric/${metricId}`),

  getCatalog: () =>
    request<ApiResponse>('/v1/explain/catalog'),

  getBlockedMetrics: () =>
    request<ApiResponse>('/v1/explain/blocked'),

  computeValue: (data: { metric_id: string; params?: Record<string, unknown> }) =>
    request<ApiResponse>('/v1/explain/compute', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// DIGITAL TWIN API (C30)
// ═══════════════════════════════════════════════════════════════════════════════

export const twinApi = {
  createScenario: (data: { title: string; description?: string }) =>
    request<ApiResponse>('/v1/twin/scenarios', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  getScenario: (scenarioId: string) =>
    request<ApiResponse>(`/v1/twin/scenarios/${scenarioId}`),

  listScenarios: () =>
    request<ApiResponse>('/v1/twin/scenarios'),

  applyDelta: (scenarioId: string, delta: object) =>
    request<ApiResponse>(`/v1/twin/scenarios/${scenarioId}/apply-delta`, {
      method: 'POST',
      body: JSON.stringify(delta)
    }),

  simulate: (scenarioId: string) =>
    request<ApiResponse>(`/v1/twin/scenarios/${scenarioId}/simulate`, {
      method: 'POST'
    }),

  solve: (scenarioId: string) =>
    request<ApiResponse>(`/v1/twin/scenarios/${scenarioId}/solve`, {
      method: 'POST'
    }),

  compare: (scenarioId: string, baselineId?: string) => {
    const queryParams = baselineId ? `?baseline_id=${baselineId}` : '';
    return request<ApiResponse>(`/v1/twin/scenarios/${scenarioId}/compare${queryParams}`);
  },

  deleteScenario: (scenarioId: string) =>
    request<void>(`/v1/twin/scenarios/${scenarioId}`, { method: 'DELETE' }),
};

