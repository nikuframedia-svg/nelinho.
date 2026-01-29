import { useState, useEffect } from 'react';
import {
  Bot,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
  Loader2,
  BookOpen,
  MessageSquare,
  TrendingUp,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Zap,
  Target,
} from 'lucide-react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { copilotApi } from '../../lib/api';
import type { CopilotResponse } from '../../lib/api';

interface InsightItem {
  id: string;
  severity?: 'CRITICAL' | 'WARN' | 'INFO';
  priority?: number;
  category?: 'QUALITY' | 'PERFORMANCE' | 'MAINTENANCE' | 'STANDARD_WORK' | 'GENERAL';
  title: string;
  text?: string;
  description?: string;
  citations?: any[];
  suggested_runbooks?: string[];
  suggested_actions?: string[];
  affected_phases?: string[];
  impact_metric?: string;
  impact_value?: number;
  origins?: string[];
  confidence?: 'LOW' | 'MEDIUM' | 'MEDIUM_HIGH' | 'HIGH';
  limitations?: string[];
  next_steps?: string[];
  data_evidence?: Record<string, any>;
}

interface InsightsResponse {
  date: string;
  now: InsightItem[];
  next: InsightItem[];
  meta: {
    generated_at: string;
    sources: string[];
  };
}

export function CopilotInsightsCard() {
  const [expandedNow, setExpandedNow] = useState<Set<string>>(new Set());
  const [expandedNext, setExpandedNext] = useState<Set<string>>(new Set());
  const [explanations, setExplanations] = useState<Record<string, CopilotResponse>>({});
  const [loadingExplanation, setLoadingExplanation] = useState<Set<string>>(new Set());

  const { data: insights, isLoading } = useQuery<InsightsResponse>({
    queryKey: ['copilot', 'insights'],
    queryFn: () => copilotApi.getInsights(),
    staleTime: 5 * 60 * 1000, // 5 minutos
    retry: false,
  });

  const explainMutation = useMutation({
    mutationFn: (data: { recommendations: InsightItem[]; user_query?: string }) =>
      copilotApi.explainRecommendations(data),
  });

  // Track the last mutation variables to get itemId in useEffect
  const [lastMutationVariables, setLastMutationVariables] = useState<{ recommendations: InsightItem[]; user_query?: string } | null>(null);

  // Handle explainMutation success (React Query v5 pattern)
  useEffect(() => {
    if (explainMutation.isSuccess && explainMutation.data && lastMutationVariables) {
      const response = explainMutation.data;
      const variables = lastMutationVariables;
      const itemId = variables.recommendations[0]?.id;
      if (itemId) {
        setExplanations((prev) => ({ ...prev, [itemId]: response }));
        setLoadingExplanation((prev) => {
          const next = new Set(prev);
          next.delete(itemId);
          return next;
        });
      }
    }
  }, [explainMutation.isSuccess, explainMutation.data, lastMutationVariables]);

  // Handle explainMutation error (React Query v5 pattern)
  useEffect(() => {
    if (explainMutation.isError && explainMutation.error) {
      const error = explainMutation.error as any;
      console.error('Erro ao obter explicação:', error);
      // Mesmo em caso de erro, remover loading state
      const itemId = expandedNext.size > 0 ? Array.from(expandedNext)[0] : null;
      if (itemId) {
        setLoadingExplanation((prev) => {
          const next = new Set(prev);
          next.delete(itemId);
          return next;
        });
        // Adicionar mensagem de erro como explicação
        setExplanations((prev) => ({
          ...prev,
          [itemId]: {
            suggestion_id: `error-${Date.now()}`,
            correlation_id: `error-${Date.now()}`,
            type: 'ERROR',
            intent: 'generic',
            summary: error.message || 'Erro ao obter explicação do COPILOT',
            facts: [],
            actions: [],
            warnings: [{
              code: 'SERVICE_ERROR',
              message: error.message || 'O backend ou o Ollama podem não estar a correr.',
            }],
            meta: {
              model: 'unknown',
              tokens: 0,
              latency_ms: 0,
              validation_passed: false,
            },
          } as CopilotResponse,
        }));
      }
    }
  }, [explainMutation.isError, explainMutation.error, expandedNext]);

  const handleToggleNow = (id: string) => {
    setExpandedNow((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleToggleNext = (id: string) => {
    setExpandedNext((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleOpenInCopilot = (item: InsightItem, type: 'alert' | 'recommendation') => {
    // Disparar evento customizado para abrir drawer do Copilot
    const query = type === 'alert'
      ? `Explica este alerta e dá próximos passos com evidência: ${item.title} - ${item.text || item.description}`
      : `Explica como implementar esta recomendação, com origem/confiança/limitações: ${item.title} - ${item.description}`;
    
    // Disparar evento customizado
    window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
  };

  const handleExplainRecommendation = async (item: InsightItem) => {
    const variables = {
      recommendations: [item],
      user_query: `Explica como implementar esta recomendação, com origem/confiança/limitações: ${item.title}`,
    };
    setLastMutationVariables(variables);
    setLoadingExplanation((prev) => new Set(prev).add(item.id));
    await explainMutation.mutateAsync(variables);
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return (
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-red-500 to-red-600 flex items-center justify-center shadow-glow-red border border-red-500/30">
            <XCircle size={20} className="text-white" />
          </div>
        );
      case 'WARN':
        return (
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center shadow-glow-amber border border-amber-500/30">
            <AlertTriangle size={20} className="text-white" />
          </div>
        );
      case 'INFO':
        return (
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-glow-blue border border-blue-500/30">
            <Info size={20} className="text-white" />
          </div>
        );
      default:
        return (
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-500 to-slate-600 flex items-center justify-center border border-slate-500/30">
            <Info size={20} className="text-white" />
          </div>
        );
    }
  };

  const getSeverityBadge = (severity: string) => {
    const classes = {
      CRITICAL: 'bg-red-500/15 text-red-400 border-red-500/30',
      WARN: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
      INFO: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    };
    return classes[severity as keyof typeof classes] || classes.INFO;
  };

  const getCategoryBadge = (category: string) => {
    const classes = {
      QUALITY: 'bg-red-500/15 text-red-400 border-red-500/30',
      PERFORMANCE: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
      MAINTENANCE: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
      STANDARD_WORK: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
    };
    return classes[category as keyof typeof classes] || 'bg-slate-500/15 text-slate-400 border-slate-500/30';
  };

  const getPriorityBadge = (priority: number) => {
    if (priority === 1) return 'bg-gradient-to-br from-red-500 to-red-600 shadow-glow-red border border-red-500/30';
    if (priority === 2) return 'bg-gradient-to-br from-amber-500 to-amber-600 shadow-glow-amber border border-amber-500/30';
    return 'bg-gradient-to-br from-blue-500 to-blue-600 shadow-glow-blue border border-blue-500/30';
  };

  const getOriginIcon = (origin: string) => {
    switch (origin) {
      case 'SYSTEM_DATA':
        return '📊';
      case 'HEURISTIC_REASONING':
        return '🧠';
      case 'BEST_PRACTICE':
        return '🏭';
      case 'DATA_GAP':
        return '⚠️';
      default:
        return '📋';
    }
  };

  const getConfidenceBadge = (confidence: string) => {
    const classes = {
      LOW: 'bg-red-500/15 text-red-400 border-red-500/30',
      MEDIUM: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
      MEDIUM_HIGH: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
      HIGH: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    };
    return classes[confidence as keyof typeof classes] || classes.MEDIUM;
  };

  if (isLoading) {
    return (
      <div className="glass-card-strong p-6">
        <div className="flex items-center gap-3 text-slate-400">
          <Loader2 size={24} className="animate-spin text-accent-400" />
          <span className="font-medium">A carregar insights do COPILOT...</span>
        </div>
      </div>
    );
  }

  if (!insights) {
    return null;
  }

  // Estado vazio: se não houver CRITICAL/WARN, mostrar 1 item INFO
  const hasCriticalOrWarn = insights.now.some((item) => item.severity === 'CRITICAL' || item.severity === 'WARN');
  const nowItems = hasCriticalOrWarn
    ? insights.now
    : [
        {
          id: 'empty-state',
          severity: 'INFO' as const,
          title: 'Tudo está sob controlo neste momento',
          text: 'Não há alertas críticos ou avisos no momento.',
          citations: [],
          suggested_runbooks: [],
          suggested_actions: [],
        },
      ];

  return (
    <div className="glass-card-strong p-6 transition-all duration-300">
      {/* Header */}
      <div className="flex items-start justify-between mb-6 pb-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-3 flex-1">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent-500 to-accent-600 flex items-center justify-center shadow-glow-teal border border-accent-500/30">
            <Bot size={24} className="text-white" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-xl font-bold text-slate-100 tracking-tight">COPILOT INSIGHTS</h3>
              <span className="px-2 py-0.5 bg-emerald-500/15 text-emerald-400 text-xs font-semibold rounded-full border border-emerald-500/30">
                LIVE
              </span>
            </div>
            <p className="text-sm text-slate-500">O que merece atenção agora e o que melhorar a seguir</p>
          </div>
        </div>
        <div className="text-xs text-slate-600 italic">
          Insights gerados pelo COPILOT
        </div>
      </div>

      {/* Secção A: Agora (Estado Atual) */}
      <div className="mb-8 bg-white/[0.02] rounded-xl p-4 -mx-2 border border-white/[0.04]">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-1 h-8 bg-gradient-to-b from-red-500 to-red-600 rounded-full" />
          <Zap size={18} className="text-red-400" />
          <h4 className="font-bold text-slate-200 text-lg">Agora (Estado Atual)</h4>
        </div>

        <div className="space-y-3">
          {nowItems.map((item) => (
            <div
              key={item.id}
              className="bg-white/[0.03] rounded-xl border border-white/[0.06] hover:border-white/[0.1] transition-all duration-200 overflow-hidden"
            >
              <button
                onClick={() => handleToggleNow(item.id)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="flex-shrink-0">
                    {getSeverityIcon(item.severity || 'INFO')}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold border ${getSeverityBadge(
                        item.severity || 'INFO'
                      )}`}>
                        {item.severity || 'INFO'}
                      </span>
                      <h5 className="font-bold text-slate-200 truncate text-base">{item.title}</h5>
                    </div>
                    <p className="text-sm text-slate-500 truncate leading-relaxed">{item.text || item.description}</p>
                  </div>
                </div>
                <div className="flex-shrink-0 ml-2">
                  {expandedNow.has(item.id) ? (
                    <ChevronUp size={20} className="text-slate-500 transition-transform duration-200" />
                  ) : (
                    <ChevronDown size={20} className="text-slate-500 transition-transform duration-200" />
                  )}
                </div>
              </button>

              {expandedNow.has(item.id) && (
                <div className="px-4 pb-4 pt-0 border-t border-white/[0.06] space-y-3">
                  {/* Citations */}
                  {item.citations && item.citations.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2">Citações:</p>
                      <div className="flex flex-wrap gap-1">
                        {item.citations.map((citation, idx) => (
                          <span
                            key={idx}
                            className="text-xs px-2 py-0.5 bg-white/[0.05] rounded-lg text-slate-400 border border-white/[0.06]"
                          >
                            {citation.label || citation.ref}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Suggested Actions */}
                  {item.suggested_actions && item.suggested_actions.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2">Ações sugeridas:</p>
                      <ul className="space-y-1">
                        {item.suggested_actions.map((action, idx) => (
                          <li key={idx} className="text-xs text-slate-500 flex items-start gap-2">
                            <CheckCircle2 size={12} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                            <span>{action}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Buttons */}
                  <div className="flex gap-2 pt-3">
                    {item.suggested_runbooks && item.suggested_runbooks.length > 0 && (
                      <button className="text-xs px-3 py-2 bg-white/[0.05] hover:bg-white/[0.08] rounded-xl text-slate-400 flex items-center gap-1.5 font-medium transition-all duration-150 border border-white/[0.06]">
                        <BookOpen size={14} />
                        Abrir Runbook
                      </button>
                    )}
                    <button
                      onClick={() => handleOpenInCopilot(item, 'alert')}
                      className="text-xs px-3 py-2 bg-accent-500/15 hover:bg-accent-500/25 rounded-xl text-accent-400 flex items-center gap-1.5 font-semibold transition-all duration-150 border border-accent-500/30"
                    >
                      <MessageSquare size={14} />
                      Abrir no Copilot
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Secção B: Próximos Passos (Melhoria) */}
      <div className="bg-blue-500/[0.03] rounded-xl p-4 -mx-2 border border-blue-500/10">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-1 h-8 bg-gradient-to-b from-blue-500 to-blue-600 rounded-full" />
          <Target size={18} className="text-blue-400" />
          <h4 className="font-bold text-slate-200 text-lg">Próximos Passos (Melhoria)</h4>
        </div>

        <div className="space-y-3">
          {insights.next.map((item) => (
            <div
              key={item.id}
              className="bg-white/[0.03] rounded-xl border border-white/[0.06] hover:border-white/[0.1] transition-all duration-200 overflow-hidden"
            >
              <button
                onClick={() => handleToggleNext(item.id)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm ${getPriorityBadge(item.priority || 999)}`}>
                    {item.priority || '?'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold border ${getCategoryBadge(
                        item.category || 'GENERAL'
                      )}`}>
                        {item.category || 'GENERAL'}
                      </span>
                      <h5 className="font-bold text-slate-200 text-base">{item.title}</h5>
                    </div>
                    <p className="text-sm text-slate-500 truncate leading-relaxed">{item.description}</p>
                  </div>
                </div>
                <div className="flex-shrink-0 ml-2">
                  {expandedNext.has(item.id) ? (
                    <ChevronUp size={20} className="text-slate-500 transition-transform duration-200" />
                  ) : (
                    <ChevronDown size={20} className="text-slate-500 transition-transform duration-200" />
                  )}
                </div>
              </button>

              {expandedNext.has(item.id) && (
                <div className="px-4 pb-4 pt-0 border-t border-white/[0.06] space-y-3">
                  {/* Origem */}
                  {item.origins && item.origins.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2">Origem:</p>
                      <div className="flex flex-wrap gap-2">
                        {item.origins.map((origin, idx) => (
                          <span
                            key={idx}
                            className="text-xs px-2 py-0.5 bg-white/[0.05] rounded-lg text-slate-400 flex items-center gap-1 border border-white/[0.06]"
                          >
                            <span>{getOriginIcon(origin)}</span>
                            {origin}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Confiança */}
                  {item.confidence && (
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2">Confiança:</p>
                      <span className={`text-xs px-2.5 py-1 rounded-lg border ${getConfidenceBadge(item.confidence)}`}>
                        {item.confidence}
                      </span>
                    </div>
                  )}

                  {/* Limitações */}
                  {item.limitations && item.limitations.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2">Limitações:</p>
                      <ul className="space-y-1">
                        {item.limitations.map((limitation, idx) => (
                          <li key={idx} className="text-xs text-slate-500 flex items-start gap-2">
                            <AlertCircle size={12} className="text-amber-400 mt-0.5 flex-shrink-0" />
                            <span>{limitation}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Próximo Passo */}
                  {item.next_steps && item.next_steps.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2">Próximo passo:</p>
                      <div className="flex flex-wrap gap-1">
                        {item.next_steps.map((step, idx) => (
                          <span
                            key={idx}
                            className="text-xs px-2 py-0.5 bg-blue-500/15 rounded-lg text-blue-400 border border-blue-500/30"
                          >
                            {step}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Ações Sugeridas */}
                  {item.suggested_actions && item.suggested_actions.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2">Ações sugeridas:</p>
                      <ul className="space-y-1">
                        {item.suggested_actions.map((action, idx) => (
                          <li key={idx} className="text-xs text-slate-500 flex items-start gap-2">
                            <CheckCircle2 size={12} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                            <span>{action}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Fases Afetadas */}
                  {item.affected_phases && item.affected_phases.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-400 mb-2">Fases afetadas:</p>
                      <div className="flex flex-wrap gap-1">
                        {item.affected_phases.map((phase, idx) => (
                          <span
                            key={idx}
                            className="text-xs px-2 py-0.5 bg-white/[0.05] rounded-lg text-slate-400 border border-white/[0.06]"
                          >
                            {phase}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* LLM Explanation */}
                  {explanations[item.id] && (
                    <div className={`rounded-xl p-3 border ${
                      explanations[item.id].type === 'ERROR'
                        ? 'bg-red-500/10 border-red-500/30'
                        : 'bg-white/[0.03] border-white/[0.06]'
                    }`}>
                      <div className="flex items-center gap-2 mb-2">
                        <Bot size={14} className={explanations[item.id].type === 'ERROR' ? 'text-red-400' : 'text-accent-400'} />
                        <span className={`text-xs font-semibold ${
                          explanations[item.id].type === 'ERROR' ? 'text-red-400' : 'text-slate-300'
                        }`}>
                          Explicação COPILOT
                        </span>
                      </div>
                      <p className={`text-xs leading-relaxed ${
                        explanations[item.id].type === 'ERROR' ? 'text-red-400' : 'text-slate-400'
                      }`}>
                        {explanations[item.id].summary}
                      </p>
                      {explanations[item.id].warnings && explanations[item.id].warnings.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {explanations[item.id].warnings.map((warning: any, wIdx: number) => (
                            <p key={wIdx} className="text-xs text-red-400 pl-4 border-l-2 border-red-500/50">
                              ⚠️ {warning.message}
                            </p>
                          ))}
                        </div>
                      )}
                      {explanations[item.id].facts && explanations[item.id].facts.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {explanations[item.id].facts.map((fact: any, fIdx: number) => (
                            <p key={fIdx} className="text-xs text-slate-500 pl-4 border-l-2 border-slate-600">
                              • {fact.text}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Buttons */}
                  <div className="flex gap-2 pt-3">
                    <button
                      onClick={() => handleExplainRecommendation(item)}
                      disabled={loadingExplanation.has(item.id)}
                      className="text-xs px-3 py-2 bg-accent-500/15 hover:bg-accent-500/25 rounded-xl text-accent-400 flex items-center gap-1.5 font-semibold transition-all duration-150 border border-accent-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {loadingExplanation.has(item.id) ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <MessageSquare size={14} />
                      )}
                      Pedir explicação ao Copilot
                    </button>
                    <button className="text-xs px-3 py-2 bg-white/[0.05] hover:bg-white/[0.08] rounded-xl text-slate-400 flex items-center gap-1.5 font-medium transition-all duration-150 border border-white/[0.06]">
                      <TrendingUp size={14} />
                      Criar PR
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
