import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Truck, Plus, Edit, Trash2, Loader2, Star } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkBadge, DarkSearchInput, DarkIconButton } from '../../components/dark';
import { FormModal, DeleteConfirmDialog, type FormField } from '../../components/ui';
import { suppliersApi } from '../../lib/api';
import type { Supplier } from '../../types';
import { useToastContext } from '../../components/ToastProvider';

const materialCategoryOptions = ['STEEL', 'WOOD', 'PACKAGING', 'CONSUMABLES', 'COMPONENTS', 'OTHER'];
const paymentTermsOptions = ['PREPAID', 'NET15', 'NET30', 'NET45', 'NET60', 'NET90'];

export function SuppliersPage() {
  const [filterCategory, setFilterCategory] = useState<string>('ALL');
  const [filterActive, setFilterActive] = useState<string>('ALL');
  const [filterPreferred, setFilterPreferred] = useState<string>('ALL');
  const [search, setSearch] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [deletingSupplierId, setDeletingSupplierId] = useState<string | null>(null);
  const itemsPerPage = 20;
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: suppliers = [], isLoading, error } = useQuery<Supplier[]>({
    queryKey: ['suppliers', 'list'],
    queryFn: () => suppliersApi.list({ limit: 1000 }),
  });

  const filteredSuppliers = useMemo(() => {
    return suppliers.filter(s => {
      const matchesCategory = filterCategory === 'ALL' || s.material_category === filterCategory;
      const matchesActive = filterActive === 'ALL' || (filterActive === 'ACTIVE' && s.is_active) || (filterActive === 'INACTIVE' && !s.is_active);
      const matchesPreferred = filterPreferred === 'ALL' || (filterPreferred === 'PREFERRED' && s.is_preferred) || (filterPreferred === 'NOT_PREFERRED' && !s.is_preferred);
      const matchesSearch = s.supplier_name.toLowerCase().includes(search.toLowerCase()) || s.supplier_code.toLowerCase().includes(search.toLowerCase());
      return matchesCategory && matchesActive && matchesPreferred && matchesSearch;
    });
  }, [suppliers, filterCategory, filterActive, filterPreferred, search]);

  const paginatedSuppliers = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredSuppliers.slice(start, start + itemsPerPage);
  }, [filteredSuppliers, currentPage]);

  const totalPages = Math.ceil(filteredSuppliers.length / itemsPerPage);

  const stats = useMemo(() => ({
    total: suppliers.length,
    active: suppliers.filter(s => s.is_active).length,
    inactive: suppliers.filter(s => !s.is_active).length,
    preferred: suppliers.filter(s => s.is_preferred).length,
    steel: suppliers.filter(s => s.material_category === 'STEEL').length,
    components: suppliers.filter(s => s.material_category === 'COMPONENTS').length,
  }), [suppliers]);

  const createMutation = useMutation({ mutationFn: (data: any) => suppliersApi.create(data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['suppliers'] }); setIsCreateModalOpen(false); toast.success('Supplier created'); }, onError: (error: any) => toast.error(error.message || 'Error') });
  const updateMutation = useMutation({ mutationFn: ({ id, data }: { id: string; data: any }) => suppliersApi.update(id, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['suppliers'] }); setIsEditModalOpen(false); setEditingSupplier(null); toast.success('Supplier updated'); }, onError: (error: any) => toast.error(error.message || 'Error') });
  const deleteMutation = useMutation({ mutationFn: (id: string) => suppliersApi.delete(id), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['suppliers'] }); setIsDeleteModalOpen(false); setDeletingSupplierId(null); toast.success('Supplier deleted'); }, onError: (error: any) => toast.error(error.message || 'Error') });

  const supplierFields: FormField[] = [
    { name: 'supplier_code', label: 'Supplier Code', type: 'text', required: true },
    { name: 'supplier_name', label: 'Supplier Name', type: 'text', required: true },
    { name: 'material_category', label: 'Material Category', type: 'select', required: true, options: materialCategoryOptions.map(c => ({ value: c, label: c })) },
    { name: 'lead_time_days', label: 'Lead Time (days)', type: 'number', min: 0, required: true },
    { name: 'payment_terms', label: 'Payment Terms', type: 'select', required: true, options: paymentTermsOptions.map(t => ({ value: t, label: t })) },
    { name: 'contact_name', label: 'Contact Name', type: 'text' },
    { name: 'contact_email', label: 'Contact Email', type: 'email' },
    { name: 'quality_rating', label: 'Quality Rating (1-5)', type: 'number', min: 1, max: 5 },
    { name: 'is_active', label: 'Active', type: 'checkbox' },
    { name: 'is_preferred', label: 'Preferred', type: 'checkbox' },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ];

  if (error) return <DarkPageLayout title="Suppliers" icon={<Truck size={20} />}><DarkCard className="border-danger/30 bg-danger/10"><p className="text-danger-light">Error: {(error as Error).message}</p></DarkCard></DarkPageLayout>;

  return (
    <DarkPageLayout
      title="Suppliers"
      subtitle={isLoading ? 'Loading...' : `${suppliers.length} suppliers registered`}
      icon={<Truck size={20} />}
      actions={<DarkButton icon={<Plus size={18} />} onClick={() => setIsCreateModalOpen(true)}>Add Supplier</DarkButton>}
    >
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <DarkSearchInput placeholder="Search suppliers..." value={search} onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }} onClear={() => setSearch('')} containerClassName="w-72" />
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1 overflow-x-auto">
          {['ALL', ...materialCategoryOptions].map((cat) => (
            <DarkPillButton key={cat} active={filterCategory === cat} onClick={() => { setFilterCategory(cat); setCurrentPage(1); }}>{cat}</DarkPillButton>
          ))}
        </div>
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'ACTIVE', 'INACTIVE'].map((st) => (
            <DarkPillButton key={st} active={filterActive === st} onClick={() => { setFilterActive(st); setCurrentPage(1); }}>{st}</DarkPillButton>
          ))}
        </div>
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'PREFERRED', 'NOT_PREFERRED'].map((pref) => (
            <DarkPillButton key={pref} active={filterPreferred === pref} onClick={() => { setFilterPreferred(pref); setCurrentPage(1); }}>{pref === 'NOT_PREFERRED' ? 'Not Pref' : pref}</DarkPillButton>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-6 gap-4 mb-6">
        <DarkStatCard icon={<Truck size={18} />} label="Total" value={stats.total} size="sm" />
        <DarkStatCard icon={<Truck size={18} />} iconBg="bg-success/20" label="Active" value={stats.active} size="sm" />
        <DarkStatCard icon={<Truck size={18} />} iconBg="bg-danger/20" label="Inactive" value={stats.inactive} size="sm" />
        <DarkStatCard icon={<Star size={18} />} iconBg="bg-amber/20" label="Preferred" value={stats.preferred} size="sm" />
        <DarkStatCard icon={<Truck size={18} />} iconBg="bg-blue/20" label="Steel" value={stats.steel} size="sm" />
        <DarkStatCard icon={<Truck size={18} />} iconBg="bg-purple/20" label="Components" value={stats.components} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Supplier</DarkTableHeader>
                <DarkTableHeader>Code</DarkTableHeader>
                <DarkTableHeader>Category</DarkTableHeader>
                <DarkTableHeader>Lead Time</DarkTableHeader>
                <DarkTableHeader>Quality</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
                <DarkTableHeader align="right">Actions</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {paginatedSuppliers.map((supplier) => (
                <DarkTableRow key={supplier.id}>
                  <DarkTableCell>
                    <div className="flex items-center gap-2">
                      <div><p className="font-semibold text-text-white text-sm">{supplier.supplier_name}</p>{supplier.contact_email && <p className="text-xs text-text-tertiary">{supplier.contact_email}</p>}</div>
                      {supplier.is_preferred && <Star size={16} className="text-amber fill-amber" />}
                    </div>
                  </DarkTableCell>
                  <DarkTableCell mono className="text-text-tertiary">{supplier.supplier_code}</DarkTableCell>
                  <DarkTableCell><DarkBadge variant="info">{supplier.material_category}</DarkBadge></DarkTableCell>
                  <DarkTableCell>{supplier.lead_time_days} days</DarkTableCell>
                  <DarkTableCell>
                    {supplier.quality_rating ? (
                      <div className="flex items-center gap-0.5">
                        {Array.from({ length: 5 }, (_, i) => (
                          <Star key={i} size={12} className={i < supplier.quality_rating! ? 'text-amber fill-amber' : 'text-text-tertiary'} />
                        ))}
                      </div>
                    ) : <span className="text-xs text-text-tertiary">N/A</span>}
                  </DarkTableCell>
                  <DarkTableCell><DarkBadge variant={supplier.is_active ? 'success' : 'neutral'} dot>{supplier.is_active ? 'Active' : 'Inactive'}</DarkBadge></DarkTableCell>
                  <DarkTableCell align="right">
                    <div className="flex items-center justify-end gap-1">
                      <DarkIconButton icon={<Edit size={16} />} size="sm" variant="ghost" onClick={() => { setEditingSupplier(supplier); setIsEditModalOpen(true); }} />
                      <DarkIconButton icon={<Trash2 size={16} />} size="sm" variant="ghost" onClick={() => { setDeletingSupplierId(supplier.id); setIsDeleteModalOpen(true); }} />
                    </div>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {paginatedSuppliers.length === 0 && <DarkTableRow><DarkTableCell colSpan={7} className="text-center py-12"><Truck size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No suppliers found</p></DarkTableCell></DarkTableRow>}
            </DarkTableBody>
          </DarkTable>
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-border-subtle">
              <p className="text-sm text-text-tertiary">Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, filteredSuppliers.length)} of {filteredSuppliers.length}</p>
              <div className="flex items-center gap-2">
                <DarkButton variant="ghost" size="sm" onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}>Previous</DarkButton>
                <DarkButton variant="ghost" size="sm" onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages}>Next</DarkButton>
              </div>
            </div>
          )}
        </DarkCard>
      )}

      <FormModal title="Add Supplier" isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} onSubmit={(data) => createMutation.mutate(data)} fields={supplierFields} isLoading={createMutation.isPending} />
      {editingSupplier && <FormModal title="Edit Supplier" isOpen={isEditModalOpen} onClose={() => { setIsEditModalOpen(false); setEditingSupplier(null); }} onSubmit={(data) => updateMutation.mutate({ id: editingSupplier.id, data })} initialData={editingSupplier} fields={supplierFields} isLoading={updateMutation.isPending} />}
      <DeleteConfirmDialog isOpen={isDeleteModalOpen} onClose={() => { setIsDeleteModalOpen(false); setDeletingSupplierId(null); }} onConfirm={() => { if (deletingSupplierId) deleteMutation.mutate(deletingSupplierId); }} title="Delete Supplier" message="Are you sure?" isLoading={deleteMutation.isPending} />
    </DarkPageLayout>
  );
}
