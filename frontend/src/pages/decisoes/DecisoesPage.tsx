/**
 * DecisoesPage â€” estilo Tinder: 1 card grande, Sim/NÃ£o.
 *
 * Mostra decisÃµes PROPOSED uma de cada vez. BotÃµes Sim (verde) e NÃ£o (vermelho)
 * ocupam a largura total em baixo do card. Suporte teclado (â† NÃ£o, â†’ Sim).
 *
 * Q.115.J.
 */

import { useCallback, useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, X, Inbox, RefreshCw } from 'lucide-react';
import { decisionKeys } from '../../lib/api/keys';
import { decisionsApi, type DecisionRun } from '../../lib/api';
import { PageHeader } from '../../components/dark';

// â”€â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function sourceLabel(source: string | undefined): string {
  if (!source) return '';
  const map: Record<string, string> = {
    auto: 'Auto-proposto',
    manual: 'Manual',
    cpo: 'CPO',
    copilot: 'Copilot',
  };
  return map[source.toLowerCase()] ?? source;
}

// â”€â”€â”€ componente principal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export default function DecisoesPage() {
  const queryClient = useQueryClient();
  const [currentIndex, setCurrentIndex] = useState(0);
  // direcÃ§Ã£o da animaÃ§Ã£o: 1 = saÃ­da esquerda (NÃ£o), -1 = saÃ­da direita (Sim)
  const [exitDir, setExitDir] = useState<1 | -1>(1);

  const query = useQuery({
    queryKey: decisionKeys.list({ status: 'PROPOSED' }),
    queryFn: () => decisionsApi.list({ status: 'PROPOSED', page_size: 50 }),
    refetchInterval: 5_000,
  });

  const items: DecisionRun[] = query.data?.items ?? [];
  const total = items.length;
  const current: DecisionRun | undefined = items[currentIndex];

  // repÃµe index quando a lista muda (ex: apÃ³s invalidaÃ§Ã£o)
  useEffect(() => {
    setCurrentIndex((prev) => {
      if (items.length === 0) return 0;
      return Math.min(prev, items.length - 1);
    });
  }, [items.length]);

  const advance = useCallback(() => {
    setCurrentIndex((prev) => {
      const next = prev + 1;
      return next >= items.length ? items.length : next;
    });
  }, [items.length]);

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: decisionKeys.lists() });
  }, [queryClient]);

  const approveMutation = useMutation({
    mutationFn: (id: string) =>
      decisionsApi.approve(id, { status: 'APPROVED' }),
    onSuccess: () => {
      invalidate();
      advance();
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) =>
      decisionsApi.approve(id, { status: 'REJECTED' }),
    onSuccess: () => {
      invalidate();
      advance();
    },
  });

  const isPending = approveMutation.isPending || rejectMutation.isPending;

  const handleSim = useCallback(() => {
    if (!current || isPending) return;
    setExitDir(-1);
    approveMutation.mutate(current.id);
  }, [current, isPending, approveMutation]);

  const handleNao = useCallback(() => {
    if (!current || isPending) return;
    setExitDir(1);
    rejectMutation.mutate(current.id);
  }, [current, isPending, rejectMutation]);

  // suporte teclado
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') handleSim();
      if (e.key === 'ArrowLeft') handleNao();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleSim, handleNao]);

  // â”€â”€ estados especiais â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  if (query.isError) {
    return (
      <div>
        <PageHeader icon={<Inbox size={20} />} title="DecisÃµes" />
        <CenteredFrame>
          <div className="text-center space-y-4">
            <X size={40} className="mx-auto text-danger opacity-60" />
            <p className="text-text-dark-secondary" style={{ fontSize: 14 }}>
              Erro: {(query.error as Error)?.message ?? 'NÃ£o foi possÃ­vel carregar as decisÃµes.'}
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
        <PageHeader icon={<Inbox size={20} />} title="DecisÃµes" />
        <CenteredFrame>
          <div className="text-center text-text-dark-tertiary" style={{ fontSize: 14 }}>
            A carregar decisÃµesâ€¦
          </div>
        </CenteredFrame>
      </div>
    );
  }

  if (total === 0 || !current) {
    return (
      <div>
        <PageHeader icon={<Inbox size={20} />} title="DecisÃµes" />
        <CenteredFrame>
          <div className="text-center space-y-3">
            <Inbox size={40} className="mx-auto text-text-dark-tertiary opacity-40" />
            <p className="text-text-dark-secondary font-medium" style={{ fontSize: 16 }}>
              Sem decisÃµes pendentes
            </p>
            <p className="text-text-dark-tertiary" style={{ fontSize: 13 }}>
              Volta mais tarde â€” o sistema propÃµe decisÃµes automaticamente.
            </p>
          </div>
        </CenteredFrame>
      </div>
    );
  }

  const sb = current.sandbox_result ?? {};
  const confidence: number | undefined = sb.confidence as number | undefined;
  const source: string | undefined = sb.source as string | undefined ?? current.proposed_by;
  const ifAccept: string[] | undefined = sb.if_accept as string[] | undefined;
  const ifReject: string[] | undefined = sb.if_reject as string[] | undefined;
  const why: string | undefined = sb.why as string | undefined;
  // Q.115.E/F placeholders â€” renderizam sÃ³ quando o backend os enviar
  const qualityRisk: string | null = (sb.quality_risk as string | null) ?? null;
  const costDelta: number | null = (sb.cost_delta as number | null) ?? null;

  return (
    <div>
      <PageHeader
        icon={<Inbox size={20} />}
        title="DecisÃµes"
                actions={
          <span
            className="text-text-dark-tertiary tabular-nums"
            style={{ fontSize: 12 }}
            aria-label={`DecisÃ£o ${currentIndex + 1} de ${total} pendentes`}
          >
            {currentIndex + 1}&nbsp;/&nbsp;{total}
          </span>
        }
      />

      <CenteredFrame>
        <AnimatePresence mode="wait">
          <motion.div
            key={current.id}
            initial={{ x: exitDir * 60, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: exitDir * -60, opacity: 0 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            style={{
              width: '100%',
              maxWidth: 600,
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-xl)',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* â”€â”€ CabeÃ§alho do card â”€â”€ */}
            <div style={{ padding: '20px 20px 16px' }}>
              <div className="flex items-start gap-3 mb-3">
                {/* badges de metadata */}
                <div className="flex flex-wrap gap-2 flex-1">
                  {confidence != null ? (
                    <span
                      style={{
                        fontSize: 11,
                        padding: '2px 8px',
                        borderRadius: 99,
                        background: 'var(--blue-bg)',
                        color: 'var(--blue)',
                        border: '1px solid var(--blue-bd)',
                        fontWeight: 500,
                      }}
                    >
                      ConfianÃ§a {confidence}%
                    </span>
                  ) : null}
                  {source ? (
                    <span
                      style={{
                        fontSize: 11,
                        padding: '2px 8px',
                        borderRadius: 99,
                        background: 'var(--bg-2)',
                        color: 'var(--fg-2)',
                        border: '1px solid var(--bd-2)',
                        fontWeight: 500,
                      }}
                    >
                      {sourceLabel(source)}
                    </span>
                  ) : null}
                  {/* Q.115.E placeholder â€” quality risk */}
                  {qualityRisk != null ? (
                    <span
                      style={{
                        fontSize: 11,
                        padding: '2px 8px',
                        borderRadius: 99,
                        background: 'var(--red-bg)',
                        color: 'var(--red)',
                        border: '1px solid var(--red-bd)',
                        fontWeight: 500,
                      }}
                    >
                      Risco qualidade: {qualityRisk}
                    </span>
                  ) : null}
                  {/* Q.115.F placeholder â€” cost delta */}
                  {costDelta != null ? (
                    <span
                      style={{
                        fontSize: 11,
                        padding: '2px 8px',
                        borderRadius: 99,
                        background: costDelta >= 0 ? 'var(--green-bg)' : 'var(--red-bg)',
                        color: costDelta >= 0 ? 'var(--green)' : 'var(--red)',
                        border: `1px solid ${costDelta >= 0 ? 'var(--green-bd)' : 'var(--red-bd)'}`,
                        fontWeight: 500,
                      }}
                    >
                      {costDelta >= 0 ? '+' : ''}
                      {costDelta.toFixed(0)} â‚¬
                    </span>
                  ) : null}
                </div>
              </div>

              {/* TÃ­tulo */}
              <h2
                className="text-text-dark-primary font-bold"
                style={{ fontSize: 22, lineHeight: 1.3 }}
              >
                {current.title ?? '(Sem tÃ­tulo)'}
              </h2>

              {/* PorquÃª */}
              {why ? (
                <p className="text-text-dark-secondary mt-2" style={{ fontSize: 13, lineHeight: 1.5 }}>
                  {why}
                </p>
              ) : null}
            </div>

            {/* â”€â”€ ConsequenceBox inline (Se aceitar / Se rejeitar) â”€â”€ */}
            {(ifAccept && ifAccept.length > 0) || (ifReject && ifReject.length > 0) ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderTop: '1px solid var(--bd-1)' }}>
                {ifAccept && ifAccept.length > 0 ? (
                  <div
                    style={{
                      padding: '12px 16px',
                      background: 'var(--green-bg)',
                      borderRight: '1px solid var(--bd-1)',
                    }}
                  >
                    <div
                      className="uppercase font-semibold mb-2"
                      style={{ fontSize: 10, letterSpacing: '0.5px', color: 'var(--green)' }}
                    >
                      Se aceitar
                    </div>
                    <ul
                      style={{
                        margin: 0,
                        paddingLeft: 14,
                        color: 'var(--fg-1)',
                        fontSize: 12,
                        lineHeight: 1.6,
                      }}
                    >
                      {ifAccept.map((line, i) => (
                        <li key={i}>{line}</li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div />
                )}
                {ifReject && ifReject.length > 0 ? (
                  <div style={{ padding: '12px 16px', background: 'var(--red-bg)' }}>
                    <div
                      className="uppercase font-semibold mb-2"
                      style={{ fontSize: 10, letterSpacing: '0.5px', color: 'var(--red)' }}
                    >
                      Se rejeitar
                    </div>
                    <ul
                      style={{
                        margin: 0,
                        paddingLeft: 14,
                        color: 'var(--fg-1)',
                        fontSize: 12,
                        lineHeight: 1.6,
                      }}
                    >
                      {ifReject.map((line, i) => (
                        <li key={i}>{line}</li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div />
                )}
              </div>
            ) : null}

            {/* â”€â”€ Erro de mutation â”€â”€ */}
            {(approveMutation.isError || rejectMutation.isError) ? (
              <div
                className="text-danger px-5 py-2 text-sm"
                role="alert"
                style={{ background: 'var(--red-bg)', borderTop: '1px solid var(--red-bd)' }}
              >
                NÃ£o foi possÃ­vel registar a decisÃ£o. Tenta outra vez.
              </div>
            ) : null}

            {/* â”€â”€ BotÃµes Sim / NÃ£o â”€â”€ */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                borderTop: '1px solid var(--bd-1)',
                minHeight: 64,
              }}
            >
              <button
                type="button"
                onClick={handleNao}
                disabled={isPending}
                aria-label="Rejeitar decisÃ£o (tecla â†)"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  minHeight: 64,
                  background: 'var(--red-bg)',
                  color: 'var(--red)',
                  border: 'none',
                  borderRight: '1px solid var(--bd-1)',
                  cursor: isPending ? 'not-allowed' : 'pointer',
                  opacity: isPending ? 0.6 : 1,
                  fontSize: 16,
                  fontWeight: 600,
                  transition: 'background 0.12s',
                }}
                onMouseEnter={(e) => {
                  if (!isPending) e.currentTarget.style.background = 'var(--red)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'var(--red-bg)';
                }}
              >
                <X size={20} />
                NÃ£o
              </button>
              <button
                type="button"
                onClick={handleSim}
                disabled={isPending}
                aria-label="Aprovar decisÃ£o (tecla â†’)"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  minHeight: 64,
                  background: 'var(--green-bg)',
                  color: 'var(--green)',
                  border: 'none',
                  cursor: isPending ? 'not-allowed' : 'pointer',
                  opacity: isPending ? 0.6 : 1,
                  fontSize: 16,
                  fontWeight: 600,
                  transition: 'background 0.12s',
                }}
                onMouseEnter={(e) => {
                  if (!isPending) e.currentTarget.style.background = 'var(--green)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'var(--green-bg)';
                }}
              >
                <Check size={20} />
                Sim
              </button>
            </div>
          </motion.div>
        </AnimatePresence>

        {/* dica de teclado */}
        <p
          className="text-text-dark-tertiary text-center mt-4"
          style={{ fontSize: 11 }}
          aria-hidden="true"
        >
          â† NÃ£o &nbsp;Â·&nbsp; â†’ Sim
        </p>
      </CenteredFrame>
    </div>
  );
}

// â”€â”€â”€ layout helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function CenteredFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        padding: '24px 28px',
        minHeight: 'calc(100vh - 120px)',
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

