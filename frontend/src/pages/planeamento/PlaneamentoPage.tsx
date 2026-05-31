/**
 * PlaneamentoPage — Q.52.G · reconstrução do design NELO.
 *
 * 3 tabs: Barcos · Pessoas · Materiais. Substitui POR COMPLETO os dados
 * DEMO/fake das sub-tabs anteriores (Materiais/Forecast/Simulador) — agora
 * tudo vem de endpoints reais. ZERO MOCKS.
 *
 * - Barcos:    timeline arrastável das operações do último commit do CPO
 *              (cpoCommitsApi + schedulePreviewApi preview-delta/apply-move).
 *              Q.62.E.5 — "Replanear" agora usa POST /schedule/async +
 *              polling em /schedule/job/{id} para não bloquear a UI 30s.
 *              "Aprovar" depois promove ScheduleCommit.status DRAFT→LIVE.
 * - Pessoas:   cobertura por fase derivada das operações reais + relatório
 *              de prioridade (alinhamento receita ↔ scheduler).
 * - Materiais: viabilidade do plano com stock actual — /v1/supply/materials
 *              + .../position (PARTIAL → "—" honesto).
 */

import { useMemo, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CalendarRange,
  Boxes,
  Users,
  RefreshCw,
  Cuboid,
  AlertTriangle,
  BarChart2,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts/DarkPageLayout';
import { Segmented } from '../../components/dark/Segmented';
import { KPIBig } from '../../components/dark/KPIBig';
import { EmptyState } from '../../components/dark/EmptyState';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import {
  cpoCommitsApi,
  type CpoAlternativesResponse,
  type CpoAlternativeEnriched,
  type CpoRejectionCategory,
} from '../../lib/api';
import {
  BarcosTimeline,
  CpoGhostSuggestion,
} from '../../components/planeamento/BarcosTimeline';
import type {
  CpoOperation,
  AdherenceReport,
  AdherencePhase,
} from '../../components/planeamento/planeamentoApi';
import { planeamentoApi } from '../../components/planeamento/planeamentoApi';
import {
  materiaisApi,
  type BomMaterial,
} from '../../components/materiais/materiaisApi';

type TabId = 'barcos' | 'pessoas' | 'materiais' | 'aderencia';

const TABS: Array<{ value: TabId; label: string; icon: ReactNode }> = [
  { value: 'barcos', label: 'Barcos', icon: <Cuboid size={13} /> },
  { value: 'pessoas', label: 'Pessoas', icon: <Users size={13} /> },
  { value: 'materiais', label: 'Materiais', icon: <Boxes size={13} /> },
  { value: 'aderencia', label: 'Aderência', icon: <BarChart2 size={13} /> },
];

// ═══════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════

export default function PlaneamentoPage(): ReactNode {
  const [tab, setTab] = useState<TabId>('barcos');
  const queryClient = useQueryClient();

  // Q.62.E.5 — Replanear async via Arq + polling.
  //
  // Flow:
  //   1. mutation `enqueueReplan` chama POST /schedule/async → 202 + job_id.
  //   2. `useQuery` em /schedule/job/{id} faz polling cada 2s enquanto
  //      state ∈ {deferred, in_progress}; pára quando complete | failed.
  //   3. Quando complete, UI mostra "Aprovar" → PUT /schedule/job/{id}/approve
  //      muda ScheduleCommit.status DRAFT → LIVE.
  //
  // Manter `runSchedule` sync continua disponível em `planeamentoApi` para
  // testes/legacy, mas a página usa o caminho async (worker Arq deve estar up).
  const [jobId, setJobId] = useState<string | null>(null);

  const enqueueReplan = useMutation({
    mutationFn: () => planeamentoApi.runScheduleAsync({ horizon_days: 7 }),
    onSuccess: (data) => {
      setJobId(data.job_id);
    },
  });

  const jobStatusQuery = useQuery({
    queryKey: ['cpo-schedule-job', jobId],
    queryFn: () => planeamentoApi.pollScheduleJob(jobId as string),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 2000;
      // Para quando complete, failed, ou not_found.
      if (data.state === 'complete' || data.state === 'failed' || data.state === 'not_found') {
        return false;
      }
      return 2000; // polling cada 2s para deferred/in_progress.
    },
    refetchIntervalInBackground: false,
  });

  // Quando o job completa com sucesso, invalida queries para refrescar
  // o plano e tabelas dependentes.
  useEffect(() => {
    if (jobStatusQuery.data?.state === 'complete') {
      void queryClient.invalidateQueries({ queryKey: ['planeamento'] });
    }
  }, [jobStatusQuery.data?.state, queryClient]);

  const approveMutation = useMutation({
    mutationFn: () => planeamentoApi.approveScheduleJob(jobId as string),
    onSuccess: () => {
      // Após approve, libertar job_id (UI volta ao estado inicial).
      setJobId(null);
      void queryClient.invalidateQueries({ queryKey: ['planeamento'] });
    },
  });

  // Estado derivado para mostrar na UI / botão.
  const jobState = jobStatusQuery.data?.state;
  const isReplanning =
    enqueueReplan.isPending ||
    jobState === 'deferred' ||
    jobState === 'in_progress';
  const jobComplete = jobState === 'complete';
  const jobFailed = jobState === 'failed' || jobState === 'not_found';

  return (
    <DarkPageLayout
      title="Planeamento"
      subtitle="Plano dia/dia · 15 min · barcos, pessoas e materiais"
      icon={<CalendarRange size={18} />}
      actions={
        <div style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
          {/* Q.62.E.5 — botão Aprovar aparece quando o job está complete
              (commit ainda DRAFT). Click → PUT /approve → DRAFT → LIVE. */}
          {jobComplete && (
            <button
              type="button"
              onClick={() => approveMutation.mutate()}
              disabled={approveMutation.isPending}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 14px',
                fontSize: 12,
                fontWeight: 500,
                borderRadius: 'var(--r-sm)',
                background: 'var(--green)',
                color: '#fff',
                border: 'none',
                cursor: approveMutation.isPending ? 'wait' : 'pointer',
                opacity: approveMutation.isPending ? 0.7 : 1,
              }}
            >
              {approveMutation.isPending ? 'A aprovar…' : 'Aprovar (LIVE)'}
            </button>
          )}
          <button
            type="button"
            onClick={() => enqueueReplan.mutate()}
            disabled={isReplanning}
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
              cursor: isReplanning ? 'wait' : 'pointer',
              opacity: isReplanning ? 0.7 : 1,
            }}
          >
            <RefreshCw size={13} />
            {isReplanning ? 'A replanear…' : 'Replanear'}
          </button>
        </div>
      }
    >
      <div style={{ marginBottom: 16 }}>
        <Segmented options={TABS} value={tab} onChange={setTab} />
      </div>

      {/* Status do job async — Q.62.E.5 polling. */}
      {enqueueReplan.isError && (
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
          Falha a enfileirar replano:{' '}
          {enqueueReplan.error instanceof Error
            ? enqueueReplan.error.message
            : 'erro desconhecido'}
        </div>
      )}
      {isReplanning && jobId && (
        <div
          style={{
            marginBottom: 14,
            fontSize: 11.5,
            color: 'var(--accent)',
            background: 'var(--accent-bg)',
            border: '1px solid var(--accent-bd)',
            borderRadius: 'var(--r-sm)',
            padding: '8px 12px',
          }}
        >
          A processar plano · job {jobId.slice(0, 8)} ·{' '}
          estado: {jobState ?? 'a enfileirar'}
        </div>
      )}
      {jobFailed && (
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
          Job {jobId?.slice(0, 8)} falhou:{' '}
          {jobStatusQuery.data?.error ?? 'job não encontrado (worker desligado?)'}
        </div>
      )}
      {jobComplete && jobStatusQuery.data?.result && (
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
          Plano pronto (DRAFT) · {jobStatusQuery.data.result.operations.length}{' '}
          operações · makespan{' '}
          {jobStatusQuery.data.result.makespan_hours.toFixed(1)}h · clica em
          “Aprovar” para promover a LIVE.
          {jobStatusQuery.data.result.degraded
            ? ` · ATENÇÃO: plano degradado (${jobStatusQuery.data.result.fallback_reason ?? 'fallback'})`
            : ''}
        </div>
      )}
      {/* Q.131.H — honestidade: ordens que ficaram FORA do plano por não terem
          rota (sem histórico nem template do ERP). NÃO são "sem operador" —
          são ordens inteiras que o motor não soube planear. Mostradas, nunca
          omitidas em silêncio. */}
      {jobComplete &&
        jobStatusQuery.data?.result &&
        jobStatusQuery.data.result.unplanned_orders.length > 0 && (
          <div
            style={{
              marginBottom: 14,
              fontSize: 11.5,
              color: 'var(--orange)',
              background: 'var(--orange-bg)',
              border: '1px solid var(--orange-bd)',
              borderRadius: 'var(--r-sm)',
              padding: '8px 12px',
            }}
          >
            {jobStatusQuery.data.result.unplanned_orders.length} ordens sem rota
            conhecida (sem histórico nem template no ERP) ficaram FORA do plano —
            cobertura{' '}
            {(jobStatusQuery.data.result.orders_coverage * 100).toFixed(1)}%. OFs:{' '}
            {jobStatusQuery.data.result.unplanned_orders.slice(0, 8).join(', ')}
            {jobStatusQuery.data.result.unplanned_orders.length > 8
              ? ` (+${jobStatusQuery.data.result.unplanned_orders.length - 8})`
              : ''}
            . Precisam de histórico de produção ou template de routing.
          </div>
        )}
      {approveMutation.isSuccess && (
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
          Plano aprovado · commit {approveMutation.data.commit_sha256.slice(0, 8)}{' '}
          → {approveMutation.data.new_status}.
        </div>
      )}

      {tab === 'barcos' && (
        <BarcosTabView
          draftSha={
            jobComplete ? (jobStatusQuery.data?.result?.commit_sha256 ?? undefined) : undefined
          }
        />
      )}
      {tab === 'pessoas' && <PessoasTabView />}
      {tab === 'materiais' && <MateriaisViabilityTab />}
      {tab === 'aderencia' && <AderenciaTab />}
    </DarkPageLayout>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · BARCOS
