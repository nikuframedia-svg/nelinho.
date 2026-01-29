/**
 * FocusModeModal
 * 
 * Fullscreen modal for detailed metric analysis.
 * Shows metric value, trust, sparkline, and actions.
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X,
  Maximize2,
  Lightbulb,
  Play,
  Shield,
  Clock,
  ExternalLink,
} from 'lucide-react';
import { Sparkline } from '../charts/SparkLine';
import { TrendIndicator } from '../charts/TrendIndicator';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface FocusModeMetric {
  id: string;
  label: string;
  value: number | null;
  unit?: string;
  trustIndex: number;
  coverage?: number;
  semanticLabel?: string;
  trend?: number; // Percentage change
  trendInverted?: boolean; // If true, decrease is good
  sparklineData?: number[];
  computedAt?: string;
  isBlocked?: boolean;
  blockedReason?: string;
}

interface FocusModeModalProps {
  isOpen: boolean;
  onClose: () => void;
  metric: FocusModeMetric | null;
  onExplain?: (metricId: string) => void;
  onSimulate?: (metricId: string) => void;
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function FocusModeModal({
  isOpen,
  onClose,
  metric,
  onExplain,
  onSimulate,
}: FocusModeModalProps) {
  const navigate = useNavigate();

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen || !metric) return null;

  const getTrustColor = (index: number) => {
    if (index >= 80) return 'text-emerald-400';
    if (index >= 50) return 'text-amber-400';
    return 'text-red-400';
  };

  const getTrustBg = (index: number) => {
    if (index >= 80) return 'bg-emerald-400/20';
    if (index >= 50) return 'bg-amber-400/20';
    return 'bg-red-400/20';
  };

  const getSparklineColor = (): 'success' | 'warning' | 'danger' | 'accent' => {
    if (metric.trend === undefined) return 'accent';
    const isGood = metric.trendInverted ? metric.trend < 0 : metric.trend > 0;
    return isGood ? 'success' : metric.trend === 0 ? 'neutral' as any : 'danger';
  };

  return (
    <div className="fixed inset-0 z-[250] flex items-center justify-center">
      {/* Backdrop with blur */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-md"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-4xl mx-4 bg-bg-card border border-border-subtle rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 fade-in duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle bg-gradient-to-r from-accent/5 to-transparent">
          <div className="flex items-center gap-3">
            <Maximize2 size={20} className="text-accent" />
            <span className="text-lg font-semibold text-text-white">Modo Foco</span>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-bg-secondary rounded-lg transition-colors"
          >
            <X size={20} className="text-text-tertiary" />
          </button>
        </div>

        {/* Content */}
        <div className="p-8">
          {metric.isBlocked ? (
            /* Blocked State */
            <div className="text-center py-8">
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-red-400/20 flex items-center justify-center">
                <Shield size={40} className="text-red-400" />
              </div>
              <h2 className="text-3xl font-bold text-red-400 mb-2">{metric.label}</h2>
              <p className="text-lg text-text-tertiary mb-4">BLOQUEADO</p>
              <p className="text-text-secondary max-w-md mx-auto">{metric.blockedReason}</p>
              <button
                onClick={() => {
                  onClose();
                  navigate(`/explain?metricId=${metric.id}`);
                }}
                className="mt-6 px-6 py-2 bg-red-400/20 text-red-400 rounded-lg hover:bg-red-400/30 transition-colors"
              >
                Como desbloquear →
              </button>
            </div>
          ) : (
            /* Normal State */
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Left: Main Value */}
              <div className="text-center lg:text-left">
                <p className="text-sm font-medium text-text-tertiary uppercase tracking-wider mb-2">
                  {metric.semanticLabel || metric.label}
                </p>
                <div className="flex items-baseline justify-center lg:justify-start gap-3 mb-4">
                  <span className="text-6xl font-bold text-text-white">
                    {metric.value !== null 
                      ? metric.value.toLocaleString('pt-PT', { maximumFractionDigits: 1 })
                      : '—'
                    }
                  </span>
                  {metric.unit && metric.value !== null && (
                    <span className="text-2xl text-text-tertiary">{metric.unit}</span>
                  )}
                </div>

                {/* Trend */}
                {metric.trend !== undefined && (
                  <div className="mb-6">
                    <TrendIndicator
                      value={metric.trend}
                      inverted={metric.trendInverted}
                      variant="badge"
                      size="lg"
                    />
                    <span className="ml-2 text-sm text-text-tertiary">vs período anterior</span>
                  </div>
                )}

                {/* Sparkline */}
                {metric.sparklineData && metric.sparklineData.length > 0 && (
                  <div className="bg-bg-secondary/50 rounded-xl p-4">
                    <p className="text-xs text-text-tertiary mb-2">Evolução (últimos 7 dias)</p>
                    <Sparkline
                      data={metric.sparklineData}
                      width={280}
                      height={80}
                      color={getSparklineColor()}
                      fill
                    />
                  </div>
                )}
              </div>

              {/* Right: Trust & Actions */}
              <div className="space-y-6">
                {/* Trust Card */}
                <div className={`p-6 rounded-xl ${getTrustBg(metric.trustIndex)}`}>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Shield size={20} className={getTrustColor(metric.trustIndex)} />
                      <span className="font-medium text-text-white">Trust Index</span>
                    </div>
                    <span className={`text-3xl font-bold ${getTrustColor(metric.trustIndex)}`}>
                      {metric.trustIndex}%
                    </span>
                  </div>
                  
                  {/* Trust Bar */}
                  <div className="h-2 bg-bg-base rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        metric.trustIndex >= 80 ? 'bg-emerald-400' :
                        metric.trustIndex >= 50 ? 'bg-amber-400' :
                        'bg-red-400'
                      }`}
                      style={{ width: `${metric.trustIndex}%` }}
                    />
                  </div>

                  {metric.coverage !== undefined && (
                    <p className="text-sm text-text-tertiary mt-3">
                      Cobertura de dados: {metric.coverage.toFixed(1)}%
                    </p>
                  )}
                </div>

                {/* Computed At */}
                {metric.computedAt && (
                  <div className="flex items-center gap-2 text-text-tertiary">
                    <Clock size={16} />
                    <span className="text-sm">
                      Calculado: {new Date(metric.computedAt).toLocaleString('pt-PT')}
                    </span>
                  </div>
                )}

                {/* Actions */}
                <div className="flex flex-col gap-3">
                  <button
                    onClick={() => {
                      onClose();
                      if (onExplain) onExplain(metric.id);
                    }}
                    className="flex items-center justify-center gap-2 px-6 py-3 bg-accent/20 text-accent rounded-xl hover:bg-accent/30 transition-colors"
                  >
                    <Lightbulb size={18} />
                    Explicar esta métrica
                  </button>
                  
                  {onSimulate && metric.trustIndex >= 50 && (
                    <button
                      onClick={() => {
                        onClose();
                        onSimulate(metric.id);
                      }}
                      className="flex items-center justify-center gap-2 px-6 py-3 bg-blue-500/20 text-blue-400 rounded-xl hover:bg-blue-500/30 transition-colors"
                    >
                      <Play size={18} />
                      Simular cenário
                    </button>
                  )}

                  <button
                    onClick={() => {
                      onClose();
                      navigate(`/explain?metricId=${metric.id}`);
                    }}
                    className="flex items-center justify-center gap-2 px-6 py-3 bg-bg-secondary text-text-secondary rounded-xl hover:bg-bg-tertiary transition-colors"
                  >
                    <ExternalLink size={18} />
                    Abrir página completa
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-border-subtle bg-bg-secondary/50">
          <span className="text-xs text-text-tertiary">
            Prima <kbd className="px-1.5 py-0.5 bg-bg-card rounded border border-border-subtle">Esc</kbd> para fechar
          </span>
          <span className="text-xs text-text-tertiary">
            ID: {metric.id}
          </span>
        </div>
      </div>
    </div>
  );
}

export default FocusModeModal;

