/**
 * DecisionPRsPage (Sprint Q.37.C)
 * ================================
 *
 * `/admin/decision-prs` — painel de Decision PRs do copiloto.
 *
 * O copiloto PROPÕE (cria um CopilotDecisionPR em PENDING via a acção
 * CREATE_DECISION_PR). Um humano APROVA (com Segregation of Duties — o
 * aprovador não pode ser o proponente) e só DEPOIS há EXECUÇÃO via o
 * ActionExecutor (invariante 4 — aprovação humana antes da execução).
 *
 * Composição estilo RegrasPage: split-pane (lista à esquerda, detalhe
 * + acções à direita). Dark theme, PT-PT, ZERO MOCKS — todos os dados
 * vêm da API real (`copilotApi.listDecisionPRs` etc.).
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  GitPullRequest,
  CheckCircle2,
  XCircle,
  Play,
  Clock,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkButton, DarkBadge } from '../../components/dark';
import { copilotApi, type DecisionPR, type DecisionPRStatus } from '../../lib/api';

// ─── Mapeamento visual de status ──────────────────────────────────────────

const STATUS_VARIANTS: Record<
  DecisionPRStatus,
  'success' | 'warning' | 'danger' | 'info'
> = {
  PENDING: 'warning',
  APPROVED: 'info',
  REJECTED: 'danger',
  EXECUTED: 'success',
};

const STATUS_LABELS: Record<DecisionPRStatus, string> = {
  PENDING: 'Pendente',
  APPROVED: 'Aprovado',
  REJECTED: 'Rejeitado',
  EXECUTED: 'Executado',
};

const STATUS_FILTERS: Array<{ value: string; label: string }> = [
  { value: '', label: 'Todos' },
  { value: 'PENDING', label: 'Pendentes' },
  { value: 'APPROVED', label: 'Aprovados' },
  { value: 'EXECUTED', label: 'Executados' },
  { value: 'REJECTED', label: 'Rejeitados' },
];

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export default function DecisionPRsPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const {
    data: prs,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['decision-prs', statusFilter],
    queryFn: () => copilotApi.listDecisionPRs(statusFilter || undefined),
  });

  const selected: DecisionPR | undefined = (prs ?? []).find(
    (p) => p.id === selectedId
  );

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['decision-prs'] });
  };

  const approveMutation = useMutation({
    mutationFn: (id: string) => copilotApi.approveDecisionPR(id),
    onSuccess: invalidate,
  });
  const rejectMutation = useMutation({
    mutationFn: (id: string) => copilotApi.rejectDecisionPR(id),
    onSuccess: invalidate,
  });
  const executeMutation = useMutation({
    mutationFn: (id: string) => copilotApi.executeDecisionPR(id),
    onSuccess: invalidate,
  });

  const busy =
    approveMutation.isPending ||
    rejectMutation.isPending ||
    executeMutation.isPending;

  const actionError =
    (approveMutation.error as Error | null) ||
    (rejectMutation.error as Error | null) ||
    (executeMutation.error as Error | null);

  return (
    <DarkPageLayout
      title="Decision PRs do Copiloto"
      subtitle="O copiloto propõe, um humano aprova, e só depois há execução."
    >
      {/* Filtros de status */}
      <div className="mb-6 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value || 'all'}
            onClick={() => setStatusFilter(f.value)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              statusFilter === f.value
                ? 'bg-teal-600 text-white'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* ── Lista ─────────────────────────────────────────────── */}
        <DarkCard>
          <div className="mb-4 flex items-center gap-2">
            <GitPullRequest className="h-5 w-5 text-teal-400" />
            <h2 className="text-lg font-semibold text-slate-100">
              Propostas ({prs?.length ?? 0})
            </h2>
          </div>

          {isLoading && (
            <div className="flex items-center gap-2 py-8 text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              A carregar Decision PRs…
            </div>
          )}

          {isError && (
            <div className="flex items-start gap-2 rounded-lg bg-rose-900/30 p-4 text-rose-300">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span>
                Falha ao carregar:{' '}
                {(error as Error)?.message ?? 'erro desconhecido'}
              </span>
            </div>
          )}

          {!isLoading && !isError && (prs?.length ?? 0) === 0 && (
            <div className="py-8 text-center text-slate-400">
              Sem Decision PRs
              {statusFilter ? ` com status ${STATUS_LABELS[statusFilter as DecisionPRStatus] ?? statusFilter}` : ''}.
            </div>
          )}

          <div className="space-y-2">
            {(prs ?? []).map((pr) => (
              <button
                key={pr.id}
                onClick={() => setSelectedId(pr.id)}
                className={`w-full rounded-lg border p-3 text-left transition-colors ${
                  selectedId === pr.id
                    ? 'border-teal-500 bg-slate-800'
                    : 'border-slate-700 bg-slate-900 hover:bg-slate-800'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium text-slate-100">
                    {pr.title}
                  </span>
                  <DarkBadge variant={STATUS_VARIANTS[pr.status]}>
                    {STATUS_LABELS[pr.status]}
                  </DarkBadge>
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
                  <Clock className="h-3 w-3" />
                  {formatDate(pr.created_at)}
                  {pr.action_type && (
                    <span className="font-mono text-slate-500">
                      · {pr.action_type}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </DarkCard>

        {/* ── Detalhe + acções ──────────────────────────────────── */}
        <DarkCard>
          {!selected && (
            <div className="flex h-full min-h-[16rem] items-center justify-center text-slate-400">
              Selecciona um Decision PR para ver o detalhe.
            </div>
          )}

          {selected && (
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-lg font-semibold text-slate-100">
                  {selected.title}
                </h2>
                <DarkBadge variant={STATUS_VARIANTS[selected.status]}>
                  {STATUS_LABELS[selected.status]}
                </DarkBadge>
              </div>

              <p className="text-sm text-slate-300">{selected.description}</p>

              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <dt className="text-slate-400">Tipo de acção</dt>
                <dd className="font-mono text-slate-200">
                  {selected.action_type ?? '—'}
                </dd>
                <dt className="text-slate-400">Criado</dt>
                <dd className="text-slate-200">
                  {formatDate(selected.created_at)}
                </dd>
                <dt className="text-slate-400">Aprovado por</dt>
                <dd className="text-slate-200">
                  {selected.approved_by ?? '—'}
                </dd>
                <dt className="text-slate-400">Executado por</dt>
                <dd className="text-slate-200">
                  {selected.executed_by ?? '—'}
                </dd>
              </dl>

              {/* Payload da decisão */}
              <div>
                <h3 className="mb-1 text-sm font-medium text-slate-300">
                  Payload
                </h3>
                <pre className="max-h-48 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
                  {JSON.stringify(selected.payload, null, 2)}
                </pre>
              </div>

              {/* Resultado de execução, se houver */}
              {selected.execution_result && (
                <div>
                  <h3 className="mb-1 text-sm font-medium text-slate-300">
                    Resultado da execução
                  </h3>
                  <pre className="max-h-48 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-emerald-300">
                    {JSON.stringify(selected.execution_result, null, 2)}
                  </pre>
                </div>
              )}

              {actionError && (
                <div className="flex items-start gap-2 rounded-lg bg-rose-900/30 p-3 text-sm text-rose-300">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                  <span>{actionError.message}</span>
                </div>
              )}

              {/* Acções por status */}
              <div className="flex flex-wrap gap-2 border-t border-slate-700 pt-4">
                {selected.status === 'PENDING' && (
                  <>
                    <DarkButton
                      variant="primary"
                      disabled={busy}
                      onClick={() => approveMutation.mutate(selected.id)}
                    >
                      <CheckCircle2 className="mr-1 h-4 w-4" />
                      Aprovar
                    </DarkButton>
                    <DarkButton
                      variant="danger"
                      disabled={busy}
                      onClick={() => rejectMutation.mutate(selected.id)}
                    >
                      <XCircle className="mr-1 h-4 w-4" />
                      Rejeitar
                    </DarkButton>
                  </>
                )}
                {selected.status === 'APPROVED' && (
                  <DarkButton
                    variant="primary"
                    disabled={busy}
                    onClick={() => executeMutation.mutate(selected.id)}
                  >
                    <Play className="mr-1 h-4 w-4" />
                    Executar
                  </DarkButton>
                )}
                {(selected.status === 'EXECUTED' ||
                  selected.status === 'REJECTED') && (
                  <span className="text-sm text-slate-400">
                    Sem acções disponíveis — PR{' '}
                    {STATUS_LABELS[selected.status].toLowerCase()}.
                  </span>
                )}
                {busy && (
                  <Loader2 className="h-5 w-5 animate-spin text-teal-400" />
                )}
              </div>
            </div>
          )}
        </DarkCard>
      </div>
    </DarkPageLayout>
  );
}
