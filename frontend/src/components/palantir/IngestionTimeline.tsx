/**
 * IngestionTimeline — Data ingestion history timeline
 * Part of TIER 2: OPERATIONAL EXCELLENCE
 * 
 * "Every byte has a story. We make that story visible."
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { RotateCcw, Clock, AlertTriangle, FileSpreadsheet } from 'lucide-react';
import type { Ingestion, RollbackImpact } from '@/types';
import { useIngestions } from '@/hooks';

function RollbackModal({ 
  target, 
  current, 
  impact,
  onConfirm, 
  onCancel 
}: { 
  target: Ingestion;
  current: Ingestion;
  impact: RollbackImpact | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [confirmText, setConfirmText] = useState('');

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
      onClick={onCancel}
    >
      <motion.div 
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        exit={{ scale: 0.9 }}
        className="bg-surface-800 rounded-2xl max-w-2xl w-full border border-red-500/30"
        onClick={e => e.stopPropagation()}
      >
        {/* Warning Header */}
        <div className="bg-red-500/20 p-6 rounded-t-2xl">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-red-500/30 rounded-xl">
              <AlertTriangle className="w-8 h-8 text-red-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-text-white">
                Confirmar Rollback
              </h2>
              <p className="text-red-300">
                Esta acção vai reverter o sistema para uma versão anterior
              </p>
            </div>
          </div>
        </div>

        {/* Comparison */}
        <div className="p-6 grid grid-cols-2 gap-6">
          <div className="p-4 bg-red-500/10 rounded-xl border border-red-500/20">
            <h4 className="text-sm text-red-400 font-medium mb-2">ACTUAL (será perdido)</h4>
            <p className="text-text-white">{current.filename}</p>
            <p className="text-text-muted text-sm">
              {current.row_count.toLocaleString()} rows
            </p>
          </div>
          <div className="p-4 bg-emerald-500/10 rounded-xl border border-emerald-500/20">
            <h4 className="text-sm text-emerald-400 font-medium mb-2">DESTINO</h4>
            <p className="text-text-white">{target.filename}</p>
            <p className="text-text-muted text-sm">
              {target.row_count.toLocaleString()} rows
            </p>
          </div>
        </div>

        {/* Impact Analysis */}
        {impact && (
          <div className="px-6 pb-6">
            <h4 className="text-sm text-text-muted mb-2">Impacto estimado:</h4>
            <div className="space-y-2">
              <div className="flex items-center justify-between p-3 bg-surface-900 rounded-lg">
                <span className="text-text-secondary">📉 Rows que serão perdidos</span>
                <span className="text-red-400 font-medium">{impact.rows_lost.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-surface-900 rounded-lg">
                <span className="text-text-secondary">📊 Métricas afectadas</span>
                <span className="text-amber-400 font-medium">{impact.metrics_affected}</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-surface-900 rounded-lg">
                <span className="text-text-secondary">⏱️ Idade dos dados</span>
                <span className="text-text-white">{impact.data_age}</span>
              </div>
            </div>
          </div>
        )}

        {/* Confirmation Input */}
        <div className="px-6 pb-6">
          <label className="text-sm text-text-muted">
            Escreva <code className="bg-surface-700 px-1.5 py-0.5 rounded">ROLLBACK</code> para confirmar:
          </label>
          <input 
            value={confirmText}
            onChange={e => setConfirmText(e.target.value)}
            className="mt-2 w-full bg-surface-900 border border-surface-600 rounded-lg 
                      px-4 py-3 text-text-white focus:border-red-500 focus:ring-1 
                      focus:ring-red-500 transition-all"
            placeholder="ROLLBACK"
          />
        </div>

        {/* Actions */}
        <div className="px-6 py-4 bg-surface-900 rounded-b-2xl flex justify-between">
          <button 
            onClick={onCancel}
            className="px-4 py-2 text-text-muted hover:text-text-secondary transition-colors"
          >
            Cancelar
          </button>
          <button 
            onClick={onConfirm}
            disabled={confirmText !== 'ROLLBACK'}
            className="px-6 py-2 bg-red-500 text-white rounded-lg font-medium
                      disabled:opacity-50 disabled:cursor-not-allowed
                      hover:bg-red-600 transition-colors"
          >
            Executar Rollback
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="text-center">
      <div className="text-text-white font-medium">{value}</div>
      <div className="text-xs text-text-muted">{label}</div>
    </div>
  );
}

