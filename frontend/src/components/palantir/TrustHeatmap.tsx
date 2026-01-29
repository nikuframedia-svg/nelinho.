/**
 * TrustHeatmap — Visual trust index heatmap
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 * 
 * "See data quality like X-ray vision"
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, TrendingUp, Wrench, Copy, AlertTriangle } from 'lucide-react';
import type { TrustCell } from '@/types';

interface TrustHeatmapProps {
  data: TrustCell[][];
  onCellClick?: (cell: TrustCell) => void;
}

const TRUST_COLORS = {
  high: { bg: 'bg-emerald-500', text: 'text-emerald-100', border: 'border-emerald-500/30' },
  medium: { bg: 'bg-amber-500', text: 'text-amber-100', border: 'border-amber-500/30' },
  low: { bg: 'bg-orange-500', text: 'text-orange-100', border: 'border-orange-500/30' },
  critical: { bg: 'bg-red-500', text: 'text-red-100', border: 'border-red-500/30' },
};

function getTrustLevel(trust: number): keyof typeof TRUST_COLORS {
  if (trust >= 80) return 'high';
  if (trust >= 60) return 'medium';
  if (trust >= 40) return 'low';
  return 'critical';
}

function CellDetailModal({ cell, onClose }: { cell: TrustCell; onClose: () => void }) {
  const level = getTrustLevel(cell.trust_index);
  const colors = TRUST_COLORS[level];

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
        {/* Header */}
        <div className={`${colors.bg}/20 px-6 py-4 border-b ${colors.border}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`text-3xl font-bold ${colors.text.replace('100', '400')}`}>
                {cell.trust_index}%
              </div>
              <div>
                <h3 className="text-lg font-semibold text-text-white">
                  {cell.entity}.{cell.field}
                </h3>
                <p className="text-sm text-text-muted">Trust Index</p>
              </div>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-surface-700 rounded-lg transition-colors">
              <X className="w-5 h-5 text-text-muted" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Coverage Stats */}
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-3 bg-surface-900 rounded-lg">
              <div className="text-2xl font-bold text-text-white">{cell.coverage_pct.toFixed(1)}%</div>
              <div className="text-xs text-text-muted">Coverage</div>
            </div>
            <div className="text-center p-3 bg-surface-900 rounded-lg">
              <div className="text-2xl font-bold text-red-400">{cell.null_pct.toFixed(1)}%</div>
              <div className="text-xs text-text-muted">Nulls</div>
            </div>
            <div className="text-center p-3 bg-surface-900 rounded-lg">
              <div className="text-2xl font-bold text-amber-400">{cell.zero_pct.toFixed(1)}%</div>
              <div className="text-xs text-text-muted">Zeros</div>
            </div>
          </div>

          {/* Impact */}
          {cell.impact.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text-muted mb-2 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                Impacto
              </h4>
              <div className="space-y-1">
                {cell.impact.map((impact, i) => (
                  <p key={i} className="text-sm text-text-secondary">• {impact}</p>
                ))}
              </div>
            </div>
          )}

          {/* Blocked Metrics */}
          {cell.blocked_metrics.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text-muted mb-2">Métricas Bloqueadas</h4>
              <div className="flex flex-wrap gap-2">
                {cell.blocked_metrics.map((metric, i) => (
                  <span key={i} className="text-xs px-2 py-1 rounded-full bg-red-500/20 text-red-400">
                    {metric}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* How to Improve */}
          {cell.how_to_improve.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text-muted mb-2 flex items-center gap-2">
                <Wrench className="w-4 h-4 text-brand-400" />
                Como Melhorar
              </h4>
              <ol className="space-y-2">
                {cell.how_to_improve.map((step, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm text-text-secondary">
                    <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-500/20 
                                    text-brand-400 text-xs flex items-center justify-center">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-surface-900 flex justify-between">
          <button className="text-sm text-text-muted hover:text-text-secondary transition-colors flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            Ver Evolução
          </button>
          <div className="flex gap-2">
            <button className="text-sm px-4 py-2 rounded-lg bg-surface-700 text-text-secondary 
                              hover:bg-surface-600 transition-colors flex items-center gap-2">
              <Copy className="w-4 h-4" />
              Copiar Diagnóstico
            </button>
            <button className="text-sm px-4 py-2 rounded-lg bg-brand-500 text-white 
                              hover:bg-brand-600 transition-colors">
              Abrir Ticket
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

export function TrustHeatmap({ data, onCellClick }: TrustHeatmapProps) {
  const [selectedCell, setSelectedCell] = useState<TrustCell | null>(null);

  if (!data || data.length === 0) {
    return (
      <div className="bg-surface-800 rounded-xl p-8 text-center">
        <p className="text-text-muted">A carregar dados de qualidade...</p>
      </div>
    );
  }

  const headers = ['Completude', 'Precisão', 'Freshness', 'Overall'];

  return (
    <div className="bg-surface-800 rounded-2xl p-6 border border-surface-700">
      <h3 className="text-lg font-semibold text-text-white mb-6 flex items-center gap-2">
        🔍 Trust Heatmap
        <span className="text-xs px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-400">
          Data Quality
        </span>
      </h3>

      {/* Grid */}
      <div className="overflow-x-auto">
        <div className="grid gap-2" style={{ 
          gridTemplateColumns: `180px repeat(${headers.length}, 1fr)`,
          minWidth: '600px'
        }}>
          {/* Header Row */}
          <div className="text-text-muted text-sm font-medium p-2">Entidade</div>
          {headers.map(header => (
            <div key={header} className="text-text-muted text-sm font-medium p-2 text-center">
              {header}
            </div>
          ))}

          {/* Data Rows */}
          {data.map((row, rowIndex) => (
            <div key={`row-${rowIndex}`} className="contents">
              <div className="text-text-primary text-sm p-2 
                              flex items-center font-medium">
                {row[0]?.entity}
              </div>
              {row.map((cell, cellIndex) => {
                const level = getTrustLevel(cell.trust_index);
                const colors = TRUST_COLORS[level];
                
                return (
                  <motion.button
                    key={`cell-${rowIndex}-${cellIndex}`}
                    className={`${colors.bg} rounded-lg p-3 text-center cursor-pointer 
                               transition-all hover:scale-105 hover:shadow-lg hover:shadow-${level === 'high' ? 'emerald' : level === 'medium' ? 'amber' : level === 'low' ? 'orange' : 'red'}-500/20`}
                    onClick={() => {
                      setSelectedCell(cell);
                      onCellClick?.(cell);
                    }}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: (rowIndex * 4 + cellIndex) * 0.03 }}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <span className={`text-lg font-bold ${colors.text}`}>
                      {cell.trust_index}%
                    </span>
                  </motion.button>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 mt-6 justify-center">
        {Object.entries(TRUST_COLORS).map(([level, colors]) => (
          <div key={level} className="flex items-center gap-2">
            <div className={`w-4 h-4 rounded ${colors.bg}`} />
            <span className="text-text-muted text-sm capitalize">
              {level === 'high' ? '>80%' : level === 'medium' ? '60-80%' : level === 'low' ? '40-60%' : '<40%'}
            </span>
          </div>
        ))}
      </div>

      {/* Detail Modal */}
      <AnimatePresence>
        {selectedCell && (
          <CellDetailModal cell={selectedCell} onClose={() => setSelectedCell(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}

export default TrustHeatmap;

