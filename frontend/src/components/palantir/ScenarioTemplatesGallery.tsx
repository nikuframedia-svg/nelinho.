/**
 * ScenarioTemplatesGallery — Pre-built scenario templates
 * Part of TIER 2: OPERATIONAL EXCELLENCE
 * 
 * "The Decision Accelerator"
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Play, Filter } from 'lucide-react';
import type { ScenarioTemplate } from '@/types';

const SCENARIO_TEMPLATES: ScenarioTemplate[] = [
  {
    id: 'capacity-increase-10',
    name: 'Aumento Capacidade 10%',
    description: 'Simula efeito de aumentar capacidade em 10% na fase seleccionada',
    icon: '📈',
    category: 'capacity',
    deltas: [{ type: 'CAPACITY_CHANGE', delta_pct: 10 }]
  },
  {
    id: 'cross-training-critical',
    name: 'Cross-Training Fase Crítica',
    description: 'Adiciona 2 funcionários aptos na fase com maior risco',
    icon: '🎓',
    category: 'workforce',
    deltas: [{ type: 'ADD_SKILLED_WORKERS', count: 2, target: 'highest_risk_phase' }]
  },
  {
    id: 'new-hire',
    name: 'Nova Contratação',
    description: 'Simula impacto de contratar 1 funcionário polivalente',
    icon: '👤',
    category: 'workforce',
    deltas: [{ type: 'NEW_HIRE', skills: 'versatile' }]
  },
  {
    id: 'machine-breakdown',
    name: 'Avaria de Máquina',
    description: 'Simula perda de capacidade por avaria numa fase',
    icon: '⚠️',
    category: 'risk',
    deltas: [{ type: 'CAPACITY_CHANGE', delta_pct: -30, duration_hours: 24 }]
  },
  {
    id: 'rush-order',
    name: 'Encomenda Urgente',
    description: 'Adiciona ordem com prioridade máxima ao backlog',
    icon: '🚨',
    category: 'orders',
    deltas: [{ type: 'ADD_ORDER', priority: 'critical', hours: 50 }]
  },
  {
    id: 'vacation-period',
    name: 'Período de Férias',
    description: 'Simula 30% menos workforce durante 2 semanas',
    icon: '🏖️',
    category: 'workforce',
    deltas: [{ type: 'WORKFORCE_REDUCTION', delta_pct: -30, duration_days: 14 }]
  },
  {
    id: 'quality-issue',
    name: 'Problema de Qualidade',
    description: 'Simula aumento de 20% em retrabalho numa fase',
    icon: '🔧',
    category: 'risk',
    deltas: [{ type: 'REWORK_INCREASE', delta_pct: 20 }]
  },
  {
    id: 'mold-maintenance',
    name: 'Manutenção de Molde',
    description: 'Simula indisponibilidade de molde por 3 dias',
    icon: '🔩',
    category: 'risk',
    deltas: [{ type: 'MOLD_UNAVAILABLE', duration_days: 3 }]
  },
  {
    id: 'overtime-week',
    name: 'Semana com Horas Extra',
    description: 'Adiciona 20% de capacidade via horas extra',
    icon: '⏰',
    category: 'capacity',
    deltas: [{ type: 'OVERTIME', delta_pct: 20, duration_days: 7 }]
  },
];

const CATEGORIES = [
  { id: 'all', label: 'Todos', icon: '🎯' },
  { id: 'capacity', label: 'Capacidade', icon: '📈' },
  { id: 'workforce', label: 'Workforce', icon: '👥' },
  { id: 'risk', label: 'Risco', icon: '⚠️' },
  { id: 'orders', label: 'Encomendas', icon: '📦' },
];

interface ScenarioTemplatesGalleryProps {
  onSelectTemplate: (template: ScenarioTemplate) => void;
}

export function ScenarioTemplatesGallery({ onSelectTemplate }: ScenarioTemplatesGalleryProps) {
  const [filter, setFilter] = useState<string>('all');

  const filtered = filter === 'all' 
    ? SCENARIO_TEMPLATES 
    : SCENARIO_TEMPLATES.filter(t => t.category === filter);

  return (
    <div className="bg-surface-800 rounded-2xl border border-surface-700 overflow-hidden">
      <div className="px-6 py-4 border-b border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand-500/20 rounded-lg">
              <Filter className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text-white">Templates de Cenário</h3>
              <p className="text-sm text-text-muted">Simulações pré-configuradas para decisões rápidas</p>
            </div>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Category Filters */}
        <div className="flex gap-2 flex-wrap">
          {CATEGORIES.map(cat => (
            <button
              key={cat.id}
              onClick={() => setFilter(cat.id)}
              className={`px-4 py-2 rounded-full text-sm flex items-center gap-2
                         transition-all ${filter === cat.id 
                           ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/25' 
                           : 'bg-surface-700 text-text-muted hover:bg-surface-600 hover:text-text-secondary'}`}
            >
              <span>{cat.icon}</span>
              {cat.label}
            </button>
          ))}
        </div>

        {/* Templates Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((template, index) => (
            <motion.button
              key={template.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              onClick={() => onSelectTemplate(template)}
              className="p-6 bg-surface-900 rounded-xl border border-surface-700
                        hover:border-brand-500/50 hover:bg-surface-800
                        transition-all text-left group"
            >
              <span className="text-4xl mb-4 block">{template.icon}</span>
              <h3 className="text-text-white font-medium group-hover:text-brand-400 
                            transition-colors">
                {template.name}
              </h3>
              <p className="text-text-muted text-sm mt-2 line-clamp-2">
                {template.description}
              </p>
              
              {/* Category Badge */}
              <div className="mt-4 flex items-center justify-between">
                <span className={`text-xs px-2 py-0.5 rounded-full
                               ${template.category === 'capacity' ? 'bg-blue-500/20 text-blue-400' :
                                 template.category === 'workforce' ? 'bg-purple-500/20 text-purple-400' :
                                 template.category === 'risk' ? 'bg-red-500/20 text-red-400' :
                                 'bg-emerald-500/20 text-emerald-400'}`}>
                  {CATEGORIES.find(c => c.id === template.category)?.icon} {template.category}
                </span>
                
                <div className="flex items-center gap-1 text-brand-400 text-sm 
                               opacity-0 group-hover:opacity-100 transition-opacity">
                  <Play className="w-4 h-4" />
                  Usar
                </div>
              </div>
            </motion.button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default ScenarioTemplatesGallery;

