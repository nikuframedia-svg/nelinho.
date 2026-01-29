/**
 * Trust Gate Component
 * ====================
 * 
 * Blocks actions when trust index is below threshold.
 * Shows warning for low trust, blocks for very low trust.
 * 
 * Trust Thresholds:
 * - >= 70: OK (green) - Automation allowed
 * - >= 50: WARNING (amber) - Manual action allowed with confirmation
 * - >= 40: DEGRADED (orange) - Display only, no actions
 * - < 40: BLOCKED (red) - Not shown
 * 
 * Source: src/explain/models/explained_value.py TrustInfo
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { Shield, AlertTriangle, Ban, CheckCircle, Lock } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface TrustGateProps {
  children: ReactNode;
  // Current trust index (0-100)
  trustIndex: number;
  // Minimum trust required to show content
  minTrust?: number;
  // Minimum trust required for actions
  minTrustForAction?: number;
  // What happens when action is blocked
  onBlockedAction?: () => void;
  // Custom blocked message
  blockedMessage?: string;
  // Show trust badge with content
  showTrustBadge?: boolean;
  // Variant
  variant?: 'default' | 'action' | 'inline';
  // Additional class names
  className?: string;
}

interface TrustBadgeProps {
  trustIndex: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

interface TrustStatus {
  status: 'OK' | 'WARNING' | 'DEGRADED' | 'BLOCKED';
  color: string;
  bgColor: string;
  icon: ReactNode;
  label: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

function getTrustStatus(trustIndex: number): TrustStatus {
  if (trustIndex >= 70) {
    return {
      status: 'OK',
      color: 'text-emerald-400',
      bgColor: 'bg-emerald-500/20',
      icon: <CheckCircle size={14} />,
      label: 'High Trust',
    };
  }
  if (trustIndex >= 50) {
    return {
      status: 'WARNING',
      color: 'text-amber-400',
      bgColor: 'bg-amber-500/20',
      icon: <AlertTriangle size={14} />,
      label: 'Medium Trust',
    };
  }
  if (trustIndex >= 40) {
    return {
      status: 'DEGRADED',
      color: 'text-orange-400',
      bgColor: 'bg-orange-500/20',
      icon: <AlertTriangle size={14} />,
      label: 'Low Trust',
    };
  }
  return {
    status: 'BLOCKED',
    color: 'text-red-400',
    bgColor: 'bg-red-500/20',
    icon: <Ban size={14} />,
    label: 'Blocked',
  };
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRUST BADGE COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function TrustBadge({ trustIndex, size = 'md', showLabel = true, className = '' }: TrustBadgeProps) {
  const status = getTrustStatus(trustIndex);
  
  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-[10px] gap-1',
    md: 'px-2 py-1 text-xs gap-1.5',
    lg: 'px-3 py-1.5 text-sm gap-2',
  };
  
  const iconSizes = {
    sm: 10,
    md: 12,
    lg: 14,
  };

  return (
    <div className={`inline-flex items-center rounded ${status.bgColor} ${status.color} ${sizeClasses[size]} ${className}`}>
      <Shield size={iconSizes[size]} />
      <span className="font-medium">{trustIndex}%</span>
      {showLabel && size !== 'sm' && (
        <span className="opacity-70">({status.label})</span>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCKED STATE
// ═══════════════════════════════════════════════════════════════════════════════

function TrustBlockedState({ 
  trustIndex, 
  minTrust, 
  message,
  className,
}: { 
  trustIndex: number; 
  minTrust: number;
  message?: string;
  className?: string;
}) {
  return (
    <div className={`p-6 bg-red-500/10 border border-red-500/20 rounded-xl ${className}`}>
      <div className="text-center">
        <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-red-500/20 flex items-center justify-center">
          <Lock size={28} className="text-red-400" />
        </div>
        <h3 className="font-semibold text-red-300 mb-2">Content Blocked</h3>
        <p className="text-sm text-slate-400 mb-4">
          {message || `Trust index is too low to display this content.`}
        </p>
        <div className="flex items-center justify-center gap-4">
          <div className="text-center">
            <p className="text-xs text-slate-500 mb-1">Current Trust</p>
            <TrustBadge trustIndex={trustIndex} size="md" showLabel={false} />
          </div>
          <div className="text-center">
            <p className="text-xs text-slate-500 mb-1">Required</p>
            <span className="text-sm text-slate-300 font-medium">{minTrust}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// WARNING STATE (for actions)
// ═══════════════════════════════════════════════════════════════════════════════

function TrustWarningGate({
  children,
  trustIndex,
}: {
  children: ReactNode;
  trustIndex: number;
}) {
  const [confirmed, setConfirmed] = useState(false);
  
  if (confirmed) {
    return <>{children}</>;
  }

  return (
    <div className="relative">
      <div className="opacity-50 pointer-events-none">
        {children}
      </div>
      <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80 rounded-lg">
        <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg max-w-sm text-center">
          <AlertTriangle size={32} className="mx-auto mb-3 text-amber-400" />
          <h4 className="font-medium text-amber-300 mb-2">Low Trust Warning</h4>
          <p className="text-sm text-slate-400 mb-4">
            The data has a trust index of {trustIndex}%. Actions may have uncertain outcomes.
          </p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => setConfirmed(true)}
              className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded text-sm font-medium transition-colors"
            >
              Proceed Anyway
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function TrustGate({
  children,
  trustIndex,
  minTrust = 40,
  minTrustForAction = 50,
  blockedMessage,
  showTrustBadge = true,
  variant = 'default',
  className = '',
}: TrustGateProps) {
  const status = getTrustStatus(trustIndex);

  // Fully blocked - don't show content
  if (trustIndex < minTrust) {
    return (
      <TrustBlockedState 
        trustIndex={trustIndex} 
        minTrust={minTrust}
        message={blockedMessage}
        className={className}
      />
    );
  }

  // Action variant - show warning for low trust
  if (variant === 'action' && trustIndex < minTrustForAction) {
    return (
      <TrustWarningGate trustIndex={trustIndex}>
        {children}
      </TrustWarningGate>
    );
  }

  // Inline variant - just show badge
  if (variant === 'inline') {
    return (
      <div className={`inline-flex items-center gap-2 ${className}`}>
        {children}
        {showTrustBadge && <TrustBadge trustIndex={trustIndex} size="sm" showLabel={false} />}
      </div>
    );
  }

  // Default variant - show content with optional badge
  return (
    <div className={className}>
      {showTrustBadge && (
        <div className="mb-3 flex items-center gap-2">
          <TrustBadge trustIndex={trustIndex} size="md" />
          {status.status === 'WARNING' && (
            <span className="text-xs text-amber-400/70">Results may be less reliable</span>
          )}
          {status.status === 'DEGRADED' && (
            <span className="text-xs text-orange-400/70">Actions disabled due to low trust</span>
          )}
        </div>
      )}
      {children}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRUST INDICATOR (simple visual)
// ═══════════════════════════════════════════════════════════════════════════════

export function TrustIndicator({ 
  trustIndex, 
  label,
  className = '',
}: { 
  trustIndex: number;
  label?: string;
  className?: string;
}) {
  const status = getTrustStatus(trustIndex);
  
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="flex items-center gap-1.5">
        <div className={`w-2 h-2 rounded-full ${status.bgColor.replace('/20', '')}`} />
        <span className={`text-sm font-medium ${status.color}`}>{trustIndex}%</span>
      </div>
      {label && <span className="text-xs text-slate-500">{label}</span>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRUST BAR (visual progress)
// ═══════════════════════════════════════════════════════════════════════════════

export function TrustBar({ 
  trustIndex,
  showThresholds = true,
  className = '',
}: { 
  trustIndex: number;
  showThresholds?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="relative h-2 bg-slate-700 rounded-full overflow-hidden">
        <div 
          className={`absolute left-0 top-0 h-full rounded-full transition-all ${
            trustIndex >= 70 ? 'bg-emerald-500' :
            trustIndex >= 50 ? 'bg-amber-500' :
            trustIndex >= 40 ? 'bg-orange-500' :
            'bg-red-500'
          }`}
          style={{ width: `${trustIndex}%` }}
        />
        {showThresholds && (
          <>
            <div className="absolute top-0 bottom-0 w-px bg-slate-500" style={{ left: '40%' }} />
            <div className="absolute top-0 bottom-0 w-px bg-slate-500" style={{ left: '50%' }} />
            <div className="absolute top-0 bottom-0 w-px bg-slate-500" style={{ left: '70%' }} />
          </>
        )}
      </div>
      {showThresholds && (
        <div className="flex justify-between text-[10px] text-slate-600 mt-1">
          <span>0</span>
          <span>40</span>
          <span>50</span>
          <span>70</span>
          <span>100</span>
        </div>
      )}
    </div>
  );
}

export default TrustGate;

