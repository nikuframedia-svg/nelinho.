import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  DollarSign,
  Plus,
  Users,
  Cpu,
  Building2,
  Loader2,
  AlertCircle,
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
} from '../../components/dark';
import { FormModal, type FormField } from '../../components/ui';
import { ratesApi, employeesApi, machinesApi } from '../../lib/api';
import type { MutationError, EntityLite } from '../../lib/api-helpers';

type EmployeeLite = EntityLite & { employee_name?: string; employee_code?: string };
type MachineLite = EntityLite & { machine_name?: string; machine_code?: string };
import { useToastContext } from '../../components/ToastProvider';
import { format } from 'date-fns';

type RateTab = 'labor' | 'machine' | 'overhead';

interface LaborRate {
  id: string;
  employee_id: string;
  base_hourly_rate: number;
  burden_rate: number;
  loaded_rate: number;
  effective_date: string;
  valid_until?: string;
  currency_code: string;
}

interface MachineRate {
  id: string;
  machine_id: string;
  depreciation_rate: number;
  energy_cost_per_hour: number;
  maintenance_cost_per_hour: number;
  total_rate: number;
  effective_date: string;
  valid_until?: string;
  currency_code: string;
}

interface OverheadRate {
  id: string;
  year_month: string;
  rent_amount: number;
  utilities_amount: number;
  management_amount: number;
  other_overhead_amount: number;
  total_monthly_overhead: number;
  total_available_hours: number;
  calculated_rate: number;
  currency_code: string;
}

