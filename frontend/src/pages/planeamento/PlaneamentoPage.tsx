/**
 * PlaneamentoPage — Q.52.G · reconstrução do design NELO.
 *
 * 3 tabs: Barcos · Pessoas · Materiais. Substitui POR COMPLETO os dados
 * DEMO/fake das sub-tabs anteriores (Materiais/Forecast/Simulador) — agora
 * tudo vem de endpoints reais. ZERO MOCKS.
 *
 * - Barcos:    timeline arrastável das operações do último commit do CPO
 *              (cpoCommitsApi + schedulePreviewApi preview-delta/apply-move).
 *              "Replanear" → POST /v1/plan/cpo/schedule.
 * - Pessoas:   cobertura por fase derivada das operações reais + relatório
 *              de prioridade (alinhamento receita ↔ scheduler).
 * - Materiais: viabilidade do plano com stock actual — /v1/supply/materials
 *              + .../position (PARTIAL → "—" honesto).
 */

import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CalendarRange,
  Boxes,
  Users,
  RefreshCw,
  Cuboid,
  AlertTriangle,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts/DarkPageLayout';
import { Segmented } from '../../components/dark/Segmented';
import { KPIBig } from '../../components/dark/KPIBig';
import { EmptyState } from '../../components/dark/EmptyState';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import { cpoCommitsApi } from '../../lib/api';
import {
  BarcosTimeline,
  CpoGhostSuggestion,
} from '../../components/planeamento/BarcosTimeline';
import type { CpoOperation } from '../../components/planeamento/planeamentoApi';
import { planeamentoApi } from '../../components/planeamento/planeamentoApi';
import {
  materiaisApi,
  type BomMaterial,
} from '../../components/materiais/materiaisApi';

type TabId = 'barcos' | 'pessoas' | 'materiais';

const TABS: Array<{ value: TabId; label: string; icon: ReactNode }> = [
  { value: 'barcos', label: 'Barcos', icon: <Cuboid size={13} /> },
  { value: 'pessoas', label: 'Pessoas', icon: <Users size={13} /> },
  { value: 'materiais', label: 'Materiais', icon: <Boxes size={13} /> },
];

// ═══════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════

export default function PlaneamentoPage(): ReactNode {
  const [tab, setTab] = useState<TabId>('barcos');
  const queryClient = useQueryClient();

  const replanMutation = useMutation({
    mutationFn: () => planeamentoApi.runSchedule({ horizon_days: 7 }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['planeamento'] });
    },
  });

  return (
    <DarkPageLayout
      title="Planeamento"
      subtitle="Plano dia/dia · 15 min · barcos, pessoas e materiais"
      icon={<CalendarRange size={18} />}
      actions={
        <button
          type="button"
          onClick={() => replanMutation.mutate()}
          disabled={replanMutation.isPending}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 14px',
            fontSize: 12,
            fontWeight: 500,
            borderRadius: 'var(--r-sm)',
            background: 'var(--accent)',
            color: '#fff',
            border: 'none',
            cursor: replanMutation.isPending ? 'wait' : 'pointer',
            opacity: replanMutation.isPending ? 0.7 : 1,
          }}
        >
          <RefreshCw size={13} />
          {replanMutation.isPending ? 'A replanear…' : 'Replanear'}
        </button>
      }
    >
      <div style={{ marginBottom: 16 }}>
        <Segmented options={TABS} value={tab} onChange={setTab} />
      </div>

      {replanMutation.isError && (
        <div
          style={{
            marginBottom: 14,
            fontSize: 11.5,
            color: 'var(--red)',
            background: 'var(--red-bg)',
            border: '1px solid var(--red-bd)',
            borderRadius: 'var(--r-sm)',
            padding: '8px 12px',
          }}
        >
          Falha a replanear:{' '}
          {replanMutation.error instanceof Error
            ? replanMutation.error.message
            : 'erro desconhecido'}
        </div>
      )}
      {replanMutation.isSuccess && (
        <div
          style={{
            marginBottom: 14,
            fontSize: 11.5,
            color: 'var(--green)',
            background: 'var(--green-bg)',
            border: '1px solid var(--green-bd)',
            borderRadius: 'var(--r-sm)',
            padding: '8px 12px',
          }}
        >
          Plano regenerado · {replanMutation.data.operations.length} operações ·
          makespan {replanMutation.data.makespan_hours.toFixed(1)}h
          {replanMutation.data.degraded
            ? ` · ATENÇÃO: plano degradado (${replanMutation.data.fallback_reason ?? 'fallback'})`
            : ''}
        </div>
      )}

      {tab === 'barcos' && <BarcosTabView />}
      {tab === 'pessoas' && <PessoasTabView />}
      {tab === 'materiais' && <MateriaisViabilityTab />}
    </DarkPageLayout>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · BARCOS
