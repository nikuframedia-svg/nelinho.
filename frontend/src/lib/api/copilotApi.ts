/**
 * ProdPlan ONE — API: copiloto, explain, twin.
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 */
import { request, API_BASE } from './client';

// ═══════════════════════════════════════════════════════════════════════════════
// COPILOT API
// ═══════════════════════════════════════════════════════════════════════════════

// Import types from separate file (import before using)
import type { CopilotAskRequest, CopilotResponse, DailyFeedbackResponse } from '../copilot-types';

// Re-export types for external use
export type { CopilotAskRequest, CopilotResponse, DailyFeedbackResponse };

const DEV_TENANT = '00000000-0000-0000-0000-000000000001';

// ── Q.R — Cube-first: adaptador AskCubeResponse → CopilotResponse ───────────
// O chat passa a perguntar primeiro à camada semântica (Cube, dados reais).
// Em `abstain` (perguntas causais / fora do catálogo) cai para o pipeline
// SQL+RAG geral (/ask). A UI do chat já consome CopilotResponse — só wiring.

interface AskCubeResponse {
  status: 'ok' | 'abstain' | 'no_data' | 'guard_failed' | 'ambiguous';
  narration?: string | null;
  query?: Record<string, unknown> | null;
  data?: Array<Record<string, unknown>>;
  annotation?: Record<string, unknown> | null;
  abstain_reason?: string | null;
  warnings?: string[];
}

function cubeToCopilotResponse(r: AskCubeResponse): CopilotResponse {
  const id = `cube-${Date.now()}`;
  const cubeCitation = {
    source_type: 'calculation' as const,
    ref: 'cube',
    label: 'Cube · camada semântica',
    confidence: 1,
    trust_index: 1,
  };

  const facts: CopilotResponse['facts'] = [];
  if (r.narration) {
    facts.push({ text: r.narration, citations: [cubeCitation] });
  }
  // Dados crus (amostra) como facto auditável quando o guard rejeitou a
  // narração ou quando não há narração mas há linhas.
  if (r.data && r.data.length > 0 && (r.status === 'guard_failed' || !r.narration)) {
    const preview = r.data
      .slice(0, 8)
      .map((row) =>
        Object.entries(row)
          .map(([k, v]) => `${k.split('.').pop()}: ${v}`)
          .join(' · '),
      )
      .join('\n');
    facts.push({ text: preview, citations: [cubeCitation] });
  }

  const warnings: CopilotResponse['warnings'] = [];
  if (r.status === 'no_data')
    warnings.push({ code: 'INSUFFICIENT_EVIDENCE', message: 'Sem dados para os filtros indicados.' });
  if (r.status === 'ambiguous')
    warnings.push({ code: 'INSUFFICIENT_EVIDENCE', message: 'Pergunta vaga — especifica material e/ou período.' });
  if (r.status === 'guard_failed')
    warnings.push({ code: 'VALIDATION_FAILED', message: 'A narração não passou o guard de números; mostro os dados crus.' });
  for (const w of r.warnings ?? []) warnings.push({ code: 'VALIDATION_FAILED', message: w });

  const summary =
    r.narration ??
    (r.status === 'no_data'
      ? 'Não há dados para esses filtros.'
      : r.status === 'ambiguous'
        ? 'Pergunta demasiado vaga — especifica material e/ou período.'
        : 'Resposta do Cube.');

  return {
    suggestion_id: id,
    correlation_id: id,
    type: 'ANSWER',
    intent: 'generic',
    summary,
    facts,
    actions: [],
    warnings,
    meta: { model: 'cube+gemma4', tokens: 0, latency_ms: 0, validation_passed: r.status === 'ok' },
  };
}

/** Tenta a camada Cube; devolve a resposta adaptada ou null para fazer fallback. */
async function tryAskCube(userQuery: string): Promise<CopilotResponse | null> {
  try {
    const response = await fetch(`${API_BASE}/api/copilot/ask-dev-cube`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Tenant-Id': DEV_TENANT },
      body: JSON.stringify({ question: userQuery }),
    });
    if (!response.ok) return null;
    const cube = (await response.json()) as AskCubeResponse;
    // abstain = causal / fora-catálogo → deixar o pipeline geral responder.
    if (cube.status === 'abstain') return null;
    return cubeToCopilotResponse(cube);
  } catch {
    return null; // Cube indisponível → fallback silencioso
  }
}

