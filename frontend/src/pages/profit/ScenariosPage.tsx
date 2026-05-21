import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Beaker, Plus, Play, AlertTriangle, Loader2, Trash2, Eye } from 'lucide-react';
import { format } from 'date-fns';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkBadge, DarkIconButton } from '../../components/dark';
import { scenariosApi } from '../../lib/api';
import type { MutationError, MutationPayload } from '../../lib/api-helpers';
import { FormModal, DeleteConfirmDialog, type FormField } from '../../components/ui';
import { useToastContext } from '../../components/ToastProvider';

interface ScenarioLite {
  id: string;
  name?: string;
  description?: string;
  type?: string;
  status?: string;
  created_at?: string;
  impact?: number;
  [key: string]: unknown;
}

export function ScenariosPage() {
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [simulatingId, setSimulatingId] = useState<string | null>(null);
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: scenarios = [], isLoading, error } = useQuery({
    queryKey: ['scenarios', 'list'],
    queryFn: () => scenariosApi.list(),
  });

  const filteredScenarios = useMemo(() => {
    if (filterStatus === 'ALL') return scenarios;
    return (scenarios as ScenarioLite[]).filter((s) => s.status ===filterStatus);
  }, [scenarios, filterStatus]);

  const stats = useMemo(() => ({
    total: scenarios.length,
    draft: (scenarios as ScenarioLite[]).filter((s) => s.status ==='DRAFT').length,
    simulated: (scenarios as ScenarioLite[]).filter((s) => s.status ==='SIMULATED').length,
    applied: (scenarios as ScenarioLite[]).filter((s) => s.status ==='APPLIED').length,
  }), [scenarios]);

  const createMutation = useMutation({
    mutationFn: (data: MutationPayload) => scenariosApi.create(data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['scenarios'] }); setIsCreateModalOpen(false); toast.success('Scenario created'); },
    onError: (err: MutationError) => toast.error(err.message || 'Error'),
  });

  const simulateMutation = useMutation({
    mutationFn: (id: string) => scenariosApi.simulate({ base_order_id: id }),
    onMutate: (id) => setSimulatingId(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['scenarios'] }); toast.success('Simulation completed'); },
    onError: (err: MutationError) => toast.error(err.message || 'Simulation failed'),
    onSettled: () => setSimulatingId(null),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => scenariosApi.delete(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['scenarios'] }); setIsDeleteModalOpen(false); setDeletingId(null); toast.success('Scenario deleted'); },
    onError: (err: MutationError) => toast.error(err.message || 'Error'),
  });

  const scenarioFields: FormField[] = [
    { name: 'name', label: 'Scenario Name', type: 'text', required: true },
    { name: 'description', label: 'Description', type: 'textarea' },
    { name: 'type', label: 'Type', type: 'select', required: true, options: [
      { value: 'WHAT_IF', label: 'What-If Analysis' },
      { value: 'OPTIMIZATION', label: 'Optimization' },
      { value: 'FORECAST', label: 'Forecast' },
    ]},
  ];

  if (error) {
    return (
      <DarkPageLayout title="Scenario Simulation" icon={<Beaker size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading scenarios</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="Scenario Simulation"
      subtitle={isLoading ? 'Loading...' : `${scenarios.length} scenarios`}
      icon={<Beaker size={20} />}
      actions={<DarkButton icon={<Plus size={18} />} onClick={() => setIsCreateModalOpen(true)}>New Scenario</DarkButton>}
    >
      <div className="flex items-center gap-4 mb-6">
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'DRAFT', 'SIMULATED', 'APPLIED'].map((status) => (
            <DarkPillButton key={status} active={filterStatus === status} onClick={() => setFilterStatus(status)}>{status}</DarkPillButton>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <DarkStatCard icon={<Beaker size={18} />} label="Total" value={stats.total} size="sm" />
        <DarkStatCard icon={<Beaker size={18} />} iconBg="bg-amber/20" label="Draft" value={stats.draft} size="sm" />
        <DarkStatCard icon={<Beaker size={18} />} iconBg="bg-blue/20" label="Simulated" value={stats.simulated} size="sm" />
        <DarkStatCard icon={<Beaker size={18} />} iconBg="bg-success/20" label="Applied" value={stats.applied} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Scenario</DarkTableHeader>
                <DarkTableHeader>Type</DarkTableHeader>
                <DarkTableHeader>Created</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
                <DarkTableHeader>Impact</DarkTableHeader>
                <DarkTableHeader align="right">Actions</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredScenarios.map((scenario: ScenarioLite) => (
                <DarkTableRow key={scenario.id}>
                  <DarkTableCell>
                    <div><p className="font-semibold text-text-white">{scenario.name}</p>{scenario.description && <p className="text-xs text-text-tertiary truncate max-w-xs">{scenario.description}</p>}</div>
                  </DarkTableCell>
                  <DarkTableCell><DarkBadge variant="info">{scenario.type || 'WHAT_IF'}</DarkBadge></DarkTableCell>
                  <DarkTableCell className="text-text-tertiary">{scenario.created_at ? format(new Date(scenario.created_at), 'dd/MM/yy HH:mm') : '-'}</DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={scenario.status === 'APPLIED' ? 'success' : scenario.status === 'SIMULATED' ? 'info' : 'warning'} dot>
                      {scenario.status || 'DRAFT'}
                    </DarkBadge>
                  </DarkTableCell>
                  <DarkTableCell mono className={(scenario.impact ?? 0) > 0 ? 'text-success' : (scenario.impact ?? 0) < 0 ? 'text-danger' : 'text-text-tertiary'}>
                    {scenario.impact ? `${scenario.impact > 0 ? '+' : ''}${scenario.impact.toFixed(1)}%` : '-'}
                  </DarkTableCell>
                  <DarkTableCell align="right">
                    <div className="flex items-center justify-end gap-1">
                      <DarkIconButton icon={<Eye size={16} />} size="sm" variant="ghost" title="View" />
                      <DarkButton 
                        variant="ghost" 
                        size="sm" 
                        icon={simulatingId === scenario.id ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                        onClick={() => simulateMutation.mutate(scenario.id)}
                        disabled={simulatingId === scenario.id || scenario.status === 'APPLIED'}
                      >
                        Simulate
                      </DarkButton>
                      <DarkIconButton icon={<Trash2 size={16} />} size="sm" variant="ghost" onClick={() => { setDeletingId(scenario.id); setIsDeleteModalOpen(true); }} />
                    </div>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {filteredScenarios.length === 0 && (
                <DarkTableRow><DarkTableCell colSpan={6} className="text-center py-12"><Beaker size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No scenarios found</p></DarkTableCell></DarkTableRow>
              )}
            </DarkTableBody>
          </DarkTable>
        </DarkCard>
      )}

      <FormModal title="New Scenario" isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} onSubmit={(data) => createMutation.mutate(data)} fields={scenarioFields} isLoading={createMutation.isPending} />
      <DeleteConfirmDialog isOpen={isDeleteModalOpen} onClose={() => { setIsDeleteModalOpen(false); setDeletingId(null); }} onConfirm={() => { if (deletingId) deleteMutation.mutate(deletingId); }} title="Delete Scenario" message="Are you sure?" isLoading={deleteMutation.isPending} />
    </DarkPageLayout>
  );
}
