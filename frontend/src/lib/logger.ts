/**
 * Logger with endpoint availability check and localStorage fallback
 * Prevents ERR_CONNECTION_REFUSED errors when debug endpoint is unavailable
 * 
 * The debug endpoint (port 7242) is OPTIONAL and used only for telemetry/debug.
 * If unavailable, logs automatically fall back to localStorage.
 */

const DEBUG_ENDPOINT =
  import.meta.env.VITE_DEBUG_ENDPOINT ||
  'http://127.0.0.1:7242/ingest/b36927af-6ca5-4f4b-8938-4f4afe8aa116';

// Check if debug logging is enabled (can be disabled via env var)
// Default to false to avoid errors - only enable if explicitly configured
const DEBUG_LOGGING_ENABLED = import.meta.env.VITE_ENABLE_DEBUG_LOGGING === 'true';

// Cache endpoint availability to avoid repeated checks
let endpointAvailable: boolean | null = null;
let checkPromise: Promise<boolean> | null = null;
let lastCheckTime: number = 0;
const CHECK_CACHE_DURATION = 5 * 60 * 1000; // Cache for 5 minutes

/**
 * Check if the debug endpoint is available
 * Uses cache to avoid repeated checks
 * Returns false immediately if disabled or previously marked unavailable
 */
async function checkEndpointAvailability(): Promise<boolean> {
  // If debug logging is disabled, skip endpoint check
  if (!DEBUG_LOGGING_ENABLED) {
    return false;
  }

  // If we've already determined it's unavailable, don't check again for a while
  if (endpointAvailable === false && Date.now() - lastCheckTime < CHECK_CACHE_DURATION) {
    return false;
  }

  // Return cached result if available and recent
  if (endpointAvailable === true && Date.now() - lastCheckTime < CHECK_CACHE_DURATION) {
    return true;
  }

  // If check is already in progress, wait for it
  if (checkPromise) {
    return checkPromise;
  }

  // Start new availability check - but mark as unavailable immediately if it fails
  checkPromise = (async () => {
    // Mark as checking to prevent multiple simultaneous checks
    endpointAvailable = null;
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        controller.abort();
      }, 300); // Reduced timeout to 300ms

      // Try to fetch with very short timeout
      const fetchPromise = fetch(DEBUG_ENDPOINT, {
        method: 'HEAD',
        signal: controller.signal,
        mode: 'no-cors',
      });

      // Race between fetch and timeout
      await Promise.race([
        fetchPromise,
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('timeout')), 300)
        )
      ]);

      clearTimeout(timeoutId);
      endpointAvailable = true;
      lastCheckTime = Date.now();
      return true;
    } catch (error) {
      // Endpoint is not available - mark as unavailable immediately
      // This prevents future fetch attempts that would show errors in console
      endpointAvailable = false;
      lastCheckTime = Date.now();
      return false;
    } finally {
      checkPromise = null;
    }
  })();

  return checkPromise;
}

/**
 * Log to endpoint with fallback to localStorage
 * Always logs to console, attempts endpoint, falls back to localStorage if needed
 */
export async function logToEndpoint(
  location: string,
  message: string,
  data: any,
  hypothesisId: string
): Promise<void> {
  const logEntry = {
    location,
    message,
    data,
    timestamp: Date.now(),
    sessionId: 'debug-session',
    runId: 'run1',
    hypothesisId,
  };

  // Always log to console in development
  if (import.meta.env.DEV) {
    console.log('[CSP Debug]', logEntry);
  }

  // Skip endpoint if debug logging is disabled
  if (!DEBUG_LOGGING_ENABLED) {
    // Go directly to localStorage fallback
    saveToLocalStorage(logEntry);
    return;
  }

  // Check if endpoint is available (with caching)
  // If unavailable, skip fetch entirely to avoid console errors
  const isAvailable = await checkEndpointAvailability();

  if (!isAvailable) {
    // Endpoint is not available - go directly to localStorage
    saveToLocalStorage(logEntry);
    return;
  }

  // Only try to send if we know it's available
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 500);

    await Promise.race([
      fetch(DEBUG_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(logEntry),
        mode: 'no-cors',
        signal: controller.signal,
      }),
      new Promise((_, reject) => 
        setTimeout(() => reject(new Error('timeout')), 500)
      )
    ]).catch(() => {
      // If fetch fails, mark as unavailable for future attempts
      endpointAvailable = false;
      lastCheckTime = Date.now();
    });

    clearTimeout(timeoutId);
    
    // If still marked as available, success
    if (endpointAvailable === true) {
      return;
    }
  } catch (error) {
    // Endpoint failed, mark as unavailable and fallback
    endpointAvailable = false;
    lastCheckTime = Date.now();
  }

  // Fallback to localStorage
  saveToLocalStorage(logEntry);
}

/**
 * Save log entry to localStorage
 */
function saveToLocalStorage(logEntry: any): void {
  try {
    const existingLogs = localStorage.getItem('debug_logs');
    const logs: any[] = existingLogs ? JSON.parse(existingLogs) : [];
    
    // Add new log
    logs.push(logEntry);
    
    // Keep only last 100 logs
    if (logs.length > 100) {
      logs.shift();
    }
    
    localStorage.setItem('debug_logs', JSON.stringify(logs));
  } catch (e) {
    // Silently ignore localStorage errors (e.g., quota exceeded, disabled)
  }
}
