/**
 * ProdPlan ONE — API client: infraestrutura partilhada.
 * =====================================================
 *
 * request<T> + retry + circuit-breaker + headers de tenant/user +
 * conversão camelCase→snake_case. Os objectos de API por endpoint vivem em
 * ./index.ts (e, a partir da Fase 2 da campanha Q.60, em ficheiros por
 * domínio) e importam `request`/`filterParams` daqui.
 */
import { getErrorMessage } from '../api-errors';
import { logToEndpoint } from '../logger';
import { getCircuitBreaker } from '../circuit-breaker';

// Q.21.A — porta única. O `.env` de dev usa 8001 e o backend arranca em 8001
// (ver agent_docs/HANDOFF.md §4.7). O fallback aqui tem de concordar com o
// `.env` para que `npm run dev` sem `.env` continue a falar com o backend.
// Build de produção (single-origin atrás de reverse-proxy): sem VITE_API_URL,
// usa a origem de quem serviu a página — agnóstico ao host (Tailscale/Caddy).
export const API_BASE =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8001' : window.location.origin);

// Retry configuration
const MAX_RETRIES = 1; // Reduced from 3 to 1 to avoid flooding console
const RETRYABLE_STATUSES = [502, 504]; // Bad Gateway, Gateway Timeout (NOT 503 - often DB unavailable)
const INITIAL_RETRY_DELAY = 1000; // 1 second

// Retry configuration interface
interface RetryConfig {
  maxRetries?: number;
  retryableStatuses?: number[];
  initialDelay?: number;
}

/**
 * Get retry configuration for a specific endpoint
 * Some endpoints (like health checks) should not retry
 */
function getRetryConfig(endpoint: string): RetryConfig {
  // Health check endpoints should not retry
  if (endpoint === '/health' || endpoint === '/api/health' || endpoint.includes('/health')) {
    return { maxRetries: 0 };
  }
  
  // Database-dependent endpoints should not retry on 503
  // These will fail immediately if PostgreSQL is not running
  if (endpoint.includes('/v1/core/') || 
      endpoint.includes('/v1/plan/') || 
      endpoint.includes('/v1/profit/') ||
      endpoint.includes('/v1/hr/') ||
      endpoint.includes('/v1/supply/')) {
    return { maxRetries: 0 }; // No retry for DB-dependent endpoints
  }
  
  // Default configuration
  return {
    maxRetries: MAX_RETRIES,
    retryableStatuses: RETRYABLE_STATUSES,
    initialDelay: INITIAL_RETRY_DELAY,
  };
}

/**
 * Check if HTTP status is 404 (Not Found)
 * Used to identify when a feature/endpoint is not available
 */
function isNotFoundError(status: number): boolean {
  return status === 404;
}

// Helper to wait for a delay (exponential backoff)
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Helper to show retry toast (if ToastProvider is available)
let toastContext: { info: (msg: string) => string } | null = null;

export function setToastContext(context: { info: (msg: string) => string } | null) {
  toastContext = context;
}

/**
 * Convert a camelCase key to snake_case (employeeId → employee_id).
 *
 * Sprint Q.12 — antes do helper, FastAPI ignorava silenciosamente
 * params como `employeeId` porque esperava `employee_id`, e devolvia a
 * lista completa em vez de filtrada. A conversão fica num único sítio.
 */
const camelToSnake = (key: string): string =>
  key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);

/**
 * Filter out undefined/null values AND convert camelCase keys to
 * snake_case. Single conversion point for both query strings and
 * any other place that builds a backend-facing record.
 */
export const filterParams = (params: Record<string, any> | undefined): Record<string, string> =>
  Object.fromEntries(
    Object.entries(params || {})
      .filter(([_, v]) => v !== undefined && v !== null)
      .map(([k, v]) => [camelToSnake(k), String(v)])
  );

// ═══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

