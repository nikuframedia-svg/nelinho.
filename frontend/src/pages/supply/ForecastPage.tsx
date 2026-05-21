import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { TrendingUp, Play, AlertTriangle, Loader2 } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkSearchInput } from '../../components/dark';
import { supplyApi } from '../../lib/api';
import type { MutationError } from '../../lib/api-helpers';
import { LineChart } from '../../components/charts';
import { useToastContext } from '../../components/ToastProvider';

interface ForecastItem {
  id?: string;
  product_name?: string;
  product_code?: string;
  weekly_forecast?: number[];
  current_stock?: number;
  avg_weekly_demand?: number;
  total_forecast?: number;
  weeks_of_stock?: number;
}

export function ForecastPage() {
  const [horizonWeeks, setHorizonWeeks] = useState<number>(12);
  const [search, setSearch] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: forecastData = [], isLoading, error } = useQuery({
    queryKey: ['forecast', horizonWeeks],
    queryFn: () => supplyApi.getForecast({ horizon_weeks: horizonWeeks }),
  });

  const filteredForecast = useMemo(() => {
    if (!search) return forecastData;
    return (forecastData as ForecastItem[]).filter((f) =>
      f.product_name?.toLowerCase().includes(search.toLowerCase()) ||
      f.product_code?.toLowerCase().includes(search.toLowerCase())
    );
  }, [forecastData, search]);

  const generateMutation = useMutation({
    mutationFn: () => supplyApi.generateForecast({ horizon_weeks: horizonWeeks }),
    onMutate: () => setIsGenerating(true),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['forecast'] }); toast.success('Forecast generated'); },
    onError: (err: MutationError) => toast.error(err.message || 'Generation failed'),
    onSettled: () => setIsGenerating(false),
  });

  const chartData = useMemo(() => {
    if (!forecastData.length) return [];
    const topProduct = forecastData[0];
    if (!topProduct?.weekly_forecast) return [];
    return topProduct.weekly_forecast.map((val: number, i: number) => ({
      name: `W${i + 1}`,
      Forecast: val,
    }));
  }, [forecastData]);

  if (error) {
    return (
      <DarkPageLayout title="Demand Forecast" icon={<TrendingUp size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading forecast</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="Demand Forecast"
      subtitle={isLoading ? 'Loading...' : `${forecastData.length} products forecasted`}
      icon={<TrendingUp size={20} />}
      actions={
        <DarkButton icon={<Play size={18} />} onClick={() => generateMutation.mutate()} disabled={isGenerating}>
          {isGenerating ? <><Loader2 size={18} className="animate-spin" /> Generating...</> : 'Generate Forecast'}
        </DarkButton>
      }
    >
      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput placeholder="Search products..." value={search} onChange={(e) => setSearch(e.target.value)} onClear={() => setSearch('')} containerClassName="w-72" />
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {[4, 8, 12, 24].map((weeks) => (
            <DarkPillButton key={weeks} active={horizonWeeks === weeks} onClick={() => setHorizonWeeks(weeks)}>{weeks} weeks</DarkPillButton>
          ))}
        </div>
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <>
          {chartData.length > 0 && (
            <DarkCard className="mb-6" title="Forecast Trend">
              <div className="h-64 mt-4">
                <LineChart data={chartData} dataKey="Forecast" color="#4fd1c5" />
              </div>
            </DarkCard>
          )}

          <DarkCard padding="none">
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Product</DarkTableHeader>
                  <DarkTableHeader>Code</DarkTableHeader>
                  <DarkTableHeader>Current Stock</DarkTableHeader>
                  <DarkTableHeader>Avg Weekly Demand</DarkTableHeader>
                  <DarkTableHeader>Total Forecast</DarkTableHeader>
                  <DarkTableHeader>Weeks of Stock</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {(filteredForecast as ForecastItem[]).slice(0, 50).map((forecast, i: number) => (
                  <DarkTableRow key={forecast.id || i}>
                    <DarkTableCell className="text-text-white">{forecast.product_name || '-'}</DarkTableCell>
                    <DarkTableCell mono className="text-text-tertiary">{forecast.product_code || '-'}</DarkTableCell>
                    <DarkTableCell mono>{forecast.current_stock || 0}</DarkTableCell>
                    <DarkTableCell mono>{(forecast.avg_weekly_demand || 0).toFixed(1)}</DarkTableCell>
                    <DarkTableCell mono>{forecast.total_forecast || 0}</DarkTableCell>
                    <DarkTableCell mono className={(forecast.weeks_of_stock ?? 0) < 4 ? 'text-danger' : (forecast.weeks_of_stock ?? 0) < 8 ? 'text-amber' : 'text-success'}>
                      {(forecast.weeks_of_stock || 0).toFixed(1)}
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
                {filteredForecast.length === 0 && (
                  <DarkTableRow><DarkTableCell colSpan={6} className="text-center py-12"><TrendingUp size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No forecast data</p></DarkTableCell></DarkTableRow>
                )}
              </DarkTableBody>
            </DarkTable>
          </DarkCard>
        </>
      )}
    </DarkPageLayout>
  );
}

