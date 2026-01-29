import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Package, AlertTriangle, Loader2, TrendingDown } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkPillButton, DarkBadge, DarkSearchInput } from '../../components/dark';
import { supplyApi } from '../../lib/api';

export function InventoryPage() {
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [search, setSearch] = useState('');

  const { data: inventory = [], isLoading, error } = useQuery({
    queryKey: ['inventory', 'list'],
    queryFn: () => supplyApi.listInventory({ limit: 500 }),
  });

  const filteredInventory = useMemo(() => {
    return inventory.filter((item: any) => {
      const matchesStatus = filterStatus === 'ALL' ||
        (filterStatus === 'LOW' && item.quantity <= item.reorder_point) ||
        (filterStatus === 'OK' && item.quantity > item.reorder_point);
      const matchesSearch = !search ||
        item.product_name?.toLowerCase().includes(search.toLowerCase()) ||
        item.product_code?.toLowerCase().includes(search.toLowerCase());
      return matchesStatus && matchesSearch;
    });
  }, [inventory, filterStatus, search]);

  const stats = useMemo(() => ({
    total: inventory.length,
    lowStock: inventory.filter((i: any) => i.quantity <= i.reorder_point).length,
    outOfStock: inventory.filter((i: any) => i.quantity === 0).length,
    totalValue: inventory.reduce((sum: number, i: any) => sum + (i.quantity * (i.unit_cost || 0)), 0),
  }), [inventory]);

  if (error) {
    return (
      <DarkPageLayout title="Inventory Management" icon={<Package size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading inventory</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout title="Inventory Management" subtitle={isLoading ? 'Loading...' : `${inventory.length} items`} icon={<Package size={20} />}>
      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput placeholder="Search items..." value={search} onChange={(e) => setSearch(e.target.value)} onClear={() => setSearch('')} containerClassName="w-72" />
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'LOW', 'OK'].map((status) => (
            <DarkPillButton key={status} active={filterStatus === status} onClick={() => setFilterStatus(status)}>{status === 'LOW' ? 'Low Stock' : status}</DarkPillButton>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <DarkStatCard icon={<Package size={18} />} label="Total Items" value={stats.total} size="sm" />
        <DarkStatCard icon={<TrendingDown size={18} />} iconBg="bg-amber/20" label="Low Stock" value={stats.lowStock} size="sm" />
        <DarkStatCard icon={<AlertTriangle size={18} />} iconBg="bg-danger/20" label="Out of Stock" value={stats.outOfStock} size="sm" />
        <DarkStatCard icon={<Package size={18} />} iconBg="bg-success/20" label="Total Value" value={`€${stats.totalValue.toLocaleString()}`} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Product</DarkTableHeader>
                <DarkTableHeader>Code</DarkTableHeader>
                <DarkTableHeader>Quantity</DarkTableHeader>
                <DarkTableHeader>Reorder Point</DarkTableHeader>
                <DarkTableHeader>Unit Cost</DarkTableHeader>
                <DarkTableHeader>Total Value</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredInventory.slice(0, 50).map((item: any, i: number) => (
                <DarkTableRow key={item.id || i}>
                  <DarkTableCell className="text-text-white">{item.product_name || '-'}</DarkTableCell>
                  <DarkTableCell mono className="text-text-tertiary">{item.product_code || '-'}</DarkTableCell>
                  <DarkTableCell mono>{item.quantity || 0}</DarkTableCell>
                  <DarkTableCell mono>{item.reorder_point || 0}</DarkTableCell>
                  <DarkTableCell mono>€{(item.unit_cost || 0).toFixed(2)}</DarkTableCell>
                  <DarkTableCell mono>€{((item.quantity || 0) * (item.unit_cost || 0)).toFixed(2)}</DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={item.quantity === 0 ? 'danger' : item.quantity <= item.reorder_point ? 'warning' : 'success'} dot>
                      {item.quantity === 0 ? 'Out of Stock' : item.quantity <= item.reorder_point ? 'Low Stock' : 'OK'}
                    </DarkBadge>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {filteredInventory.length === 0 && (
                <DarkTableRow><DarkTableCell colSpan={7} className="text-center py-12"><Package size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No inventory items found</p></DarkTableCell></DarkTableRow>
              )}
            </DarkTableBody>
          </DarkTable>
        </DarkCard>
      )}
    </DarkPageLayout>
  );
}

