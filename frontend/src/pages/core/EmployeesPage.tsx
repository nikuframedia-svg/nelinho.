import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Plus, 
  Users,
  UserCheck,
  UserX,
  Wrench,
  Loader2,
  AlertCircle,
  Edit,
  Trash2,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { 
  DarkCard, 
  DarkStatCard, 
  DarkButton,
  DarkPillButton,
  DarkBadge,
  DarkSearchInput,
  DarkSelect,
  DarkIconButton,
} from '../../components/dark';
import { FormModal, DeleteConfirmDialog, type FormField } from '../../components/ui';
import { employeesApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';

interface Employee {
  id: string;
  name: string;
  employee_code?: string;
  status: string;
  skills: string[];
  skillIds: string[];
  department: string;
  shift_pattern?: string;
}

export function EmployeesPage() {
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToastContext();

  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'INACTIVE'>('ALL');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 12;

  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [deletingEmployee, setDeletingEmployee] = useState<Employee | null>(null);

  const { data: employeesList, isLoading, error } = useQuery({
    queryKey: ['employees', 'list'],
    queryFn: () => employeesApi.list({ limit: 1000 }),
    refetchInterval: 300000,
  });

  const employees: Employee[] = useMemo(() => {
    if (!employeesList) return [];
    return (Array.isArray(employeesList) ? employeesList : []).map((e: any) => ({
      id: e.id || e.employee_id || '',
      name: e.name || e.employee_name || '',
      employee_code: e.employee_code || '',
      status: e.status || 'ACTIVE',
      skills: e.skills || e.skill_names || [],
      skillIds: e.skill_ids || [],
      department: e.department || 'Unknown',
      shift_pattern: e.shift_pattern || undefined,
    }));
  }, [employeesList]);

  const departments = useMemo(() => {
    const depts = new Set(employees.map(e => e.department).filter(Boolean));
    return ['ALL', ...Array.from(depts)].sort();
  }, [employees]);

  const filteredEmployees = useMemo(() => {
    return employees.filter(e => {
      const matchesFilter = filter === 'ALL' || e.department === filter;
      const matchesStatus = statusFilter === 'ALL' || e.status === statusFilter;
      const matchesSearch = e.name.toLowerCase().includes(search.toLowerCase()) || 
                            e.id.includes(search) ||
                            e.skills.some(s => s.toLowerCase().includes(search.toLowerCase()));
      return matchesFilter && matchesSearch && matchesStatus;
    });
  }, [employees, filter, statusFilter, search]);

  const paginatedEmployees = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredEmployees.slice(start, start + itemsPerPage);
  }, [filteredEmployees, currentPage]);

  const totalPages = Math.ceil(filteredEmployees.length / itemsPerPage);

  const stats = useMemo(() => {
    if (employees.length === 0) {
      return { total: 0, active: 0, inactive: 0, departments: 0, avgSkills: '0.0' };
    }
    return {
      total: employees.length,
      active: employees.filter(e => e.status === 'ACTIVE').length,
      inactive: employees.filter(e => e.status === 'INACTIVE').length,
      departments: new Set(employees.map(e => e.department)).size,
      avgSkills: (employees.reduce((sum, e) => sum + e.skills.length, 0) / employees.length).toFixed(1),
    };
  }, [employees]);

  const departmentCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    employees.forEach(e => { counts[e.department] = (counts[e.department] || 0) + 1; });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [employees]);

  const createMutation = useMutation({
    mutationFn: employeesApi.create,
    onSuccess: () => {
      success('Employee added successfully');
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      setIsFormModalOpen(false);
    },
    onError: (err: any) => toastError(err.message || 'Error adding employee'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => employeesApi.update(id, data),
    onSuccess: () => {
      success('Employee updated successfully');
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      setIsFormModalOpen(false);
      setEditingEmployee(null);
    },
    onError: (err: any) => toastError(err.message || 'Error updating employee'),
  });

  const deleteMutation = useMutation({
    mutationFn: employeesApi.delete,
    onSuccess: () => {
      success('Employee deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      setIsDeleteConfirmOpen(false);
      setDeletingEmployee(null);
    },
    onError: (err: any) => toastError(err.message || 'Error deleting employee'),
  });

  const employeeFormFields: FormField[] = [
    { name: 'employee_code', label: 'Employee Code', type: 'text', required: true },
    { name: 'employee_name', label: 'Employee Name', type: 'text', required: true },
    { name: 'department', label: 'Department', type: 'text', required: true },
    {
      name: 'shift_pattern',
      label: 'Shift Pattern',
      type: 'select',
      options: [
        { value: 'DAY', label: 'Day Shift' },
        { value: 'NIGHT', label: 'Night Shift' },
        { value: 'ROTATING', label: 'Rotating' },
        { value: 'FLEXIBLE', label: 'Flexible' },
      ],
      defaultValue: 'DAY',
    },
    {
      name: 'status',
      label: 'Status',
      type: 'select',
      options: [
        { value: 'ACTIVE', label: 'Active' },
        { value: 'INACTIVE', label: 'Inactive' },
        { value: 'ON_LEAVE', label: 'On Leave' },
      ],
      defaultValue: 'ACTIVE',
    },
  ];

  const handleFormSubmit = (data: Record<string, any>) => {
    const payload = {
      employee_code: data.employee_code,
      employee_name: data.employee_name,
      department: data.department,
      shift_pattern: data.shift_pattern,
      status: data.status,
    };

    if (editingEmployee) {
      updateMutation.mutate({ id: editingEmployee.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const handleDeleteConfirm = () => {
    if (deletingEmployee) deleteMutation.mutate(deletingEmployee.id);
  };

  return (
    <DarkPageLayout
      title="Employees"
      subtitle={isLoading ? 'Loading...' : `${employees.length} workforce members`}
      icon={<Users size={20} />}
      actions={
        <DarkButton
          icon={<Plus size={18} />}
          onClick={() => { setEditingEmployee(null); setIsFormModalOpen(true); }}
        >
          Add Employee
        </DarkButton>
      }
    >
      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput
          placeholder="Search by name or skill..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
          onClear={() => setSearch('')}
          containerClassName="w-72"
        />
        
        <DarkSelect
          options={departments.slice(0, 10).map(dept => ({ value: dept, label: dept }))}
          value={filter}
          onChange={(e) => { setFilter(e.target.value); setCurrentPage(1); }}
          containerClassName="w-40"
        />

        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {(['ALL', 'ACTIVE', 'INACTIVE'] as const).map((status) => (
            <DarkPillButton
              key={status}
              active={statusFilter === status}
              onClick={() => { setStatusFilter(status); setCurrentPage(1); }}
            >
              {status}
            </DarkPillButton>
          ))}
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <DarkCard className="mb-6">
          <div className="flex items-center justify-center gap-3 text-text-secondary py-8">
            <Loader2 size={20} className="animate-spin" />
            <p>Loading employees...</p>
          </div>
        </DarkCard>
      )}

      {/* Error State */}
      {error && (
        <DarkCard className="mb-6 border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertCircle size={20} />
            <div>
              <p className="font-semibold">Error loading employees</p>
              <p className="text-sm opacity-80">
                {error instanceof Error ? error.message : 'Failed to load employees from API'}
              </p>
            </div>
          </div>
        </DarkCard>
      )}

      {!isLoading && !error && (
        <>
          {/* Stats */}
          <div className="grid grid-cols-5 gap-4 mb-6">
            <DarkStatCard icon={<Users size={18} />} label="Total" value={stats.total} size="sm" />
            <DarkStatCard icon={<UserCheck size={18} />} iconBg="bg-success/20" label="Active" value={stats.active} size="sm" />
            <DarkStatCard icon={<UserX size={18} />} iconBg="bg-neutral/20" label="Inactive" value={stats.inactive} size="sm" />
            <DarkStatCard icon={<Wrench size={18} />} iconBg="bg-blue/20" label="Departments" value={stats.departments} size="sm" />
            <DarkStatCard icon={<Wrench size={18} />} iconBg="bg-amber/20" label="Avg Skills" value={stats.avgSkills} size="sm" />
          </div>

          {/* Department Distribution */}
          <DarkCard className="mb-6" title="Department Distribution">
            <div className="grid grid-cols-6 gap-3">
              {departmentCounts.map(([dept, count]) => (
                <button
                  key={dept}
                  onClick={() => { setFilter(dept); setCurrentPage(1); }}
                  className={`p-3 rounded-xl border transition-all text-center ${
                    filter === dept 
                      ? 'border-accent bg-accent/10' 
                      : 'border-border-subtle hover:border-border-hover bg-bg-elevated'
                  }`}
                >
                  <p className="text-lg font-bold text-text-white">{count}</p>
                  <p className="text-xs text-text-tertiary truncate">{dept}</p>
                </button>
              ))}
            </div>
          </DarkCard>

          {/* Employee Cards */}
          <div className="grid grid-cols-3 gap-4">
            {paginatedEmployees.map((employee) => (
              <DarkCard key={employee.id} className="hover:border-border-hover transition-all">
                <div className="flex items-start gap-4 mb-4">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-semibold ${
                    employee.status === 'ACTIVE' 
                      ? 'bg-gradient-to-br from-accent to-accent-dark' 
                      : 'bg-gradient-to-br from-bg-elevated to-bg-tertiary'
                  }`}>
                    {employee.name.split(' ').slice(0, 2).map(n => n[0]).join('')}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-text-white truncate">{employee.name}</h3>
                    <p className="text-sm text-text-tertiary">{employee.department}</p>
                    <DarkBadge 
                      variant={employee.status === 'ACTIVE' ? 'success' : 'neutral'} 
                      dot 
                      size="sm"
                      className="mt-1"
                    >
                      {employee.status}
                    </DarkBadge>
                  </div>
                  <div className="flex items-center gap-1">
                    <DarkIconButton
                      icon={<Edit size={14} />}
                      size="sm"
                      variant="ghost"
                      onClick={() => { setEditingEmployee(employee); setIsFormModalOpen(true); }}
                    />
                    <DarkIconButton
                      icon={<Trash2 size={14} />}
                      size="sm"
                      variant="ghost"
                      onClick={() => { setDeletingEmployee(employee); setIsDeleteConfirmOpen(true); }}
                    />
                  </div>
                </div>
                
                <div className="space-y-3">
                  <div>
                    <p className="text-xs text-text-tertiary mb-1">Employee ID</p>
                    <p className="text-sm font-medium text-text-white">#{employee.id}</p>
                  </div>
                  
                  <div>
                    <p className="text-xs text-text-tertiary mb-1">Skills ({employee.skills.length})</p>
                    <div className="flex flex-wrap gap-1">
                      {employee.skills.slice(0, 3).map((skill) => (
                        <DarkBadge key={skill} variant="info" size="sm">
                          {skill}
                        </DarkBadge>
                      ))}
                      {employee.skills.length > 3 && (
                        <DarkBadge variant="neutral" size="sm">
                          +{employee.skills.length - 3}
                        </DarkBadge>
                      )}
                    </div>
                  </div>
                </div>
              </DarkCard>
            ))}
            {paginatedEmployees.length === 0 && (
              <div className="col-span-3">
                <DarkCard className="text-center py-12">
                  <Users size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                  <p className="font-medium text-text-secondary">No employees found</p>
                  <p className="text-sm text-text-tertiary">Try adjusting your search or filters</p>
                </DarkCard>
              </div>
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <DarkCard className="mt-6">
              <div className="flex items-center justify-between">
                <p className="text-sm text-text-tertiary">
                  Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, filteredEmployees.length)} of {filteredEmployees.length} employees
                </p>
                <div className="flex items-center gap-2">
                  <DarkButton variant="ghost" size="sm" onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}>
                    Previous
                  </DarkButton>
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    const page = currentPage <= 3 ? i + 1 : currentPage + i - 2;
                    if (page > totalPages || page < 1) return null;
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
            </DarkCard>
          )}
        </>
      )}

      <FormModal
        title={editingEmployee ? 'Edit Employee' : 'Add Employee'}
        isOpen={isFormModalOpen}
        onClose={() => { setIsFormModalOpen(false); setEditingEmployee(null); }}
        onSubmit={handleFormSubmit}
        initialData={editingEmployee ? {
          employee_code: editingEmployee.employee_code,
          employee_name: editingEmployee.name,
          department: editingEmployee.department,
          shift_pattern: editingEmployee.shift_pattern,
          status: editingEmployee.status,
        } : {}}
        fields={employeeFormFields}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      <DeleteConfirmDialog
        isOpen={isDeleteConfirmOpen}
        onClose={() => { setIsDeleteConfirmOpen(false); setDeletingEmployee(null); }}
        onConfirm={handleDeleteConfirm}
        title={deletingEmployee ? `Employee ${deletingEmployee.name}` : 'Employee'}
        message="Are you sure you want to delete this employee? This action cannot be undone."
        isLoading={deleteMutation.isPending}
      />
    </DarkPageLayout>
  );
}
