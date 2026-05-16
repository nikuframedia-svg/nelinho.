/**
 * Scenario Comparison Matrix
 * ===========================
 * 
 * Compare multiple workforce scenarios side by side.
 * This is the FEATURE 5 from the Workforce Operations System.
 * 
 * Features:
 * - Side-by-side comparison of baseline vs scenarios
 * - Visual indicators for better/worse metrics
 * - Recommended scenario highlighting
 */

import { useState } from 'react';
import {
  BarChart3,
  Check,
  Share2,
  Shield,
  TrendingDown,
  DollarSign,
  Clock,
  AlertTriangle,
  Users,
} from 'lucide-react';
import type { ScenarioComparison } from './types';

interface ScenarioComparisonMatrixProps {
  comparison: ScenarioComparison | null;
  onSaveAll?: () => void;
  onPresent?: () => void;
  onApproveScenario?: (scenarioId: string) => void;
  isLoading?: boolean;
}

const SCENARIO_TYPE_STYLES = {
  baseline: { bg: 'bg-slate-700', text: 'text-slate-400', label: 'Actual' },
  training: { bg: 'bg-purple-500/20', text: 'text-purple-400', label: 'Formação' },
  hiring: { bg: 'bg-cyan-500/20', text: 'text-cyan-400', label: 'Contratação' },
  custom: { bg: 'bg-amber-500/20', text: 'text-amber-400', label: 'Personalizado' },
};

