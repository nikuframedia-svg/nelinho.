/**
 * OverallPage — Planeamento redesenhado (C1..C4).
 *
 * 4 vistas sempre abertas em grelha (xl:2×2).
 * Seleção partilhada: clicar numa op/fase/barco/operador realça nas 4 vistas.
 * Drag-drop: DndContext separado por vista (sem colisão de ids).
 * Estética: superfícies em camadas, mono nos ids, acento único, motion staggered.
 */

import { useMemo, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { addDays, startOfDay, format } from 'date-fns';
import { pt } from 'date-fns/locale';
import { Calendar, AlertTriangle, Ship, RotateCcw } from 'lucide-react';
import { planKeys, fabricaKeys, coreKeys } from '../../lib/api/keys';
import { cpoCommitsApi, planOperationsApi, timelineActualsApi, phasesCatalogApi, copilotAlertsApi, planExclusionApi, schedulePreviewApi, filtersContextApi } from '../../lib/api';
import type { CpoCommit, TimelineActualItem, CopilotAlertItem, ExcludedBoat } from '../../lib/api';
import { PlanFilters } from '../../components/overall/PlanFilters';
import { filterOps, filtersToSearchParams, filtersFromSearchParams } from '../../components/overall/planFilterLogic';
import type { PlanFilterState } from '../../components/overall/planFilterLogic';
import { MoveBoatConfirm } from '../producao/MoveBoatConfirm';
import { fabricaApi } from '../producao/fabricaApi';
import type { ActiveOrderCard } from '../producao/fabricaApi';
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
import { OperationEditSheet } from '../../components/overall/OperationEditSheet';
import { CellOpsSheet } from '../../components/overall/CellOpsSheet';
import { planeamentoApi } from '../../components/planeamento/planeamentoApi';
import { CellExpandProvider } from '../../components/overall/cellExpand';
import { employeesApi } from '../../lib/api/masterDataApi';
import { useEntitySheet } from '../../components/entitySheets';

// ─── Constantes ───────────────────────────────────────────────────────────────

const DAYS_PAST = 7;
const DAYS_FUTURE = 15;

// ─── Tipos ───────────────────────────────────────────────────────────────────

type ViewMode = 'ver' | 'editar';
type TimelineScale = 'mes' | 'semana' | 'dia';
// Q.146.A — dimensão de agrupamento (vista única comutável, padrão APS:
// Dynamics Order↔Resource view). Substitui o quad de 4 painéis.
type GroupBy = 'fase' | 'barco' | 'pessoa' | 'expedicao';
const GROUP_TABS: { id: GroupBy; label: string }[] = [
  { id: 'fase', label: 'Fase' },
  { id: 'barco', label: 'Barco' },
  { id: 'pessoa', label: 'Pessoa' },
  { id: 'expedicao', label: 'Expedição' },
];

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
  const { openSheet } = useEntitySheet();
  const reducedMotion = usePrefersReducedMotion();
  const variants = reducedMotion ? reducedVariants : panelVariants;

  const today = startOfDay(new Date());
  const [windowStart, setWindowStart] = useState(() => addDays(today, -DAYS_PAST));
  const [windowEnd, setWindowEnd] = useState(() => addDays(today, DAYS_FUTURE));
  const [scale, setScale] = useState<TimelineScale>('dia');
  const [mode, setMode] = useState<ViewMode>('ver');
  const [groupBy, setGroupBy] = useState<GroupBy>('fase');
  // Q.147.B — ops da célula em drill-down (heatmap → lista).
  const [expandedCellOps, setExpandedCellOps] = useState<ScheduledOp[] | null>(null);
  // Q.173.AF — filtros estruturados (12, persistidos no URL).
  const [searchParams, setSearchParams] = useSearchParams();
  const planFilters: PlanFilterState = useMemo(
    () => filtersFromSearchParams(searchParams),
    [searchParams],
  );
  const setPlanFilters = useCallback(
    (f: PlanFilterState) => {
      const p = filtersToSearchParams(f);
      // Preservar params não-filtros (como ?tab=...) que possam existir.
      // Limpa só os que começam por f_
      const next = new URLSearchParams(searchParams);
      for (const key of Array.from(next.keys())) {
        if (key.startsWith('f_')) next.delete(key);
      }
      for (const [k, v] of p.entries()) next.append(k, v);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );
  // Q.153.C0 — "Só barcos" (ligado por defeito): esconde acessórios/straps das
  // vistas (a Por Barco inundava com ~1912 lanes de straps dos realizados).
  const [boatsOnly, setBoatsOnly] = useState(true);
  // Q.153.D1 — drag em curso a aguardar confirmação (preview→reorder). O drag
  // deixa de commitar logo: mostra a consequência (MoveBoatConfirm) e só escreve
  // após o motivo (≥10 chars). null = sem movimento pendente.
  const [pendingMove, setPendingMove] = useState<{
    op: ScheduledOp;
    newPhase: string;
    newStartTs: string;
    newOperatorId?: string;
  } | null>(null);
  // Q.149.C.3 — alertas de override manual já dispensados nesta sessão.
  const [dismissedAlerts, setDismissedAlerts] = useState<Set<string>>(() => new Set());

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

  // Q.158 — "barcos em produção" pela regra EXATA da NELO (snapshot da fábrica,
  // view factory_raw.v_of_em_producao). É a MESMA definição que o CPO planeia e
  // que o robô vigia. `boats_em_producao=null` (view ausente em dev) → não se
  // mostra KPI (zero-mocks, nunca inventa um número).
  const { data: factorySnapshot } = useQuery({
    queryKey: fabricaKeys.snapshot(),
    queryFn: () => fabricaApi.snapshot(),
    refetchInterval: 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const emProducao = factorySnapshot?.boats_em_producao ?? null;

  // ── Query ──────────────────────────────────────────────────────────────────
  const { data: commits, isLoading, isError, refetch } = useQuery({
    queryKey: planKeys.scheduleCurrent(),
    // Q.162.B — o "plano atual" é o último commit SAUDÁVEL. Um plano degenerado
    // (cobertura colapsada, ex.: falha transitória) nunca vira o atual só por ser
    // o mais recente — o grid continua a mostrar o último plano válido.
    queryFn: () => cpoCommitsApi.list({ limit: 1, excludeDegenerate: true }),
    refetchInterval: 30_000,
    // Q.144.D — voltar ao separador re-tenta (em vez de ficar preso no erro do
    // breaker quando o backend já recuperou).
    refetchOnWindowFocus: true,
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
    // Q.163 — boatsOnly na key: alternar "Mostrar acessórios" refaz o fetch.
    queryKey: [...planKeys.actuals(actualsFrom, actualsTo), actualsLimit, boatsOnly],
    queryFn: () =>
      timelineActualsApi.list({
        from: actualsFrom, to: actualsTo, granularity: 'raw', limit: actualsLimit,
        boats_only: boatsOnly,
      }),
    // Só vale a pena quando a janela inclui passado/hoje.
    enabled: windowStart <= today,
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Q.163 — catálogo canónico de fases (factory_raw.fases_producao), para a vista
  // "Por Fase" ordenar pela ordem REAL de produção (FP_SEQUENCIA) e rotular com o
  // nome canónico. Raramente muda → cache longa.
  const { data: phaseCatalog } = useQuery({
    queryKey: planKeys.phaseCatalog(),
    queryFn: () => phasesCatalogApi.list(),
    staleTime: 60 * 60 * 1000,
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Q.173.AD — contexto de filtros do Gantt (mapas de nomes/sectores/boosts).
  // Derivado do mesmo commit saudável que o plano — TTL 5 min, ≤5s de latência.
  const { data: filtersCtx } = useQuery({
    queryKey: planKeys.filtersContext(),
    queryFn: () => filtersContextApi.get(),
    staleTime: 5 * 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Q.147.C — operadores com NOMES reais (para o editor de operação). O plano
  // identifica operadores pelo `employee_code`, a mesma identidade do reorder.
  // Lista COMPLETA (incl. terminados): só serve para resolver código→nome de
  // ops históricas (empNameByCode); o dropdown usa a lista ATIVA abaixo.
  const employeesQuery = useQuery({
    queryKey: coreKeys.employeesForPlanEditor(),
    queryFn: () => employeesApi.list({ limit: 1000 }),
    staleTime: 10 * 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  // Q.159 — só operadores ATIVOS (E_ACTIVO + últimos 2 meses, ~107) para o
  // dropdown de atribuição. Key separada (não polui o mapa de nomes acima).
  const activeEmployeesQuery = useQuery({
    queryKey: coreKeys.employeesActiveForPlanEditor(),
    queryFn: () => employeesApi.list({ limit: 1000, active_only: true }),
    staleTime: 10 * 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  // Q.149.C.3 — overrides manuais que o reapply do robô já não conseguiu manter
  // (a pessoa escolhida deixou de bater com o WIP). Sem isto, a pessoa "revertia
  // sozinha" no replan sem o utilizador perceber porquê. Filtra-se pelo prefixo
  // do code porque cada alerta é MANUAL_OVERRIDE_INVALID:<op> (não fixo).
  const { data: overrideAlertsRaw } = useQuery({
    queryKey: planKeys.manualOverrideAlerts(),
    queryFn: () => copilotAlertsApi.list({ status: 'active', severity: 'WARN' }),
    refetchInterval: 30_000,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const overrideAlerts: CopilotAlertItem[] = useMemo(
    () =>
      (overrideAlertsRaw ?? []).filter(
        (a) => a.code.startsWith('MANUAL_OVERRIDE_INVALID') && !dismissedAlerts.has(a.id),
      ),
    [overrideAlertsRaw, dismissedAlerts],
  );

  // Q.148.B — mapa código→nome: o plano guarda códigos de worker; resolver para
  // nome real torna a mudança de operador VISÍVEL (drill/Por-pessoa/editor).
  const empNameByCode = useMemo(() => {
    const m = new Map<string, string>();
    for (const e of (employeesQuery.data ?? []) as Array<{
      employee_code?: string; employee_name?: string;
    }>) {
      if (e.employee_code && e.employee_name) {
        m.set(String(e.employee_code), String(e.employee_name));
      }
    }
    return m;
  }, [employeesQuery.data]);

  // ── Mutation Q.115.C ───────────────────────────────────────────────────────
  const [localOverrides, setLocalOverrides] = useState<
    Map<string, { phase_id: string; start: string }>
  >(new Map());

  const reorderMutation = useMutation({
    mutationFn: planOperationsApi.reorder,
    onSuccess: (resp) => {
      queryClient.invalidateQueries({ queryKey: planKeys.scheduleCurrent() });
      setLocalOverrides(new Map());
      setPendingMove(null); // Q.153.D1 — fecha o modal de confirmação no sucesso.
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

  // ── Q.153.B2 — Replanear (async) + Aprovar (DRAFT→LIVE) no /overall ─────────
  const [replanJobId, setReplanJobId] = useState<string | null>(null);

  const replanMutation = useMutation({
    mutationFn: () =>
      planeamentoApi.runScheduleAsync({
        horizon_days: 42,
        message: 'Replaneamento via /overall',
      }),
    onSuccess: (resp) => {
      setReplanJobId(resp.job_id);
      toast.info('Replaneamento em curso…');
    },
    onError: (err: unknown) => {
      const e = err as { message?: string };
      toast.error(`Falha ao replanear: ${e.message ?? 'erro desconhecido'}`);
    },
  });

  const replanJobQuery = useQuery({
    queryKey: ['cpo', 'replan-job', replanJobId],
    queryFn: () => planeamentoApi.pollScheduleJob(replanJobId as string),
    enabled: Boolean(replanJobId),
    refetchInterval: (query) => {
      const st = query.state.data?.state;
      return st === 'complete' || st === 'failed' ? false : 2000;
    },
  });

  useEffect(() => {
    const st = replanJobQuery.data?.state;
    if (!replanJobId || !st) return;
    if (st === 'complete') {
      queryClient.invalidateQueries({ queryKey: planKeys.scheduleCurrent() });
      toast.success('Novo plano pronto (Rascunho). Reveja e aprove.');
      setReplanJobId(null);
    } else if (st === 'failed') {
      toast.error(`Replaneamento falhou: ${replanJobQuery.data?.error ?? 'erro'}`);
      setReplanJobId(null);
    }
  }, [replanJobQuery.data?.state, replanJobId, queryClient, toast]);

  const approveMutation = useMutation({
    mutationFn: (sha: string) => planeamentoApi.approveCommit(sha),
    onSuccess: (resp) => {
      queryClient.invalidateQueries({ queryKey: planKeys.scheduleCurrent() });
      toast.success(`Plano aprovado · LIVE · ${resp.commit_sha256.slice(0, 8)}`);
    },
    onError: (err: unknown) => {
      const e = err as { status?: number; message?: string };
      if (e.status === 403) {
        toast.error('Não pode aprovar o plano que propôs (segregação de funções).');
      } else if (e.status === 409) {
        toast.info('Plano já está LIVE.');
      } else {
        toast.error(`Falha ao aprovar: ${e.message ?? 'erro desconhecido'}`);
      }
    },
  });

  // ── Q.153.C2 — barcos excluídos do plano (zona de remoção por drag) ─────────
  const excludedQuery = useQuery({
    queryKey: planKeys.excludedBoats(),
    queryFn: () => planExclusionApi.listExcludedBoats(),
  });
  const excludedBoats: ExcludedBoat[] = excludedQuery.data ?? [];

  const excludeMutation = useMutation({
    mutationFn: (orderId: string) => planExclusionApi.excludeBoat(orderId),
    onSuccess: (_resp, orderId) => {
      queryClient.invalidateQueries({ queryKey: planKeys.excludedBoats() });
      toast.info(`Barco ${orderId} excluído — Replaneie para aplicar`);
    },
    onError: (err: unknown) => {
      const e = err as { message?: string };
      toast.error(`Falha ao excluir: ${e.message ?? 'erro desconhecido'}`);
    },
  });

  const reincludeMutation = useMutation({
    mutationFn: (orderId: string) => planExclusionApi.reincludeBoat(orderId),
    onSuccess: (_resp, orderId) => {
      queryClient.invalidateQueries({ queryKey: planKeys.excludedBoats() });
      toast.success(`Barco ${orderId} reposto — Replaneie para aplicar`);
    },
    onError: (err: unknown) => {
      const e = err as { message?: string };
      toast.error(`Falha ao repor: ${e.message ?? 'erro desconhecido'}`);
    },
  });

  const handleExclude = useCallback(
    (orderId: string) => excludeMutation.mutate(orderId),
    [excludeMutation],
  );

  const isReplanning = replanMutation.isPending || Boolean(replanJobId);

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
          // Q.173.AF — nome real do modelo nas lanes (decisão da auditoria:
          // OF_P_ID cru era ilegível); código continua no tooltip/filtros.
          product_name: (() => {
            const code = op.product_id
              ? String(op.product_id)
              : op.order_id
                ? filtersCtx?.order_products?.[String(op.order_id)]
                : undefined;
            return code ? filtersCtx?.product_names?.[code] : undefined;
          })(),
          // Q.135.F4 — operadores vêm em `workers: [code,…]`, não `operator_id`.
          operator_id: op.operator_id
            ? String(op.operator_id)
            : Array.isArray(op.workers) && op.workers.length > 0
              ? String((op.workers as unknown[])[0])
              : undefined,
          operator_name: op.operator_name
            ? String(op.operator_name)
            : Array.isArray(op.workers) && op.workers.length > 0
              ? (op.workers as unknown[])
                  .map((w) => empNameByCode.get(String(w)) ?? String(w))
                  .join(' + ')
              : undefined,
          cliente: op.client_name ? String(op.client_name) : undefined,
          // Q.146.F — o commit envia `start_time/end_time/duration_minutes`; o
          // mapeamento lia `op.start/op.end/op.duration_min` (undefined) → todas as
          // ops de PLANO ficavam sem data → `dateToSlotIndex(undefined)`=null → o
          // plano (futuro) NUNCA renderizava (só os actuals). Fallback aos 2 nomes.
          start: override?.start ?? (op.start as string | undefined) ?? (op.start_time as string | undefined),
          end: (op.end as string | undefined) ?? (op.end_time as string | undefined),
          duration_min: (op.duration_min as number | undefined) ?? (op.duration_minutes as number | undefined),
          status: op.status as string | undefined,
          // Q.153.C0 — barco vs acessório (injectado pelo backend ao ler o commit).
          is_boat: typeof op.is_boat === 'boolean' ? op.is_boat : undefined,
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
        // Q.153.C3 — modelo (OF_P_ID) p/ abrir o ModeloSheet de barcos só-realizados.
        product_id: it.modelo_id ? String(it.modelo_id) : undefined,
        product_name: it.modelo_id
          ? filtersCtx?.product_names?.[String(it.modelo_id)]
          : undefined,
        operator_id: it.worker_id ?? undefined,
        operator_name: it.worker_nome ?? undefined,
        cliente: it.barco_nome ?? undefined,
        start: it.start,
        end: it.end ?? undefined,
        duration_min: it.duration_min ?? undefined,
        status: 'realizado',
        // Q.153.C0 — barco vs acessório/strap dos realizados (of_fp).
        is_boat: typeof it.is_boat === 'boolean' ? it.is_boat : undefined,
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
  }, [commitDetail, localOverrides, actualsData, empNameByCode, filtersCtx]);

  // Q.147.C — opções do editor de operação. Q.159 — só operadores ATIVOS
  // (a query já filtra via active_only; o `status === 'ACTIVE'` é defesa em
  // profundidade — o enum serializa UPPERCASE, por isso `!== 'inactive'` nunca
  // removia ninguém e mostrava os terminados).
  const operatorOptions = useMemo(() => {
    const rows = (activeEmployeesQuery.data ?? []) as Array<{
      employee_code?: string; employee_name?: string; status?: string;
    }>;
    return rows
      .filter((e) => e.employee_code && e.employee_name && e.status === 'ACTIVE')
      .map((e) => ({ code: String(e.employee_code), name: String(e.employee_name) }))
      .sort((a, b) => a.name.localeCompare(b.name, 'pt'));
  }, [activeEmployeesQuery.data]);

  const phaseOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const op of operations) {
      // Preferir um nome legível (actuals têm phase_nome) ao id numérico do plano.
      const cur = seen.get(op.phase_id);
      const better = op.phase_name && op.phase_name !== op.phase_id;
      if (!seen.has(op.phase_id) || (better && (!cur || cur === op.phase_id))) {
        seen.set(op.phase_id, op.phase_name ?? op.phase_id);
      }
    }
    return Array.from(seen.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name, 'pt'));
  }, [operations]);

  // Q.147.D / Q.173.AF — operações filtradas (alimentam as VISTAS; as opções do
  // editor e o editingOp usam `operations` completo). Filtrar esconde lanes vazias
  // (as lanes derivam das ops passadas à vista).
  const filteredOperations = useMemo(() => {
    // Q.153.C0 — "Só barcos" (ligado por defeito): esconde acessórios/straps
    // (is_boat===false). Mantém os de is_boat desconhecido (undefined) — honesto,
    // não esconde por omissão; a vista Por Barco passa de ~1912 lanes para barcos.
    let base = operations;
    if (boatsOnly) base = base.filter((o) => o.is_boat !== false);
    // Q.173.AF — 12 filtros estruturados (texto incluído em planFilters.text).
    return filterOps(base, filtersCtx, planFilters);
  }, [operations, boatsOnly, filtersCtx, planFilters]);

  // Op em edição: em modo Editar, clicar numa op de PLANO abre o editor.
  const editingOp = useMemo(() => {
    if (mode !== 'editar' || selection?.kind !== 'op') return null;
    const op = operations.find((o) => o.id === selection.id);
    return op && op.source !== 'actual' ? op : null;
  }, [mode, selection, operations]);

  // Q.148.C — clicar numa op REALIZADA (passado) em modo Editar → avisa que só
  // o plano futuro se edita (em vez de não acontecer nada). Ref evita re-disparos.
  const operationsRef = useRef(operations);
  operationsRef.current = operations;
  useEffect(() => {
    if (mode !== 'editar' || selection?.kind !== 'op') return;
    const op = operationsRef.current.find((o) => o.id === selection.id);
    if (op && op.source === 'actual') {
      toast.info('Operação já realizada — só o plano futuro se edita.');
    }
  }, [selection, mode, toast]);

  // ── Handler drag-drop central (Q.153.D1: preview → confirmar → reorder) ─────
  // Deixou de commitar logo. Guarda o movimento pendente; o MoveBoatConfirm
  // mostra a consequência (preview-delta) e só o `onConfirm(motivo)` escreve.
  const handleDrop = useCallback(
    (opId: string, newPhase: string, newStartTs: string, newOperatorId?: string) => {
      const op = operations.find((o) => o.id === opId);
      if (!op) return;
      reorderMutation.reset(); // limpa erro stale de um movimento anterior
      setPendingMove({ op, newPhase, newStartTs, newOperatorId });
    },
    [operations, reorderMutation],
  );

  // Q.153.D1 — preview da consequência do movimento pendente (read-only, NÃO
  // apply-move; o /overall conhece o operation_id directamente).
  const previewQuery = useQuery({
    queryKey: ['cpo', 'preview-delta', pendingMove?.op.id, pendingMove?.newPhase, pendingMove?.newOperatorId],
    queryFn: () =>
      schedulePreviewApi.previewDelta({
        operation_id: pendingMove!.op.id,
        new_phase_id: pendingMove!.newPhase,
        new_worker_ids: pendingMove!.newOperatorId ? [pendingMove!.newOperatorId] : undefined,
      }),
    enabled: Boolean(pendingMove),
  });

  const handleConfirmMove = useCallback(
    async (reason: string) => {
      if (!pendingMove) return;
      try {
        await reorderMutation.mutateAsync({
          operation_id: pendingMove.op.id,
          new_phase: pendingMove.newPhase,
          new_start_ts: pendingMove.newStartTs,
          new_operator_id: pendingMove.newOperatorId ?? null,
          reason,
        });
        // sucesso fecha o modal via onSuccess; erro mantém-no aberto (applyError).
      } catch {
        /* erro já tratado no onError (toast); modal fica aberto p/ ver o erro */
      }
    },
    [pendingMove, reorderMutation],
  );

  // ActiveOrderCard mínimo a partir da op (reuso do MoveBoatConfirm sem refactor).
  const pendingBoatCard: ActiveOrderCard | null = useMemo(() => {
    if (!pendingMove) return null;
    const op = pendingMove.op;
    return {
      id: op.id,
      hull: op.order_id ?? null,
      product_name: op.product_id ?? null,
      product_type: null,
      customer_name: op.cliente ?? null,
      phase: op.phase_name ?? op.phase_id,
      phase_sequence: null,
      status: op.status ?? 'plan',
      created_date: null,
      transport_date: null,
    };
  }, [pendingMove]);

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
    const s = new Set(filteredOperations.map((o) => o.order_id ?? o.id));
    return s.size;
  }, [filteredOperations]);

  const pessoaCount = useMemo(() => {
    const s = new Set(
      filteredOperations.map((o) => o.operator_id ?? o.operator_name ?? 'sem-operador'),
    );
    return s.size;
  }, [filteredOperations]);

  // Q.163 — nº de FASES distintas (não o total de ops). O chip "Fase" mostrava
  // `filteredOperations.length` (ex.: 1003 ops) e parecia "1003 fases" — confuso.
  const faseCount = useMemo(
    () => new Set(filteredOperations.map((o) => o.phase_id)).size,
    [filteredOperations],
  );

  // Q.153.C3 — product_id (modelo) da selecção, p/ abrir o editor de sequência
  // do modelo na tab Fases. Clicar numa op emite kind='op'; resolvemos o modelo
  // dessa op (ou de uma op do barco, se a selecção for um barco).
  const selectedBoatProductId = useMemo(() => {
    if (!selection) return null;
    if (selection.kind === 'op') {
      return operations.find((o) => o.id === selection.id)?.product_id ?? null;
    }
    if (selection.kind === 'boat') {
      return (
        operations.find((o) => (o.order_id ?? o.id) === selection.id && o.product_id)
          ?.product_id ?? null
      );
    }
    return null;
  }, [selection, operations]);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    // Q.146.A — capar ao viewport (TopBar=52px) + overflow-hidden: o `<main>` da
    // shell tem `min-h` sem `max` (cresce com o conteúdo), por isso o `h-full`
    // nunca capava. Assim a vista ativa faz scroll INTERNO em vez da página.
    <div className="flex flex-col h-[calc(100vh-52px)] overflow-hidden" style={{ minHeight: 0 }}>
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

            {/* Q.153.C3 — acesso de 1ª classe ao editor de sequência do modelo
                (abre o ModeloSheet na tab Fases) quando há um barco seleccionado. */}
            {selectedBoatProductId && (
              <DarkButton
                size="sm"
                variant="outline"
                onClick={() => openSheet('modelo', selectedBoatProductId)}
                title="Editar a sequência de fases deste modelo de barco"
              >
                Editar sequência do modelo
              </DarkButton>
            )}

            {/* Q.153.B2 — Replanear (async) + Aprovar (DRAFT→LIVE) */}
            <DarkButton
              size="sm"
              variant="secondary"
              disabled={isReplanning}
              onClick={() => replanMutation.mutate()}
            >
              {isReplanning ? 'A replanear…' : 'Replanear'}
            </DarkButton>

            {latestCommit && latestCommit.status !== 'LIVE' && (
              <DarkButton
                size="sm"
                variant="primary"
                disabled={approveMutation.isPending}
                onClick={() => approveMutation.mutate(latestCommit.commit_sha256)}
                title="Promover este plano de Rascunho para LIVE (aprovação humana)."
              >
                {approveMutation.isPending ? 'A aprovar…' : 'Aprovar plano'}
              </DarkButton>
            )}
          </div>
        }
      />

      {/* Q.146.A — overflow-hidden + flex-col: a página NÃO faz scroll; a vista
          ativa preenche o resto e faz scroll INTERNO (mata o super-scroll). */}
      <div className="flex-1 overflow-hidden p-4 flex flex-col gap-3 relative min-h-0">
        {/* AutoProposeOverlay — fantasmas PROPOSED (Q.115.M) */}
        <AutoProposeOverlay />

        {/* Faixa colapsável de riscos operacionais */}
        <RiskStrip />

        {/* Q.158 — KPI "barcos em produção" pela regra EXATA da NELO (≈830 =
            NOT fila). Mesma definição do CPO scope e do watermark do robô. Só
            aparece quando a view existe (zero-mocks). */}
        {emProducao && (
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs flex-shrink-0"
            style={{ background: 'var(--bg-3)', border: '1px solid var(--bd-2)' }}
          >
            <Ship size={13} style={{ color: 'var(--accent)' }} />
            <span className="font-mono tabular-nums text-sm font-semibold" style={{ color: 'var(--fg-1)' }}>
              {emProducao.em_producao.toLocaleString('pt-PT')}
            </span>
            <span style={{ color: 'var(--fg-2)' }}>barcos em produção</span>
            <span style={{ color: 'var(--fg-3)' }}>
              · fila{' '}
              <span className="font-mono tabular-nums" style={{ color: 'var(--fg-2)' }}>
                {emProducao.fila.toLocaleString('pt-PT')}
              </span>
            </span>
            {emProducao.reparacao > 0 && (
              <span style={{ color: 'var(--fg-3)' }}>
                · reparações{' '}
                <span className="font-mono tabular-nums" style={{ color: 'var(--fg-2)' }}>
                  {emProducao.reparacao.toLocaleString('pt-PT')}
                </span>
              </span>
            )}
            <span className="ml-auto" style={{ color: 'var(--fg-3)' }}>
              <span className="font-mono tabular-nums">{emProducao.total.toLocaleString('pt-PT')}</span>
              {' '}no plano (inclui fila)
            </span>
          </div>
        )}

        {/* Q.153.C2 — barcos excluídos do plano (repor no plano) */}
        {excludedBoats.length > 0 && (
          <div
            className="flex flex-col gap-1.5 rounded-lg p-2.5"
            style={{ background: 'var(--bg-3)', border: '1px solid var(--bd-2)' }}
          >
            <div className="flex items-center gap-2 text-xs font-semibold" style={{ color: 'var(--fg-2)' }}>
              <Ship size={13} />
              {excludedBoats.length === 1
                ? '1 barco excluído do plano'
                : `${excludedBoats.length} barcos excluídos do plano`}
              <span className="font-normal" style={{ color: 'var(--fg-3)' }}>
                — voltam no próximo replan se forem repostos
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {excludedBoats.map((b) => (
                <div
                  key={b.order_id}
                  className="flex items-center gap-2 px-2 py-1 rounded-md text-xs"
                  style={{ background: 'var(--bg-4)', border: '1px solid var(--bd-2)' }}
                >
                  <span className="font-mono tabular-nums" style={{ color: 'var(--fg-1)' }}>
                    {b.order_id}
                  </span>
                  {b.reason && (
                    <span className="truncate max-w-[160px]" style={{ color: 'var(--fg-3)' }} title={b.reason}>
                      {b.reason}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => reincludeMutation.mutate(b.order_id)}
                    disabled={reincludeMutation.isPending}
                    className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium transition disabled:opacity-50"
                    style={{ color: 'var(--accent)', background: 'transparent' }}
                    title="Repor este barco no plano"
                  >
                    <RotateCcw size={11} />
                    Repor no plano
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Q.149.C.3 — overrides manuais que o reapply do robô já não manteve */}
        {overrideAlerts.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {overrideAlerts.map((a) => (
              <div
                key={a.id}
                className="flex items-start gap-2 px-3 py-2 rounded-lg text-xs"
                style={{
                  background: 'var(--red-bg)',
                  border: '1px solid var(--red-bd)',
                  color: 'var(--red)',
                }}
              >
                <AlertTriangle size={13} className="flex-shrink-0 mt-0.5" />
                <span className="flex-1">{a.message_pt}</span>
                <button
                  type="button"
                  onClick={() => setDismissedAlerts((prev) => new Set(prev).add(a.id))}
                  className="flex-shrink-0 opacity-70 hover:opacity-100"
                  aria-label="Dispensar alerta"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

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
                    {latestCommit?.commit_sha256?.slice(0, 8) ?? '—'}
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

            {/* Q.146.A — Seletor "Agrupar por" (vista única comutável, padrão APS). */}
            <div className="flex items-center gap-1.5 flex-shrink-0 flex-wrap">
              <span
                className="text-[10px] uppercase tracking-wide font-semibold mr-1"
                style={{ color: 'var(--fg-3)' }}
              >
                Agrupar por
              </span>
              {GROUP_TABS.map((g) => {
                const active = groupBy === g.id;
                const cnt =
                  g.id === 'fase' ? faseCount
                  : g.id === 'barco' ? boatCount
                  : g.id === 'pessoa' ? pessoaCount
                  : null;
                return (
                  <button
                    key={g.id}
                    type="button"
                    onClick={() => setGroupBy(g.id)}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition"
                    style={
                      active
                        ? { background: 'var(--accent)', color: '#fff' }
                        : { color: 'var(--fg-2)', background: 'var(--bg-4)', border: '1px solid var(--bd-2)' }
                    }
                  >
                    {g.label}
                    {cnt != null && (
                      <span className="font-mono tabular-nums text-[10px]" style={{ opacity: 0.8 }}>
                        {cnt}
                      </span>
                    )}
                  </button>
                );
              })}

              {/* Q.153.C0 — "Só barcos": esconde acessórios/straps (ligado por
                  defeito). Sem isto a Por Barco mostra ~1912 lanes de straps. */}
              <button
                type="button"
                onClick={() => setBoatsOnly((b) => !b)}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition"
                style={
                  boatsOnly
                    ? { background: 'var(--accent)', color: '#fff' }
                    : { color: 'var(--fg-2)', background: 'var(--bg-4)', border: '1px solid var(--bd-2)' }
                }
                title={boatsOnly ? 'A mostrar só barcos — clica para incluir acessórios/straps' : 'A mostrar tudo — clica para só barcos'}
                aria-pressed={boatsOnly}
              >
                <Ship size={13} />
                {boatsOnly ? 'Só barcos' : 'Mostrar acessórios'}
              </button>
            </div>

            {/* Q.173.AF — barra de 12 filtros estruturados (substitui o input texto avulso). */}
            <PlanFilters
              filters={planFilters}
              onChange={setPlanFilters}
              ctx={filtersCtx}
              phaseCatalog={phaseCatalog}
              operators={operatorOptions}
              opCount={filteredOperations.length}
              boatCount={boatCount}
            />

            {/* Vista ativa — preenche o resto e faz scroll INTERNO (sem super-scroll). */}
            <CellExpandProvider value={setExpandedCellOps}>
            <motion.div
              key={groupBy}
              custom={0}
              initial="hidden"
              animate="visible"
              variants={variants}
              className="flex-1 min-h-0"
            >
              <ViewPanel
                title={`Por ${groupBy === 'expedicao' ? 'expedição' : groupBy}`}
                count={
                  groupBy === 'fase' ? faseCount
                  : groupBy === 'barco' ? boatCount
                  : groupBy === 'pessoa' ? pessoaCount
                  : undefined
                }
                selection={selection}
                onClearSelection={clearSelection}
                className="h-full"
              >
                {groupBy === 'expedicao' ? (
                  <PorExpedicaoView
                    startDate={windowStart}
                    endDate={windowEnd}
                    expeditions={actualsData?.expeditions ?? []}
                  />
                ) : operations.length === 0 ? (
                  <EmptyState
                    title="Sem operações"
                    hint="O commit activo não contém operações."
                  />
                ) : groupBy === 'fase' ? (
                  <PorFaseView
                    operations={filteredOperations}
                    phaseCatalog={phaseCatalog}
                    editable={mode === 'editar'}
                    startDate={windowStart}
                    endDate={windowEnd}
                    scale={ganttScale}
                    onDrop={handleDrop}
                    onExclude={handleExclude}
                    selection={selection}
                    onSelect={handleSelect}
                  />
                ) : groupBy === 'barco' ? (
                  <PorBarcoView
                    operations={filteredOperations}
                    editable={mode === 'editar'}
                    startDate={windowStart}
                    endDate={windowEnd}
                    scale={ganttScale}
                    onDrop={handleDrop}
                    onExclude={handleExclude}
                    selection={selection}
                    onSelect={handleSelect}
                  />
                ) : (
                  <PorPessoaView
                    operations={filteredOperations}
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
            </CellExpandProvider>
          </>
        )}
      </div>

      {/* Q.147.B — drill-down de uma célula densa (heatmap → lista de ops). */}
      {expandedCellOps && (
        <CellOpsSheet
          ops={expandedCellOps}
          onClose={() => setExpandedCellOps(null)}
          onPick={(op) => {
            handleSelect({ kind: 'op', id: op.id });
            setExpandedCellOps(null);
          }}
        />
      )}

      {/* Q.147.C — editor de operação (clicar numa op de plano em modo Editar). */}
      {editingOp && (
        <OperationEditSheet
          op={editingOp}
          operators={operatorOptions}
          phases={phaseOptions}
          isPending={reorderMutation.isPending}
          onClose={clearSelection}
          onSave={({ phaseId, operatorId, date }) =>
            reorderMutation.mutate(
              {
                operation_id: editingOp.id,
                new_phase: phaseId,
                new_start_ts: `${date}T08:00:00+00:00`,
                new_operator_id: operatorId || null,
              },
              { onSuccess: () => clearSelection() },
            )
          }
        />
      )}

      {/* Q.153.D1 — preview de consequência no drag → confirmar → reorder. */}
      {pendingMove && pendingBoatCard && (
        <MoveBoatConfirm
          boat={pendingBoatCard}
          targetPhase={pendingMove.newPhase}
          preview={previewQuery.data ?? null}
          previewLoading={previewQuery.isLoading}
          previewError={
            previewQuery.isError
              ? ((previewQuery.error as { message?: string })?.message ?? 'erro ao pré-visualizar')
              : null
          }
          applying={reorderMutation.isPending}
          applyError={
            reorderMutation.isError
              ? (() => {
                  const e = reorderMutation.error as {
                    status?: number;
                    data?: { axiom?: string; reason_pt?: string };
                    message?: string;
                  };
                  return e.status === 422 && e.data?.axiom
                    ? `Violou axioma "${e.data.axiom}": ${e.data.reason_pt ?? 'sem detalhe'}`
                    : (e.message ?? 'falha desconhecida');
                })()
              : null
          }
          onConfirm={handleConfirmMove}
          onCancel={() => setPendingMove(null)}
        />
      )}
    </div>
  );
}
