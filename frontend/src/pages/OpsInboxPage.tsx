/**
 * Operations Inbox Page
 * =====================
 * 
 * Central exception management page.
 * Displays actionable exceptions from semantic queries.
 * Each exception has: source data, explanation, recommended action, sandbox link.
 * 
 * Data Sources:
 * - /v1/factory/semantic/queries/bottlenecks
 * - /v1/factory/semantic/queries/quality
 * - /v1/factory/semantic/queries/skills-risk
 * - /v1/factory/semantic/queries/mold-conflicts
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Inbox,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  TrendingDown,
  Users,
  Wrench,
  Loader2,
  ArrowRight,
  Play,
  Shield,
  Info,
  Ban,
  RefreshCw,
} from 'lucide-react';
import { DarkPageLayout } from '../layouts';
import { DarkCard, DarkBadge, DarkButton } from '../components/dark';
import { factoryApi } from '../lib/factoryApi';
import { TrustBadge } from '../components/capabilities/TrustGate';

// PALANTIR-LEVEL COMPONENTS
import { ModuleErrorBoundary } from '../components/palantir';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface Exception {
  id: string;
  type: 'bottleneck' | 'quality' | 'skills_risk' | 'mold_conflict';
  title: string;
  description: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  trustIndex: number;
  dataSource: string;
  semanticLabel?: string;
  value?: number | string;
  unit?: string;
  recommendation?: string;
  sandboxAction?: {
    actionType: string;
    description: string;
    params?: Record<string, any>;
  };
  blockedReason?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// EXCEPTION CARD
// ═══════════════════════════════════════════════════════════════════════════════

function ExceptionCard({ exception }: { exception: Exception }) {
  const getSeverityStyle = () => {
    switch (exception.severity) {
      case 'critical':
        return { bg: 'bg-red-500/10', border: 'border-red-500/30', icon: 'text-red-400' };
      case 'high':
        return { bg: 'bg-orange-500/10', border: 'border-orange-500/30', icon: 'text-orange-400' };
      case 'medium':
        return { bg: 'bg-amber-500/10', border: 'border-amber-500/30', icon: 'text-amber-400' };
      default:
        return { bg: 'bg-blue-500/10', border: 'border-blue-500/30', icon: 'text-blue-400' };
    }
  };

  const getTypeIcon = () => {
    switch (exception.type) {
      case 'bottleneck':
        return <TrendingDown size={20} />;
      case 'quality':
        return <AlertCircle size={20} />;
      case 'skills_risk':
        return <Users size={20} />;
      case 'mold_conflict':
        return <Wrench size={20} />;
      default:
        return <AlertTriangle size={20} />;
    }
  };

  const style = getSeverityStyle();
  const isBlocked = !!exception.blockedReason;

  return (
    <div className={`${style.bg} ${style.border} border rounded-xl p-5 transition-all hover:border-opacity-50`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-start gap-3">
          <div className={`p-2 rounded-lg ${style.bg} ${style.icon}`}>
            {getTypeIcon()}
          </div>
          <div>
            <h3 className="font-semibold text-white">{exception.title}</h3>
            <p className="text-sm text-slate-400 mt-1">{exception.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <TrustBadge trustIndex={exception.trustIndex} size="sm" showLabel={false} />
          <DarkBadge variant={
            exception.severity === 'critical' ? 'danger' :
            exception.severity === 'high' ? 'warning' :
            exception.severity === 'medium' ? 'warning' :
            'neutral'
          }>
            {exception.severity.toUpperCase()}
          </DarkBadge>
        </div>
      </div>

      {/* Value Display */}
      {exception.value !== undefined && !isBlocked && (
        <div className="mb-4 p-3 bg-slate-800/50 rounded-lg">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">
              {typeof exception.value === 'number' 
                ? exception.value.toLocaleString() 
                : exception.value}
            </span>
            {exception.unit && (
              <span className="text-sm text-slate-400">{exception.unit}</span>
            )}
          </div>
          {exception.semanticLabel && (
            <p className="text-xs text-slate-500 italic mt-1">{exception.semanticLabel}</p>
          )}
        </div>
      )}

      {/* Blocked Notice */}
      {isBlocked && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
          <div className="flex items-start gap-2">
            <Ban size={16} className="text-red-400 mt-0.5" />
            <div>
              <p className="text-sm text-red-300 font-medium">Cannot Compute</p>
              <p className="text-xs text-red-400/80">{exception.blockedReason}</p>
            </div>
          </div>
        </div>
      )}

      {/* Data Source */}
      <div className="flex items-center gap-2 mb-4 text-xs text-slate-500">
        <Info size={12} />
        <span>Source: {exception.dataSource}</span>
      </div>

      {/* Recommendation */}
      {exception.recommendation && !isBlocked && (
        <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
          <p className="text-sm text-emerald-300">
            <strong className="font-medium">Recommendation:</strong> {exception.recommendation}
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3 pt-3 border-t border-slate-700/50">
        <Link
          to={`/explain/${exception.type}`}
          className="flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 transition-colors"
        >
          <Info size={14} />
          Explain
        </Link>
        {exception.sandboxAction && !isBlocked && (
          <Link
            to={`/twin?action=${exception.sandboxAction.actionType}`}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-500 text-white rounded text-sm font-medium transition-colors"
          >
            <Play size={14} />
            Simulate Fix
          </Link>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function OpsInboxPage() {
  // Fetch all exception sources
  const { data: bottlenecks, isLoading: loadingBottlenecks } = useQuery({
    queryKey: ['factory', 'semantic', 'bottlenecks'],
    queryFn: () => factoryApi.getBottlenecks(),
    staleTime: 60000,
  });

  const { data: quality, isLoading: loadingQuality } = useQuery({
    queryKey: ['factory', 'semantic', 'quality'],
    queryFn: () => factoryApi.getQuality(),
    staleTime: 60000,
  });

  const { data: skillsRisk, isLoading: loadingSkills } = useQuery({
    queryKey: ['factory', 'semantic', 'skills-risk'],
    queryFn: () => factoryApi.getSkillsRisk(),
    staleTime: 60000,
  });

  const { data: moldConflicts, isLoading: loadingMolds } = useQuery({
    queryKey: ['factory', 'semantic', 'mold-conflicts'],
    queryFn: () => factoryApi.getMoldConflicts(),
    staleTime: 60000,
  });

  const isLoading = loadingBottlenecks || loadingQuality || loadingSkills || loadingMolds;

  // Process exceptions from all sources
  const exceptions = useMemo<Exception[]>(() => {
    const result: Exception[] = [];

    // Process bottlenecks
    if (bottlenecks?.data?.bottlenecks) {
      bottlenecks.data.bottlenecks.slice(0, 5).forEach((b: any, idx: number) => {
        result.push({
          id: `bottleneck-${idx}`,
          type: 'bottleneck',
          title: `Bottleneck: ${b.fase_nome}`,
          description: `${b.pending_phases_count} phases pending with ${b.total_horas_previstas?.toLocaleString() || '?'} hours`,
          severity: b.bottleneck_score > 80 ? 'critical' : b.bottleneck_score > 60 ? 'high' : 'medium',
          trustIndex: bottlenecks.data_confidence || 58,
          dataSource: '/v1/factory/semantic/queries/bottlenecks',
          semanticLabel: bottlenecks.semantic_label,
          value: b.bottleneck_score,
          unit: 'bottleneck score',
          recommendation: 'Consider increasing capacity or redistributing workload',
          sandboxAction: {
            actionType: 'capacity_adjustment',
            description: 'Simulate capacity increase for this phase',
            params: { phase_id: b.fase_id },
          },
        });
      });
    }

    // Process quality errors
    if (quality?.data?.total_errors && quality.data.total_errors > 0) {
      const totalErrors = quality.data.total_errors;
      result.push({
        id: 'quality-total',
        type: 'quality',
        title: 'Quality Errors Detected',
        description: `${totalErrors.toLocaleString()} errors registered in system`,
        severity: totalErrors > 50000 ? 'high' : 'medium',
        trustIndex: quality.data_confidence ?? 67,
        dataSource: '/v1/factory/semantic/queries/quality',
        semanticLabel: quality.semantic_label ?? '',
        value: totalErrors,
        unit: 'total errors',
        recommendation: 'Review top error types and implement targeted improvements',
        sandboxAction: {
          actionType: 'quality_improvement',
          description: 'Simulate quality improvement impact',
        },
      });
    }

    // Process skills risk
    if (skillsRisk?.data?.phases_at_risk && skillsRisk.data.phases_at_risk > 0) {
      const phasesAtRisk = skillsRisk.data.phases_at_risk;
      result.push({
        id: 'skills-risk',
        type: 'skills_risk',
        title: 'Skills Gap Risk',
        description: `${phasesAtRisk} phases have single-point-of-failure risk`,
        severity: phasesAtRisk > 5 ? 'high' : 'medium',
        trustIndex: skillsRisk.data_confidence ?? 55,
        dataSource: '/v1/factory/semantic/queries/skills-risk',
        semanticLabel: skillsRisk.semantic_label ?? '',
        value: phasesAtRisk,
        unit: 'phases at risk',
        recommendation: 'Cross-train employees to reduce single-point-of-failure risk',
        sandboxAction: {
          actionType: 'skills_training',
          description: 'Simulate cross-training impact',
        },
      });
    }

    // Process mold conflicts
    if (moldConflicts?.data?.potential_conflicts && moldConflicts.data.potential_conflicts > 0) {
      const potentialConflicts = moldConflicts.data.potential_conflicts;
      const dataConfidence = moldConflicts.data_confidence ?? 35;
      result.push({
        id: 'mold-conflicts',
        type: 'mold_conflict',
        title: 'Potential Mold Conflicts',
        description: `${potentialConflicts} potential scheduling conflicts detected`,
        severity: 'medium',
        trustIndex: dataConfidence,
        dataSource: '/v1/factory/semantic/queries/mold-conflicts',
        semanticLabel: moldConflicts.semantic_label ?? '',
        value: potentialConflicts,
        unit: 'conflicts',
        blockedReason: dataConfidence < 40 
          ? 'DataPrevista has only 4.8% coverage - cannot confirm conflicts' 
          : undefined,
      });
    }

    // Sort by severity
    const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    result.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);

    return result;
  }, [bottlenecks, quality, skillsRisk, moldConflicts]);

  // Summary stats
  const stats = useMemo(() => ({
    total: exceptions.length,
    critical: exceptions.filter(e => e.severity === 'critical').length,
    high: exceptions.filter(e => e.severity === 'high').length,
    blocked: exceptions.filter(e => !!e.blockedReason).length,
  }), [exceptions]);

  return (
    <ModuleErrorBoundary moduleName="Operations Inbox">
    <DarkPageLayout
      title="Operations Inbox"
      subtitle="Actionable exceptions from factory data"
      icon={<Inbox size={20} />}
      actions={
        <DarkButton
          variant="secondary"
          icon={<RefreshCw size={16} />}
          onClick={() => window.location.reload()}
        >
          Refresh
        </DarkButton>
      }
    >
      {/* Data Source Notice */}
      <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-xl mb-6">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="text-sm font-medium text-blue-400">Real-Time Data from Semantic Queries</h4>
            <p className="text-xs text-slate-400 mt-1">
              Exceptions are identified from Factory Data Product semantic views.
              Trust indices reflect data quality from Folha_IA_extra.xlsx.
            </p>
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <DarkCard>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-slate-700 rounded-lg">
              <Inbox size={20} className="text-white" />
            </div>
            <div>
              <p className="text-xs text-slate-400">Total Exceptions</p>
              <p className="text-2xl font-bold text-white">{stats.total}</p>
            </div>
          </div>
        </DarkCard>
        <DarkCard>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/20 rounded-lg">
              <AlertTriangle size={20} className="text-red-400" />
            </div>
            <div>
              <p className="text-xs text-slate-400">Critical</p>
              <p className="text-2xl font-bold text-red-400">{stats.critical}</p>
            </div>
          </div>
        </DarkCard>
        <DarkCard>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-500/20 rounded-lg">
              <AlertCircle size={20} className="text-orange-400" />
            </div>
            <div>
              <p className="text-xs text-slate-400">High Priority</p>
              <p className="text-2xl font-bold text-orange-400">{stats.high}</p>
            </div>
          </div>
        </DarkCard>
        <DarkCard>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-slate-700 rounded-lg">
              <Ban size={20} className="text-slate-400" />
            </div>
            <div>
              <p className="text-xs text-slate-400">Blocked</p>
              <p className="text-2xl font-bold text-slate-400">{stats.blocked}</p>
            </div>
          </div>
        </DarkCard>
      </div>

      {/* Exceptions List */}
      {isLoading ? (
        <DarkCard className="text-center py-12">
          <Loader2 size={32} className="mx-auto mb-4 text-teal-400 animate-spin" />
          <p className="text-slate-400">Loading exceptions from semantic queries...</p>
        </DarkCard>
      ) : exceptions.length > 0 ? (
        <div className="space-y-4">
          {exceptions.map((exception) => (
            <ExceptionCard key={exception.id} exception={exception} />
          ))}
        </div>
      ) : (
        <DarkCard className="text-center py-12">
          <CheckCircle2 size={48} className="mx-auto mb-4 text-emerald-400" />
          <h3 className="text-lg font-semibold text-white mb-2">No Active Exceptions</h3>
          <p className="text-slate-400">All systems operating within normal parameters.</p>
        </DarkCard>
      )}

      {/* Quick Links */}
      <div className="mt-8 pt-6 border-t border-slate-700">
        <h3 className="text-sm font-medium text-slate-400 mb-4">Related Surfaces</h3>
        <div className="flex gap-4">
          <Link
            to="/twin"
            className="flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Play size={16} />
            Open Sandbox
            <ArrowRight size={14} />
          </Link>
          <Link
            to="/admin/data-quality"
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Shield size={16} />
            Data Quality Center
            <ArrowRight size={14} />
          </Link>
          <Link
            to="/profit/quality"
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <AlertCircle size={16} />
            Quality Analysis
            <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </DarkPageLayout>
    </ModuleErrorBoundary>
  );
}

export default OpsInboxPage;

