/**
 * useBlockedMetrics — Hook for fetching blocked metrics
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 *
 * ZERO MOCKS: hits the real `/v1/factory/semantic/blocked-metrics`
 * endpoint. The previous implementation hardcoded a list mirroring
 * `src/factory_data_product/config.py`, which silently rotted out of
 * sync whenever the backend list changed and is therefore the kind of
 * fallback the ZERO MOCKS rule explicitly forbids. If the endpoint is
 * not yet implemented, this hook surfaces the API error so consumer
 * pages render an explicit "endpoint missing" empty state.
 */

import { useEffect, useState, useCallback } from 'react';
import type { BlockedMetric } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useBlockedMetrics() {
  const [metrics, setMetrics] = useState<BlockedMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/v1/factory/semantic/blocked-metrics`);
      if (!response.ok) {
        throw new Error(
          `BlockedMetrics API returned ${response.status} ${response.statusText}`
        );
      }
      const data = await response.json();
      const list: BlockedMetric[] = Array.isArray(data?.metrics)
        ? data.metrics
        : Array.isArray(data)
        ? data
        : [];
      setMetrics(list);
      setError(null);
    } catch (e) {
      setMetrics([]);
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  return { metrics, loading, error, refresh: fetchMetrics };
}

export default useBlockedMetrics;
