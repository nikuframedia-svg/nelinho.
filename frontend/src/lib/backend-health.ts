/**
 * Backend Health Check System
 * Monitors backend availability and notifies listeners of status changes
 */

import { getApiBase } from './api';

// Health probes deliberately use raw `fetch` (not `apiFetch`): they must NOT
// pass through the circuit breaker — this is the code that *detects* the
// backend being down, so it cannot depend on the breaker being closed.
const API_BASE = getApiBase();

export type BackendStatus = 'online' | 'offline' | 'checking';

let backendStatus: BackendStatus = 'checking';
let statusListeners: Array<(status: BackendStatus) => void> = [];
let toastContext: { error: (msg: string) => string } | null = null;
let hasShownOfflineToast = false;

/**
 * Get current backend status
 */
export function getBackendStatus(): BackendStatus {
  return backendStatus;
}

/**
 * Subscribe to backend status changes
 * Returns unsubscribe function
 */
export function onBackendStatusChange(callback: (status: BackendStatus) => void): () => void {
  statusListeners.push(callback);
  
  // Immediately call with current status
  callback(backendStatus);
  
  // Return unsubscribe function
  return () => {
    statusListeners = statusListeners.filter(cb => cb !== callback);
  };
}

/**
 * Set toast context for showing notifications
 */
export function setBackendHealthToastContext(context: { error: (msg: string) => string } | null) {
  toastContext = context;
}

/**
 * Notify all listeners of status change
 */
function notifyListeners(status: BackendStatus): void {
  const previousStatus = backendStatus;
  backendStatus = status;
  
  // Show toast when backend goes offline (only once)
  if (status === 'offline' && previousStatus !== 'offline' && !hasShownOfflineToast && toastContext) {
    toastContext.error('Backend indisponível. Verifica se o servidor está a correr.');
    hasShownOfflineToast = true;
  }
  
  // Reset toast flag when backend comes back online
  if (status === 'online' && previousStatus === 'offline') {
    hasShownOfflineToast = false;
  }
  
  statusListeners.forEach(cb => cb(status));
}

/**
 * Check backend health by calling health endpoint
 * Tries /health first, then /api/health as fallback
 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    notifyListeners('checking');
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000); // 3s timeout
    
    // Try /health first (backend has /health, not /api/health)
    let response: Response | null = null;
    
    try {
      response = await fetch(`${API_BASE}/health`, {
        method: 'GET',
        signal: controller.signal,
      });
      
      // If 404, try /api/health as fallback
      if (!response.ok && response.status === 404) {
        try {
          const fallbackResponse = await fetch(`${API_BASE}/api/health`, {
            method: 'GET',
            signal: controller.signal,
          });
          if (fallbackResponse.ok) {
            response = fallbackResponse;
          }
        } catch (fallbackError) {
          // Fallback also failed
        }
      }
    } catch (error) {
      // Network error - try fallback
      try {
        response = await fetch(`${API_BASE}/api/health`, {
          method: 'GET',
          signal: controller.signal,
        });
      } catch (fallbackError) {
        // Both failed
      }
    }
    
    clearTimeout(timeoutId);
    
    if (response && response.ok) {
      notifyListeners('online');
      return true;
    } else {
      notifyListeners('offline');
      return false;
    }
  } catch (error) {
    // Network error or timeout
    notifyListeners('offline');
    return false;
  }
}

// Initialize health check in browser environment
if (typeof window !== 'undefined') {
  // Initial check
  checkBackendHealth();
  
  // Periodic check every 30 seconds
  setInterval(() => {
    checkBackendHealth();
  }, 30000);
}

