import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Info, TrendingUp, TrendingDown, X, Loader2, ArrowUpRight } from 'lucide-react';
import { cn } from '../lib/utils';

interface KPIFactor {
  name: string;
  weight: string;
  count: number;
}

interface KPISuggestion {
  title: string;
  description: string;
  estimatedImpact?: Record<string, string>;
}

interface KPIExplanation {
  reason: string;
  topFactors: KPIFactor[];
  suggestion?: KPISuggestion | null;
}

interface KPICardProps {
  label: string;
  value: string | number;
  target?: number;
  change?: { value: number; label: string };
  icon: React.ReactNode;
  iconBg?: string;
  glowColor?: 'teal' | 'blue' | 'green' | 'amber' | 'red';
  href?: string;
  explanation?: KPIExplanation;
  isLoading?: boolean;
  onExplain?: () => void;
  className?: string;
}

export function KPICard({
  label,
  value,
  target,
  change,
  icon,
  iconBg,
  glowColor = 'teal',
  href,
  explanation,
  isLoading = false,
  onExplain,
  className,
}: KPICardProps) {
  const [showExplanation, setShowExplanation] = useState(false);

  const isOnTrack = target !== undefined ? (typeof value === 'number' ? value >= target : parseFloat(String(value)) >= target) : undefined;

  // Map glow colors to Tailwind classes
  const glowClasses: Record<string, string> = {
    teal: 'hover:shadow-glow-teal hover:border-accent-500/40',
    blue: 'hover:shadow-glow-blue hover:border-blue-500/40',
    green: 'hover:shadow-glow-green hover:border-emerald-500/40',
    amber: 'hover:shadow-glow-amber hover:border-amber-500/40',
    red: 'hover:shadow-glow-red hover:border-red-500/40',
  };

  const iconGradients: Record<string, string> = {
    teal: 'from-accent-500/20 to-accent-600/20 border-accent-500/30 text-accent-400',
    blue: 'from-blue-500/20 to-blue-600/20 border-blue-500/30 text-blue-400',
    green: 'from-emerald-500/20 to-emerald-600/20 border-emerald-500/30 text-emerald-400',
    amber: 'from-amber-500/20 to-amber-600/20 border-amber-500/30 text-amber-400',
    red: 'from-red-500/20 to-red-600/20 border-red-500/30 text-red-400',
  };

  const progressGradients: Record<string, string> = {
    teal: 'from-accent-600 via-accent-500 to-accent-400',
    blue: 'from-blue-600 via-blue-500 to-blue-400',
    green: 'from-emerald-600 via-emerald-500 to-emerald-400',
    amber: 'from-amber-600 via-amber-500 to-amber-400',
    red: 'from-red-600 via-red-500 to-red-400',
  };

  const cardContent = (
    <div className={cn(
      "glass-card-strong p-5 transition-all duration-300 group",
      href && "cursor-pointer",
      glowClasses[glowColor],
      className
    )}>
      {/* Header Row */}
      <div className="flex items-start justify-between mb-4">
        <div className={cn(
          'w-12 h-12 rounded-xl bg-gradient-to-br border flex items-center justify-center',
          iconBg || iconGradients[glowColor]
        )}>
          {icon}
        </div>
        <div className="flex items-center gap-2">
          {explanation && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setShowExplanation(true);
                onExplain?.();
              }}
              className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-slate-500 hover:text-accent-400 transition-colors"
              title="Why?"
            >
              <Info size={16} />
            </button>
          )}
          {change && (
            <div className={cn(
              'flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 rounded-full',
              change.value >= 0 
                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' 
                : 'bg-red-500/15 text-red-400 border border-red-500/30'
            )}>
              {change.value >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {change.value >= 0 ? '+' : ''}{change.value}%
            </div>
          )}
        </div>
      </div>

      {/* Value & Label */}
      <div className="mb-3">
        <div className="metric-xl mb-1 tabular-nums">
          {isLoading ? (
            <div className="flex items-center gap-2">
              <Loader2 size={24} className="animate-spin text-slate-500" />
              <span className="text-slate-600">--</span>
            </div>
          ) : (
            <span className="text-slate-100">{value}</span>
          )}
        </div>
        <div className="text-sm text-slate-400 font-medium">{label}</div>
        {target !== undefined && (
          <div className="text-xs text-slate-500 mt-1">
            Target: {target}{typeof value === 'string' && value.includes('%') ? '%' : ''}
          </div>
        )}
      </div>

      {/* Status Badge */}
      {isOnTrack !== undefined && (
        <div className="mb-3">
          {isOnTrack ? (
            <span className="badge-dark badge-success">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              On Track
            </span>
          ) : (
            <span className="badge-dark badge-danger">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400"></span>
              Below Target
            </span>
          )}
        </div>
      )}

      {/* Inline Factors (when present) */}
      {explanation && explanation.topFactors.length > 0 && (
        <div className="mt-4 pt-4 border-t border-white/[0.06]">
          <p className="text-xs text-slate-500 mb-3 line-clamp-2">{explanation.reason}</p>
          <div className="space-y-2">
            {explanation.topFactors.slice(0, 3).map((factor, idx) => {
              const weightNum = parseFloat(factor.weight.replace('%', ''));
              return (
                <div key={idx} className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 w-20 truncate">{factor.name}</span>
                  <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                    <div
                      className={cn('h-full rounded-full bg-gradient-to-r', progressGradients[glowColor])}
                      style={{ width: `${Math.min(100, weightNum)}%` }}
                    />
                  </div>
                  <span className="text-xs font-semibold text-slate-300 w-10 text-right tabular-nums">{factor.weight}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Hover indicator for links */}
      {href && (
        <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
          <ArrowUpRight size={16} className="text-accent-400" />
        </div>
      )}
    </div>
  );

  // Explanation Modal - Dark Theme
  const explanationModal = showExplanation && explanation && (
    <div 
      className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fadeIn" 
      onClick={() => setShowExplanation(false)}
    >
      <div 
        className="glass-card-strong max-w-2xl w-full p-6 animate-scaleIn" 
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-slate-100">
            Why is <span className="gradient-text">{label}</span> {value}?
          </h3>
          <button
            onClick={() => setShowExplanation(false)}
            className="w-10 h-10 rounded-xl bg-white/5 hover:bg-white/10 flex items-center justify-center text-slate-500 hover:text-slate-300 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="space-y-6">
          <p className="text-slate-400 leading-relaxed">{explanation.reason}</p>

          {explanation.topFactors.length > 0 && (
            <div className="space-y-4">
              <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Top Contributing Factors</h4>
              <div className="space-y-4">
                {explanation.topFactors.map((factor, idx) => {
                  const weightNum = parseFloat(factor.weight.replace('%', ''));
                  return (
                    <div key={idx} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-300">{factor.name}</span>
                        <span className="text-sm font-bold text-accent-400">{factor.weight}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                          <div
                            className={cn('h-full rounded-full bg-gradient-to-r transition-all duration-500', progressGradients[glowColor])}
                            style={{ width: `${Math.min(100, weightNum)}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-500 min-w-max">({factor.count} occurrences)</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {explanation.suggestion && (
            <div className="p-5 rounded-xl bg-accent-500/10 border border-accent-500/30">
              <h4 className="font-semibold text-accent-400 mb-2 flex items-center gap-2">
                <span className="text-lg">💡</span>
                Suggested Action
              </h4>
              <p className="text-sm text-slate-300 mb-2 font-medium">{explanation.suggestion.title}</p>
              <p className="text-sm text-slate-400">{explanation.suggestion.description}</p>
              {explanation.suggestion.estimatedImpact && (
                <div className="mt-4 pt-4 border-t border-accent-500/20">
                  <p className="text-xs font-semibold text-accent-400 mb-3 uppercase tracking-wider">Estimated Impact</p>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(explanation.suggestion.estimatedImpact).map(([key, val]) => (
                      <div key={key} className="text-sm">
                        <span className="text-slate-500">{key}:</span>{' '}
                        <span className="font-semibold text-slate-200">{val}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {href ? <Link to={href} className="block">{cardContent}</Link> : cardContent}
      {explanationModal}
    </>
  );
}
