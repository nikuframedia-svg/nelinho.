import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Plus, 
  Cpu,
  Loader2,
  AlertCircle,
  MapPin,
  Gauge,
  Settings,
  AlertTriangle,
  CheckCircle2,
  Edit,
  Trash2,
  Eye,
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
  DarkSelect,
  DarkIconButton,
} from '../../components/dark';
import { FormModal, DeleteConfirmDialog, type FormField } from '../../components/ui';
import { machinesApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';

interface Machine {
  id: string;
  machine_code: string;
  machine_name: string;
  machine_type: string;
  status: string;
  location?: string;
  work_center?: string;
  capacity_units_per_hour?: number;
  available_hours_per_day?: number;
}

export function MachinesPage() {
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToastContext();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'MAINTENANCE' | 'BREAKDOWN' | 'RETIRED'>('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [editingMachine, setEditingMachine] = useState<Machine | null>(null);
  const [deletingMachine, setDeletingMachine] = useState<Machine | null>(null);

  const { data: machinesList, isLoading, error } = useQuery({
    queryKey: ['machines', 'list'],
    queryFn: () => machinesApi.list({ limit: 1000 }),
    refetchInterval: 300000,
  });

  const machines: Machine[] = useMemo(() => {
    if (!machinesList) return [];
    return (Array.isArray(machinesList) ? machinesList : []).map((m: any) => ({
      id: m.id || m.machine_id || '',
      machine_code: m.machine_code || '',
      machine_name: m.machine_name || '',
      machine_type: m.machine_type || 'OTHER',
      status: m.status || 'ACTIVE',
      location: m.location || undefined,
      work_center: m.work_center || undefined,
      capacity_units_per_hour: m.capacity_units_per_hour || undefined,
      available_hours_per_day: m.available_hours_per_day || undefined,
    }));
  }, [machinesList]);

  const machineTypes = useMemo(() => {
    const types = new Set(machines.map(m => m.machine_type).filter(Boolean));
    return ['ALL', ...Array.from(types)].sort();
  }, [machines]);

  const filteredMachines = useMemo(() => {
    return machines.filter(m => {
      const matchesStatus = statusFilter === 'ALL' || m.status === statusFilter;
      const matchesType = typeFilter === 'ALL' || m.machine_type === typeFilter;
      const matchesSearch = m.machine_name.toLowerCase().includes(search.toLowerCase()) || 
                            m.machine_code.toLowerCase().includes(search.toLowerCase()) ||
                            m.id.toLowerCase().includes(search.toLowerCase());
      return matchesStatus && matchesType && matchesSearch;
    });
  }, [machines, statusFilter, typeFilter, search]);

  const paginatedMachines = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredMachines.slice(start, start + itemsPerPage);
  }, [filteredMachines, currentPage]);

  const totalPages = Math.ceil(filteredMachines.length / itemsPerPage);

  const stats = useMemo(() => {
    if (machines.length === 0) {
      return { total: 0, active: 0, maintenance: 0, breakdown: 0, avgCapacity: 0 };
    }
    const capacities = machines.filter(m => m.capacity_units_per_hour).map(m => m.capacity_units_per_hour!);
    return {
      total: machines.length,
      active: machines.filter(m => m.status === 'ACTIVE').length,
      maintenance: machines.filter(m => m.status === 'MAINTENANCE').length,
      breakdown: machines.filter(m => m.status === 'BREAKDOWN').length,
      avgCapacity: capacities.length > 0 ? Math.round(capacities.reduce((sum, c) => sum + c, 0) / capacities.length) : 0,
    };
  }, [machines]);

  const createMutation = useMutation({
    mutationFn: machinesApi.create,
    onSuccess: () => {
      success('Machine added successfully');
      queryClient.invalidateQueries({ queryKey: ['machines'] });
      setIsFormModalOpen(false);
    },
    onError: (err: any) => toastError(err.message || 'Error adding machine'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => machinesApi.update(id, data),
    onSuccess: () => {
      success('Machine updated successfully');
      queryClient.invalidateQueries({ queryKey: ['machines'] });
      setIsFormModalOpen(false);
      setEditingMachine(null);
    },
    onError: (err: any) => toastError(err.message || 'Error updating machine'),
  });

  const deleteMutation = useMutation({
    mutationFn: machinesApi.delete,
    onSuccess: () => {
      success('Machine deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['machines'] });
      setIsDeleteConfirmOpen(false);
      setDeletingMachine(null);
    },
    onError: (err: any) => toastError(err.message || 'Error deleting machine'),
  });

  const machineFormFields: FormField[] = [
    { name: 'machine_code', label: 'Machine Code', type: 'text', required: true },
    { name: 'machine_name', label: 'Machine Name', type: 'text', required: true },
    {
      name: 'machine_type',
      label: 'Machine Type',
      type: 'select',
      options: [
        { value: 'MOLD', label: 'Mold' },
        { value: 'CNC', label: 'CNC' },
        { value: 'SANDING', label: 'Sanding' },
        { value: 'PAINTING', label: 'Painting' },
        { value: 'ASSEMBLY', label: 'Assembly' },
        { value: 'OTHER', label: 'Other' },
      ],
      defaultValue: 'OTHER',
    },
    { name: 'location', label: 'Location', type: 'text' },
    { name: 'capacity_units_per_hour', label: 'Capacity (units/hour)', type: 'number', min: 0 },
    {
      name: 'status',
      label: 'Status',
      type: 'select',
      options: [
        { value: 'ACTIVE', label: 'Active' },
        { value: 'MAINTENANCE', label: 'Maintenance' },
        { value: 'BREAKDOWN', label: 'Breakdown' },
        { value: 'RETIRED', label: 'Retired' },
      ],
      defaultValue: 'ACTIVE',
    },
  ];

  const handleFormSubmit = (data: Record<string, any>) => {
    const payload = {
      machine_code: data.machine_code,
      machine_name: data.machine_name,
      machine_type: data.machine_type,
      location: data.location || null,
      capacity_units_per_hour: data.capacity_units_per_hour ? parseInt(data.capacity_units_per_hour) : null,
      status: data.status,
    };

    if (editingMachine) {
      updateMutation.mutate({ id: editingMachine.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const handleDeleteConfirm = () => {
    if (deletingMachine) deleteMutation.mutate(deletingMachine.id);
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'success';
      case 'MAINTENANCE': return 'warning';
      case 'BREAKDOWN': return 'danger';
      case 'RETIRED': return 'neutral';
      default: return 'neutral';
    }
  };

  return (
    <DarkPageLayout
      title="Machines"
      subtitle={isLoading ? 'Loading...' : `${machines.length} machines in system`}
      icon={<Cpu size={20} />}
      actions={
        <DarkButton
          icon={<Plus size={18} />}
          onClick={() => { setEditingMachine(null); setIsFormModalOpen(true); }}
        >
          Add Machine
        </DarkButton>
      }
    >
      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput
          placeholder="Search machines..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
          onClear={() => setSearch('')}
          containerClassName="w-72"
        />
        
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {(['ALL', 'ACTIVE', 'MAINTENANCE', 'BREAKDOWN', 'RETIRED'] as const).map((status) => (
            <DarkPillButton
              key={status}
              active={statusFilter === status}
              onClick={() => { setStatusFilter(status); setCurrentPage(1); }}
            >
              {status}
            </DarkPillButton>
          ))}
        </div>

        <DarkSelect
          options={machineTypes.slice(0, 10).map(type => ({ value: type, label: type }))}
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setCurrentPage(1); }}
          containerClassName="w-40"
        />
      </div>

      {/* Loading State */}
      {isLoading && (
        <DarkCard className="mb-6">
          <div className="flex items-center justify-center gap-3 text-text-secondary py-8">
            <Loader2 size={20} className="animate-spin" />
            <p>Loading machines...</p>
          </div>
        </DarkCard>
      )}

      {/* Error State */}
      {error && (
        <DarkCard className="mb-6 border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertCircle size={20} />
            <div>
              <p className="font-semibold">Error loading machines</p>
              <p className="text-sm opacity-80">
                {error instanceof Error ? error.message : 'Failed to load machines from API'}
              </p>
            </div>
          </div>
        </DarkCard>
      )}

      {!isLoading && !error && (
        <>
          {/* Stats */}
          <div className="grid grid-cols-5 gap-4 mb-6">
            <DarkStatCard icon={<Cpu size={18} />} label="Total" value={stats.total} size="sm" />
            <DarkStatCard icon={<CheckCircle2 size={18} />} iconBg="bg-success/20" label="Active" value={stats.active} size="sm" />
            <DarkStatCard icon={<Settings size={18} />} iconBg="bg-warning/20" label="Maintenance" value={stats.maintenance} size="sm" />
            <DarkStatCard icon={<AlertTriangle size={18} />} iconBg="bg-danger/20" label="Breakdown" value={stats.breakdown} size="sm" />
            <DarkStatCard icon={<Gauge size={18} />} iconBg="bg-blue/20" label="Avg Capacity" value={stats.avgCapacity} unit="/h" size="sm" />
          </div>

          {/* Table */}
          <DarkCard padding="none">
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Code</DarkTableHeader>
                  <DarkTableHeader>Machine Name</DarkTableHeader>
                  <DarkTableHeader>Type</DarkTableHeader>
                  <DarkTableHeader>Location</DarkTableHeader>
                  <DarkTableHeader>Capacity</DarkTableHeader>
                  <DarkTableHeader>Hours/Day</DarkTableHeader>
                  <DarkTableHeader>Status</DarkTableHeader>
                  <DarkTableHeader align="right">Actions</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {paginatedMachines.map((machine) => (
                  <DarkTableRow key={machine.id}>
                    <DarkTableCell className="text-text-white font-semibold">{machine.machine_code}</DarkTableCell>
                    <DarkTableCell>
                      <div>
                        <p className="font-semibold text-text-white text-sm">{machine.machine_name}</p>
                        <p className="text-xs text-text-tertiary">ID: {machine.id}</p>
                      </div>
                    </DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge variant="info">{machine.machine_type}</DarkBadge>
                    </DarkTableCell>
                    <DarkTableCell>
                      {machine.location ? (
                        <div className="flex items-center gap-1 text-text-secondary">
                          <MapPin size={14} />
                          {machine.location}
                        </div>
                      ) : (
                        <span className="text-text-tertiary">-</span>
                      )}
                    </DarkTableCell>
                    <DarkTableCell mono>
                      {machine.capacity_units_per_hour ? `${machine.capacity_units_per_hour}/h` : '-'}
                    </DarkTableCell>
                    <DarkTableCell mono>
                      {machine.available_hours_per_day ? `${machine.available_hours_per_day}h` : '-'}
                    </DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge variant={getStatusBadgeVariant(machine.status)} dot>
                        {machine.status}
                      </DarkBadge>
                    </DarkTableCell>
                    <DarkTableCell align="right">
                      <div className="flex items-center justify-end gap-1">
                        <DarkIconButton icon={<Eye size={16} />} size="sm" variant="ghost" />
                        <DarkIconButton
                          icon={<Edit size={16} />}
                          size="sm"
                          variant="ghost"
                          onClick={() => { setEditingMachine(machine); setIsFormModalOpen(true); }}
                        />
                        <DarkIconButton
                          icon={<Trash2 size={16} />}
                          size="sm"
                          variant="ghost"
                          onClick={() => { setDeletingMachine(machine); setIsDeleteConfirmOpen(true); }}
                        />
                      </div>
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
                {paginatedMachines.length === 0 && (
                  <DarkTableRow>
                    <DarkTableCell colSpan={8} className="text-center py-12">
                      <div className="text-text-tertiary">
                        <Cpu size={40} className="mx-auto mb-3 opacity-50" />
                        <p className="font-medium text-text-secondary">No machines found</p>
                        <p className="text-sm">Try adjusting your search or filters</p>
                      </div>
                    </DarkTableCell>
                  </DarkTableRow>
                )}
              </DarkTableBody>
            </DarkTable>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-6 py-4 border-t border-border-subtle">
                <p className="text-sm text-text-tertiary">
                  Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, filteredMachines.length)} of {filteredMachines.length} results
                </p>
                <div className="flex items-center gap-2">
                  <DarkButton variant="ghost" size="sm" onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}>
                    Previous
                  </DarkButton>
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    const page = currentPage <= 3 ? i + 1 : currentPage + i - 2;
                    if (page > totalPages) return null;
                    return (
                      <button
                        key={page}
                        onClick={() => setCurrentPage(page)}
                        className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                          currentPage === page ? 'bg-accent text-bg-base' : 'text-text-secondary hover:bg-bg-elevated'
                        }`}
                      >
                        {page}
                      </button>
                    );
                  })}
                  <DarkButton variant="ghost" size="sm" onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages}>
                    Next
                  </DarkButton>
                </div>
              </div>
            )}
          </DarkCard>
        </>
      )}

      <FormModal
        title={editingMachine ? 'Edit Machine' : 'Add Machine'}
        isOpen={isFormModalOpen}
        onClose={() => { setIsFormModalOpen(false); setEditingMachine(null); }}
        onSubmit={handleFormSubmit}
        initialData={editingMachine ? {
          machine_code: editingMachine.machine_code,
          machine_name: editingMachine.machine_name,
          machine_type: editingMachine.machine_type,
          location: editingMachine.location,
          capacity_units_per_hour: editingMachine.capacity_units_per_hour,
          status: editingMachine.status,
        } : {}}
        fields={machineFormFields}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      <DeleteConfirmDialog
        isOpen={isDeleteConfirmOpen}
        onClose={() => { setIsDeleteConfirmOpen(false); setDeletingMachine(null); }}
        onConfirm={handleDeleteConfirm}
        title={deletingMachine ? `Machine ${deletingMachine.machine_name}` : 'Machine'}
        message="Are you sure you want to delete this machine? This action cannot be undone."
        isLoading={deleteMutation.isPending}
      />
    </DarkPageLayout>
  );
}
