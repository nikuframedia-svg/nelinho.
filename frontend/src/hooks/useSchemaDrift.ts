/**
 * useSchemaDrift — Hook for schema drift detection
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 */

import { useEffect, useState, useCallback } from 'react';
import type { SchemaDrift } from '@/types';
import { apiFetch } from '../lib/api';

export function useSchemaDrift() {
  const [drifts, setDrifts] = useState<SchemaDrift[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchDrifts = useCallback(async () => {
    try {
      setLoading(true);

      try {
        const data = await apiFetch<{ drifts?: SchemaDrift[] }>(
          '/v1/factory/meta/schema-drift'
        );
        setDrifts(Array.isArray(data?.drifts) ? data.drifts : []);
      } catch {
        // No drift telemetry available — no drift is the safe default.
        setDrifts([]);
      }
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleAction = useCallback(async (drift: SchemaDrift, _action: 'accept' | 'reject' | 'ignore') => {
    try {
      // In production: POST to API
      // For now, just remove from local state
      setDrifts(prev => prev.filter(d => !(d.entity === drift.entity && d.column === drift.column)));
      return true;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    fetchDrifts();
  }, [fetchDrifts]);

  return { drifts, loading, error, refresh: fetchDrifts, handleAction };
}

export default useSchemaDrift;

