import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Plus, 
  Wrench,
  Cog,
  PlayCircle,
  PauseCircle,
  ArrowUpDown,
  Factory,
  Bot,
  Hand,
  Loader2,
  AlertCircle,
  Edit,
  Trash2,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { 
  DarkCard, 
  DarkStatCard, 
  DarkTable, 
  DarkTableHead, 
  DarkTableBody, 
  DarkTableRow, 
  DarkTableHeader, 
  DarkTableCell,
  DarkButton,
  DarkPillButton,
  DarkBadge,
  DarkSearchInput,
  DarkIconButton,
} from '../../components/dark';
import { FormModal, DeleteConfirmDialog, type FormField } from '../../components/ui';
import { operationsApi, machinesApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';

interface Phase {
  id: string;
  name: string;
  operation_code?: string;
  sequence: number;
  isProduction: boolean;
  isAutomatic: boolean;
  status: string;
  machine_id?: string;
  std_time_minutes?: number;
  setup_time_minutes?: number;
}

export function OperationsPage() {
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToastContext();

  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<'ALL' | 'PRODUCTION' | 'NON_PRODUCTION'>('ALL');
  const [sortBy, setSortBy] = useState<'sequence' | 'name'>('sequence');

  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [editingPhase, setEditingPhase] = useState<Phase | null>(null);
  const [deletingPhase, setDeletingPhase] = useState<Phase | null>(null);

  const { data: machines = [] } = useQuery<any[]>({
    queryKey: ['machines', 'list'],
    queryFn: () => machinesApi.list({ limit: 1000 }),
  });

  const { data: operationsList, isLoading, error } = useQuery({
    queryKey: ['operations', 'list'],
    queryFn: () => operationsApi.list({ limit: 1000 }),
    refetchInterval: 300000,
  });

  const phases: Phase[] = useMemo(() => {
    if (!operationsList) return [];
    return (Array.isArray(operationsList) ? operationsList : []).map((op: any) => ({
      id: op.id || op.operation_id || '',
      name: op.name || op.operation_name || '',
      operation_code: op.operation_code || '',
      sequence: op.sequence || op.sequence_number || 0,
      isProduction: op.is_production ?? op.isProduction ?? true,
      isAutomatic: op.is_automatic ?? op.isAutomatic ?? false,
      status: op.status || 'ACTIVE',
      machine_id: op.machine_id,
      std_time_minutes: op.std_time_minutes,
      setup_time_minutes: op.setup_time_minutes,
    }));
  }, [operationsList]);

  const filteredPhases = useMemo(() => {
    return phases
      .filter(p => {
        const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase()) || p.id.includes(search);
        const matchesType = filterType === 'ALL' || 
                           (filterType === 'PRODUCTION' && p.isProduction) ||
                           (filterType === 'NON_PRODUCTION' && !p.isProduction);
        return matchesSearch && matchesType;
      })
      .sort((a, b) => sortBy === 'sequence' ? a.sequence - b.sequence : a.name.localeCompare(b.name));
  }, [phases, search, filterType, sortBy]);

  const stats = useMemo(() => ({
    total: phases.length,
    production: phases.filter(p => p.isProduction).length,
    automatic: phases.filter(p => p.isAutomatic).length,
    manual: phases.filter(p => !p.isAutomatic).length,
  }), [phases]);

  const productionPhases = useMemo(() => {
    return phases.filter(p => p.isProduction).sort((a, b) => a.sequence - b.sequence);
  }, [phases]);

  const machineOptions = useMemo(() => [
    { value: '', label: '-- No Machine --' },
    ...machines.map((m: any) => ({ value: m.id, label: `${m.machine_name} (${m.machine_code})` })),
  ], [machines]);

  const createMutation = useMutation({
    mutationFn: operationsApi.create,
    onSuccess: () => { success('Operation added'); queryClient.invalidateQueries({ queryKey: ['operations'] }); setIsFormModalOpen(false); },
    onError: (err: any) => toastError(err.message || 'Error'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => operationsApi.update(id, data),
    onSuccess: () => { success('Operation updated'); queryClient.invalidateQueries({ queryKey: ['operations'] }); setIsFormModalOpen(false); setEditingPhase(null); },
    onError: (err: any) => toastError(err.message || 'Error'),
  });

  const deleteMutation = useMutation({
    mutationFn: operationsApi.delete,
    onSuccess: () => { success('Operation deleted'); queryClient.invalidateQueries({ queryKey: ['operations'] }); setIsDeleteConfirmOpen(false); setDeletingPhase(null); },
    onError: (err: any) => toastError(err.message || 'Error'),
  });

  const operationFormFields: FormField[] = [
    { name: 'operation_code', label: 'Operation Code', type: 'text', required: true },
    { name: 'operation_name', label: 'Operation Name', type: 'text', required: true },
    { name: 'machine_id', label: 'Machine', type: 'select', options: machineOptions },
    { name: 'std_time_minutes', label: 'Standard Time (min)', type: 'number', min: 0, step: 0.1 },
    { name: 'setup_time_minutes', label: 'Setup Time (min)', type: 'number', min: 0, step: 0.1, defaultValue: 0 },
  ];

  const handleFormSubmit = (data: Record<string, any>) => {
    const payload = {
      operation_code: data.operation_code,
      operation_name: data.operation_name,
      machine_id: data.machine_id || null,
      std_time_minutes: data.std_time_minutes ? parseFloat(data.std_time_minutes) : null,
      setup_time_minutes: data.setup_time_minutes ? parseFloat(data.setup_time_minutes) : 0,
    };
    editingPhase ? updateMutation.mutate({ id: editingPhase.id, data: payload }) : createMutation.mutate(payload);
  };

  return (
    <DarkPageLayout
      title="Production Phases"
      subtitle={isLoading ? 'Loading...' : `${phases.length} phases in workflow`}
      icon={<Wrench size={20} />}
      actions={
        <DarkButton icon={<Plus size={18} />} onClick={() => { setEditingPhase(null); setIsFormModalOpen(true); }}>
          Add Phase
        </DarkButton>
      }
    >
      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput
          placeholder="Search phases..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onClear={() => setSearch('')}
          containerClassName="w-72"
        />
        
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {(['ALL', 'PRODUCTION', 'NON_PRODUCTION'] as const).map((type) => (
            <DarkPillButton key={type} active={filterType === type} onClick={() => setFilterType(type)}>
              {type === 'ALL' ? 'All' : type === 'PRODUCTION' ? 'Production' : 'Non-Production'}
            </DarkPillButton>
          ))}
        </div>

        <DarkButton variant="secondary" size="sm" icon={<ArrowUpDown size={14} />} onClick={() => setSortBy(sortBy === 'sequence' ? 'name' : 'sequence')}>
          Sort by {sortBy === 'sequence' ? 'Sequence' : 'Name'}
        </DarkButton>
      </div>

      {isLoading && (
        <DarkCard className="mb-6">
          <div className="flex items-center justify-center gap-3 text-text-secondary py-8">
            <Loader2 size={20} className="animate-spin" /><p>Loading operations...</p>
          </div>
        </DarkCard>
      )}

      {error && (
        <DarkCard className="mb-6 border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertCircle size={20} />
            <div><p className="font-semibold">Error loading operations</p><p className="text-sm opacity-80">{error instanceof Error ? error.message : 'Failed to load'}</p></div>
          </div>
        </DarkCard>
      )}

      {!isLoading && !error && (
        <>
          <div className="grid grid-cols-4 gap-4 mb-6">
            <DarkStatCard icon={<Cog size={18} />} label="Total Phases" value={stats.total} size="sm" />
            <DarkStatCard icon={<Factory size={18} />} iconBg="bg-blue/20" label="Production" value={stats.production} size="sm" />
            <DarkStatCard icon={<Bot size={18} />} iconBg="bg-success/20" label="Automatic" value={stats.automatic} size="sm" />
            <DarkStatCard icon={<Hand size={18} />} iconBg="bg-amber/20" label="Manual" value={stats.manual} size="sm" />
          </div>

          <DarkCard className="mb-6" title="Production Flow">
            <div className="flex items-center gap-1 overflow-x-auto pb-2">
              {productionPhases.slice(0, 12).map((phase, index) => (
                <div key={phase.id} className="flex items-center">
                  <div className="flex flex-col items-center min-w-[80px]">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold ${phase.isAutomatic ? 'bg-success' : 'bg-blue'}`}>
                      {phase.sequence}
                    </div>
                    <p className="text-xs text-text-tertiary mt-1 text-center truncate w-full">{phase.name}</p>
                  </div>
                  {index < Math.min(productionPhases.length, 12) - 1 && <div className="w-4 h-0.5 bg-border-subtle mx-1" />}
                </div>
              ))}
              {productionPhases.length > 12 && <span className="text-xs text-text-tertiary ml-2">+{productionPhases.length - 12} more</span>}
            </div>
          </DarkCard>

          <DarkCard padding="none">
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Seq</DarkTableHeader>
                  <DarkTableHeader>Phase</DarkTableHeader>
                  <DarkTableHeader>Type</DarkTableHeader>
                  <DarkTableHeader>Mode</DarkTableHeader>
                  <DarkTableHeader>Status</DarkTableHeader>
                  <DarkTableHeader align="right">Actions</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {filteredPhases.map((phase) => (
                  <DarkTableRow key={phase.id}>
                    <DarkTableCell>
                      <span className={`inline-flex items-center justify-center w-8 h-8 rounded-lg text-sm font-bold ${phase.isProduction ? 'bg-blue/20 text-blue' : 'bg-bg-elevated text-text-tertiary'}`}>
                        {phase.sequence}
                      </span>
                    </DarkTableCell>
                    <DarkTableCell>
                      <div><p className="font-semibold text-text-white text-sm">{phase.name}</p><p className="text-xs text-text-tertiary">ID: {phase.id}</p></div>
                    </DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge variant={phase.isProduction ? 'info' : 'neutral'} icon={phase.isProduction ? <PlayCircle size={12} /> : <PauseCircle size={12} />}>
                        {phase.isProduction ? 'Production' : 'Non-Production'}
                      </DarkBadge>
                    </DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge variant={phase.isAutomatic ? 'success' : 'warning'} icon={phase.isAutomatic ? <Bot size={12} /> : <Hand size={12} />}>
                        {phase.isAutomatic ? 'Automatic' : 'Manual'}
                      </DarkBadge>
                    </DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge variant={phase.status === 'ACTIVE' ? 'success' : 'neutral'} dot>{phase.status}</DarkBadge>
                    </DarkTableCell>
                    <DarkTableCell align="right">
                      <div className="flex items-center justify-end gap-1">
                        <DarkIconButton icon={<Edit size={16} />} size="sm" variant="ghost" onClick={() => { setEditingPhase(phase); setIsFormModalOpen(true); }} />
                        <DarkIconButton icon={<Trash2 size={16} />} size="sm" variant="ghost" onClick={() => { setDeletingPhase(phase); setIsDeleteConfirmOpen(true); }} />
                      </div>
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
                {filteredPhases.length === 0 && (
                  <DarkTableRow>
                    <DarkTableCell colSpan={6} className="text-center py-12">
                      <Wrench size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                      <p className="font-medium text-text-secondary">No phases found</p>
                    </DarkTableCell>
                  </DarkTableRow>
                )}
              </DarkTableBody>
            </DarkTable>
            <div className="px-6 py-4 border-t border-border-subtle">
              <p className="text-sm text-text-tertiary">Showing {filteredPhases.length} of {phases.length} phases</p>
            </div>
          </DarkCard>
        </>
      )}

      <FormModal
        title={editingPhase ? 'Edit Operation' : 'Add Operation'}
        isOpen={isFormModalOpen}
        onClose={() => { setIsFormModalOpen(false); setEditingPhase(null); }}
        onSubmit={handleFormSubmit}
        initialData={editingPhase ? { operation_code: editingPhase.operation_code, operation_name: editingPhase.name, machine_id: editingPhase.machine_id, std_time_minutes: editingPhase.std_time_minutes, setup_time_minutes: editingPhase.setup_time_minutes } : {}}
        fields={operationFormFields}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      <DeleteConfirmDialog
        isOpen={isDeleteConfirmOpen}
        onClose={() => { setIsDeleteConfirmOpen(false); setDeletingPhase(null); }}
        onConfirm={() => { if (deletingPhase) deleteMutation.mutate(deletingPhase.id); }}
        title={deletingPhase ? `Operation ${deletingPhase.name}` : 'Operation'}
        message="Are you sure you want to delete this operation?"
        isLoading={deleteMutation.isPending}
      />
    </DarkPageLayout>
  );
}
