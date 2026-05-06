import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Package, Play, AlertTriangle, Loader2 } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkBadge, DarkSearchInput } from '../../components/dark';
import { supplyApi } from '../../lib/api';
import { DonutChart } from '../../components/charts';
import { useToastContext } from '../../components/ToastProvider';

export function ABCPage() {
  const [filterClass, setFilterClass] = useState<string>('ALL');
  const [search, setSearch] = useState('');
  const [isCalculating, setIsCalculating] = useState(false);
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: abcData = [], isLoading, error } = useQuery({
    queryKey: ['abc', 'list'],
    queryFn: () => supplyApi.getABC(),
  });

  const filteredABC = useMemo(() => {
    return abcData.filter((item: any) => {
      const matchesClass = filterClass === 'ALL' || item.abc_class === filterClass;
      const matchesSearch = !search ||
        item.product_name?.toLowerCase().includes(search.toLowerCase()) ||
        item.product_code?.toLowerCase().includes(search.toLowerCase());
      return matchesClass && matchesSearch;
    });
  }, [abcData, filterClass, search]);

  const stats = useMemo(() => ({
    total: abcData.length,
    classA: abcData.filter((i: any) => i.abc_class === 'A').length,
    classB: abcData.filter((i: any) => i.abc_class === 'B').length,
    classC: abcData.filter((i: any) => i.abc_class === 'C').length,
  }), [abcData]);

  const donutData = useMemo(() => [
    { name: 'Class A', value: stats.classA, color: '#4fd1c5' },
    { name: 'Class B', value: stats.classB, color: '#8B5CF6' },
    { name: 'Class C', value: stats.classC, color: '#6B7280' },
  ], [stats]);

  const calculateMutation = useMutation({
    mutationFn: () => supplyApi.calculateABC(),
    onMutate: () => setIsCalculating(true),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['abc'] }); toast.success('ABC analysis completed'); },
    onError: (err: any) => toast.error(err.message || 'Calculation failed'),
    onSettled: () => setIsCalculating(false),
  });

  if (error) {
    return (
      <DarkPageLayout title="ABC Analysis" icon={<Package size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading ABC data</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="ABC Analysis"
      subtitle={isLoading ? 'Loading...' : `${abcData.length} items classified`}
      icon={<Package size={20} />}
      actions={
        <DarkButton icon={<Play size={18} />} onClick={() => calculateMutation.mutate()} disabled={isCalculating}>
          {isCalculating ? <><Loader2 size={18} className="animate-spin" /> Calculating...</> : 'Run ABC Analysis'}
        </DarkButton>
      }
    >
      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput placeholder="Search items..." value={search} onChange={(e) => setSearch(e.target.value)} onClear={() => setSearch('')} containerClassName="w-72" />
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'A', 'B', 'C'].map((cls) => (
            <DarkPillButton key={cls} active={filterClass === cls} onClick={() => setFilterClass(cls)}>{cls === 'ALL' ? 'All' : `Class ${cls}`}</DarkPillButton>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6 mb-6">
        <div className="grid grid-cols-4 gap-4">
          <DarkStatCard icon={<Package size={18} />} label="Total Items" value={stats.total} size="sm" />
          <DarkStatCard icon={<Package size={18} />} iconBg="bg-accent/20" label="Class A" value={stats.classA} size="sm" />
          <DarkStatCard icon={<Package size={18} />} iconBg="bg-purple/20" label="Class B" value={stats.classB} size="sm" />
          <DarkStatCard icon={<Package size={18} />} iconBg="bg-bg-elevated" label="Class C" value={stats.classC} size="sm" />
        </div>
        <DarkCard title="Distribution">
          <div className="h-40 flex items-center justify-center">
            <DonutChart data={donutData} innerRadius={40} outerRadius={60} />
          </div>
        </DarkCard>
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
                <DarkTableHeader>Annual Usage</DarkTableHeader>
                <DarkTableHeader>Unit Cost</DarkTableHeader>
                <DarkTableHeader>Annual Value</DarkTableHeader>
                <DarkTableHeader>Cumulative %</DarkTableHeader>
                <DarkTableHeader>Class</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredABC.slice(0, 50).map((item: any, i: number) => (
                <DarkTableRow key={item.id || i}>
                  <DarkTableCell className="text-text-white">{item.product_name || '-'}</DarkTableCell>
                  <DarkTableCell mono className="text-text-tertiary">{item.product_code || '-'}</DarkTableCell>
                  <DarkTableCell mono>{item.annual_usage || 0}</DarkTableCell>
                  <DarkTableCell mono>€{(item.unit_cost || 0).toFixed(2)}</DarkTableCell>
                  <DarkTableCell mono>€{(item.annual_value || 0).toLocaleString()}</DarkTableCell>
                  <DarkTableCell mono>{(item.cumulative_pct || 0).toFixed(1)}%</DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={item.abc_class === 'A' ? 'accent' : item.abc_class === 'B' ? 'info' : 'neutral'}>
                      Class {item.abc_class || '-'}
                    </DarkBadge>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {filteredABC.length === 0 && (
                <DarkTableRow><DarkTableCell colSpan={7} className="text-center py-12"><Package size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No ABC data</p></DarkTableCell></DarkTableRow>
              )}
              {filteredABC.length > 50 && (
                <DarkTableRow>
                  <DarkTableCell colSpan={7} className="text-center text-xs text-text-secondary py-2">
                    A mostrar 50 de {filteredABC.length} SKUs. Refina a pesquisa para ver mais.
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

