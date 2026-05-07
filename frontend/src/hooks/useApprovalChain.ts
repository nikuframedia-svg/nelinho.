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

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
      const response = await fetch(
        `${API_BASE}/v1/governance/decisions/${decisionId}/approval-chain`
      );
      if (!response.ok) {
        throw new Error(
          `Approval-chain API returned ${response.status} ${response.statusText}`
        );
      }
      const data = await response.json();
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
    const response = await fetch(
      `${API_BASE}/v1/governance/decisions/${decisionId}/approval-chain/${stepId}/approve`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment }),
      }
    );
    if (!response.ok) {
      throw new Error(`Approve failed: ${response.status} ${response.statusText}`);
    }
    setApprovalChain(prev => prev.map(step =>
      step.id === stepId
        ? { ...step, status: 'approved' as const, comment, decided_at: new Date().toISOString() }
        : step
    ));
    return true;
  }, [decisionId]);

  const reject = useCallback(async (stepId: string, comment: string): Promise<boolean> => {
    const response = await fetch(
      `${API_BASE}/v1/governance/decisions/${decisionId}/approval-chain/${stepId}/reject`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment }),
      }
    );
    if (!response.ok) {
      throw new Error(`Reject failed: ${response.status} ${response.statusText}`);
    }
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
