import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Boxes, Plus, Play, AlertTriangle, Loader2, Trash2, Upload } from 'lucide-react';
import { format } from 'date-fns';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkBadge, DarkIconButton } from '../../components/dark';
import { sandboxApi } from '../../lib/api';
import type { MutationError, MutationPayload } from '../../lib/api-helpers';
import { FormModal, DeleteConfirmDialog, type FormField } from '../../components/ui';
import { useToastContext } from '../../components/ToastProvider';

interface SandboxScenario {
  id: string;
  name?: string;
  description?: string;
  status?: string;
  created_at?: string;
  base_scenario?: string;
  impact?: number;
  changes_count?: number;
}

export function SandboxPage() {
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [simulatingId, setSimulatingId] = useState<string | null>(null);
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: scenarios = [], isLoading, error } = useQuery({
    queryKey: ['sandbox', 'scenarios'],
    queryFn: () => sandboxApi.listScenarios(),
  });

  const filteredScenarios = useMemo(() => {
    if (filterStatus === 'ALL') return scenarios;
    return (scenarios as SandboxScenario[]).filter((s) => s.status ===filterStatus);
  }, [scenarios, filterStatus]);

  const stats = useMemo(() => ({
    total: scenarios.length,
    draft: (scenarios as SandboxScenario[]).filter((s) => s.status ==='DRAFT').length,
    simulated: (scenarios as SandboxScenario[]).filter((s) => s.status ==='SIMULATED').length,
    published: (scenarios as SandboxScenario[]).filter((s) => s.status ==='PUBLISHED').length,
  }), [scenarios]);

  const createMutation = useMutation({
    mutationFn: (data: MutationPayload) => sandboxApi.createScenario(data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['sandbox'] }); setIsCreateModalOpen(false); toast.success('Sandbox created'); },
    onError: (err: MutationError) => toast.error(err.message || 'Error'),
  });

  const simulateMutation = useMutation({
    mutationFn: (id: string) => sandboxApi.simulate(id),
    onMutate: (id) => setSimulatingId(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['sandbox'] }); toast.success('Simulation completed'); },
    onError: (err: MutationError) => toast.error(err.message || 'Simulation failed'),
    onSettled: () => setSimulatingId(null),
  });

  const publishMutation = useMutation({
    mutationFn: (id: string) => sandboxApi.publish(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['sandbox'] }); toast.success('Changes published'); },
    onError: (err: MutationError) => toast.error(err.message || 'Publish failed'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => sandboxApi.deleteScenario ? sandboxApi.deleteScenario(id) : Promise.resolve(),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['sandbox'] }); setIsDeleteModalOpen(false); setDeletingId(null); toast.success('Sandbox deleted'); },
    onError: (err: MutationError) => toast.error(err.message || 'Error'),
  });

  const sandboxFields: FormField[] = [
    { name: 'name', label: 'Sandbox Name', type: 'text', required: true },
    { name: 'description', label: 'Description', type: 'textarea' },
    { name: 'base_scenario', label: 'Base On', type: 'select', options: [
      { value: 'current', label: 'Current Production' },
      { value: 'optimized', label: 'Optimized Schedule' },
    ]},
  ];

  if (error) {
    return (
      <DarkPageLayout title="Sandbox Environment" icon={<Boxes size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading sandboxes</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="Sandbox Environment"
      subtitle="Test changes safely before applying"
      icon={<Boxes size={20} />}
      actions={<DarkButton icon={<Plus size={18} />} onClick={() => setIsCreateModalOpen(true)}>New Sandbox</DarkButton>}
    >
      {/* Info Banner */}
      <DarkCard className="mb-6 bg-blue/10 border-blue/20">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue/20 flex items-center justify-center shrink-0">
            <Boxes size={18} className="text-blue" />
          </div>
          <div>
            <p className="text-sm font-semibold text-blue">Safe Testing Environment</p>
            <p className="text-sm text-text-secondary mt-1">
              Sandboxes allow you to test AI suggestions and manual changes in an isolated environment.
              Simulate the impact before publishing to production.
            </p>
          </div>
        </div>
      </DarkCard>

      <div className="flex items-center gap-4 mb-6">
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'DRAFT', 'SIMULATED', 'PUBLISHED'].map((status) => (
            <DarkPillButton key={status} active={filterStatus === status} onClick={() => setFilterStatus(status)}>{status}</DarkPillButton>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <DarkStatCard icon={<Boxes size={18} />} label="Total" value={stats.total} size="sm" />
        <DarkStatCard icon={<Boxes size={18} />} iconBg="bg-amber/20" label="Draft" value={stats.draft} size="sm" />
        <DarkStatCard icon={<Boxes size={18} />} iconBg="bg-blue/20" label="Simulated" value={stats.simulated} size="sm" />
        <DarkStatCard icon={<Boxes size={18} />} iconBg="bg-success/20" label="Published" value={stats.published} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Sandbox</DarkTableHeader>
                <DarkTableHeader>Created</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
                <DarkTableHeader>Changes</DarkTableHeader>
                <DarkTableHeader align="right">Actions</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredScenarios.map((scenario: SandboxScenario) => (
                <DarkTableRow key={scenario.id}>
                  <DarkTableCell>
                    <div><p className="font-semibold text-text-white">{scenario.name}</p>{scenario.description && <p className="text-xs text-text-tertiary truncate max-w-xs">{scenario.description}</p>}</div>
                  </DarkTableCell>
                  <DarkTableCell className="text-text-tertiary">{scenario.created_at ? format(new Date(scenario.created_at), 'dd/MM/yy HH:mm') : '-'}</DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={scenario.status === 'PUBLISHED' ? 'success' : scenario.status === 'SIMULATED' ? 'info' : 'warning'} dot>
                      {scenario.status || 'DRAFT'}
                    </DarkBadge>
                  </DarkTableCell>
                  <DarkTableCell>{scenario.changes_count || 0} changes</DarkTableCell>
                  <DarkTableCell align="right">
                    <div className="flex items-center justify-end gap-1">
                      <DarkButton 
                        variant="ghost" 
                        size="sm" 
                        icon={simulatingId === scenario.id ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                        onClick={() => simulateMutation.mutate(scenario.id)}
                        disabled={simulatingId === scenario.id}
                      >
                        Simulate
                      </DarkButton>
                      {scenario.status === 'SIMULATED' && (
                        <DarkButton variant="ghost" size="sm" icon={<Upload size={14} />} onClick={() => publishMutation.mutate(scenario.id)}>
                          Publish
                        </DarkButton>
                      )}
                      <DarkIconButton icon={<Trash2 size={16} />} size="sm" variant="ghost" onClick={() => { setDeletingId(scenario.id); setIsDeleteModalOpen(true); }} />
                    </div>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {filteredScenarios.length === 0 && (
                <DarkTableRow><DarkTableCell colSpan={5} className="text-center py-12"><Boxes size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No sandboxes found</p></DarkTableCell></DarkTableRow>
              )}
            </DarkTableBody>
          </DarkTable>
        </DarkCard>
      )}

      <FormModal title="New Sandbox" isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} onSubmit={(data) => createMutation.mutate(data)} fields={sandboxFields} isLoading={createMutation.isPending} />
      <DeleteConfirmDialog isOpen={isDeleteModalOpen} onClose={() => { setIsDeleteModalOpen(false); setDeletingId(null); }} onConfirm={() => { if (deletingId) deleteMutation.mutate(deletingId); }} title="Delete Sandbox" message="Are you sure?" isLoading={deleteMutation.isPending} />
    </DarkPageLayout>
  );
}
