/**
 * Blocked Metrics Notice Component
 * =================================
 * 
 * Displays a list of blocked metrics with their reasons.
 * Used to inform users about unavailable data.
 * 
 * Source: src/factory_data_product/config.py BLOCKED_METRICS
 */

import { useState } from 'react';
import { Ban, ChevronDown, ChevronUp, AlertCircle, Info, X } from 'lucide-react';
import { BLOCKED_METRICS, BLOCKED_METRIC_IDS } from '../../providers/CapabilitiesProvider';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface BlockedMetricsNoticeProps {
  // Show only specific metrics (if provided, otherwise show all)
  metrics?: string[];
  // Visual variant
  variant?: 'banner' | 'card' | 'minimal' | 'collapsible';
  // Allow dismissal
  dismissable?: boolean;
  // Custom title
  title?: string;
  // Additional class names
  className?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function BlockedMetricsNotice({
  metrics,
  variant = 'banner',
  dismissable = false,
  title = 'Blocked Metrics',
  className = '',
}: BlockedMetricsNoticeProps) {
  const [isExpanded, setIsExpanded] = useState(variant !== 'collapsible');
  const [isDismissed, setIsDismissed] = useState(false);

  // Filter to show only specified metrics or all
  const displayMetrics = metrics 
    ? metrics.filter(m => BLOCKED_METRIC_IDS.includes(m as keyof typeof BLOCKED_METRICS))
    : BLOCKED_METRIC_IDS;

  if (isDismissed || displayMetrics.length === 0) {
    return null;
  }

  // Minimal variant
  if (variant === 'minimal') {
    return (
      <div className={`text-red-400 text-xs flex items-center gap-1 ${className}`}>
        <Ban size={12} />
        <span>{displayMetrics.length} blocked metrics</span>
      </div>
    );
  }

  // Collapsible variant
  if (variant === 'collapsible') {
    return (
      <div className={`bg-red-500/5 border border-red-500/20 rounded-xl ${className}`}>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex items-center justify-between p-4 text-left"
        >
          <div className="flex items-center gap-3">
            <Ban size={18} className="text-red-400" />
            <span className="font-medium text-red-300">{title}</span>
            <span className="text-xs px-2 py-0.5 bg-red-500/20 text-red-400 rounded-full">
              {displayMetrics.length}
            </span>
          </div>
          {isExpanded ? (
            <ChevronUp size={18} className="text-red-400" />
          ) : (
            <ChevronDown size={18} className="text-red-400" />
          )}
        </button>
        
        {isExpanded && (
          <div className="px-4 pb-4 pt-0">
            <div className="space-y-2">
              {displayMetrics.map((metricId) => {
                const info = BLOCKED_METRICS[metricId as keyof typeof BLOCKED_METRICS];
                return (
                  <div 
                    key={metricId}
                    className="p-3 bg-slate-800/50 rounded-lg"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <AlertCircle size={14} className="text-red-400" />
                      <span className="font-medium text-red-300 text-sm">{metricId}</span>
                    </div>
                    <p className="text-xs text-slate-400 pl-6">{info?.reason}</p>
                    {info?.required_data && (
                      <div className="pl-6 mt-2 flex flex-wrap gap-1">
                        {info.required_data.map((data) => (
                          <span key={data} className="text-[10px] px-1.5 py-0.5 bg-slate-700 text-slate-300 rounded">
                            {data}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Banner variant
  if (variant === 'banner') {
    return (
      <div className={`p-4 bg-red-500/10 border border-red-500/20 rounded-xl relative ${className}`}>
        {dismissable && (
          <button
            onClick={() => setIsDismissed(true)}
            className="absolute top-3 right-3 p-1 text-slate-400 hover:text-white transition-colors"
          >
            <X size={16} />
          </button>
        )}
        <div className="flex items-start gap-3">
          <div className="p-2 bg-red-500/20 rounded-lg flex-shrink-0">
            <Ban size={20} className="text-red-400" />
          </div>
          <div className="flex-1 pr-6">
            <h4 className="font-medium text-red-300 mb-2">{title}</h4>
            <p className="text-sm text-slate-400 mb-3">
              These metrics cannot be calculated due to missing data in the source Excel file.
            </p>
            <div className="flex flex-wrap gap-2">
              {displayMetrics.map((metricId) => (
                <span 
                  key={metricId}
                  className="inline-flex items-center gap-1 px-2 py-1 bg-red-500/20 text-red-300 rounded text-xs"
                  title={BLOCKED_METRICS[metricId as keyof typeof BLOCKED_METRICS]?.reason}
                >
                  <AlertCircle size={10} />
                  {metricId}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Card variant (default)
  return (
    <div className={`bg-slate-800/50 border border-red-500/20 rounded-xl ${className}`}>
      <div className="p-4 border-b border-slate-700/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/20 rounded-lg">
              <Ban size={20} className="text-red-400" />
            </div>
            <div>
              <h3 className="font-semibold text-white">{title}</h3>
              <p className="text-xs text-slate-400">Cannot be calculated - missing source data</p>
            </div>
          </div>
          {dismissable && (
            <button
              onClick={() => setIsDismissed(true)}
              className="p-2 text-slate-400 hover:text-white transition-colors rounded-lg hover:bg-slate-700/50"
            >
              <X size={18} />
            </button>
          )}
        </div>
      </div>
      <div className="p-4 space-y-3">
        {displayMetrics.map((metricId) => {
          const info = BLOCKED_METRICS[metricId as keyof typeof BLOCKED_METRICS];
          return (
            <div 
              key={metricId}
              className="p-4 bg-red-500/5 border border-red-500/10 rounded-lg"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <AlertCircle size={16} className="text-red-400" />
                  <span className="font-medium text-red-300">{metricId}</span>
                </div>
                <span className="text-[10px] px-2 py-0.5 bg-red-500/20 text-red-400 rounded-full uppercase tracking-wide">
                  Blocked
                </span>
              </div>
              <p className="text-sm text-slate-400 mb-3">{info?.reason}</p>
              {info?.required_data && info.required_data.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 mb-2">Required to enable:</p>
                  <div className="flex flex-wrap gap-1">
                    {info.required_data.map((data) => (
                      <span 
                        key={data} 
                        className="text-xs px-2 py-1 bg-slate-700 text-slate-300 rounded"
                      >
                        {data}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="px-4 py-3 bg-slate-900/50 border-t border-slate-700/50 rounded-b-xl">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Info size={12} />
          <span>Source: src/factory_data_product/config.py BLOCKED_METRICS</span>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SINGLE BLOCKED METRIC
// ═══════════════════════════════════════════════════════════════════════════════

export function BlockedMetricTag({ 
  metricId, 
  showReason = false,
  className = '',
}: { 
  metricId: string; 
  showReason?: boolean;
  className?: string;
}) {
  const info = BLOCKED_METRICS[metricId as keyof typeof BLOCKED_METRICS];
  
  if (!info) {
    return null;
  }

  if (showReason) {
    return (
      <div className={`flex items-start gap-2 p-2 bg-red-500/10 border border-red-500/20 rounded-lg ${className}`}>
        <Ban size={14} className="text-red-400 mt-0.5 flex-shrink-0" />
        <div>
          <span className="text-sm text-red-300 font-medium">{metricId}</span>
          <p className="text-xs text-red-400/80 mt-0.5">{info.reason}</p>
        </div>
      </div>
    );
  }

  return (
    <span 
      className={`inline-flex items-center gap-1 px-2 py-1 bg-red-500/20 text-red-300 rounded text-xs ${className}`}
      title={info.reason}
    >
      <Ban size={10} />
      {metricId}
    </span>
  );
}

export default BlockedMetricsNotice;

