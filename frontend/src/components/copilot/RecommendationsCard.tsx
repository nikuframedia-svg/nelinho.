import { useState } from 'react';
import { Sparkles, ArrowRight, Bot, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { copilotApi } from '../../lib/api';
import type { CopilotResponse } from '../../lib/api';

interface Recommendation {
  priority: number;
  category: string;
  title: string;
  description: string;
  impact_metric: string;
  impact_value: number;
  affected_phases: string[];
  suggested_actions: string[];
  data_evidence: Record<string, any>;
}

export function RecommendationsCard() {
  const [expandedRecommendation, setExpandedRecommendation] = useState<number | null>(null);
  const [explanation, setExplanation] = useState<Record<number, CopilotResponse>>({});
  const [loadingExplanation, setLoadingExplanation] = useState<Record<number, boolean>>({});

  const { data: recommendations, isLoading } = useQuery<Recommendation[]>({
    queryKey: ['copilot', 'recommendations'],
    queryFn: () => copilotApi.getRecommendations(),
    staleTime: 10 * 60 * 1000, // 10 minutos
    retry: false,
  });

  const explainMutation = useMutation({
    mutationFn: (data: { recommendations: Recommendation[]; user_query?: string }) =>
      copilotApi.explainRecommendations(data),
    onSuccess: (response) => {
      // Guardar explicação para a recomendação expandida
      const index = expandedRecommendation;
      if (index !== null) {
        setExplanation((prev) => ({ ...prev, [index]: response }));
      }
    },
  });

  const handleToggleRecommendation = async (index: number) => {
    if (expandedRecommendation === index) {
      setExpandedRecommendation(null);
    } else {
      setExpandedRecommendation(index);
      
      // Se ainda não há explicação, pedir ao LLM
      if (!explanation[index] && recommendations) {
        setLoadingExplanation((prev) => ({ ...prev, [index]: true }));
        try {
          await explainMutation.mutateAsync({
            recommendations: [recommendations[index]],
            user_query: `Explica-me esta recomendação em detalhe: "${recommendations[index].title}". Como implementá-la e qual o impacto esperado?`,
          });
        } catch (error) {
          console.error('Erro ao obter explicação:', error);
        } finally {
          setLoadingExplanation((prev) => ({ ...prev, [index]: false }));
        }
      }
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'QUALITY':
        return 'from-red-400 to-red-600';
      case 'PERFORMANCE':
        return 'from-amber-400 to-amber-600';
      case 'MAINTENANCE':
        return 'from-blue-400 to-blue-600';
      case 'STANDARD_WORK':
        return 'from-purple-400 to-purple-600';
      default:
        return 'from-slate-400 to-slate-600';
    }
  };

  const getCategoryBadge = (category: string) => {
    const colors = {
      QUALITY: 'bg-red-100 text-red-800 border-red-200',
      PERFORMANCE: 'bg-amber-100 text-amber-800 border-amber-200',
      MAINTENANCE: 'bg-blue-100 text-blue-800 border-blue-200',
      STANDARD_WORK: 'bg-purple-100 text-purple-800 border-purple-200',
    };
    return colors[category as keyof typeof colors] || 'bg-slate-100 text-slate-800 border-slate-200';
  };

  if (isLoading) {
    return (
      <div className="bg-gradient-to-br from-slate-800 via-slate-900 to-slate-800 rounded-2xl p-6 border border-slate-700">
        <div className="flex items-center gap-2 text-slate-400">
          <Loader2 size={20} className="animate-spin" />
          <span>A carregar recomendações...</span>
        </div>
      </div>
    );
  }

  if (!recommendations || recommendations.length === 0) {
    return null;
  }

  return (
    <div className="bg-gradient-to-br from-slate-800 via-slate-900 to-slate-800 rounded-2xl p-6 border border-slate-700 shadow-xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#FF6B6B] to-red-600 flex items-center justify-center shadow-lg">
          <Sparkles size={20} className="text-white" />
        </div>
        <div>
          <h3 className="text-xl font-bold text-white">Ações Recomendadas</h3>
          <p className="text-sm text-slate-300">Baseadas em análise de dados OEE</p>
        </div>
      </div>

      <div className="space-y-4">
        {recommendations.map((rec, index) => (
          <div
            key={index}
            className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/20 hover:bg-white/15 transition-all"
          >
            <div className="flex items-start gap-3">
              {/* Priority Number */}
              <div
                className={`w-8 h-8 rounded-full bg-gradient-to-br ${getCategoryColor(
                  rec.category
                )} flex items-center justify-center text-white font-bold text-sm shadow-lg flex-shrink-0`}
              >
                {rec.priority}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-semibold text-white">{rec.title}</span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium border ${getCategoryBadge(
                      rec.category
                    )}`}
                  >
                    {rec.category}
                  </span>
                  <button
                    onClick={() => handleToggleRecommendation(index)}
                    className="ml-auto p-1 hover:bg-white/20 rounded transition-colors"
                    title={expandedRecommendation === index ? 'Recolher' : 'Expandir'}
                  >
                    {expandedRecommendation === index ? (
                      <ChevronUp size={16} className="text-white" />
                    ) : (
                      <ChevronDown size={16} className="text-white" />
                    )}
                  </button>
                </div>

                <p className="text-sm text-white/80 leading-relaxed mb-2">{rec.description}</p>

                {/* Expanded Content */}
                {expandedRecommendation === index && (
                  <div className="mt-4 pt-4 border-t border-white/20 space-y-3">
                    {/* LLM Explanation */}
                    {loadingExplanation[index] ? (
                      <div className="flex items-center gap-2 text-white/60 text-sm">
                        <Loader2 size={14} className="animate-spin" />
                        <span>A obter explicação do COPILOT...</span>
                      </div>
                    ) : explanation[index] ? (
                      <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                        <div className="flex items-center gap-2 mb-2">
                          <Bot size={14} className="text-[#FF6B6B]" />
                          <span className="text-xs font-semibold text-white/90">Explicação COPILOT</span>
                        </div>
                        <p className="text-sm text-white/80 leading-relaxed">
                          {explanation[index].summary}
                        </p>
                        {explanation[index].facts && explanation[index].facts.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {explanation[index].facts.map((fact: any, fIdx: number) => (
                              <p key={fIdx} className="text-xs text-white/70 pl-4 border-l-2 border-white/20">
                                • {fact.text}
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : null}

                    {/* Affected Phases */}
                    {rec.affected_phases && rec.affected_phases.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-white/70 mb-1">Fases Afetadas:</p>
                        <div className="flex flex-wrap gap-1">
                          {rec.affected_phases.map((phase, pIdx) => (
                            <span
                              key={pIdx}
                              className="px-2 py-0.5 bg-white/10 rounded text-xs text-white/80"
                            >
                              {phase}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Suggested Actions */}
                    {rec.suggested_actions && rec.suggested_actions.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-white/70 mb-1">Ações Sugeridas:</p>
                        <ul className="space-y-1">
                          {rec.suggested_actions.map((action, aIdx) => (
                            <li key={aIdx} className="text-xs text-white/70 flex items-start gap-2">
                              <ArrowRight size={12} className="text-white/50 mt-0.5 flex-shrink-0" />
                              <span>{action}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Impact Metric */}
                    <div className="text-xs text-white/60">
                      Impacto: <span className="font-semibold text-white/80">{rec.impact_metric}</span> ={' '}
                      <span className="font-semibold text-white/80">{rec.impact_value.toFixed(1)}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