export function ScenarioComparisonMatrix({
  comparison,
  onSaveAll,
  onPresent,
  onApproveScenario,
  isLoading = false,
}: ScenarioComparisonMatrixProps) {
  const [hoveredScenario, setHoveredScenario] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-8 animate-pulse">
        <div className="h-8 bg-slate-800 rounded w-1/3 mb-6" />
        <div className="h-64 bg-slate-800 rounded" />
      </div>
    );
  }

  if (!comparison || comparison.scenarios.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-8 text-center">
        <BarChart3 size={40} className="mx-auto mb-3 text-slate-600" />
        <h3 className="font-semibold text-white mb-1">Sem Cenários para Comparar</h3>
        <p className="text-sm text-slate-500">
          Crie cenários no simulador para poder compará-los.
        </p>
      </div>
    );
  }

  // Helper to get value from both camelCase and snake_case keys
  const getMetricValue = (metrics: Record<string, unknown>, camelKey: string, snakeKey: string): number | null => {
    const value = metrics[camelKey] ?? metrics[snakeKey];
    return typeof value === 'number' ? value : null;
  };

  // Helper to safely check isRecommended with both key formats
  const isScenarioRecommended = (scenario: typeof comparison.scenarios[0]): boolean => {
    return !!(scenario.isRecommended ?? scenario.is_recommended);
  };

  const getRecommendationReason = (scenario: typeof comparison.scenarios[0]): string | undefined => {
    return scenario.recommendationReason ?? scenario.recommendation_reason;
  };

  const metrics = [
    { 
      camelKey: 'spofCount',
      snakeKey: 'spof_count',
      label: 'SPOF Count', 
      icon: AlertTriangle, 
      format: (v: number | null) => v !== null ? v.toString() : '—', 
      better: 'lower' as const,
      description: 'Single Points of Failure',
    },
    { 
      camelKey: 'avgRiskScore',
      snakeKey: 'avg_risk_score',
      label: 'Risco Médio', 
      icon: TrendingDown, 
      format: (v: number | null) => v !== null ? `${v.toFixed(0)}%` : '—', 
      better: 'lower' as const,
      description: 'Score médio de risco operacional',
    },
    { 
      camelKey: 'backlogAtRisk',
      snakeKey: 'backlog_at_risk',
      label: 'Backlog em Risco', 
      icon: Clock, 
      format: (v: number | null) => v !== null ? `${v.toFixed(0)}h` : '—', 
      better: 'lower' as const,
      description: 'Horas de trabalho em risco',
    },
    { 
      camelKey: 'estimatedCost',
      snakeKey: 'estimated_cost',
      label: 'Custo Estimado', 
      icon: DollarSign, 
      format: (v: number | null) => v !== null ? `€${v.toFixed(0)}` : '—', 
      better: 'lower' as const,
      description: 'Investimento necessário',
    },
    { 
      camelKey: 'paybackDays',
      snakeKey: 'payback_days',
      label: 'Payback Est.', 
      icon: Clock, 
      format: (v: number | null) => v ? `${v} dias` : '—', 
      better: 'lower' as const,
      description: 'Tempo para retorno do investimento',
    },
  ];

  const recommendedScenario = comparison.scenarios.find(s => isScenarioRecommended(s));
  const baselineScenario = comparison.scenarios.find(s => s.type === 'baseline');
  const trustIndex = comparison.trustIndex ?? comparison.trust_index ?? 0;

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-lg">
            <BarChart3 className="text-indigo-400" size={20} />
          </div>
          <div>
            <h3 className="font-semibold text-white">📊 Comparação de Cenários — Workforce</h3>
            <p className="text-xs text-slate-500">
              {comparison.scenarios.length} cenários • Trust: {trustIndex}%
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {onSaveAll && (
            <button
              onClick={onSaveAll}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg text-sm transition-colors"
            >
              Guardar Todos
            </button>
          )}
          {onPresent && (
            <button
              onClick={onPresent}
              className="px-3 py-1.5 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg text-sm flex items-center gap-2 transition-colors"
            >
              <Share2 size={14} />
              Apresentar
            </button>
          )}
        </div>
      </div>

      {/* Comparison Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="text-left px-6 py-4 text-sm font-medium text-slate-400 w-48">
                Métrica
              </th>
              {comparison.scenarios.map(scenario => {
                const typeStyle = SCENARIO_TYPE_STYLES[scenario.type as keyof typeof SCENARIO_TYPE_STYLES] || SCENARIO_TYPE_STYLES.custom;
                
                return (
                  <th
                    key={scenario.id}
                    className={`text-center px-4 py-4 min-w-[140px] transition-colors ${
                      isScenarioRecommended(scenario) 
                        ? 'bg-emerald-500/10' 
                        : hoveredScenario === scenario.id 
                          ? 'bg-slate-800/50' 
                          : ''
                    }`}
                    onMouseEnter={() => setHoveredScenario(scenario.id)}
                    onMouseLeave={() => setHoveredScenario(null)}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className={`text-sm font-semibold ${
                        scenario.type === 'baseline' ? 'text-slate-400' : 'text-white'
                      }`}>
                        {scenario.name}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${typeStyle.bg} ${typeStyle.text}`}>
                        {typeStyle.label}
                      </span>
                      {isScenarioRecommended(scenario) && (
                        <span className="text-xs px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded flex items-center gap-1">
                          <Check size={10} />
                          RECOMENDADO
                        </span>
                      )}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric, idx) => {
              const Icon = metric.icon;
              const baselineValue = baselineScenario ? getMetricValue(baselineScenario.metrics as Record<string, unknown>, metric.camelKey, metric.snakeKey) : null;
              
              return (
                <tr 
                  key={metric.camelKey} 
                  className={`border-b border-slate-800 ${idx % 2 === 0 ? 'bg-slate-900/50' : ''}`}
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <Icon size={16} className="text-slate-500" />
                      <div>
                        <span className="text-sm text-slate-300">{metric.label}</span>
                        <p className="text-xs text-slate-600">{metric.description}</p>
                      </div>
                    </div>
                  </td>
                  {comparison.scenarios.map(scenario => {
                    const value = getMetricValue(scenario.metrics as Record<string, unknown>, metric.camelKey, metric.snakeKey);
                    const isBaseline = scenario.type === 'baseline';
                    
                    // Determine if this value is better than baseline
                    let isBetter = false;
                    let isWorse = false;
                    if (!isBaseline && baselineValue !== null && value !== null) {
                      if (metric.better === 'lower') {
                        isBetter = value < baselineValue;
                        isWorse = value > baselineValue;
                      } else {
                        isBetter = value > baselineValue;
                        isWorse = value < baselineValue;
                      }
                    }
                    
                    // Calculate percentage change
                    let changePercent = 0;
                    if (!isBaseline && baselineValue && baselineValue !== 0 && value !== null) {
                      changePercent = ((value - baselineValue) / baselineValue) * 100;
                    }
                    
                    return (
                      <td
                        key={`${scenario.id}-${metric.camelKey}`}
                        className={`text-center px-4 py-4 ${
                          isScenarioRecommended(scenario) ? 'bg-emerald-500/5' : ''
                        }`}
                      >
                        <div className="flex flex-col items-center">
                          <span className={`text-sm font-medium ${
                            isBaseline 
                              ? 'text-slate-400' 
                              : isBetter 
                                ? 'text-emerald-400' 
                                : isWorse
                                  ? 'text-red-400'
                                  : 'text-white'
                          }`}>
                            {metric.format(value as number)}
                          </span>
                          {!isBaseline && changePercent !== 0 && (
                            <span className={`text-xs ${
                              isBetter ? 'text-emerald-500' : isWorse ? 'text-red-500' : 'text-slate-500'
                            }`}>
                              {changePercent > 0 ? '+' : ''}{changePercent.toFixed(0)}%
                              {isBetter ? ' ▼' : isWorse ? ' ▲' : ''}
                            </span>
                          )}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Summary Row */}
      <div className="px-6 py-4 bg-slate-800/30 border-t border-slate-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            {comparison.scenarios.filter(s => s.type !== 'baseline').map(scenario => {
              const typeStyle = SCENARIO_TYPE_STYLES[scenario.type as keyof typeof SCENARIO_TYPE_STYLES] || SCENARIO_TYPE_STYLES.custom;
              const baselineSpof = baselineScenario ? getMetricValue(baselineScenario.metrics as Record<string, unknown>, 'spofCount', 'spof_count') : 0;
              const scenarioSpof = getMetricValue(scenario.metrics as Record<string, unknown>, 'spofCount', 'spof_count') || 0;
              const spofReduction = (baselineSpof || 0) - scenarioSpof;
              
              return (
                <div key={scenario.id} className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${typeStyle.bg}`} />
                  <span className="text-xs text-slate-400">
                    {scenario.name}: 
                    {spofReduction > 0 && (
                      <span className="text-emerald-400 ml-1">-{spofReduction} SPOF</span>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="flex items-center gap-2">
            <Users size={14} className="text-slate-500" />
            <span className="text-xs text-slate-400">
              Base: {baselineScenario ? (getMetricValue(baselineScenario.metrics as Record<string, unknown>, 'spofCount', 'spof_count') || 0) : 0} SPOFs
            </span>
          </div>
        </div>
      </div>

      {/* Recommendation Footer */}
      {recommendedScenario && (
        <div className="px-6 py-4 bg-emerald-500/5 border-t border-emerald-500/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Check size={20} className="text-emerald-400" />
              <div>
                <p className="text-sm font-medium text-emerald-400">
                  ✅ Cenário Recomendado: {recommendedScenario.name}
                </p>
                {getRecommendationReason(recommendedScenario) && (
                  <p className="text-xs text-emerald-300/70">
                    {getRecommendationReason(recommendedScenario)}
                  </p>
                )}
              </div>
            </div>
            {onApproveScenario && (
              <button 
                onClick={() => onApproveScenario(recommendedScenario.id)}
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
              >
                <Check size={14} />
                Aprovar para Execução
              </button>
            )}
          </div>
        </div>
      )}

      {/* Trust Warning */}
      <div className="px-6 py-3 bg-amber-500/5 border-t border-amber-500/20">
        <p className="text-xs text-amber-400/70 flex items-center gap-2">
          <Shield size={12} />
          ⚠️ Todos os valores são TEÓRICOS baseados em Trust {trustIndex}% — 
          Não inclui custos reais de formação, curva de aprendizagem ou benefícios.
        </p>
      </div>
    </div>
  );
}

export default ScenarioComparisonMatrix;

