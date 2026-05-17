/**
 * useQuarantine — Hook for quarantine command center
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 *
 * ZERO MOCKS: dev and prod both hit the real `/v1/factory/quarantine`
 * endpoint. The only difference is the tenant header. Empty/error
 * states are explicit; never silently substituted with fake rows.
 */

import { useEffect, useState, useCallback } from 'react';
import type { QuarantinedRow } from '@/types';
import { getApiBase } from '@/lib/api';

// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const API_BASE = getApiBase();

interface QuarantineStats {
  critical: number;
  high: number;
  medium: number;
  low: number;
  avgDays: number;
}

function computeStats(rows: QuarantinedRow[]): QuarantineStats {
  const critical = rows.filter(r => r.severity === 'critical').length;
  const high = rows.filter(r => r.severity === 'high').length;
  const medium = rows.filter(r => r.severity === 'medium').length;
  const low = rows.filter(r => r.severity === 'low').length;
  const totalDays = rows.reduce((acc, row) => {
    const days = (Date.now() - new Date(row.detected_at).getTime()) / (24 * 60 * 60 * 1000);
    return acc + days;
  }, 0);
  return {
    critical,
    high,
    medium,
    low,
    avgDays: rows.length > 0 ? totalDays / rows.length : 0,
  };
}

export function useQuarantine() {
  const [rows, setRows] = useState<QuarantinedRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [stats, setStats] = useState<QuarantineStats>({
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    avgDays: 0,
  });

  const fetchQuarantine = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/v1/factory/quarantine`);
      if (!response.ok) {
        throw new Error(
          `Quarantine API returned ${response.status} ${response.statusText}`
        );
      }
      const data = await response.json();
      const rowsArr: QuarantinedRow[] = Array.isArray(data?.rows) ? data.rows : [];
      setRows(rowsArr);
      setStats(computeStats(rowsArr));
      setError(null);
    } catch (e) {
      // Explicit error state. No mock fallback — the UI shows the
      // error and an empty table; we never invent rows that aren't
      // in the database.
      setRows([]);
      setStats({ critical: 0, high: 0, medium: 0, low: 0, avgDays: 0 });
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  const resolveRow = useCallback(async (rowId: string, resolution: {
    type: 'fix' | 'override' | 'discard';
    justification: string;
  }) => {
    const response = await fetch(`${API_BASE}/v1/factory/quarantine/${rowId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(resolution),
    });
    if (!response.ok) {
      throw new Error(
        `Quarantine resolve failed: ${response.status} ${response.statusText}`
      );
    }
    setRows(prev => {
      const next = prev.filter(r => r.id !== rowId);
      setStats(computeStats(next));
      return next;
    });
    return true;
  }, []);

  const autoFix = useCallback(async (rowId: string) => {
    return resolveRow(rowId, { type: 'fix', justification: 'Auto-fix applied' });
  }, [resolveRow]);

  useEffect(() => {
    fetchQuarantine();
  }, [fetchQuarantine]);

  return { rows, stats, loading, error, refresh: fetchQuarantine, resolveRow, autoFix };
}

export default useQuarantine;
