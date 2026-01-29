import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Package, Loader2, AlertCircle, Plus, Edit, Trash2 } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkSearchInput, DarkSelect, DarkIconButton } from '../../components/dark';
import { FormModal, DeleteConfirmDialog, type FormField } from '../../components/ui';
import { bomApi, productsApi } from '../../lib/api';
import type { BOMItem } from '../../types';
import { useToastContext } from '../../components/ToastProvider';

export function BOMPage() {
  const [selectedProductId, setSelectedProductId] = useState<string>('');
  const [search, setSearch] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<BOMItem | null>(null);
  const [deletingItemId, setDeletingItemId] = useState<string | null>(null);
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: products = [], isLoading: productsLoading } = useQuery({
    queryKey: ['products', 'list'],
    queryFn: () => productsApi.list({ limit: 1000 }),
  });

  const { data: bomItems = [], isLoading: bomLoading, error } = useQuery<BOMItem[]>({
    queryKey: ['bom', selectedProductId],
    queryFn: () => bomApi.getByProduct(selectedProductId),
    enabled: !!selectedProductId,
  });

  const { data: allProducts = [] } = useQuery({
    queryKey: ['products', 'all'],
    queryFn: () => productsApi.list({ limit: 1000 }),
  });

  const filteredBomItems = useMemo(() => {
    if (!selectedProductId) return [];
    return bomItems.filter(item => {
      const componentProduct = allProducts.find((p: any) => p.id === item.component_product_id);
      const componentName = componentProduct?.product_name || item.component_product_id;
      return componentName.toLowerCase().includes(search.toLowerCase());
    });
  }, [bomItems, search, allProducts, selectedProductId]);

  const selectedProduct = useMemo(() => products.find((p: any) => p.id === selectedProductId), [products, selectedProductId]);

  const createMutation = useMutation({
    mutationFn: (data: any) => bomApi.create(data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['bom', selectedProductId] }); setIsCreateModalOpen(false); toast.success('BOM item added'); },
    onError: (error: any) => toast.error(error.message || 'Error'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => bomApi.update(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['bom', selectedProductId] }); setIsEditModalOpen(false); setEditingItem(null); toast.success('BOM item updated'); },
    onError: (error: any) => toast.error(error.message || 'Error'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => bomApi.delete(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['bom', selectedProductId] }); setIsDeleteModalOpen(false); setDeletingItemId(null); toast.success('BOM item deleted'); },
    onError: (error: any) => toast.error(error.message || 'Error'),
  });

  const bomFields: FormField[] = [
    { name: 'component_product_id', label: 'Component', type: 'select', required: true, options: allProducts.map((p: any) => ({ value: p.id, label: `${p.product_code} - ${p.product_name}` })) },
    { name: 'quantity_per', label: 'Quantity', type: 'number', required: true, min: 0, step: 0.01 },
    { name: 'unit_of_measure', label: 'Unit', type: 'text', placeholder: 'UN' },
    { name: 'sequence', label: 'Sequence', type: 'number', min: 0 },
    { name: 'scrap_factor', label: 'Scrap Factor', type: 'number', min: 1, step: 0.01, placeholder: '1.0' },
    { name: 'bom_version', label: 'BOM Version', type: 'number', min: 1 },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ];

  const productOptions = products.map((p: any) => ({ value: p.id, label: `${p.product_code} - ${p.product_name}` }));

  return (
    <DarkPageLayout
      title="Bill of Materials"
      subtitle={selectedProduct ? `BOM for ${selectedProduct.product_name || selectedProduct.product_code}` : 'Select a product to view BOM'}
      icon={<Package size={20} />}
      actions={selectedProductId && (
        <DarkButton icon={<Plus size={18} />} onClick={() => setIsCreateModalOpen(true)} disabled={productsLoading}>
          Add Item
        </DarkButton>
      )}
    >
      <div className="flex items-center gap-4 mb-6">
        <DarkSelect
          options={[{ value: '', label: 'Select a product...' }, ...productOptions]}
          value={selectedProductId}
          onChange={(e) => { setSelectedProductId(e.target.value); setSearch(''); }}
          containerClassName="w-80"
        />
        
        {selectedProductId && (
          <DarkSearchInput
            placeholder="Search components..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onClear={() => setSearch('')}
            containerClassName="flex-1 max-w-md"
          />
        )}
      </div>

      {!selectedProductId ? (
        <DarkCard className="text-center py-12">
          <Package size={48} className="mx-auto mb-3 text-text-tertiary opacity-50" />
          <p className="font-medium text-text-secondary">No product selected</p>
          <p className="text-sm text-text-tertiary">Select a product above to view its Bill of Materials</p>
        </DarkCard>
      ) : bomLoading ? (
        <DarkCard className="text-center py-12">
          <Loader2 className="animate-spin mx-auto text-accent" size={32} />
        </DarkCard>
      ) : error ? (
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertCircle size={20} />
            <div><p className="font-medium">Error loading BOM</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      ) : filteredBomItems.length === 0 ? (
        <DarkCard className="text-center py-12">
          <Package size={48} className="mx-auto mb-3 text-text-tertiary opacity-50" />
          <p className="font-medium text-text-secondary">No BOM items</p>
          <p className="text-sm text-text-tertiary">This product has no components. Click 'Add Item' to start.</p>
        </DarkCard>
      ) : (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Sequence</DarkTableHeader>
                <DarkTableHeader>Component</DarkTableHeader>
                <DarkTableHeader>Quantity</DarkTableHeader>
                <DarkTableHeader>Unit</DarkTableHeader>
                <DarkTableHeader>Scrap Factor</DarkTableHeader>
                <DarkTableHeader>Version</DarkTableHeader>
                <DarkTableHeader align="right">Actions</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredBomItems.map((item) => {
                const componentProduct = allProducts.find((p: any) => p.id === item.component_product_id);
                return (
                  <DarkTableRow key={item.id}>
                    <DarkTableCell mono>{item.sequence}</DarkTableCell>
                    <DarkTableCell className="text-text-white">{componentProduct ? `${componentProduct.product_code} - ${componentProduct.product_name}` : item.component_product_id}</DarkTableCell>
                    <DarkTableCell mono>{item.quantity_per}</DarkTableCell>
                    <DarkTableCell>{item.unit_of_measure || 'UN'}</DarkTableCell>
                    <DarkTableCell mono>{item.scrap_factor}</DarkTableCell>
                    <DarkTableCell>{item.bom_version}</DarkTableCell>
                    <DarkTableCell align="right">
                      <div className="flex items-center justify-end gap-1">
                        <DarkIconButton icon={<Edit size={16} />} size="sm" variant="ghost" onClick={() => { setEditingItem(item); setIsEditModalOpen(true); }} />
                        <DarkIconButton icon={<Trash2 size={16} />} size="sm" variant="ghost" onClick={() => { setDeletingItemId(item.id); setIsDeleteModalOpen(true); }} />
                      </div>
                    </DarkTableCell>
                  </DarkTableRow>
                );
              })}
            </DarkTableBody>
          </DarkTable>
        </DarkCard>
      )}

      <FormModal title="Add BOM Item" isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} onSubmit={(data) => createMutation.mutate({ parent_product_id: selectedProductId, ...data })} fields={bomFields} isLoading={createMutation.isPending} />
      {editingItem && <FormModal title="Edit BOM Item" isOpen={isEditModalOpen} onClose={() => { setIsEditModalOpen(false); setEditingItem(null); }} onSubmit={(data) => updateMutation.mutate({ id: editingItem.id, data })} initialData={editingItem} fields={bomFields} isLoading={updateMutation.isPending} />}
      <DeleteConfirmDialog isOpen={isDeleteModalOpen} onClose={() => { setIsDeleteModalOpen(false); setDeletingItemId(null); }} onConfirm={() => { if (deletingItemId) deleteMutation.mutate(deletingItemId); }} title="Delete BOM Item" message="Are you sure?" isLoading={deleteMutation.isPending} />
    </DarkPageLayout>
  );
}
