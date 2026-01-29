/**
 * Cascade Impact View
 * ====================
 * 
 * Visualizes the cascading impact when a phase becomes unavailable.
 * Shows how workforce issues ripple through:
 * 1. Workforce level (employees)
 * 2. Production level (orders in phase)
 * 3. Downstream level (dependent phases)
 * 4. Economic level (cost impact)
 */

import { useState } from 'react';
import { 
  Waves, 
  User, 
  Package, 
  ArrowDown, 
  AlertTriangle,
  DollarSign,
  Layers,
  Shield,
  Play,
  Info,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import type { CascadeImpact, CascadeLevel, RiskLevel } from './types';

interface CascadeImpactViewProps {
  impact: CascadeImpact | null;
  onSimulateMitigation?: () => void;
  onExportReport?: () => void;
  isLoading?: boolean;
}

const LEVEL_ICONS = {
  workforce: User,
  production: Package,
  downstream: Layers,
  economic: DollarSign,
};

const LEVEL_COLORS = {
  workforce: { bg: 'bg-cyan-500/20', text: 'text-cyan-400', border: 'border-cyan-500/30' },
  production: { bg: 'bg-indigo-500/20', text: 'text-indigo-400', border: 'border-indigo-500/30' },
  downstream: { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/30' },
  economic: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' },
};

const SEVERITY_COLORS: Record<RiskLevel, string> = {
  critical: 'text-red-400',
  high: 'text-orange-400',
  medium: 'text-amber-400',
  low: 'text-yellow-400',
  ok: 'text-slate-400',
};

function CascadeLevelSection({ 
  level, 
  isLast,
  isExpanded,
  onToggle,
}: { 
  level: CascadeLevel; 
  isLast: boolean;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const Icon = LEVEL_ICONS[level.type as keyof typeof LEVEL_ICONS] || Layers;
  const colors = LEVEL_COLORS[level.type as keyof typeof LEVEL_COLORS] || LEVEL_COLORS.production;

  return (
    <div className="relative">
      {/* Connector Line */}
      {!isLast && (
        <div className="absolute left-7 top-16 bottom-0 w-0.5 bg-gradient-to-b from-slate-600 to-transparent" />
      )}

      {/* Level Card */}
      <div className={`${colors.bg} ${colors.border} border rounded-xl overflow-hidden`}>
        {/* Header */}
        <button
          onClick={onToggle}
          className="w-full px-5 py-4 flex items-center justify-between hover:bg-white/5 transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className={`p-2 ${colors.bg} rounded-lg`}>
              <Icon size={18} className={colors.text} />
            </div>
            <div className="text-left">
              <p className="text-xs text-slate-500 uppercase">Nível {level.level}</p>
              <h4 className="font-semibold text-white">{level.title}</h4>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">{level.items.length} items</span>
            {isExpanded ? (
              <ChevronUp size={16} className="text-slate-400" />
            ) : (
              <ChevronDown size={16} className="text-slate-400" />
            )}
          </div>
        </button>

        {/* Items */}
        {isExpanded && (
          <div className="px-5 pb-4 space-y-2">
            {level.items.map((item, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg"
              >
                <span className="text-sm text-slate-300">{item.label}</span>
                <span className={`text-sm font-medium ${item.severity ? SEVERITY_COLORS[item.severity] : 'text-white'}`}>
                  {item.value}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Cascade Arrow */}
      {!isLast && (
        <div className="flex justify-center py-2">
          <div className="flex flex-col items-center">
            <ArrowDown size={16} className="text-slate-600" />
            <span className="text-[10px] text-slate-600">CASCATA</span>
          </div>
        </div>
      )}
    </div>
  );
}

export function CascadeImpactView({
  impact,
  onSimulateMitigation,
  onExportReport,
  isLoading = false,
}: CascadeImpactViewProps) {
  const [expandedLevels, setExpandedLevels] = useState<number[]>([0, 1]); // First two expanded by default

  const toggleLevel = (levelIndex: number) => {
    setExpandedLevels((prev) =>
      prev.includes(levelIndex)
        ? prev.filter((i) => i !== levelIndex)
        : [...prev, levelIndex]
    );
  };

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-800 rounded w-1/3" />
          <div className="h-32 bg-slate-800 rounded" />
          <div className="h-32 bg-slate-800 rounded" />
        </div>
      </div>
    );
  }

  if (!impact) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-8 text-center">
        <Waves size={40} className="mx-auto mb-3 text-slate-600" />
        <h3 className="font-semibold text-white mb-1">Selecione uma Fase</h3>
        <p className="text-sm text-slate-500">
          Clique numa fase no heatmap ou grafo para ver o impacto em cascata.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-700 bg-gradient-to-r from-orange-500/10 to-red-500/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-500/20 rounded-lg">
              <Waves className="text-orange-400" size={20} />
            </div>
            <div>
              <h3 className="font-semibold text-white">
                🌊 Impacto em Cascata — {impact.sourcePhaseName}
              </h3>
              {impact.triggerEmployeeName && (
                <p className="text-xs text-slate-400">
                  Se <span className="text-orange-400">{impact.triggerEmployeeName}</span> ficar indisponível
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/50 rounded-lg">
            <Shield size={14} className="text-amber-400" />
            <span className="text-sm text-slate-400">Trust: <span className="text-white">{impact.trustIndex}%</span></span>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 p-6 border-b border-slate-700">
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-center">
          <Package size={20} className="mx-auto mb-2 text-red-400" />
          <p className="text-2xl font-bold text-white">{impact.totalOrdersAffected}</p>
          <p className="text-xs text-slate-400">Ordens Afectadas</p>
        </div>
        <div className="p-4 bg-orange-500/10 border border-orange-500/20 rounded-xl text-center">
          <AlertTriangle size={20} className="mx-auto mb-2 text-orange-400" />
          <p className="text-2xl font-bold text-white">{impact.totalBacklogAffected}h</p>
          <p className="text-xs text-slate-400">Backlog em Risco</p>
        </div>
        <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl text-center">
          <DollarSign size={20} className="mx-auto mb-2 text-amber-400" />
          <p className="text-2xl font-bold text-white">€{impact.estimatedDailyCost.toFixed(0)}</p>
          <p className="text-xs text-slate-400">Custo/Dia (Teórico)</p>
        </div>
      </div>

      {/* Cascade Levels */}
      <div className="p-6 space-y-2">
        {impact.levels.map((level, index) => (
          <CascadeLevelSection
            key={level.level}
            level={level}
            isLast={index === impact.levels.length - 1}
            isExpanded={expandedLevels.includes(index)}
            onToggle={() => toggleLevel(index)}
          />
        ))}
      </div>

      {/* Warnings */}
      {impact.warnings.length > 0 && (
        <div className="px-6 pb-4">
          <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
            <p className="text-xs text-amber-400 font-medium mb-2">⚠️ Limitações da Análise:</p>
            <ul className="space-y-1">
              {impact.warnings.map((warning, i) => (
                <li key={i} className="text-xs text-amber-300/80 flex items-start gap-2">
                  <Info size={10} className="flex-shrink-0 mt-0.5" />
                  {warning}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="px-6 pb-6 flex items-center gap-3">
        <button
          onClick={onSimulateMitigation}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-lg font-medium transition-all"
        >
          <Play size={16} />
          Simular Mitigação
        </button>
        <button
          onClick={onExportReport}
          className="px-4 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
        >
          Exportar
        </button>
      </div>

      {/* Footer */}
      <div className="px-6 py-3 bg-slate-800/50 border-t border-slate-700">
        <p className="text-xs text-slate-500 flex items-center gap-2">
          <Info size={10} />
          Análise teórica baseada em dados disponíveis. Não inclui: férias, ausências reais, flexibilidade de turnos.
        </p>
      </div>
    </div>
  );
}

export default CascadeImpactView;


