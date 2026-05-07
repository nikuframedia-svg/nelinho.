/**
 * useCoverageAnalysis — Hook for table coverage analysis
 * Part of TIER 3: ENTERPRISE EXCELLENCE
 *
 * ZERO MOCKS: hits the real `/v1/factory/semantic/coverage` endpoint.
 * The previous implementation hardcoded a fixed snapshot of one tenant's
 * tables, which silently rotted whenever ingestion changed and is the
 * exact pattern the ZERO MOCKS rule forbids. Empty/error states are
 * explicit; never silently substituted with fake rows.
 */

import { useEffect, useState, useCallback } from 'react';
import type { TableCoverage } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useCoverageAnalysis() {
  const [coverage, setCoverage] = useState<TableCoverage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchCoverage = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/v1/factory/semantic/coverage`);
      if (!response.ok) {
        throw new Error(
          `Coverage API returned ${response.status} ${response.statusText}`
        );
      }
      const data = await response.json();
      const list: TableCoverage[] = Array.isArray(data?.tables)
        ? data.tables
        : Array.isArray(data)
        ? data
        : [];
      setCoverage(list);
      setError(null);
    } catch (e) {
      setCoverage([]);
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCoverage();
  }, [fetchCoverage]);

  return { coverage, loading, error, refresh: fetchCoverage };
}

export default useCoverageAnalysis;
