/**
 * Scenario Diff Viewer Component
 * ==============================
 * 
 * Displays before/after comparison of scenario simulation.
 * Automatically filters out BLOCKED metrics.
 * Shows trust index for each metric.
 * 
 * Used in: Twin Sandbox, Delta Wizard results
 */

import { useMemo } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Minus, 
  Shield, 
  Ban, 
  ChevronRight,
  AlertTriangle,
  Info,
} from 'lucide-react';
import { BLOCKED_METRICS, BLOCKED_METRIC_IDS } from '../../providers/CapabilitiesProvider';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface MetricValue {
  value: number | null;
  status?: 'OK' | 'WARNING' | 'BLOCKED' | 'DEGRADED';
  trust_index?: number;
  semantic_label?: string;
  reason?: string;
}

interface ScenarioDiffViewerProps {
  // Before state (baseline)
  beforeState: Record<string, MetricValue | number | null>;
  // After state (simulated)
  afterState: Record<string, MetricValue | number | null>;
  // Optional: Show only these metrics
  metrics?: string[];
  // Title for the viewer
  title?: string;
  // Show blocked metrics section
  showBlockedMetrics?: boolean;
  // Show trust index
  showTrust?: boolean;
  // Additional class names
  className?: string;
}

interface ProcessedMetric {
  id: string;
  label: string;
  before: number | null;
  after: number | null;
  change: number | null;
  changePercent: number | null;
  trustIndex: number;
  status: 'OK' | 'WARNING' | 'BLOCKED' | 'DEGRADED';
  semanticLabel?: string;
  isBlocked: boolean;
  blockedReason?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

function formatMetricLabel(id: string): string {
  return id
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase())
    .replace('Theoretical', '(Theoretical)')
    .replace('Observed', '(Observed)');
}

function extractValue(data: MetricValue | number | null): number | null {
  if (data === null || data === undefined) return null;
  if (typeof data === 'number') return data;
  return data.value ?? null;
}

function extractStatus(data: MetricValue | number | null): 'OK' | 'WARNING' | 'BLOCKED' | 'DEGRADED' {
  if (data === null || data === undefined) return 'OK';
  if (typeof data === 'number') return 'OK';
  return data.status ?? 'OK';
}

function extractTrust(data: MetricValue | number | null): number {
  if (data === null || data === undefined) return 0;
  if (typeof data === 'number') return 50;
  return data.trust_index ?? 50;
}

