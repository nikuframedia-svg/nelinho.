/**
 * useApprovalChain — Hook for multi-level approval chains
 * Part of TIER 3: ENTERPRISE EXCELLENCE
 */

import { useEffect, useState, useCallback } from 'react';
import type { ApprovalStep } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useApprovalChain(decisionId: string) {
  const [approvalChain, setApprovalChain] = useState<ApprovalStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchChain = useCallback(async () => {
    if (!decisionId) return;
    
    try {
      setLoading(true);
      
      // Try API first
      try {
        const response = await fetch(`${API_BASE}/api/v1/governance/decisions/${decisionId}/approval-chain`);
        if (response.ok) {
          const data = await response.json();
          if (data && data.chain) {
            setApprovalChain(data.chain);
            return;
          }
        }
      } catch {
        // Fall back to mock
      }
      
      // Mock data
      const mockChain: ApprovalStep[] = [
        {
          id: 'step-1',
          approver: {
            id: 'u1',
            name: 'Ana Silva',
            role: 'Chefe de Produção',
            avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Ana',
          },
          status: 'approved',
          comment: 'Aprovado. Impacto positivo na capacidade.',
          decided_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          can_approve: false,
        },
        {
          id: 'step-2',
          approver: {
            id: 'u2',
            name: 'João Costa',
            role: 'Director Industrial',
            avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Joao',
          },
          status: 'pending',
          can_approve: true,
        },
        {
          id: 'step-3',
          approver: {
            id: 'u3',
            name: 'Maria Santos',
            role: 'CFO',
            avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Maria',
          },
          status: 'pending',
          can_approve: false,
        },
      ];
      
      setApprovalChain(mockChain);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [decisionId]);

  const approve = useCallback(async (stepId: string, comment?: string): Promise<boolean> => {
    try {
      // In production: POST to API
      setApprovalChain(prev => prev.map(step => 
        step.id === stepId 
          ? { ...step, status: 'approved' as const, comment, decided_at: new Date().toISOString() }
          : step
      ));
      return true;
    } catch {
      return false;
    }
  }, []);

  const reject = useCallback(async (stepId: string, comment: string): Promise<boolean> => {
    try {
      // In production: POST to API
      setApprovalChain(prev => prev.map(step => 
        step.id === stepId 
          ? { ...step, status: 'rejected' as const, comment, decided_at: new Date().toISOString() }
          : step
      ));
      return true;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    fetchChain();
  }, [fetchChain]);

  return { approvalChain, loading, error, refresh: fetchChain, approve, reject };
}

export default useApprovalChain;

