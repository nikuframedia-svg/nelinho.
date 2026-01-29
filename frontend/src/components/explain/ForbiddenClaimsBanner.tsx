/**
 * Forbidden Claims Banner Component
 * ==================================
 * 
 * Displays forbidden_claims from ExplainedValue contract.
 * Shows what claims CANNOT be made about a metric.
 * 
 * Source: src/explain/catalog.py MetricDefinition.forbidden_claims
 */

import { Ban, AlertOctagon, Info, X } from 'lucide-react';
import { useState } from 'react';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface ForbiddenClaimsBannerProps {
  // List of forbidden claims
  claims: string[];
  // Metric ID for context
  metricId?: string;
  // Metric name for display
  metricName?: string;
  // Visual variant
  variant?: 'banner' | 'card' | 'inline' | 'tooltip';
  // Allow dismissal
  dismissable?: boolean;
  // Additional class names
  className?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function ForbiddenClaimsBanner({
  claims,
  metricName,
  variant = 'banner',
  dismissable = false,
  className = '',
}: ForbiddenClaimsBannerProps) {
  const [isDismissed, setIsDismissed] = useState(false);

  if (isDismissed || !claims || claims.length === 0) {
    return null;
  }

  // Inline variant - compact
  if (variant === 'inline') {
    return (
      <div className={`flex items-center gap-2 text-amber-400 ${className}`}>
        <AlertOctagon size={14} />
        <span className="text-xs">{claims.length} forbidden claims</span>
      </div>
    );
  }

  // Tooltip variant - for hover states
  if (variant === 'tooltip') {
    return (
      <div className={`p-3 bg-slate-800 border border-amber-500/30 rounded-lg shadow-xl ${className}`}>
        <div className="flex items-center gap-2 mb-2">
          <AlertOctagon size={14} className="text-amber-400" />
          <span className="text-xs font-medium text-amber-300">Forbidden Claims</span>
        </div>
        <ul className="space-y-1">
          {claims.map((claim, idx) => (
            <li key={idx} className="text-xs text-slate-400 flex items-start gap-2">
              <Ban size={10} className="text-amber-500 mt-0.5 flex-shrink-0" />
              <span>{claim}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  // Card variant
  if (variant === 'card') {
    return (
      <div className={`bg-slate-800/50 border border-amber-500/30 rounded-xl ${className}`}>
        <div className="p-4 border-b border-slate-700/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-500/20 rounded-lg">
                <AlertOctagon size={20} className="text-amber-400" />
              </div>
              <div>
                <h4 className="font-medium text-white">Forbidden Claims</h4>
                {metricName && (
                  <p className="text-xs text-slate-400">For metric: {metricName}</p>
                )}
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
        <div className="p-4">
          <p className="text-sm text-slate-400 mb-4">
            The following claims <strong className="text-amber-400">cannot be made</strong> based on available data:
          </p>
          <ul className="space-y-2">
            {claims.map((claim, idx) => (
              <li key={idx} className="flex items-start gap-3 p-3 bg-amber-500/5 border border-amber-500/10 rounded-lg">
                <Ban size={16} className="text-amber-400 mt-0.5 flex-shrink-0" />
                <span className="text-sm text-slate-300">{claim}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="px-4 py-3 bg-slate-900/50 border-t border-slate-700/50 rounded-b-xl">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Info size={12} />
            <span>Source: ExplainedValue.forbidden_claims from metric catalog</span>
          </div>
        </div>
      </div>
    );
  }

  // Banner variant (default)
  return (
    <div className={`p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl relative ${className}`}>
      {dismissable && (
        <button
          onClick={() => setIsDismissed(true)}
          className="absolute top-3 right-3 p-1 text-slate-400 hover:text-white transition-colors"
        >
          <X size={16} />
        </button>
      )}
      <div className="flex items-start gap-3">
        <div className="p-2 bg-amber-500/20 rounded-lg flex-shrink-0">
          <AlertOctagon size={20} className="text-amber-400" />
        </div>
        <div className="flex-1 pr-6">
          <h4 className="font-medium text-amber-300 mb-1">
            Forbidden Claims
            {metricName && <span className="text-amber-400/70 font-normal"> — {metricName}</span>}
          </h4>
          <p className="text-sm text-slate-400 mb-3">
            These claims cannot be made based on available data:
          </p>
          <ul className="space-y-2">
            {claims.map((claim, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <Ban size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
                <span className="text-sm text-amber-200/80">{claim}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// FORBIDDEN CLAIM TAG
// ═══════════════════════════════════════════════════════════════════════════════

export function ForbiddenClaimTag({ claim }: { claim: string }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-amber-500/20 text-amber-300 rounded text-xs">
      <Ban size={10} />
      {claim}
    </span>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PREDEFINED FORBIDDEN CLAIMS (from metric catalog)
// ═══════════════════════════════════════════════════════════════════════════════

export const METRIC_FORBIDDEN_CLAIMS: Record<string, string[]> = {
  oee_real: [
    'Cannot claim any OEE value',
    'Cannot claim machine efficiency',
  ],
  availability_oee: [
    'Cannot claim machine availability',
    'Cannot claim uptime percentage',
  ],
  otd_official: [
    'Cannot claim delivery performance',
    'Cannot claim on-time delivery rate',
  ],
  productivity_individual_real: [
    'Cannot claim individual productivity',
    'Cannot compare employee performance',
  ],
  cost_real_per_order: [
    'Cannot claim actual order costs',
    'Cannot calculate real profit margins',
  ],
  capacity_real_per_day: [
    'Cannot claim actual daily capacity',
    'Cannot plan based on real capacity',
  ],
  // Theoretical metrics also have claims
  wip_theoretical: [
    'Value is theoretical, not measured WIP',
    'Does not account for physical location',
  ],
  backlog_theoretical_hours: [
    'Based on HorasPrevistas with 56.6% zeros',
    'May significantly underestimate actual backlog',
  ],
};

export default ForbiddenClaimsBanner;

