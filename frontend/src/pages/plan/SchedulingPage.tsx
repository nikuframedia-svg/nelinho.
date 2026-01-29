import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Calendar, Play, Clock, AlertTriangle, Loader2, RefreshCw, Download } from 'lucide-react';
import { format } from 'date-fns';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkBadge } from '../../components/dark';
import { planApi, ordersApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';
import { GanttChart } from '../../components/charts';

export function SchedulingPage() {
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [isGenerating, setIsGenerating] = useState(false);
  const toast = useToastContext();
  const queryClient = useQueryClient();

  // FIX: API returns {data: [], total: 0} - extract .data from response
  const { data: schedulesResponse, isLoading, error } = useQuery({
    queryKey: ['schedules', 'list'],
    queryFn: () => planApi.getSchedules({ limit: 100 }),
  });

  // Normalize response - handle both array and {data: []} formats
  const schedules = useMemo(() => {
    if (!schedulesResponse) return [];
    if (Array.isArray(schedulesResponse)) return schedulesResponse;
    if (schedulesResponse.data && Array.isArray(schedulesResponse.data)) return schedulesResponse.data;
    return [];
  }, [schedulesResponse]);

  useQuery({
    queryKey: ['orders', 'list'],
    queryFn: () => ordersApi.list({ limit: 500 }),
  });

  const generateMutation = useMutation({
    mutationFn: () => planApi.generateSchedule({ horizon_days: 14 }),
    onMutate: () => setIsGenerating(true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      toast.success('Schedule generated successfully');
    },
    onError: (err: any) => toast.error(err.message || 'Generation failed'),
    onSettled: () => setIsGenerating(false),
  });

  const filteredSchedules = useMemo(() => {
    if (filterStatus === 'ALL') return schedules;
    return schedules.filter((s: any) => s.status === filterStatus);
  }, [schedules, filterStatus]);

  const stats = useMemo(() => ({
    total: schedules.length,
    scheduled: schedules.filter((s: any) => s.status === 'SCHEDULED').length,
    inProgress: schedules.filter((s: any) => s.status === 'IN_PROGRESS').length,
    completed: schedules.filter((s: any) => s.status === 'COMPLETED').length,
    delayed: schedules.filter((s: any) => s.status === 'DELAYED').length,
  }), [schedules]);

  // Prepare Gantt data
  const ganttData = useMemo(() => {
    return filteredSchedules.slice(0, 20).map((s: any, i: number) => ({
      id: s.id?.toString() || `task-${i}`,
      name: s.order_code || s.product_name || `Order ${i + 1}`,
      start: s.scheduled_start || new Date().toISOString(),
      end: s.scheduled_end || new Date(Date.now() + 86400000).toISOString(),
      status: s.status,
    }));
  }, [filteredSchedules]);

  const ganttDateRange = useMemo(() => {
    if (ganttData.length === 0) {
      return { startDate: new Date(), endDate: new Date(Date.now() + 7 * 86400000) };
    }
    const starts = ganttData.map((d: { start: string }) => new Date(d.start).getTime());
    const ends = ganttData.map((d: { end: string }) => new Date(d.end).getTime());
    return {
      startDate: new Date(Math.min(...starts)),
      endDate: new Date(Math.max(...ends)),
    };
  }, [ganttData]);

  if (error) {
    return (
      <DarkPageLayout title="Production Scheduling" icon={<Calendar size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading schedules</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="Production Scheduling"
      subtitle={isLoading ? 'Loading...' : `${schedules.length} scheduled orders`}
      icon={<Calendar size={20} />}
      actions={
        <div className="flex items-center gap-2">
          <DarkButton variant="secondary" icon={<Download size={18} />}>Export</DarkButton>
          <DarkButton icon={<Play size={18} />} onClick={() => generateMutation.mutate()} disabled={isGenerating}>
            {isGenerating ? <><Loader2 size={18} className="animate-spin" /> Generating...</> : 'Generate Schedule'}
          </DarkButton>
        </div>
      }
    >
      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'DELAYED'].map((status) => (
            <DarkPillButton key={status} active={filterStatus === status} onClick={() => setFilterStatus(status)}>
              {status.replace('_', ' ')}
            </DarkPillButton>
          ))}
        </div>
        <DarkButton variant="ghost" size="sm" icon={<RefreshCw size={14} />} onClick={() => queryClient.invalidateQueries({ queryKey: ['schedules'] })}>
          Refresh
        </DarkButton>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <DarkStatCard icon={<Calendar size={18} />} label="Total" value={stats.total} size="sm" />
        <DarkStatCard icon={<Clock size={18} />} iconBg="bg-blue/20" label="Scheduled" value={stats.scheduled} size="sm" />
        <DarkStatCard icon={<Play size={18} />} iconBg="bg-amber/20" label="In Progress" value={stats.inProgress} size="sm" />
        <DarkStatCard icon={<Calendar size={18} />} iconBg="bg-success/20" label="Completed" value={stats.completed} size="sm" />
        <DarkStatCard icon={<AlertTriangle size={18} />} iconBg="bg-danger/20" label="Delayed" value={stats.delayed} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <>
          {/* Gantt Chart */}
          {ganttData.length > 0 && (
            <DarkCard className="mb-6" title="Schedule Timeline">
              <div className="h-96 mt-4">
                <GanttChart tasks={ganttData} startDate={ganttDateRange.startDate} endDate={ganttDateRange.endDate} />
              </div>
            </DarkCard>
          )}

          {/* Table */}
          <DarkCard padding="none">
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Order</DarkTableHeader>
                  <DarkTableHeader>Product</DarkTableHeader>
                  <DarkTableHeader>Quantity</DarkTableHeader>
                  <DarkTableHeader>Scheduled Start</DarkTableHeader>
                  <DarkTableHeader>Scheduled End</DarkTableHeader>
                  <DarkTableHeader>Progress</DarkTableHeader>
                  <DarkTableHeader>Status</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {filteredSchedules.slice(0, 50).map((schedule: any, i: number) => (
                  <DarkTableRow key={schedule.id || i}>
                    <DarkTableCell mono className="text-text-white">{schedule.order_code || '-'}</DarkTableCell>
                    <DarkTableCell>{schedule.product_name || '-'}</DarkTableCell>
                    <DarkTableCell mono>{schedule.quantity || 0}</DarkTableCell>
                    <DarkTableCell>{schedule.scheduled_start ? format(new Date(schedule.scheduled_start), 'dd/MM HH:mm') : '-'}</DarkTableCell>
                    <DarkTableCell>{schedule.scheduled_end ? format(new Date(schedule.scheduled_end), 'dd/MM HH:mm') : '-'}</DarkTableCell>
                    <DarkTableCell>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-bg-elevated rounded-full overflow-hidden max-w-20">
                          <div className="h-full bg-accent rounded-full" style={{ width: `${schedule.progress || 0}%` }} />
                        </div>
                        <span className="text-xs text-text-tertiary">{schedule.progress || 0}%</span>
                      </div>
                    </DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge variant={
                        schedule.status === 'COMPLETED' ? 'success' :
                        schedule.status === 'IN_PROGRESS' ? 'warning' :
                        schedule.status === 'DELAYED' ? 'danger' : 'info'
                      } dot>
                        {schedule.status || 'PENDING'}
                      </DarkBadge>
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
                {filteredSchedules.length === 0 && (
                  <DarkTableRow>
                    <DarkTableCell colSpan={7} className="text-center py-12">
                      <Calendar size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                      <p className="text-text-secondary">No schedules found</p>
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
