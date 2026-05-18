import { useState, useEffect } from 'react';
import { RefreshCw, Bot, AlertTriangle, Info } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { copilotApi } from '../../lib/api';
import type { DailyFeedbackResponse } from '../../lib/api';

export function DailyCopilotFeedbackCard() {
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const queryClient = useQueryClient();

  const { data: feedback, isLoading, error } = useQuery<DailyFeedbackResponse>({
    queryKey: ['copilot', 'daily-feedback'],
    queryFn: () => copilotApi.getDailyFeedback(),
    staleTime: 5 * 60 * 1000, // 5 minutos
    retry: false, // Não tentar novamente se o endpoint não existir
  });

  // Handle query success (React Query v5 pattern)
  useEffect(() => {
    if (feedback && feedback.last_updated) {
      setLastUpdated(new Date(feedback.last_updated).toLocaleTimeString('pt-PT'));
    }
  }, [feedback]);

  const refreshMutation = useMutation({
    mutationFn: () => copilotApi.getDailyFeedback(),
  });

  // Handle refresh mutation success (React Query v5 pattern)
  useEffect(() => {
    if (refreshMutation.isSuccess && refreshMutation.data) {
      const data = refreshMutation.data;
      queryClient.setQueryData(['copilot', 'daily-feedback'], data);
      setLastUpdated(new Date(data.last_updated).toLocaleTimeString('pt-PT'));
    }
  }, [refreshMutation.isSuccess, refreshMutation.data, queryClient]);

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return <AlertTriangle size={16} className="text-red-500" />;
      case 'WARN':
        return <AlertTriangle size={16} className="text-yellow-500" />;
      case 'INFO':
        return <Info size={16} className="text-blue-500" />;
      default:
        return null;
    }
  };

  const getSeverityBadge = (severity: string) => {
    const classes = {
      CRITICAL: 'bg-red-100 text-red-800 border-red-200',
      WARN: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      INFO: 'bg-blue-100 text-blue-800 border-blue-200',
    };
    return classes[severity as keyof typeof classes] || classes.INFO;
  };

  // Q.35.4.4 — abrir o drawer do Copilot (mesmo evento que o resto da app).
  const openInCopilot = (query: string) => {
    window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
  };

  if (isLoading) {
    return (
      <div className="bg-slate-900 rounded-2xl p-6 border border-slate-800">
        <div className="flex items-center gap-2 text-slate-400">
          <Bot size={20} className="animate-pulse" />
          <span>A carregar feedback...</span>
        </div>
      </div>
    );
  }

  // Se houver erro (endpoint não existe), não mostrar o card
  if (error) {
    return null;
  }

  if (!feedback || !feedback.bullets || feedback.bullets.length === 0) {
    return null;
  }

  return (
    <div className="bg-slate-900 rounded-2xl p-6 border border-slate-800 hover:border-slate-700 transition-all">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#FF6B6B]/15 flex items-center justify-center">
            <Bot size={20} className="text-[#FF6B6B]" />
          </div>
          <div>
            <h3 className="font-bold text-lg text-slate-100">Feedback COPILOT Diário</h3>
            <p className="text-sm text-slate-400">
              {lastUpdated && `Última atualização: ${lastUpdated}`}
            </p>
          </div>
        </div>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="p-2 hover:bg-slate-800 rounded-lg transition-colors disabled:opacity-50"
          title="Atualizar"
        >
          <RefreshCw
            size={18}
            className={`text-slate-400 ${refreshMutation.isPending ? 'animate-spin' : ''}`}
          />
        </button>
      </div>

      <div className="space-y-3">
        {feedback.bullets.map((bullet, idx) => (
          <div
            key={idx}
            className="p-3 rounded-lg border border-slate-800 hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-start gap-3">
              {getSeverityIcon(bullet.severity)}
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium border ${getSeverityBadge(
                      bullet.severity
                    )}`}
                  >
                    {bullet.severity}
                  </span>
                  <h4 className="font-semibold text-sm text-slate-100">{bullet.title}</h4>
                </div>
                <p className="text-sm text-slate-300">{bullet.text}</p>

                {bullet.citations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {bullet.citations.map((citation, cIdx) => (
                      <span
                        key={cIdx}
                        className="text-xs px-2 py-0.5 bg-slate-800 rounded text-slate-400"
                      >
                        {citation.label}
                      </span>
                    ))}
                  </div>
                )}

                {bullet.suggested_runbooks.length > 0 && (
                  <div className="mt-2">
                    <button
                      onClick={() => openInCopilot(`Detalha este ponto do feedback diário: "${bullet.title}". ${bullet.text}`)}
                      className="text-xs text-[#FF6B6B] hover:underline"
                    >
                      Abrir no Copilot →
                    </button>
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