// ═══════════════════════════════════════════════════════════════════════════

function BarcosTabView(): ReactNode {
  const commitsQuery = useQuery({
    queryKey: ['planeamento', 'cpo-commits'],
    queryFn: () => cpoCommitsApi.list({ limit: 1 }),
  });
  const latest = commitsQuery.data?.[0];

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
          Plano actual do CPO
        </h2>
        <p style={{ fontSize: 11.5, color: 'var(--fg-3)', marginTop: 2 }}>
          Granularidade 15 min · arrasta uma operação para outra fase para ver a
          consequência
        </p>
      </div>
      <BarcosTimeline />
      <CpoGhostSuggestion commit={latest} />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · PESSOAS  (cobertura por fase derivada das operações reais)
// ═══════════════════════════════════════════════════════════════════════════

function PessoasTabView(): ReactNode {
  const commitsQuery = useQuery({
    queryKey: ['planeamento', 'cpo-commits'],
    queryFn: () => cpoCommitsApi.list({ limit: 1 }),
  });
  const latestSha = commitsQuery.data?.[0]?.commit_sha256;

  const commitQuery = useQuery({
    queryKey: ['planeamento', 'cpo-commit', latestSha],
    queryFn: () =>
      cpoCommitsApi.get(latestSha as string, { include_operations: true }),
    enabled: latestSha !== undefined,
  });

  const priorityQuery = useQuery({
    queryKey: ['planeamento', 'priority-report', latestSha],
    queryFn: () => planeamentoApi.priorityReport(latestSha),
    enabled: latestSha !== undefined,
    retry: 0,
  });

  const operations = useMemo<CpoOperation[]>(
    () => (commitQuery.data?.operations as CpoOperation[] | undefined) ?? [],
    [commitQuery.data],
  );

  // Cobertura por fase: nº de operadores distintos atribuídos a cada fase.
  const coverage = useMemo(() => {
    const byPhase = new Map<string, { workers: Set<string>; ops: number }>();
    for (const op of operations) {
      const phase = op.phase_id ?? 'sem fase';
      const entry = byPhase.get(phase) ?? { workers: new Set(), ops: 0 };
      for (const w of op.workers) entry.workers.add(w);
      entry.ops += 1;
      byPhase.set(phase, entry);
    }
    return Array.from(byPhase.entries())
      .map(([phase, e]) => ({ phase, workers: e.workers.size, ops: e.ops }))
      .sort((a, b) => b.ops - a.ops);
  }, [operations]);

  if (commitsQuery.isLoading || (latestSha && commitQuery.isLoading)) {
    return <SkeletonLoader count={5} />;
  }
  if (latestSha === undefined) {
    return (
      <EmptyState
        title="Sem plano para analisar cobertura"
        hint="Corre o CPO (botão Replanear) para gerar um plano com atribuições de operadores."
        icon={<Users size={28} />}
      />
    );
  }
  if (operations.length === 0) {
    return (
      <EmptyState
        title="Plano sem operações"
        hint="O último commit do CPO não tem operações com atribuição de pessoas."
        icon={<Users size={28} />}
      />
    );
  }

  const opsWithoutWorker = operations.filter((o) => o.workers.length === 0).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <section
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionTitle
          icon={<Users size={14} />}
          title="Cobertura de pessoas por fase"
          subtitle="Operadores distintos atribuídos no plano actual do CPO"
        />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
            gap: 10,
          }}
        >
          {coverage.map((c) => (
            <div
              key={c.phase}
              style={{
                background: 'var(--bg-2)',
                border: '1px solid var(--bd-1)',
                borderLeft: `2px solid ${c.workers === 0 ? 'var(--orange)' : 'var(--green)'}`,
                borderRadius: 'var(--r-sm)',
                padding: 12,
              }}
            >
              <div style={{ fontSize: 11.5, color: 'var(--fg-1)', fontWeight: 500 }}>
                {c.phase}
              </div>
              <div
                className="display tabular"
                style={{
                  fontSize: 20,
                  fontWeight: 600,
                  marginTop: 4,
                  color: c.workers === 0 ? 'var(--orange)' : 'var(--green)',
                }}
              >
                {c.workers}
              </div>
              <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 2 }}>
                {c.workers === 1 ? 'operador' : 'operadores'} · {c.ops} ops
              </div>
            </div>
          ))}
        </div>
        {opsWithoutWorker > 0 && (
          <div
            style={{
              marginTop: 12,
              fontSize: 11.5,
              color: 'var(--orange)',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <AlertTriangle size={13} />
            {opsWithoutWorker} operações ainda sem operador atribuído.
          </div>
        )}
      </section>

      <section
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionTitle
          title="Relatório de prioridade"
          subtitle="O scheduler está a servir as ordens de maior receita primeiro?"
        />
        {priorityQuery.isLoading ? (
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>A carregar…</div>
        ) : priorityQuery.isError ? (
          <EmptyState
            title="Relatório de prioridade indisponível"
            hint="O endpoint /v1/plan/priority-report falhou para este commit."
            size="sm"
          />
        ) : priorityQuery.data ? (
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span
                className="display tabular"
                style={{
                  fontSize: 30,
                  fontWeight: 600,
                  color:
                    priorityQuery.data.alignment_pct >= 80
                      ? 'var(--green)'
                      : priorityQuery.data.alignment_pct >= 50
                        ? 'var(--yellow)'
                        : 'var(--red)',
                }}
              >
                {priorityQuery.data.alignment_pct.toFixed(0)}%
              </span>
              <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>
                alinhamento receita ↔ ordem do scheduler
              </span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
              {priorityQuery.data.inversions} inversões de{' '}
              {priorityQuery.data.max_inversions} possíveis ·{' '}
              {priorityQuery.data.items.length} ordens
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · MATERIAIS  (viabilidade do plano com stock actual)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Estado de risco de um material da BOM. `supply.material_master` está
 * vazio nesta instalação — os materiais reais são os componentes-folha das
 * BOMs (`/v1/supply/materials/from-bom`). Sem `min_stock` no shape, o
 * risco vem do stock real (`on_hand`) e da rutura prevista (Q.53.D).
 */
type BomRisk = 'sem-stock' | 'risco' | 'ok' | 'sem-leitura';

function bomRiskFor(m: BomMaterial): BomRisk {
  if (m.on_hand === null) return 'sem-leitura';
  if (m.on_hand <= 0) return 'sem-stock';
  // Rutura prevista para os próximos ~14 dias = risco para o plano.
  if (m.predicted_stockout_date) {
    const days =
      (new Date(m.predicted_stockout_date).getTime() - Date.now()) / 86_400_000;
    if (days <= 14) return 'risco';
  }
  return 'ok';
}

function MateriaisViabilityTab(): ReactNode {
  const materialsQuery = useQuery({
    queryKey: ['planeamento', 'materials-from-bom'],
    queryFn: () => materiaisApi.listMaterialsFromBom({ limit: 2000 }),
  });
  const envelope = materialsQuery.data;
  const materials = useMemo<BomMaterial[]>(
    () => envelope?.items ?? [],
    [envelope],
  );

  if (materialsQuery.isLoading) {
    return <SkeletonLoader count={4} />;
  }
  if (materialsQuery.isError) {
    return (
      <EmptyState
        title="Não foi possível verificar a viabilidade"
        hint="O endpoint /v1/supply/materials/from-bom falhou."
        icon={<Boxes size={28} />}
        action={
          <button
            type="button"
            onClick={() => materialsQuery.refetch()}
            style={{
              padding: '6px 14px',
              fontSize: 12,
              borderRadius: 'var(--r-sm)',
              background: 'var(--accent)',
              color: '#fff',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Tentar novamente
          </button>
        }
      />
    );
  }
  if (materials.length === 0) {
    return (
      <EmptyState
        title="Sem materiais para verificar"
        hint="Não há componentes-folha nas BOMs para este tenant."
        icon={<Boxes size={28} />}
      />
    );
  }

  const stockSynced = envelope?.stock_available ?? false;
  const rows = materials.map((m) => ({ material: m, risk: bomRiskFor(m) }));
  const critical = rows.filter(
    (r) => r.risk === 'sem-stock' || r.risk === 'risco',
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 12,
        }}
      >
        <KPIBig
          label="Materiais verificados"
          value={materials.length}
          status="accent"
        />
        <KPIBig
          label="Em risco"
          value={critical.length}
          status={critical.length > 0 ? 'red' : 'green'}
          accent={critical.length > 0 ? 'red' : 'green'}
        />
        <KPIBig
          label="Viabilidade do plano"
          value={
            !stockSynced ? '—' : critical.length === 0 ? 'OK' : 'Em risco'
          }
          context={
            !stockSynced
              ? envelope?.unavailable_reason ?? 'Stock do ERP não sincronizado'
              : critical.length === 0
                ? 'Stock cobre o plano actual'
                : `${critical.length} materiais podem bloquear barcos`
          }
          status={
            !stockSynced ? 'gray' : critical.length === 0 ? 'green' : 'red'
          }
        />
      </div>

      <section
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionTitle
          icon={<Boxes size={14} />}
          title="O plano é viável com o stock actual?"
          subtitle="Componentes-folha das BOMs cruzados com o stock do ERP — ligado à página Materiais"
        />
        {!stockSynced && (
          <div
            style={{
              marginBottom: 12,
              fontSize: 11.5,
              color: 'var(--orange)',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <AlertTriangle size={13} />
            {envelope?.unavailable_reason ??
              'Stock do ERP ainda não foi sincronizado — leituras indisponíveis.'}
          </div>
        )}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))',
            gap: 10,
          }}
        >
          {rows.map((r) => {
            const tone =
              r.risk === 'sem-stock'
                ? 'red'
                : r.risk === 'risco'
                  ? 'yellow'
                  : r.risk === 'sem-leitura'
                    ? 'gray'
                    : 'green';
            const m = r.material;
            return (
              <div
                key={m.id}
                style={{
                  background: 'var(--bg-2)',
                  border: '1px solid var(--bd-1)',
                  borderLeft: `2px solid var(--${tone})`,
                  borderRadius: 'var(--r-sm)',
                  padding: 11,
                }}
              >
                <div
                  style={{
                    fontSize: 11,
                    color: 'var(--fg-1)',
                    fontWeight: 500,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                  title={m.product_name}
                >
                  {m.product_name}
                </div>
                <div
                  className="tabular"
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    marginTop: 3,
                    color: tone === 'gray' ? 'var(--fg-3)' : `var(--${tone})`,
                  }}
                >
                  {m.on_hand !== null
                    ? `${m.on_hand.toLocaleString('pt-PT')} ${m.unit_of_measure}`
                    : '—'}
                </div>
                <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 2 }}>
                  {m.predicted_stockout_date
                    ? `rutura ~${new Date(
                        m.predicted_stockout_date,
                      ).toLocaleDateString('pt-PT', {
                        day: '2-digit',
                        month: 'short',
                      })}`
                    : m.on_hand === null
                      ? 'sem leitura de stock'
                      : 'sem rutura prevista'}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════

function SectionTitle({
  icon,
  title,
  subtitle,
}: {
  icon?: ReactNode;
  title: string;
  subtitle?: string;
}): ReactNode {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        {icon && <span style={{ color: 'var(--fg-2)' }}>{icon}</span>}
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
          {title}
        </span>
      </div>
      {subtitle && (
        <div style={{ fontSize: 11.5, color: 'var(--fg-3)', marginTop: 3 }}>
          {subtitle}
        </div>
      )}
    </div>
  );
}
