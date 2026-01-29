/**
 * SemanticMetricCard
 * ==================
 * 
 * A comprehensive metric card that displays:
 * - Value with unit
 * - Trust index with color coding
 * - Coverage percentage
 * - Semantic label (theoretical/observed/imputed)
 * - Explain button (opens ExplainDrawer)
 * - Simulate button (navigates to Twin sandbox)
 * - BLOCKED state with reason and required data
 * 
 * This is the standard component for displaying semantic metrics
 * across the entire application.
 */

import { type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  HelpCircle, 
  Play, 
  Lock, 
  Ban,
  AlertTriangle,
  Clock,
  TrendingUp,
  TrendingDown,
  Maximize2,
} from 'lucide-react';
import { formatCompactNumber } from '../../lib/utils';
import { Sparkline } from '../charts/SparkLine';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export interface SemanticMetricCardProps {
  metricId: string;
  label: string;
  value: number | null;
  unit?: string;
  trustIndex: number;
  coverage?: number;
  semanticLabel?: 'theoretical' | 'observed' | 'imputed' | string;
  computedAt?: string;
  onExplain: () => void;
  onSimulate?: () => void;
  onFocus?: () => void; // Opens Focus Mode Modal
  canSimulate?: boolean;
  isBlocked?: boolean;
  blockedReason?: string;
  requiredData?: string[];
  icon?: ReactNode;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'highlighted' | 'muted';
  trend?: {
    direction: 'up' | 'down' | 'neutral';
    value: number;
    label?: string;
  };
  // Sparkline data for mini trend chart
  sparklineData?: number[];
  sparklineColor?: 'accent' | 'success' | 'warning' | 'danger' | 'neutral';
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRUST BADGE COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function TrustBadge({ 
  index, 
  coverage, 
  size = 'md' 
}: { 
  index: number; 
  coverage?: number; 
  size?: 'sm' | 'md' | 'lg';
}) {
  const getColor = (value: number) => {
    if (value >= 70) return 'bg-success/20 text-success border-success/30';
    if (value >= 50) return 'bg-amber/20 text-amber border-amber/30';
    return 'bg-danger/20 text-danger border-danger/30';
  };

  const sizeClasses = {
    sm: 'text-xs px-1.5 py-0.5',
    md: 'text-xs px-2 py-1',
    lg: 'text-sm px-2.5 py-1',
  };

  return (
    <div className="flex items-center gap-1.5">
      <span className={`font-medium rounded border ${getColor(index)} ${sizeClasses[size]}`}>
        {index}% confiança
      </span>
      {coverage !== undefined && (
        <span className="text-xs text-text-tertiary">
          ({coverage.toFixed(0)}% cobertura)
        </span>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SEMANTIC LABEL COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function SemanticLabel({ label }: { label: string }) {
  const getStyle = (l: string) => {
    switch (l.toLowerCase()) {
      case 'theoretical':
        return 'bg-blue/10 text-blue border-blue/20';
      case 'observed':
        return 'bg-success/10 text-success border-success/20';
      case 'imputed':
        return 'bg-purple/10 text-purple border-purple/20';
      default:
        return 'bg-bg-elevated text-text-secondary border-border-subtle';
    }
  };

  const getLabel = (l: string) => {
    switch (l.toLowerCase()) {
      case 'theoretical':
        return 'Teórico';
      case 'observed':
        return 'Observado';
      case 'imputed':
        return 'Imputado';
      default:
        return l;
    }
  };

  return (
    <span className={`text-xs px-2 py-0.5 rounded border ${getStyle(label)}`}>
      {getLabel(label)}
    </span>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCKED STATE COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function BlockedState({ 
  label,
  reason, 
  requiredData,
}: { 
  label: string;
  reason: string; 
  requiredData?: string[];
}) {
  return (
    <div className="alpha-card p-5 bg-danger/5 border-danger/20 opacity-90">
      <div className="flex items-center justify-between mb-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-danger/20">
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
        <p className="text-xs text-danger/80 leading-relaxed">{reason}</p>
        {requiredData && requiredData.length > 0 && (
          <div className="mt-2">
            <p className="text-xs text-text-tertiary mb-1">Dados necessários:</p>
            <div className="flex flex-wrap gap-1">
              {requiredData.map((data) => (
                <span key={data} className="text-xs px-2 py-0.5 rounded bg-danger/10 text-danger/80">
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
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function SemanticMetricCard({
  metricId,
  label,
  value,
  unit = '',
  trustIndex,
  coverage,
  semanticLabel,
  computedAt,
  onExplain,
  onSimulate,
  onFocus,
  canSimulate = true,
  isBlocked = false,
  blockedReason,
  requiredData,
  icon,
  size = 'md',
  variant = 'default',
  trend,
  sparklineData,
  sparklineColor,
}: SemanticMetricCardProps) {
  const navigate = useNavigate();

  // If blocked, show blocked state
  if (isBlocked && blockedReason) {
    return (
      <BlockedState 
        label={label}
        reason={blockedReason} 
        requiredData={requiredData}
      />
    );
  }

  const hasValue = value !== null && value !== undefined;
  const displayValue = hasValue 
    ? (typeof value === 'number' && Math.abs(value) >= 1000 
        ? formatCompactNumber(value) 
        : value.toLocaleString('pt-PT', { maximumFractionDigits: 1 }))
    : '—';

  const sizeClasses = {
    sm: 'p-4',
    md: 'p-5',
    lg: 'p-6',
  };

  const valueSizeClasses = {
    sm: 'text-xl',
    md: 'text-2xl',
    lg: 'text-3xl',
  };

  const variantClasses = {
    default: '',
    highlighted: 'ring-2 ring-accent/30 bg-accent/5',
    muted: 'opacity-75',
  };

  const handleSimulate = () => {
    if (onSimulate) {
      onSimulate();
    } else {
      navigate(`/twin?metric=${metricId}`);
    }
  };

  const showLowTrustWarning = trustIndex < 50;
  const canPerformSimulation = canSimulate && trustIndex >= 30;

  return (
    <div 
      className={`alpha-card group relative hover:bg-bg-elevated transition-all ${sizeClasses[size]} ${variantClasses[variant]}`}
    >
      {/* Header with icon and actions */}
      <div className="flex items-center justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
          hasValue ? 'bg-accent/20' : 'bg-bg-elevated'
        }`}>
          {icon || <TrendingUp size={20} className={hasValue ? 'text-accent' : 'text-text-tertiary'} />}
        </div>
        
        <div className="flex items-center gap-2">
          {/* Focus Mode button */}
          {onFocus && hasValue && (
            <button
              onClick={onFocus}
              className="w-7 h-7 rounded-lg bg-bg-elevated hover:bg-bg-secondary flex items-center justify-center text-text-tertiary hover:text-text-white transition-colors opacity-0 group-hover:opacity-100"
              title="Expandir para Focus Mode"
            >
              <Maximize2 size={14} />
            </button>
          )}
          
          {/* Explain button */}
          <button
            onClick={onExplain}
            className="w-7 h-7 rounded-lg bg-accent/20 hover:bg-accent/30 flex items-center justify-center text-accent transition-colors opacity-0 group-hover:opacity-100"
            title="Explicar esta métrica"
          >
            <HelpCircle size={14} />
          </button>
          
          {/* Simulate button */}
          {canPerformSimulation && (
            <button
              onClick={handleSimulate}
              className="w-7 h-7 rounded-lg bg-purple/20 hover:bg-purple/30 flex items-center justify-center text-purple transition-colors opacity-0 group-hover:opacity-100"
              title="Simular alteração"
            >
              <Play size={14} />
            </button>
          )}
          
          {/* Low trust warning */}
          {showLowTrustWarning && hasValue && (
            <div className="group/tooltip relative">
              <AlertTriangle size={16} className="text-amber" />
              <div className="absolute bottom-full right-0 mb-2 px-3 py-2 bg-bg-elevated text-text-primary text-xs rounded-lg opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all z-50 w-64 shadow-xl border border-border-subtle">
                Trust baixo ({trustIndex}%): resultados podem não ser fiáveis
              </div>
            </div>
          )}
        </div>
      </div>
      
      {/* Label */}
      <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider mb-1">{label}</p>
      
      {/* Value + Sparkline Row */}
      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="flex items-baseline gap-2">
            <span className={`font-bold ${valueSizeClasses[size]} ${
              hasValue ? 'text-text-white group-hover:text-accent transition-colors' : 'text-text-tertiary'
            }`}>
              {displayValue}
            </span>
            {hasValue && unit && (
              <span className="text-sm font-medium text-text-tertiary">{unit}</span>
            )}
          </div>
          {trend && hasValue && (
            <span className={`flex items-center gap-0.5 text-xs font-medium mt-1 ${
              trend.direction === 'up' ? 'text-success' : 
              trend.direction === 'down' ? 'text-danger' : 'text-text-tertiary'
            }`}>
              {trend.direction === 'up' ? <TrendingUp size={12} /> : 
               trend.direction === 'down' ? <TrendingDown size={12} /> : null}
              {trend.value > 0 ? '+' : ''}{trend.value}%
              {trend.label && <span className="text-text-tertiary ml-1">({trend.label})</span>}
            </span>
          )}
        </div>
        
        {/* Sparkline */}
        {sparklineData && sparklineData.length >= 2 && hasValue && (
          <div className="flex-shrink-0">
            <Sparkline 
              data={sparklineData}
              width={80}
              height={32}
              color={sparklineColor || (
                trustIndex >= 70 ? 'accent' : 
                trustIndex >= 50 ? 'warning' : 'danger'
              )}
              fill={true}
              animated={true}
            />
          </div>
        )}
      </div>
      
      {/* Footer with trust, semantic label, and timestamp */}
      <div className="mt-3 pt-3 border-t border-border-subtle space-y-2">
        <div className="flex items-center justify-between">
          <TrustBadge index={trustIndex} coverage={coverage} size="sm" />
          {semanticLabel && <SemanticLabel label={semanticLabel} />}
        </div>
        
        {computedAt && (
          <div className="flex items-center gap-1 text-xs text-text-tertiary">
            <Clock size={12} />
            <span>Calculado: {new Date(computedAt).toLocaleString('pt-PT')}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default SemanticMetricCard;

