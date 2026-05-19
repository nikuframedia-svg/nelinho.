/**
 * FabricaPage — war room: Kanban de fases + atribuição dinâmica (Q.52.F).
 *
 * Onda 1 · T1 · Q.54.C/D. Reconstrução fiel do `page-fabrica.jsx` do
 * design NELO: strip de KPIs, colunas-fase Kanban com drag-drop
 * bidirecional e o rail de operadores com fit-scoring. Ligada a
 * endpoints REAIS:
 *   - /v1/plan/orders/active            (cartões de barco, com
 *                                        phase_sequence p/ ordenar)
 *   - /v1/plan/cpo/commits/latest/orders (plano optimizado do CPO)
 *   - /v1/factory-map/snapshot          (score de gargalo por fase)
 *   - /v1/core/employees                (operadores)
 *   - POST /v1/workforce/employees/profiles (perfis em LOTE — uma só
 *                                        chamada substitui o fan-out
 *                                        de ~3×N pedidos que congelava)
 *   - /v1/plan/schedule/preview-delta   (consequência do drag)
 *   - /v1/plan/schedule/apply-move      (persistir o movimento)
 *   - /v1/hr/allocations/daily          (atribuir operador → barco)
 *
 * Q.54.C — colunas ordenadas pela sequência de routing NELO
 * (`phase_sequence`), não alfabética; perfis de operador pré-carregados
 * em lote → atribuição instantânea.
 * Q.54.D — toggle "Plano sugerido" alterna estado cru ↔ plano CPO.
 *
 * DnD bidirecional via HTML5 dataTransfer (MIME application/x-nelo-dnd):
 * `boat` arrasta entre colunas-fase; `worker` arrasta para os cartões.
 *
 * ZERO MOCKS: as colunas derivam das fases reais presentes nas ordens +
 * scores de gargalo do snapshot. Sem ordens / sem operadores → empty
 * state honesto. O movimento de barco passa SEMPRE pelo preview antes
 * de persistir — nunca aplica às cegas.
 */

import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { Factory, Layers, Sparkles, X } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkButton, EmptyState, LiveBadge } from '../../components/dark';
import {
  allocationsApi,
  employeesApi,
  schedulePreviewApi,
  type PreviewDeltaResult,
} from '../../lib/api';
import { fabricaApi } from './fabricaApi';
import type { ActiveOrderCard, OptimizedOrderCard } from './fabricaApi';
import { FabricaPhaseColumn } from './FabricaPhaseColumn';
import type { PhaseColumnModel } from './FabricaPhaseColumn';
import type { AssignedWorker } from './BoatAssignCard';
import { WorkersStrip } from './WorkersStrip';
import type { WorkerProfile } from './fabricaScoring';
import { BoatDetailSheet } from './BoatDetailSheet';
import { MoveBoatConfirm } from './MoveBoatConfirm';
import { ImpactToast } from './ImpactToast';
import type { ImpactToastData } from './ImpactToast';

interface PendingMove {
  boat: ActiveOrderCard;
  targetPhase: string;
}

interface EmployeeRow {
  id: string;
  name: string;
}

function deriveInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '—';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Vista da Fábrica: estado cru vs plano optimizado do CPO. */
type FabricaView = 'estado' | 'plano';

