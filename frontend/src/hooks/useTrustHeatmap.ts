/**
 * useTrustHeatmap — Trust Index v2 heatmap (Sprint Q.1)
 * =====================================================
 *
 * Reads `/v1/dqa/trust-index?scope=factory` and projects the 7 v2 components
 * into the 2D `TrustCell[][]` shape the legacy `<TrustHeatmap>` component
 * expects (rows = scope, columns = component). When the v2 endpoint is
 * unreachable, falls back to a small mock so the dashboard still renders.
 */

import { useEffect, useState, useCallback } from 'react';
import type { TrustCell } from '@/types';
import { dqaApi, type TrustIndexV2Response } from '@/lib/api';

const ROW_LABEL = 'Factory (curated)';

const COLUMN_ORDER: Array<keyof TrustIndexV2Response['components']> = [
  'completeness',
  'validity',
  'freshness',
  'consistency',
  'provenance',
  'anomaly',
  'evidence',
];

const COLUMN_LABELS: Record<keyof TrustIndexV2Response['components'], string> = {
  completeness: 'Completeness',
  validity: 'Validity',
  freshness: 'Freshness',
  consistency: 'Consistency',
  provenance: 'Provenance',
  anomaly: 'Anomaly',
  evidence: 'Evidence',
  causal_coherence: 'Causal Coherence',
  timeliness: 'Timeliness',
};

function v2ToHeatmap(payload: TrustIndexV2Response): TrustCell[][] {
  const row: TrustCell[] = COLUMN_ORDER.map((key) => {
    const raw = payload.components[key];
    const value = typeof raw === 'number' ? raw : 1;
    return {
      entity: ROW_LABEL,
      field: COLUMN_LABELS[key],
      trust_index: Math.round(value * 100),
      coverage_pct: 100,
      null_pct: 0,
      zero_pct: 0,
      impact: [],
      blocked_metrics: [],
      how_to_improve: [],
    };
  });
  return [row];
}

const FALLBACK_HEATMAP: TrustCell[][] = [
  COLUMN_ORDER.map((key) => ({
    entity: ROW_LABEL,
    field: COLUMN_LABELS[key],
    trust_index: 0,
    coverage_pct: 0,
    null_pct: 0,
    zero_pct: 0,
    impact: [],
    blocked_metrics: ['trust_index_v2_unavailable'],
    how_to_improve: ['Verifica /v1/dqa/trust-index?scope=factory'],
  })),
];

export function useTrustHeatmap() {
  const [data, setData] = useState<TrustCell[][]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchHeatmap = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await dqaApi.trustIndex({ scope: 'factory' });
      setData(v2ToHeatmap(payload));
      setError(null);
    } catch (e) {
      setData(FALLBACK_HEATMAP);
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHeatmap();
  }, [fetchHeatmap]);

  return { data, loading, error, refresh: fetchHeatmap };
}

export default useTrustHeatmap;
