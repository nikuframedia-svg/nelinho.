import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DollarSign, Play, AlertTriangle, Loader2, TrendingUp, Percent } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkBadge, DarkSearchInput } from '../../components/dark';
import { pricingApi, productsApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';

export function PricingPage() {
  const [filterCategory, setFilterCategory] = useState<string>('ALL');
  const [search, setSearch] = useState('');
  const [isCalculating, setIsCalculating] = useState(false);
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: pricingData = [], isLoading, error } = useQuery({
    queryKey: ['pricing', 'list'],
    queryFn: () => pricingApi.list(),
  });

  const { data: products = [] } = useQuery({
    queryKey: ['products', 'list'],
    queryFn: () => productsApi.list({ limit: 500 }),
  });

  const categories = useMemo((): string[] => {
    const cats = new Set<string>(products.map((p: any) => p.product_type as string).filter(Boolean));
    return ['ALL', ...Array.from(cats)];
  }, [products]);

  const filteredPricing = useMemo(() => {
    return pricingData.filter((item: any) => {
      const matchesCategory = filterCategory === 'ALL' || item.product_type === filterCategory;
      const matchesSearch = !search ||
        item.product_name?.toLowerCase().includes(search.toLowerCase()) ||
        item.product_code?.toLowerCase().includes(search.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [pricingData, filterCategory, search]);

  const stats = useMemo(() => {
    const avgMargin = filteredPricing.length ? filteredPricing.reduce((sum: number, p: any) => sum + (p.margin_pct || 0), 0) / filteredPricing.length : 0;
    const avgPrice = filteredPricing.length ? filteredPricing.reduce((sum: number, p: any) => sum + (p.recommended_price || 0), 0) / filteredPricing.length : 0;
    const underpriced = filteredPricing.filter((p: any) => p.margin_pct < 20).length;
    const optimal = filteredPricing.filter((p: any) => p.margin_pct >= 20 && p.margin_pct <= 40).length;
    return { avgMargin, avgPrice, underpriced, optimal, count: filteredPricing.length };
  }, [filteredPricing]);

  const recommendMutation = useMutation({
    mutationFn: () => pricingApi.recommend({ order_id: 'all' }),
    onMutate: () => setIsCalculating(true),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['pricing'] }); toast.success('Pricing recommendations generated'); },
    onError: (err: any) => toast.error(err.message || 'Calculation failed'),
    onSettled: () => setIsCalculating(false),
  });

  if (error) {
    return (
      <DarkPageLayout title="Pricing Management" icon={<DollarSign size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading pricing</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="Pricing Management"
      subtitle={isLoading ? 'Loading...' : `${pricingData.length} products`}
      icon={<DollarSign size={20} />}
      actions={
        <DarkButton icon={<Play size={18} />} onClick={() => recommendMutation.mutate()} disabled={isCalculating}>
          {isCalculating ? <><Loader2 size={18} className="animate-spin" /> Calculating...</> : 'Generate Recommendations'}
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
        <DarkStatCard icon={<Percent size={18} />} iconBg="bg-accent/20" label="Avg Margin" value={`${stats.avgMargin.toFixed(1)}%`} size="sm" />
        <DarkStatCard icon={<DollarSign size={18} />} iconBg="bg-blue/20" label="Avg Price" value={`€${stats.avgPrice.toFixed(2)}`} size="sm" />
        <DarkStatCard icon={<TrendingUp size={18} />} iconBg="bg-danger/20" label="Underpriced" value={stats.underpriced} size="sm" />
        <DarkStatCard icon={<TrendingUp size={18} />} iconBg="bg-success/20" label="Optimal" value={stats.optimal} size="sm" />
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
                <DarkTableHeader>COGS</DarkTableHeader>
                <DarkTableHeader>Current Price</DarkTableHeader>
                <DarkTableHeader>Recommended</DarkTableHeader>
                <DarkTableHeader>Margin</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredPricing.slice(0, 50).map((pricing: any, i: number) => (
                <DarkTableRow key={pricing.id || i}>
                  <DarkTableCell className="text-text-white">{pricing.product_name || '-'}</DarkTableCell>
                  <DarkTableCell mono className="text-text-tertiary">{pricing.product_code || '-'}</DarkTableCell>
                  <DarkTableCell mono>€{(pricing.cogs || 0).toFixed(2)}</DarkTableCell>
                  <DarkTableCell mono>€{(pricing.current_price || 0).toFixed(2)}</DarkTableCell>
                  <DarkTableCell mono className="text-accent">€{(pricing.recommended_price || 0).toFixed(2)}</DarkTableCell>
                  <DarkTableCell mono className={pricing.margin_pct < 20 ? 'text-danger' : pricing.margin_pct > 40 ? 'text-success' : 'text-text-primary'}>
                    {(pricing.margin_pct || 0).toFixed(1)}%
                  </DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={pricing.margin_pct < 20 ? 'danger' : pricing.margin_pct > 40 ? 'success' : 'warning'} dot>
                      {pricing.margin_pct < 20 ? 'Low' : pricing.margin_pct > 40 ? 'High' : 'Optimal'}
                    </DarkBadge>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {filteredPricing.length === 0 && (
                <DarkTableRow><DarkTableCell colSpan={7} className="text-center py-12"><DollarSign size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No pricing data</p></DarkTableCell></DarkTableRow>
              )}
            </DarkTableBody>
          </DarkTable>
        </DarkCard>
      )}
    </DarkPageLayout>
  );
}
