/**
 * Capability Gate Component
 * =========================
 * 
 * Wraps features that require specific capabilities or metrics.
 * Shows blocking UI when capability is not available.
 * 
 * Usage:
 * <CapabilityGate module="twin" fallback={<BlockedMessage />}>
 *   <TwinFeature />
 * </CapabilityGate>
 * 
 * <CapabilityGate metric="oee_real" showBlockedReason>
 *   <OEEChart />
 * </CapabilityGate>
 */

import type { ReactNode } from 'react';
import { Ban, AlertTriangle } from 'lucide-react';
import { useCapabilities, BLOCKED_METRICS } from '../../providers/CapabilitiesProvider';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface CapabilityGateProps {
  children: ReactNode;
  // Gate by module (e.g., 'twin', 'copilot')
  module?: string;
  // Gate by feature (e.g., 'sandbox', 'simulation')
  feature?: string;
  // Gate by metric (e.g., 'oee_real')
  metric?: string;
  // Require minimum trust index
  minTrust?: number;
  // Custom fallback when blocked
  fallback?: ReactNode;
  // Show blocked reason in default fallback
  showBlockedReason?: boolean;
  // Variant affects visual style
  variant?: 'card' | 'inline' | 'banner' | 'minimal';
  // Additional class names
  className?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCKED STATE COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

interface BlockedStateProps {
  title: string;
  reason?: string;
  requiredData?: string[];
  variant: 'card' | 'inline' | 'banner' | 'minimal';
  className?: string;
}

function BlockedState({ title, reason, requiredData, variant, className = '' }: BlockedStateProps) {
  if (variant === 'minimal') {
    return (
      <div className={`flex items-center gap-2 text-red-400 ${className}`}>
        <Ban size={16} />
        <span className="text-sm">{title}</span>
      </div>
    );
  }

  if (variant === 'inline') {
    return (
      <div className={`inline-flex items-center gap-2 px-3 py-1.5 bg-red-500/10 border border-red-500/20 rounded-lg ${className}`}>
        <Ban size={14} className="text-red-400" />
        <span className="text-sm text-red-300">{title}</span>
      </div>
    );
  }

  if (variant === 'banner') {
    return (
      <div className={`p-4 bg-red-500/10 border border-red-500/20 rounded-xl ${className}`}>
        <div className="flex items-start gap-3">
          <div className="p-2 bg-red-500/20 rounded-lg">
            <Ban size={20} className="text-red-400" />
          </div>
          <div className="flex-1">
            <h4 className="font-medium text-red-300">{title}</h4>
            {reason && <p className="text-sm text-red-400/80 mt-1">{reason}</p>}
            {requiredData && requiredData.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1">
                <span className="text-xs text-slate-500">Required data:</span>
                {requiredData.map((data) => (
                  <span key={data} className="text-xs px-2 py-0.5 bg-slate-700 text-slate-300 rounded">
                    {data}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Default: card variant
  return (
    <div className={`bg-slate-800/50 border border-red-500/20 rounded-xl p-6 ${className}`}>
      <div className="text-center">
        <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-red-500/10 flex items-center justify-center">
          <Ban size={28} className="text-red-400" />
        </div>
        <h3 className="font-semibold text-red-300 mb-2">{title}</h3>
        {reason && <p className="text-sm text-slate-400 mb-4">{reason}</p>}
        {requiredData && requiredData.length > 0 && (
          <div className="p-3 bg-slate-900/50 rounded-lg">
            <p className="text-xs text-slate-500 mb-2">Required to enable:</p>
            <div className="flex flex-wrap gap-1 justify-center">
              {requiredData.map((data) => (
                <span key={data} className="text-xs px-2 py-1 bg-slate-700 text-slate-300 rounded">
                  {data}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MODULE BLOCKED STATE
// ═══════════════════════════════════════════════════════════════════════════════

function ModuleBlocked({ module, variant, className }: { module: string; variant: 'card' | 'inline' | 'banner' | 'minimal'; className?: string }) {
  return (
    <BlockedState
      title={`Module "${module}" Unavailable`}
      reason="This module is not available in your current configuration."
      variant={variant}
      className={className}
    />
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// FEATURE BLOCKED STATE
// ═══════════════════════════════════════════════════════════════════════════════

function FeatureBlocked({ feature, variant, className }: { feature: string; variant: 'card' | 'inline' | 'banner' | 'minimal'; className?: string }) {
  return (
    <BlockedState
      title={`Feature "${feature}" Disabled`}
      reason="This feature is not enabled for your tenant."
      variant={variant}
      className={className}
    />
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// METRIC BLOCKED STATE
// ═══════════════════════════════════════════════════════════════════════════════

function MetricBlocked({ 
  metric, 
  showReason, 
  variant,
  className 
}: { 
  metric: string; 
  showReason: boolean;
  variant: 'card' | 'inline' | 'banner' | 'minimal';
  className?: string;
}) {
  const blockedInfo = BLOCKED_METRICS[metric as keyof typeof BLOCKED_METRICS];
  
  return (
    <BlockedState
      title={`Metric "${metric}" Blocked`}
      reason={showReason ? blockedInfo?.reason : undefined}
      requiredData={showReason ? [...(blockedInfo?.required_data ?? [])] : undefined}
      variant={variant}
      className={className}
    />
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// LOW TRUST STATE
// ═══════════════════════════════════════════════════════════════════════════════

function LowTrustBlocked({ 
  currentTrust, 
  requiredTrust, 
  variant,
  className 
}: { 
  currentTrust: number; 
  requiredTrust: number;
  variant: 'card' | 'inline' | 'banner' | 'minimal';
  className?: string;
}) {
  if (variant === 'minimal') {
    return (
      <div className={`flex items-center gap-2 text-amber-400 ${className}`}>
        <AlertTriangle size={16} />
        <span className="text-sm">Trust too low ({currentTrust}% &lt; {requiredTrust}%)</span>
      </div>
    );
  }

  return (
    <div className={`p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl ${className}`}>
      <div className="flex items-start gap-3">
        <div className="p-2 bg-amber-500/20 rounded-lg">
          <AlertTriangle size={20} className="text-amber-400" />
        </div>
        <div>
          <h4 className="font-medium text-amber-300">Insufficient Trust Index</h4>
          <p className="text-sm text-amber-400/80 mt-1">
            Current trust: {currentTrust}% | Required: {requiredTrust}%
          </p>
          <p className="text-xs text-slate-400 mt-2">
            This feature requires higher data quality to function safely.
          </p>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function CapabilityGate({
  children,
  module,
  feature,
  metric,
  minTrust,
  fallback,
  showBlockedReason = false,
  variant = 'card',
  className = '',
}: CapabilityGateProps) {
  const { 
    hasModule, 
    hasFeature, 
    isMetricBlocked, 
    capabilities 
  } = useCapabilities();

  // Check module gate
  if (module && !hasModule(module)) {
    if (fallback) return <>{fallback}</>;
    return <ModuleBlocked module={module} variant={variant} className={className} />;
  }

  // Check feature gate
  if (feature && !hasFeature(feature)) {
    if (fallback) return <>{fallback}</>;
    return <FeatureBlocked feature={feature} variant={variant} className={className} />;
  }

  // Check metric gate
  if (metric && isMetricBlocked(metric)) {
    if (fallback) return <>{fallback}</>;
    return <MetricBlocked metric={metric} showReason={showBlockedReason} variant={variant} className={className} />;
  }

  // Check trust gate
  if (minTrust !== undefined && capabilities?.trust_index) {
    const avgTrust = Object.values(capabilities.trust_index).reduce((a, b) => a + b, 0) / 
                     Object.values(capabilities.trust_index).length;
    if (avgTrust < minTrust) {
      if (fallback) return <>{fallback}</>;
      return <LowTrustBlocked currentTrust={avgTrust} requiredTrust={minTrust} variant={variant} className={className} />;
    }
  }

  // All gates passed - render children
  return <>{children}</>;
}

// ═══════════════════════════════════════════════════════════════════════════════
// CONVENIENCE COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

export function MetricGate({ 
  metricId, 
  children, 
  fallback,
  showBlockedReason = true,
  variant = 'inline',
}: { 
  metricId: string; 
  children: ReactNode;
  fallback?: ReactNode;
  showBlockedReason?: boolean;
  variant?: 'card' | 'inline' | 'banner' | 'minimal';
}) {
  return (
    <CapabilityGate 
      metric={metricId} 
      fallback={fallback}
      showBlockedReason={showBlockedReason}
      variant={variant}
    >
      {children}
    </CapabilityGate>
  );
}

export function ModuleGate({ 
  moduleId, 
  children,
  fallback,
}: { 
  moduleId: string; 
  children: ReactNode;
  fallback?: ReactNode;
}) {
  return (
    <CapabilityGate module={moduleId} fallback={fallback}>
      {children}
    </CapabilityGate>
  );
}

export function FeatureGate({ 
  featureId, 
  children,
  fallback,
}: { 
  featureId: string; 
  children: ReactNode;
  fallback?: ReactNode;
}) {
  return (
    <CapabilityGate feature={featureId} fallback={fallback}>
      {children}
    </CapabilityGate>
  );
}

export default CapabilityGate;

