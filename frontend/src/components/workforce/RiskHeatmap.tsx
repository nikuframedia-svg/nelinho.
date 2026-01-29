/**
 * Risk Heatmap Component
 * =======================
 * 
 * Visualizes workforce risk as a 2D scatter plot where:
 * - X-axis: Backlog hours (operational load)
 * - Y-axis: Risk score (operational fragility)
 * 
 * Each phase is a bubble whose size represents the number of employees.
 * Color indicates risk level: red (critical), orange (high), yellow (medium), green (ok)
 */

import { useMemo, useState } from 'react';
import { AlertTriangle, Users, Clock, Info, Play, Shield } from 'lucide-react';
import type { PhaseRisk, RiskLevel } from './types';

interface RiskHeatmapProps {
  data: PhaseRisk[];
  onPhaseClick?: (phaseId: string) => void;
  onSimulate?: (phaseId: string) => void;
  trustIndex?: number;
  isLoading?: boolean;
}

const RISK_COLORS: Record<RiskLevel, { bg: string; border: string; glow: string }> = {
  critical: { bg: 'bg-red-500', border: 'border-red-400', glow: 'shadow-red-500/50' },
  high: { bg: 'bg-orange-500', border: 'border-orange-400', glow: 'shadow-orange-500/50' },
  medium: { bg: 'bg-amber-500', border: 'border-amber-400', glow: 'shadow-amber-500/50' },
  low: { bg: 'bg-yellow-500', border: 'border-yellow-400', glow: 'shadow-yellow-500/50' },
  ok: { bg: 'bg-emerald-500', border: 'border-emerald-400', glow: 'shadow-emerald-500/50' },
};

const RISK_LABELS: Record<RiskLevel, string> = {
  critical: 'CRÍTICO',
  high: 'ALTO',
  medium: 'MÉDIO',
  low: 'BAIXO',
  ok: 'OK',
};

