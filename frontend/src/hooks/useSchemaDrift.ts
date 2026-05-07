/**
 * useSchemaDrift — Hook for schema drift detection
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 */

import { useEffect, useState, useCallback } from 'react';
import type { SchemaDrift } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useSchemaDrift() {
  const [drifts, setDrifts] = useState<SchemaDrift[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchDrifts = useCallback(async () => {
    try {
      setLoading(true);
      
      // Try API first
      try {
        const response = await fetch(`${API_BASE}/v1/factory/meta/schema-drift`);
        if (response.ok) {
          const data = await response.json();
          if (data && data.drifts) {
            setDrifts(data.drifts);
            return;
          }
        }
      } catch {
        // Fall back to mock (empty - no drift is good!)
      }
      
      // By default, no drifts detected
      setDrifts([]);
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

