/**
 * Circuit Breaker Pattern Implementation
 * Prevents cascading failures by stopping requests when backend is consistently failing
 */

export type CircuitState = 'closed' | 'open' | 'half-open';

export interface CircuitBreakerConfig {
  failureThreshold: number; // Number of failures before opening circuit
  timeout: number; // Time in ms before trying half-open
  halfOpenMaxCalls: number; // Max calls in half-open state before deciding
}

const DEFAULT_CONFIG: CircuitBreakerConfig = {
  failureThreshold: 5,
  timeout: 20000, // Q.144.D — 20s (era 60s): recupera mais depressa de um blip
  halfOpenMaxCalls: 3,
};

export class CircuitBreaker {
  private state: CircuitState = 'closed';
  private failureCount = 0;
  private lastFailureTime: number | null = null;
  private halfOpenCalls = 0;
  private config: CircuitBreakerConfig;

  constructor(config: Partial<CircuitBreakerConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Execute a function with circuit breaker protection
   */
  async call<T>(fn: () => Promise<T>): Promise<T> {
    // Check if circuit should transition from open to half-open
    if (this.state === 'open') {
      if (this.lastFailureTime && Date.now() - this.lastFailureTime >= this.config.timeout) {
        this.state = 'half-open';
        this.halfOpenCalls = 0;
      } else {
        // Circuit is still open, reject immediately
        throw new Error('Circuit breaker is open. Backend is unavailable.');
      }
    }

    try {
      // Execute the function
      const result = await fn();
      
      // Success - reset failure count and close circuit if it was half-open
      if (this.state === 'half-open') {
        this.state = 'closed';
        this.failureCount = 0;
        this.halfOpenCalls = 0;
      } else if (this.state === 'closed') {
        // Reset failure count on success
        this.failureCount = 0;
      }
      
      return result;
    } catch (error) {
      // Failure - increment failure count
      this.failureCount++;
      this.lastFailureTime = Date.now();

      // Check if we should open the circuit
      if (this.state === 'closed' && this.failureCount >= this.config.failureThreshold) {
        this.state = 'open';
      } else if (this.state === 'half-open') {
        // If half-open and it fails, go back to open
        this.halfOpenCalls++;
        if (this.halfOpenCalls >= this.config.halfOpenMaxCalls) {
          this.state = 'open';
        }
      }

      throw error;
    }
  }

  /**
   * Get current circuit state
   */
  getState(): CircuitState {
    return this.state;
  }

  /**
   * Manually reset the circuit breaker
   */
  reset(): void {
    this.state = 'closed';
    this.failureCount = 0;
    this.lastFailureTime = null;
    this.halfOpenCalls = 0;
  }
}

// Global circuit breaker instance (can be shared across the app)
let globalCircuitBreaker: CircuitBreaker | null = null;

/**
 * Get or create global circuit breaker instance
 */
export function getCircuitBreaker(): CircuitBreaker {
  if (!globalCircuitBreaker) {
    globalCircuitBreaker = new CircuitBreaker();
  }
  return globalCircuitBreaker;
}

/**
 * Reset global circuit breaker
 */
export function resetCircuitBreaker(): void {
  if (globalCircuitBreaker) {
    globalCircuitBreaker.reset();
  }
}








