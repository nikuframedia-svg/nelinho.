/**
 * useRunbooks — Hook for runbook gallery
 * Part of TIER 3: ENTERPRISE EXCELLENCE
 */

import { useEffect, useState, useCallback } from 'react';
import type { Runbook } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useRunbooks() {
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchRunbooks = useCallback(async () => {
    try {
      setLoading(true);
      
      // Try API first
      try {
        const response = await fetch(`${API_BASE}/api/copilot/runbooks`);
        if (response.ok) {
          const data = await response.json();
          if (data && data.runbooks) {
            setRunbooks(data.runbooks);
            return;
          }
        }
      } catch {
        // Fall back to mock
      }
      
      // Mock data
      const mockRunbooks: Runbook[] = [
        {
          id: 'rb-001',
          name: 'Alerta de Gargalo Crítico',
          description: 'Notifica supervisores quando uma fase atinge >80% de capacidade teórica',
          trigger_type: 'event',
          steps: [
            { id: 's1', name: 'Verificar backlog', action_type: 'query', parameters: { metric: 'backlog_by_phase' }, order: 1 },
            { id: 's2', name: 'Calcular utilização', action_type: 'compute', parameters: { formula: 'backlog/capacity' }, order: 2 },
            { id: 's3', name: 'Enviar alerta', action_type: 'notify', parameters: { channel: 'slack', priority: 'high' }, order: 3 },
          ],
          execution_count: 47,
          last_executed: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          category: 'Capacidade',
        },
        {
          id: 'rb-002',
          name: 'Cross-Training Automático',
          description: 'Sugere cross-training quando uma fase tem menos de 2 funcionários aptos',
          trigger_type: 'scheduled',
          steps: [
            { id: 's1', name: 'Verificar aptidões', action_type: 'query', parameters: { metric: 'skills_risk' }, order: 1 },
            { id: 's2', name: 'Identificar candidatos', action_type: 'compute', parameters: {}, order: 2 },
            { id: 's3', name: 'Criar sugestão', action_type: 'create_decision', parameters: { type: 'training' }, order: 3 },
          ],
          execution_count: 12,
          last_executed: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
          category: 'Workforce',
        },
        {
          id: 'rb-003',
          name: 'Qualidade Diária',
          description: 'Resumo diário de erros de qualidade e fases culpadas',
          trigger_type: 'scheduled',
          steps: [
            { id: 's1', name: 'Buscar erros', action_type: 'query', parameters: { metric: 'quality_errors' }, order: 1 },
            { id: 's2', name: 'Agregar por fase', action_type: 'compute', parameters: {}, order: 2 },
            { id: 's3', name: 'Gerar relatório', action_type: 'report', parameters: { format: 'pdf' }, order: 3 },
            { id: 's4', name: 'Enviar por email', action_type: 'notify', parameters: { channel: 'email' }, order: 4 },
          ],
          execution_count: 156,
          last_executed: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
          category: 'Qualidade',
        },
        {
          id: 'rb-004',
          name: 'Detecção de Conflito de Moldes',
          description: 'Verifica diariamente conflitos potenciais de moldes',
          trigger_type: 'scheduled',
          steps: [
            { id: 's1', name: 'Buscar ordens pendentes', action_type: 'query', parameters: {}, order: 1 },
            { id: 's2', name: 'Verificar moldes', action_type: 'compute', parameters: {}, order: 2 },
            { id: 's3', name: 'Alertar se conflito', action_type: 'notify', parameters: {}, order: 3 },
          ],
          execution_count: 89,
          category: 'Alertas',
        },
      ];
      
      setRunbooks(mockRunbooks);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  const executeRunbook = useCallback(async (runbookId: string): Promise<boolean> => {
    try {
      // In production: POST to API
      console.log(`Executing runbook ${runbookId}`);
      return true;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    fetchRunbooks();
  }, [fetchRunbooks]);

  return { runbooks, loading, error, refresh: fetchRunbooks, executeRunbook };
}

export default useRunbooks;

