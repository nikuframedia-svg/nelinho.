import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Package, Play, AlertTriangle, Loader2, RefreshCw, Download, TrendingDown, ShoppingCart } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkBadge } from '../../components/dark';
import { planApi } from '../../lib/api';
import type { MutationError } from '../../lib/api-helpers';
import { useToastContext } from '../../components/ToastProvider';

interface MrpItem {
  id?: string;
  material_name?: string;
  material_code?: string;
  product_name?: string;
  product_code?: string;
  shortage?: number;
  action?: 'ORDER' | 'OK' | string;
  required_qty?: number;
  required?: number;
  available_qty?: number;
  on_hand?: number;
  lead_time_days?: number;
}

export function MRPPage() {
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [isCalculating, setIsCalculating] = useState(false);
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: mrpResults = [], isLoading, error } = useQuery({
    queryKey: ['mrp', 'results'],
    queryFn: () => planApi.getMRPResults({ limit: 500 }),
  });

  const calculateMutation = useMutation({
    mutationFn: () => planApi.calculateMRP({ horizon_weeks: 8 }),
    onMutate: () => setIsCalculating(true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mrp'] });
      toast.success('MRP calculation completed');
    },
    onError: (err: MutationError) => toast.error(err.message || 'Calculation failed'),
    onSettled: () => setIsCalculating(false),
  });

  const filteredResults = useMemo(() => {
    if (filterStatus === 'ALL') return mrpResults;
    return (mrpResults as MrpItem[]).filter((r) => {
      if (filterStatus === 'SHORTAGE') return r.shortage && r.shortage > 0;
      if (filterStatus === 'ORDER') return r.action === 'ORDER';
      if (filterStatus === 'OK') return !r.shortage || r.shortage <= 0;
      return true;
    });
  }, [mrpResults, filterStatus]);

  const stats = useMemo(() => {
    const items = mrpResults as MrpItem[];
    return {
      total: items.length,
      shortages: items.filter((r) => r.shortage && r.shortage > 0).length,
      toOrder: items.filter((r) => r.action === 'ORDER').length,
      ok: items.filter((r) => !r.shortage || r.shortage <= 0).length,
    };
  }, [mrpResults]);

  if (error) {
    return (
      <DarkPageLayout title="MRP - Material Requirements" icon={<Package size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading MRP data</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="MRP - Material Requirements"
      subtitle={isLoading ? 'Loading...' : `${mrpResults.length} material items`}
      icon={<Package size={20} />}
      actions={
        <div className="flex items-center gap-2">
          <DarkButton variant="secondary" icon={<Download size={18} />}>Export</DarkButton>
          <DarkButton icon={<Play size={18} />} onClick={() => calculateMutation.mutate()} disabled={isCalculating}>
            {isCalculating ? <><Loader2 size={18} className="animate-spin" /> Calculating...</> : 'Calculate MRP'}
          </DarkButton>
        </div>
      }
    >
      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'SHORTAGE', 'ORDER', 'OK'].map((status) => (
            <DarkPillButton key={status} active={filterStatus === status} onClick={() => setFilterStatus(status)}>
              {status}
            </DarkPillButton>
          ))}
        </div>
        <DarkButton variant="ghost" size="sm" icon={<RefreshCw size={14} />} onClick={() => queryClient.invalidateQueries({ queryKey: ['mrp'] })}>
          Refresh
        </DarkButton>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <DarkStatCard icon={<Package size={18} />} label="Total Items" value={stats.total} size="sm" />
        <DarkStatCard icon={<TrendingDown size={18} />} iconBg="bg-danger/20" label="Shortages" value={stats.shortages} size="sm" />
        <DarkStatCard icon={<ShoppingCart size={18} />} iconBg="bg-amber/20" label="To Order" value={stats.toOrder} size="sm" />
        <DarkStatCard icon={<Package size={18} />} iconBg="bg-success/20" label="OK" value={stats.ok} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Material</DarkTableHeader>
                <DarkTableHeader>Code</DarkTableHeader>
                <DarkTableHeader>On Hand</DarkTableHeader>
                <DarkTableHeader>Required</DarkTableHeader>
                <DarkTableHeader>Shortage</DarkTableHeader>
                <DarkTableHeader>Action</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {(filteredResults as MrpItem[]).slice(0, 50).map((item, i: number) => (
                <DarkTableRow key={item.id || i}>
                  <DarkTableCell className="text-text-white">{item.material_name || item.product_name || '-'}</DarkTableCell>
                  <DarkTableCell mono className="text-text-tertiary">{item.material_code || item.product_code || '-'}</DarkTableCell>
                  <DarkTableCell mono>{item.on_hand || 0}</DarkTableCell>
                  <DarkTableCell mono>{item.required || 0}</DarkTableCell>
                  <DarkTableCell mono className={(item.shortage ?? 0) > 0 ? 'text-danger' : 'text-success'}>{item.shortage || 0}</DarkTableCell>
                  <DarkTableCell>
                    {item.action === 'ORDER' ? (
                      <DarkBadge variant="warning" icon={<ShoppingCart size={12} />}>Order</DarkBadge>
                    ) : (
                      <span className="text-text-tertiary">-</span>
                    )}
                  </DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={(item.shortage ?? 0) > 0 ? 'danger' : 'success'} dot>
                      {(item.shortage ?? 0) > 0 ? 'Shortage' : 'OK'}
                    </DarkBadge>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {filteredResults.length === 0 && (
                <DarkTableRow>
                  <DarkTableCell colSpan={7} className="text-center py-12">
                    <Package size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                    <p className="text-text-secondary">No MRP results</p>
                    <p className="text-xs text-text-tertiary mt-1">Click "Calculate MRP" to generate requirements</p>
                  </DarkTableCell>
                </DarkTableRow>
              )}
            </DarkTableBody>
          </DarkTable>
        </DarkCard>
      )}
    </DarkPageLayout>
  );
}
