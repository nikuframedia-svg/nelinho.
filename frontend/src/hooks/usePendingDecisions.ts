/**
 * usePendingDecisions — hook reutilizável para decisões PROPOSED.
 *
 * Partilha cache com DecisoesPage (mesma queryKey decisionKeys.list({status:'PROPOSED'})).
 * Polling 5s. Devolve mutations approve + reject com invalidação após sucesso.
 *
 * Q.115.M.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { decisionKeys, planKeys } from '../lib/api/keys';
import { decisionsApi, type DecisionRun } from '../lib/api';

export interface UsePendingDecisionsOptions {
  pollInterval?: number;
  filter?: (d: DecisionRun) => boolean;
}

export interface UsePendingDecisionsResult {
  decisions: DecisionRun[];
  isLoading: boolean;
  error: unknown;
  approveMutation: ReturnType<typeof useMutation<DecisionRun, Error, string>>;
  rejectMutation: ReturnType<typeof useMutation<DecisionRun, Error, string>>;
}

export function usePendingDecisions(
  options: UsePendingDecisionsOptions = {},
): UsePendingDecisionsResult {
  const { pollInterval = 5_000, filter } = options;
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: decisionKeys.list({ status: 'PROPOSED' }),
    queryFn: () => decisionsApi.list({ status: 'PROPOSED', page_size: 50 }),
    refetchInterval: pollInterval,
    refetchOnWindowFocus: false,
  });

  const allDecisions: DecisionRun[] = query.data?.decisions ?? [];
  const decisions = filter ? allDecisions.filter(filter) : allDecisions;

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: decisionKeys.lists() });
    // Q.170.D — aprovar uma decisão de planeamento promove um commit do CPO:
    // invalidar SÓ scheduleCurrent deixava o resto do plano stale (commits,
    // timeline, fases, barcos excluídos…). planKeys.all cobre a árvore toda.
    queryClient.invalidateQueries({ queryKey: planKeys.all });
  };

  const approveMutation = useMutation<DecisionRun, Error, string>({
    mutationFn: (id: string) => decisionsApi.approve(id, { status: 'APPROVED' }),
    onSuccess: invalidate,
  });

  const rejectMutation = useMutation<DecisionRun, Error, string>({
    mutationFn: (id: string) => decisionsApi.approve(id, { status: 'REJECTED' }),
    onSuccess: invalidate,
  });

  return {
    decisions,
    isLoading: query.isLoading,
    error: query.error,
    approveMutation,
    rejectMutation,
  };
}
