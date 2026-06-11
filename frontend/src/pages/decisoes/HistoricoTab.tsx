/**
 * HistoricoTab — decisões já tomadas + loop de aprendizagem visível (Q.118.F).
 * =============================================================================
 *
 * Lista as decisões não-pendentes (aprovadas/rejeitadas/executadas) com filtro
 * por estado. Cada linha:
 *   • estado (DarkBadge) + título + data + entidades clicáveis (decisionEntities)
 *   • clicar expande o detalhe: audit trail (decisionsApi.getAuditTrail) +
 *     aprovações + estado antes/depois.
 * Secção "O que o sistema aprendeu" liga o loop de aprendizagem: mostra as
 * preference-rules detectadas/confirmadas a partir das decisões (Camada 1).
 *
 * ZERO MOCKS — empty/error/loading explícitos.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { History, AlertTriangle, RefreshCw, ChevronDown, ChevronRight, Brain } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkBadge, DarkButton, EmptyState, Segmented } from '../../components/dark';
import { decisionsApi, preferenceRulesApi } from '../../lib/api';
import { decisionKeys, governanceKeys } from '../../lib/api/keys';
import type { DecisionRun } from '../../lib/api';
import { DecisionEntities } from './decisionEntities';

type StatusFilter = 'all' | 'APPROVED' | 'REJECTED' | 'EXECUTED';

const FILTER_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'Todas' },
  { value: 'APPROVED', label: 'Aprovadas' },
  { value: 'REJECTED', label: 'Rejeitadas' },
  { value: 'EXECUTED', label: 'Executadas' },
];

const STATUS_VARIANT: Record<string, 'success' | 'danger' | 'info' | 'neutral' | 'warning'> = {
  APPROVED: 'success',
  EXECUTED: 'info',
  REJECTED: 'danger',
  ROLLED_BACK: 'warning',
  PROPOSED: 'neutral',
};

const STATUS_LABEL: Record<string, string> = {
  APPROVED: 'Aprovada',
  EXECUTED: 'Executada',
  REJECTED: 'Rejeitada',
  ROLLED_BACK: 'Revertida',
  PROPOSED: 'Pendente',
};

// ── Detalhe expansível: audit trail + aprovações ──────────────────────────

type AuditEvent = { timestamp: string | null; event: string; by?: string };

function buildTimeline(
  data: Awaited<ReturnType<typeof decisionsApi.getAuditTrail>>,
): AuditEvent[] {
  const events: AuditEvent[] = [];

  const d = data?.decision;
  if (d?.proposed_at) {
    events.push({ timestamp: d.proposed_at, event: 'Proposta', by: d.proposed_by });
  }
  if (d?.executed_at) {
    events.push({ timestamp: d.executed_at, event: 'Execução' });
  }
  if (d?.rolled_back_at) {
    events.push({ timestamp: d.rolled_back_at, event: 'Revertida' });
  }

  const approvals = Array.isArray(data?.approvals) ? data.approvals : [];
  for (const a of approvals) {
    events.push({
      timestamp: a.approved_at ?? null,
      event: a.status === 'APPROVED' ? 'Aprovação' : a.status === 'REJECTED' ? 'Rejeição' : a.status,
      by: a.approver_id,
    });
  }

  events.sort((a, b) => {
    if (!a.timestamp) return 1;
    if (!b.timestamp) return -1;
    return a.timestamp < b.timestamp ? -1 : 1;
  });

  return events;
}

function DecisionDetail({ id }: { id: string }) {
  const auditQuery = useQuery({
    queryKey: [...decisionKeys.detail(id), 'audit'],
    queryFn: () => decisionsApi.getAuditTrail(id),
    refetchOnWindowFocus: false,
  });

  if (auditQuery.isLoading) {
    return <p className="text-xs text-fg-3 px-3 py-2">A carregar trilho de auditoria…</p>;
  }
  if (auditQuery.isError) {
    return (
      <p className="text-xs text-fg-3 px-3 py-2">
        Sem trilho de auditoria disponível.
      </p>
    );
  }

  const trail = buildTimeline(auditQuery.data!);
  const sc = auditQuery.data?.state_changes;

  if (trail.length === 0 && !sc) {
    return <p className="text-xs text-fg-3 px-3 py-2">Sem eventos de auditoria.</p>;
  }

  return (
    <div className="border-t border-bd-1 mt-2">
      {trail.length > 0 && (
        <ol className="px-3 py-2 flex flex-col gap-1.5">
          {trail.map((ev, i) => (
            <li key={i} className="text-xs text-fg-2 flex items-baseline gap-2">
              <span className="text-fg-3 tabular-nums shrink-0">
                {ev.timestamp ? new Date(ev.timestamp).toLocaleString('pt-PT') : '—'}
              </span>
              <span className="font-medium">{ev.event}</span>
              {ev.by ? <span className="text-fg-3">· {ev.by}</span> : null}
            </li>
          ))}
        </ol>
      )}
      {sc?.before_state || sc?.after_state ? (
        <p className="px-3 pb-2 text-xs text-fg-3">
          Estado:{' '}
          <span className="font-medium text-fg-2">
            {JSON.stringify(sc.before_state ?? {})}
          </span>
          {' → '}
          <span className="font-medium text-fg-2">
            {JSON.stringify(sc.after_state ?? {})}
          </span>
        </p>
      ) : null}
    </div>
  );
}

// ── Secção de aprendizagem (loop visível) ─────────────────────────────────

function AprendizagemSection() {
  const rulesQuery = useQuery({
    queryKey: governanceKeys.preferenceRules({ status: 'any' }),
    queryFn: () => preferenceRulesApi.list({ limit: 50 }),
    refetchOnWindowFocus: false,
    retry: false,
  });

  const rules = rulesQuery.data ?? [];
  if (rulesQuery.isLoading || rules.length === 0) {
    // Sem regras aprendidas ainda → não mostra a secção (evita ruído).
    return null;
  }

  return (
    <DarkCard className="mb-4 border-accent/20 bg-accent/5">
      <div className="flex items-center gap-2 mb-2">
        <Brain size={15} className="text-accent" />
        <p className="text-sm font-medium text-fg-1">O que o sistema aprendeu</p>
        <span className="text-xs text-fg-3">
          · regras detectadas a partir das tuas decisões
        </span>
      </div>
      <ul className="flex flex-col gap-1.5">
        {rules.slice(0, 6).map((r) => (
          <li key={r.id} className="flex items-center gap-2 text-sm text-fg-2">
            <DarkBadge variant={r.status === 'confirmed' ? 'success' : 'neutral'} size="sm">
              {r.status === 'confirmed' ? 'Confirmada' : 'Detectada'}
            </DarkBadge>
            <span className="truncate flex-1">{r.description}</span>
            <span className="text-xs text-fg-3 shrink-0">
              {Math.round((r.confidence ?? 0) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </DarkCard>
  );
}

const PAGE_SIZE = 25;

export default function HistoricoTab() {
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Q.173.AT — paginação real (antes: page_size 100 hardcoded cortava o
  // histórico a 100 sem aviso; a API já devolvia total/page).
  const query = useQuery({
    queryKey: decisionKeys.list({ status: `historico:${filter}:p${page}` }),
    queryFn: () =>
      decisionsApi.list({
        ...(filter === 'all' ? {} : { status: filter }),
        page,
        page_size: PAGE_SIZE,
      }),
    refetchOnWindowFocus: false,
  });

  const items: DecisionRun[] = (query.data?.decisions ?? []).filter((d) =>
    filter === 'all' ? d.status !== 'PROPOSED' : true,
  );
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const changeFilter = (next: StatusFilter) => {
    setFilter(next);
    setPage(1);
  };

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Decisões' }, { label: 'Histórico' }]}
      title="Histórico de decisões"
      subtitle="Decisões já tomadas — aprovadas, rejeitadas e executadas"
      icon={<History className="h-6 w-6" />}
    >
      <AprendizagemSection />

      <div className="mb-4">
        <Segmented<StatusFilter>
          options={FILTER_OPTIONS}
          value={filter}
          onChange={changeFilter}
          ariaLabel="Filtrar por estado"
        />
      </div>

      {query.isError ? (
        <DarkCard className="border-danger/30 bg-danger/5">
          <div className="flex items-center gap-3">
            <AlertTriangle size={18} className="text-danger shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-fg-1">Falha ao carregar o histórico</p>
              <p className="text-xs text-fg-3 mt-0.5">
                {(query.error as Error)?.message ?? 'Erro desconhecido'}
              </p>
            </div>
            <DarkButton variant="ghost" icon={<RefreshCw size={13} />} onClick={() => query.refetch()}>
              Tentar novamente
            </DarkButton>
          </div>
        </DarkCard>
      ) : query.isLoading ? (
        <DarkCard className="text-center py-10">
          <p className="text-sm text-fg-3">A carregar histórico…</p>
        </DarkCard>
      ) : items.length === 0 ? (
        <EmptyState
          mascot={false}
          icon={<History size={28} />}
          title="Sem decisões neste filtro"
          hint="As decisões aparecem aqui depois de aprovadas, rejeitadas ou executadas."
        />
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((d) => {
            const open = expandedId === d.id;
            return (
              <DarkCard key={d.id} className="py-3">
                <button
                  type="button"
                  className="w-full flex items-center justify-between gap-3 text-left"
                  onClick={() => setExpandedId(open ? null : d.id)}
                  aria-expanded={open}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      {open ? (
                        <ChevronDown size={14} className="text-fg-3 shrink-0" />
                      ) : (
                        <ChevronRight size={14} className="text-fg-3 shrink-0" />
                      )}
                      <DarkBadge variant={STATUS_VARIANT[d.status] ?? 'neutral'}>
                        {STATUS_LABEL[d.status] ?? d.status}
                      </DarkBadge>
                      <span className="text-sm font-medium text-fg-1 truncate">{d.title}</span>
                    </div>
                    <p className="text-xs text-fg-3 mt-1 pl-6">
                      {d.action_type}
                      {d.proposed_at
                        ? ` · ${new Date(d.proposed_at).toLocaleString('pt-PT')}`
                        : ''}
                    </p>
                  </div>
                </button>
                <div className="pl-6">
                  <DecisionEntities decision={d} />
                </div>
                {open ? <DecisionDetail id={d.id} /> : null}
              </DarkCard>
            );
          })}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <DarkButton
                variant="ghost"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                ← Anterior
              </DarkButton>
              <span className="text-xs text-fg-3">
                Página {page} de {totalPages} · {total} decisões
              </span>
              <DarkButton
                variant="ghost"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Próxima →
              </DarkButton>
            </div>
          )}
        </div>
      )}
    </DarkPageLayout>
  );
}
