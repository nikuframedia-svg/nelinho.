/**
 * useLiveKPIs — Hook for real-time KPI data with auto-refresh
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 * 
 * "O Dashboard não é uma página — é o batimento cardíaco da fábrica."
 */

import { useEffect, useState, useCallback } from 'react';
import { factoryApi } from '@/lib/factoryApi';
import type { ExplainedValue } from '@/types';

export interface LiveKPIs {
  wip: ExplainedValue | null;
  backlogHours: ExplainedValue | null;
  bottlenecks: ExplainedValue[] | null;
  qualityRate: ExplainedValue | null;
  skillsRisk: ExplainedValue | null;
  lastUpdate: Date;
  isStale: boolean;
}

interface UseLiveKPIsOptions {
  refreshInterval?: number;
  enabled?: boolean;
}

export function useLiveKPIs(options: UseLiveKPIsOptions = {}) {
  const { refreshInterval = 30000, enabled = true } = options;
  
  const [kpis, setKPIs] = useState<LiveKPIs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchKPIs = useCallback(async () => {
    if (!enabled) return;
    
    try {
      const [wip, backlog, bottlenecks, quality, skills] = await Promise.all([
        factoryApi.getWIP().catch(() => null),
        factoryApi.getBacklog().catch(() => null),
        factoryApi.getBottlenecks().catch(() => null),
        factoryApi.getQuality().catch(() => null),
        factoryApi.getSkillsRisk().catch(() => null),
      ]);

      // Transform API responses to ExplainedValue format
      const transformToExplainedValue = (data: unknown, defaults: Partial<ExplainedValue>): ExplainedValue | null => {
        if (!data) return null;
        
        // If already in ExplainedValue format
        if (typeof data === 'object' && data !== null && 'value' in data) {
          return data as ExplainedValue;
        }
        
        // If it's a simple value, wrap it
        if (typeof data === 'object' && data !== null && 'total' in data) {
          const d = data as Record<string, unknown>;
          return {
            value: d.total as number,
            formatted_value: String(d.total),
            unit: defaults.unit || 'count',
            semantic_label: defaults.semantic_label || '',
            semantic_kind: 'theoretical',
            trust_index: (d.trust_index as number) || 75,
            coverage_pct: 100,
            lineage: {
              sources: [],
              transformations: [],
              computation_timestamp: new Date().toISOString(),
            },
            explanation: {
              what: defaults.semantic_label || '',
              how: 'Calculated from factory data',
              assumptions: [],
              forbidden_claims: [],
              how_to_improve: [],
            },
          };
        }
        
        return null;
      };

      setKPIs({
        wip: transformToExplainedValue(wip, { 
          semantic_label: 'WIP Teórico', 
          unit: 'ordens' 
        }),
        backlogHours: transformToExplainedValue(backlog, { 
          semantic_label: 'Backlog Total', 
          unit: 'horas' 
        }),
        bottlenecks: bottlenecks ? (Array.isArray(bottlenecks) ? bottlenecks : []) : null,
        qualityRate: transformToExplainedValue(quality, { 
          semantic_label: 'Taxa de Erros', 
          unit: '%' 
        }),
        skillsRisk: transformToExplainedValue(skills, { 
          semantic_label: 'Risco de Competências', 
          unit: 'fases' 
        }),
        lastUpdate: new Date(),
        isStale: false,
      });
      setError(null);
    } catch (e) {
      setError(e as Error);
      if (kpis) {
        setKPIs({ ...kpis, isStale: true });
      }
    } finally {
      setLoading(false);
    }
  }, [enabled, kpis]);

  useEffect(() => {
    fetchKPIs();
    
    if (enabled && refreshInterval > 0) {
      const interval = setInterval(fetchKPIs, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchKPIs, refreshInterval, enabled]);

  return { kpis, loading, error, refresh: fetchKPIs };
}

export default useLiveKPIs;

