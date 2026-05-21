import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Users, Plus, Edit, Trash2, Loader2 } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkBadge, DarkSearchInput, DarkIconButton } from '../../components/dark';
import { FormModal, DeleteConfirmDialog, type FormField } from '../../components/ui';
import { customersApi } from '../../lib/api';
import type { Customer } from '../../types';
import type { MutationError, MutationPayload } from '../../lib/api-helpers';
import { useToastContext } from '../../components/ToastProvider';

const segmentOptions = ['RETAIL', 'WHOLESALE', 'BULK', 'OEM', 'DISTRIBUTOR'];
const priceTierOptions = ['ECONOMY', 'STANDARD', 'PREMIUM', 'VIP'];
const paymentTermsOptions = ['PREPAID', 'NET15', 'NET30', 'NET45', 'NET60', 'NET90'];

export function CustomersPage() {
  const [filterSegment, setFilterSegment] = useState<string>('ALL');
  const [filterActive, setFilterActive] = useState<string>('ALL');
  const [search, setSearch] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [deletingCustomerId, setDeletingCustomerId] = useState<string | null>(null);
  const itemsPerPage = 20;
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: customers = [], isLoading, error } = useQuery<Customer[]>({
    queryKey: ['customers', 'list'],
    queryFn: () => customersApi.list({ limit: 1000 }),
  });

  const filteredCustomers = useMemo(() => {
    return customers.filter(c => {
      const matchesSegment = filterSegment === 'ALL' || c.segment === filterSegment;
      const matchesActive = filterActive === 'ALL' || (filterActive === 'ACTIVE' && c.is_active) || (filterActive === 'INACTIVE' && !c.is_active);
      const matchesSearch = c.customer_name.toLowerCase().includes(search.toLowerCase()) || c.customer_code.toLowerCase().includes(search.toLowerCase());
      return matchesSegment && matchesActive && matchesSearch;
    });
  }, [customers, filterSegment, filterActive, search]);

  const paginatedCustomers = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredCustomers.slice(start, start + itemsPerPage);
  }, [filteredCustomers, currentPage]);

  const totalPages = Math.ceil(filteredCustomers.length / itemsPerPage);

  const stats = useMemo(() => ({
    total: customers.length,
    active: customers.filter(c => c.is_active).length,
    inactive: customers.filter(c => !c.is_active).length,
    retail: customers.filter(c => c.segment === 'RETAIL').length,
    wholesale: customers.filter(c => c.segment === 'WHOLESALE').length,
    premium: customers.filter(c => c.price_tier === 'PREMIUM' || c.price_tier === 'VIP').length,
  }), [customers]);

  const createMutation = useMutation({
    mutationFn: (data: MutationPayload) => customersApi.create(data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['customers'] }); setIsCreateModalOpen(false); toast.success('Customer created'); },
    onError: (error: MutationError) => toast.error(error.message || 'Error'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: MutationPayload }) => customersApi.update(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['customers'] }); setIsEditModalOpen(false); setEditingCustomer(null); toast.success('Customer updated'); },
    onError: (error: MutationError) => toast.error(error.message || 'Error'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => customersApi.delete(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['customers'] }); setIsDeleteModalOpen(false); setDeletingCustomerId(null); toast.success('Customer deleted'); },
    onError: (error: MutationError) => toast.error(error.message || 'Error'),
  });

  const customerFields: FormField[] = [
    { name: 'customer_code', label: 'Customer Code', type: 'text', required: true },
    { name: 'customer_name', label: 'Customer Name', type: 'text', required: true },
    { name: 'segment', label: 'Segment', type: 'select', required: true, options: segmentOptions.map(s => ({ value: s, label: s })) },
    { name: 'payment_terms', label: 'Payment Terms', type: 'select', required: true, options: paymentTermsOptions.map(t => ({ value: t, label: t })) },
    { name: 'price_tier', label: 'Price Tier', type: 'select', required: true, options: priceTierOptions.map(t => ({ value: t, label: t })) },
    { name: 'credit_limit', label: 'Credit Limit', type: 'number', min: 0 },
    { name: 'contact_email', label: 'Contact Email', type: 'email' },
    { name: 'is_active', label: 'Active', type: 'checkbox' },
  ];

  if (error) return <DarkPageLayout title="Customers" icon={<Users size={20} />}><DarkCard className="border-danger/30 bg-danger/10"><p className="text-danger-light">Error: {(error as Error).message}</p></DarkCard></DarkPageLayout>;

  return (
    <DarkPageLayout
      title="Customers"
      subtitle={isLoading ? 'Loading...' : `${customers.length} customers registered`}
      icon={<Users size={20} />}
      actions={<DarkButton icon={<Plus size={18} />} onClick={() => setIsCreateModalOpen(true)}>Add Customer</DarkButton>}
    >
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <DarkSearchInput placeholder="Search customers..." value={search} onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }} onClear={() => setSearch('')} containerClassName="w-72" />
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', ...segmentOptions].map((segment) => (
            <DarkPillButton key={segment} active={filterSegment === segment} onClick={() => { setFilterSegment(segment); setCurrentPage(1); }}>{segment}</DarkPillButton>
          ))}
        </div>
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'ACTIVE', 'INACTIVE'].map((status) => (
            <DarkPillButton key={status} active={filterActive === status} onClick={() => { setFilterActive(status); setCurrentPage(1); }}>{status}</DarkPillButton>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-6 gap-4 mb-6">
        <DarkStatCard icon={<Users size={18} />} label="Total" value={stats.total} size="sm" />
        <DarkStatCard icon={<Users size={18} />} iconBg="bg-success/20" label="Active" value={stats.active} size="sm" />
        <DarkStatCard icon={<Users size={18} />} iconBg="bg-danger/20" label="Inactive" value={stats.inactive} size="sm" />
        <DarkStatCard icon={<Users size={18} />} iconBg="bg-blue/20" label="Retail" value={stats.retail} size="sm" />
        <DarkStatCard icon={<Users size={18} />} iconBg="bg-purple/20" label="Wholesale" value={stats.wholesale} size="sm" />
        <DarkStatCard icon={<Users size={18} />} iconBg="bg-amber/20" label="Premium/VIP" value={stats.premium} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Customer</DarkTableHeader>
                <DarkTableHeader>Code</DarkTableHeader>
                <DarkTableHeader>Segment</DarkTableHeader>
                <DarkTableHeader>Price Tier</DarkTableHeader>
                <DarkTableHeader>Payment</DarkTableHeader>
                <DarkTableHeader>Credit Limit</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
                <DarkTableHeader align="right">Actions</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {paginatedCustomers.map((customer) => (
                <DarkTableRow key={customer.id}>
                  <DarkTableCell><div><p className="font-semibold text-text-white text-sm">{customer.customer_name}</p>{customer.contact_email && <p className="text-xs text-text-tertiary">{customer.contact_email}</p>}</div></DarkTableCell>
                  <DarkTableCell mono className="text-text-tertiary">{customer.customer_code}</DarkTableCell>
                  <DarkTableCell><DarkBadge variant="info">{customer.segment}</DarkBadge></DarkTableCell>
                  <DarkTableCell><DarkBadge variant="accent">{customer.price_tier}</DarkBadge></DarkTableCell>
                  <DarkTableCell>{customer.payment_terms}</DarkTableCell>
                  <DarkTableCell mono>{customer.credit_limit ? `€${customer.credit_limit.toLocaleString()}` : '-'}</DarkTableCell>
                  <DarkTableCell><DarkBadge variant={customer.is_active ? 'success' : 'neutral'} dot>{customer.is_active ? 'Active' : 'Inactive'}</DarkBadge></DarkTableCell>
                  <DarkTableCell align="right">
                    <div className="flex items-center justify-end gap-1">
                      <DarkIconButton icon={<Edit size={16} />} size="sm" variant="ghost" onClick={() => { setEditingCustomer(customer); setIsEditModalOpen(true); }} />
                      <DarkIconButton icon={<Trash2 size={16} />} size="sm" variant="ghost" onClick={() => { setDeletingCustomerId(customer.id); setIsDeleteModalOpen(true); }} />
                    </div>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {paginatedCustomers.length === 0 && <DarkTableRow><DarkTableCell colSpan={8} className="text-center py-12"><Users size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No customers found</p></DarkTableCell></DarkTableRow>}
            </DarkTableBody>
          </DarkTable>
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-border-subtle">
              <p className="text-sm text-text-tertiary">Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, filteredCustomers.length)} of {filteredCustomers.length}</p>
              <div className="flex items-center gap-2">
                <DarkButton variant="ghost" size="sm" onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}>Previous</DarkButton>
                <DarkButton variant="ghost" size="sm" onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages}>Next</DarkButton>
              </div>
            </div>
          )}
        </DarkCard>
      )}

      <FormModal title="Add Customer" isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} onSubmit={(data) => createMutation.mutate(data)} fields={customerFields} isLoading={createMutation.isPending} />
      {editingCustomer && <FormModal title="Edit Customer" isOpen={isEditModalOpen} onClose={() => { setIsEditModalOpen(false); setEditingCustomer(null); }} onSubmit={(data) => updateMutation.mutate({ id: editingCustomer.id, data })} initialData={editingCustomer} fields={customerFields} isLoading={updateMutation.isPending} />}
      <DeleteConfirmDialog isOpen={isDeleteModalOpen} onClose={() => { setIsDeleteModalOpen(false); setDeletingCustomerId(null); }} onConfirm={() => { if (deletingCustomerId) deleteMutation.mutate(deletingCustomerId); }} title="Delete Customer" message="Are you sure?" isLoading={deleteMutation.isPending} />
    </DarkPageLayout>
  );
}