export async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  retryCount = 0
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  
  // Get retry configuration for this endpoint
  const retryConfig = getRetryConfig(endpoint);
  const maxRetries = retryConfig.maxRetries ?? MAX_RETRIES;
  const retryableStatuses = retryConfig.retryableStatuses ?? RETRYABLE_STATUSES;
  const initialDelay = retryConfig.initialDelay ?? INITIAL_RETRY_DELAY;
  
  // Obter token de autenticação do localStorage
  const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
  // Q.18.AUTH — dev tenant default. Backend (Q.12 Onda 0.1) rejeita zero UUID
  // explicitamente (`Invalid tenant: zero UUID is reserved`). 000…001 é a
  // dev tenant seeded por scripts/bootstrap_dev_tenant.py. Ver plano Q.18.AUTH.
  const tenantId = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000001';
  // Several backend endpoints (notably /v1/core/tenants and the governance
  // lifecycle endpoints) call require_user_uuid / require_user_header which
  // 401 when X-User-Id is missing. Use the dev seed user UUID until the
  // JWT-cookie path lands; same fallback as tenant_id above.
  const userId = localStorage.getItem('user_id') || '00000000-0000-0000-0000-000000000001';
  const userRole = localStorage.getItem('user_role') || 'admin';

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  // Adicionar token se existir
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Adicionar tenant + user identity (requeridos pelo backend)
  headers['X-Tenant-Id'] = tenantId;
  headers['X-User-Id'] = userId;
  headers['X-User-Role'] = userRole;

  // Q.61.12 — trace_id end-to-end. crypto.randomUUID e standard em
  // browsers modernos (Chrome 92+, Firefox 95+, Safari 15.4+). Backend
  // middleware extrai, propaga via ContextVar; logs/audit/outbox
  // correlacionam pelo mesmo id. Echo no response (cliente pode
  // tracear no DevTools network).
  if (!headers['X-Request-Id']) {
    headers['X-Request-Id'] =
      typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2) + Date.now().toString(36);
  }
  
  try {
    // Use circuit breaker to prevent cascading failures
    const circuitBreaker = getCircuitBreaker();
    let response: Response;
    
    try {
      response = await circuitBreaker.call(async () => {
        const fetchResponse = await fetch(url, {
          headers,
          ...options,
        });
        // Consider HTTP errors (5xx) as failures for circuit breaker
        if (!fetchResponse.ok && fetchResponse.status >= 500) {
          throw new Error(`HTTP ${fetchResponse.status}: ${fetchResponse.statusText}`);
        }
        return fetchResponse;
      });
    } catch (circuitError: any) {
      // Circuit breaker rejected (circuit is open)
      if (circuitError.message?.includes('Circuit breaker is open')) {
        const errorObj = new Error('Backend indisponível. Circuit breaker está aberto.');
        (errorObj as any).status = 503;
        throw errorObj;
      }
      // Re-throw network errors or HTTP 5xx errors
      throw circuitError;
    }

    if (!response.ok) {
      // 404 errors should not retry - feature may not be available
      if (isNotFoundError(response.status)) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.message || getErrorMessage({ status: 404, response: errorData } as any);
        const errorObj = new Error(errorMessage);
        (errorObj as any).status = 404;
        (errorObj as any).response = errorData;
        (errorObj as any).isFeatureNotAvailable = true; // Flag para identificar
        throw errorObj;
      }
      
      // Check if error is retryable and we haven't exceeded max retries
      if (retryableStatuses.includes(response.status) && retryCount < maxRetries) {
        const retryDelay = initialDelay * Math.pow(2, retryCount); // Exponential backoff
        
        // Show toast notification on first retry
        if (retryCount === 0 && toastContext) {
          toastContext.info(`Serviço temporariamente indisponível. Tentando reconectar em ${retryDelay / 1000}s...`);
        }
        
        // Wait before retrying
        await delay(retryDelay);
        
        // Retry the request
        return request<T>(endpoint, options, retryCount + 1);
      }
      
      // This is a final failure (not retryable or max retries exceeded)
      const isFinalFailure = !retryableStatuses.includes(response.status) || retryCount >= maxRetries;
      
      // Log only final failures
      if (isFinalFailure) {
        logToEndpoint('api.ts', 'response not ok', {
          status: response.status,
          statusText: response.statusText,
          url,
          retryCount,
        }, 'C');
      }
      
      const errorData = await response.json().catch(() => ({}));
      
      // Use Portuguese error messages
      const errorMessage = errorData.detail || errorData.message || getErrorMessage({ status: response.status, response: errorData } as any);
      const errorObj = new Error(errorMessage);
      (errorObj as any).status = response.status;
      (errorObj as any).response = errorData;
      
      // Log only final failures
      if (isFinalFailure) {
        logToEndpoint('api.ts', 'throwing error', {
          errorMessage,
          status: response.status,
          retryCount,
        }, 'C');
      }
      
      throw errorObj;
    }

    return await response.json();
  } catch (error: any) {
    // Network errors or other fetch failures - retry if applicable
    if (retryCount < maxRetries && !error.status) {
      const retryDelay = initialDelay * Math.pow(2, retryCount);
      
      // Show toast notification on first retry
      if (retryCount === 0 && toastContext) {
        toastContext.info(`Erro de ligação. Tentando reconectar em ${retryDelay / 1000}s...`);
      }
      
      await delay(retryDelay);
      return request<T>(endpoint, options, retryCount + 1);
    }
    
    // Log only final network errors (after all retries)
    if (retryCount >= maxRetries) {
      logToEndpoint('api.ts', 'network error after retries', {
        error: error.message,
        retryCount,
        url,
      }, 'C');
    }
    
    throw error;
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Q.21.A — Helper público de fetch
// ═══════════════════════════════════════════════════════════════════════════════
//
// `apiFetch` expõe o `request()` interno para que cada chamada à API passe pelo
// mesmo circuit breaker, política de retry e headers de tenant/user. Chamadas
// `fetch()` directas que saltam isto perdem os três. O endpoint é relativo
// (ex: `/v1/plan/orders/active`) — a base URL vem do `VITE_API_URL`.
//
// `getApiBase()` devolve a base URL só para casos que precisam de um URL cru
// (SSE/EventSource, sondas de saúde) — nunca para reconstruir um `fetch` que
// devia ter passado pelo `apiFetch`.
export { request as apiFetch };

export function getApiBase(): string {
  return API_BASE;
}

