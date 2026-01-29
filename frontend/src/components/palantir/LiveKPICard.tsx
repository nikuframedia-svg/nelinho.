/**
 * LiveKPICard — Real-time KPI card with trust indication
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 * 
 * "Each number pulses with real life"
 */

import { motion } from 'framer-motion';
import { Info, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { ExplainedValue } from '@/types';

interface LiveKPICardProps {
  value: ExplainedValue;
  onExplain: () => void;
  trend?: 'up' | 'down' | 'stable';
  isLoading?: boolean;
}

const getTrustConfig = (trust: number) => {
  if (trust >= 80) return { color: 'emerald', label: 'Alto' };
  if (trust >= 60) return { color: 'amber', label: 'Médio' };
  return { color: 'red', label: 'Baixo' };
};

const TrendIcon = ({ trend }: { trend?: 'up' | 'down' | 'stable' }) => {
  if (trend === 'up') return <TrendingUp className="w-4 h-4 text-emerald-400" />;
  if (trend === 'down') return <TrendingDown className="w-4 h-4 text-red-400" />;
  return <Minus className="w-4 h-4 text-text-muted" />;
};

export function LiveKPICard({ value, onExplain, trend, isLoading }: LiveKPICardProps) {
  const trustConfig = getTrustConfig(value.trust_index);

  if (isLoading) {
    return (
      <div className="relative bg-surface-800 rounded-2xl p-6 border border-surface-700 animate-pulse">
        <div className="h-8 w-24 bg-surface-700 rounded mb-2" />
        <div className="h-4 w-32 bg-surface-700 rounded" />
        <div className="mt-4 h-1 bg-surface-700 rounded-full" />
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative bg-surface-800 rounded-2xl p-6 border border-surface-700
                 hover:border-brand-500/50 transition-all duration-300 group"
    >
      {/* Trust Ring - Palantir signature */}
      <div className="absolute -top-2 -right-2">
        <motion.div 
          className={`w-10 h-10 rounded-full bg-${trustConfig.color}-500/20 
                      flex items-center justify-center border-2 border-${trustConfig.color}-500/40`}
          whileHover={{ scale: 1.2 }}
          title={`Trust Index: ${value.trust_index}% (${trustConfig.label})`}
        >
          <span className={`text-xs font-bold text-${trustConfig.color}-400`}>
            {value.trust_index}
          </span>
        </motion.div>
      </div>

      {/* Main Value with Pulse Animation */}
      <div className="flex items-baseline gap-2">
        <motion.span 
          className="text-4xl font-bold text-text-white"
          key={value.value?.toString()}
          initial={{ scale: 1.1, color: '#10B981' }}
          animate={{ scale: 1, color: '#FFFFFF' }}
          transition={{ duration: 0.5 }}
        >
          {value.formatted_value}
        </motion.span>
        <span className="text-text-muted">{value.unit}</span>
        {trend && <TrendIcon trend={trend} />}
      </div>

      {/* Semantic Label */}
      <p className="text-sm text-text-secondary mt-1">
        {value.semantic_label}
      </p>

      {/* Semantic Kind Badge */}
      <div className="mt-2">
        <span className={`text-xs px-2 py-0.5 rounded-full 
                         ${value.semantic_kind === 'real' ? 'bg-emerald-500/20 text-emerald-400' :
                           value.semantic_kind === 'calculated' ? 'bg-blue-500/20 text-blue-400' :
                           value.semantic_kind === 'estimated' ? 'bg-amber-500/20 text-amber-400' :
                           'bg-purple-500/20 text-purple-400'}`}>
          {value.semantic_kind === 'theoretical' ? 'Teórico' :
           value.semantic_kind === 'calculated' ? 'Calculado' :
           value.semantic_kind === 'estimated' ? 'Estimado' : 'Real'}
        </span>
      </div>

      {/* Trust Bar */}
      <div className="mt-4 h-1.5 bg-surface-700 rounded-full overflow-hidden">
        <motion.div 
          className={`h-full bg-${trustConfig.color}-500`}
          initial={{ width: 0 }}
          animate={{ width: `${value.trust_index}%` }}
          transition={{ duration: 1, ease: 'easeOut' }}
        />
      </div>

      {/* Hover Actions */}
      <motion.div 
        className="absolute inset-x-0 bottom-0 p-4 bg-gradient-to-t from-surface-900
                   opacity-0 group-hover:opacity-100 transition-opacity rounded-b-2xl"
      >
        <button 
          onClick={onExplain}
          className="text-sm text-brand-400 hover:text-brand-300 flex items-center gap-1
                     transition-colors"
        >
          <Info className="w-4 h-4" />
          Explicar este valor
        </button>
      </motion.div>
    </motion.div>
  );
}

export default LiveKPICard;

