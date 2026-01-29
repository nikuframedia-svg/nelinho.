import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { 
  BarChart3,
  Info,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Target,
  Package,
  HelpCircle,
  Ban,
  Lock,
} from 'lucide-react';
import { kpisApi } from '../../lib/api';
import { format } from 'date-fns';
import { formatCompactNumber } from '../../lib/utils';
import { DarkPageLayout } from '../../layouts';
import { DarkCard } from '../../components/dark';
import { NoDataState } from '../../components/ui';
import { Heatmap } from '../../components/charts';
import { ExplainDrawer } from '../../components/explain';
import { BLOCKED_METRICS } from '../../providers/CapabilitiesProvider';

interface Citation {
  source_type: string;
  ref: string;
  label: string;
  confidence?: number;
  trust_index?: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCKED KPI CARD - Shows when metric cannot be computed
// ═══════════════════════════════════════════════════════════════════════════════
function BlockedKPICard({ 
  label, 
  blockedReason,
  requiredData,
  learnMoreLink,
}: { 
  label: string; 
  blockedReason: string;
  requiredData?: readonly string[] | string[];
  learnMoreLink?: string;
}) {
  return (
    <div className="alpha-card p-5 group relative bg-danger/5 border-danger/20 opacity-80">
      <div className="flex items-center justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center bg-danger/20`}>
          <Lock size={20} className="text-danger" />
        </div>
        <div className="w-7 h-7 rounded-lg bg-danger/10 flex items-center justify-center">
          <Ban size={14} className="text-danger" />
        </div>
      </div>
      
      <p className="text-xs font-medium text-danger uppercase tracking-wider mb-1">{label}</p>
      
      <div className="flex items-baseline gap-1">
        <span className="text-lg font-bold text-danger">BLOCKED</span>
      </div>
      
      <div className="mt-3 pt-3 border-t border-danger/20">
        <p className="text-xs text-danger/80 leading-relaxed">{blockedReason}</p>
        {requiredData && requiredData.length > 0 && (
          <div className="mt-2">
            <p className="text-xs text-text-tertiary mb-1">Required data:</p>
            <div className="flex flex-wrap gap-1">
              {requiredData.map((data) => (
                <span key={data} className="text-xs px-2 py-0.5 rounded bg-danger/10 text-danger/80">
                  {data}
                </span>
              ))}
            </div>
          </div>
        )}
        {learnMoreLink && (
          <Link 
            to={learnMoreLink} 
            className="inline-flex items-center gap-1 mt-2 text-xs text-danger hover:text-danger-light transition-colors"
          >
            Learn more <ArrowRight size={12} />
          </Link>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// NORMAL KPI CARD
// ═══════════════════════════════════════════════════════════════════════════════
function DarkKPICard({ 
  label, 
  value, 
  unit = '%',
  icon,
  iconBgClass,
  reason,
  citations,
  isNumber = false,
  metricId,
  onExplainClick
}: { 
  label: string; 
  value: number | null; 
  unit?: string;
  icon: React.ReactNode;
  iconBgClass?: string;
  reason?: string | null;
  citations?: Citation[];
  isNumber?: boolean;
  metricId?: string;
  onExplainClick?: (metricId: string) => void;
}) {
  const hasValue = value !== null;
  const displayValue = hasValue ? (isNumber ? formatCompactNumber(value) : `${value.toFixed(1)}`) : '—';

  return (
    <div className="alpha-card p-5 group relative hover:bg-bg-elevated transition-all">
      <div className="flex items-center justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${iconBgClass || 'bg-accent/20'}`}>
          {icon}
        </div>
        <div className="flex items-center gap-2">
          {metricId && onExplainClick && (
            <button
              onClick={() => onExplainClick(metricId)}
              className="w-7 h-7 rounded-lg bg-accent/20 hover:bg-accent/30 flex items-center justify-center text-accent transition-colors opacity-0 group-hover:opacity-100"
              title="Explain this metric"
            >
              <HelpCircle size={14} />
            </button>
          )}
          {!hasValue && reason && (
            <div className="group/tooltip relative">
              <AlertTriangle size={16} className="text-amber" />
              <div className="absolute bottom-full right-0 mb-2 px-3 py-2 bg-bg-elevated text-text-primary text-xs rounded-lg opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all z-50 w-64 shadow-xl border border-border-subtle">
                {reason}
              </div>
            </div>
          )}
        </div>
      </div>
      
      <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider mb-1">{label}</p>
      
      <div className="flex items-baseline gap-1">
        <span className={`text-2xl font-bold ${hasValue ? 'text-text-white group-hover:text-accent transition-colors' : 'text-text-tertiary'}`}>
          {displayValue}
        </span>
        {hasValue && unit && <span className="text-sm font-medium text-text-tertiary">{unit}</span>}
      </div>
      
      {citations && citations.length > 0 && (
        <div className="mt-2 pt-2 border-t border-border-subtle">
          <p className="text-xs text-text-tertiary">{citations[0].label}</p>
        </div>
      )}
    </div>
  );
}

export function KPIsPage() {
  const [explainMetricId, setExplainMetricId] = useState<string | null>(null);
  
  const { data: kpiSnapshotData, isLoading, error } = useQuery({
    queryKey: ['kpis', 'snapshot-explained'],
    queryFn: () => kpisApi.getSnapshotExplained(),
    refetchInterval: 60000,
  });

  const kpiSnapshot = kpiSnapshotData?.snapshot;

  const { data: otdHeatmap, isLoading: heatmapLoading } = useQuery({
    queryKey: ['kpis', 'otd-heatmap'],
    queryFn: () => kpisApi.getOtdHeatmap(12),
    refetchInterval: 300000,
    enabled: !!kpiSnapshot,
  });

  const allKPIsNull = useMemo(() => {
    if (!kpiSnapshot) return true;
    return Object.values(kpiSnapshot).every((v: any) => v?.value === null || v?.value === undefined);
  }, [kpiSnapshot]);

  if (error) {
    return (
      <DarkPageLayout title="KPIs Snapshot" icon={<BarChart3 size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading KPIs</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  if (isLoading) {
    return (
      <DarkPageLayout title="KPIs Snapshot" icon={<BarChart3 size={20} />}>
        <DarkCard className="text-center py-12">
          <div className="animate-pulse flex flex-col items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-accent/20" />
            <p className="text-text-secondary">Loading KPIs snapshot...</p>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  if (!kpiSnapshot || allKPIsNull) {
    return (
      <DarkPageLayout title="KPIs Snapshot" icon={<BarChart3 size={20} />}>
        <NoDataState title="No KPI data available" message="KPIs have not been calculated yet or there is insufficient data." />
      </DarkPageLayout>
    );
  }

  const lastUpdated = kpiSnapshot.updated_at ? format(new Date(kpiSnapshot.updated_at), 'dd MMM yyyy HH:mm') : 'N/A';

  return (
    <DarkPageLayout
      title="KPIs Snapshot"
      subtitle={`Last updated: ${lastUpdated}`}
      icon={<BarChart3 size={20} />}
    >
      {/* Info Banner */}
      <DarkCard className="mb-6 bg-accent/10 border-accent/20">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center shrink-0">
            <Info size={18} className="text-accent" />
          </div>
          <div>
            <p className="text-sm font-semibold text-accent">KPIs Source-of-Truth for COPILOT</p>
            <p className="text-sm text-text-secondary mt-1 leading-relaxed">
              These KPIs are calculated directly from the database and serve as source of truth for COPILOT.
              <strong className="text-text-primary"> OEE</strong> = Availability × Performance × Quality
            </p>
          </div>
        </div>
      </DarkCard>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {/* OEE - BLOCKED because no machine downtime data */}
        <BlockedKPICard 
          label="OEE" 
          blockedReason={BLOCKED_METRICS.oee_real.reason}
          requiredData={BLOCKED_METRICS.oee_real.required_data}
          learnMoreLink="/profit/oee"
        />
        {/* Availability - BLOCKED because no downtime data */}
        <BlockedKPICard 
          label="Availability" 
          blockedReason={BLOCKED_METRICS.availability_oee.reason}
          requiredData={BLOCKED_METRICS.availability_oee.required_data}
          learnMoreLink="/profit/oee"
        />
        {/* Performance - also blocked as it requires OEE components */}
        <BlockedKPICard 
          label="Performance" 
          blockedReason="Não existem dados de produção real vs planeada"
          requiredData={['actual_cycle_time', 'ideal_cycle_time']}
          learnMoreLink="/profit/oee"
        />
        <DarkKPICard label="Quality (FPY)" value={kpiSnapshot.quality_fpy.value} icon={<CheckCircle2 size={20} className="text-amber" />} iconBgClass="bg-amber/20" reason={kpiSnapshot.quality_fpy.reason} citations={kpiSnapshot.quality_fpy.citations} metricId="quality_fpy" onExplainClick={setExplainMetricId} />
        <DarkKPICard label="Rework Rate" value={kpiSnapshot.rework_rate.value} icon={<AlertTriangle size={20} className="text-danger" />} iconBgClass="bg-danger/20" reason={kpiSnapshot.rework_rate.reason} citations={kpiSnapshot.rework_rate.citations} metricId="rework_rate_pct" onExplainClick={setExplainMetricId} />
        <DarkKPICard label="Orders Total" value={kpiSnapshot.orders_total.value} unit="" icon={<Package size={20} className="text-text-secondary" />} iconBgClass="bg-bg-elevated" reason={kpiSnapshot.orders_total.reason} citations={kpiSnapshot.orders_total.citations} isNumber metricId="orders_total" onExplainClick={setExplainMetricId} />
        <DarkKPICard label="Orders In Progress" value={kpiSnapshot.orders_in_progress.value} unit="" icon={<Target size={20} className="text-blue" />} iconBgClass="bg-blue/20" reason={kpiSnapshot.orders_in_progress.reason} citations={kpiSnapshot.orders_in_progress.citations} isNumber metricId="orders_in_progress" onExplainClick={setExplainMetricId} />
        <DarkKPICard label="Orders Completed" value={kpiSnapshot.orders_completed.value} unit="" icon={<CheckCircle2 size={20} className="text-success" />} iconBgClass="bg-success/20" reason={kpiSnapshot.orders_completed.reason} citations={kpiSnapshot.orders_completed.citations} isNumber metricId="orders_completed" onExplainClick={setExplainMetricId} />
      </div>

      {/* OTD Heatmap */}
      {otdHeatmap && (
        <DarkCard className="mb-6" title="On-Time Delivery Heatmap" subtitle="OTD percentage by product type and week (last 12 weeks)">
          {heatmapLoading ? (
            <div className="h-96 flex items-center justify-center">
              <p className="text-text-secondary">Loading heatmap...</p>
            </div>
          ) : (
            <div className="mt-4">
              <Heatmap data={otdHeatmap} height={400} />
            </div>
          )}
        </DarkCard>
      )}

      {/* Links */}
      <div className="flex items-center gap-4 pt-4 border-t border-border-subtle">
        <p className="text-sm text-text-secondary">View more details:</p>
        <Link to="/profit/oee" className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue/20 hover:bg-blue/30 text-blue font-medium text-sm transition-colors">
          OEE Dashboard <ArrowRight size={16} />
        </Link>
        <Link to="/profit/quality" className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber/20 hover:bg-amber/30 text-amber font-medium text-sm transition-colors">
          Quality Page <ArrowRight size={16} />
        </Link>
      </div>
      
      <ExplainDrawer open={!!explainMetricId} onClose={() => setExplainMetricId(null)} metricId={explainMetricId || ''} />
    </DarkPageLayout>
  );
}
