/**
 * BlockedMetricsWall — Visual wall of blocked metrics
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 * 
 * "We don't hide what we don't know. We show it clearly."
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, Unlock, FileText, Ticket, X, ArrowRight } from 'lucide-react';
import type { BlockedMetric } from '@/types';
import { useBlockedMetricsWall } from '@/hooks';

interface BlockedMetricsWallProps {
  compact?: boolean;
  maxItems?: number;
}

function MetricDetailModal({ metric, onClose }: { metric: BlockedMetric; onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 
                 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, y: 20 }}
        className="bg-surface-800 rounded-2xl max-w-lg w-full overflow-hidden
                  border border-surface-600 shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="bg-red-500/10 px-6 py-4 border-b border-red-500/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <Lock className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-text-white">
                  {metric.name_pt}
                </h3>
                <p className="text-sm text-red-400">🔒 BLOQUEADA</p>
              </div>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-surface-700 rounded-lg">
              <X className="w-5 h-5 text-text-muted" />
            </button>
          </div>
        </div>

        {/* Modal Content */}
        <div className="p-6 space-y-6">
          {/* Reason */}
          <div>
            <h4 className="text-sm font-medium text-text-muted mb-2">
              Por que está bloqueada:
            </h4>
            <p className="text-text-secondary">{metric.reason}</p>
          </div>

          {/* Required Data */}
          <div>
            <h4 className="text-sm font-medium text-text-muted mb-2">
              Dados necessários:
            </h4>
            <div className="space-y-2">
              {metric.required_data.map(data => (
                <div key={data.field} className="flex items-center gap-3 
                                                  p-3 bg-surface-900 rounded-lg">
                  <span className={`text-lg ${
                    data.status === 'missing' ? 'text-red-400' :
                    data.status === 'partial' ? 'text-amber-400' :
                    'text-emerald-400'
                  }`}>
                    {data.status === 'missing' ? '❌' :
                     data.status === 'partial' ? '⚠️' : '✅'}
                  </span>
                  <div className="flex-1">
                    <code className="text-sm text-text-white">{data.field}</code>
                    <div className="h-1.5 bg-surface-700 rounded-full mt-1">
                      <motion.div 
                        className={`h-full rounded-full ${
                          data.coverage === 0 ? 'bg-red-500' :
                          data.coverage < 50 ? 'bg-amber-500' :
                          'bg-emerald-500'
                        }`}
                        initial={{ width: 0 }}
                        animate={{ width: `${data.coverage}%` }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                  </div>
                  <span className="text-xs text-text-muted">
                    {data.coverage}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* How to Unlock */}
          {metric.how_to_unlock.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text-muted mb-2">
                Como desbloquear:
              </h4>
              <ol className="space-y-2">
                {metric.how_to_unlock.map((step, i) => (
                  <li key={i} className="flex items-start gap-3 text-text-secondary">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-500/20 
                                    text-brand-400 text-sm flex items-center justify-center">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Alternative */}
          {metric.alternative && (
            <div className="p-4 bg-emerald-500/10 rounded-xl border border-emerald-500/20">
              <div className="flex items-center gap-2 mb-2">
                <Unlock className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-medium text-emerald-400">
                  Alternativa Disponível
                </span>
              </div>
              <p className="text-text-white">
                {metric.alternative.name}
              </p>
              <p className="text-xs text-text-muted mt-1">
                Trust Index: {metric.alternative.trust_index}%
              </p>
              <button className="mt-3 text-sm text-emerald-400 hover:text-emerald-300 
                               flex items-center gap-1 transition-colors">
                Ver métrica alternativa
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-surface-900 flex justify-between">
          <button 
            onClick={onClose}
            className="text-sm text-text-muted hover:text-text-secondary transition-colors"
          >
            Fechar
          </button>
          <div className="flex gap-2">
            <button className="text-sm px-4 py-2 rounded-lg bg-surface-700 
                              text-text-secondary hover:bg-surface-600 
                              transition-colors flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Exportar Spec
            </button>
            <button className="text-sm px-4 py-2 rounded-lg bg-brand-500 
                              text-white hover:bg-brand-600 
                              transition-colors flex items-center gap-2">
              <Ticket className="w-4 h-4" />
              Criar Ticket IT
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

export function BlockedMetricsWall({ compact = false, maxItems }: BlockedMetricsWallProps) {
  const { metrics, loading } = useBlockedMetricsWall();
  const [selectedMetric, setSelectedMetric] = useState<BlockedMetric | null>(null);

  const displayMetrics = maxItems ? metrics.slice(0, maxItems) : metrics;

  if (loading) {
    return (
      <div className="bg-surface-800 rounded-2xl border border-red-500/20 p-6 animate-pulse">
        <div className="h-8 w-48 bg-surface-700 rounded mb-4" />
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-24 bg-surface-700 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (metrics.length === 0) {
    return (
      <div className="bg-surface-800 rounded-2xl border border-emerald-500/20 p-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/20 rounded-lg">
            <Unlock className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-text-white">
              Todas as métricas disponíveis!
            </h3>
            <p className="text-sm text-text-muted">
              Não há métricas bloqueadas neste momento.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface-800 rounded-2xl border border-red-500/20 overflow-hidden">
      {/* Header */}
      <div className="bg-red-500/10 px-6 py-4 border-b border-red-500/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/20 rounded-lg">
              <Lock className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text-white">
                Métricas Bloqueadas
              </h3>
              <p className="text-sm text-text-muted">
                {metrics.length} métricas não disponíveis com dados actuais
              </p>
            </div>
          </div>
          <span className="text-3xl font-bold text-red-400">
            {metrics.length}
          </span>
        </div>
      </div>

      {/* Grid of Blocked Metrics */}
      <div className="p-6">
        <div className={`grid gap-3 ${compact ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4'}`}>
          {displayMetrics.map((metric, index) => (
            <motion.button
              key={metric.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.05 }}
              onClick={() => setSelectedMetric(metric)}
              className="relative p-4 bg-surface-900/50 rounded-xl border border-surface-700
                        hover:border-red-500/50 transition-all group text-left overflow-hidden"
            >
              {/* Blocked Pattern Overlay */}
              <div 
                className="absolute inset-0 opacity-5 pointer-events-none"
                style={{
                  backgroundImage: `repeating-linear-gradient(
                    45deg,
                    transparent,
                    transparent 10px,
                    rgba(239, 68, 68, 0.5) 10px,
                    rgba(239, 68, 68, 0.5) 20px
                  )`
                }}
              />
              
              <div className="relative">
                <Lock className="w-4 h-4 text-red-400 mb-2" />
                <p className="text-sm font-medium text-text-white group-hover:text-red-300 
                             transition-colors line-clamp-2">
                  {metric.name_pt}
                </p>
                <p className="text-xs text-text-muted mt-1 line-clamp-1">
                  {metric.reason.substring(0, 40)}...
                </p>
                {metric.alternative && (
                  <div className="mt-2 flex items-center gap-1 text-xs text-emerald-400">
                    <Unlock className="w-3 h-3" />
                    Alternativa
                  </div>
                )}
              </div>
            </motion.button>
          ))}
        </div>

        {maxItems && metrics.length > maxItems && (
          <div className="mt-4 text-center">
            <button className="text-sm text-brand-400 hover:text-brand-300 transition-colors">
              Ver todas as {metrics.length} métricas bloqueadas →
            </button>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      <AnimatePresence>
        {selectedMetric && (
          <MetricDetailModal metric={selectedMetric} onClose={() => setSelectedMetric(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}

export default BlockedMetricsWall;

