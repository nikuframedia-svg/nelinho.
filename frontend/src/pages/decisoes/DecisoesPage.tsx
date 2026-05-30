/**
 * DecisoesPage — grelha de decisões pendentes (Q.121.C · redesign Q.123).
 *
 * Mostra TODAS as decisões PROPOSED ao mesmo tempo numa grelha de cartões
 * (<DecisionCard>), cada um com botões Sim/Não próprios. Antes era um hub
 * estilo Tinder (1 cartão de cada vez); o Luis quer ver várias em simultâneo.
 *
 * Shell de 3 sub-abas: Decidir · Simulações · Histórico (?tab=, useTabRouting).
 *
 * Q.123 — alinhado ao padrão sénior do OverallPage:
 *   • PageHeader FORA do scroll (corrige a sobreposição cabeçalho↔cartão que
 *     o `sticky top:52` causava dentro do contentor de scroll);
 *   • estados (erro/loading/vazio) via <EmptyState>;
 *   • entrada da grelha com motion staggered (respeita prefers-reduced-motion).
 */

import { useCallback } from 'react';
import { motion } from 'framer-motion';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Inbox, RefreshCw, FlaskConical, History } from 'lucide-react';
import { decisionKeys } from '../../lib/api/keys';
import { decisionsApi, type DecisionRun } from '../../lib/api';
import { PageHeader, Tabs, DarkButton, EmptyState } from '../../components/dark';
import { useTabRouting } from '../../hooks/useTabRouting';
import SimulacoesTab from './SimulacoesTab';
import HistoricoTab from './HistoricoTab';
import { DecisionCard } from './DecisionCard';
import { useRealtimeType } from '../../providers/RealtimeProvider';

// ─── Motion: entrada staggered dos cartões (respeita reduced-motion) ─────────

const cardVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: (delay: number) => ({ opacity: 1, y: 0, transition: { duration: 0.2, delay } }),
};
const reducedVariants = {
  hidden: { opacity: 1, y: 0 },
  visible: () => ({ opacity: 1, y: 0 }),
};
function usePrefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// ─── aba Decidir: grelha de cartões ─────────────────────────────────────────

function DecidirTab() {
  const queryClient = useQueryClient();
  const reducedMotion = usePrefersReducedMotion();
  const variants = reducedMotion ? reducedVariants : cardVariants;

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

  return (
    <div className="flex flex-col h-full">
      {header}
      <div className="flex-1 min-h-0 overflow-auto">
        {query.isError ? (
          <div className="h-full grid place-items-center px-6">
            <EmptyState
              mascot={false}
              icon={<RefreshCw size={30} />}
              title="Não foi possível carregar as decisões"
              hint={(query.error as Error)?.message ?? 'Erro ao contactar o servidor.'}
              action={
                <DarkButton size="sm" variant="secondary" onClick={() => query.refetch()}>
                  Tentar novamente
                </DarkButton>
              }
            />
          </div>
        ) : query.isLoading ? (
          <div
            className="h-full grid place-items-center px-6 text-text-dark-tertiary"
            style={{ fontSize: 14 }}
          >
            A carregar decisões…
          </div>
        ) : total === 0 ? (
          <div className="h-full grid place-items-center px-6">
            <EmptyState
              title="Sem decisões pendentes"
              hint="Volta mais tarde — o sistema propõe decisões automaticamente."
            />
          </div>
        ) : (
          <>
            {hasError ? (
              <div
                className="text-danger px-6 py-2 text-sm"
                role="alert"
                style={{ background: 'var(--red-bg)', borderBottom: '1px solid var(--red-bd)' }}
              >
                Não foi possível registar a decisão. Tenta outra vez.
              </div>
            ) : null}
            <motion.div
              className="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start"
              style={{ padding: '20px 24px' }}
              initial="hidden"
              animate="visible"
            >
              {items.map((d, i) => (
                <motion.div
                  key={d.id}
                  custom={Math.min(i, 10) * 0.04}
                  variants={variants}
                >
                  <DecisionCard
                    decision={d}
                    onApprove={(id) => approveMutation.mutate(id)}
                    onReject={(id) => rejectMutation.mutate(id)}
                    isPending={isPending}
                  />
                </motion.div>
              ))}
            </motion.div>
          </>
        )}
      </div>
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
      <div className="px-4 pt-3 shrink-0">
        <Tabs
          tabs={DECISOES_TABS}
          value={activeTab}
          onChange={(id) => setTab(id as DecisoesTabId)}
        />
      </div>
      {/* min-h-0 sem overflow no nível da página: o Decidir gere o seu próprio
          scroll (header fixo); Simulações/Histórico usam DarkPageLayout e são
          envolvidos num scroll próprio. */}
      <div className="flex-1 min-h-0">
        {activeTab === 'decidir' && <DecidirTab />}
        {activeTab === 'simulacoes' && (
          <div className="h-full overflow-auto">
            <SimulacoesTab />
          </div>
        )}
        {activeTab === 'historico' && (
          <div className="h-full overflow-auto">
            <HistoricoTab />
          </div>
        )}
      </div>
    </div>
  );
}
