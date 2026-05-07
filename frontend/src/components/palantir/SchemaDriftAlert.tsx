/**
 * SchemaDriftAlert — Schema drift detection alert panel
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 * 
 * "Silent changes in source data are the biggest threat"
 */

import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Plus, Minus, RefreshCw, TrendingUp, X } from 'lucide-react';
import type { SchemaDrift } from '@/types';
import { useSchemaDrift } from '@/hooks';

const DRIFT_ICONS = {
  new_column: <Plus className="w-4 h-4 text-emerald-400" />,
  missing_column: <Minus className="w-4 h-4 text-red-400" />,
  type_change: <RefreshCw className="w-4 h-4 text-amber-400" />,
  distribution_shift: <TrendingUp className="w-4 h-4 text-blue-400" />,
};

const DRIFT_LABELS = {
  new_column: { label: 'Novo Campo', color: 'emerald' },
  missing_column: { label: 'Campo Removido', color: 'red' },
  type_change: { label: 'Tipo Alterado', color: 'amber' },
  distribution_shift: { label: 'Distribuição Alterada', color: 'blue' },
};

interface SchemaDriftAlertProps {
  position?: 'fixed' | 'inline';
  onDismiss?: () => void;
  /** Optional: caller-provided drifts (overrides the internal hook). */
  drifts?: SchemaDrift[];
  /** Optional: caller-provided action handler (overrides the internal hook). */
  onAction?: (drift: SchemaDrift, action: 'reject' | 'accept' | 'ignore') => Promise<boolean>;
}

export function SchemaDriftAlert({
  position = 'fixed',
  onDismiss,
  drifts: driftsOverride,
  onAction: onActionOverride,
}: SchemaDriftAlertProps) {
  const hookData = useSchemaDrift();
  const drifts = driftsOverride ?? hookData.drifts;
  const handleAction = onActionOverride ?? hookData.handleAction;

  if (drifts.length === 0) return null;

  const criticalCount = drifts.filter(d => d.impact === 'critical').length;
  
  const containerClass = position === 'fixed' 
    ? 'fixed top-4 right-4 z-50 max-w-md' 
    : 'w-full';

  return (
    <motion.div
      initial={{ opacity: 0, y: position === 'fixed' ? -20 : 0, x: position === 'fixed' ? 20 : 0 }}
      animate={{ opacity: 1, y: 0, x: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className={containerClass}
    >
      <div className="bg-surface-800 border border-amber-500/50 rounded-xl 
                      shadow-2xl shadow-amber-500/10 overflow-hidden">
        {/* Header */}
        <div className="bg-amber-500/20 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            <span className="font-semibold text-amber-100">
              Schema Drift Detectado
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs bg-amber-500/30 px-2 py-1 rounded-full text-amber-200">
              {drifts.length} mudanças
            </span>
            {onDismiss && (
              <button onClick={onDismiss} className="p-1 hover:bg-amber-500/30 rounded transition-colors">
                <X className="w-4 h-4 text-amber-300" />
              </button>
            )}
          </div>
        </div>

        {/* Critical Alert */}
        {criticalCount > 0 && (
          <div className="bg-red-500/20 px-4 py-2 border-b border-red-500/30">
            <p className="text-red-300 text-sm">
              ⚠️ {criticalCount} mudança(s) crítica(s) podem quebrar métricas
            </p>
          </div>
        )}

        {/* Drift List */}
        <div className="max-h-96 overflow-y-auto">
          <AnimatePresence mode="popLayout">
            {drifts.map((drift, index) => {
              const config = DRIFT_LABELS[drift.type];
              
              return (
                <motion.div
                  key={`${drift.entity}-${drift.column}`}
                  layout
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 10 }}
                  transition={{ delay: index * 0.05 }}
                  className="p-4 border-b border-surface-700 last:border-0"
                >
                  <div className="flex items-start gap-3">
                    <div className={`p-2 rounded-lg bg-${config.color}-500/20`}>
                      {DRIFT_ICONS[drift.type]}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-xs px-2 py-0.5 rounded-full 
                                         bg-${config.color}-500/20 text-${config.color}-400`}>
                          {config.label}
                        </span>
                        {drift.impact === 'critical' && (
                          <span className="text-xs px-2 py-0.5 rounded-full 
                                          bg-red-500/20 text-red-400">
                            Crítico
                          </span>
                        )}
                      </div>
                      <p className="text-text-white text-sm mt-1">
                        <code className="bg-surface-700 px-1.5 py-0.5 rounded text-xs">
                          {drift.entity}.{drift.column}
                        </code>
                      </p>
                      <p className="text-text-muted text-xs mt-1">
                        {drift.suggestion}
                      </p>
                      
                      {drift.affected_metrics.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {drift.affected_metrics.map(m => (
                            <span key={m} className="text-xs px-1.5 py-0.5 
                                                    bg-red-500/10 text-red-400 rounded">
                              {m}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2 mt-3 ml-11">
                    <button 
                      onClick={() => handleAction(drift, 'accept')}
                      className="text-xs px-3 py-1.5 rounded-lg bg-emerald-500/20 
                                text-emerald-400 hover:bg-emerald-500/30 transition-colors"
                    >
                      Aceitar
                    </button>
                    <button 
                      onClick={() => handleAction(drift, 'ignore')}
                      className="text-xs px-3 py-1.5 rounded-lg bg-surface-700 
                                text-text-muted hover:bg-surface-600 transition-colors"
                    >
                      Ignorar
                    </button>
                    <button 
                      onClick={() => handleAction(drift, 'reject')}
                      className="text-xs px-3 py-1.5 rounded-lg bg-red-500/20 
                                text-red-400 hover:bg-red-500/30 transition-colors"
                    >
                      Rejeitar
                    </button>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>

        {/* Footer Actions */}
        <div className="bg-surface-900 px-4 py-3 flex justify-between">
          <button className="text-xs text-text-muted hover:text-text-secondary transition-colors">
            Ver Schema Completo
          </button>
          <button 
            className="text-xs px-3 py-1.5 rounded-lg bg-brand-500 
                      text-white hover:bg-brand-600 transition-colors"
            onClick={() => {
              drifts.filter(d => d.impact !== 'critical').forEach(d => handleAction(d, 'accept'));
            }}
          >
            Aceitar Todas ({drifts.filter(d => d.impact !== 'critical').length})
          </button>
        </div>
      </div>
    </motion.div>
  );
}

export default SchemaDriftAlert;

