/**
 * DecisoesPage — grelha de decisões pendentes (Q.121.C).
 *
 * Mostra TODAS as decisões PROPOSED ao mesmo tempo numa grelha de cartões
 * (<DecisionCard>), cada um com botões Sim/Não próprios. Antes era um hub
 * estilo Tinder (1 cartão de cada vez); o Luis quer ver várias em simultâneo.
 *
 * Shell de 3 sub-abas: Decidir · Simulações · Histórico (?tab=, useTabRouting).
 */

import { useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Inbox, RefreshCw, FlaskConical, History } from 'lucide-react';
import { decisionKeys } from '../../lib/api/keys';
import { decisionsApi, type DecisionRun } from '../../lib/api';
import { PageHeader, Tabs } from '../../components/dark';
import { useTabRouting } from '../../hooks/useTabRouting';
import SimulacoesTab from './SimulacoesTab';
import HistoricoTab from './HistoricoTab';
import { DecisionCard } from './DecisionCard';
import { useRealtimeType } from '../../providers/RealtimeProvider';

// ─── aba Decidir: grelha de cartões ─────────────────────────────────────────

function DecidirTab() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: decisionKeys.list({ status: 'PROPOSED' }),
    queryFn: () => decisionsApi.list({ status: 'PROPOSED', page_size: 50 }),
    refetchInterval: 5_000,
  });

  const items: DecisionRun[] = query.data?.decisions ?? [];
  const total = items.length;

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: decisionKeys.lists() });
  }, [queryClient]);

  // Realtime SSE (canal governance): push em vez de esperar o polling de 5s.
  useRealtimeType('DECISION_PROPOSED', invalidate);
  useRealtimeType('DECISION_APPROVED', invalidate);
  useRealtimeType('DECISION_EXECUTED', invalidate);
  useRealtimeType('DECISION_REJECTED', invalidate);
  useRealtimeType('DECISION_ROLLED_BACK', invalidate);

  const approveMutation = useMutation({
    mutationFn: (id: string) => decisionsApi.approve(id, { status: 'APPROVED' }),
    onSuccess: invalidate,
  });
  const rejectMutation = useMutation({
    mutationFn: (id: string) => decisionsApi.approve(id, { status: 'REJECTED' }),
    onSuccess: invalidate,
  });
  const isPending = approveMutation.isPending || rejectMutation.isPending;
  const hasError = approveMutation.isError || rejectMutation.isError;

  const header = (
    <PageHeader
      icon={<Inbox size={20} />}
      title="Decisões"
      actions={
        total > 0 ? (
          <span
            className="text-text-dark-tertiary tabular-nums"
            style={{ fontSize: 12 }}
            aria-label={`${total} ${total === 1 ? 'decisão pendente' : 'decisões pendentes'}`}
          >
            {total}&nbsp;{total === 1 ? 'pendente' : 'pendentes'}
          </span>
        ) : null
      }
    />
  );

  if (query.isError) {
    return (
      <div>
        {header}
        <CenteredFrame>
          <div className="text-center space-y-4">
            <p className="text-text-dark-secondary" style={{ fontSize: 14 }}>
              Erro: {(query.error as Error)?.message ?? 'Não foi possível carregar as decisões.'}
            </p>
            <button
              type="button"
              onClick={() => query.refetch()}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-bg-2 border border-bd-1
                         text-text-dark-primary text-sm hover:bg-bg-3 transition-colors"
            >
              <RefreshCw size={14} />
              Tentar novamente
            </button>
          </div>
        </CenteredFrame>
      </div>
    );
  }

  if (query.isLoading) {
    return (
      <div>
        {header}
        <CenteredFrame>
          <div className="text-center text-text-dark-tertiary" style={{ fontSize: 14 }}>
            A carregar decisões…
          </div>
        </CenteredFrame>
      </div>
    );
  }

  if (total === 0) {
    return (
      <div>
        {header}
        <CenteredFrame>
          <div className="text-center space-y-3">
            <Inbox size={40} className="mx-auto text-text-dark-tertiary opacity-40" />
            <p className="text-text-dark-secondary font-medium" style={{ fontSize: 16 }}>
              Sem decisões pendentes
            </p>
            <p className="text-text-dark-tertiary" style={{ fontSize: 13 }}>
              Volta mais tarde — o sistema propõe decisões automaticamente.
            </p>
          </div>
        </CenteredFrame>
      </div>
    );
  }

  return (
    <div>
      {header}
      {hasError ? (
        <div
          className="text-danger px-6 py-2 text-sm"
          role="alert"
          style={{ background: 'var(--red-bg)', borderTop: '1px solid var(--red-bd)' }}
        >
          Não foi possível registar a decisão. Tenta outra vez.
        </div>
      ) : null}
      <div
        className="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start"
        style={{ padding: '20px 24px' }}
      >
        {items.map((d) => (
          <DecisionCard
            key={d.id}
            decision={d}
            onApprove={(id) => approveMutation.mutate(id)}
            onReject={(id) => rejectMutation.mutate(id)}
            isPending={isPending}
          />
        ))}
      </div>
    </div>
  );
}

// ─── layout helper (estados especiais centrados) ────────────────────────────

function CenteredFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        padding: '24px 28px',
        minHeight: 'calc(100vh - 200px)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div style={{ width: '100%', maxWidth: 600 }}>{children}</div>
    </div>
  );
}

// ─── shell de 3 sub-abas ────────────────────────────────────────────────────

const DECISOES_TAB_IDS = ['decidir', 'simulacoes', 'historico'] as const;
type DecisoesTabId = (typeof DECISOES_TAB_IDS)[number];

const DECISOES_TABS = [
  { id: 'decidir', label: 'Decidir', icon: <Inbox size={14} /> },
  { id: 'simulacoes', label: 'Simulações', icon: <FlaskConical size={14} /> },
  { id: 'historico', label: 'Histórico', icon: <History size={14} /> },
];

export default function DecisoesPage() {
  const { activeTab, setTab } = useTabRouting<DecisoesTabId>(
    DECISOES_TAB_IDS,
    'decidir',
  );

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-3">
        <Tabs
          tabs={DECISOES_TABS}
          value={activeTab}
          onChange={(id) => setTab(id as DecisoesTabId)}
        />
      </div>
      <div className="flex-1 min-h-0 overflow-auto">
        {activeTab === 'decidir' && <DecidirTab />}
        {activeTab === 'simulacoes' && <SimulacoesTab />}
        {activeTab === 'historico' && <HistoricoTab />}
      </div>
    </div>
  );
}