// ═══════════════════════════════════════════════════════════════════════════

function BarcosTabView({ draftSha }: { draftSha?: string }): ReactNode {
  const commitsQuery = useQuery({
    queryKey: ['planeamento', 'cpo-commits'],
    queryFn: () => cpoCommitsApi.list({ limit: 1 }),
  });
  const latest = commitsQuery.data?.[0];

  // sha efectivo para as alternativas: DRAFT se houver, senão o LIVE
  const effectiveSha = draftSha ?? latest?.commit_sha256;

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
          Plano actual do CPO
        </h2>
        {draftSha && (
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              padding: '2px 7px',
              borderRadius: 'var(--r-sm)',
              background: 'var(--orange-bg)',
              border: '1px solid var(--orange-bd)',
              color: 'var(--orange)',
            }}
          >
            DRAFT — por aprovar
          </span>
        )}
        <p style={{ fontSize: 11.5, color: 'var(--fg-3)', margin: 0 }}>
          Granularidade 15 min · arrasta uma operação para outra fase para ver a
          consequência
        </p>
      </div>
      <BarcosTimeline overrideSha={draftSha} />
      {!draftSha && <CpoGhostSuggestion commit={latest} />}
      {effectiveSha && <AlternativasPanel sha={effectiveSha} />}
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
// Q.132.H — ALTERNATIVAS MAP-Elites acionáveis
// ═══════════════════════════════════════════════════════════════════════════

