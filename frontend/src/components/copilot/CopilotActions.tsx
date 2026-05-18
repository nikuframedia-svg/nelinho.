/**
 * CopilotActions
 * ==============
 *
 * Render ÚNICO das acções propostas pelo Copilot (Q.35.4.1 — antes o
 * `CopilotMessage` montava isto E um `ActionWrapper` separado, duas
 * secções para as mesmas acções). Cada acção tem até três botões:
 *
 *   - Simular  → abre o Digital Twin com a acção pré-carregada.
 *   - Dry-run  → corre a acção em modo simulação (não persiste).
 *   - Executar → corre a acção a sério (só se não exigir aprovação).
 *
 * Q.35.4.2 — a mutação tem `onError`: uma falha (401, 500, runbook
 * inexistente) aparece num banner, nunca um `console.error` silencioso.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, FileText, Navigation, BookOpen, FlaskConical, AlertTriangle } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { copilotApi } from '../../lib/api';

interface CopilotAction {
  action_type: string;
  label: string;
  requires_approval: boolean;
  payload: any;
}

interface CopilotActionsProps {
  actions: CopilotAction[];
  suggestionId: string;
}

export function CopilotActions({ actions, suggestionId }: CopilotActionsProps) {
  const navigate = useNavigate();
  const [result, setResult] = useState<any>(null);

  const actionMutation = useMutation({
    mutationFn: (data: { action_type: string; payload: any }) =>
      copilotApi.action({
        action_type: data.action_type,
        suggestion_id: suggestionId,
        payload: data.payload,
      }),
    onSuccess: (res) => {
      setResult(res);
    },
    onError: () => {
      // Q.35.4.2 — limpar o resultado anterior; o erro mostra-se pelo
      // banner abaixo (actionMutation.isError), nunca em silêncio.
      setResult(null);
    },
  });

  if (!actions || actions.length === 0) return null;

  const getIcon = (actionType: string) => {
    switch (actionType) {
      case 'CREATE_DECISION_PR':
        return <FileText size={16} />;
      case 'DRY_RUN':
        return <Play size={16} />;
      case 'OPEN_ENTITY':
        return <Navigation size={16} />;
      case 'RUN_RUNBOOK':
        return <BookOpen size={16} />;
      default:
        return null;
    }
  };

  const handleSimulate = (action: CopilotAction) => {
    // Q.35.4.3 — o Twin abre o modal de criação quando recebe
    // `?action=new`; passamos a descrição para pré-preencher o cenário.
    const params = new URLSearchParams({
      action: 'new',
      source: 'copilot',
      description: action.label,
    });
    navigate(`/twin?${params.toString()}`);
  };

  const handleAction = (action: CopilotAction, isDryRun: boolean) => {
    if (isDryRun && action.action_type !== 'DRY_RUN') {
      actionMutation.mutate({
        action_type: 'DRY_RUN',
        payload: { original_action: action.action_type, ...action.payload },
      });
    } else {
      actionMutation.mutate({
        action_type: action.action_type,
        payload: action.payload,
      });
    }
  };

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-bold text-slate-800 uppercase tracking-wide">
        Acções Sugeridas
      </h4>
      {actions.map((action, idx) => (
        <div
          key={idx}
          className="p-3 bg-slate-50/80 border border-slate-200/60 rounded-xl space-y-2"
        >
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-white border border-slate-200 flex items-center justify-center flex-shrink-0">
              {getIcon(action.action_type)}
            </div>
            <p className="text-sm font-medium text-slate-800 flex-1">{action.label}</p>
            <span className="text-xs text-slate-500">{action.action_type}</span>
            {action.requires_approval && (
              <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">
                Requer aprovação
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => handleSimulate(action)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-xs font-medium rounded-lg transition-colors"
            >
              <FlaskConical size={12} />
              Simular
            </button>
            <button
              onClick={() => handleAction(action, true)}
              disabled={actionMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              <Play size={12} />
              Dry-run
            </button>
            {!action.requires_approval && (
              <button
                onClick={() => handleAction(action, false)}
                disabled={actionMutation.isPending}
                className="px-4 py-1.5 bg-gradient-to-br from-[#1a2744] to-[#2d4a7c] hover:from-[#2d4a7c] hover:to-[#3d5a9c] text-white text-xs font-semibold rounded-lg transition-all disabled:opacity-50"
              >
                {actionMutation.isPending ? 'A correr…' : 'Executar'}
              </button>
            )}
          </div>
        </div>
      ))}

      {actionMutation.isError && (
        <div className="p-3 bg-red-50 border border-red-200/60 rounded-xl flex items-start gap-2">
          <AlertTriangle size={14} className="text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-800">A acção falhou</p>
            <p className="text-xs text-red-600/90 mt-0.5">
              {(actionMutation.error as Error)?.message || 'Erro desconhecido'}
            </p>
          </div>
        </div>
      )}

      {result && (
        <div className="p-4 bg-gradient-to-r from-blue-50 to-cyan-50 border border-blue-200/60 rounded-xl text-sm shadow-sm">
          <p className="font-semibold text-blue-900 mb-1">Resultado:</p>
          <p className="text-blue-700 leading-relaxed">
            {result.message || JSON.stringify(result)}
          </p>
        </div>
      )}
    </div>
  );
}
