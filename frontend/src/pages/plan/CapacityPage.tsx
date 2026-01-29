import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, AlertTriangle, Loader2, RefreshCw, Gauge } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkBadge } from '../../components/dark';
import { planApi, machinesApi } from '../../lib/api';
import { BarChart } from '../../components/charts';

export function CapacityPage() {
  const { data: capacityData = [], isLoading, error } = useQuery({
    queryKey: ['capacity', 'analysis'],
    queryFn: () => planApi.getCapacityAnalysis(),
  });

  useQuery({
    queryKey: ['machines', 'list'],
    queryFn: () => machinesApi.list({ limit: 100 }),
  });

  const stats = useMemo(() => {
    if (!capacityData.length) return { avgUtilization: 0, bottlenecks: 0, underutilized: 0, optimal: 0 };
    const total = capacityData.length;
    const avgUtilization = capacityData.reduce((sum: number, c: any) => sum + (c.utilization || 0), 0) / total;
    const bottlenecks = capacityData.filter((c: any) => c.utilization > 90).length;
    const underutilized = capacityData.filter((c: any) => c.utilization < 50).length;
    const optimal = capacityData.filter((c: any) => c.utilization >= 50 && c.utilization <= 90).length;
    return { avgUtilization, bottlenecks, underutilized, optimal };
  }, [capacityData]);

  const chartData = useMemo(() => {
    return capacityData.slice(0, 10).map((c: any) => ({
      name: c.resource_name || c.machine_name || 'Resource',
      Utilization: c.utilization || 0,
    }));
  }, [capacityData]);

  if (error) {
    return (
      <DarkPageLayout title="Capacity Analysis" icon={<Activity size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading capacity data</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="Capacity Analysis"
      subtitle={isLoading ? 'Loading...' : `${capacityData.length} resources analyzed`}
      icon={<Activity size={20} />}
      actions={
        <DarkButton variant="secondary" icon={<RefreshCw size={18} />}>
          Refresh Analysis
        </DarkButton>
      }
    >
      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <DarkStatCard icon={<Gauge size={18} />} label="Avg Utilization" value={`${stats.avgUtilization.toFixed(1)}%`} size="sm" />
        <DarkStatCard icon={<AlertTriangle size={18} />} iconBg="bg-danger/20" label="Bottlenecks (>90%)" value={stats.bottlenecks} size="sm" />
        <DarkStatCard icon={<Activity size={18} />} iconBg="bg-amber/20" label="Underutilized (<50%)" value={stats.underutilized} size="sm" />
        <DarkStatCard icon={<Activity size={18} />} iconBg="bg-success/20" label="Optimal (50-90%)" value={stats.optimal} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <>
          {/* Chart */}
          {chartData.length > 0 && (
            <DarkCard className="mb-6" title="Resource Utilization">
              <div className="h-64 mt-4">
                <BarChart data={chartData} dataKey="Utilization" color="#4fd1c5" />
              </div>
            </DarkCard>
          )}

          {/* Table */}
          <DarkCard padding="none">
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Resource</DarkTableHeader>
                  <DarkTableHeader>Type</DarkTableHeader>
                  <DarkTableHeader>Available Hours</DarkTableHeader>
                  <DarkTableHeader>Loaded Hours</DarkTableHeader>
                  <DarkTableHeader>Utilization</DarkTableHeader>
                  <DarkTableHeader>Status</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {capacityData.slice(0, 30).map((item: any, i: number) => (
                  <DarkTableRow key={item.id || i}>
                    <DarkTableCell className="text-text-white">{item.resource_name || item.machine_name || '-'}</DarkTableCell>
                    <DarkTableCell className="text-text-tertiary">{item.resource_type || 'Machine'}</DarkTableCell>
                    <DarkTableCell mono>{item.available_hours || 0}h</DarkTableCell>
                    <DarkTableCell mono>{item.loaded_hours || 0}h</DarkTableCell>
                    <DarkTableCell>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-bg-elevated rounded-full overflow-hidden max-w-24">
                          <div 
                            className={`h-full rounded-full ${
                              item.utilization > 90 ? 'bg-danger' : 
                              item.utilization < 50 ? 'bg-amber' : 'bg-success'
                            }`} 
                            style={{ width: `${Math.min(item.utilization || 0, 100)}%` }} 
                          />
                        </div>
                        <span className="text-xs text-text-tertiary w-12">{(item.utilization || 0).toFixed(1)}%</span>
                      </div>
                    </DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge variant={
                        item.utilization > 90 ? 'danger' :
                        item.utilization < 50 ? 'warning' : 'success'
                      } dot>
                        {item.utilization > 90 ? 'Bottleneck' : item.utilization < 50 ? 'Low' : 'Optimal'}
                      </DarkBadge>
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
                {capacityData.length === 0 && (
                  <DarkTableRow>
                    <DarkTableCell colSpan={6} className="text-center py-12">
                      <Activity size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                      <p className="text-text-secondary">No capacity data</p>
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
