/**
 * API Error handling utilities
 * Provides type-safe error handling for API calls
 */

export class ApiError extends Error {
  status?: number;
  response?: any;
  
  constructor(message: string, status?: number, response?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.response = response;
  }
}

/**
 * Type guard to check if an error is an ApiError
 */
export function isApiError(error: unknown): error is ApiError {
  return (
    error instanceof ApiError ||
    (typeof error === 'object' &&
      error !== null &&
      ('status' in error || 'response' in error))
  );
}

/**
 * Portuguese error messages mapped to HTTP status codes
 */
const ERROR_MESSAGES: Record<number, string> = {
  400: 'Pedido inválido. Verifica os dados enviados.',
  401: 'Sessão expirada. Por favor, faz login novamente.',
  403: 'Não tens permissão para realizar esta ação.',
  404: 'Funcionalidade não disponível. Este módulo pode não estar implementado no backend.',
  409: 'Conflito. O recurso já existe ou foi modificado.',
  422: 'Dados inválidos. Verifica a validação dos campos.',
  429: 'Muitos pedidos. Por favor, aguarda um momento.',
  500: 'Erro interno do servidor. Tenta novamente mais tarde.',
  502: 'Serviço temporariamente indisponível.',
  503: 'Serviço temporariamente indisponível. Verifica se o backend está a correr.',
  504: 'Timeout. O servidor demorou muito a responder.',
};

/**
 * Get user-friendly error message in Portuguese
 */
export function getErrorMessage(error: unknown): string {
  const status = getErrorStatus(error);
  
  // Try to get Portuguese message from status code
  if (status && ERROR_MESSAGES[status]) {
    return ERROR_MESSAGES[status];
  }
  
  // Fallback to error message or response detail
  if (isApiError(error)) {
    // Try to get detail from response
    if (error.response?.detail) {
      return error.response.detail;
    }
    if (error.response?.message) {
      return error.response.message;
    }
    return error.message || 'Ocorreu um erro ao comunicar com o servidor.';
  }
  
  if (error instanceof Error) {
    return error.message;
  }
  
  if (typeof error === 'string') {
    return error;
  }
  
  return 'Ocorreu um erro inesperado.';
}

/**
 * Get actionable suggestions based on error status
 */
export function getErrorSuggestion(error: unknown): string | null {
  const status = getErrorStatus(error);
  
  switch (status) {
    case 401:
      return 'Podes precisar de fazer login novamente.';
    case 403:
      return 'Contacta o administrador se precisares de mais permissões.';
    case 404:
      return 'Esta funcionalidade pode não estar disponível no backend atual. Verifica quais módulos estão implementados.';
    case 422:
      return 'Verifica os campos do formulário e tenta novamente.';
    case 429:
      return 'Aguarda alguns segundos antes de tentar novamente.';
    case 500:
      return 'O problema pode ser temporário. Tenta novamente em alguns momentos.';
    case 502:
      return 'O problema pode ser temporário. Tenta novamente em alguns momentos.';
    case 503:
      // Q.21.A — porta única. Evita importar getApiBase() (criaria ciclo
      // api.ts ↔ api-errors.ts); lê a env directamente com o mesmo fallback.
      return `Verifica se o servidor backend está a correr em ${
        import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'
      }`;
    case 504:
      return 'A ligação pode estar lenta. Verifica a tua ligação à internet.';
    default:
      return null;
  }
}

/**
 * Extract status code from various error types
 */
export function getErrorStatus(error: unknown): number | undefined {
  if (isApiError(error)) {
    return error.status;
  }
  if (typeof error === 'object' && error !== null && 'status' in error) {
    return (error as any).status;
  }
  return undefined;
}