export function FabricaPage(): ReactNode {
  const queryClient = useQueryClient();

  // ─── Vista: Estado actual vs Plano sugerido (Q.54.D) ────────────────────
  const [view, setView] = useState<FabricaView>('estado');

  // ─── Ordens activas ─────────────────────────────────────────────────────
  const ordersQuery = useQuery({
    queryKey: ['fabrica', 'orders'],
    queryFn: () => fabricaApi.activeOrders({ limit: 500 }),
    refetchOnWindowFocus: false,
  });

  // ─── Plano optimizado do CPO (só carrega na vista "plano") ──────────────
  const planQuery = useQuery({
    queryKey: ['fabrica', 'plan', 'latest'],
    queryFn: () => fabricaApi.commitOrders('latest'),
    refetchOnWindowFocus: false,
    enabled: view === 'plano',
    retry: false,
  });

  // ─── Snapshot (score de gargalo por fase) ───────────────────────────────
  const snapshotQuery = useQuery({
    queryKey: ['fabrica', 'snapshot'],
    queryFn: () => fabricaApi.snapshot(),
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });

  // ─── Operadores ─────────────────────────────────────────────────────────
  const employeesQuery = useQuery({
    queryKey: ['fabrica', 'employees'],
    queryFn: () => employeesApi.list({ limit: 200, status: 'ACTIVE' }),
    refetchOnWindowFocus: false,
    staleTime: 5 * 60_000,
  });

  const employees: EmployeeRow[] = useMemo(() => {
    const raw =
      (employeesQuery.data as { data?: unknown[] } | undefined)?.data ??
      employeesQuery.data;
    if (!Array.isArray(raw)) return [];
    return raw
      .map((e) => {
        const rec = e as Record<string, unknown>;
        const id = rec.id ?? rec.employee_id;
        if (!id) return null;
        const parts = [rec.first_name, rec.last_name].filter(Boolean);
        const name =
          (rec.employee_name as string) ||
          (parts.join(' ') as string) ||
          (rec.full_name as string) ||
          (rec.name as string) ||
          String(id).slice(0, 8);
        return { id: String(id), name };
      })
      .filter((x): x is EmployeeRow => x !== null);
  }, [employeesQuery.data]);

  // ─── Perfis de operador em LOTE (Q.54.C) ────────────────────────────────
  // Uma só chamada batch substitui o fan-out de ~3×N pedidos que congelava
  // a página. Pré-carregada no load (não só ao clicar num barco) → a
  // atribuição é instantânea.
  const employeeIds = useMemo(
    () => employees.map((e) => e.id),
    [employees],
  );
  const profilesQuery = useQuery({
    queryKey: ['fabrica', 'profiles', employeeIds],
    queryFn: () => fabricaApi.employeeProfiles(employeeIds),
    enabled: employeeIds.length > 0,
    refetchOnWindowFocus: false,
    staleTime: 5 * 60_000,
    retry: false,
  });

  // ─── State da página ────────────────────────────────────────────────────
  const [activeBoatId, setActiveBoatId] = useState<string | null>(null);
  const [draggedBoatId, setDraggedBoatId] = useState<string | null>(null);
  const [sheetBoatId, setSheetBoatId] = useState<string | null>(null);
  const [pendingMove, setPendingMove] = useState<PendingMove | null>(null);
  const [toast, setToast] = useState<ImpactToastData | null>(null);
  // Atribuições optimistas locais (order id → worker ids). A fonte de
  // verdade é o backend; isto é o eco visual imediato do drag.
  const [assignments, setAssignments] = useState<Record<string, string[]>>(
    {},
  );

  // No modo "plano" as ordens vêm do commit optimizado; no modo "estado"
  // vêm do snapshot cru.
  const rawOrders = ordersQuery.data ?? [];
  const planOrders = planQuery.data?.orders ?? [];
  const orders: ActiveOrderCard[] =
    view === 'plano' ? planOrders : rawOrders;

  // ─── Fit-scoring: perfis vindos da chamada batch (Q.54.C) ───────────────
  // Indexa o resultado batch por employee_id para o cruzar com a lista.
  const workerProfiles: WorkerProfile[] = useMemo(() => {
    const byId = new Map(
      (profilesQuery.data?.profiles ?? []).map((p) => [
        p.employee_id,
        p,
      ]),
    );
    return employees.map((e) => {
      const p = byId.get(e.id);
      return {
        id: e.id,
        name: e.name,
        quality: p?.quality_score ?? undefined,
        skills: p?.skill_matrix ?? undefined,
        metrics: p?.qualification_metrics ?? undefined,
      };
    });
  }, [employees, profilesQuery.data]);
  const profilesLoading = profilesQuery.isLoading;

  // Fase a usar para agrupar/ordenar uma ordem: no modo "plano" é a fase
  // optimizada do CPO, no modo "estado" é a fase actual.
  const phaseOf = (o: ActiveOrderCard): string => {
    if (view === 'plano') {
      const opt = (o as OptimizedOrderCard).optimized_phase;
      if (opt) return opt;
    }
    return o.phase ?? 'Sem fase';
  };
  const seqOf = (o: ActiveOrderCard): number => {
    if (view === 'plano') {
      const s = (o as OptimizedOrderCard).optimized_phase_sequence;
      if (typeof s === 'number') return s;
    }
    return typeof o.phase_sequence === 'number'
      ? o.phase_sequence
      : Number.MAX_SAFE_INTEGER;
  };

  // ─── Colunas Kanban ordenadas pela sequência de routing NELO (Q.54.C) ───
  const columns: PhaseColumnModel[] = useMemo(() => {
    const bottlenecks = snapshotQuery.data?.phases.bottlenecks ?? [];
    // Indexa scores de gargalo por nome de fase.
    const scoreByPhase = new Map<string, { score: number; load: number | null; cap: number | null }>();
    for (const b of bottlenecks) {
      const key = (b.name ?? b.phase ?? '').toString();
      if (!key) continue;
      let score = typeof b.score === 'number' ? b.score : 0;
      const load = typeof b.load === 'number' ? b.load : null;
      const cap = typeof b.capacity === 'number' ? b.capacity : null;
      if (score === 0 && load !== null && cap !== null && cap > 0) {
        score = Math.min(100, Math.round((load / cap) * 100));
      }
      scoreByPhase.set(key.toLowerCase(), { score, load, cap });
    }
    // Fases presentes nas ordens, com a sua sequência de routing.
    const seqByPhase = new Map<string, number>();
    for (const o of orders) {
      const name = phaseOf(o);
      const seq = seqOf(o);
      const prev = seqByPhase.get(name);
      // Guarda a menor sequência vista para a fase (estável).
      if (prev === undefined || seq < prev) seqByPhase.set(name, seq);
    }
    // Ordena por sequência de routing crescente; empate → nome.
    const phaseNames = [...seqByPhase.keys()].sort((a, b) => {
      const sa = seqByPhase.get(a) ?? Number.MAX_SAFE_INTEGER;
      const sb = seqByPhase.get(b) ?? Number.MAX_SAFE_INTEGER;
      if (sa !== sb) return sa - sb;
      return a.localeCompare(b, 'pt-PT');
    });
    return phaseNames.map((name) => {
      const bn = scoreByPhase.get(name.toLowerCase());
      return {
        id: name,
        short: name,
        score: bn?.score ?? 0,
        load: bn?.load ?? null,
        cap: bn?.cap ?? null,
      };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orders, snapshotQuery.data, view]);

  // ─── Helpers de derivação ───────────────────────────────────────────────
  const activeBoat = orders.find((o) => o.id === activeBoatId) ?? null;
  const sheetBoat = orders.find((o) => o.id === sheetBoatId) ?? null;

  const assignedWorkersByBoat: Record<string, AssignedWorker[]> = useMemo(() => {
    const nameById = new Map(employees.map((e) => [e.id, e.name]));
    const out: Record<string, AssignedWorker[]> = {};
    for (const [boatId, ids] of Object.entries(assignments)) {
      out[boatId] = ids.map((id) => {
        const name = nameById.get(id) ?? id.slice(0, 8);
        return { id, name, initials: deriveInitials(name) };
      });
    }
    return out;
  }, [assignments, employees]);

  // ─── Preview-delta (consequência do drag de barco) ──────────────────────
  const previewQuery = useQuery({
    queryKey: [
      'fabrica',
      'preview',
      pendingMove?.boat.id,
      pendingMove?.targetPhase,
    ],
    queryFn: () =>
      schedulePreviewApi.previewDelta({
        operation_id: pendingMove!.boat.id,
        new_phase_id: pendingMove!.targetPhase,
      }),
    enabled: !!pendingMove,
    retry: false,
  });

  // ─── Apply-move ─────────────────────────────────────────────────────────
  const applyMutation = useMutation({
    mutationFn: (reason: string) =>
      schedulePreviewApi.applyMove({
        operation_id: pendingMove!.boat.id,
        new_phase_id: pendingMove!.targetPhase,
        reason,
      }),
    onSuccess: () => {
      const mv = pendingMove!;
      setToast({
        title: `#${mv.boat.hull ?? mv.boat.id.slice(0, 6)} movido para ${
          mv.targetPhase
        }`,
        detail: `Era ${mv.boat.phase ?? 'sem fase'} · movimento registado`,
        impact: previewQuery.data?.throughput_eur_delta ?? 0,
      });
      setPendingMove(null);
      queryClient.invalidateQueries({ queryKey: ['fabrica', 'orders'] });
      queryClient.invalidateQueries({ queryKey: ['fabrica', 'snapshot'] });
    },
  });

  // ─── Allocate-daily (atribuir operador) ─────────────────────────────────
  const allocateMutation = useMutation({
    mutationFn: (vars: { boatId: string; workerId: string }) =>
      allocationsApi.createDaily({
        employee_id: vars.workerId,
        order_id: vars.boatId,
      }),
    onSuccess: (_data, vars) => {
      // Eco optimista: o operador passa a contar para este barco.
      setAssignments((prev) => {
        const next: Record<string, string[]> = {};
        for (const [bid, ids] of Object.entries(prev)) {
          next[bid] = ids.filter((id) => id !== vars.workerId);
        }
        next[vars.boatId] = [
          ...(next[vars.boatId] ?? []),
          vars.workerId,
        ];
        return next;
      });
      const name =
        employees.find((e) => e.id === vars.workerId)?.name ?? 'Operador';
      const boat = orders.find((o) => o.id === vars.boatId);
      setToast({
        title: `${name} → #${boat?.hull ?? vars.boatId.slice(0, 6)}`,
        detail: 'Atribuição diária registada',
        impact: 0,
      });
      queryClient.invalidateQueries({ queryKey: ['fabrica', 'orders'] });
    },
    onError: () => {
      setToast({
        title: 'Atribuição falhou',
        detail: 'O backend recusou a atribuição diária. Tenta de novo.',
        impact: 0,
      });
    },
  });

  // ─── Handlers ───────────────────────────────────────────────────────────
  // No modo "plano" a fábrica é só leitura — o plano sugerido não se
  // edita por drag (corre-se uma nova optimização para o mudar).
  function handleBoatDrop(boatId: string, phaseId: string): void {
    if (view === 'plano') return;
    const boat = orders.find((o) => o.id === boatId);
    if (!boat) return;
    if (boat.phase === phaseId) return; // mesma coluna — nada a fazer
    setPendingMove({ boat, targetPhase: phaseId });
  }

  function handleWorkerDrop(boatId: string, workerId: string): void {
    if (view === 'plano') return;
    allocateMutation.mutate({ boatId, workerId });
  }

  function handleWorkerRemove(boatId: string, workerId: string): void {
    setAssignments((prev) => ({
      ...prev,
      [boatId]: (prev[boatId] ?? []).filter((id) => id !== workerId),
    }));
    const name =
      employees.find((e) => e.id === workerId)?.name ?? 'Operador';
    setToast({
      title: `${name} removido`,
      detail: 'Operador disponível de novo no rail',
      impact: 0,
    });
  }

  // ─── KPIs do strip ──────────────────────────────────────────────────────
  const statusCount = (s: string) =>
    orders.filter((o) => o.status === s).length;

  // ─── Render ─────────────────────────────────────────────────────────────
  const isLoading =
    view === 'plano'
      ? planQuery.isLoading
      : ordersQuery.isLoading || snapshotQuery.isLoading;
  const planKpis = planQuery.data?.kpis ?? null;
  const inOptimizedCount =
    view === 'plano'
      ? planOrders.filter((o) => o.in_optimized_plan).length
      : 0;

  return (
    <DarkPageLayout
      title="Fábrica"
      subtitle={
        view === 'plano'
          ? 'Plano sugerido pelo CPO — fases e operadores optimizados (só leitura)'
          : 'Arrasta barcos entre fases · clica num barco para ver operadores recomendados · arrasta para atribuir'
      }
      icon={<Factory size={18} />}
      actions={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Toggle Estado actual ↔ Plano sugerido (Q.54.D) */}
          <div
            style={{
              display: 'flex',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-md)',
              overflow: 'hidden',
            }}
          >
            <button
              type="button"
              onClick={() => setView('estado')}
              style={{
                padding: '5px 10px',
                fontSize: 11,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background:
                  view === 'estado' ? 'var(--accent)' : 'var(--bg-2)',
                color: view === 'estado' ? '#fff' : 'var(--fg-2)',
              }}
            >
              Estado actual
            </button>
            <button
              type="button"
              onClick={() => setView('plano')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '5px 10px',
                fontSize: 11,
                fontWeight: 600,
                border: 'none',
                borderLeft: '1px solid var(--bd-1)',
                cursor: 'pointer',
                background:
                  view === 'plano' ? 'var(--accent)' : 'var(--bg-2)',
                color: view === 'plano' ? '#fff' : 'var(--fg-2)',
              }}
            >
              <Sparkles size={11} />
              Plano sugerido
            </button>
          </div>
          {activeBoatId && (
            <DarkButton
              variant="ghost"
              size="sm"
              onClick={() => setActiveBoatId(null)}
            >
              <X size={12} />
              Limpar selecção
            </DarkButton>
          )}
          <LiveBadge />
        </div>
      }
    >
      {ordersQuery.isError ? (
        <EmptyState
          mascot={false}
          title="Não foi possível carregar a fábrica"
          hint="As ordens activas não responderam. Verifica se o backend está ligado."
          action={
            <DarkButton size="sm" onClick={() => ordersQuery.refetch()}>
              Tentar novamente
            </DarkButton>
          }
        />
      ) : (
        <>
          {/* Strip de KPIs — no modo plano mostra os KPIs do commit CPO */}
          {view === 'plano' ? (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 10,
                marginBottom: 14,
              }}
            >
              <KpiTile
                label="No plano optimizado"
                value={inOptimizedCount}
                tone="green"
              />
              <KpiTile
                label="Makespan (h)"
                value={Math.round(planKpis?.makespan_hours ?? 0)}
              />
              <KpiTile label="Setups" value={planKpis?.setups ?? 0} />
              <KpiTile
                label="Ordens atrasadas"
                value={planKpis?.num_late_orders ?? 0}
                tone="red"
              />
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 10,
                marginBottom: 14,
              }}
            >
              <KpiTile label="Em produção" value={orders.length} />
              <KpiTile
                label="No prazo"
                value={statusCount('IN_PROGRESS')}
                tone="green"
              />
              <KpiTile
                label="Em risco"
                value={statusCount('AT_RISK')}
                tone="yellow"
              />
              <KpiTile
                label="Atrasados"
                value={statusCount('LATE')}
                tone="red"
              />
            </div>
          )}

          {view === 'plano' && planKpis?.avg_utilization != null && (
            <div
              style={{
                fontSize: 11,
                color: 'var(--fg-3)',
                marginBottom: 12,
              }}
            >
              Utilização média{' '}
              <span style={{ color: 'var(--fg-1)', fontWeight: 600 }}>
                {planKpis.avg_utilization.toFixed(1)}%
              </span>
              {planKpis.safety_net_triggered && (
                <span style={{ color: 'var(--yellow)' }}>
                  {'  ·  '}safety-net activo
                </span>
              )}
              {planQuery.data?.short_sha && (
                <span> · commit {planQuery.data.short_sha}</span>
              )}
            </div>
          )}

          {/* Colunas Kanban */}
          <div style={{ marginBottom: 12 }}>
            {isLoading ? (
              <div
                style={{
                  background: 'var(--bg-1)',
                  border: '1px solid var(--bd-1)',
                  borderRadius: 'var(--r-lg)',
                  padding: 40,
                  textAlign: 'center',
                  fontSize: 12,
                  color: 'var(--fg-3)',
                }}
              >
                A carregar as colunas da fábrica…
              </div>
            ) : view === 'plano' && planQuery.isError ? (
              <EmptyState
                mascot={false}
                icon={<Sparkles size={28} />}
                title="Sem plano optimizado"
                hint="O CPO ainda não gerou um commit. Corre uma optimização para ver o plano sugerido."
                action={
                  <DarkButton
                    size="sm"
                    onClick={() => setView('estado')}
                  >
                    Voltar ao estado actual
                  </DarkButton>
                }
              />
            ) : orders.length === 0 ? (
              <EmptyState
                mascot={false}
                icon={<Layers size={28} />}
                title="Sem barcos em produção"
                hint={
                  view === 'plano'
                    ? 'O commit optimizado não tem ordens. Corre uma nova optimização.'
                    : 'Nenhuma ordem activa hoje. Confirma se a ingestão de ordens correu.'
                }
              />
            ) : (
              <div
                style={{
                  display: 'grid',
                  gridAutoFlow: 'column',
                  gridAutoColumns: 'minmax(200px, 1fr)',
                  gap: 10,
                  paddingBottom: 12,
                  overflowX: 'auto',
                }}
              >
                {columns.map((col) => (
                  <FabricaPhaseColumn
                    key={col.id}
                    phase={col}
                    boats={orders.filter((o) => phaseOf(o) === col.id)}
                    assignments={assignedWorkersByBoat}
                    activeBoatId={activeBoatId}
                    draggedBoatId={draggedBoatId}
                    onBoatClick={(id) => {
                      setActiveBoatId(id);
                      setSheetBoatId(id);
                    }}
                    onBoatDrop={handleBoatDrop}
                    onWorkerDrop={handleWorkerDrop}
                    onWorkerRemove={handleWorkerRemove}
                    onBoatDragStart={setDraggedBoatId}
                    onBoatDragEnd={() => setDraggedBoatId(null)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Rail de operadores com fit-scoring */}
          {employeesQuery.isError ? (
            <EmptyState
              mascot={false}
              title="Operadores indisponíveis"
              hint="A lista de empregados não respondeu — não é possível mostrar o rail de atribuição."
              action={
                <DarkButton
                  size="sm"
                  onClick={() => employeesQuery.refetch()}
                >
                  Tentar novamente
                </DarkButton>
              }
            />
          ) : (
            <WorkersStrip
              workers={workerProfiles}
              activeBoat={activeBoat}
              assignedToActive={
                activeBoatId ? assignments[activeBoatId] ?? [] : []
              }
              loadingProfiles={profilesLoading || employeesQuery.isLoading}
            />
          )}
        </>
      )}

      {/* Painel de detalhe do barco */}
      <BoatDetailSheet
        boat={sheetBoat}
        workers={
          sheetBoat ? assignedWorkersByBoat[sheetBoat.id] ?? [] : []
        }
        onClose={() => setSheetBoatId(null)}
      />

      {/* Confirmação de movimento de fase */}
      {pendingMove && (
        <MoveBoatConfirm
          boat={pendingMove.boat}
          targetPhase={pendingMove.targetPhase}
          preview={(previewQuery.data as PreviewDeltaResult) ?? null}
          previewLoading={previewQuery.isLoading}
          previewError={
            previewQuery.isError
              ? previewQuery.error instanceof Error
                ? previewQuery.error.message
                : 'erro desconhecido'
              : null
          }
          applying={applyMutation.isPending}
          applyError={
            applyMutation.isError
              ? applyMutation.error instanceof Error
                ? applyMutation.error.message
                : 'Não foi possível aplicar o movimento.'
              : null
          }
          onConfirm={(reason) => applyMutation.mutate(reason)}
          onCancel={() => setPendingMove(null)}
        />
      )}

      {/* Toast de impacto */}
      <ImpactToast toast={toast} onClose={() => setToast(null)} />
    </DarkPageLayout>
  );
}

function KpiTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: 'green' | 'yellow' | 'red';
}): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        padding: 12,
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
        }}
      >
        {label}
      </div>
      <div
        className="display tabular"
        style={{
          fontSize: 22,
          fontWeight: 500,
          color: tone ? `var(--${tone})` : 'var(--fg-0)',
          marginTop: 4,
        }}
      >
        {value}
      </div>
    </div>
  );
}

export default FabricaPage;
