/**
 * SPOF Alert Panel
 * =================
 * 
 * Displays critical Single Point of Failure alerts.
 * These are phases where only 1 employee is capable,
 * meaning if that person is unavailable, production stops.
 */

import { AlertTriangle, User, Clock, ArrowRight, Play, Shield, XCircle } from 'lucide-react';
import type { SPOFAlert } from './types';

interface SPOFAlertPanelProps {
  alerts: SPOFAlert[];
  onSimulate?: (phaseId: string) => void;
  onViewDetails?: (phaseId: string) => void;
  onViewEmployee?: (employeeId: string) => void;
  trustIndex?: number;
  compact?: boolean;
}

export function SPOFAlertPanel({
  alerts,
  onSimulate,
  onViewDetails,
  onViewEmployee,
  trustIndex = 55,
  compact = false,
}: SPOFAlertPanelProps) {
  if (alerts.length === 0) {
    return (
      <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-6 text-center">
        <div className="w-12 h-12 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
          <Shield className="text-emerald-400" size={24} />
        </div>
        <h3 className="font-semibold text-emerald-400 mb-1">Sem SPOFs Detectados</h3>
        <p className="text-sm text-slate-400">
          Nenhuma fase depende de um único funcionário.
        </p>
      </div>
    );
  }

  const criticalCount = alerts.filter(a => a.riskLevel === 'critical').length;
  const highCount = alerts.filter(a => a.riskLevel === 'high').length;

  return (
    <div className="bg-slate-900 border border-red-500/30 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 bg-gradient-to-r from-red-500/10 to-orange-500/10 border-b border-red-500/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="p-2 bg-red-500/20 rounded-lg animate-pulse">
                <AlertTriangle className="text-red-400" size={20} />
              </div>
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-[10px] font-bold flex items-center justify-center text-white">
                {alerts.length}
              </span>
            </div>
            <div>
              <h3 className="font-semibold text-white">⚠️ Single Points of Failure</h3>
              <p className="text-xs text-red-300/70">
                {criticalCount > 0 && <span className="text-red-400">{criticalCount} críticos</span>}
                {criticalCount > 0 && highCount > 0 && ' • '}
                {highCount > 0 && <span className="text-orange-400">{highCount} altos</span>}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/50 rounded-lg">
            <Shield size={14} className="text-amber-400" />
            <span className="text-sm text-slate-400">Trust: <span className="text-white">{trustIndex}%</span></span>
          </div>
        </div>
      </div>

      {/* Alerts List */}
      <div className={`divide-y divide-slate-800 ${compact ? 'max-h-64 overflow-y-auto' : ''}`}>
        {alerts.map((alert, index) => (
          <div 
            key={`${alert.phaseId}-${alert.employeeId}`}
            className={`
              p-4 hover:bg-slate-800/30 transition-colors
              ${alert.riskLevel === 'critical' ? 'border-l-4 border-l-red-500' : 'border-l-4 border-l-orange-500'}
            `}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                {/* Phase Name */}
                <div className="flex items-center gap-2 mb-2">
                  <span className={`
                    px-2 py-0.5 rounded text-xs font-medium
                    ${alert.riskLevel === 'critical' ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'}
                  `}>
                    #{index + 1} {alert.riskLevel === 'critical' ? 'CRÍTICO' : 'ALTO'}
                  </span>
                  <h4 className="font-semibold text-white truncate">{alert.phaseName}</h4>
                </div>

                {/* Details */}
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <button
                    onClick={() => onViewEmployee?.(alert.employeeId)}
                    className="flex items-center gap-2 p-2 bg-slate-800/50 rounded-lg text-left hover:bg-slate-800 transition-colors group"
                  >
                    <User size={14} className="text-slate-400" />
                    <div className="min-w-0">
                      <p className="text-[10px] text-slate-500 uppercase">Único Apto</p>
                      <p className="text-sm text-white font-medium truncate group-hover:text-accent">
                        {alert.employeeName}
                      </p>
                    </div>
                  </button>
                  <div className="flex items-center gap-2 p-2 bg-slate-800/50 rounded-lg">
                    <Clock size={14} className="text-slate-400" />
                    <div>
                      <p className="text-[10px] text-slate-500 uppercase">Backlog em Risco</p>
                      <p className="text-sm text-white font-medium">{alert.backlogHours.toFixed(0)}h</p>
                    </div>
                  </div>
                </div>

                {/* Impact Warning */}
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                  <p className="text-xs text-red-300 flex items-start gap-2">
                    <XCircle size={14} className="flex-shrink-0 mt-0.5" />
                    <span>
                      <strong>Se {alert.employeeName.split(' ')[0]} ficar indisponível:</strong>{' '}
                      {alert.ordersAffected} ordens param • ~€{alert.estimatedDailyCost.toFixed(0)}/dia em risco
                    </span>
                  </p>
                </div>
              </div>

              {/* Actions */}
              {!compact && (
                <div className="flex flex-col gap-2">
                  <button
                    onClick={() => onSimulate?.(alert.phaseId)}
                    className="flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-lg text-sm font-medium transition-all whitespace-nowrap"
                  >
                    <Play size={12} />
                    Simular
                  </button>
                  <button
                    onClick={() => onViewDetails?.(alert.phaseId)}
                    className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors whitespace-nowrap"
                  >
                    <ArrowRight size={12} />
                    Detalhes
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Summary Footer */}
      <div className="px-4 py-3 bg-slate-800/50 border-t border-slate-800">
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">
            💡 Recomendação: Cross-train pelo menos 1 pessoa adicional para cada fase SPOF
          </p>
          {compact && onSimulate && (
            <button
              onClick={() => onSimulate(alerts[0]?.phaseId)}
              className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300"
            >
              Simular todos <ArrowRight size={12} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default SPOFAlertPanel;

