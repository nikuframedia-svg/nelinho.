import { useState } from 'react';
import { Play, FileText, Navigation, BookOpen } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { copilotApi } from '../../lib/api';

interface CopilotActionsProps {
  actions: Array<{
    action_type: string;
    label: string;
    requires_approval: boolean;
    payload: Record<string, unknown>;
  }>;
  suggestionId: string;
}

type ActionResult = { message?: string } & Record<string, unknown>;

export function CopilotActions({ actions, suggestionId }: CopilotActionsProps) {
  const [dryRunResult, setDryRunResult] = useState<ActionResult | null>(null);

  const actionMutation = useMutation({
    mutationFn: (data: { action_type: string; payload: Record<string, unknown> }) =>
      copilotApi.action({
        action_type: data.action_type,
        suggestion_id: suggestionId,
        payload: data.payload,
      }),
    onSuccess: (result) => {
      setDryRunResult(result as ActionResult);
    },
  });

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

  const handleAction = (action: typeof actions[0], isDryRun: boolean = false) => {
    if (isDryRun && action.action_type !== 'DRY_RUN') {
      // Simular dry-run para outras ações
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
      <h4 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Ações Propostas</h4>
      {actions.map((action, idx) => (
        <div key={idx} className="flex items-center gap-2">
          <button
            onClick={() => handleAction(action, true)}
            className="flex-1 flex items-center gap-2.5 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 rounded-xl text-sm font-medium text-slate-700 transition-all duration-150 hover:shadow-sm"
            disabled={actionMutation.isPending}
          >
            <div className="w-6 h-6 rounded-lg bg-white flex items-center justify-center">
              {getIcon(action.action_type)}
            </div>
            <span>Dry-run: {action.label}</span>
          </button>
          {!action.requires_approval && (
            <button
              onClick={() => handleAction(action, false)}
              className="px-5 py-2.5 bg-gradient-to-br from-[#1a2744] to-[#2d4a7c] text-white rounded-xl hover:from-[#2d4a7c] hover:to-[#3d5a9c] text-sm font-semibold transition-all duration-150 disabled:opacity-50 shadow-sm hover:shadow-md"
              disabled={actionMutation.isPending}
            >
              Executar
            </button>
          )}
        </div>
      ))}
      
      {dryRunResult && (
        <div className="mt-3 p-4 bg-gradient-to-r from-blue-50 to-cyan-50 border border-blue-200/60 rounded-xl text-sm shadow-sm">
          <p className="font-semibold text-blue-900 mb-1">Dry-run Resultado:</p>
          <p className="text-blue-700 leading-relaxed">{dryRunResult.message || JSON.stringify(dryRunResult)}</p>
        </div>
      )}
    </div>
  );
}