export function RatesPage() {
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToastContext();

  const [activeTab, setActiveTab] = useState<RateTab>('labor');
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);

  // Fetch employees and machines for dropdowns
  const { data: employees = [] } = useQuery<any[]>({
    queryKey: ['employees', 'list'],
    queryFn: () => employeesApi.list({ limit: 1000 }),
  });

  const { data: machines = [] } = useQuery<any[]>({
    queryKey: ['machines', 'list'],
    queryFn: () => machinesApi.list({ limit: 1000 }),
  });

  // Fetch rates based on active tab
  const {
    data: laborRates = [],
    isLoading: isLoadingLabor,
    error: laborError,
  } = useQuery<LaborRate[]>({
    queryKey: ['rates', 'labor'],
    queryFn: () => ratesApi.laborRates.list(),
    enabled: activeTab === 'labor',
  });

  const {
    data: machineRates = [],
    isLoading: isLoadingMachine,
    error: machineError,
  } = useQuery<MachineRate[]>({
    queryKey: ['rates', 'machine'],
    queryFn: () => ratesApi.machineRates.list(),
    enabled: activeTab === 'machine',
  });

  const {
    data: overheadRates = [],
    isLoading: isLoadingOverhead,
    error: overheadError,
  } = useQuery<OverheadRate[]>({
    queryKey: ['rates', 'overhead'],
    queryFn: () => ratesApi.overheadRates.list(),
    enabled: activeTab === 'overhead',
  });

  // Mutations
  const createLaborRateMutation = useMutation({
    mutationFn: ratesApi.laborRates.create,
    onSuccess: () => {
      success('Labor rate added successfully');
      queryClient.invalidateQueries({ queryKey: ['rates', 'labor'] });
      setIsFormModalOpen(false);
    },
    onError: (err: MutationError) => {
      toastError(err.message || 'Error adding labor rate');
    },
  });

  const createMachineRateMutation = useMutation({
    mutationFn: ratesApi.machineRates.create,
    onSuccess: () => {
      success('Machine rate added successfully');
      queryClient.invalidateQueries({ queryKey: ['rates', 'machine'] });
      setIsFormModalOpen(false);
    },
    onError: (err: MutationError) => {
      toastError(err.message || 'Error adding machine rate');
    },
  });

  const createOverheadRateMutation = useMutation({
    mutationFn: ratesApi.overheadRates.create,
    onSuccess: () => {
      success('Overhead rate added successfully');
      queryClient.invalidateQueries({ queryKey: ['rates', 'overhead'] });
      setIsFormModalOpen(false);
    },
    onError: (err: MutationError) => {
      toastError(err.message || 'Error adding overhead rate');
    },
  });

  // Form field definitions
  const employeeOptions = useMemo(
    () =>
      (employees as EmployeeLite[]).map((e) => ({
        value: e.id,
        label: `${e.employee_name ?? ''} (${e.employee_code ?? ''})`,
      })),
    [employees]
  );

  const machineOptions = useMemo(
    () =>
      (machines as MachineLite[]).map((m) => ({
        value: m.id,
        label: `${m.machine_name ?? ''} (${m.machine_code ?? ''})`,
      })),
    [machines]
  );

  const laborFormFields: FormField[] = [
    {
      name: 'employee_id',
      label: 'Employee',
      type: 'select',
      options: employeeOptions,
      required: true,
    },
    {
      name: 'base_hourly_rate',
      label: 'Base Hourly Rate (€)',
      type: 'number',
      required: true,
      min: 0,
      step: 0.01,
    },
    {
      name: 'burden_rate',
      label: 'Burden Rate (%)',
      type: 'number',
      defaultValue: 32,
      min: 0,
      max: 100,
      step: 0.1,
    },
    {
      name: 'effective_date',
      label: 'Effective Date',
      type: 'date',
      required: true,
    },
    {
      name: 'valid_until',
      label: 'Valid Until (Optional)',
      type: 'date',
    },
  ];

  const machineFormFields: FormField[] = [
    {
      name: 'machine_id',
      label: 'Machine',
      type: 'select',
      options: machineOptions,
      required: true,
    },
    {
      name: 'depreciation_rate',
      label: 'Depreciation Rate (€/hour)',
      type: 'number',
      defaultValue: 0,
      min: 0,
      step: 0.01,
    },
    {
      name: 'energy_cost_per_hour',
      label: 'Energy Cost (€/hour)',
      type: 'number',
      defaultValue: 0,
      min: 0,
      step: 0.01,
    },
    {
      name: 'maintenance_cost_per_hour',
      label: 'Maintenance Cost (€/hour)',
      type: 'number',
      defaultValue: 0,
      min: 0,
      step: 0.01,
    },
    {
      name: 'effective_date',
      label: 'Effective Date',
      type: 'date',
      required: true,
    },
    {
      name: 'valid_until',
      label: 'Valid Until (Optional)',
      type: 'date',
    },
  ];

  const overheadFormFields: FormField[] = [
    {
      name: 'year_month',
      label: 'Month (YYYY-MM-01)',
      type: 'date',
      required: true,
    },
    {
      name: 'rent_amount',
      label: 'Rent Amount (€)',
      type: 'number',
      defaultValue: 0,
      min: 0,
      step: 0.01,
    },
    {
      name: 'utilities_amount',
      label: 'Utilities Amount (€)',
      type: 'number',
      defaultValue: 0,
      min: 0,
      step: 0.01,
    },
    {
      name: 'management_amount',
      label: 'Management Amount (€)',
      type: 'number',
      defaultValue: 0,
      min: 0,
      step: 0.01,
    },
    {
      name: 'other_overhead_amount',
      label: 'Other Overhead (€)',
      type: 'number',
      defaultValue: 0,
      min: 0,
      step: 0.01,
    },
    {
      name: 'total_available_hours',
      label: 'Total Available Hours',
      type: 'number',
      defaultValue: 10000,
      min: 1,
    },
  ];

  const handleFormSubmit = (data: Record<string, any>) => {
    if (activeTab === 'labor') {
      createLaborRateMutation.mutate({
        employee_id: data.employee_id,
        base_hourly_rate: parseFloat(data.base_hourly_rate),
        burden_rate: parseFloat(data.burden_rate) / 100,
        effective_date: data.effective_date,
        valid_until: data.valid_until || null,
      });
    } else if (activeTab === 'machine') {
      createMachineRateMutation.mutate({
        machine_id: data.machine_id,
        depreciation_rate: parseFloat(data.depreciation_rate),
        energy_cost_per_hour: parseFloat(data.energy_cost_per_hour),
        maintenance_cost_per_hour: parseFloat(data.maintenance_cost_per_hour),
        effective_date: data.effective_date,
        valid_until: data.valid_until || null,
      });
    } else if (activeTab === 'overhead') {
      createOverheadRateMutation.mutate({
        year_month: data.year_month,
        rent_amount: parseFloat(data.rent_amount),
        utilities_amount: parseFloat(data.utilities_amount),
        management_amount: parseFloat(data.management_amount),
        other_overhead_amount: parseFloat(data.other_overhead_amount),
        total_available_hours: parseInt(data.total_available_hours),
      });
    }
  };

  const isLoading =
    (activeTab === 'labor' && isLoadingLabor) ||
    (activeTab === 'machine' && isLoadingMachine) ||
    (activeTab === 'overhead' && isLoadingOverhead);

  const error = laborError || machineError || overheadError;

  const currentFormFields =
    activeTab === 'labor'
      ? laborFormFields
      : activeTab === 'machine'
      ? machineFormFields
      : overheadFormFields;

  const formTitle =
    activeTab === 'labor'
      ? 'Add Labor Rate'
      : activeTab === 'machine'
      ? 'Add Machine Rate'
      : 'Add Overhead Rate';

  const isMutating =
    createLaborRateMutation.isPending ||
    createMachineRateMutation.isPending ||
    createOverheadRateMutation.isPending;

  // Stats
  const stats = useMemo(() => ({
    laborCount: laborRates.length,
    machineCount: machineRates.length,
    overheadCount: overheadRates.length,
    avgLaborRate: laborRates.length > 0 ? laborRates.reduce((sum, r) => sum + r.loaded_rate, 0) / laborRates.length : 0,
    avgMachineRate: machineRates.length > 0 ? machineRates.reduce((sum, r) => sum + r.total_rate, 0) / machineRates.length : 0,
    avgOverheadRate: overheadRates.length > 0 ? overheadRates.reduce((sum, r) => sum + r.calculated_rate, 0) / overheadRates.length : 0,
  }), [laborRates, machineRates, overheadRates]);

  return (
    <DarkPageLayout
      title="Rate Tables"
      subtitle="Labor, Machine & Overhead rates"
      icon={<DollarSign size={20} />}
      actions={
        <DarkButton
          icon={<Plus size={18} />}
          onClick={() => setIsFormModalOpen(true)}
        >
          Add Rate
        </DarkButton>
      }
    >
      {/* Tabs */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          <DarkPillButton
            active={activeTab === 'labor'}
            onClick={() => setActiveTab('labor')}
          >
            <Users size={16} className="mr-1.5" />
            Labor Rates
          </DarkPillButton>
          <DarkPillButton
            active={activeTab === 'machine'}
            onClick={() => setActiveTab('machine')}
          >
            <Cpu size={16} className="mr-1.5" />
            Machine Rates
          </DarkPillButton>
          <DarkPillButton
            active={activeTab === 'overhead'}
            onClick={() => setActiveTab('overhead')}
          >
            <Building2 size={16} className="mr-1.5" />
            Overhead Rates
          </DarkPillButton>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <DarkStatCard
          icon={<Users size={18} />}
          iconBg="bg-success/20"
          label="Labor Rates"
          value={stats.laborCount}
          size="sm"
        />
        <DarkStatCard
          icon={<Cpu size={18} />}
          iconBg="bg-blue/20"
          label="Machine Rates"
          value={stats.machineCount}
          size="sm"
        />
        <DarkStatCard
          icon={<Building2 size={18} />}
          iconBg="bg-amber/20"
          label="Overhead Rates"
          value={stats.overheadCount}
          size="sm"
        />
      </div>

      {/* Error State */}
      {error && (
        <DarkCard className="mb-6 border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertCircle size={20} />
            <div>
              <p className="font-semibold">Error loading rates</p>
              <p className="text-sm opacity-80">{(error as Error).message}</p>
            </div>
          </div>
        </DarkCard>
      )}

      {/* Loading State */}
      {isLoading && (
        <DarkCard className="mb-6">
          <div className="flex items-center justify-center gap-3 text-text-secondary py-8">
            <Loader2 size={20} className="animate-spin" />
            <p>Loading rates...</p>
          </div>
        </DarkCard>
      )}

      {/* Tables */}
      {!isLoading && !error && (
        <DarkCard padding="none">
          {/* Labor Rates Table */}
          {activeTab === 'labor' && (
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Employee</DarkTableHeader>
                  <DarkTableHeader>Base Rate</DarkTableHeader>
                  <DarkTableHeader>Burden Rate</DarkTableHeader>
                  <DarkTableHeader>Loaded Rate</DarkTableHeader>
                  <DarkTableHeader>Effective From</DarkTableHeader>
                  <DarkTableHeader>Valid Until</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {laborRates.map((rate) => {
                  const employee = (employees as EmployeeLite[]).find((e) => e.id === rate.employee_id);
                  return (
                    <DarkTableRow key={rate.id}>
                      <DarkTableCell>
                        <div>
                          <p className="font-semibold text-text-white text-sm">
                            {employee?.employee_name || 'Unknown'}
                          </p>
                          <p className="text-xs text-text-tertiary">
                            {employee?.employee_code || rate.employee_id}
                          </p>
                        </div>
                      </DarkTableCell>
                      <DarkTableCell mono>€{rate.base_hourly_rate.toFixed(2)}/h</DarkTableCell>
                      <DarkTableCell mono>{(rate.burden_rate * 100).toFixed(1)}%</DarkTableCell>
                      <DarkTableCell>
                        <DarkBadge variant="success">€{rate.loaded_rate.toFixed(2)}/h</DarkBadge>
                      </DarkTableCell>
                      <DarkTableCell>{format(new Date(rate.effective_date), 'dd MMM yyyy')}</DarkTableCell>
                      <DarkTableCell>
                        {rate.valid_until ? format(new Date(rate.valid_until), 'dd MMM yyyy') : '-'}
                      </DarkTableCell>
                    </DarkTableRow>
                  );
                })}
                {laborRates.length === 0 && (
                  <DarkTableRow>
                    <DarkTableCell colSpan={6} className="text-center py-12">
                      <Users size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                      <p className="font-medium text-text-secondary">No labor rates found</p>
                      <p className="text-sm text-text-tertiary">Click 'Add Rate' to create one</p>
                    </DarkTableCell>
                  </DarkTableRow>
                )}
              </DarkTableBody>
            </DarkTable>
          )}

          {/* Machine Rates Table */}
          {activeTab === 'machine' && (
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Machine</DarkTableHeader>
                  <DarkTableHeader>Depreciation</DarkTableHeader>
                  <DarkTableHeader>Energy</DarkTableHeader>
                  <DarkTableHeader>Maintenance</DarkTableHeader>
                  <DarkTableHeader>Total Rate</DarkTableHeader>
                  <DarkTableHeader>Effective From</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {machineRates.map((rate) => {
                  const machine = (machines as MachineLite[]).find((m) => m.id === rate.machine_id);
                  return (
                    <DarkTableRow key={rate.id}>
                      <DarkTableCell>
                        <div>
                          <p className="font-semibold text-text-white text-sm">
                            {machine?.machine_name || 'Unknown'}
                          </p>
                          <p className="text-xs text-text-tertiary">
                            {machine?.machine_code || rate.machine_id}
                          </p>
                        </div>
                      </DarkTableCell>
                      <DarkTableCell mono>€{rate.depreciation_rate.toFixed(2)}/h</DarkTableCell>
                      <DarkTableCell mono>€{rate.energy_cost_per_hour.toFixed(2)}/h</DarkTableCell>
                      <DarkTableCell mono>€{rate.maintenance_cost_per_hour.toFixed(2)}/h</DarkTableCell>
                      <DarkTableCell>
                        <DarkBadge variant="info">€{rate.total_rate.toFixed(2)}/h</DarkBadge>
                      </DarkTableCell>
                      <DarkTableCell>{format(new Date(rate.effective_date), 'dd MMM yyyy')}</DarkTableCell>
                    </DarkTableRow>
                  );
                })}
                {machineRates.length === 0 && (
                  <DarkTableRow>
                    <DarkTableCell colSpan={6} className="text-center py-12">
                      <Cpu size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                      <p className="font-medium text-text-secondary">No machine rates found</p>
                      <p className="text-sm text-text-tertiary">Click 'Add Rate' to create one</p>
                    </DarkTableCell>
                  </DarkTableRow>
                )}
              </DarkTableBody>
            </DarkTable>
          )}

          {/* Overhead Rates Table */}
          {activeTab === 'overhead' && (
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Month</DarkTableHeader>
                  <DarkTableHeader>Rent</DarkTableHeader>
                  <DarkTableHeader>Utilities</DarkTableHeader>
                  <DarkTableHeader>Management</DarkTableHeader>
                  <DarkTableHeader>Other</DarkTableHeader>
                  <DarkTableHeader>Total Monthly</DarkTableHeader>
                  <DarkTableHeader>Hours</DarkTableHeader>
                  <DarkTableHeader>Rate/Hour</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {overheadRates.map((rate) => (
                  <DarkTableRow key={rate.id}>
                    <DarkTableCell className="text-text-white font-semibold">
                      {format(new Date(rate.year_month), 'MMM yyyy')}
                    </DarkTableCell>
                    <DarkTableCell mono>€{rate.rent_amount.toFixed(2)}</DarkTableCell>
                    <DarkTableCell mono>€{rate.utilities_amount.toFixed(2)}</DarkTableCell>
                    <DarkTableCell mono>€{rate.management_amount.toFixed(2)}</DarkTableCell>
                    <DarkTableCell mono>€{rate.other_overhead_amount.toFixed(2)}</DarkTableCell>
                    <DarkTableCell mono className="text-text-white font-medium">
                      €{rate.total_monthly_overhead.toFixed(2)}
                    </DarkTableCell>
                    <DarkTableCell mono>{rate.total_available_hours.toLocaleString()}</DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge variant="warning">€{rate.calculated_rate.toFixed(2)}/h</DarkBadge>
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
                {overheadRates.length === 0 && (
                  <DarkTableRow>
                    <DarkTableCell colSpan={8} className="text-center py-12">
                      <Building2 size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                      <p className="font-medium text-text-secondary">No overhead rates found</p>
                      <p className="text-sm text-text-tertiary">Click 'Add Rate' to create one</p>
                    </DarkTableCell>
                  </DarkTableRow>
                )}
              </DarkTableBody>
            </DarkTable>
          )}
        </DarkCard>
      )}

      {/* Form Modal */}
      <FormModal
        title={formTitle}
        isOpen={isFormModalOpen}
        onClose={() => setIsFormModalOpen(false)}
        onSubmit={handleFormSubmit}
        initialData={{}}
        fields={currentFormFields}
        isLoading={isMutating}
      />
    </DarkPageLayout>
  );
}
