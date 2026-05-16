/**
 * useApprovalChain — Hook for multi-level approval chains
 * Part of TIER 3: ENTERPRISE EXCELLENCE
 *
 * ZERO MOCKS: real `/v1/governance/decisions/:id/approval-chain` endpoint.
 * Empty/error states explicit. approve()/reject() POST to the backend
 * and only mutate local state after the server confirms the change.
 */

import { useEffect, useState, useCallback } from 'react';
import type { ApprovalStep } from '@/types';
import { apiFetch } from '../lib/api';

export function useApprovalChain(decisionId: string) {
  const [approvalChain, setApprovalChain] = useState<ApprovalStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchChain = useCallback(async () => {
    if (!decisionId) {
      setApprovalChain([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await apiFetch<{ chain?: ApprovalStep[] }>(
        `/v1/governance/decisions/${decisionId}/approval-chain`
      );
      const chain: ApprovalStep[] = Array.isArray(data?.chain) ? data.chain : [];
      setApprovalChain(chain);
      setError(null);
    } catch (e) {
      setApprovalChain([]);
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, [decisionId]);

  const approve = useCallback(async (stepId: string, comment?: string): Promise<boolean> => {
    await apiFetch<unknown>(
      `/v1/governance/decisions/${decisionId}/approval-chain/${stepId}/approve`,
      { method: 'POST', body: JSON.stringify({ comment }) }
    );
    setApprovalChain(prev => prev.map(step =>
      step.id === stepId
        ? { ...step, status: 'approved' as const, comment, decided_at: new Date().toISOString() }
        : step
    ));
    return true;
  }, [decisionId]);

  const reject = useCallback(async (stepId: string, comment: string): Promise<boolean> => {
    await apiFetch<unknown>(
      `/v1/governance/decisions/${decisionId}/approval-chain/${stepId}/reject`,
      { method: 'POST', body: JSON.stringify({ comment }) }
    );
    setApprovalChain(prev => prev.map(step =>
      step.id === stepId
        ? { ...step, status: 'rejected' as const, comment, decided_at: new Date().toISOString() }
        : step
    ));
    return true;
  }, [decisionId]);

  useEffect(() => {
    fetchChain();
  }, [fetchChain]);

  return { approvalChain, loading, error, refresh: fetchChain, approve, reject };
}

export default useApprovalChain;
