import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Cpu, Plus, Play, AlertTriangle, Loader2, Trash2, GitCompare, Copy, Hash, X, Sparkles } from 'lucide-react';
import { format } from 'date-fns';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkBadge, DarkIconButton } from '../../components/dark';
import { twinApi } from '../../lib/api';
import { FormModal, DeleteConfirmDialog, type FormField } from '../../components/ui';
import { useToastContext } from '../../components/ToastProvider';
import { BlockedMetricsNotice } from '../../components/capabilities';
import { ScenarioDiffViewer } from '../../components/twin';

// PALANTIR-LEVEL COMPONENTS
import { ScenarioTemplatesGallery, ModuleErrorBoundary } from '../../components/palantir';

export function TwinPage() {
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [simulatingId, setSimulatingId] = useState<string | null>(null);
  const [compareScenario, setCompareScenario] = useState<any | null>(null);
  const [showTemplates, setShowTemplates] = useState(false);
  const [, setSelectedTemplate] = useState<any | null>(null);
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: scenarios = [], isLoading, error } = useQuery({
    queryKey: ['twin', 'scenarios'],
    queryFn: () => twinApi.listScenarios(),
  });

  const filteredScenarios = useMemo(() => {
    if (filterStatus === 'ALL') return scenarios;
    return scenarios.filter((s: any) => s.status === filterStatus);
  }, [scenarios, filterStatus]);

  const stats = useMemo(() => ({
    total: scenarios.length,
    draft: scenarios.filter((s: any) => s.status === 'DRAFT').length,
    simulated: scenarios.filter((s: any) => s.status === 'SIMULATED').length,
    solved: scenarios.filter((s: any) => s.status === 'SOLVED').length,
  }), [scenarios]);

  const createMutation = useMutation({
    mutationFn: (data: any) => twinApi.createScenario(data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['twin'] }); setIsCreateModalOpen(false); toast.success('Scenario created'); },
    onError: (err: any) => toast.error(err.message || 'Error'),
  });

  const simulateMutation = useMutation({
    mutationFn: (id: string) => twinApi.simulate(id),
    onMutate: (id) => setSimulatingId(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['twin'] }); toast.success('Simulation completed'); },
    onError: (err: any) => toast.error(err.message || 'Simulation failed'),
    onSettled: () => setSimulatingId(null),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => twinApi.deleteScenario(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['twin'] }); setIsDeleteModalOpen(false); setDeletingId(null); toast.success('Scenario deleted'); },
    onError: (err: any) => toast.error(err.message || 'Error'),
  });

  const scenarioFields: FormField[] = [
    { name: 'title', label: 'Scenario Title', type: 'text', required: true },
    { name: 'description', label: 'Description', type: 'textarea' },
  ];

  if (error) {
    return (
      <DarkPageLayout title="Digital Twin" icon={<Cpu size={20} />}>
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
    <ModuleErrorBoundary moduleName="Digital Twin">
    <DarkPageLayout
      title="Digital Twin"
      subtitle="Simulate factory scenarios"
      icon={<Cpu size={20} />}
      actions={<DarkButton icon={<Plus size={18} />} onClick={() => setIsCreateModalOpen(true)}>New Scenario</DarkButton>}
    >
      {/* Info Banner */}
      <DarkCard className="mb-6 bg-purple/10 border-purple/20">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-purple/20 flex items-center justify-center shrink-0">
            <Cpu size={18} className="text-purple" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-purple">Digital Twin Technology</p>
            <p className="text-sm text-text-secondary mt-1">
              Create virtual copies of your factory to test changes safely. Simulate scheduling changes, 
              capacity modifications, and process improvements without affecting production.
            </p>
          </div>
          <DarkButton 
            variant="secondary" 
            size="sm"
            icon={<Sparkles size={16} />}
            onClick={() => setShowTemplates(!showTemplates)}
          >
            {showTemplates ? 'Esconder Templates' : 'Usar Template'}
          </DarkButton>
        </div>
      </DarkCard>

      {/* PALANTIR: Scenario Templates Gallery */}
      {showTemplates && (
        <DarkCard className="mb-6" title="Scenario Templates" subtitle="Escolhe um template para começar rapidamente">
          <ScenarioTemplatesGallery 
            onSelectTemplate={(template) => {
              setSelectedTemplate(template);
              setIsCreateModalOpen(true);
              setShowTemplates(false);
              toast.success(`Template "${template.name}" seleccionado!`);
            }}
          />
        </DarkCard>
      )}

      {/* Blocked Metrics Notice - inform user about simulation limitations */}
      <BlockedMetricsNotice 
        variant="collapsible" 
        title="Simulation Limitations" 
        dismissable 
        className="mb-6" 
      />

      <div className="flex items-center gap-4 mb-6">
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'DRAFT', 'SIMULATED', 'SOLVED'].map((status) => (
            <DarkPillButton key={status} active={filterStatus === status} onClick={() => setFilterStatus(status)}>{status}</DarkPillButton>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <DarkStatCard icon={<Cpu size={18} />} label="Total" value={stats.total} size="sm" />
        <DarkStatCard icon={<Cpu size={18} />} iconBg="bg-amber/20" label="Draft" value={stats.draft} size="sm" />
        <DarkStatCard icon={<Cpu size={18} />} iconBg="bg-blue/20" label="Simulated" value={stats.simulated} size="sm" />
        <DarkStatCard icon={<Cpu size={18} />} iconBg="bg-success/20" label="Solved" value={stats.solved} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Scenario</DarkTableHeader>
                <DarkTableHeader>Created</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
                <DarkTableHeader>Results</DarkTableHeader>
                <DarkTableHeader>Hash</DarkTableHeader>
                <DarkTableHeader align="right">Actions</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredScenarios.map((scenario: any) => (
                <DarkTableRow key={scenario.id}>
                  <DarkTableCell>
                    <div><p className="font-semibold text-text-white">{scenario.title}</p>{scenario.description && <p className="text-xs text-text-tertiary truncate max-w-xs">{scenario.description}</p>}</div>
                  </DarkTableCell>
                  <DarkTableCell className="text-text-tertiary">{scenario.created_at ? format(new Date(scenario.created_at), 'dd/MM/yy HH:mm') : '-'}</DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={scenario.status === 'SOLVED' ? 'success' : scenario.status === 'SIMULATED' ? 'info' : 'warning'} dot>
                      {scenario.status || 'DRAFT'}
                    </DarkBadge>
                  </DarkTableCell>
                  <DarkTableCell>
                    {scenario.results ? (
                      <span className="text-accent">{scenario.results.improvement || '0'}% improvement</span>
                    ) : <span className="text-text-tertiary">-</span>}
                  </DarkTableCell>
                  <DarkTableCell>
                    {scenario.reproducibility_hash ? (
                      <code className="text-xs text-text-tertiary font-mono flex items-center gap-1" title={scenario.reproducibility_hash}>
                        <Hash size={12} />
                        {scenario.reproducibility_hash.slice(0, 8)}...
                      </code>
                    ) : <span className="text-text-tertiary">-</span>}
                  </DarkTableCell>
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
                      <DarkIconButton 
                        icon={<GitCompare size={16} />} 
                        size="sm" 
                        variant="ghost" 
                        title="Compare" 
                        onClick={() => setCompareScenario(scenario)}
                        disabled={!scenario.results}
                      />
                      <DarkIconButton icon={<Copy size={16} />} size="sm" variant="ghost" title="Clone" />
                      <DarkIconButton icon={<Trash2 size={16} />} size="sm" variant="ghost" onClick={() => { setDeletingId(scenario.id); setIsDeleteModalOpen(true); }} />
                    </div>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {filteredScenarios.length === 0 && (
                <DarkTableRow><DarkTableCell colSpan={6} className="text-center py-12"><Cpu size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No scenarios found</p></DarkTableCell></DarkTableRow>
              )}
            </DarkTableBody>
          </DarkTable>
        </DarkCard>
      )}

      {/* Scenario Comparison Viewer */}
      {compareScenario && compareScenario.results && (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Scenario Comparison: {compareScenario.title}</h3>
            <DarkIconButton 
              icon={<X size={18} />} 
              variant="ghost" 
              onClick={() => setCompareScenario(null)}
              title="Close comparison"
            />
          </div>
          <ScenarioDiffViewer
            beforeState={compareScenario.results.before_state || {}}
            afterState={compareScenario.results.after_state || {}}
            title={`Simulation Results: ${compareScenario.title}`}
            showBlockedMetrics
            showTrust
          />
        </div>
      )}

      <FormModal title="New Twin Scenario" isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} onSubmit={(data) => createMutation.mutate(data)} fields={scenarioFields} isLoading={createMutation.isPending} />
      <DeleteConfirmDialog isOpen={isDeleteModalOpen} onClose={() => { setIsDeleteModalOpen(false); setDeletingId(null); }} onConfirm={() => { if (deletingId) deleteMutation.mutate(deletingId); }} title="Delete Scenario" message="Are you sure?" isLoading={deleteMutation.isPending} />
    </DarkPageLayout>
    </ModuleErrorBoundary>
  );
}
