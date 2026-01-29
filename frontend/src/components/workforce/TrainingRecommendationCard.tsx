/**
 * Training Recommendation Card
 * =============================
 * 
 * Displays AI-generated training recommendations.
 * Each recommendation shows:
 * - Employee to train
 * - Target phase
 * - Reasoning
 * - Expected impact
 * - Estimated cost
 */

import { 
  GraduationCap, 
  User, 
  ArrowRight, 
  Layers, 
  AlertTriangle,
  TrendingDown,
  Shield,
  Play,
  ClipboardList,
  Eye,
  Star,
  Sparkles,
} from 'lucide-react';
import type { TrainingRecommendation } from './types';

interface TrainingRecommendationCardProps {
  recommendation: TrainingRecommendation;
  rank?: number;
  onSimulate?: () => void;
  onCreatePlan?: () => void;
  onViewProfile?: () => void;
  compact?: boolean;
}

const PRIORITY_STYLES = {
  critical: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    badge: 'bg-red-500/20 text-red-400',
    glow: 'shadow-red-500/20',
  },
  high: {
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/30',
    badge: 'bg-orange-500/20 text-orange-400',
    glow: 'shadow-orange-500/20',
  },
  medium: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    badge: 'bg-amber-500/20 text-amber-400',
    glow: 'shadow-amber-500/20',
  },
  low: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    badge: 'bg-blue-500/20 text-blue-400',
    glow: 'shadow-blue-500/20',
  },
};

const PRIORITY_LABELS = {
  critical: 'PRIORIDADE MÁXIMA',
  high: 'ALTA PRIORIDADE',
  medium: 'PRIORIDADE MÉDIA',
  low: 'BAIXA PRIORIDADE',
};

