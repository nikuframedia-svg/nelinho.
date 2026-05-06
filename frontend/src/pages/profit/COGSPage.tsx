import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DollarSign, Play, AlertTriangle, Loader2, TrendingUp } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkSearchInput } from '../../components/dark';
import { cogsApi, productsApi } from '../../lib/api';
import { BarChart } from '../../components/charts';
import { useToastContext } from '../../components/ToastProvider';

// Sprint Q.12 — formatador único pt-PT. Antes `toLocaleString()` sem args
// herdava o locale do browser e em EN-US mostrava "€1,234.56" em vez de
// "€1.234,56".
const eurFmt = new Intl.NumberFormat('pt-PT', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
});
const formatEur = (value: number): string => eurFmt.format(value);

export function COGSPage() {
  const [filterCategory, setFilterCategory] = useState<string>('ALL');
  const [search, setSearch] = useState('');
  const [isCalculating, setIsCalculating] = useState(false);
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: cogsData = [], isLoading, error } = useQuery({
    queryKey: ['cogs', 'list'],
    queryFn: () => cogsApi.list(),
  });

  const { data: products = [] } = useQuery({
    queryKey: ['products', 'list'],
    queryFn: () => productsApi.list({ limit: 500 }),
  });

  const categories = useMemo((): string[] => {
    const cats = new Set<string>(products.map((p: any) => p.product_type as string).filter(Boolean));
    return ['ALL', ...Array.from(cats)];
  }, [products]);

  const filteredCOGS = useMemo(() => {
    return cogsData.filter((item: any) => {
      const matchesCategory = filterCategory === 'ALL' || item.product_type === filterCategory;
      const matchesSearch = !search ||
        item.product_name?.toLowerCase().includes(search.toLowerCase()) ||
        item.product_code?.toLowerCase().includes(search.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [cogsData, filterCategory, search]);

  const stats = useMemo(() => {
    const totalCOGS = filteredCOGS.reduce((sum: number, c: any) => sum + (c.total_cogs || 0), 0);
    const avgCOGS = filteredCOGS.length ? totalCOGS / filteredCOGS.length : 0;
    const totalMaterials = filteredCOGS.reduce((sum: number, c: any) => sum + (c.material_cost || 0), 0);
    const totalLabor = filteredCOGS.reduce((sum: number, c: any) => sum + (c.labor_cost || 0), 0);
    return { totalCOGS, avgCOGS, totalMaterials, totalLabor, count: filteredCOGS.length };
  }, [filteredCOGS]);

  const chartData = useMemo(() => {
    return filteredCOGS.slice(0, 10).map((c: any) => ({
      name: c.product_code || 'Product',
      COGS: c.total_cogs || 0,
    }));
  }, [filteredCOGS]);

  const calculateMutation = useMutation({
    mutationFn: () => cogsApi.calculate({ order_id: 'all' }),
    onMutate: () => setIsCalculating(true),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['cogs'] }); toast.success('COGS calculated'); },
    onError: (err: any) => toast.error(err.message || 'Calculation failed'),
    onSettled: () => setIsCalculating(false),
  });

  if (error) {
    return (
      <DarkPageLayout title="Cost of Goods Sold" icon={<DollarSign size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading COGS</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="Cost of Goods Sold"
      subtitle={isLoading ? 'Loading...' : `${cogsData.length} products analyzed`}
      icon={<DollarSign size={20} />}
      actions={
        <DarkButton icon={<Play size={18} />} onClick={() => calculateMutation.mutate()} disabled={isCalculating}>
          {isCalculating ? <><Loader2 size={18} className="animate-spin" /> Calculating...</> : 'Calculate COGS'}
        </DarkButton>
      }
    >
      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput placeholder="Search products..." value={search} onChange={(e) => setSearch(e.target.value)} onClear={() => setSearch('')} containerClassName="w-72" />
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1 overflow-x-auto">
          {categories.map((cat) => (
            <DarkPillButton key={cat} active={filterCategory === cat} onClick={() => setFilterCategory(cat)}>{cat}</DarkPillButton>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-5 gap-4 mb-6">
        <DarkStatCard icon={<DollarSign size={18} />} label="Products" value={stats.count} size="sm" />
        <DarkStatCard icon={<DollarSign size={18} />} iconBg="bg-accent/20" label="Total COGS" value={formatEur(stats.totalCOGS)} size="sm" />
        <DarkStatCard icon={<TrendingUp size={18} />} iconBg="bg-blue/20" label="Avg COGS" value={formatEur(stats.avgCOGS)} size="sm" />
        <DarkStatCard icon={<DollarSign size={18} />} iconBg="bg-purple/20" label="Materials" value={formatEur(stats.totalMaterials)} size="sm" />
        <DarkStatCard icon={<DollarSign size={18} />} iconBg="bg-amber/20" label="Labor" value={formatEur(stats.totalLabor)} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <>
          {chartData.length > 0 && (
            <DarkCard className="mb-6" title="Top 10 Products by COGS">
              <div className="h-64 mt-4">
                <BarChart data={chartData} dataKey="COGS" color="#4fd1c5" />
              </div>
            </DarkCard>
          )}

          <DarkCard padding="none">
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Product</DarkTableHeader>
                  <DarkTableHeader>Code</DarkTableHeader>
                  <DarkTableHeader>Material Cost</DarkTableHeader>
                  <DarkTableHeader>Labor Cost</DarkTableHeader>
                  <DarkTableHeader>Overhead</DarkTableHeader>
                  <DarkTableHeader>Total COGS</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {filteredCOGS.slice(0, 50).map((cogs: any, i: number) => (
                  <DarkTableRow key={cogs.id || i}>
                    <DarkTableCell className="text-text-white">{cogs.product_name || '-'}</DarkTableCell>
                    <DarkTableCell mono className="text-text-tertiary">{cogs.product_code || '-'}</DarkTableCell>
                    <DarkTableCell mono>{formatEur(cogs.material_cost || 0)}</DarkTableCell>
                    <DarkTableCell mono>{formatEur(cogs.labor_cost || 0)}</DarkTableCell>
                    <DarkTableCell mono>{formatEur(cogs.overhead_cost || 0)}</DarkTableCell>
                    <DarkTableCell mono className="text-accent font-semibold">{formatEur(cogs.total_cogs || 0)}</DarkTableCell>
                  </DarkTableRow>
                ))}
                {filteredCOGS.length === 0 && (
                  <DarkTableRow><DarkTableCell colSpan={6} className="text-center py-12"><DollarSign size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No COGS data</p></DarkTableCell></DarkTableRow>
                )}
                {filteredCOGS.length > 50 && (
                  <DarkTableRow>
                    <DarkTableCell colSpan={6} className="text-center text-xs text-text-secondary py-2">
                      A mostrar 50 de {filteredCOGS.length} produtos. Refina a pesquisa para ver mais.
                    </DarkTableCell>
                  </DarkTableRow>
                )}
              </DarkTableBody>
            </DarkTable>
          </DarkCard>
        </>
      )}
    </DarkPageLayout>
  );
}
