/**
 * InboxDecisoesPage — port literal de design/nelo-zip/src/page-inbox.jsx.
 *
 * Filter tabs (Pendentes/Aceites hoje/Rejeitadas hoje/Tudo) + lista de
 * SuggestionCard rica com ConsequenceBox 2-col (Se aceitar / Se rejeitar)
 * + Alternativa + confidence + source.
 *
 * Wire ao /v1/decisions/?status_filter=PROPOSED|EXECUTED|REJECTED.
 *
 * Sprint Q.18.ZIP.shell.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Inbox, RefreshCw } from 'lucide-react';
import {
  ApprovalButtons,
  PageHeader,
  Tabs,
  ZipSevBadge,
  type ZipSeverity,
} from '../../components/dark';
import { decisionsApi } from '../../lib/api';

const TAB_IDS = ['pending', 'accepted', 'rejected', 'all'] as const;
type TabId = (typeof TAB_IDS)[number];

const STATUS_BY_TAB: Record<TabId, string | undefined> = {
  pending: 'PROPOSED',
  accepted: 'EXECUTED',
  rejected: 'REJECTED',
  all: undefined,
};

export default function InboxDecisoesPage() {
  const [tab, setTab] = useState<TabId>('pending');
  const [refreshKey, setRefreshKey] = useState(0);
  const queryClient = useQueryClient();

  const counts = useQuery({
    queryKey: ['inbox', 'counts', refreshKey],
    queryFn: async () => {
      const fetchTotal = async (status?: string) => {
        try {
          const r: any = await decisionsApi.list({ status, page_size: 1 });
          return r?.total ?? 0;
        } catch {
          return 0;
        }
      };
      const [pending, accepted, rejected, all] = await Promise.all([
        fetchTotal('PROPOSED'),
        fetchTotal('EXECUTED'),
        fetchTotal('REJECTED'),
        fetchTotal(undefined),
      ]);
      return { pending, accepted, rejected, all };
    },
    staleTime: 30_000,
    retry: 0,
  });

  const list = useQuery({
    queryKey: ['inbox', 'list', tab, refreshKey],
    queryFn: async () => {
      try {
        return (await decisionsApi.list({ status: STATUS_BY_TAB[tab], page_size: 20 })) as any;
      } catch {
        return null;
      }
    },
    staleTime: 15_000,
    retry: 0,
  });

  const items: any[] = useMemo(() => {
    const data: any = list.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    return data.items ?? data.decisions ?? [];
  }, [list.data]);

  const tabsConfig = [
    { id: 'pending', label: 'Pendentes', count: counts.data?.pending },
    { id: 'accepted', label: 'Aceites hoje', count: counts.data?.accepted },
    { id: 'rejected', label: 'Rejeitadas hoje', count: counts.data?.rejected },
    { id: 'all', label: 'Tudo', count: counts.data?.all },
  ];

  return (
    <div>
      <PageHeader
        icon={<Inbox size={20} />}
        title="Inbox de decisões"
        subtitle="Aprovações pendentes · histórico recente · padrões aprendidos"
        helpId="inbox"
        actions={
          <button
            type="button"
            onClick={() => setRefreshKey((k) => k + 1)}
            className="inline-flex items-center gap-1.5 text-text-dark-secondary hover:text-text-dark-primary transition-colors"
            style={{
              padding: '6px 12px',
              height: 32,
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-md)',
              fontSize: 12,
            }}
          >
            <RefreshCw size={13} />
            Actualizar
          </button>
        }
      />

      <div style={{ padding: '24px 28px' }} className="space-y-4 page-enter">
        <Tabs
          variant="pills"
          tabs={tabsConfig}
          value={tab}
          onChange={(v) => setTab(v as TabId)}
        />

        {list.isLoading ? (
          <div className="py-12 text-center text-text-dark-tertiary" style={{ fontSize: 13 }}>
            A carregar decisões…
          </div>
        ) : list.isError || list.data === null ? (
          <div className="py-12 text-center text-text-dark-tertiary" style={{ fontSize: 13 }}>
            Endpoint /v1/decisions indisponível.
          </div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-text-dark-tertiary" style={{ fontSize: 13 }}>
            <Inbox size={24} className="mx-auto mb-3 opacity-50" />
            {tab === 'pending'
              ? 'Sem decisões pendentes. Tudo decidido!'
              : tab === 'accepted'
                ? 'Sem decisões aceites no período.'
                : tab === 'rejected'
                  ? 'Sem decisões rejeitadas.'
                  : 'Sem decisões.'}
          </div>
        ) : (
          <div className="flex flex-col page-enter" style={{ gap: 14 }}>
            {items.map((d, idx) => (
              <SuggestionCardZip
                key={d.id ?? idx}
                decision={d}
                onDecided={() =>
                  queryClient.invalidateQueries({ queryKey: ['inbox'] })
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SuggestionCardZip({
  decision,
  onDecided,
}: {
  decision: any;
  onDecided: () => void;
}) {
  const sandbox = decision.sandbox_result ?? {};

  // Q.30.B — aprovar/rejeitar a decisão directamente no Inbox.
  const decideMutation = useMutation({
    mutationFn: (v: { status: 'APPROVED' | 'REJECTED'; comment?: string }) =>
      decisionsApi.approve(decision.id, v),
    onSuccess: () => onDecided(),
  });
  const priority: ZipSeverity =
    sandbox.priority === 'critical' ||
    sandbox.priority === 'high' ||
    sandbox.priority === 'medium' ||
    sandbox.priority === 'low'
      ? sandbox.priority
      : 'medium';
  const sevColor =
    priority === 'critical' ? 'red' : priority === 'high' ? 'orange' : priority === 'medium' ? 'yellow' : 'blue';

  return (
    <div
      style={{
        padding: 18,
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderLeft: `3px solid var(--${sevColor})`,
        borderRadius: 'var(--r-lg)',
      }}
    >
      <div className="flex items-center justify-between gap-2 mb-3">
        <ZipSevBadge severity={priority} size="sm" />
        {sandbox.confidence ? (
          <span className="text-text-dark-tertiary tabular-nums" style={{ fontSize: 11 }}>
            confiança {sandbox.confidence}%
          </span>
        ) : null}
      </div>
      <div className="text-text-dark-primary font-medium" style={{ fontSize: 15, lineHeight: 1.4 }}>
        {decision.title ?? '(Sem título)'}
      </div>
      {sandbox.why ? (
        <div className="text-text-dark-secondary mt-2" style={{ fontSize: 13, lineHeight: 1.5 }}>
          <strong className="text-text-dark-primary">Porquê:</strong> {sandbox.why}
        </div>
      ) : null}
      {sandbox.if_accept || sandbox.if_reject ? (
        <div className="grid grid-cols-2 gap-3 mt-3">
          {sandbox.if_accept ? (
            <div
              style={{
                padding: 10,
                background: 'var(--green-bg)',
                border: '1px solid var(--green-bd)',
                borderRadius: 'var(--r-md)',
              }}
            >
              <div
                className="uppercase font-semibold mb-1.5"
                style={{ fontSize: 10, letterSpacing: '0.4px', color: 'var(--green)' }}
              >
                Se aceitar
              </div>
              <ul className="text-text-dark-secondary space-y-0.5 list-none" style={{ fontSize: 12 }}>
                {sandbox.if_accept.map((line: string, i: number) => (
                  <li key={i}>· {line}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {sandbox.if_reject ? (
            <div
              style={{
                padding: 10,
                background: 'var(--red-bg)',
                border: '1px solid var(--red-bd)',
                borderRadius: 'var(--r-md)',
              }}
            >
              <div
                className="uppercase font-semibold mb-1.5"
                style={{ fontSize: 10, letterSpacing: '0.4px', color: 'var(--red)' }}
              >
                Se rejeitar
              </div>
              <ul className="text-text-dark-secondary space-y-0.5 list-none" style={{ fontSize: 12 }}>
                {sandbox.if_reject.map((line: string, i: number) => (
                  <li key={i}>· {line}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
      {sandbox.alternative ? (
        <div
          style={{
            marginTop: 12,
            padding: 10,
            background: 'var(--purple-bg)',
            border: '1px solid var(--purple-bd)',
            borderRadius: 'var(--r-md)',
          }}
        >
          <div
            className="uppercase font-semibold mb-1"
            style={{ fontSize: 10, letterSpacing: '0.4px', color: 'var(--purple)' }}
          >
            Alternativa
          </div>
          <div className="text-text-dark-primary font-medium" style={{ fontSize: 12 }}>
            {sandbox.alternative.label}
          </div>
          {sandbox.alternative.detail ? (
            <div className="text-text-dark-secondary mt-1" style={{ fontSize: 12 }}>
              {sandbox.alternative.detail}
            </div>
          ) : null}
        </div>
      ) : null}
      {sandbox.source ? (
        <div className="text-text-dark-tertiary mt-3" style={{ fontSize: 11 }}>
          fonte: {sandbox.source}
        </div>
      ) : null}

      {/* Q.30.B — só decisões pendentes (PROPOSED) são acionáveis */}
      {decision.status === 'PROPOSED' ? (
        <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--bd-1)' }}>
          <ApprovalButtons
            loading={decideMutation.isPending}
            requireReason="on_reject"
            onAccept={async (reason) => {
              // erro fica visível via decideMutation.isError (banner abaixo)
              try {
                await decideMutation.mutateAsync({ status: 'APPROVED', comment: reason });
              } catch { /* tratado pelo estado isError */ }
            }}
            onReject={async (reason) => {
              try {
                await decideMutation.mutateAsync({ status: 'REJECTED', comment: reason });
              } catch { /* tratado pelo estado isError */ }
            }}
          />
          {decideMutation.isError ? (
            <div className="text-danger mt-2" style={{ fontSize: 12 }} role="alert">
              Não foi possível registar a decisão. Tenta outra vez.
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
