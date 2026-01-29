/**
 * useToolRegistry — Hook for LLM tool registry management
 * Part of TIER 4: CI/DEVOPS & FUTURE
 */

import { useEffect, useState, useCallback } from 'react';
import type { LLMTool } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useToolRegistry() {
  const [tools, setTools] = useState<LLMTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchTools = useCallback(async () => {
    try {
      setLoading(true);
      
      // Try API first
      try {
        const response = await fetch(`${API_BASE}/v1/copilot/tools`);
        if (response.ok) {
          const data = await response.json();
          if (data && data.tools) {
            setTools(data.tools);
            return;
          }
        }
      } catch {
        // Fall back to mock
      }
      
      // Mock data based on PP1 copilot tools
      const mockTools: LLMTool[] = [
        {
          id: 't-001',
          name: 'Consultar WIP',
          function_name: 'get_wip',
          description: 'Obtém o Work in Progress teórico actual',
          category: 'query',
          risk_level: 'low',
          enabled: true,
          requires_approval: false,
          usage_count: 234,
        },
        {
          id: 't-002',
          name: 'Consultar Gargalos',
          function_name: 'get_bottlenecks',
          description: 'Lista as fases com maior backlog relativo',
          category: 'query',
          risk_level: 'low',
          enabled: true,
          requires_approval: false,
          usage_count: 189,
        },
        {
          id: 't-003',
          name: 'Risco de Competências',
          function_name: 'get_skills_risk',
          description: 'Identifica fases com poucos funcionários aptos',
          category: 'query',
          risk_level: 'low',
          enabled: true,
          requires_approval: false,
          usage_count: 156,
        },
        {
          id: 't-004',
          name: 'Criar Cenário',
          function_name: 'create_scenario',
          description: 'Cria um novo cenário no Digital Twin',
          category: 'simulation',
          risk_level: 'medium',
          enabled: true,
          requires_approval: false,
          usage_count: 78,
        },
        {
          id: 't-005',
          name: 'Aplicar Delta',
          function_name: 'apply_delta',
          description: 'Aplica uma mudança a um cenário existente',
          category: 'simulation',
          risk_level: 'medium',
          enabled: true,
          requires_approval: false,
          usage_count: 45,
        },
        {
          id: 't-006',
          name: 'Criar Decisão',
          function_name: 'create_decision',
          description: 'Cria uma nova decisão no ledger',
          category: 'action',
          risk_level: 'high',
          enabled: true,
          requires_approval: true,
          usage_count: 23,
        },
        {
          id: 't-007',
          name: 'Executar Runbook',
          function_name: 'execute_runbook',
          description: 'Executa um runbook automatizado',
          category: 'action',
          risk_level: 'high',
          enabled: true,
          requires_approval: true,
          usage_count: 12,
        },
        {
          id: 't-008',
          name: 'Rollback Ingestion',
          function_name: 'rollback_ingestion',
          description: 'Reverte para uma ingestion anterior',
          category: 'admin',
          risk_level: 'high',
          enabled: false,
          requires_approval: true,
          usage_count: 2,
        },
        {
          id: 't-009',
          name: 'Forçar Activação',
          function_name: 'force_activation',
          description: 'Activa uma ingestion ignorando quality gates',
          category: 'admin',
          risk_level: 'high',
          enabled: false,
          requires_approval: true,
          usage_count: 0,
        },
      ];
      
      setTools(mockTools);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  const updateTool = useCallback(async (toolId: string, updates: Partial<LLMTool>): Promise<boolean> => {
    try {
      // In production: PATCH to API
      setTools(prev => prev.map(tool => 
        tool.id === toolId ? { ...tool, ...updates } : tool
      ));
      return true;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    fetchTools();
  }, [fetchTools]);

  return { tools, loading, error, refresh: fetchTools, updateTool };
}

export default useToolRegistry;

