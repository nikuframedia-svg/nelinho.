/**
 * ToolRegistryPage — LLM Tool Registry Control Panel
 * Part of TIER 4: CI/DEVOPS & FUTURE
 * 
 * "The LLM Control Panel"
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Search, Zap, FlaskConical, Shield, Code, Plus, Activity } from 'lucide-react';
import { useToolRegistry } from '@/hooks';
import type { LLMTool } from '@/types';

const CATEGORY_CONFIG = {
  query: { name: 'Consulta', icon: Search, color: 'blue' },
  action: { name: 'Acção', icon: Zap, color: 'amber' },
  simulation: { name: 'Simulação', icon: FlaskConical, color: 'purple' },
  admin: { name: 'Admin', icon: Shield, color: 'red' },
};

function ToolCard({ tool, onToggle }: { tool: LLMTool; onToggle: () => void }) {
  const category = CATEGORY_CONFIG[tool.category];
  const CategoryIcon = category.icon;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`bg-surface-800 rounded-xl border transition-all ${
        tool.enabled 
          ? `border-${category.color}-500/30 hover:border-${category.color}-500/50` 
          : 'border-surface-700 opacity-60 hover:opacity-80'
      }`}
    >
      <div className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${
              tool.enabled 
                ? `bg-${category.color}-500/20` 
                : 'bg-surface-700'
            }`}>
              <CategoryIcon className={`w-5 h-5 ${
                tool.enabled 
                  ? `text-${category.color}-400` 
                  : 'text-text-muted'
              }`} />
            </div>
            <div>
              <h3 className="text-text-white font-medium">
                {tool.name}
              </h3>
              <code className="text-xs text-text-muted bg-surface-900 
                              px-1.5 py-0.5 rounded">
                {tool.function_name}
              </code>
            </div>
          </div>

          {/* Enable/Disable Toggle */}
          <button
            onClick={onToggle}
            className={`relative w-12 h-6 rounded-full transition-colors ${
              tool.enabled ? 'bg-emerald-500' : 'bg-surface-600'
            }`}
          >
            <motion.div
              layout
              className="absolute top-1 w-4 h-4 rounded-full bg-white"
              style={{ left: tool.enabled ? 'calc(100% - 20px)' : '4px' }}
            />
          </button>
        </div>

        <p className="text-text-secondary text-sm mt-3">
          {tool.description}
        </p>

        {/* Metadata */}
        <div className="mt-4 flex items-center gap-4 flex-wrap">
          {/* Risk Level */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-text-muted">Risco:</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              tool.risk_level === 'high' 
                ? 'bg-red-500/20 text-red-400' 
                : tool.risk_level === 'medium'
                ? 'bg-amber-500/20 text-amber-400'
                : 'bg-emerald-500/20 text-emerald-400'
            }`}>
              {tool.risk_level === 'high' ? 'Alto' :
               tool.risk_level === 'medium' ? 'Médio' : 'Baixo'}
            </span>
          </div>

          {/* Requires Approval */}
          {tool.requires_approval && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400">
              Requer Aprovação
            </span>
          )}

          {/* Usage Count */}
          <div className="flex items-center gap-1 text-xs text-text-muted">
            <Activity className="w-3 h-3" />
            {tool.usage_count} usos
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export function ToolRegistryPage() {
  const { tools, loading, updateTool } = useToolRegistry();
  const [filter, setFilter] = useState<'all' | 'enabled' | 'disabled'>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  const filteredTools = tools.filter(tool => {
    const statusMatch = filter === 'all' || 
      (filter === 'enabled' && tool.enabled) || 
      (filter === 'disabled' && !tool.enabled);
    const categoryMatch = categoryFilter === 'all' || tool.category === categoryFilter;
    return statusMatch && categoryMatch;
  });

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-12 w-64 bg-surface-700 rounded" />
        <div className="grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-48 bg-surface-700 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-white flex items-center gap-3">
            <Code className="w-7 h-7 text-brand-400" />
            Tool Registry
          </h1>
          <p className="text-text-muted mt-1">
            Controle as ferramentas disponíveis para o Copilot LLM
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-text-muted">
            <span className="text-text-white font-medium">
              {tools.filter(t => t.enabled).length}
            </span> de {tools.length} activas
          </div>
          <button className="px-4 py-2 bg-brand-500 text-white rounded-lg 
                            hover:bg-brand-600 transition-colors flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Adicionar Tool
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        {/* Status Filter */}
        <div className="flex gap-2">
          {[
            { id: 'all', label: 'Todas' },
            { id: 'enabled', label: 'Activas' },
            { id: 'disabled', label: 'Desactivadas' },
          ].map(f => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id as typeof filter)}
              className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                filter === f.id 
                  ? 'bg-brand-500 text-white' 
                  : 'bg-surface-700 text-text-muted hover:bg-surface-600'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Category Filter */}
        <div className="flex gap-2">
          <button
            onClick={() => setCategoryFilter('all')}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              categoryFilter === 'all' 
                ? 'bg-surface-600 text-text-white' 
                : 'bg-surface-700 text-text-muted hover:bg-surface-600'
            }`}
          >
            Todas Categorias
          </button>
          {Object.entries(CATEGORY_CONFIG).map(([id, config]) => {
            const Icon = config.icon;
            return (
              <button
                key={id}
                onClick={() => setCategoryFilter(id)}
                className={`px-4 py-2 rounded-lg text-sm transition-colors flex items-center gap-2 ${
                  categoryFilter === id 
                    ? `bg-${config.color}-500/20 text-${config.color}-400` 
                    : 'bg-surface-700 text-text-muted hover:bg-surface-600'
                }`}
              >
                <Icon className="w-4 h-4" />
                {config.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tools by Category */}
      {Object.entries(CATEGORY_CONFIG).map(([categoryId, category]) => {
        const categoryTools = filteredTools.filter(t => t.category === categoryId);
        
        if (categoryTools.length === 0) return null;
        if (categoryFilter !== 'all' && categoryFilter !== categoryId) return null;

        const CategoryIcon = category.icon;

        return (
          <div key={categoryId}>
            <div className="flex items-center gap-2 mb-4">
              <CategoryIcon className={`w-5 h-5 text-${category.color}-400`} />
              <h2 className="text-lg font-semibold text-text-white">
                {category.name}
              </h2>
              <span className="text-sm text-text-muted">
                ({categoryTools.length})
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {categoryTools.map(tool => (
                <ToolCard
                  key={tool.id}
                  tool={tool}
                  onToggle={() => updateTool(tool.id, { enabled: !tool.enabled })}
                />
              ))}
            </div>
          </div>
        );
      })}

      {/* Empty State */}
      {filteredTools.length === 0 && (
        <div className="text-center py-12 bg-surface-800 rounded-xl">
          <Code className="w-12 h-12 text-text-muted mx-auto mb-4" />
          <p className="text-text-white font-medium">Nenhuma tool encontrada</p>
          <p className="text-text-muted text-sm">Tente ajustar os filtros</p>
        </div>
      )}
    </div>
  );
}

export default ToolRegistryPage;

