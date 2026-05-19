// Decomposto de Dashboard.tsx (Q.60.AB).
import { Link, useNavigate } from 'react-router-dom';
import { Clock, AlertTriangle, Users, TrendingUp, AlertCircle, ArrowRight, Play, HelpCircle, ChevronRight } from 'lucide-react';
import { SimulateButton } from '../components/semantic';

// ═══════════════════════════════════════════════════════════════════════════════
// ALERT BANNER - Shows when critical exceptions exist
// ═══════════════════════════════════════════════════════════════════════════════

export function AlertBanner({ 
  criticalCount, 
  highCount 
}: { 
  criticalCount: number; 
  highCount: number;
}) {
  if (criticalCount === 0 && highCount === 0) return null;

  return (
    <div className="mb-6 p-4 bg-gradient-to-r from-danger/20 via-danger/10 to-transparent border border-danger/30 rounded-xl animate-pulse-subtle">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-danger/20 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-danger" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-danger">Atenção Requerida</h4>
            <p className="text-xs text-danger/80">
              {criticalCount > 0 && `${criticalCount} excepções críticas`}
              {criticalCount > 0 && highCount > 0 && ' • '}
              {highCount > 0 && `${highCount} excepções de alta prioridade`}
            </p>
          </div>
        </div>
        <Link 
          to="/ops-inbox"
          className="flex items-center gap-2 px-4 py-2 bg-danger/20 hover:bg-danger/30 text-danger rounded-lg text-sm font-medium transition-colors"
        >
          Ver Inbox <ArrowRight size={16} />
        </Link>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRUST BADGE
// ═══════════════════════════════════════════════════════════════════════════════

export function TrustBadge({ value, size = 'sm' }: { value: number; size?: 'sm' | 'md' }) {
  const getColor = (v: number) => {
    if (v >= 70) return 'bg-success/20 text-success border-success/30';
    if (v >= 50) return 'bg-amber/20 text-amber border-amber/30';
    return 'bg-danger/20 text-danger border-danger/30';
  };

  const sizeClasses = size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-xs px-2 py-1';

  return (
    <span className={`font-medium rounded border ${getColor(value)} ${sizeClasses}`}>
      {value.toFixed(0)}% confiança
    </span>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SEMANTIC VALUE CARD - Enhanced with Explain and Simulate
// ═══════════════════════════════════════════════════════════════════════════════

export function SemanticValueCard({ 
  title, 
  metricId,
  value, 
  unit,
  confidence,
  semanticLabel,
  icon: Icon,
  trend,
  isBlocked,
  blockedReason,
  onExplain,
  canSimulate = true,
}: {
  title: string;
  metricId: string;
  value: number | string | null;
  unit?: string;
  confidence: number;
  semanticLabel: string;
  icon: React.ElementType;
  trend?: { value: number; label: string };
  isBlocked?: boolean;
  blockedReason?: string;
  onExplain: (metricId: string) => void;
  canSimulate?: boolean;
}) {
  const navigate = useNavigate();

  if (isBlocked) {
    return (
      <div className="bg-slate-800/50 border border-danger/30 rounded-xl p-4 opacity-90">
        <div className="flex items-center gap-2 mb-2">
          <div className="p-2 rounded-lg bg-danger/10">
            <AlertCircle className="w-4 h-4 text-danger" />
          </div>
          <span className="text-sm text-slate-400">{title}</span>
        </div>
        <div className="text-lg font-semibold text-danger mb-1">BLOCKED</div>
        <p className="text-xs text-danger/80">{blockedReason}</p>
        <Link 
          to="/profit/oee" 
          className="inline-flex items-center gap-1 mt-2 text-xs text-danger hover:text-danger-light transition-colors"
        >
          Saber mais <ArrowRight size={12} />
        </Link>
      </div>
    );
  }

  const hasValue = value !== null && value !== undefined;
  const showLowTrustWarning = confidence < 50;

  return (
    <div className="group bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 hover:border-accent/30 hover:bg-slate-800/70 transition-all">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-accent/10">
            <Icon className="w-4 h-4 text-accent" />
          </div>
          <span className="text-sm text-slate-400">{title}</span>
        </div>
        <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => onExplain(metricId)}
            className="w-6 h-6 rounded-lg bg-accent/20 hover:bg-accent/30 flex items-center justify-center text-accent transition-colors"
            title="Explicar"
          >
            <HelpCircle size={12} />
          </button>
          {canSimulate && confidence >= 30 && (
            <button
              onClick={() => navigate(`/twin?metric=${metricId}`)}
              className={`w-6 h-6 rounded-lg flex items-center justify-center transition-colors ${
                confidence >= 50 
                  ? 'bg-purple/20 hover:bg-purple/30 text-purple' 
                  : 'bg-purple/10 text-purple/40 cursor-not-allowed'
              }`}
              title={confidence >= 50 ? 'Simular' : `Trust baixo (${confidence}%)`}
              disabled={confidence < 50}
            >
              <Play size={12} />
            </button>
          )}
          {showLowTrustWarning && hasValue && (
            <span title={`Trust baixo: ${confidence}%`}>
              <AlertTriangle size={14} className="text-amber" />
            </span>
          )}
        </div>
      </div>
      <div className="flex items-baseline gap-1 mb-2">
        <span className="text-2xl font-bold text-white group-hover:text-accent transition-colors">
          {hasValue ? (typeof value === 'number' ? value.toLocaleString('pt-PT') : value) : '—'}
        </span>
        {unit && hasValue && <span className="text-sm text-slate-400">{unit}</span>}
      </div>
      <div className="flex items-center gap-2">
        <TrustBadge value={confidence} />
        <span className="text-xs text-slate-500 italic">{semanticLabel}</span>
      </div>
      {trend && hasValue && (
        <div className={`flex items-center gap-1 mt-2 text-xs ${trend.value >= 0 ? 'text-success' : 'text-danger'}`}>
          <TrendingUp className={`w-3 h-3 ${trend.value < 0 ? 'rotate-180' : ''}`} />
          <span>{trend.value >= 0 ? '+' : ''}{trend.value}% {trend.label}</span>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ACTION CARD - "O Que Fazer Hoje" item
// ═══════════════════════════════════════════════════════════════════════════════

export interface ActionItem {
  id: string;
  type: 'bottleneck' | 'quality' | 'skills' | 'schedule';
  severity: 'critical' | 'high' | 'medium';
  title: string;
  description: string;
  impact: string;
  trustIndex: number;
  metricId: string;
  actionType: 'capacity_adjustment' | 'quality_improvement' | 'skills_training' | 'schedule_change';
}

export function ActionCard({ 
  action, 
  onExplain 
}: { 
  action: ActionItem; 
  onExplain: (metricId: string) => void;
}) {
  const severityColors = {
    critical: 'border-danger/40 bg-danger/5',
    high: 'border-amber/40 bg-amber/5',
    medium: 'border-blue/40 bg-blue/5',
  };

  const severityBadge = {
    critical: 'bg-danger/20 text-danger',
    high: 'bg-amber/20 text-amber',
    medium: 'bg-blue/20 text-blue',
  };

  const typeIcons = {
    bottleneck: AlertCircle,
    quality: AlertTriangle,
    skills: Users,
    schedule: Clock,
  };

  const Icon = typeIcons[action.type];

  return (
    <div className={`rounded-xl border p-4 ${severityColors[action.severity]} hover:scale-[1.01] transition-transform`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${severityBadge[action.severity]}`}>
            <Icon size={16} />
          </div>
          <div>
            <span className={`text-xs font-medium px-2 py-0.5 rounded ${severityBadge[action.severity]}`}>
              {action.severity.toUpperCase()}
            </span>
          </div>
        </div>
        <TrustBadge value={action.trustIndex} />
      </div>
      
      <h4 className="text-sm font-semibold text-white mb-1">{action.title}</h4>
      <p className="text-xs text-slate-400 mb-3">{action.description}</p>
      
      <div className="flex items-center justify-between">
        <span className="text-xs text-accent">Impacto: {action.impact}</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onExplain(action.metricId)}
            className="text-xs text-slate-400 hover:text-accent transition-colors flex items-center gap-1"
          >
            <HelpCircle size={12} /> Porquê?
          </button>
          <SimulateButton
            actionType={action.actionType}
            description={action.title}
            trustIndex={action.trustIndex}
            size="sm"
            variant="secondary"
          />
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// QUICK NAV CARD
// ═══════════════════════════════════════════════════════════════════════════════

export function QuickNavCard({ 
  title, 
  description, 
  icon: Icon, 
  to, 
  color 
}: { 
  title: string; 
  description: string; 
  icon: React.ElementType; 
  to: string; 
  color: string;
}) {
  return (
    <Link 
      to={to}
      className={`group flex items-center gap-4 p-4 rounded-xl border border-slate-700/50 hover:border-${color}/30 bg-slate-800/30 hover:bg-slate-800/50 transition-all`}
    >
      <div className={`w-10 h-10 rounded-xl bg-${color}/10 flex items-center justify-center group-hover:scale-110 transition-transform`}>
        <Icon className={`w-5 h-5 text-${color}`} />
      </div>
      <div className="flex-1">
        <h4 className="text-sm font-medium text-white group-hover:text-accent transition-colors">{title}</h4>
        <p className="text-xs text-slate-500">{description}</p>
      </div>
      <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-accent group-hover:translate-x-1 transition-all" />
    </Link>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN DASHBOARD COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

// Type for focus mode metric
export interface FocusMetric {
  id: string;
  label: string;
  value: number | null;
  unit?: string;
  trustIndex: number;
  coverage?: number;
  semanticLabel?: string;
  trend?: number;
  sparklineData?: number[];
}
