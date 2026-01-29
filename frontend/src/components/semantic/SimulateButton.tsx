/**
 * SimulateButton
 * ==============
 * 
 * Universal button for triggering simulations in the Twin sandbox.
 * 
 * Behavior:
 * - Trust >= 50: Active, navigates to /twin with query params
 * - Trust < 50: Disabled with tooltip "Trust muito baixo"
 * - Trust < 30: Hidden entirely
 */

import { useNavigate } from 'react-router-dom';
import { Play, AlertTriangle, Lock } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export interface SimulateButtonProps {
  actionType: 'capacity_adjustment' | 'quality_improvement' | 'skills_training' | 'schedule_change' | 'custom';
  params?: Record<string, unknown>;
  description: string;
  trustIndex: number;
  minTrustForSimulation?: number;
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  onSimulate?: () => void;
  disabled?: boolean;
  disabledReason?: string;
  className?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function SimulateButton({
  actionType,
  params = {},
  description,
  trustIndex,
  minTrustForSimulation = 50,
  variant = 'primary',
  size = 'md',
  onSimulate,
  disabled = false,
  disabledReason,
  className = '',
}: SimulateButtonProps) {
  const navigate = useNavigate();

  // Hide entirely if trust is too low
  if (trustIndex < 30) {
    return null;
  }

  const isLowTrust = trustIndex < minTrustForSimulation;
  const isDisabled = disabled || isLowTrust;

  const handleClick = () => {
    if (isDisabled) return;
    
    if (onSimulate) {
      onSimulate();
    } else {
      // Navigate to Twin sandbox with params
      const queryParams = new URLSearchParams({
        action: actionType,
        description: description,
        ...Object.fromEntries(
          Object.entries(params).map(([k, v]) => [k, String(v)])
        ),
      });
      navigate(`/twin?${queryParams.toString()}`);
    }
  };

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-xs gap-1.5',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-5 py-2.5 text-base gap-2',
  };

  const variantClasses = {
    primary: isDisabled 
      ? 'bg-purple/10 text-purple/50 cursor-not-allowed' 
      : 'bg-purple hover:bg-purple-light text-white shadow-lg shadow-purple/20',
    secondary: isDisabled
      ? 'bg-bg-elevated text-text-tertiary cursor-not-allowed border border-border-subtle'
      : 'bg-bg-elevated hover:bg-bg-secondary text-purple border border-purple/30 hover:border-purple/50',
    ghost: isDisabled
      ? 'text-text-tertiary cursor-not-allowed'
      : 'text-purple hover:bg-purple/10',
  };

  const iconSize = size === 'sm' ? 14 : size === 'md' ? 16 : 18;

  return (
    <div className="relative inline-flex group/simulate">
      <button
        onClick={handleClick}
        disabled={isDisabled}
        className={`
          inline-flex items-center justify-center font-medium rounded-lg transition-all
          ${sizeClasses[size]}
          ${variantClasses[variant]}
          ${className}
        `}
      >
        {isLowTrust ? (
          <Lock size={iconSize} />
        ) : (
          <Play size={iconSize} />
        )}
        <span>Simular</span>
        {isLowTrust && (
          <AlertTriangle size={iconSize - 2} className="text-amber" />
        )}
      </button>
      
      {/* Tooltip for disabled state */}
      {isDisabled && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-bg-elevated text-text-primary text-xs rounded-lg opacity-0 invisible group-hover/simulate:opacity-100 group-hover/simulate:visible transition-all z-50 w-48 shadow-xl border border-border-subtle text-center">
          {disabledReason || (isLowTrust 
            ? `Trust muito baixo (${trustIndex}%). Mínimo: ${minTrustForSimulation}%`
            : 'Simulação não disponível'
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// QUICK SIMULATE BUTTON - Simplified version for inline use
// ═══════════════════════════════════════════════════════════════════════════════

export function QuickSimulateButton({
  metricId,
  trustIndex,
  onSimulate,
}: {
  metricId: string;
  trustIndex: number;
  onSimulate?: () => void;
}) {
  const navigate = useNavigate();

  if (trustIndex < 30) return null;

  const isLowTrust = trustIndex < 50;

  const handleClick = () => {
    if (isLowTrust) return;
    if (onSimulate) {
      onSimulate();
    } else {
      navigate(`/twin?metric=${metricId}`);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={isLowTrust}
      className={`
        w-7 h-7 rounded-lg flex items-center justify-center transition-colors
        ${isLowTrust 
          ? 'bg-purple/10 text-purple/40 cursor-not-allowed' 
          : 'bg-purple/20 hover:bg-purple/30 text-purple'
        }
      `}
      title={isLowTrust ? `Trust baixo (${trustIndex}%)` : 'Simular alteração'}
    >
      {isLowTrust ? <Lock size={14} /> : <Play size={14} />}
    </button>
  );
}

export default SimulateButton;

