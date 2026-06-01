/**
 * OverallPage — Planeamento redesenhado (C1..C4).
 *
 * 4 vistas sempre abertas em grelha (xl:2×2).
 * Seleção partilhada: clicar numa op/fase/barco/operador realça nas 4 vistas.
 * Drag-drop: DndContext separado por vista (sem colisão de ids).
 * Estética: superfícies em camadas, mono nos ids, acento único, motion staggered.
 */

import { useMemo, useState, useCallback, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { addDays, startOfDay, format } from 'date-fns';
import { pt } from 'date-fns/locale';
import { Calendar, AlertTriangle } from 'lucide-react';
import { planKeys } from '../../lib/api/keys';
import { cpoCommitsApi, planOperationsApi, timelineActualsApi } from '../../lib/api';
import type { CpoCommit, TimelineActualItem } from '../../lib/api';
import { PageHeader, DarkCard, DarkButton, EmptyState } from '../../components/dark';
import { useToastContext } from '../../components/ToastProvider';
import { PorBarcoView } from '../../components/overall/views/PorBarcoView';
import { PorPessoaView } from '../../components/overall/views/PorPessoaView';
import { PorExpedicaoView } from '../../components/overall/views/PorExpedicaoView';
import { PorFaseView } from '../../components/overall/views/PorFaseView';
import type { ScheduledOp } from '../../components/overall/types';
import { AutoProposeOverlay } from '../../components/overall/AutoProposeOverlay';
import { ViewPanel } from '../../components/overall/ViewPanel';
import { RiskStrip } from '../../components/overall/RiskStrip';
import { PeriodSelector } from '../../components/overall/PeriodSelector';
import type { PlanSelection } from '../../components/overall/selection';
import { usePendingDecisions } from '../../hooks/usePendingDecisions';

// ─── Constantes ───────────────────────────────────────────────────────────────

const DAYS_PAST = 7;
const DAYS_FUTURE = 15;

// ─── Tipos ───────────────────────────────────────────────────────────────────

type ViewMode = 'ver' | 'editar';
type TimelineScale = 'mes' | 'semana' | 'dia';

// ─── Motion helpers ───────────────────────────────────────────────────────────

// Respeita prefers-reduced-motion: se activo, sem translateY nem fade
const panelVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: (delay: number) => ({ opacity: 1, y: 0, transition: { duration: 0.22, delay } }),
};

const reducedVariants = {
  hidden: { opacity: 1, y: 0 },
  visible: () => ({ opacity: 1, y: 0 }),
};

function usePrefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function OverallPage(): ReactNode {
  const toast = useToastContext();
  const queryClient = useQueryClient();
  const reducedMotion = usePrefersReducedMotion();
  const variants = reducedMotion ? reducedVariants : panelVariants;

  const today = startOfDay(new Date());
  const [windowStart, setWindowStart] = useState(() => addDays(today, -DAYS_PAST));
  const [windowEnd, setWindowEnd] = useState(() => addDays(today, DAYS_FUTURE));
  const [scale, setScale] = useState<TimelineScale>('dia');
  const [mode, setMode] = useState<ViewMode>('ver');

  // Q.141.F — escala PT do toggle → escala EN da Timeline (day/week/month).
  const ganttScale: 'day' | 'week' | 'month' =
    scale === 'dia' ? 'day' : scale === 'semana' ? 'week' : 'month';

  // ── Seleção partilhada entre as 4 vistas (C2) ─────────────────────────────
  const [selection, setSelection] = useState<PlanSelection | null>(null);

  const handleSelect = useCallback((sel: PlanSelection) => {
    setSelection((prev) =>
      prev && prev.kind === sel.kind && prev.id === sel.id ? null : sel,
    );
  }, []);

  const clearSelection = useCallback(() => setSelection(null), []);

  // Badge decisões pendentes
  const { decisions: pendingDecisions } = usePendingDecisions();

  // ── Query ──────────────────────────────────────────────────────────────────
  const { data: commits, isLoading, isError, refetch } = useQuery({
    queryKey: planKeys.scheduleCurrent(),
    queryFn: () => cpoCommitsApi.list({ limit: 1 }),
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });

  const latestCommit: CpoCommit | undefined = commits?.[0];

  const { data: commitDetail, isLoading: detailLoading } = useQuery({
    queryKey: [...planKeys.scheduleCurrent(), latestCommit?.commit_sha256 ?? 'none'],
    queryFn: () =>
      latestCommit
        ? cpoCommitsApi.get(latestCommit.commit_sha256, { include_operations: true })
        : Promise.resolve(null),
    enabled: Boolean(latestCommit),
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });

  // ── Q.141.H — actuals (o que ACONTECEU) no intervalo (passado real) ─────────
  const actualsFrom = format(windowStart, 'yyyy-MM-dd');
  const actualsTo = format(windowEnd, 'yyyy-MM-dd');
  // Q.141.J — sempre raw (para o gantt ter items em qualquer intervalo); cap
  // generoso nas escalas grossas (mês cheio ~17k fases) e leve no dia.
  const actualsLimit = scale === 'dia' ? 5000 : 20000;
  const { data: actualsData } = useQuery({
    queryKey: [...planKeys.actuals(actualsFrom, actualsTo), actualsLimit],
    queryFn: () =>
      timelineActualsApi.list({
        from: actualsFrom, to: actualsTo, granularity: 'raw', limit: actualsLimit,
      }),
    // Só vale a pena quando a janela inclui passado/hoje.
    enabled: windowStart <= today,
    retry: false,
    refetchOnWindowFocus: false,
  });

  // ── Mutation Q.115.C ───────────────────────────────────────────────────────
  const [localOverrides, setLocalOverrides] = useState<
    Map<string, { phase_id: string; start: string }>
  >(new Map());

  const reorderMutation = useMutation({
    mutationFn: planOperationsApi.reorder,
    onSuccess: (resp) => {
      queryClient.invalidateQueries({ queryKey: planKeys.scheduleCurrent() });
      setLocalOverrides(new Map());
      toast.success(`Plano actualizado · ${resp.commit_sha.slice(0, 8)}`);
    },
    onError: (err: unknown) => {
      const apiErr = err as { status?: number; data?: { axiom?: string; reason_pt?: string }; message?: string };
      if (apiErr.status === 422 && apiErr.data?.axiom) {
        toast.error(`Violou axioma "${apiErr.data.axiom}": ${apiErr.data.reason_pt ?? 'sem detalhe'}`);
      } else {
        toast.error(`Erro: ${apiErr.message ?? 'falha desconhecida'}`);
      }
      setLocalOverrides(new Map());
    },
  });

  // ── Operações = plano (futuro) + actuals (passado real), Q.141.H ────────────
  const operations: ScheduledOp[] = useMemo(() => {
    // Plano CPO (futuro) — tag source 'plan'.
    const planOps: ScheduledOp[] = (commitDetail?.operations ?? []).map(
      (op: Record<string, unknown>) => {
        const override = localOverrides.get(String(op.id ?? op.operation_id ?? ''));
        return {
          id: String(op.id ?? op.operation_id ?? ''),
          phase_id: override?.phase_id ?? String(op.phase_id ?? op.phase_name ?? 'UNKNOWN'),
          phase_name: String(op.phase_name ?? op.phase_id ?? 'UNKNOWN'),
          order_id: op.order_id ? String(op.order_id) : undefined,
          product_id: op.product_id ? String(op.product_id) : undefined,
          // Q.135.F4 — operadores vêm em `workers: [code,…]`, não `operator_id`.
          operator_id: op.operator_id
            ? String(op.operator_id)
            : Array.isArray(op.workers) && op.workers.length > 0
              ? String((op.workers as unknown[])[0])
              : undefined,
          operator_name: op.operator_name
            ? String(op.operator_name)
            : Array.isArray(op.workers) && op.workers.length > 0
              ? (op.workers as unknown[]).map((w) => String(w)).join(' + ')
              : undefined,
          cliente: op.client_name ? String(op.client_name) : undefined,
          start: override?.start ?? (op.start as string | undefined),
          end: op.end as string | undefined,
          duration_min: op.duration_min as number | undefined,
          status: op.status as string | undefined,
          source: 'plan',
        } satisfies ScheduledOp;
      },
    );

    // Actuals (passado real, of_fp) — tag source 'actual'.
    const actualOps: ScheduledOp[] = (actualsData?.items ?? []).map(
      (it: TimelineActualItem) => ({
        id: String(it.id ?? `act-${it.of_id}-${it.phase_id}-${it.start}`),
        phase_id: String(it.phase_id ?? 'UNKNOWN'),
        phase_name: String(it.phase_nome ?? it.phase_id ?? 'UNKNOWN'),
        order_id: it.of_id ? String(it.of_id) : undefined,
        operator_id: it.worker_id ?? undefined,
        operator_name: it.worker_nome ?? undefined,
        cliente: it.barco_nome ?? undefined,
        start: it.start,
        end: it.end ?? undefined,
        duration_min: it.duration_min ?? undefined,
        status: 'realizado',
        source: 'actual',
      } satisfies ScheduledOp),
    );

    // Dedupe: uma fase já REALIZADA (actual) não volta a aparecer como plano.
    const doneKeys = new Set(
      actualOps.map((o) => `${o.order_id ?? ''}__${o.phase_id}`),
    );
    const planFiltered = planOps.filter(
      (o) => !doneKeys.has(`${o.order_id ?? ''}__${o.phase_id}`),
    );
    return [...actualOps, ...planFiltered];
  }, [commitDetail, localOverrides, actualsData]);

  // ── Handler drag-drop central ──────────────────────────────────────────────
  const handleDrop = useCallback(
    (opId: string, newPhase: string, newStartTs: string, newOperatorId?: string) => {
      setLocalOverrides((prev) => {
        const next = new Map(prev);
        next.set(opId, { phase_id: newPhase, start: newStartTs });
        return next;
      });
      reorderMutation.mutate({
        operation_id: opId,
        new_phase: newPhase,
        new_start_ts: newStartTs,
        new_operator_id: newOperatorId ?? null,
      });
    },
    [reorderMutation],
  );

  // ── Reset window ───────────────────────────────────────────────────────────
  const resetToToday = useCallback(() => {
    const t = startOfDay(new Date());
    setWindowStart(addDays(t, -DAYS_PAST));
    setWindowEnd(addDays(t, DAYS_FUTURE));
  }, []);

  const windowLabel = `${format(windowStart, 'd MMM', { locale: pt })} – ${format(windowEnd, 'd MMM', { locale: pt })}`;
  const loadingAny = isLoading || detailLoading;

  // ── Contagens para headers dos painéis ────────────────────────────────────
  const boatCount = useMemo(() => {
    const s = new Set(operations.map((o) => o.order_id ?? o.id));
    return s.size;
  }, [operations]);

  const pessoaCount = useMemo(() => {
    const s = new Set(
      operations.map((o) => o.operator_id ?? o.operator_name ?? 'sem-operador'),
    );
    return s.size;
  }, [operations]);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full" style={{ minHeight: 0 }}>
      <PageHeader
        title="Planeamento"
        subtitle={windowLabel}
        icon={<Calendar size={18} />}
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            {pendingDecisions.length > 0 && (
              <Link
                to="/decisoes"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-amber-500/50 bg-amber-500/10 text-xs font-medium text-amber-300 hover:bg-amber-500/20 transition-colors"
                aria-label={`${pendingDecisions.length} decisões pendentes`}
              >
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400" />
                <span className="font-mono tabular-nums">{pendingDecisions.length}</span>
                {' '}{pendingDecisions.length === 1 ? 'decisão pendente' : 'decisões pendentes'}
              </Link>
            )}

            {/* Q.141.E — selector de intervalo (atalhos + custom) */}
            <PeriodSelector
              start={windowStart}
              end={windowEnd}
              today={today}
              onChange={({ start, end }) => {
                setWindowStart(start);
                setWindowEnd(end);
              }}
            />

            {/* Toggle escala */}
            <div
              className="flex items-center gap-0.5 rounded-lg p-0.5"
              style={{
                background: 'var(--bg-4)',
                border: '1px solid var(--bd-2)',
              }}
            >
              {(['dia', 'semana', 'mes'] as TimelineScale[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setScale(s)}
                  className="px-3 py-1 rounded-md text-xs font-medium transition"
                  style={
                    scale === s
                      ? { background: 'var(--accent)', color: '#fff' }
                      : { color: 'var(--fg-3)' }
                  }
                >
                  {s === 'dia' ? 'Dia' : s === 'semana' ? 'Semana' : 'Mês'}
                </button>
              ))}
            </div>

            <DarkButton variant="secondary" size="sm" onClick={resetToToday}>
              Hoje
            </DarkButton>

            <DarkButton
              size="sm"
              variant={mode === 'editar' ? 'primary' : 'secondary'}
              onClick={() => setMode((m) => (m === 'ver' ? 'editar' : 'ver'))}
            >
              {mode === 'ver' ? 'Editar' : 'A editar'}
            </DarkButton>
          </div>
        }
      />

      <div className="flex-1 overflow-auto p-4 space-y-3 relative">
        {/* AutoProposeOverlay — fantasmas PROPOSED (Q.115.M) */}
        <AutoProposeOverlay />

        {/* Faixa colapsável de riscos operacionais */}
        <RiskStrip />

        {/* Banner editar activo */}
        {mode === 'editar' && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs"
            style={{
              background: 'var(--yellow-bg)',
              border: '1px solid var(--yellow-bd)',
              color: 'var(--yellow)',
            }}
          >
            <AlertTriangle size={13} className="flex-shrink-0" />
            Modo editar activo — arrastar operação actualiza o plano via Q.115.C.
            {reorderMutation.isPending && (
              <span className="ml-1" style={{ color: 'var(--teal)' }}>A guardar…</span>
            )}
          </div>
        )}

        {/* Estados de carregamento / erro / vazio */}
        {loadingAny && (
          <DarkCard className="p-6 text-center text-sm text-[color:var(--fg-2)]">
            A carregar plano actual…
          </DarkCard>
        )}

        {!loadingAny && isError && (
          <EmptyState
            title="Erro ao carregar plano"
            hint="Não foi possível obter o schedule commit actual."
            action={
              <DarkButton size="sm" onClick={() => refetch()}>
                Tentar novamente
              </DarkButton>
            }
          />
        )}

        {!loadingAny && !isError && !latestCommit && (
          <EmptyState
            title="Sem plano activo"
            hint="Use Decisões para aprovar o primeiro plano ou corre POST /v1/plan/cpo/schedule."
          />
        )}

        {/* Quad-layout — 4 vistas sempre abertas */}
        {!loadingAny && !isError && (
          <>
            {/* Cabeçalho do quad: commit sha + contagem */}
            {latestCommit && (
              <div className="flex items-center gap-3 px-1">
                <span className="text-xs" style={{ color: 'var(--fg-3)' }}>
                  <span className="font-mono tabular-nums" style={{ color: 'var(--fg-2)' }}>
                    {operations.length}
                  </span>
                  {' '}operações · commit{' '}
                  <code
                    className="font-mono text-[11px] px-1 py-0.5 rounded"
                    style={{ background: 'var(--bg-4)', color: 'var(--fg-2)' }}
                  >
                    {latestCommit?.commit_sha256?.slice(0, 8) ?? latestCommit?.commit_sha256?.slice(0, 8) ?? '—'}
                  </code>
                </span>
                {/* Q.133.A.3 — rotular honestamente um plano não-aprovado/degradado:
                    nunca deixar um DRAFT/safety-net parecer o plano oficial. */}
                {latestCommit.status && latestCommit.status !== 'LIVE' && (
                  <span
                    className="text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide"
                    style={{ background: 'var(--yellow-bg)', border: '1px solid var(--yellow-bd)', color: 'var(--yellow)' }}
                    title="Plano ainda não aprovado — precisa de aprovação humana (DRAFT→LIVE) para ser oficial."
                  >
                    Rascunho · não aprovado
                  </span>
                )}
                {latestCommit.safety_net_triggered && (
                  <span
                    className="text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide"
                    style={{ background: 'var(--red-bg)', border: '1px solid var(--red-bd)', color: 'var(--red)' }}
                    title="O solver não superou a baseline — plano de recurso (safety-net), degradado."
                  >
                    Plano degradado
                  </span>
                )}
                {/* Q.141.H — legenda Realizado (sólido) vs Planeado (tracejado) */}
                <span className="flex items-center gap-2 text-[10px]" style={{ color: 'var(--fg-3)' }}>
                  <span className="inline-flex items-center gap-1">
                    <span
                      className="inline-block w-3 h-2 rounded-sm"
                      style={{ background: 'var(--green-bg)', border: '1px solid var(--green-bd)' }}
                    />
                    Realizado
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span
                      className="inline-block w-3 h-2 rounded-sm"
                      style={{ background: 'var(--gray-bg)', border: '1px dashed var(--gray-bd)' }}
                    />
                    Planeado
                  </span>
                </span>
                {actualsData?.truncated && (
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full"
                    style={{ background: 'var(--yellow-bg)', border: '1px solid var(--yellow-bd)', color: 'var(--yellow)' }}
                    title="Intervalo grande: a mostrar as fases mais recentes. Reduz o intervalo para veres tudo."
                  >
                    Realizado truncado · mais recentes
                  </span>
                )}
                {selection && (
                  <button
                    onClick={clearSelection}
                    className="text-xs px-2 py-0.5 rounded-full transition-colors"
                    style={{
                      background: 'var(--accent-bg)',
                      border: '1px solid var(--accent-bd)',
                      color: 'var(--accent)',
                    }}
                  >
                    Limpar filtro ✕
                  </button>
                )}
              </div>
            )}

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3" style={{ minHeight: 0 }}>
              {/* Painel 1 — Por fase */}
              <motion.div
                custom={0}
                initial="hidden"
                animate="visible"
                variants={variants}
                style={{ minHeight: 320 }}
              >
                <ViewPanel
                  title="Por fase"
                  count={operations.length}
                  selection={selection}
                  onClearSelection={clearSelection}
                >
                  {operations.length === 0 ? (
                    <EmptyState
                      title="Sem operações"
                      hint="O commit activo não contém operações."
                    />
                  ) : (
                    <PorFaseView
                      operations={operations}
                      editable={mode === 'editar'}
                      startDate={windowStart}
                      endDate={windowEnd}
                      scale={ganttScale}
                      onDrop={handleDrop}
                      selection={selection}
                      onSelect={handleSelect}
                    />
                  )}
                </ViewPanel>
              </motion.div>

              {/* Painel 2 — Por barco */}
              <motion.div
                custom={0.06}
                initial="hidden"
                animate="visible"
                variants={variants}
                style={{ minHeight: 320 }}
              >
                <ViewPanel
                  title="Por barco"
                  count={boatCount}
                  selection={selection}
                  onClearSelection={clearSelection}
                >
                  {operations.length === 0 ? (
                    <EmptyState
                      title="Sem operações"
                      hint="O commit activo não contém operações."
                    />
                  ) : (
                    <PorBarcoView
                      operations={operations}
                      editable={mode === 'editar'}
                      startDate={windowStart}
                      endDate={windowEnd}
                      scale={ganttScale}
                      onDrop={handleDrop}
                      selection={selection}
                      onSelect={handleSelect}
                    />
                  )}
                </ViewPanel>
              </motion.div>

              {/* Painel 3 — Por pessoa */}
              <motion.div
                custom={0.12}
                initial="hidden"
                animate="visible"
                variants={variants}
                style={{ minHeight: 320 }}
              >
                <ViewPanel
                  title="Por pessoa"
                  count={pessoaCount}
                  selection={selection}
                  onClearSelection={clearSelection}
                >
                  {operations.length === 0 ? (
                    <EmptyState
                      title="Sem operações"
                      hint="O commit activo não contém operações."
                    />
                  ) : (
                    <PorPessoaView
                      operations={operations}
                      editable={mode === 'editar'}
                      startDate={windowStart}
                      endDate={windowEnd}
                      scale={ganttScale}
                      onDrop={handleDrop}
                      selection={selection}
                      onSelect={handleSelect}
                    />
                  )}
                </ViewPanel>
              </motion.div>

              {/* Painel 4 — Por expedição */}
              <motion.div
                custom={0.18}
                initial="hidden"
                animate="visible"
                variants={variants}
                style={{ minHeight: 320 }}
              >
                <ViewPanel
                  title="Por expedição"
                  selection={selection}
                  onClearSelection={clearSelection}
                >
                  <PorExpedicaoView
                    startDate={windowStart}
                    endDate={windowEnd}
                    expeditions={actualsData?.expeditions ?? []}
                  />
                </ViewPanel>
              </motion.div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
