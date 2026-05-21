import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Package, AlertTriangle, Loader2, ShoppingCart } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkPillButton, DarkBadge, DarkSearchInput } from '../../components/dark';
import { supplyApi } from '../../lib/api';

interface RopItem {
  id?: string;
  product_name?: string;
  product_code?: string;
  quantity?: number;
  reorder_point?: number;
  safety_stock?: number;
  lead_time_days?: number;
  supplier_name?: string;
}

export function ROPPage() {
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [search, setSearch] = useState('');

  const { data: ropData = [], isLoading, error } = useQuery({
    queryKey: ['rop', 'list'],
    queryFn: () => supplyApi.getROP(),
  });

  const filteredROP = useMemo(() => {
    return (ropData as RopItem[]).filter((item) => {
      const matchesStatus = filterStatus === 'ALL' ||
        (filterStatus === 'REORDER' && (item.quantity ?? 0) <= (item.reorder_point ?? 0)) ||
        (filterStatus === 'OK' && (item.quantity ?? 0) > (item.reorder_point ?? 0));
      const matchesSearch = !search ||
        item.product_name?.toLowerCase().includes(search.toLowerCase()) ||
        item.product_code?.toLowerCase().includes(search.toLowerCase());
      return matchesStatus && matchesSearch;
    });
  }, [ropData, filterStatus, search]);

  const stats = useMemo(() => {
    const items = ropData as RopItem[];
    return {
      total: items.length,
      needsReorder: items.filter((i) => (i.quantity ?? 0) <= (i.reorder_point ?? 0)).length,
      safetyStock: items.filter((i) => (i.quantity ?? 0) <= (i.safety_stock ?? 0)).length,
      ok: items.filter((i) => (i.quantity ?? 0) > (i.reorder_point ?? 0)).length,
    };
  }, [ropData]);

  if (error) {
    return (
      <DarkPageLayout title="Reorder Point Analysis" icon={<Package size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading ROP data</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="Reorder Point Analysis"
      subtitle={isLoading ? 'Loading...' : `${ropData.length} items analyzed`}
      icon={<Package size={20} />}
    >
      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput placeholder="Search items..." value={search} onChange={(e) => setSearch(e.target.value)} onClear={() => setSearch('')} containerClassName="w-72" />
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'REORDER', 'OK'].map((status) => (
            <DarkPillButton key={status} active={filterStatus === status} onClick={() => setFilterStatus(status)}>{status === 'REORDER' ? 'Needs Reorder' : status}</DarkPillButton>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <DarkStatCard icon={<Package size={18} />} label="Total Items" value={stats.total} size="sm" />
        <DarkStatCard icon={<ShoppingCart size={18} />} iconBg="bg-amber/20" label="Needs Reorder" value={stats.needsReorder} size="sm" />
        <DarkStatCard icon={<AlertTriangle size={18} />} iconBg="bg-danger/20" label="Below Safety" value={stats.safetyStock} size="sm" />
        <DarkStatCard icon={<Package size={18} />} iconBg="bg-success/20" label="OK" value={stats.ok} size="sm" />
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
                <DarkTableHeader>Current Qty</DarkTableHeader>
                <DarkTableHeader>Reorder Point</DarkTableHeader>
                <DarkTableHeader>Safety Stock</DarkTableHeader>
                <DarkTableHeader>Lead Time</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredROP.slice(0, 50).map((item, i: number) => (
                <DarkTableRow key={item.id || i}>
                  <DarkTableCell className="text-text-white">{item.product_name || '-'}</DarkTableCell>
                  <DarkTableCell mono className="text-text-tertiary">{item.product_code || '-'}</DarkTableCell>
                  <DarkTableCell mono>{item.quantity || 0}</DarkTableCell>
                  <DarkTableCell mono>{item.reorder_point || 0}</DarkTableCell>
                  <DarkTableCell mono>{item.safety_stock || 0}</DarkTableCell>
                  <DarkTableCell>{item.lead_time_days || 0} days</DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={(item.quantity ?? 0) <= (item.safety_stock ?? 0) ? 'danger' : (item.quantity ?? 0) <= (item.reorder_point ?? 0) ? 'warning' : 'success'} dot>
                      {(item.quantity ?? 0) <= (item.safety_stock ?? 0) ? 'Critical' : (item.quantity ?? 0) <= (item.reorder_point ?? 0) ? 'Reorder' : 'OK'}
                    </DarkBadge>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {filteredROP.length === 0 && (
                <DarkTableRow><DarkTableCell colSpan={7} className="text-center py-12"><Package size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No ROP data</p></DarkTableCell></DarkTableRow>
              )}
            </DarkTableBody>
          </DarkTable>
        </DarkCard>
      )}
    </DarkPageLayout>
  );
}

