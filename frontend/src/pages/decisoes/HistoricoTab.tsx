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
  const trail = auditQuery.data ?? [];
  if (trail.length === 0) {
    return <p className="text-xs text-fg-3 px-3 py-2">Sem eventos de auditoria.</p>;
  }
  return (
    <ol className="px-3 py-2 flex flex-col gap-1.5 border-t border-bd-1 mt-2">
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

export default function HistoricoTab() {
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: decisionKeys.list({ status: `historico:${filter}` }),
    queryFn: () =>
      decisionsApi.list({
        ...(filter === 'all' ? {} : { status: filter }),
        page_size: 100,
      }),
    refetchOnWindowFocus: false,
  });

  const items: DecisionRun[] = (query.data?.items ?? []).filter((d) =>
    filter === 'all' ? d.status !== 'PROPOSED' : true,
  );

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
          onChange={setFilter}
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
        </div>
      )}
    </DarkPageLayout>
  );
}
