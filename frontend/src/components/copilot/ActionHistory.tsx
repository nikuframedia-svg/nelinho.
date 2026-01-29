import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { RefreshCw, AlertTriangle, CheckCircle2, XCircle, Clock, Undo2 } from 'lucide-react';
import { copilotApi } from '../../lib/api';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';

interface ActionLog {
  transaction_id: string;
  action_type: string;
  user_id: string;
  plan_id: string | null;
  before_state: Record<string, any>;
  after_state: Record<string, any>;
  status: 'executed' | 'failed' | 'rolled_back';
  executed_at: string;
  rollback_until: string | null;
}

interface ActionHistoryProps {
  className?: string;
}

export function ActionHistory({ className }: ActionHistoryProps) {
  const [selectedAction, setSelectedAction] = useState<ActionLog | null>(null);
  
  // Fetch action logs
  const { data: actions, isLoading, error, refetch } = useQuery<ActionLog[]>({
    queryKey: ['copilot', 'actions'],
    queryFn: () => copilotApi.listActions({ limit: 50, status: 'executed' }),
    retry: false,
    refetchInterval: 60000, // Refresh every minute
  });

  // Rollback mutation
  const rollbackMutation = useMutation({
    mutationFn: (transactionId: string) => copilotApi.rollbackAction(transactionId),
    onSuccess: () => {
      refetch();
      setSelectedAction(null);
    },
  });

  const handleRollback = (action: ActionLog) => {
    if (!window.confirm(`Tens a certeza que queres reverter esta ação?\n\nTipo: ${action.action_type}\nID: ${action.transaction_id}`)) {
      return;
    }
    rollbackMutation.mutate(action.transaction_id);
  };

  const canRollback = (action: ActionLog): boolean => {
    if (action.status !== 'executed') return false;
    if (!action.rollback_until) return false;
    const rollbackUntil = new Date(action.rollback_until);
    return new Date() < rollbackUntil;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'executed':
        return <CheckCircle2 size={16} className="text-green-600" />;
      case 'failed':
        return <XCircle size={16} className="text-red-600" />;
      case 'rolled_back':
        return <Undo2 size={16} className="text-amber-600" />;
      default:
        return <Clock size={16} className="text-slate-400" />;
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'executed':
        return 'Executada';
      case 'failed':
        return 'Falhou';
      case 'rolled_back':
        return 'Revertida';
      default:
        return status;
    }
  };

  if (error && (error as any).status !== 404) {
    return (
      <Card className={className}>
        <div className="p-6 text-center">
          <AlertTriangle size={32} className="text-red-500 mx-auto mb-2" />
          <p className="text-sm text-red-600 mb-2">Erro ao carregar histórico de ações.</p>
          <Button onClick={() => refetch()} variant="ghost" size="sm">
            <RefreshCw size={14} className="mr-2" />
            Tentar novamente
          </Button>
        </div>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card className={className}>
        <div className="p-6 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="text-sm text-slate-500 mt-2">A carregar histórico de ações...</p>
        </div>
      </Card>
    );
  }

  if (!actions || actions.length === 0) {
    return (
      <Card className={className}>
        <div className="p-6 text-center">
          <Clock size={32} className="text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-500 mb-1">Nenhuma ação ainda.</p>
          <p className="text-xs text-slate-400">
            As ações executadas pelo COPILOT aparecerão aqui.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <div className={className}>
      <Card>
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-slate-900">Histórico de Ações</h3>
            <Button onClick={() => refetch()} variant="ghost" size="sm">
              <RefreshCw size={14} className="mr-2" />
              Atualizar
            </Button>
          </div>
          
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {actions.map((action) => {
              const canUndo = canRollback(action);
              const isRollingBack = rollbackMutation.isPending && rollbackMutation.variables === action.transaction_id;
              
              return (
                <div
                  key={action.transaction_id}
                  className="p-4 border border-slate-200 rounded-lg hover:border-slate-300 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        {getStatusIcon(action.status)}
                        <span className="font-medium text-slate-900">{action.action_type}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          action.status === 'executed' ? 'bg-green-100 text-green-700' :
                          action.status === 'failed' ? 'bg-red-100 text-red-700' :
                          'bg-amber-100 text-amber-700'
                        }`}>
                          {getStatusLabel(action.status)}
                        </span>
                      </div>
                      
                      <div className="text-xs text-slate-500 space-y-1">
                        <p>Executada em: {new Date(action.executed_at).toLocaleString('pt-PT')}</p>
                        {action.rollback_until && canUndo && (
                          <p className="text-amber-600">
                            Reversão disponível até: {new Date(action.rollback_until).toLocaleString('pt-PT')}
                          </p>
                        )}
                        {action.rollback_until && !canUndo && (
                          <p className="text-slate-400">
                            Janela de reversão expirada
                          </p>
                        )}
                      </div>
                      
                      {selectedAction?.transaction_id === action.transaction_id && (
                        <div className="mt-3 p-3 bg-slate-50 rounded border border-slate-200 text-xs">
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <p className="font-medium text-slate-700 mb-1">Estado Antes:</p>
                              <pre className="bg-white p-2 rounded text-xs overflow-auto max-h-32">
                                {JSON.stringify(action.before_state, null, 2)}
                              </pre>
                            </div>
                            <div>
                              <p className="font-medium text-slate-700 mb-1">Estado Depois:</p>
                              <pre className="bg-white p-2 rounded text-xs overflow-auto max-h-32">
                                {JSON.stringify(action.after_state, null, 2)}
                              </pre>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                    
                    <div className="flex items-start gap-2 flex-shrink-0">
                      <Button
                        onClick={() => setSelectedAction(
                          selectedAction?.transaction_id === action.transaction_id ? null : action
                        )}
                        variant="ghost"
                        size="sm"
                      >
                        {selectedAction?.transaction_id === action.transaction_id ? 'Ocultar' : 'Detalhes'}
                      </Button>
                      
                      {canUndo && (
                        <Button
                          onClick={() => handleRollback(action)}
                          disabled={isRollingBack}
                          variant="ghost"
                          size="sm"
                          className="text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                        >
                          {isRollingBack ? (
                            <>
                              <RefreshCw size={14} className="mr-1 animate-spin" />
                              A reverter...
                            </>
                          ) : (
                            <>
                              <Undo2 size={14} className="mr-1" />
                              Reverter
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </Card>
    </div>
  );
}