const REJECTION_CATEGORIES: CpoRejectionCategory[] = [
  'COST', 'QUALITY', 'CUSTOMER', 'CAPACITY', 'MOLD', 'WORKFORCE', 'OTHER',
];

function AlternativasPanel({ sha }: { sha: string }): ReactNode {
  const queryClient = useQueryClient();

  const altsQuery = useQuery<CpoAlternativesResponse>({
    queryKey: ['planeamento', 'cpo-alternatives', sha],
    queryFn: () => cpoCommitsApi.alternatives(sha),
    retry: 0,
  });

  const [choosingIdx, setChoosingIdx] = useState<number | null>(null);
  const [reason, setReason] = useState('');
  const [category, setCategory] = useState<CpoRejectionCategory>('OTHER');

  const decideMutation = useMutation({
    mutationFn: ({
      chosenIdx,
      rejectedIdxs,
    }: {
      chosenIdx: number;
      rejectedIdxs: number[];
    }) =>
      cpoCommitsApi.decide(sha, {
        chosen_alt_idx: chosenIdx,
        rejected_alt_idxs: rejectedIdxs,
        reason,
        rejection_category: rejectedIdxs.length > 0 ? category : null,
      }),
    onSuccess: () => {
      setChoosingIdx(null);
      setReason('');
      void queryClient.invalidateQueries({ queryKey: ['planeamento'] });
    },
  });

  if (altsQuery.isLoading) {
    return (
      <div style={{ marginTop: 14 }}>
        <SkeletonLoader count={2} />
      </div>
    );
  }

  // Sem alternativas (inclui erro 404 — commit sem MAP-Elites): empty state silencioso
  if (altsQuery.isError || !altsQuery.data || altsQuery.data.alternatives.length === 0) {
    return null;
  }

  const alts: CpoAlternativeEnriched[] = altsQuery.data.alternatives;

  return (
    <div
      style={{
        marginTop: 18,
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding: 18,
      }}
    >
      <SectionTitle
        icon={<RefreshCw size={14} />}
        title="Alternativas MAP-Elites"
        subtitle={`${alts.length} alternativas geradas pelo CPO — escolhe uma para registar a tua preferência`}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {alts.map((alt, idx) => {
          const isChoosing = choosingIdx === idx;
          return (
            <div
              key={idx}
              style={{
                background: 'var(--bg-2)',
                border: `1px solid ${isChoosing ? 'var(--accent-bd)' : 'var(--bd-1)'}`,
                borderRadius: 'var(--r-sm)',
                padding: 12,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-0)', marginBottom: 2 }}>
                    Alt {idx + 1}
                    {alt.rank !== undefined && (
                      <span style={{ fontSize: 10.5, color: 'var(--fg-3)', fontWeight: 400, marginLeft: 6 }}>
                        rank {alt.rank} · fitness {alt.fitness.toFixed(0)}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--fg-2)', marginBottom: 6 }}>
                    {alt.trade_off_narrative}
                  </div>
                  {Object.keys(alt.vs_primary).length > 0 && (
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {Object.entries(alt.vs_primary).map(([k, v]) =>
                        v ? (
                          <span
                            key={k}
                            style={{
                              fontSize: 10.5,
                              padding: '1px 6px',
                              borderRadius: 4,
                              background: 'var(--bg-0)',
                              border: '1px solid var(--bd-1)',
                              color: 'var(--fg-2)',
                            }}
                          >
                            {k}: {v}
                          </span>
                        ) : null,
                      )}
                    </div>
                  )}
                </div>
                {!isChoosing && (
                  <button
                    type="button"
                    onClick={() => {
                      setChoosingIdx(idx);
                      setReason('');
                    }}
                    disabled={decideMutation.isPending}
                    style={{
                      flexShrink: 0,
                      padding: '5px 12px',
                      fontSize: 11.5,
                      fontWeight: 500,
                      borderRadius: 'var(--r-sm)',
                      background: 'var(--accent-bg)',
                      border: '1px solid var(--accent-bd)',
                      color: 'var(--accent)',
                      cursor: 'pointer',
                    }}
                  >
                    Escolher
                  </button>
                )}
              </div>
              {isChoosing && (
                <div style={{ marginTop: 10, borderTop: '1px solid var(--bd-1)', paddingTop: 10 }}>
                  <div style={{ marginBottom: 8 }}>
                    <label style={{ fontSize: 11, color: 'var(--fg-2)', display: 'block', marginBottom: 4 }}>
                      Razão (mínimo 10 caracteres)
                    </label>
                    <textarea
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Ex: menos setups na laminagem esta semana"
                      rows={2}
                      style={{
                        width: '100%',
                        padding: '6px 8px',
                        fontSize: 12,
                        background: '#fff',
                        color: 'var(--slate-900, #0f172a)',
                        border: '1px solid var(--bd-1)',
                        borderRadius: 'var(--r-sm)',
                        resize: 'vertical',
                        boxSizing: 'border-box',
                      }}
                    />
                  </div>
                  <div style={{ marginBottom: 10 }}>
                    <label style={{ fontSize: 11, color: 'var(--fg-2)', display: 'block', marginBottom: 4 }}>
                      Categoria de rejeição das restantes
                    </label>
                    <select
                      value={category}
                      onChange={(e) => setCategory(e.target.value as CpoRejectionCategory)}
                      style={{
                        padding: '5px 8px',
                        fontSize: 12,
                        background: '#fff',
                        color: 'var(--slate-900, #0f172a)',
                        border: '1px solid var(--bd-1)',
                        borderRadius: 'var(--r-sm)',
                      }}
                    >
                      {REJECTION_CATEGORIES.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                  {decideMutation.isError && (
                    <div style={{ fontSize: 11.5, color: 'var(--red)', marginBottom: 8 }}>
                      {decideMutation.error instanceof Error
                        ? decideMutation.error.message
                        : 'Erro ao registar decisão.'}
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      type="button"
                      onClick={() => {
                        if (reason.length < 10) return;
                        const rejectedIdxs = alts
                          .map((_, i) => i)
                          .filter((i) => i !== idx);
                        decideMutation.mutate({ chosenIdx: idx, rejectedIdxs });
                      }}
                      disabled={reason.length < 10 || decideMutation.isPending}
                      style={{
                        padding: '5px 14px',
                        fontSize: 12,
                        fontWeight: 500,
                        borderRadius: 'var(--r-sm)',
                        background: reason.length < 10 ? 'var(--bg-2)' : 'var(--accent)',
                        color: reason.length < 10 ? 'var(--fg-3)' : '#fff',
                        border: 'none',
                        cursor: reason.length < 10 || decideMutation.isPending ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {decideMutation.isPending ? 'A registar…' : 'Confirmar escolha'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setChoosingIdx(null)}
                      disabled={decideMutation.isPending}
                      style={{
                        padding: '5px 12px',
                        fontSize: 12,
                        borderRadius: 'var(--r-sm)',
                        background: 'transparent',
                        border: '1px solid var(--bd-1)',
                        color: 'var(--fg-2)',
                        cursor: 'pointer',
                      }}
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {decideMutation.isSuccess && (
        <div
          style={{
            marginTop: 12,
            fontSize: 11.5,
            color: 'var(--green)',
            background: 'var(--green-bg)',
            border: '1px solid var(--green-bd)',
            borderRadius: 'var(--r-sm)',
            padding: '8px 12px',
          }}
        >
          Preferência registada — o detector de regras vai aprender com esta escolha.
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Q.132.E — TAB · ADERÊNCIA
// ═══════════════════════════════════════════════════════════════════════════

function AderenciaTab(): ReactNode {
  const adherenceQuery = useQuery<AdherenceReport>({
    queryKey: ['planeamento', 'adherence'],
    queryFn: () => planeamentoApi.adherence(),
    retry: 0,
  });

  if (adherenceQuery.isLoading) {
    return <SkeletonLoader count={4} />;
  }

  if (adherenceQuery.isError) {
    return (
      <EmptyState
        title="Não foi possível carregar a aderência"
        hint="O endpoint /v1/plan/adherence falhou."
        icon={<BarChart2 size={28} />}
        action={
          <button
            type="button"
            onClick={() => adherenceQuery.refetch()}
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

  const report = adherenceQuery.data;

  if (!report?.has_committed_plan) {
    return (
      <EmptyState
        title="Sem plano comprometido para comparar"
        hint="Aprova um plano do CPO (fica LIVE) para começar a medir a aderência. Os dados de realização vêm do ERP em tempo real."
        icon={<BarChart2 size={28} />}
      />
    );
  }

  const { summary, phases } = report;
  const pct = summary.adherence_pct;
  const pctColor =
    pct === null ? 'var(--fg-3)' : pct >= 80 ? 'var(--green)' : pct >= 50 ? 'var(--yellow)' : 'var(--red)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* Resumo */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 12,
        }}
      >
        <KPIBig
          label="Operações planeadas"
          value={summary.total_planned_ops}
          status="accent"
        />
        <KPIBig
          label="Realizadas"
          value={summary.total_realised_ops}
          status={summary.total_realised_ops > 0 ? 'green' : 'gray'}
        />
        <KPIBig
          label="Aderência global"
          value={pct !== null ? `${pct.toFixed(1)}%` : '—'}
          status={
            pct === null ? 'gray' : pct >= 80 ? 'green' : pct >= 50 ? 'yellow' : 'red'
          }
        />
      </div>

      {/* Tabela por fase */}
      <section
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionTitle
          icon={<BarChart2 size={14} />}
          title="Aderência por fase"
          subtitle={`Commit ${report.commit_sha ? report.commit_sha.slice(0, 8) : '—'} · ${phases.length} fases`}
        />
        {phases.length === 0 ? (
          <EmptyState
            title="Sem fases para mostrar"
            hint="O plano activo não tem operações por fase registadas."
            size="sm"
          />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--bd-1)' }}>
                  {(['Fase', 'Planeadas', 'Realizadas', 'Aderência %', 'Taxa defeito %'] as const).map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: '6px 10px',
                        textAlign: 'left',
                        fontSize: 10.5,
                        textTransform: 'uppercase',
                        letterSpacing: 0.4,
                        color: 'var(--fg-3)',
                        fontWeight: 600,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {phases.map((ph: AdherencePhase) => {
                  const rowPct = ph.adherence_pct;
                  const rowColor =
                    rowPct === null
                      ? 'var(--fg-3)'
                      : rowPct >= 80
                        ? 'var(--green)'
                        : rowPct >= 50
                          ? 'var(--yellow)'
                          : 'var(--red)';
                  return (
                    <tr
                      key={ph.phase_id}
                      style={{ borderBottom: '1px solid var(--bd-1)' }}
                    >
                      <td style={{ padding: '8px 10px', color: 'var(--fg-0)', fontWeight: 500 }}>
                        {ph.phase_id}
                      </td>
                      <td className="tabular" style={{ padding: '8px 10px', color: 'var(--fg-1)' }}>
                        {ph.planned_ops}
                      </td>
                      <td className="tabular" style={{ padding: '8px 10px', color: 'var(--fg-1)' }}>
                        {ph.realised_ops}
                      </td>
                      <td
                        className="tabular"
                        style={{ padding: '8px 10px', color: rowColor, fontWeight: 600 }}
                      >
                        {rowPct !== null ? `${rowPct.toFixed(1)}%` : '—'}
                      </td>
                      <td
                        className="tabular"
                        style={{
                          padding: '8px 10px',
                          color: ph.defect_rate_pct !== null && ph.defect_rate_pct > 5
                            ? 'var(--red)'
                            : 'var(--fg-2)',
                        }}
                      >
                        {ph.defect_rate_pct !== null ? `${ph.defect_rate_pct.toFixed(1)}%` : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {report.commit_created_at && (
          <div style={{ marginTop: 10, fontSize: 10.5, color: 'var(--fg-3)' }}>
            Commit criado em{' '}
            {new Date(report.commit_created_at).toLocaleString('pt-PT', {
              day: '2-digit',
              month: 'short',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </div>
        )}
      </section>

      {/* Resumo visual da aderência global */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          fontSize: 13,
          color: 'var(--fg-2)',
        }}
      >
        <span style={{ fontSize: 32, fontWeight: 700, color: pctColor }} className="display tabular">
          {pct !== null ? `${pct.toFixed(1)}%` : '—'}
        </span>
        <span>de aderência ao plano · {summary.n_phases} fases analisadas</span>
      </div>
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