export const copilotApi = {
  ask: async (data: CopilotAskRequest) => {
    // Q.R — Cube-first: a pergunta vai primeiro à camada semântica (dados
    // reais via Cube). Se responder (ok/no_data/ambiguous/guard_failed),
    // adaptamos e devolvemos. Em `abstain` (causal/fora-catálogo) ou erro,
    // cai para o pipeline SQL+RAG geral abaixo (comportamento preservado).
    const cubeAnswer = await tryAskCube(data.user_query);
    if (cubeAnswer) return cubeAnswer;

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
        const errorObj = new Error(errorMessage);
        (errorObj as any).status = response.status;
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
    } catch (error: any) {
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
          const errorObj = new Error(errorMessage);
          (errorObj as any).status = response.status;
          throw errorObj;
        }
        
        return await response.json();
      }
      throw error;
    }
  },
  
  action: (data: { action_type: string; suggestion_id: string; payload: any }) =>
    request<any>('/api/copilot/action', {
      method: 'POST',
      body: JSON.stringify(data),
    }).catch((error: any) => {
      // Q.55.C.2 — sem sessão iniciada o /action devolve 401 "Not
      // authenticated"; cai para o endpoint dev, tal como o getDailyFeedback.
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        return request<any>('/api/copilot/action-dev', {
          method: 'POST',
          body: JSON.stringify(data),
        });
      }
      throw error;
    }),
  
  getDailyFeedback: (date?: string) => {
    const endpoint = `/api/copilot/daily-feedback${date ? `?date=${date}` : ''}`;
    const devEndpoint = `/api/copilot/daily-feedback-dev${date ? `?date=${date}` : ''}`;
    
    return request<DailyFeedbackResponse>(endpoint).catch((error: any) => {
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
    request<any>('/api/copilot/health').catch((error: any) => {
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
    
    return request<any[]>(endpoint).catch((error: any) => {
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        return request<any[]>(devEndpoint);
      }
      throw error;
    });
  },
  
  explainRecommendations: (data: { recommendations: any[]; user_query?: string }) => {
    const endpoint = '/api/copilot/recommendations/explain';
    const devEndpoint = '/api/copilot/recommendations/explain-dev';
    
    return request<CopilotResponse>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    }).catch((error: any) => {
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
    
    return request<any>(endpoint).catch((error: any) => {
      if (error.status === 401 || error.message?.includes('Not authenticated')) {
        return request<any>(devEndpoint);
      }
      throw error;
    });
  },
  
  // Conversations API
  createConversation: (title?: string) => {
    // Se não houver token, rejeitar imediatamente (sem fazer chamada)
    const token = typeof window !== 'undefined' ? (localStorage.getItem('auth_token') || localStorage.getItem('token')) : null;
    if (!token) {
      const error = new Error('Authentication required');
      (error as any).status = 401;
      return Promise.reject(error);
    }
    
    return request<{ id: string; title: string; created_at: string }>('/api/copilot/conversations', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }).catch((error: any) => {
      // Se erro 401, re-throw para que o componente possa tratar (criar conversa sem BD)
      throw error;
    });
  },
  
  listConversations: (params?: { limit?: number; offset?: number; archived?: boolean }) => {
    // Histórico de conversas exige JWT real. Sem token — ou com um token que não
    // tem forma de JWT (ex. dev-fallback sem login) — devolve [] sem chamar, para
    // não gerar 401 de rede/consola. O empty-state continua honesto (ZERO MOCKS).
    const token = typeof window !== 'undefined' ? (localStorage.getItem('auth_token') || localStorage.getItem('token')) : null;
    if (!token || token.split('.').length !== 3) {
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
    }>>(`/api/copilot/conversations?${queryParams.toString()}`).catch((error: any) => {
      // Se erro 401, retornar array vazio (conversas requerem auth, mas não são críticas)
      if (error.status === 401 || error.status === 403) {
        return [];
      }
      throw error;
    });
  },
  
  getConversationMessages: (conversationId: string, params?: { limit?: number; offset?: number }) => {
    const token = typeof window !== 'undefined' ? (localStorage.getItem('auth_token') || localStorage.getItem('token')) : null;
    if (!token || token.split('.').length !== 3) {
      return Promise.resolve([]);
    }
    const queryParams = new URLSearchParams();
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    return request<Array<{
      id: string;
      role: 'user' | 'copilot';
      content_text: string;
      content_structured: any | null;
      created_at: string;
    }>>(`/api/copilot/conversations/${conversationId}/messages?${queryParams.toString()}`).catch((error: any) => {
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
    }).catch((error: any) => {
      // Se erro 401, re-throw para que o componente possa usar endpoint normal
      throw error;
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
      before_state: Record<string, any>;
      after_state: Record<string, any>;
      status: 'executed' | 'failed' | 'rolled_back';
      executed_at: string;
      rollback_until: string | null;
    }>>(`/api/copilot/actions?${queryParams.toString()}`).catch((error: any) => {
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
  ingestRAG: (sourceType: string, sourceId: string, text: string, metadata?: Record<string, any>) =>
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
    params?: Record<string, any>;
    capture_state?: string[];
  }) =>
    request<{
      success: boolean;
      before_state: Record<string, any>;
      after_state: Record<string, any>;
      deltas: Record<string, any>;
      actual_impact: Record<string, any>;
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
    request<any>(`/v1/explain/metric/${metricId}`),
  
  getCatalog: () => 
    request<any>('/v1/explain/catalog'),
  
  getBlockedMetrics: () => 
    request<any>('/v1/explain/blocked'),
  
  computeValue: (data: { metric_id: string; params?: Record<string, any> }) => 
    request<any>('/v1/explain/compute', { 
      method: 'POST', 
      body: JSON.stringify(data) 
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// DIGITAL TWIN API (C30)
// ═══════════════════════════════════════════════════════════════════════════════

export const twinApi = {
  createScenario: (data: { title: string; description?: string }) => 
    request<any>('/v1/twin/scenarios', { 
      method: 'POST', 
      body: JSON.stringify(data) 
    }),
  
  getScenario: (scenarioId: string) => 
    request<any>(`/v1/twin/scenarios/${scenarioId}`),
  
  listScenarios: () => 
    request<any>('/v1/twin/scenarios'),
  
  applyDelta: (scenarioId: string, delta: any) => 
    request<any>(`/v1/twin/scenarios/${scenarioId}/apply-delta`, { 
      method: 'POST', 
      body: JSON.stringify(delta) 
    }),
  
  simulate: (scenarioId: string) => 
    request<any>(`/v1/twin/scenarios/${scenarioId}/simulate`, { 
      method: 'POST' 
    }),
  
  solve: (scenarioId: string) => 
    request<any>(`/v1/twin/scenarios/${scenarioId}/solve`, { 
      method: 'POST' 
    }),
  
  compare: (scenarioId: string, baselineId?: string) => {
    const queryParams = baselineId ? `?baseline_id=${baselineId}` : '';
    return request<any>(`/v1/twin/scenarios/${scenarioId}/compare${queryParams}`);
  },
  
  deleteScenario: (scenarioId: string) =>
    request<void>(`/v1/twin/scenarios/${scenarioId}`, { method: 'DELETE' }),
};


// ═══════════════════════════════════════════════════════════════════════════════
// Q.118.J — Alertas proativos do copiloto (GET /v1/copilot/alerts + ack/resolve)
// ═══════════════════════════════════════════════════════════════════════════════

export interface CopilotAlertItem {
  id: string;
  severity: string; // INFO | WARN | CRITICAL
  code: string;
  title: string;
  message_pt: string;
  context: Record<string, unknown>;
  entity_refs: string[];
  status: string; // open | acknowledged | resolved
  created_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved_at: string | null;
}

export const copilotAlertsApi = {
  list: (params?: { status?: string; severity?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.severity) qs.set('severity', params.severity);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<CopilotAlertItem[]>(`/v1/copilot/alerts${suffix}`);
  },
  acknowledge: (alertId: string) =>
    request<CopilotAlertItem>(`/v1/copilot/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
      method: 'POST',
    }),
  resolve: (alertId: string) =>
    request<CopilotAlertItem>(`/v1/copilot/alerts/${encodeURIComponent(alertId)}/resolve`, {
      method: 'POST',
    }),
};