export function TrainingRecommendationCard({
  recommendation,
  rank,
  onSimulate,
  onCreatePlan,
  onViewProfile,
  compact = false,
}: TrainingRecommendationCardProps) {
  const styles = PRIORITY_STYLES[recommendation.priority];

  return (
    <div className={`
      ${styles.bg} ${styles.border} border rounded-xl overflow-hidden
      transition-all hover:shadow-lg ${styles.glow}
    `}>
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-700/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {rank && (
              <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center">
                <span className="text-lg font-bold text-white">#{rank}</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <span className={`px-2 py-1 rounded text-xs font-medium ${styles.badge}`}>
                {recommendation.priority === 'critical' && <Star size={10} className="inline mr-1" />}
                {PRIORITY_LABELS[recommendation.priority]}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 px-2 py-1 bg-slate-800/50 rounded">
            <Shield size={12} className="text-amber-400" />
            <span className="text-xs text-slate-400">Trust: {recommendation.trustIndex}%</span>
          </div>
        </div>
      </div>

      {/* Training Direction */}
      <div className="px-5 py-4">
        <div className="flex items-center gap-4 mb-4">
          {/* From Employee */}
          <button
            onClick={onViewProfile}
            className="flex-1 p-3 bg-slate-800/50 rounded-lg hover:bg-slate-800 transition-colors group"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-cyan-500/20 flex items-center justify-center">
                <User size={20} className="text-cyan-400" />
              </div>
              <div className="text-left min-w-0">
                <p className="text-xs text-slate-500 uppercase">Funcionário</p>
                <p className="text-sm font-medium text-white truncate group-hover:text-cyan-400 transition-colors">
                  {recommendation.employee.name}
                </p>
                <p className="text-xs text-slate-500">
                  {recommendation.employee.currentPhases.length} fases actuais
                </p>
              </div>
            </div>
          </button>

          {/* Arrow */}
          <div className="flex-shrink-0">
            <div className="w-10 h-10 rounded-full bg-gradient-to-r from-purple-500/20 to-pink-500/20 flex items-center justify-center">
              <ArrowRight size={20} className="text-purple-400" />
            </div>
          </div>

          {/* To Phase */}
          <div className="flex-1 p-3 bg-slate-800/50 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-indigo-500/20 flex items-center justify-center">
                <Layers size={20} className="text-indigo-400" />
              </div>
              <div className="text-left">
                <p className="text-xs text-slate-500 uppercase">Fase Alvo</p>
                <p className="text-sm font-medium text-white">{recommendation.targetPhase.name}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Reasoning */}
        {!compact && (
          <div className="mb-4">
            <p className="text-xs text-slate-400 uppercase mb-2 flex items-center gap-1">
              <Sparkles size={10} />
              Porquê esta recomendação:
            </p>
            <ul className="space-y-1">
              {recommendation.reasoning.map((reason, i) => (
                <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                  <span className="text-emerald-400 flex-shrink-0">•</span>
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Impact Metrics */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="p-3 bg-slate-900/50 rounded-lg text-center">
            <div className="flex items-center justify-center gap-1 text-emerald-400 mb-1">
              {recommendation.expectedImpact.spofEliminated ? (
                <AlertTriangle size={14} className="text-emerald-400" />
              ) : (
                <TrendingDown size={14} />
              )}
            </div>
            <p className="text-xs text-slate-500">SPOF Eliminado</p>
            <p className="text-sm font-bold text-white">
              {recommendation.expectedImpact.spofEliminated ? 'SIM ✓' : 'NÃO'}
            </p>
          </div>
          <div className="p-3 bg-slate-900/50 rounded-lg text-center">
            <div className="flex items-center justify-center gap-1 text-emerald-400 mb-1">
              <TrendingDown size={14} />
            </div>
            <p className="text-xs text-slate-500">Redução Risco</p>
            <p className="text-sm font-bold text-white">-{recommendation.expectedImpact.riskReduction}%</p>
          </div>
          <div className="p-3 bg-slate-900/50 rounded-lg text-center">
            <div className="flex items-center justify-center gap-1 text-cyan-400 mb-1">
              <Shield size={14} />
            </div>
            <p className="text-xs text-slate-500">Backlog Seguro</p>
            <p className="text-sm font-bold text-white">{recommendation.expectedImpact.backlogSecured}h</p>
          </div>
        </div>

        {/* Estimated Cost */}
        <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg mb-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-amber-400">💰 Custo Estimado de Formação</p>
              <p className="text-lg font-bold text-white">
                €{recommendation.estimatedCost.cost.toFixed(0)}
                <span className="text-sm font-normal text-slate-400 ml-2">
                  ({recommendation.estimatedCost.hours}h)
                </span>
              </p>
            </div>
            <p className="text-xs text-amber-400/70">
              ⚠️ Teórico
            </p>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="px-5 pb-4 flex items-center gap-2">
        <button
          onClick={onSimulate}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-lg font-medium text-sm transition-all"
        >
          <Play size={14} />
          Simular
        </button>
        <button
          onClick={onCreatePlan}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors"
        >
          <ClipboardList size={14} />
          Criar Plano
        </button>
        <button
          onClick={onViewProfile}
          className="px-3 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg transition-colors"
        >
          <Eye size={14} />
        </button>
      </div>
    </div>
  );
}

export function TrainingRecommendationList({
  recommendations,
  onSimulate,
  onCreatePlan,
  onViewProfile,
}: {
  recommendations: TrainingRecommendation[];
  onSimulate?: (rec: TrainingRecommendation) => void;
  onCreatePlan?: (rec: TrainingRecommendation) => void;
  onViewProfile?: (employeeId: string) => void;
}) {
  if (recommendations.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-8 text-center">
        <GraduationCap size={40} className="mx-auto mb-3 text-slate-600" />
        <h3 className="font-semibold text-white mb-1">Sem Recomendações</h3>
        <p className="text-sm text-slate-500">
          Não foram identificadas necessidades de formação críticas.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {recommendations.map((rec, index) => (
        <TrainingRecommendationCard
          key={rec.id}
          recommendation={rec}
          rank={index + 1}
          onSimulate={() => onSimulate?.(rec)}
          onCreatePlan={() => onCreatePlan?.(rec)}
          onViewProfile={() => onViewProfile?.(rec.employee.id)}
        />
      ))}
    </div>
  );
}

export default TrainingRecommendationCard;


