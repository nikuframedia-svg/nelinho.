import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Plus, 
  Building2,
  Edit,
  Eye,
  Power,
  PowerOff,
  CreditCard,
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
  DarkSearchInput,
  DarkSelect,
  DarkIconButton,
} from '../../components/dark';
import { FormModal, type FormField } from '../../components/ui';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogCloseButton } from '../../components/ui';
import { tenantsApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';
import { format } from 'date-fns';

interface Tenant {
  id: string;
  tenant_name: string;
  tenant_code: string;
  status: 'ACTIVE' | 'SUSPENDED' | 'PENDING' | 'CANCELLED';
  subscription_level: 'STARTER' | 'PROFESSIONAL' | 'ENTERPRISE';
  contact_email?: string | null;
  currency_code: string;
  timezone: string;
  created_at: string;
  updated_at: string;
}

const statusOptions = ['ALL', 'ACTIVE', 'SUSPENDED', 'PENDING', 'CANCELLED'] as const;
const subscriptionOptions = ['ALL', 'STARTER', 'PROFESSIONAL', 'ENTERPRISE'] as const;

export function TenantsPage() {
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToastContext();

  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [filterSubscription, setFilterSubscription] = useState<string>('ALL');
  const [search, setSearch] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isSubscriptionModalOpen, setIsSubscriptionModalOpen] = useState(false);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [subscriptionTenant, setSubscriptionTenant] = useState<Tenant | null>(null);
  const [newSubscriptionLevel, setNewSubscriptionLevel] = useState<string>('');

  // Fetch tenants from API
  const { data: tenants = [], isLoading, error } = useQuery<Tenant[]>({
    queryKey: ['tenants', filterStatus, filterSubscription],
    queryFn: () => tenantsApi.list(),
    retry: false, // Don't retry on 503 errors (DB unavailable)
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  // Filter and search
  const filteredTenants = useMemo(() => {
    return tenants.filter(t => {
      const matchesStatus = filterStatus === 'ALL' || t.status === filterStatus;
      const matchesSubscription = filterSubscription === 'ALL' || t.subscription_level === filterSubscription;
      const matchesSearch = 
        t.tenant_name.toLowerCase().includes(search.toLowerCase()) || 
        t.tenant_code.toLowerCase().includes(search.toLowerCase());
      return matchesStatus && matchesSubscription && matchesSearch;
    });
  }, [tenants, filterStatus, filterSubscription, search]);

  // Pagination
  const paginatedTenants = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredTenants.slice(start, start + itemsPerPage);
  }, [filteredTenants, currentPage]);

  const totalPages = Math.ceil(filteredTenants.length / itemsPerPage);

  // Stats
  const stats = useMemo(() => ({
    total: tenants.length,
    active: tenants.filter(t => t.status === 'ACTIVE').length,
    suspended: tenants.filter(t => t.status === 'SUSPENDED').length,
    starter: tenants.filter(t => t.subscription_level === 'STARTER').length,
    professional: tenants.filter(t => t.subscription_level === 'PROFESSIONAL').length,
    enterprise: tenants.filter(t => t.subscription_level === 'ENTERPRISE').length,
  }), [tenants]);

  // Mutations
  const createMutation = useMutation({
    mutationFn: tenantsApi.create,
    onSuccess: () => {
      success('Tenant created successfully');
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
      setIsFormModalOpen(false);
    },
    onError: (err: any) => {
      toastError(err.message || 'Error creating tenant');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => tenantsApi.update(id, data),
    onSuccess: () => {
      success('Tenant updated successfully');
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
      setIsFormModalOpen(false);
      setEditingTenant(null);
    },
    onError: (err: any) => {
      toastError(err.message || 'Error updating tenant');
    },
  });

  const activateMutation = useMutation({
    mutationFn: tenantsApi.activate,
    onSuccess: () => {
      success('Tenant activated successfully');
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
    },
    onError: (err: any) => {
      toastError(err.message || 'Error activating tenant');
    },
  });

  const suspendMutation = useMutation({
    mutationFn: tenantsApi.suspend,
    onSuccess: () => {
      success('Tenant suspended successfully');
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
    },
    onError: (err: any) => {
      toastError(err.message || 'Error suspending tenant');
    },
  });

  const updateSubscriptionMutation = useMutation({
    mutationFn: ({ id, level }: { id: string; level: string }) => tenantsApi.updateSubscription(id, level),
    onSuccess: () => {
      success('Subscription updated successfully');
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
      setIsSubscriptionModalOpen(false);
      setSubscriptionTenant(null);
    },
    onError: (err: any) => {
      toastError(err.message || 'Error updating subscription');
    },
  });

  const tenantFormFields: FormField[] = [
    { name: 'tenant_name', label: 'Tenant Name', type: 'text', required: true },
    { name: 'tenant_code', label: 'Tenant Code', type: 'text', required: true },
    { name: 'contact_email', label: 'Contact Email', type: 'email' },
    { name: 'currency_code', label: 'Currency Code', type: 'text', defaultValue: 'EUR' },
    { name: 'timezone', label: 'Timezone', type: 'text', defaultValue: 'UTC' },
    {
      name: 'subscription_level',
      label: 'Subscription Level',
      type: 'select',
      options: [
        { value: 'STARTER', label: 'Starter' },
        { value: 'PROFESSIONAL', label: 'Professional' },
        { value: 'ENTERPRISE', label: 'Enterprise' },
      ],
      defaultValue: 'STARTER',
    },
  ];

  const handleFormSubmit = (data: Record<string, any>) => {
    const payload = {
      tenant_name: data.tenant_name,
      tenant_code: data.tenant_code,
      contact_email: data.contact_email || null,
      currency_code: data.currency_code || 'EUR',
      timezone: data.timezone || 'UTC',
      subscription_level: data.subscription_level,
    };

    if (editingTenant) {
      updateMutation.mutate({ id: editingTenant.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const handleSubscriptionUpdate = () => {
    if (subscriptionTenant && newSubscriptionLevel) {
      updateSubscriptionMutation.mutate({ id: subscriptionTenant.id, level: newSubscriptionLevel });
    }
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'success';
      case 'SUSPENDED': return 'danger';
      case 'PENDING': return 'warning';
      case 'CANCELLED': return 'neutral';
      default: return 'neutral';
    }
  };

  const getSubscriptionBadgeVariant = (level: string) => {
    switch (level) {
      case 'STARTER': return 'info';
      case 'PROFESSIONAL': return 'accent';
      case 'ENTERPRISE': return 'warning';
      default: return 'neutral';
    }
  };

  return (
    <DarkPageLayout
      title="Tenants Management"
      subtitle={isLoading ? 'Loading...' : `${tenants.length} tenants registered`}
      icon={<Building2 size={20} />}
      actions={
        <DarkButton
          icon={<Plus size={18} />}
          onClick={() => {
            setEditingTenant(null);
            setIsFormModalOpen(true);
          }}
        >
          Add Tenant
        </DarkButton>
      }
    >
      {/* Filters */}
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <DarkSearchInput
          placeholder="Search tenants..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
          onClear={() => setSearch('')}
          containerClassName="w-72"
        />
        
        {/* Status filters */}
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {statusOptions.map((status) => (
            <DarkPillButton
              key={status}
              active={filterStatus === status}
              onClick={() => { setFilterStatus(status); setCurrentPage(1); }}
            >
              {status}
            </DarkPillButton>
          ))}
        </div>

        {/* Subscription filters */}
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {subscriptionOptions.map((sub) => (
            <DarkPillButton
              key={sub}
              active={filterSubscription === sub}
              onClick={() => { setFilterSubscription(sub); setCurrentPage(1); }}
            >
              {sub}
            </DarkPillButton>
          ))}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-6 gap-4 mb-6">
        <DarkStatCard icon={<Building2 size={18} />} label="Total" value={stats.total} size="sm" />
        <DarkStatCard icon={<Building2 size={18} />} iconBg="bg-success/20" label="Active" value={stats.active} size="sm" />
        <DarkStatCard icon={<Building2 size={18} />} iconBg="bg-danger/20" label="Suspended" value={stats.suspended} size="sm" />
        <DarkStatCard icon={<Building2 size={18} />} iconBg="bg-blue/20" label="Starter" value={stats.starter} size="sm" />
        <DarkStatCard icon={<Building2 size={18} />} iconBg="bg-purple/20" label="Professional" value={stats.professional} size="sm" />
        <DarkStatCard icon={<Building2 size={18} />} iconBg="bg-amber/20" label="Enterprise" value={stats.enterprise} size="sm" />
      </div>

      {/* Error State */}
      {error && (
        <DarkCard className="mb-6 border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertCircle size={20} />
            <div>
              <p className="font-semibold">Error loading tenants</p>
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
            <p>Loading tenants...</p>
          </div>
        </DarkCard>
      )}

      {/* Table */}
      {!isLoading && !error && (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Tenant Name</DarkTableHeader>
                <DarkTableHeader>Code</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
                <DarkTableHeader>Subscription</DarkTableHeader>
                <DarkTableHeader>Currency/Timezone</DarkTableHeader>
                <DarkTableHeader>Created Date</DarkTableHeader>
                <DarkTableHeader align="right">Actions</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {paginatedTenants.map((tenant) => (
                <DarkTableRow key={tenant.id}>
                  <DarkTableCell>
                    <div>
                      <p className="font-semibold text-text-white text-sm">{tenant.tenant_name}</p>
                      {tenant.contact_email && (
                        <p className="text-xs text-text-tertiary">{tenant.contact_email}</p>
                      )}
                    </div>
                  </DarkTableCell>
                  <DarkTableCell>
                    <code className="text-xs text-text-tertiary font-mono">{tenant.tenant_code}</code>
                  </DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={getStatusBadgeVariant(tenant.status)} dot>
                      {tenant.status}
                    </DarkBadge>
                  </DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={getSubscriptionBadgeVariant(tenant.subscription_level)}>
                      {tenant.subscription_level}
                    </DarkBadge>
                  </DarkTableCell>
                  <DarkTableCell>{tenant.currency_code} / {tenant.timezone}</DarkTableCell>
                  <DarkTableCell>{format(new Date(tenant.created_at), 'dd MMM yyyy')}</DarkTableCell>
                  <DarkTableCell align="right">
                    <div className="flex items-center justify-end gap-1">
                      <DarkIconButton icon={<Eye size={16} />} size="sm" variant="ghost" />
                      <DarkIconButton
                        icon={<Edit size={16} />}
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setEditingTenant(tenant);
                          setIsFormModalOpen(true);
                        }}
                      />
                      {tenant.status !== 'ACTIVE' && (
                        <DarkIconButton
                          icon={<Power size={16} />}
                          size="sm"
                          variant="ghost"
                          onClick={() => activateMutation.mutate(tenant.id)}
                        />
                      )}
                      {tenant.status === 'ACTIVE' && (
                        <DarkIconButton
                          icon={<PowerOff size={16} />}
                          size="sm"
                          variant="ghost"
                          onClick={() => suspendMutation.mutate(tenant.id)}
                        />
                      )}
                      <DarkIconButton
                        icon={<CreditCard size={16} />}
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setSubscriptionTenant(tenant);
                          setNewSubscriptionLevel(tenant.subscription_level);
                          setIsSubscriptionModalOpen(true);
                        }}
                      />
                    </div>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {paginatedTenants.length === 0 && (
                <DarkTableRow>
                  <DarkTableCell colSpan={7} className="text-center py-12">
                    <Building2 size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                    <p className="font-medium text-text-secondary">No tenants found</p>
                    <p className="text-sm text-text-tertiary">Try adjusting your search or filters</p>
                  </DarkTableCell>
                </DarkTableRow>
              )}
            </DarkTableBody>
          </DarkTable>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-border-subtle">
              <p className="text-sm text-text-tertiary">
                Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, filteredTenants.length)} of {filteredTenants.length} results
              </p>
              <div className="flex items-center gap-2">
                <DarkButton
                  variant="ghost"
                  size="sm"
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
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
                        currentPage === page 
                          ? 'bg-accent text-bg-base' 
                          : 'text-text-secondary hover:bg-bg-elevated'
                      }`}
                    >
                      {page}
                    </button>
                  );
                })}
                <DarkButton
                  variant="ghost"
                  size="sm"
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                </DarkButton>
              </div>
            </div>
          )}
        </DarkCard>
      )}

      {/* Form Modal */}
      <FormModal
        title={editingTenant ? 'Edit Tenant' : 'Add Tenant'}
        isOpen={isFormModalOpen}
        onClose={() => {
          setIsFormModalOpen(false);
          setEditingTenant(null);
        }}
        onSubmit={handleFormSubmit}
        initialData={editingTenant ? {
          tenant_name: editingTenant.tenant_name,
          tenant_code: editingTenant.tenant_code,
          contact_email: editingTenant.contact_email,
          currency_code: editingTenant.currency_code,
          timezone: editingTenant.timezone,
          subscription_level: editingTenant.subscription_level,
        } : {}}
        fields={tenantFormFields}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Subscription Update Modal */}
      <Dialog open={isSubscriptionModalOpen} onOpenChange={() => setIsSubscriptionModalOpen(false)}>
        <DialogContent className="max-w-sm bg-bg-card border-border-subtle">
          <DialogHeader>
            <DialogTitle className="text-text-white">Update Subscription</DialogTitle>
            <DialogCloseButton onClose={() => setIsSubscriptionModalOpen(false)} />
          </DialogHeader>
          <div className="p-6 flex flex-col gap-4">
            <p className="text-sm text-text-secondary">
              Update subscription level for <strong className="text-text-white">{subscriptionTenant?.tenant_name}</strong>
            </p>
            <DarkSelect
              options={[
                { value: 'STARTER', label: 'Starter' },
                { value: 'PROFESSIONAL', label: 'Professional' },
                { value: 'ENTERPRISE', label: 'Enterprise' },
              ]}
              value={newSubscriptionLevel}
              onChange={(e) => setNewSubscriptionLevel(e.target.value)}
            />
            <div className="flex justify-end gap-3 mt-2">
              <DarkButton
                variant="secondary"
                onClick={() => setIsSubscriptionModalOpen(false)}
                disabled={updateSubscriptionMutation.isPending}
              >
                Cancel
              </DarkButton>
              <DarkButton
                onClick={handleSubscriptionUpdate}
                loading={updateSubscriptionMutation.isPending}
              >
                Update
              </DarkButton>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </DarkPageLayout>
  );
}
