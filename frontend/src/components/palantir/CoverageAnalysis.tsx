/**
 * CoverageAnalysis — Table coverage analysis visualization
 * Part of TIER 3: ENTERPRISE EXCELLENCE
 * 
 * "The Data Completeness Map"
 */

import { motion } from 'framer-motion';
import { Database, AlertCircle, CheckCircle } from 'lucide-react';
import { useCoverageAnalysis } from '@/hooks';

function CoverageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {[1, 2, 3].map(i => (
        <div key={i} className="bg-surface-800 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-surface-700">
            <div className="h-6 w-48 bg-surface-700 rounded" />
          </div>
          <div className="p-4 grid grid-cols-4 gap-3">
            {[1, 2, 3, 4].map(j => (
              <div key={j} className="h-24 bg-surface-700 rounded-lg" />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function CoverageAnalysis() {
  const { coverage, loading, error } = useCoverageAnalysis();

  if (loading) return <CoverageSkeleton />;

  if (error) {
    return (
      <div className="bg-surface-800 rounded-xl p-8 text-center">
        <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <p className="text-text-white">Erro ao carregar análise de coverage</p>
        <p className="text-text-muted text-sm">{error.message}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {coverage.map((table, tableIndex) => (
        <motion.div 
          key={table.name} 
          className="bg-surface-800 rounded-xl overflow-hidden border border-surface-700"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: tableIndex * 0.1 }}
        >
          {/* Table Header */}
          <div className="p-4 border-b border-surface-700 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-brand-500/20 rounded-lg">
                <Database className="w-5 h-5 text-brand-400" />
              </div>
              <div>
                <h3 className="text-text-white font-medium">{table.name}</h3>
                <p className="text-xs text-text-muted">
                  {table.row_count.toLocaleString()} rows
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className={`text-2xl font-bold ${
                  table.overall_coverage >= 80 ? 'text-emerald-400' :
                  table.overall_coverage >= 60 ? 'text-amber-400' : 'text-red-400'
                }`}>
                  {table.overall_coverage.toFixed(1)}%
                </div>
                <div className="text-xs text-text-muted">Overall Coverage</div>
              </div>
              {table.overall_coverage >= 80 ? (
                <CheckCircle className="w-6 h-6 text-emerald-400" />
              ) : (
                <AlertCircle className={`w-6 h-6 ${
                  table.overall_coverage >= 60 ? 'text-amber-400' : 'text-red-400'
                }`} />
              )}
            </div>
          </div>

          {/* Field Coverage Grid */}
          <div className="p-4">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {table.fields.map((field, fieldIndex) => (
                <motion.div 
                  key={field.name}
                  className="p-3 bg-surface-900 rounded-lg"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: tableIndex * 0.1 + fieldIndex * 0.02 }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span 
                      className="text-sm text-text-secondary truncate max-w-[120px]" 
                      title={field.name}
                    >
                      {field.name}
                    </span>
                    <span className={`text-xs font-medium ${
                      field.coverage >= 80 ? 'text-emerald-400' :
                      field.coverage >= 60 ? 'text-amber-400' : 'text-red-400'
                    }`}>
                      {field.coverage.toFixed(1)}%
                    </span>
                  </div>
                  
                  {/* Coverage Bar */}
                  <div className="h-2 bg-surface-700 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${field.coverage}%` }}
                      transition={{ duration: 0.5, delay: 0.2 }}
                      className={`h-full rounded-full ${
                        field.coverage >= 80 ? 'bg-emerald-500' :
                        field.coverage >= 60 ? 'bg-amber-500' : 'bg-red-500'
                      }`}
                    />
                  </div>

                  {/* Null/Zero breakdown */}
                  <div className="flex justify-between mt-2 text-xs text-text-muted">
                    <span className={field.null_pct > 20 ? 'text-red-400' : ''}>
                      Nulls: {field.null_pct.toFixed(1)}%
                    </span>
                    <span className={field.zero_pct > 30 ? 'text-amber-400' : ''}>
                      Zeros: {field.zero_pct.toFixed(1)}%
                    </span>
                  </div>

                  {/* Data Type Badge */}
                  <div className="mt-2">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-surface-700 text-text-muted">
                      {field.data_type}
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  );
}

export default CoverageAnalysis;