export function RiskHeatmap({ 
  data, 
  onPhaseClick, 
  onSimulate,
  trustIndex = 55,
  isLoading = false,
}: RiskHeatmapProps) {
  const [hoveredPhase, setHoveredPhase] = useState<string | null>(null);
  const [selectedPhase, setSelectedPhase] = useState<string | null>(null);

  // Calculate chart bounds
  const bounds = useMemo(() => {
    if (!data.length) return { maxBacklog: 1000, maxRisk: 100 };
    const maxBacklog = Math.max(...data.map(d => d.backlogHours), 100);
    const maxRisk = 100; // Risk is always 0-100
    return { maxBacklog: maxBacklog * 1.1, maxRisk };
  }, [data]);

  // Calculate bubble positions
  const bubbles = useMemo(() => {
    return data.map(phase => ({
      ...phase,
      x: (phase.backlogHours / bounds.maxBacklog) * 100,
      y: 100 - phase.riskScore, // Invert Y so high risk is at top
      size: Math.max(20, Math.min(60, 15 + phase.aptosActive * 5)),
    }));
  }, [data, bounds]);

  const handlePhaseSelect = (phaseId: string) => {
    setSelectedPhase(phaseId === selectedPhase ? null : phaseId);
    onPhaseClick?.(phaseId);
  };

  const selectedPhaseData = selectedPhase 
    ? data.find(p => p.phaseId === selectedPhase) 
    : null;

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 animate-pulse">
        <div className="h-8 bg-slate-800 rounded w-1/3 mb-4" />
        <div className="h-64 bg-slate-800 rounded" />
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-lg">
            <AlertTriangle className="text-purple-400" size={20} />
          </div>
          <div>
            <h3 className="font-semibold text-white">Superfície de Risco Operacional</h3>
            <p className="text-xs text-slate-500">Clique numa fase para ver detalhes</p>
          </div>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-lg">
          <Shield size={14} className={trustIndex >= 60 ? 'text-emerald-400' : 'text-amber-400'} />
          <span className="text-sm text-slate-400">Trust: <span className="text-white font-medium">{trustIndex}%</span></span>
        </div>
      </div>

      {/* Chart Area */}
      <div className="p-6">
        <div className="relative h-80 bg-slate-800/50 rounded-lg border border-slate-700/50 overflow-hidden">
          {/* Y-Axis Label */}
          <div className="absolute left-0 top-0 bottom-0 w-12 flex items-center justify-center">
            <span className="text-xs text-slate-500 -rotate-90 whitespace-nowrap">RISCO (%)</span>
          </div>

          {/* X-Axis Label */}
          <div className="absolute bottom-0 left-12 right-0 h-8 flex items-center justify-center">
            <span className="text-xs text-slate-500">BACKLOG (horas)</span>
          </div>

          {/* Grid Lines */}
          <div className="absolute left-12 right-4 top-4 bottom-8">
            {/* Horizontal grid lines */}
            {[0, 25, 50, 75, 100].map((y) => (
              <div
                key={y}
                className="absolute left-0 right-0 border-t border-slate-700/30"
                style={{ top: `${y}%` }}
              >
                <span className="absolute -left-8 -translate-y-1/2 text-[10px] text-slate-600">
                  {100 - y}%
                </span>
              </div>
            ))}
            {/* Vertical grid lines */}
            {[0, 25, 50, 75, 100].map((x) => (
              <div
                key={x}
                className="absolute top-0 bottom-0 border-l border-slate-700/30"
                style={{ left: `${x}%` }}
              >
                <span className="absolute -bottom-6 -translate-x-1/2 text-[10px] text-slate-600">
                  {Math.round((x / 100) * bounds.maxBacklog)}h
                </span>
              </div>
            ))}

            {/* Risk Zone Background */}
            <div className="absolute inset-0 overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-1/4 bg-gradient-to-b from-red-500/10 to-transparent" />
              <div className="absolute bottom-0 left-0 right-0 h-1/4 bg-gradient-to-t from-emerald-500/10 to-transparent" />
            </div>

            {/* Bubbles */}
            {bubbles.map((bubble) => {
              const isHovered = hoveredPhase === bubble.phaseId;
              const isSelected = selectedPhase === bubble.phaseId;
              const colors = RISK_COLORS[bubble.riskLevel];

              return (
                <button
                  key={bubble.phaseId}
                  className={`
                    absolute transform -translate-x-1/2 -translate-y-1/2 rounded-full 
                    transition-all duration-300 cursor-pointer
                    ${colors.bg} ${colors.border} border-2
                    ${isHovered || isSelected ? `scale-125 ${colors.glow} shadow-lg z-10` : 'opacity-80 hover:opacity-100'}
                    ${bubble.isSPOF ? 'ring-2 ring-white/50 ring-offset-2 ring-offset-slate-800' : ''}
                  `}
                  style={{
                    left: `${bubble.x}%`,
                    top: `${bubble.y}%`,
                    width: `${bubble.size}px`,
                    height: `${bubble.size}px`,
                  }}
                  onMouseEnter={() => setHoveredPhase(bubble.phaseId)}
                  onMouseLeave={() => setHoveredPhase(null)}
                  onClick={() => handlePhaseSelect(bubble.phaseId)}
                  title={`${bubble.phaseName}: ${bubble.aptosActive} aptos, ${bubble.backlogHours}h backlog`}
                >
                  {bubble.isSPOF && (
                    <span className="absolute -top-1 -right-1 text-xs">⚠️</span>
                  )}
                </button>
              );
            })}

            {/* Hover Tooltip */}
            {hoveredPhase && !selectedPhase && (
              <div className="absolute bottom-4 right-4 bg-slate-800 border border-slate-600 rounded-lg p-3 z-20 min-w-48 shadow-xl">
                {(() => {
                  const phase = data.find(p => p.phaseId === hoveredPhase);
                  if (!phase) return null;
                  return (
                    <>
                      <p className="font-semibold text-white text-sm mb-2">{phase.phaseName}</p>
                      <div className="space-y-1 text-xs">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Aptos activos:</span>
                          <span className={`font-medium ${phase.isSPOF ? 'text-red-400' : 'text-white'}`}>
                            {phase.aptosActive}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Backlog:</span>
                          <span className="text-white font-medium">{phase.backlogHours.toFixed(0)}h</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Risco:</span>
                          <span className={`font-medium ${RISK_COLORS[phase.riskLevel].bg.replace('bg-', 'text-').replace('-500', '-400')}`}>
                            {phase.riskScore.toFixed(0)}% ({RISK_LABELS[phase.riskLevel]})
                          </span>
                        </div>
                      </div>
                    </>
                  );
                })()}
              </div>
            )}
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center justify-center gap-6 mt-4">
          {(['critical', 'high', 'medium', 'low', 'ok'] as RiskLevel[]).map((level) => (
            <div key={level} className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${RISK_COLORS[level].bg}`} />
              <span className="text-xs text-slate-400">{RISK_LABELS[level]}</span>
            </div>
          ))}
          <div className="flex items-center gap-2 ml-4 pl-4 border-l border-slate-700">
            <div className="w-3 h-3 rounded-full bg-white ring-2 ring-white/50" />
            <span className="text-xs text-slate-400">SPOF</span>
          </div>
        </div>
      </div>

      {/* Selected Phase Details */}
      {selectedPhaseData && (
        <div className="px-6 pb-6">
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h4 className="font-semibold text-white text-lg">{selectedPhaseData.phaseName}</h4>
                <p className="text-sm text-slate-400 flex items-center gap-2 mt-1">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${RISK_COLORS[selectedPhaseData.riskLevel].bg}`}>
                    {RISK_LABELS[selectedPhaseData.riskLevel]}
                  </span>
                  {selectedPhaseData.isSPOF && (
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30">
                      ⚠️ SINGLE POINT OF FAILURE
                    </span>
                  )}
                </p>
              </div>
              <button
                onClick={() => setSelectedPhase(null)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                  <Users size={12} />
                  <span>Funcionários Aptos</span>
                </div>
                <p className="text-2xl font-bold text-white">{selectedPhaseData.aptosActive}</p>
                <p className="text-xs text-slate-500">de {selectedPhaseData.aptosCount} total</p>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                  <Clock size={12} />
                  <span>Backlog em Risco</span>
                </div>
                <p className="text-2xl font-bold text-white">{selectedPhaseData.backlogHours.toFixed(0)}h</p>
                <p className="text-xs text-slate-500">≈ {selectedPhaseData.backlogDays.toFixed(1)} dias</p>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                  <AlertTriangle size={12} />
                  <span>Ordens Afectadas</span>
                </div>
                <p className="text-2xl font-bold text-white">{selectedPhaseData.ordersAtRisk}</p>
                <p className="text-xs text-slate-500">ordens em aberto</p>
              </div>
            </div>

            {/* Employees List */}
            <div className="mb-4">
              <p className="text-xs text-slate-400 mb-2">Funcionários qualificados:</p>
              <div className="flex flex-wrap gap-2">
                {selectedPhaseData.employees.map((emp) => (
                  <span
                    key={emp.id}
                    className={`px-2 py-1 rounded text-xs ${
                      emp.isActive 
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-slate-700 text-slate-400 border border-slate-600'
                    }`}
                  >
                    {emp.name} {!emp.isActive && '(inativo)'}
                  </span>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => onSimulate?.(selectedPhaseData.phaseId)}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-lg font-medium text-sm transition-all"
              >
                <Play size={14} />
                Simular Cross-Training
              </button>
              <button
                onClick={() => onPhaseClick?.(selectedPhaseData.phaseId)}
                className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors"
              >
                <Info size={14} />
                Ver Detalhes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Warning Footer */}
      <div className="px-6 py-3 bg-slate-800/50 border-t border-slate-700">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Info size={12} />
          <span>
            Dados teóricos baseados em FuncionariosFasesAptos e FasesOrdemFabrico. 
            Trust Index: {trustIndex}%. Não inclui ausências, férias ou formação em curso.
          </span>
        </div>
      </div>
    </div>
  );
}

export default RiskHeatmap;