export function IngestionTimeline() {
  const { ingestions, activeIngestion, loading, fetchRollbackImpact, rollback } = useIngestions();
  const [rollbackTarget, setRollbackTarget] = useState<Ingestion | null>(null);
  const [rollbackImpact, setRollbackImpact] = useState<RollbackImpact | null>(null);

  const handleOpenRollback = async (ing: Ingestion) => {
    setRollbackTarget(ing);
    const impact = await fetchRollbackImpact(ing.id);
    setRollbackImpact(impact);
  };

  const handleConfirmRollback = async () => {
    if (rollbackTarget) {
      await rollback(rollbackTarget.id);
      setRollbackTarget(null);
      setRollbackImpact(null);
    }
  };

  if (loading) {
    return (
      <div className="bg-surface-800 rounded-2xl p-6 border border-surface-700 animate-pulse">
        <div className="h-8 w-48 bg-surface-700 rounded mb-6" />
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-32 bg-surface-700 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface-800 rounded-2xl border border-surface-700 overflow-hidden">
      <div className="px-6 py-4 border-b border-surface-700">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-brand-500/20 rounded-lg">
            <FileSpreadsheet className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-text-white">Ingestion Timeline</h3>
            <p className="text-sm text-text-muted">{ingestions.length} ingestions registadas</p>
          </div>
        </div>
      </div>

      <div className="p-6">
        <div className="relative">
          {/* Vertical Line */}
          <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-surface-700" />
          
          {ingestions.map((ing, i) => (
            <motion.div
              key={ing.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.1 }}
              className="relative pl-14 pb-8 last:pb-0"
            >
              {/* Status Dot */}
              <div className={`absolute left-3 w-4 h-4 rounded-full border-4 
                             ${ing.status === 'active' 
                               ? 'bg-emerald-500 border-emerald-500/30' 
                               : ing.status === 'superseded' 
                               ? 'bg-surface-600 border-surface-500' 
                               : 'bg-amber-500 border-amber-500/30'}`}
              />
              
              {/* Content Card */}
              <div className={`p-4 rounded-xl transition-all ${
                ing.status === 'active' 
                  ? 'bg-surface-900 border border-emerald-500/30' 
                  : 'bg-surface-900/50 border border-surface-700 hover:border-surface-600'
              }`}>
                <div className="flex items-center justify-between">
                  <div>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      ing.status === 'active' 
                        ? 'bg-emerald-500/20 text-emerald-400' 
                        : 'bg-surface-700 text-text-muted'
                    }`}>
                      {ing.status === 'active' ? '✓ Activo' : 'Superseded'}
                    </span>
                    <p className="text-text-white font-medium mt-2 flex items-center gap-2">
                      <FileSpreadsheet className="w-4 h-4 text-text-muted" />
                      {ing.filename}
                    </p>
                    <p className="text-text-muted text-sm flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(ing.timestamp).toLocaleString('pt-PT')}
                    </p>
                  </div>
                  
                  {/* Quality Badge */}
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${
                      ing.quality_score >= 80 ? 'text-emerald-400' :
                      ing.quality_score >= 60 ? 'text-amber-400' : 'text-red-400'
                    }`}>
                      {ing.quality_score}%
                    </div>
                    <span className="text-xs text-text-muted">Quality</span>
                  </div>
                </div>
                
                {/* Stats Row */}
                <div className="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-surface-700">
                  <Stat label="Rows" value={ing.row_count.toLocaleString()} />
                  <Stat label="Tabelas" value={ing.table_count} />
                  <Stat label="Erros" value={ing.error_count} />
                  <Stat label="Warnings" value={ing.warning_count} />
                </div>
                
                {/* Actions */}
                {ing.status !== 'active' && (
                  <button 
                    className="mt-4 text-sm text-brand-400 hover:text-brand-300 
                              flex items-center gap-1 transition-colors"
                    onClick={() => handleOpenRollback(ing)}
                  >
                    <RotateCcw className="w-4 h-4" />
                    Rollback para esta versão
                  </button>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Rollback Modal */}
      <AnimatePresence>
        {rollbackTarget && activeIngestion && (
          <RollbackModal
            target={rollbackTarget}
            current={activeIngestion}
            impact={rollbackImpact}
            onConfirm={handleConfirmRollback}
            onCancel={() => {
              setRollbackTarget(null);
              setRollbackImpact(null);
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

export default IngestionTimeline;

