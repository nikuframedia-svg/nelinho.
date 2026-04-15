import { useState, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { sandboxApi } from '../lib/factoryApi';

export interface SandboxScenario {
  id: string;
  title: string;
  description?: string;
  status: string;
  suggestion_id?: string;
  created_at: string;
  updated_at: string;
  before_state: Record<string, any>;
  after_state?: Record<string, any>;
  impact?: Record<string, any>;
}

export interface SandboxAction {
  action_type: string;
  target?: string;
  params?: Record<string, any>;
}

export interface SandboxResult {
  scenario: SandboxScenario;
  before_state: Record<string, any>;
  after_state?: Record<string, any>;
  impact?: Record<string, any>;
}

export function useSandboxSimulation() {
  const queryClient = useQueryClient();
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(null);

  const scenariosQuery = useQuery<SandboxScenario[]>({
    queryKey: ['sandbox', 'scenarios'],
    queryFn: () => sandboxApi.getScenarios(),
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: (data: { title: string; description?: string; suggestion_id?: string }) =>
      sandboxApi.createScenario(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sandbox', 'scenarios'] });
    },
  });

  const simulateMutation = useMutation({
    mutationFn: ({ id, suggestionType }: { id: string; suggestionType?: string }) =>
      sandboxApi.simulate(id, suggestionType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sandbox', 'scenarios'] });
    },
  });

  const publishMutation = useMutation({
    mutationFn: (id: string) => sandboxApi.publish(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sandbox', 'scenarios'] });
    },
  });

  const createAndSimulate = useCallback(
    async (data: { title: string; description?: string; suggestion_id?: string; suggestionType?: string }) => {
      const scenario = await createMutation.mutateAsync(data);
      setActiveScenarioId(scenario.id);
      const result = await simulateMutation.mutateAsync({
        id: scenario.id,
        suggestionType: data.suggestionType,
      });
      return {
        scenario: result,
        before_state: result.before_state,
        after_state: result.after_state,
        impact: result.impact,
      } as SandboxResult;
    },
    [createMutation, simulateMutation]
  );

  return {
    scenarios: scenariosQuery.data ?? [],
    isLoading: scenariosQuery.isLoading,
    activeScenarioId,
    setActiveScenarioId,
    createScenario: createMutation.mutateAsync,
    simulate: simulateMutation.mutateAsync,
    publish: publishMutation.mutateAsync,
    createAndSimulate,
    isSimulating: simulateMutation.isPending,
    isCreating: createMutation.isPending,
    isPublishing: publishMutation.isPending,
  };
}
