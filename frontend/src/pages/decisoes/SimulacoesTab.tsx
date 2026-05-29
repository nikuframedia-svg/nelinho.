/**
 * SimulacoesTab — what-if da decisão + cenários twin + crise (Q.118.E).
 * =====================================================================
 *
 * 3 segmentos:
 *   • Esta decisão — escolhe uma decisão pendente e vê o what-if real:
 *     if_accept/if_reject + KPIs do plano proposto (sandbox_result) + € fresco
 *     (margin preview por commit). Tudo dados reais; esconde o que não existe.
 *   • Cenários     — lista de cenários do digital twin + detalhe (SimDetail).
 *   • Crise        — CrisisSimulator (6 crises pré-definidas, corre no twin real).
 *
 * Reutiliza os componentes existentes (SimDetail, CrisisSimulator, twinApi).
 * NÃO usa /v1/sandbox/* (BLOCKED por defeito). ZERO MOCKS.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FlaskConical, AlertTriangle, History, Inbox } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkBadge, EmptyState, Segmented } from '../../components/dark';
import { decisionsApi, marginPreviewApi, twinApi, coerceEur, MARGIN_CONFIDENCE_LABEL } from '../../lib/api';
import { decisionKeys, profitKeys } from '../../lib/api/keys';
import type { DecisionRun } from '../../lib/api';
import { SimDetail } from '../../components/simulacoes/SimDetail';
import { CrisisSimulator } from '../../components/simulacoes/CrisisSimulator';
import type { TwinScenario } from '../../components/simulacoes/types';

type SimSeg = 'decisao' | 'cenarios' | 'crise';

const SEG_OPTIONS: { value: SimSeg; label: string }[] = [
  { value: 'decisao', label: 'Esta decisão' },
  { value: 'cenarios', label: 'Cenários' },
  { value: 'crise', label: 'Crise · agora' },
];

// ── What-if de uma decisão pendente ───────────────────────────────────────

function DecisaoWhatIf({ decision }: { decision: DecisionRun }) {
  const sb = (decision.sandbox_result ?? {}) as {
    commit_sha?: string;
    kpis?: Record<string, number | null>;
    quality_risk?: string | null;
    if_accept?: string[];
    if_reject?: string[];
  };
  const commitSha = (sb.commit_sha ?? '').trim();

  const marginQuery = useQuery({
    queryKey: profitKeys.preview(commitSha),
    queryFn: () => marginPreviewApi.get(commitSha),
    enabled: commitSha.length > 0,
    retry: false,
    staleTime: 60_000,
  });
  const delta = coerceEur(marginQuery.data?.delta_eur);
  const kpis = sb.kpis ?? {};

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      {/* KPIs do plano proposto */}
      <DarkCard>
        <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3 mb-2">
          Impacto no plano (se aceitar)
        </p>
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <Metric label="Makespan (h)" value={kpis.makespan_hours} digits={1} />
          <Metric label="Ordens atrasadas" value={kpis.num_late_orders} digits={0} />
          <Metric label="Utilização" value={kpis.avg_utilization} digits={2} />
          <Metric label="Atraso total (h)" value={kpis.total_tardiness_hours} digits={1} />
        </dl>
        <div className="mt-3 flex items-center gap-2">
          {sb.quality_risk ? (
            <DarkBadge variant="danger">Risco qualidade: {sb.quality_risk}</DarkBadge>
          ) : null}
          {commitSha && marginQuery.isSuccess && delta != null ? (
            <DarkBadge variant={delta >= 0 ? 'success' : 'danger'}>
              {delta >= 0 ? '+' : ''}
              {delta.toFixed(0)} € · {MARGIN_CONFIDENCE_LABEL[marginQuery.data?.confidence ?? ''] ?? marginQuery.data?.confidence}
            </DarkBadge>
          ) : null}
        </div>
        {!commitSha ? (
          <p className="text-xs text-fg-3 mt-3">
            Esta decisão ainda não tem plano (commit) associado — o € e os KPIs
            aparecem quando o CPO gerar o plano.
          </p>
        ) : null}
      </DarkCard>

      {/* Se aceitar / Se rejeitar */}
      <DarkCard>
        <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3 mb-2">
          Consequências
        </p>
        {(sb.if_accept?.length ?? 0) === 0 && (sb.if_reject?.length ?? 0) === 0 ? (
          <p className="text-xs text-fg-3">Sem consequências detalhadas para esta decisão.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[10px] uppercase font-semibold text-green-400 mb-1">Se aceitar</p>
              <ul className="text-xs text-fg-2 list-disc pl-4 space-y-1">
                {(sb.if_accept ?? []).map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[10px] uppercase font-semibold text-red-400 mb-1">Se rejeitar</p>
              <ul className="text-xs text-fg-2 list-disc pl-4 space-y-1">
                {(sb.if_reject ?? []).map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </DarkCard>
    </div>
  );
}

function Metric({
  label,
  value,
  digits,
}: {
  label: string;
  value: number | null | undefined;
  digits: number;
}) {
  return (
    <div>
      <dt className="text-[11px] text-fg-3">{label}</dt>
      <dd className="text-base font-semibold text-fg-0">
        {value == null ? '—' : value.toFixed(digits)}
      </dd>
    </div>
  );
}

function EstaDecisaoSeg() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const query = useQuery({
    queryKey: decisionKeys.list({ status: 'PROPOSED' }),
    queryFn: () => decisionsApi.list({ status: 'PROPOSED', page_size: 50 }),
    refetchOnWindowFocus: false,
  });
  const items = query.data?.decisions ?? [];
  const selected = items.find((d) => d.id === selectedId) ?? items[0] ?? null;

  if (query.isLoading) {
    return <DarkCard className="text-center py-8"><p className="text-sm text-fg-3">A carregar decisões…</p></DarkCard>;
  }
  if (items.length === 0) {
    return (
      <EmptyState
        mascot={false}
        icon={<Inbox size={28} />}
        title="Sem decisões pendentes para simular"
        hint="O what-if aparece quando houver decisões propostas."
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <select
        value={selected?.id ?? ''}
        onChange={(e) => setSelectedId(e.target.value)}
        className="bg-white text-slate-900 placeholder:text-slate-400 rounded-md border border-bd-2 px-3 py-2 text-sm max-w-md"
        aria-label="Escolher decisão para simular"
      >
        {items.map((d) => (
          <option key={d.id} value={d.id}>
            {d.title}
          </option>
        ))}
      </select>
      {selected ? <DecisaoWhatIf decision={selected} /> : null}
    </div>
  );
}

// ── Cenários do twin ───────────────────────────────────────────────────────

function CenariosSeg() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ['twin', 'scenarios', 'decisoes-tab'],
    queryFn: async (): Promise<TwinScenario[]> => {
      const raw = await twinApi.listScenarios();
      return Array.isArray(raw) ? (raw as TwinScenario[]) : [];
    },
    refetchOnWindowFocus: false,
  });
  const scenarios = query.data ?? [];
  const selected = scenarios.find((s) => s.id === selectedId) ?? null;

  if (query.isError) {
    return (
      <EmptyState mascot={false} icon={<AlertTriangle size={28} />}
        title="Não foi possível carregar os cenários" hint={(query.error as Error).message} />
    );
  }
  if (query.isLoading) {
    return <DarkCard className="text-center py-8"><p className="text-sm text-fg-3">A carregar cenários…</p></DarkCard>;
  }
  if (scenarios.length === 0) {
    return (
      <EmptyState mascot={false} icon={<FlaskConical size={28} />}
        title="Ainda não há cenários" hint="Usa a Crise para correr um cenário pré-definido no digital twin." />
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.3fr] gap-3">
      <div className="flex flex-col gap-1.5">
        {scenarios.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setSelectedId(s.id)}
            className={[
              'w-full text-left rounded-lg border px-3 py-2.5 transition-colors',
              selected?.id === s.id ? 'border-accent bg-bg-3' : 'border-bd-1 bg-bg-1 hover:border-bd-2',
            ].join(' ')}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-fg-1 truncate">{s.title}</span>
              <DarkBadge variant={s.status === 'SOLVED' ? 'success' : 'neutral'} size="sm">
                {s.status ?? 'DRAFT'}
              </DarkBadge>
            </div>
          </button>
        ))}
      </div>
      <DarkCard padding="none">
        <SimDetail scenario={selected} />
      </DarkCard>
    </div>
  );
}

export default function SimulacoesTab() {
  const [seg, setSeg] = useState<SimSeg>('decisao');

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Decisões' }, { label: 'Simulações' }]}
      title="Simulações"
      subtitle="What-if da decisão + cenários no digital twin · não toca produção"
      icon={<FlaskConical className="h-6 w-6" />}
    >
      <div className="mb-4">
        <Segmented<SimSeg>
          options={SEG_OPTIONS}
          value={seg}
          onChange={setSeg}
          ariaLabel="Modo de simulação"
        />
      </div>

      {seg === 'decisao' ? (
        <EstaDecisaoSeg />
      ) : seg === 'crise' ? (
        <CrisisSimulator />
      ) : (
        <CenariosSeg />
      )}

      {seg !== 'crise' ? (
        <p className="mt-4 flex items-center gap-1.5 text-xs text-fg-3">
          <History size={12} /> As simulações correm no digital twin (validação Spelke) e nunca tocam a produção.
        </p>
      ) : null}
    </DarkPageLayout>
  );
}
