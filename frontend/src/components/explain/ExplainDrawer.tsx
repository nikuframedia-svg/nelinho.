/**
 * ExplainDrawer
 * =============
 * 
 * Universal drawer for explaining any metric with 6 structured tabs:
 * 1. Definition - Description, semantics (theoretical/observed), period, scope
 * 2. Formula - Calculation formula, dependencies with trust
 * 3. Lineage - Data sources tree, active ingestion, query hash
 * 4. Trust - Trust index bar, coverage %, warnings list
 * 5. Limitations - Forbidden claims (red), allowed claims (green)
 * 6. Improve - How to increase trust, difficulty badges, Simulate buttons
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { 
  X, 
  Loader2, 
  TrendingUp, 
  TrendingDown, 
  Info, 
  Lightbulb, 
  AlertTriangle, 
  Ban, 
  Shield, 
  Database,
  GitBranch,
  Calculator,
  FileText,
  AlertOctagon,
  CheckCircle,
  Play,
  ChevronRight,
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface Factor {
  name: string;
  impact: number;
  description?: string;
}

interface ImprovementSuggestion {
  id: string;
  description: string;
  estimated_impact?: number;
  difficulty?: 'easy' | 'medium' | 'hard';
  action_type?: string;
}

interface Citation {
  label: string;
  ref: string;
  confidence?: number;
}

interface ExplainedMetric {
  metric_id: string;
  metric_name: string;
  value: number | null;
  unit: string;
  explanation: string;
  factors: Factor[];
  suggestions: ImprovementSuggestion[];
  citations: Citation[];
  computed_at: string;
  trust_index?: number;
  // Extended fields for tabs
  definition?: {
    description: string;
    semantics: 'theoretical' | 'observed' | 'imputed';
    period?: string;
    scope?: string;
  };
  formula?: {
    expression: string;
    dependencies: Array<{ metric_id: string; name: string; trust: number }>;
  };
  lineage?: {
    sources: Array<{ table: string; columns: string[]; trust: number }>;
    query_hash?: string;
    active_ingestion_id?: string;
  };
  limitations?: {
    forbidden_claims: string[];
    allowed_claims: string[];
  };
}

interface ExplainDrawerProps {
  open: boolean;
  onClose: () => void;
  metricId: string;
  onSimulateClick?: (improvement: string) => void;
}

type TabId = 'definition' | 'formula' | 'lineage' | 'trust' | 'limitations' | 'improve';

// ═══════════════════════════════════════════════════════════════════════════════
// API FETCH
// ═══════════════════════════════════════════════════════════════════════════════

async function fetchExplainedMetric(metricId: string): Promise<ExplainedMetric> {
  const tenantId = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000000';
  
  const response = await fetch(`${API_BASE}/v1/explain/metric/${metricId}`, {
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-Id': tenantId,
    },
  });
  
  if (!response.ok) {
    if (response.status === 422) {
      const errorData = await response.json();
      throw new Error(errorData.detail?.message || 'Metric is blocked');
    }
    throw new Error(`Failed to fetch metric: ${response.status}`);
  }
  
  return response.json();
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

function TabButton({ 
  active, 
  onClick, 
  icon: Icon, 
  label 
}: { 
  active: boolean; 
  onClick: () => void; 
  icon: React.ElementType; 
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg transition-all ${
        active 
          ? 'bg-accent text-white shadow-lg shadow-accent/20' 
          : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'
      }`}
    >
      <Icon size={16} />
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

// Definition Tab
function DefinitionTab({ data }: { data: ExplainedMetric }) {
  const semanticsLabels = {
    theoretical: { label: 'Teórico', color: 'bg-blue-100 text-blue-700' },
    observed: { label: 'Observado', color: 'bg-emerald-100 text-emerald-700' },
    imputed: { label: 'Imputado', color: 'bg-purple-100 text-purple-700' },
  };

  const semantics = data.definition?.semantics || 'theoretical';
  const semanticsStyle = semanticsLabels[semantics] || semanticsLabels.theoretical;

  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Descrição</h4>
        <p className="text-sm text-slate-700 leading-relaxed">
          {data.definition?.description || data.explanation}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Semântica</h4>
          <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${semanticsStyle.color}`}>
            {semanticsStyle.label}
          </span>
        </div>
        
        <div>
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Período</h4>
          <span className="text-sm text-slate-700">{data.definition?.period || 'Atual'}</span>
        </div>
      </div>

      {data.definition?.scope && (
        <div>
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Âmbito</h4>
          <span className="text-sm text-slate-700">{data.definition.scope}</span>
        </div>
      )}
    </div>
  );
}

// Formula Tab
function FormulaTab({ data }: { data: ExplainedMetric }) {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Fórmula de Cálculo</h4>
        <div className="p-3 bg-slate-100 rounded-lg font-mono text-sm text-slate-700">
          {data.formula?.expression || 'Cálculo directo a partir dos dados'}
        </div>
      </div>

      {data.formula?.dependencies && data.formula.dependencies.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Dependências</h4>
          <div className="space-y-2">
            {data.formula.dependencies.map((dep, idx) => (
              <div key={idx} className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                <span className="text-sm text-slate-700">{dep.name}</span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                  dep.trust >= 70 ? 'bg-emerald-100 text-emerald-700' :
                  dep.trust >= 50 ? 'bg-amber-100 text-amber-700' :
                  'bg-red-100 text-red-700'
                }`}>
                  {dep.trust}% trust
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Factors as formula contributors */}
      {data.factors.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Factores Contribuintes</h4>
          <div className="space-y-2">
            {data.factors.map((factor, idx) => (
              <div key={idx} className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                <div className="flex items-center gap-2">
                  {factor.impact > 0 ? (
                    <TrendingUp size={14} className="text-emerald-500" />
                  ) : factor.impact < 0 ? (
                    <TrendingDown size={14} className="text-red-500" />
                  ) : (
                    <div className="w-3.5 h-0.5 bg-slate-400" />
                  )}
                  <span className="text-sm text-slate-700">{factor.name}</span>
                </div>
                <span className={`text-xs font-medium ${
                  factor.impact > 0 ? 'text-emerald-600' : 
                  factor.impact < 0 ? 'text-red-600' : 'text-slate-500'
                }`}>
                  {factor.impact > 0 ? '+' : ''}{(factor.impact * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Lineage Tab
function LineageTab({ data }: { data: ExplainedMetric }) {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Fontes de Dados</h4>
        {data.lineage?.sources && data.lineage.sources.length > 0 ? (
          <div className="space-y-2">
            {data.lineage.sources.map((source, idx) => (
              <div key={idx} className="p-3 bg-slate-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Database size={14} className="text-slate-400" />
                    <span className="text-sm font-medium text-slate-700">{source.table}</span>
                  </div>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                    source.trust >= 70 ? 'bg-emerald-100 text-emerald-700' :
                    source.trust >= 50 ? 'bg-amber-100 text-amber-700' :
                    'bg-red-100 text-red-700'
                  }`}>
                    {source.trust}% trust
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {source.columns.map((col, cidx) => (
                    <code key={cidx} className="text-xs bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                      {col}
                    </code>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : data.citations.length > 0 ? (
          <div className="space-y-2">
            {data.citations.map((citation, idx) => (
              <div key={idx} className="flex items-center gap-2 p-2 bg-slate-50 rounded-lg">
                <Database size={14} className="text-slate-400" />
                <span className="text-sm text-slate-600">{citation.label}</span>
                <ChevronRight size={12} className="text-slate-400" />
                <code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">{citation.ref}</code>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500 italic">Sem informação de lineage disponível</p>
        )}
      </div>

      {data.lineage?.query_hash && (
        <div>
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Query Hash</h4>
          <code className="text-xs bg-slate-100 px-2 py-1 rounded text-slate-600 block">
            {data.lineage.query_hash}
          </code>
        </div>
      )}

      {data.lineage?.active_ingestion_id && (
        <div>
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Ingestion Activa</h4>
          <code className="text-xs bg-emerald-50 text-emerald-700 px-2 py-1 rounded block">
            {data.lineage.active_ingestion_id}
          </code>
        </div>
      )}
    </div>
  );
}

// Trust Tab
function TrustTab({ data }: { data: ExplainedMetric }) {
  const trustPercentage = Math.round((data.trust_index ?? 0) * 100);
  const isBlocked = trustPercentage === 0;
  const isLow = trustPercentage > 0 && trustPercentage < 50;
  const isWarning = trustPercentage >= 50 && trustPercentage < 70;

  return (
    <div className="space-y-4">
      {/* Trust Index Bar */}
      <div>
        <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Índice de Confiança</h4>
        <div className="relative h-8 bg-slate-100 rounded-lg overflow-hidden">
          <div 
            className={`absolute inset-y-0 left-0 transition-all ${
              isBlocked ? 'bg-red-500' :
              isLow ? 'bg-red-400' :
              isWarning ? 'bg-amber-400' :
              'bg-emerald-400'
            }`}
            style={{ width: `${Math.max(trustPercentage, 5)}%` }}
          />
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={`text-sm font-bold ${trustPercentage > 50 ? 'text-white' : 'text-slate-700'}`}>
              {trustPercentage}%
            </span>
          </div>
        </div>
        <div className="flex justify-between mt-1 text-xs text-slate-400">
          <span>0%</span>
          <span>50%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Status Badge */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-slate-500">Estado:</span>
        {isBlocked ? (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-red-100 text-red-700 text-xs font-medium">
            <Ban size={12} /> BLOCKED
          </span>
        ) : isLow ? (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-red-100 text-red-700 text-xs font-medium">
            <AlertTriangle size={12} /> LOW
          </span>
        ) : isWarning ? (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-amber-100 text-amber-700 text-xs font-medium">
            <AlertTriangle size={12} /> WARNING
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-emerald-100 text-emerald-700 text-xs font-medium">
            <Shield size={12} /> OK
          </span>
        )}
      </div>

      {/* Coverage from citations */}
      {data.citations.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Cobertura por Fonte</h4>
          <div className="space-y-2">
            {data.citations.map((citation, idx) => (
              <div key={idx} className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                <span className="text-sm text-slate-600">{citation.label}</span>
                {citation.confidence !== undefined && (
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-2 bg-slate-200 rounded-full overflow-hidden">
                      <div 
                        className={`h-full ${
                          citation.confidence >= 0.7 ? 'bg-emerald-400' :
                          citation.confidence >= 0.5 ? 'bg-amber-400' :
                          'bg-red-400'
                        }`}
                        style={{ width: `${citation.confidence * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-500">{(citation.confidence * 100).toFixed(0)}%</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {(isBlocked || isLow || isWarning) && (
        <div className={`p-3 rounded-lg border ${
          isBlocked ? 'bg-red-50 border-red-200' :
          isLow ? 'bg-red-50 border-red-200' :
          'bg-amber-50 border-amber-200'
        }`}>
          <div className="flex items-start gap-2">
            <AlertTriangle size={16} className={isBlocked || isLow ? 'text-red-500' : 'text-amber-500'} />
            <div>
              <p className={`text-sm font-medium ${isBlocked || isLow ? 'text-red-700' : 'text-amber-700'}`}>
                {isBlocked ? 'Dados Indisponíveis' : isLow ? 'Confiança Muito Baixa' : 'Confiança Limitada'}
              </p>
              <p className={`text-xs mt-1 ${isBlocked || isLow ? 'text-red-600' : 'text-amber-600'}`}>
                {isBlocked 
                  ? 'Os dados necessários para calcular esta métrica não existem.'
                  : 'Os valores apresentados são estimativas com base em dados parciais.'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Limitations Tab
function LimitationsTab({ data }: { data: ExplainedMetric }) {
  const forbiddenClaims = data.limitations?.forbidden_claims || [
    'Este valor NÃO representa dados reais de produção',
    'NÃO usar para decisões financeiras críticas',
    'NÃO comparar directamente com métricas de outros sistemas',
  ];

  const allowedClaims = data.limitations?.allowed_claims || [
    'Pode ser usado para identificar tendências',
    'Válido para priorização relativa',
    'Adequado para simulações what-if',
  ];

  return (
    <div className="space-y-4">
      {/* Forbidden Claims */}
      <div>
        <h4 className="text-xs font-medium text-red-600 uppercase tracking-wider mb-2 flex items-center gap-1">
          <AlertOctagon size={14} />
          Afirmações Proibidas
        </h4>
        <div className="space-y-2">
          {forbiddenClaims.map((claim, idx) => (
            <div key={idx} className="flex items-start gap-2 p-2 bg-red-50 border border-red-100 rounded-lg">
              <Ban size={14} className="text-red-500 mt-0.5 flex-shrink-0" />
              <span className="text-sm text-red-700">{claim}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Allowed Claims */}
      <div>
        <h4 className="text-xs font-medium text-emerald-600 uppercase tracking-wider mb-2 flex items-center gap-1">
          <CheckCircle size={14} />
          Afirmações Permitidas
        </h4>
        <div className="space-y-2">
          {allowedClaims.map((claim, idx) => (
            <div key={idx} className="flex items-start gap-2 p-2 bg-emerald-50 border border-emerald-100 rounded-lg">
              <CheckCircle size={14} className="text-emerald-500 mt-0.5 flex-shrink-0" />
              <span className="text-sm text-emerald-700">{claim}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Improve Tab
function ImproveTab({ data, onSimulate }: { data: ExplainedMetric; onSimulate?: (desc: string) => void }) {
  const navigate = useNavigate();
  const isBlocked = data.value === null && data.trust_index === 0;

  const difficultyColors = {
    easy: 'bg-emerald-100 text-emerald-700',
    medium: 'bg-amber-100 text-amber-700',
    hard: 'bg-red-100 text-red-700',
  };

  const handleSimulate = (suggestion: ImprovementSuggestion) => {
    if (onSimulate) {
      onSimulate(suggestion.description);
    } else {
      navigate(`/twin?action=${suggestion.action_type || 'custom'}&description=${encodeURIComponent(suggestion.description)}`);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
          {isBlocked ? 'Como Desbloquear Esta Métrica' : 'Sugestões de Melhoria'}
        </h4>
        
        {data.suggestions.length > 0 ? (
          <div className="space-y-3">
            {data.suggestions.map((suggestion, idx) => (
              <div 
                key={idx} 
                className={`p-3 rounded-lg border ${
                  suggestion.action_type === 'data_improvement' 
                    ? 'bg-blue-50 border-blue-200' 
                    : 'bg-slate-50 border-slate-200'
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <p className={`text-sm font-medium ${
                    suggestion.action_type === 'data_improvement' 
                      ? 'text-blue-900' 
                      : 'text-slate-700'
                  }`}>
                    {suggestion.description}
                  </p>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {suggestion.estimated_impact && (
                      <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
                        +{suggestion.estimated_impact}%
                      </span>
                    )}
                    {suggestion.difficulty && (
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${difficultyColors[suggestion.difficulty]}`}>
                        {suggestion.difficulty}
                      </span>
                    )}
                  </div>
                </div>
                
                {suggestion.action_type === 'data_improvement' ? (
                  <div className="flex items-center gap-1 text-xs text-blue-600">
                    <Database size={12} />
                    <span>Acção de melhoria de dados</span>
                  </div>
                ) : !isBlocked && (
                  <button
                    onClick={() => handleSimulate(suggestion)}
                    className="flex items-center gap-1 text-xs font-medium text-purple-600 hover:text-purple-700 transition-colors"
                  >
                    <Play size={12} />
                    Simular esta melhoria
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500 italic">Sem sugestões de melhoria disponíveis</p>
        )}
      </div>

      {/* Quick simulate button for non-blocked metrics */}
      {!isBlocked && data.trust_index !== undefined && data.trust_index >= 0.3 && (
        <div className="pt-4 border-t border-slate-200">
          <button
            onClick={() => navigate(`/twin?metric=${data.metric_id}`)}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
          >
            <GitBranch size={18} />
            Abrir no Twin Sandbox
          </button>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function ExplainDrawer({ open, onClose, metricId, onSimulateClick }: ExplainDrawerProps) {
  const [activeTab, setActiveTab] = useState<TabId>('definition');
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['explain', metricId],
    queryFn: () => fetchExplainedMetric(metricId),
    enabled: open && !!metricId,
    staleTime: 2 * 60 * 1000,
    retry: false,
  });

  if (!open) return null;

  const isBlocked = data?.value === null && data?.trust_index === 0;
  const isWarning = data?.trust_index !== undefined && data.trust_index > 0 && data.trust_index < 0.7;

  const tabs: Array<{ id: TabId; label: string; icon: React.ElementType }> = [
    { id: 'definition', label: 'Definição', icon: FileText },
    { id: 'formula', label: 'Fórmula', icon: Calculator },
    { id: 'lineage', label: 'Lineage', icon: GitBranch },
    { id: 'trust', label: 'Trust', icon: Shield },
    { id: 'limitations', label: 'Limites', icon: AlertOctagon },
    { id: 'improve', label: 'Melhorar', icon: Lightbulb },
  ];

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 transition-opacity"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-[560px] bg-white shadow-2xl z-50 overflow-hidden flex flex-col animate-slideInRight">
        {/* Header */}
        <div className={`px-6 py-4 border-b ${
          isBlocked ? 'bg-gradient-to-r from-red-50 to-orange-50 border-red-200' : 
          isWarning ? 'bg-gradient-to-r from-amber-50 to-yellow-50 border-amber-200' : 
          'bg-gradient-to-r from-blue-50 to-indigo-50 border-slate-200'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                isBlocked ? 'bg-red-500' : isWarning ? 'bg-amber-500' : 'bg-blue-500'
              }`}>
                {isBlocked ? <Ban size={20} className="text-white" /> : <Info size={20} className="text-white" />}
              </div>
              <div>
                <h2 className="font-bold text-slate-900">
                  {isBlocked ? 'Métrica Bloqueada' : 'Explicar Métrica'}
                </h2>
                <p className="text-sm text-slate-500">{metricId}</p>
              </div>
            </div>
            <button 
              onClick={onClose}
              className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center transition-colors"
            >
              <X size={20} className="text-slate-500" />
            </button>
          </div>
          
          {/* Value Display */}
          {data && (
            <div className="mt-4 flex items-baseline gap-2">
              {isBlocked ? (
                <span className="text-xl font-bold text-red-600 flex items-center gap-2">
                  <Ban size={20} />
                  INDISPONÍVEL
                </span>
              ) : (
                <>
                  <span className="text-3xl font-bold text-slate-900">
                    {data.value !== null ? data.value.toLocaleString('pt-PT', { maximumFractionDigits: 1 }) : '—'}
                  </span>
                  <span className="text-lg text-slate-500">{data.unit}</span>
                  {data.trust_index !== undefined && (
                    <span className={`ml-2 text-xs font-medium px-2 py-1 rounded ${
                      data.trust_index >= 0.7 ? 'bg-emerald-100 text-emerald-700' :
                      data.trust_index >= 0.5 ? 'bg-amber-100 text-amber-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {Math.round(data.trust_index * 100)}% trust
                    </span>
                  )}
                </>
              )}
            </div>
          )}
        </div>
        
        {/* Tabs */}
        <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-1 overflow-x-auto">
            {tabs.map((tab) => (
              <TabButton
                key={tab.id}
                active={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id)}
                icon={tab.icon}
                label={tab.label}
              />
            ))}
          </div>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 size={32} className="text-blue-500 animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
                <Ban size={32} className="text-red-500" />
              </div>
              <p className="text-red-600 font-medium">Erro ao carregar explicação</p>
              <p className="text-sm text-slate-500 mt-2">{(error as Error).message}</p>
            </div>
          ) : data ? (
            <>
              {activeTab === 'definition' && <DefinitionTab data={data} />}
              {activeTab === 'formula' && <FormulaTab data={data} />}
              {activeTab === 'lineage' && <LineageTab data={data} />}
              {activeTab === 'trust' && <TrustTab data={data} />}
              {activeTab === 'limitations' && <LimitationsTab data={data} />}
              {activeTab === 'improve' && <ImproveTab data={data} onSimulate={onSimulateClick} />}
            </>
          ) : null}
        </div>
        
        {/* Footer */}
        {data && (
          <div className="px-6 py-3 border-t border-slate-200 bg-slate-50">
            <p className="text-xs text-slate-400">
              Calculado em: {new Date(data.computed_at).toLocaleString('pt-PT')}
            </p>
          </div>
        )}
      </div>
    </>
  );
}
