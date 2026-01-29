/**
 * QuarantineCenter — Data quarantine command center
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 * 
 * "Problematic data never contaminates decisions"
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  AlertTriangle, CheckCircle, Trash2, Eye, Wand2, Clock, 
  TrendingDown, X, Shield 
} from 'lucide-react';
import type { QuarantinedRow } from '@/types';
import { useQuarantine } from '@/hooks';

const SEVERITY_CONFIG: Record<string, { icon: string; color: string; label: string; bgClass: string; borderClass: string }> = {
  critical: { icon: '🔴', color: 'red', label: 'Crítico', bgClass: 'bg-red-500/10', borderClass: 'border-red-500/30' },
  high: { icon: '🟠', color: 'orange', label: 'Alto', bgClass: 'bg-orange-500/10', borderClass: 'border-orange-500/30' },
  medium: { icon: '🟡', color: 'amber', label: 'Médio', bgClass: 'bg-amber-500/10', borderClass: 'border-amber-500/30' },
  low: { icon: '🟢', color: 'emerald', label: 'Baixo', bgClass: 'bg-emerald-500/10', borderClass: 'border-emerald-500/30' },
};

// Default config for unknown severities
const DEFAULT_SEVERITY_CONFIG = { 
  icon: '⚪', 
  color: 'gray', 
  label: 'Desconhecido', 
  bgClass: 'bg-gray-500/10', 
  borderClass: 'border-gray-500/30' 
};

// Helper to get severity config with fallback
const getSeverityConfig = (severity: string) => SEVERITY_CONFIG[severity] || DEFAULT_SEVERITY_CONFIG;

interface ResolveModalProps {
  row: QuarantinedRow;
  onClose: () => void;
  onResolve: (resolution: { type: 'fix' | 'override' | 'discard'; justification: string }) => void;
}

function ResolveModal({ row, onClose, onResolve }: ResolveModalProps) {
  const [type, setType] = useState<'fix' | 'override' | 'discard'>('override');
  const [justification, setJustification] = useState('');
  const config = getSeverityConfig(row.severity);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, y: 20 }}
        className="bg-surface-800 rounded-2xl max-w-lg w-full overflow-hidden border border-surface-600 shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <div className={`${config.bgClass} px-6 py-4 border-b ${config.borderClass}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-2xl">{config.icon}</span>
              <div>
                <h3 className="text-lg font-semibold text-text-white">
                  Resolver {row.entity} #{row.entity_id}
                </h3>
                <p className="text-sm text-text-muted">{row.reason}</p>
              </div>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-surface-700 rounded-lg">
              <X className="w-5 h-5 text-text-muted" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Resolution Type */}
          <div>
            <h4 className="text-sm font-medium text-text-muted mb-3">Tipo de resolução:</h4>
            <div className="space-y-2">
              {[
                { value: 'fix', label: 'Corrigir dados (abrir ERP)', icon: Wand2 },
                { value: 'override', label: 'Aceitar com override (explicar porquê)', icon: CheckCircle },
                { value: 'discard', label: 'Descartar row (não usar em cálculos)', icon: Trash2 },
              ].map(option => (
                <label
                  key={option.value}
                  className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all
                             ${type === option.value 
                               ? 'bg-brand-500/20 border border-brand-500/50' 
                               : 'bg-surface-900 border border-surface-700 hover:border-surface-600'}`}
                >
                  <input
                    type="radio"
                    name="resolution-type"
                    value={option.value}
                    checked={type === option.value}
                    onChange={() => setType(option.value as typeof type)}
                    className="hidden"
                  />
                  <option.icon className={`w-5 h-5 ${type === option.value ? 'text-brand-400' : 'text-text-muted'}`} />
                  <span className={type === option.value ? 'text-text-white' : 'text-text-secondary'}>
                    {option.label}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Justification */}
          <div>
            <label className="text-sm font-medium text-text-muted block mb-2">
              Justificação:
            </label>
            <textarea
              value={justification}
              onChange={e => setJustification(e.target.value)}
              placeholder="Explique a razão desta resolução..."
              className="w-full bg-surface-900 border border-surface-600 rounded-lg px-4 py-3
                        text-text-white placeholder:text-text-muted resize-none h-24
                        focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-all"
            />
          </div>

          {/* Warning */}
          <div className="flex items-start gap-3 p-3 bg-amber-500/10 rounded-lg border border-amber-500/20">
            <Shield className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-amber-200">Esta acção será registada no audit log</p>
              <p className="text-xs text-amber-400/70 mt-1">Resolvido por: Nelinho</p>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 bg-surface-900 flex justify-between">
          <button 
            onClick={onClose}
            className="px-4 py-2 text-text-muted hover:text-text-secondary transition-colors"
          >
            Cancelar
          </button>
          <button 
            onClick={() => onResolve({ type, justification })}
            disabled={!justification.trim()}
            className="px-6 py-2 bg-brand-500 text-white rounded-lg font-medium
                      disabled:opacity-50 disabled:cursor-not-allowed
                      hover:bg-brand-600 transition-colors"
          >
            Confirmar Resolução
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

function StatCard({ icon, value, label, trend }: { 
  icon: React.ReactNode; 
  value: string | number; 
  label: string;
  trend?: string;
}) {
  return (
    <div className="bg-surface-900 rounded-xl p-4 flex items-center gap-4">
      <div className="p-3 bg-surface-800 rounded-lg">
        {icon}
      </div>
      <div>
        <div className="text-2xl font-bold text-text-white">{value}</div>
        <div className="text-xs text-text-muted">{label}</div>
        {trend && <div className="text-xs text-emerald-400">{trend}</div>}
      </div>
    </div>
  );
}

export function QuarantineCenter() {
  const { rows = [], stats, loading, resolveRow, autoFix } = useQuarantine();
  const [selectedRow, setSelectedRow] = useState<QuarantinedRow | null>(null);
  const [viewingRow, setViewingRow] = useState<QuarantinedRow | null>(null);

  // Default stats if undefined
  const safeStats = stats || { critical: 0, high: 0, medium: 0, low: 0, avgDays: 0 };

  if (loading) {
    return (
      <div className="bg-surface-800 rounded-2xl p-6 border border-surface-700 animate-pulse">
        <div className="h-8 w-48 bg-surface-700 rounded mb-6" />
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 bg-surface-700 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface-800 rounded-2xl border border-surface-700 overflow-hidden">
      {/* Header */}
      <div className="bg-red-500/10 px-6 py-4 border-b border-red-500/20 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-red-500/20 rounded-lg">
            <Shield className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-text-white">Quarantine Center</h3>
            <p className="text-sm text-text-muted">{rows.length} rows em quarentena</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">Auto-Resolve:</span>
          <button className="px-3 py-1 rounded-lg bg-surface-700 text-text-secondary text-sm">
            ON
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="p-6">
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard 
            icon={<AlertTriangle className="w-5 h-5 text-red-400" />}
            value={safeStats.critical}
            label="Críticos"
          />
          <StatCard 
            icon={<Clock className="w-5 h-5 text-amber-400" />}
            value={`${safeStats.avgDays.toFixed(1)} dias`}
            label="Tempo médio em quarentena"
          />
          <StatCard 
            icon={<TrendingDown className="w-5 h-5 text-emerald-400" />}
            value="-15%"
            label="vs. semana passada"
          />
        </div>

        {/* Quarantine List */}
        <div className="space-y-3">
          <AnimatePresence mode="popLayout">
            {rows.map((row, index) => {
              const config = getSeverityConfig(row.severity);
              
              return (
                <motion.div
                  key={row.id}
                  layout
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20, scale: 0.9 }}
                  transition={{ delay: index * 0.05 }}
                  className={`${config.bgClass} rounded-xl border ${config.borderClass}
                             p-4 hover:border-opacity-70 transition-all`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <span className="text-2xl">{config.icon}</span>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs px-2 py-0.5 rounded-full 
                                          bg-${config.color}-500/20 text-${config.color}-400`}>
                            {config.label}
                          </span>
                          <span className="text-text-white font-medium">
                            {row.entity} #{row.entity_id}
                          </span>
                        </div>
                        <p className="text-text-muted text-sm mt-1">{row.reason}</p>
                        {row.suggestion && (
                          <p className="text-brand-400 text-xs mt-1">💡 {row.suggestion}</p>
                        )}
                        <p className="text-text-secondary text-xs mt-2">
                          Detectado: {new Date(row.detected_at).toLocaleString('pt-PT')}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {row.can_auto_fix && (
                        <motion.button
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          className="p-2 rounded-lg bg-brand-500/20 text-brand-400 
                                    hover:bg-brand-500/30 transition-colors"
                          onClick={() => autoFix(row.id)}
                          title="Auto-fix"
                        >
                          <Wand2 className="w-4 h-4" />
                        </motion.button>
                      )}
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className="p-2 rounded-lg bg-surface-700 text-text-muted 
                                  hover:bg-surface-600 transition-colors"
                        onClick={() => setViewingRow(row)}
                        title="Ver dados"
                      >
                        <Eye className="w-4 h-4" />
                      </motion.button>
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400 
                                  hover:bg-emerald-500/30 transition-colors"
                        onClick={() => setSelectedRow(row)}
                        title="Resolver"
                      >
                        <CheckCircle className="w-4 h-4" />
                      </motion.button>
                    </div>
                  </div>

                  {/* Impact Tags */}
                  {row.impact && row.impact.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3 ml-11">
                      {row.impact.map((impact, i) => (
                        <span key={i} className="text-xs px-2 py-1 rounded-md 
                                                bg-red-500/10 text-red-400">
                          ⚠️ {impact}
                        </span>
                      ))}
                    </div>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>

          {rows.length === 0 && (
            <div className="text-center py-12">
              <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
              <p className="text-text-white font-medium">Quarentena vazia!</p>
              <p className="text-text-muted text-sm">Todos os dados estão validados.</p>
            </div>
          )}
        </div>
      </div>

      {/* Resolve Modal */}
      <AnimatePresence>
        {selectedRow && (
          <ResolveModal
            row={selectedRow}
            onClose={() => setSelectedRow(null)}
            onResolve={async (resolution) => {
              await resolveRow(selectedRow.id, resolution);
              setSelectedRow(null);
            }}
          />
        )}
      </AnimatePresence>

      {/* View Data Modal */}
      <AnimatePresence>
        {viewingRow && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => setViewingRow(null)}
          >
            <motion.div
              initial={{ scale: 0.9 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.9 }}
              className="bg-surface-800 rounded-2xl max-w-lg w-full overflow-hidden border border-surface-600"
              onClick={e => e.stopPropagation()}
            >
              <div className="px-6 py-4 border-b border-surface-700 flex justify-between items-center">
                <h3 className="text-lg font-semibold text-text-white">
                  Dados: {viewingRow.entity} #{viewingRow.entity_id}
                </h3>
                <button onClick={() => setViewingRow(null)} className="p-2 hover:bg-surface-700 rounded-lg">
                  <X className="w-5 h-5 text-text-muted" />
                </button>
              </div>
              <div className="p-6">
                <pre className="bg-surface-900 rounded-lg p-4 text-sm text-text-secondary overflow-auto max-h-96">
                  {JSON.stringify(viewingRow.raw_data, null, 2)}
                </pre>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default QuarantineCenter;

