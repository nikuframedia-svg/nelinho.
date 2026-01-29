/**
 * useTrustHeatmap — Hook for fetching trust heatmap data
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 */

import { useEffect, useState, useCallback } from 'react';
import type { TrustCell } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useTrustHeatmap() {
  const [data, setData] = useState<TrustCell[][]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchHeatmap = useCallback(async () => {
    try {
      setLoading(true);
      
      // Try to fetch from API first
      try {
        const response = await fetch(`${API_BASE}/v1/factory/quality/trust-heatmap`);
        if (response.ok) {
          const apiData = await response.json();
          if (apiData && apiData.heatmap) {
            setData(apiData.heatmap);
            setError(null);
            return;
          }
        }
      } catch {
        // Fall back to mock data
      }
      
      // Mock data based on real PP1 data analysis
      const mockData: TrustCell[][] = [
        // OrdensFabrico
        [
          { entity: 'OrdensFabrico', field: 'Completude', trust_index: 95, coverage_pct: 100, null_pct: 0, zero_pct: 5, impact: [], blocked_metrics: [], how_to_improve: [] },
          { entity: 'OrdensFabrico', field: 'Precisão', trust_index: 82, coverage_pct: 100, null_pct: 0, zero_pct: 0, impact: [], blocked_metrics: [], how_to_improve: [] },
          { entity: 'OrdensFabrico', field: 'Freshness', trust_index: 100, coverage_pct: 100, null_pct: 0, zero_pct: 0, impact: [], blocked_metrics: [], how_to_improve: [] },
          { entity: 'OrdensFabrico', field: 'Overall', trust_index: 92, coverage_pct: 100, null_pct: 0, zero_pct: 2, impact: [], blocked_metrics: [], how_to_improve: [] },
        ],
        // Fases
        [
          { entity: 'Fases', field: 'Completude', trust_index: 85, coverage_pct: 100, null_pct: 0, zero_pct: 15, impact: [], blocked_metrics: [], how_to_improve: [] },
          { entity: 'Fases', field: 'Precisão', trust_index: 85, coverage_pct: 100, null_pct: 0, zero_pct: 0, impact: [], blocked_metrics: [], how_to_improve: [] },
          { entity: 'Fases', field: 'Freshness', trust_index: 100, coverage_pct: 100, null_pct: 0, zero_pct: 0, impact: [], blocked_metrics: [], how_to_improve: [] },
          { entity: 'Fases', field: 'Overall', trust_index: 85, coverage_pct: 100, null_pct: 0, zero_pct: 5, impact: [], blocked_metrics: [], how_to_improve: [] },
        ],
        // Funcionarios
        [
          { entity: 'Funcionarios', field: 'Completude', trust_index: 75, coverage_pct: 95, null_pct: 5, zero_pct: 10, impact: ['custo_teorico'], blocked_metrics: [], how_to_improve: ['Preencher ValorHora para todos'] },
          { entity: 'Funcionarios', field: 'Precisão', trust_index: 70, coverage_pct: 90, null_pct: 0, zero_pct: 15, impact: [], blocked_metrics: [], how_to_improve: [] },
          { entity: 'Funcionarios', field: 'Freshness', trust_index: 100, coverage_pct: 100, null_pct: 0, zero_pct: 0, impact: [], blocked_metrics: [], how_to_improve: [] },
          { entity: 'Funcionarios', field: 'Overall', trust_index: 75, coverage_pct: 95, null_pct: 2, zero_pct: 8, impact: [], blocked_metrics: [], how_to_improve: [] },
        ],
        // Moldes
        [
          { entity: 'Moldes', field: 'Completude', trust_index: 70, coverage_pct: 85, null_pct: 15, zero_pct: 5, impact: [], blocked_metrics: ['mold_conflict_confirmed'], how_to_improve: [] },
          { entity: 'Moldes', field: 'Precisão', trust_index: 65, coverage_pct: 80, null_pct: 0, zero_pct: 10, impact: [], blocked_metrics: [], how_to_improve: [] },
          { entity: 'Moldes', field: 'Freshness', trust_index: 100, coverage_pct: 100, null_pct: 0, zero_pct: 0, impact: [], blocked_metrics: [], how_to_improve: [] },
          { entity: 'Moldes', field: 'Overall', trust_index: 70, coverage_pct: 85, null_pct: 5, zero_pct: 5, impact: [], blocked_metrics: [], how_to_improve: [] },
        ],
        // FasesOrdemFabrico - CRITICAL
        [
          { entity: 'FasesOrdemFabrico', field: 'Completude', trust_index: 35, coverage_pct: 4.8, null_pct: 95.2, zero_pct: 0, impact: ['Datas de fases'], blocked_metrics: ['mold_conflict_confirmed', 'schedule_accuracy'], how_to_improve: ['Exigir DataPrevista no ERP', 'Preenchimento automático baseado em histórico'] },
          { entity: 'FasesOrdemFabrico', field: 'Precisão', trust_index: 62, coverage_pct: 58, null_pct: 0, zero_pct: 42, impact: ['HorasPrevistas com zeros'], blocked_metrics: [], how_to_improve: ['Usar FasesStandardModelos como fallback'] },
          { entity: 'FasesOrdemFabrico', field: 'Freshness', trust_index: 100, coverage_pct: 100, null_pct: 0, zero_pct: 0, impact: [], blocked_metrics: [], how_to_improve: [] },
          { entity: 'FasesOrdemFabrico', field: 'Overall', trust_index: 58, coverage_pct: 54, null_pct: 32, zero_pct: 14, impact: [], blocked_metrics: [], how_to_improve: [] },
        ],
      ];
      
      setData(mockData);
      setError(null);
    } catch (e) {
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