// ═══════════════════════════════════════════════════════════════════════════════
// METRIC ROW COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function MetricRow({ metric, showTrust }: { metric: ProcessedMetric; showTrust: boolean }) {
  const getTrustColor = (trust: number) => {
    if (trust >= 70) return 'text-emerald-400 bg-emerald-500/20';
    if (trust >= 50) return 'text-amber-400 bg-amber-500/20';
    return 'text-red-400 bg-red-500/20';
  };

  const getChangeColor = (change: number | null) => {
    if (change === null) return 'text-slate-400';
    if (change > 0) return 'text-emerald-400';
    if (change < 0) return 'text-red-400';
    return 'text-slate-400';
  };

  const getChangeIcon = (change: number | null) => {
    if (change === null) return <Minus size={16} className="text-slate-400" />;
    if (change > 0) return <TrendingUp size={16} className="text-emerald-400" />;
    if (change < 0) return <TrendingDown size={16} className="text-red-400" />;
    return <Minus size={16} className="text-slate-400" />;
  };

  // Blocked metric row
  if (metric.isBlocked) {
    return (
      <div className="flex items-center justify-between p-3 bg-red-500/5 border border-red-500/10 rounded-lg opacity-60">
        <div className="flex items-center gap-3">
          <Ban size={16} className="text-red-400" />
          <div>
            <span className="text-sm text-red-300">{metric.label}</span>
            {metric.blockedReason && (
              <p className="text-xs text-red-400/60">{metric.blockedReason}</p>
            )}
          </div>
        </div>
        <span className="text-xs px-2 py-0.5 bg-red-500/20 text-red-400 rounded">BLOCKED</span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between p-3 bg-slate-800/30 border border-slate-700/30 rounded-lg">
      <div className="flex items-center gap-3 flex-1">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm text-white font-medium truncate">{metric.label}</span>
            {metric.semanticLabel && (
              <span className="text-[10px] text-slate-500 italic">({metric.semanticLabel})</span>
            )}
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-6">
        {/* Before value */}
        <div className="text-right w-24">
          <p className="text-[10px] text-slate-500 mb-0.5">Before</p>
          <p className="text-sm text-slate-300 font-mono">
            {metric.before !== null ? metric.before.toLocaleString() : '—'}
          </p>
        </div>
        
        {/* Arrow */}
        <ChevronRight size={16} className="text-slate-600" />
        
        {/* After value */}
        <div className="text-right w-24">
          <p className="text-[10px] text-slate-500 mb-0.5">After</p>
          <p className="text-sm text-white font-mono font-medium">
            {metric.after !== null ? metric.after.toLocaleString() : '—'}
          </p>
        </div>
        
        {/* Change */}
        <div className="flex items-center gap-2 w-28 justify-end">
          {getChangeIcon(metric.change)}
          <span className={`text-sm font-medium ${getChangeColor(metric.changePercent)}`}>
            {metric.changePercent !== null 
              ? `${metric.changePercent > 0 ? '+' : ''}${metric.changePercent.toFixed(1)}%`
              : '—'}
          </span>
        </div>
        
        {/* Trust badge */}
        {showTrust && (
          <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${getTrustColor(metric.trustIndex)}`}>
            <Shield size={12} />
            <span>{metric.trustIndex}%</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function ScenarioDiffViewer({
  beforeState,
  afterState,
  metrics,
  title = 'Simulation Results',
  showBlockedMetrics = true,
  showTrust = true,
  className = '',
}: ScenarioDiffViewerProps) {
  // Process metrics
  const { availableMetrics, blockedMetrics } = useMemo(() => {
    const available: ProcessedMetric[] = [];
    const blocked: ProcessedMetric[] = [];
    
    // Get all metric keys from both states
    const allKeys = new Set([
      ...Object.keys(beforeState),
      ...Object.keys(afterState),
    ]);
    
    // Filter to specified metrics if provided
    const keysToProcess = metrics 
      ? Array.from(allKeys).filter(k => metrics.includes(k))
      : Array.from(allKeys);
    
    for (const key of keysToProcess) {
      // Skip internal/metadata keys
      if (key.startsWith('_')) continue;
      
      const beforeData = beforeState[key];
      const afterData = afterState[key];
      
      const beforeValue = extractValue(beforeData);
      const afterValue = extractValue(afterData);
      const status = extractStatus(afterData) || extractStatus(beforeData);
      const trustIndex = extractTrust(afterData) || extractTrust(beforeData);
      
      // Check if metric is blocked
      const isBlocked = BLOCKED_METRIC_IDS.some(blocked => 
        key.toLowerCase().includes(blocked.toLowerCase())
      ) || status === 'BLOCKED';
      
      const blockedInfo = BLOCKED_METRICS[key as keyof typeof BLOCKED_METRICS];
      
      // Calculate change
      let change: number | null = null;
      let changePercent: number | null = null;
      if (beforeValue !== null && afterValue !== null) {
        change = afterValue - beforeValue;
        if (beforeValue !== 0) {
          changePercent = (change / beforeValue) * 100;
        }
      }
      
      const processedMetric: ProcessedMetric = {
        id: key,
        label: formatMetricLabel(key),
        before: beforeValue,
        after: afterValue,
        change,
        changePercent,
        trustIndex,
        status,
        semanticLabel: typeof afterData === 'object' ? afterData?.semantic_label : undefined,
        isBlocked,
        blockedReason: blockedInfo?.reason || (typeof afterData === 'object' ? afterData?.reason : undefined),
      };
      
      if (isBlocked) {
        blocked.push(processedMetric);
      } else {
        available.push(processedMetric);
      }
    }
    
    // Sort by trust index (highest first)
    available.sort((a, b) => b.trustIndex - a.trustIndex);
    
    return { availableMetrics: available, blockedMetrics: blocked };
  }, [beforeState, afterState, metrics]);

  // Calculate summary
  const summary = useMemo(() => {
    const improvements = availableMetrics.filter(m => m.changePercent !== null && m.changePercent > 0);
    const degradations = availableMetrics.filter(m => m.changePercent !== null && m.changePercent < 0);
    const unchanged = availableMetrics.filter(m => m.changePercent === 0 || m.changePercent === null);
    
    return { improvements: improvements.length, degradations: degradations.length, unchanged: unchanged.length };
  }, [availableMetrics]);

  return (
    <div className={`bg-slate-900 border border-slate-700 rounded-xl ${className}`}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-700">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1">
              <TrendingUp size={14} className="text-emerald-400" />
              <span className="text-emerald-400">{summary.improvements} improved</span>
            </div>
            <div className="flex items-center gap-1">
              <TrendingDown size={14} className="text-red-400" />
              <span className="text-red-400">{summary.degradations} degraded</span>
            </div>
            <div className="flex items-center gap-1">
              <Minus size={14} className="text-slate-400" />
              <span className="text-slate-400">{summary.unchanged} unchanged</span>
            </div>
          </div>
        </div>
      </div>

      {/* Available metrics */}
      <div className="p-4">
        {availableMetrics.length > 0 ? (
          <div className="space-y-2">
            {availableMetrics.map((metric) => (
              <MetricRow key={metric.id} metric={metric} showTrust={showTrust} />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-slate-400">
            <Info size={24} className="mx-auto mb-2 opacity-50" />
            <p>No available metrics to display</p>
          </div>
        )}
      </div>

      {/* Blocked metrics section */}
      {showBlockedMetrics && blockedMetrics.length > 0 && (
        <div className="px-4 pb-4">
          <div className="border-t border-slate-700 pt-4">
            <div className="flex items-center gap-2 mb-3">
              <Ban size={16} className="text-red-400" />
              <span className="text-sm text-red-300 font-medium">
                {blockedMetrics.length} Blocked Metrics (Not Simulated)
              </span>
            </div>
            <div className="space-y-2">
              {blockedMetrics.map((metric) => (
                <MetricRow key={metric.id} metric={metric} showTrust={false} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-3 bg-slate-800/50 border-t border-slate-700 rounded-b-xl">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <AlertTriangle size={12} />
          <span>Results are theoretical estimates. Blocked metrics cannot be simulated due to missing source data.</span>
        </div>
      </div>
    </div>
  );
}

export default ScenarioDiffViewer;

