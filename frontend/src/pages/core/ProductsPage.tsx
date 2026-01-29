import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Plus, 
  Package,
  Edit,
  Trash2,
  Eye,
  Weight,
  Droplets,
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
  DarkIconButton,
} from '../../components/dark';
import { FormModal, DeleteConfirmDialog, type FormField } from '../../components/ui';
import { productsApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';

interface Product {
  id: string;
  name: string;
  product_code?: string;
  type: string;
  weightDismold: number;
  weightFinish: number;
  gelDeck: number;
  gelHull: number;
  status: string;
  category?: string;
  lead_time_days?: number;
  standard_cost?: number;
}

export function ProductsPage() {
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToastContext();

  const [filterType, setFilterType] = useState('ALL');
  const [search, setSearch] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [deletingProduct, setDeletingProduct] = useState<Product | null>(null);

  // Fetch products from API
  const { data: productsList, isLoading, error } = useQuery({
    queryKey: ['products', 'list'],
    queryFn: () => productsApi.list({ limit: 1000 }),
    refetchInterval: 300000,
  });

  // Convert API data to Product interface
  const products: Product[] = useMemo(() => {
    if (!productsList) return [];
    return (Array.isArray(productsList) ? productsList : []).map((p: any) => ({
      id: p.id || p.product_id || '',
      name: p.name || p.product_name || '',
      product_code: p.product_code || '',
      type: p.type || p.product_type || '',
      weightDismold: p.weight_dismold || p.weightDismold || 0,
      weightFinish: p.weight_finish || p.weightFinish || 0,
      gelDeck: p.gel_deck || p.gelDeck || 0,
      gelHull: p.gel_hull || p.gelHull || 0,
      status: p.status || 'ACTIVE',
      category: p.category || '',
      lead_time_days: p.lead_time_days || 0,
      standard_cost: p.standard_cost || 0,
    }));
  }, [productsList]);

  // Get unique product types from data
  const productTypes = useMemo(() => {
    const types = new Set(products.map(p => p.type).filter(Boolean));
    return ['ALL', ...Array.from(types)].sort();
  }, [products]);

  const filteredProducts = useMemo(() => {
    return products.filter(p => {
      const matchesType = filterType === 'ALL' || p.type === filterType;
      const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase()) || 
                            p.id.toLowerCase().includes(search.toLowerCase());
      return matchesType && matchesSearch;
    });
  }, [products, filterType, search]);

  const paginatedProducts = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredProducts.slice(start, start + itemsPerPage);
  }, [filteredProducts, currentPage]);

  const totalPages = Math.ceil(filteredProducts.length / itemsPerPage);

  const stats = useMemo(() => {
    if (products.length === 0) {
      return { total: 0, active: 0, k1: 0, k2: 0, k4: 0, avgWeight: 0 };
    }
    return {
      total: products.length,
      active: products.filter(p => p.status === 'ACTIVE').length,
      k1: products.filter(p => p.type === 'K1').length,
      k2: products.filter(p => p.type === 'K2').length,
      k4: products.filter(p => p.type === 'K4').length,
      avgWeight: products.reduce((sum, p) => sum + p.weightFinish, 0) / products.length,
    };
  }, [products]);

  // Mutations
  const createMutation = useMutation({
    mutationFn: productsApi.create,
    onSuccess: () => {
      success('Produto adicionado com sucesso');
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setIsFormModalOpen(false);
    },
    onError: (err: any) => {
      toastError(err.message || 'Erro ao adicionar produto');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => productsApi.update(id, data),
    onSuccess: () => {
      success('Produto atualizado com sucesso');
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setIsFormModalOpen(false);
      setEditingProduct(null);
    },
    onError: (err: any) => {
      toastError(err.message || 'Erro ao atualizar produto');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: productsApi.delete,
    onSuccess: () => {
      success('Produto eliminado com sucesso');
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setIsDeleteConfirmOpen(false);
      setDeletingProduct(null);
    },
    onError: (err: any) => {
      toastError(err.message || 'Erro ao eliminar produto');
    },
  });

  const productFormFields: FormField[] = [
    { name: 'product_code', label: 'Product Code', type: 'text', required: true },
    { name: 'product_name', label: 'Product Name', type: 'text', required: true },
    {
      name: 'product_type',
      label: 'Product Type',
      type: 'select',
      options: [
        { value: 'FINISHED_GOOD', label: 'Finished Good' },
        { value: 'RAW_MATERIAL', label: 'Raw Material' },
        { value: 'WIP', label: 'Work In Progress' },
        { value: 'COMPONENT', label: 'Component' },
      ],
      defaultValue: 'FINISHED_GOOD',
    },
    { name: 'category', label: 'Category', type: 'text' },
    { name: 'lead_time_days', label: 'Lead Time (Days)', type: 'number', min: 0, defaultValue: 0 },
    { name: 'standard_cost', label: 'Standard Cost (€)', type: 'number', min: 0, step: 0.01, defaultValue: 0 },
    {
      name: 'status',
      label: 'Status',
      type: 'select',
      options: [
        { value: 'ACTIVE', label: 'Active' },
        { value: 'DISCONTINUED', label: 'Discontinued' },
        { value: 'DEVELOPMENT', label: 'Development' },
      ],
      defaultValue: 'ACTIVE',
    },
  ];

  const handleFormSubmit = (data: Record<string, any>) => {
    const payload = {
      product_code: data.product_code,
      product_name: data.product_name,
      product_type: data.product_type,
      category: data.category || null,
      lead_time_days: parseInt(data.lead_time_days) || 0,
      standard_cost: parseFloat(data.standard_cost) || 0,
      status: data.status,
    };

    if (editingProduct) {
      updateMutation.mutate({ id: editingProduct.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const handleDeleteConfirm = () => {
    if (deletingProduct) {
      deleteMutation.mutate(deletingProduct.id);
    }
  };

  const getTypeBadgeVariant = (type: string) => {
    switch (type) {
      case 'K1': return 'info';
      case 'K2': return 'accent';
      case 'K4': return 'warning';
      case 'C1': return 'success';
      case 'C2': return 'teal';
      default: return 'neutral';
    }
  };

  return (
    <DarkPageLayout
      title="Kayak Models"
      subtitle={isLoading ? 'Loading...' : `${products.length} products in catalog`}
      icon={<Package size={20} />}
      actions={
        <DarkButton
          icon={<Plus size={18} />}
          onClick={() => {
            setEditingProduct(null);
            setIsFormModalOpen(true);
          }}
        >
          Add Kayak
        </DarkButton>
      }
    >
      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput
          placeholder="Search kayaks..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
          onClear={() => setSearch('')}
          containerClassName="w-72"
        />
        
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {productTypes.slice(0, 8).map((type) => (
            <DarkPillButton
              key={type}
              active={filterType === type}
              onClick={() => { setFilterType(type); setCurrentPage(1); }}
            >
              {type}
            </DarkPillButton>
          ))}
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <DarkCard className="mb-6">
          <div className="flex items-center justify-center gap-3 text-text-secondary py-8">
            <Loader2 size={20} className="animate-spin" />
            <p>Loading products...</p>
          </div>
        </DarkCard>
      )}

      {/* Error State */}
      {error && (
        <DarkCard className="mb-6 border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertCircle size={20} />
            <div>
              <p className="font-semibold">Error loading products</p>
              <p className="text-sm opacity-80">
                {error instanceof Error ? error.message : 'Failed to load products from API'}
              </p>
            </div>
          </div>
        </DarkCard>
      )}

      {!isLoading && !error && (
        <>
          {/* Stats Grid */}
          <div className="grid grid-cols-6 gap-4 mb-6">
            <DarkStatCard
              icon={<Package size={18} />}
              label="Total Models"
              value={stats.total}
              size="sm"
            />
            <DarkStatCard
              icon={<Package size={18} />}
              iconBg="bg-success/20"
              label="Active"
              value={stats.active}
              size="sm"
            />
            <DarkStatCard
              icon={<Package size={18} />}
              iconBg="bg-blue/20"
              label="K1 Singles"
              value={stats.k1}
              size="sm"
            />
            <DarkStatCard
              icon={<Package size={18} />}
              iconBg="bg-purple/20"
              label="K2 Doubles"
              value={stats.k2}
              size="sm"
            />
            <DarkStatCard
              icon={<Package size={18} />}
              iconBg="bg-amber/20"
              label="K4 Fours"
              value={stats.k4}
              size="sm"
            />
            <DarkStatCard
              icon={<Weight size={18} />}
              label="Avg Weight"
              value={stats.avgWeight.toFixed(1)}
              unit="kg"
              size="sm"
            />
          </div>

          {/* Table */}
          <DarkCard padding="none">
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Model</DarkTableHeader>
                  <DarkTableHeader>Type</DarkTableHeader>
                  <DarkTableHeader>
                    <div className="flex items-center gap-1">
                      <Weight size={14} />
                      Dismold
                    </div>
                  </DarkTableHeader>
                  <DarkTableHeader>
                    <div className="flex items-center gap-1">
                      <Weight size={14} />
                      Finish
                    </div>
                  </DarkTableHeader>
                  <DarkTableHeader>
                    <div className="flex items-center gap-1">
                      <Droplets size={14} />
                      Gel Deck
                    </div>
                  </DarkTableHeader>
                  <DarkTableHeader>
                    <div className="flex items-center gap-1">
                      <Droplets size={14} />
                      Gel Hull
                    </div>
                  </DarkTableHeader>
                  <DarkTableHeader>Status</DarkTableHeader>
                  <DarkTableHeader align="right">Actions</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {paginatedProducts.map((product) => (
                  <DarkTableRow key={product.id}>
                    <DarkTableCell>
                      <div>
                        <p className="font-semibold text-text-white text-sm">{product.name}</p>
                        <p className="text-xs text-text-tertiary">ID: {product.id}</p>
                      </div>
                    </DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge variant={getTypeBadgeVariant(product.type)}>
                        {product.type}
                      </DarkBadge>
                    </DarkTableCell>
                    <DarkTableCell mono>{product.weightDismold} kg</DarkTableCell>
                    <DarkTableCell mono className="text-text-white font-medium">{product.weightFinish} kg</DarkTableCell>
                    <DarkTableCell mono>{product.gelDeck} L</DarkTableCell>
                    <DarkTableCell mono>{product.gelHull} L</DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge 
                        variant={product.status === 'ACTIVE' ? 'success' : 'neutral'}
                        dot
                      >
                        {product.status}
                      </DarkBadge>
                    </DarkTableCell>
                    <DarkTableCell align="right">
                      <div className="flex items-center justify-end gap-1">
                        <DarkIconButton icon={<Eye size={16} />} size="sm" variant="ghost" />
                        <DarkIconButton
                          icon={<Edit size={16} />}
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setEditingProduct(product);
                            setIsFormModalOpen(true);
                          }}
                        />
                        <DarkIconButton
                          icon={<Trash2 size={16} />}
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setDeletingProduct(product);
                            setIsDeleteConfirmOpen(true);
                          }}
                        />
                      </div>
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
                {paginatedProducts.length === 0 && (
                  <DarkTableRow>
                    <DarkTableCell colSpan={8} className="text-center py-12">
                      <div className="text-text-tertiary">
                        <Package size={40} className="mx-auto mb-3 opacity-50" />
                        <p className="font-medium text-text-secondary">No products found</p>
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
                  Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, filteredProducts.length)} of {filteredProducts.length} results
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
                    if (page > totalPages) return null;
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
        </>
      )}

      {/* Form Modal */}
      <FormModal
        title={editingProduct ? 'Edit Product' : 'Add Product'}
        isOpen={isFormModalOpen}
        onClose={() => {
          setIsFormModalOpen(false);
          setEditingProduct(null);
        }}
        onSubmit={handleFormSubmit}
        initialData={editingProduct ? {
          product_code: editingProduct.product_code,
          product_name: editingProduct.name,
          product_type: editingProduct.type,
          category: editingProduct.category,
          lead_time_days: editingProduct.lead_time_days,
          standard_cost: editingProduct.standard_cost,
          status: editingProduct.status,
        } : {}}
        fields={productFormFields}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmDialog
        isOpen={isDeleteConfirmOpen}
        onClose={() => {
          setIsDeleteConfirmOpen(false);
          setDeletingProduct(null);
        }}
        onConfirm={handleDeleteConfirm}
        title={deletingProduct ? `Product ${deletingProduct.name}` : 'Product'}
        message="Are you sure you want to delete this product? This action cannot be undone."
        isLoading={deleteMutation.isPending}
      />
    </DarkPageLayout>
  );
}
