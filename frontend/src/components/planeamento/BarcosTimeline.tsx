/**
 * BarcosTimeline — timeline arrastável de barcos por fase (Q.52.G).
 *
 * Port do `BarcosTab` de design/nelo/page-planeamento.jsx, mas com dados
 * REAIS: as operações vêm do último commit do CPO
 * (`cpoCommitsApi.get(sha, {include_operations:true})`). Cada operação é
 * uma barra posicionada num grelha de 15 min (07:00–18:00, 44 slots).
 *
 * Arrastar uma barra para outra raia (fase) dispara
 * `schedulePreviewApi.previewDelta` — preview da consequência, sub-segundo,
 * sem correr o CPO. O resultado abre o ConsequenceBox; aceitar persiste
 * via `applyMove`. ZERO MOCKS — sem operações reais, empty state honesto.
 */

import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { GripVertical, Sparkles, Calendar } from 'lucide-react';
import {
  cpoCommitsApi,
  schedulePreviewApi,
  type CpoCommit,
  type PreviewDeltaResult,
} from '../../lib/api';
import { EmptyState } from '../dark/EmptyState';
import { ConsequenceBox } from '../dark/ConsequenceBox';
import { SkeletonLoader } from '../ui/Skeleton';
import { useDraggable, useDropZone } from '../dark/useDragDrop';
import { BoatDetailSheet } from '../../pages/producao/BoatDetailSheet';
import { fabricaApi, type ActiveOrderCard } from '../../pages/producao/fabricaApi';
import { CalendarStrip } from './CalendarStrip';
import { StartByCard } from './StartByCard';
import type { CpoOperation } from './planeamentoApi';

// ── Grelha temporal — 07:00 → 18:00, 15 min por slot ──────────────────────
const DAY_START_HOUR = 7;
const DAY_END_HOUR = 18;
const SLOT_MIN = 15;
const TOTAL_SLOTS = ((DAY_END_HOUR - DAY_START_HOUR) * 60) / SLOT_MIN; // 44

interface OpBar {
  op: CpoOperation;
  startSlot: number;
  spanSlots: number;
}

/** Converte ISO → índice de slot dentro do dia (clamp ao intervalo visível). */
function toSlot(iso: string): number {
  const d = new Date(iso);
  const minutes = (d.getHours() - DAY_START_HOUR) * 60 + d.getMinutes();
  return Math.round(minutes / SLOT_MIN);
}

interface DragData {
  operationId: string;
  fromPhase: string;
}

export function BarcosTimeline(): ReactNode {
  const queryClient = useQueryClient();
  const [preview, setPreview] = useState<{
    result: PreviewDeltaResult;
    operationId: string;
    newPhaseId: string;
  } | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  // Barco seleccionado ao clicar numa barra da timeline.
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  // Último commit do CPO + as suas operações.
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

  // Ordens em curso — para abrir o detalhe do barco ao clicar numa barra.
  const ordersQuery = useQuery({
    queryKey: ['planeamento', 'active-orders'],
    queryFn: () => fabricaApi.activeOrders({ limit: 500 }),
  });
  const ordersById = useMemo(() => {
    const map = new Map<string, ActiveOrderCard>();
    for (const o of ordersQuery.data ?? []) map.set(o.id, o);
    return map;
  }, [ordersQuery.data]);
  const selectedBoat = selectedOrderId
    ? (ordersById.get(selectedOrderId) ?? null)
    : null;

  const operations = useMemo<CpoOperation[]>(
    () =>
      ((commitQuery.data?.operations as CpoOperation[] | undefined) ?? []).filter(
        (o) => o.start_time && o.end_time,
      ),
    [commitQuery.data],
  );

  // Raias = fases distintas presentes nas operações.
  const phases = useMemo(() => {
    const set = new Set<string>();
    for (const o of operations) set.add(o.phase_id ?? 'sem fase');
    return Array.from(set).sort();
  }, [operations]);

  const previewMutation = useMutation({
    mutationFn: (vars: { operationId: string; newPhaseId: string }) =>
      schedulePreviewApi.previewDelta({
        operation_id: vars.operationId,
        new_phase_id: vars.newPhaseId,
      }),
    onSuccess: (result, vars) => {
      setPreviewError(null);
      setPreview({ result, operationId: vars.operationId, newPhaseId: vars.newPhaseId });
    },
    onError: (e: unknown) => {
      setPreviewError(
        e instanceof Error ? e.message : 'Não foi possível calcular o preview.',
      );
    },
  });

  const applyMutation = useMutation({
    mutationFn: (vars: { operationId: string; newPhaseId: string; reason: string }) =>
      schedulePreviewApi.applyMove({
        operation_id: vars.operationId,
        new_phase_id: vars.newPhaseId,
        reason: vars.reason || 'Movido na timeline de Planeamento',
      }),
    onSuccess: () => {
      setPreview(null);
      void queryClient.invalidateQueries({ queryKey: ['planeamento'] });
    },
    onError: (e: unknown) => {
      setPreviewError(
        e instanceof Error ? e.message : 'Não foi possível aplicar o movimento.',
      );
    },
  });

  if (commitsQuery.isLoading || (latestSha && commitQuery.isLoading)) {
    return <SkeletonLoader count={6} />;
  }

  if (commitsQuery.isError) {
    return (
      <EmptyState
        title="Não foi possível ler os planos do CPO"
        hint="O endpoint /v1/plan/cpo/commits falhou. Verifica se o backend está a correr."
        icon={<Calendar size={28} />}
        action={
          <button type="button" onClick={() => commitsQuery.refetch()} style={btnPrimary}>
            Tentar novamente
          </button>
        }
      />
    );
  }

  if (latestSha === undefined) {
    return (
      <EmptyState
        title="Ainda não há nenhum plano do CPO"
        hint="Corre o scheduler para gerar o primeiro plano. Usa o botão Replanear acima."
        icon={<Calendar size={28} />}
      />
    );
  }

  if (operations.length === 0) {
    return (
      <EmptyState
        title="Plano sem operações agendadas"
        hint="O último commit do CPO não tem operações. Replaneia ou confirma que há ordens abertas."
        icon={<Calendar size={28} />}
      />
    );
  }

  return (
    <div>
      <CalendarStrip />

      <TimelineGrid
        phases={phases}
        operations={operations}
        onMove={(operationId, newPhaseId, fromPhase) => {
          if (newPhaseId === fromPhase) return;
          previewMutation.mutate({ operationId, newPhaseId });
        }}
        onSelectOp={(op) => setSelectedOrderId(op.order_id)}
      />

      {selectedBoat && (
        <div style={{ marginTop: 14 }}>
          <StartByCard
            orderId={selectedBoat.id}
            hull={selectedBoat.hull}
            productName={selectedBoat.product_name}
          />
        </div>
      )}

      <BoatDetailSheet
        boat={selectedBoat}
        workers={[]}
        onClose={() => setSelectedOrderId(null)}
      />

      {previewError && (
        <div
          style={{
            marginTop: 12,
            fontSize: 11.5,
            color: 'var(--red)',
            background: 'var(--red-bg)',
            border: '1px solid var(--red-bd)',
            borderRadius: 'var(--r-sm)',
            padding: '8px 12px',
          }}
        >
          {previewError}
        </div>
      )}

      {preview && (
        <div style={{ marginTop: 14 }}>
          <div
            style={{
              fontSize: 11,
              textTransform: 'uppercase',
              letterSpacing: 0.5,
              color: 'var(--fg-3)',
              fontWeight: 600,
              marginBottom: 8,
            }}
          >
            Consequência de mover a operação
          </div>
          <ConsequenceBox
            ifAccept={[
              `Fitness: ${preview.result.fitness_before.toFixed(0)} → ${preview.result.fitness_after.toFixed(0)} (Δ ${preview.result.fitness_delta >= 0 ? '+' : ''}${preview.result.fitness_delta.toFixed(0)})`,
              `Throughput: ${preview.result.throughput_eur_delta >= 0 ? '+' : ''}€${Math.round(preview.result.throughput_eur_delta).toLocaleString('pt-PT')}/dia`,
              ...preview.result.warnings.map((w) => w.message),
            ]}
            ifReject={[
              'O plano mantém-se como está no último commit do CPO.',
              ...preview.result.conflicts.map((c) => `Conflito evitado: ${c.message}`),
            ]}
            source="CPO · preview-delta"
            impact={Math.max(0, Math.round(preview.result.throughput_eur_delta))}
            onAccept={(reason) =>
              applyMutation.mutate({
                operationId: preview.operationId,
                newPhaseId: preview.newPhaseId,
                reason,
              })
            }
            onReject={() => setPreview(null)}
          />
          {preview.result.pair_rule_violation && (
            <div
              style={{
                marginTop: 8,
                fontSize: 11.5,
                color: 'var(--orange)',
                background: 'var(--orange-bg)',
                border: '1px solid var(--orange-bd)',
                borderRadius: 'var(--r-sm)',
                padding: '6px 10px',
              }}
            >
              ⚠ Este movimento viola a regra de pares de Laminagem.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Grelha ────────────────────────────────────────────────────────────────

function TimelineGrid({
  phases,
  operations,
  onMove,
  onSelectOp,
}: {
  phases: string[];
  operations: CpoOperation[];
  onMove: (operationId: string, newPhaseId: string, fromPhase: string) => void;
  onSelectOp: (op: CpoOperation) => void;
}): ReactNode {
  return (
    <div
      style={{
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        background: 'var(--bg-1)',
        overflow: 'auto',
      }}
    >
      {/* Cabeçalho de horas */}
      <div style={{ display: 'flex', background: 'var(--bg-2)' }}>
        <div
          style={{
            width: 200,
            flexShrink: 0,
            padding: '10px 14px',
            borderRight: '1px solid var(--bd-1)',
            borderBottom: '1px solid var(--bd-1)',
            fontSize: 10.5,
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
            letterSpacing: 0.4,
            fontWeight: 600,
          }}
        >
          Fase
        </div>
        <div style={{ display: 'flex', flex: 1 }}>
          {Array.from({ length: DAY_END_HOUR - DAY_START_HOUR }).map((_, h) => (
            <div
              key={h}
              style={{
                flex: 1,
                minWidth: 70,
                padding: '10px 0',
                textAlign: 'center',
                fontSize: 11,
                color: 'var(--fg-2)',
                borderRight: '1px solid var(--bd-1)',
                borderBottom: '1px solid var(--bd-1)',
              }}
            >
              <span className="tabular">
                {String(DAY_START_HOUR + h).padStart(2, '0')}:00
              </span>
            </div>
          ))}
        </div>
      </div>

      {phases.map((phase) => (
        <PhaseLane
          key={phase}
          phase={phase}
          operations={operations.filter((o) => (o.phase_id ?? 'sem fase') === phase)}
          onMove={onMove}
          onSelectOp={onSelectOp}
        />
      ))}
    </div>
  );
}

function PhaseLane({
  phase,
  operations,
  onMove,
  onSelectOp,
}: {
  phase: string;
  operations: CpoOperation[];
  onMove: (operationId: string, newPhaseId: string, fromPhase: string) => void;
  onSelectOp: (op: CpoOperation) => void;
}): ReactNode {
  const { dropProps, isOver } = useDropZone<DragData>({
    accept: 'boat',
    onDrop: (payload) => {
      onMove(payload.data.operationId, phase, payload.data.fromPhase);
    },
  });

  const bars = useMemo<OpBar[]>(
    () =>
      operations.map((op) => {
        const startSlot = Math.max(0, Math.min(TOTAL_SLOTS - 1, toSlot(op.start_time)));
        const endSlot = Math.max(startSlot + 1, Math.min(TOTAL_SLOTS, toSlot(op.end_time)));
        return { op, startSlot, spanSlots: endSlot - startSlot };
      }),
    [operations],
  );

  return (
    <div style={{ display: 'flex', borderBottom: '1px solid var(--bd-1)' }}>
      <div
        style={{
          width: 200,
          flexShrink: 0,
          padding: '8px 14px',
          borderRight: '1px solid var(--bd-1)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
        }}
      >
        <span style={{ fontSize: 12, color: 'var(--fg-0)', fontWeight: 500 }}>
          {phase}
        </span>
        <span style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>
          {operations.length} {operations.length === 1 ? 'operação' : 'operações'}
        </span>
      </div>
      <div
        {...dropProps}
        style={{
          flex: 1,
          position: 'relative',
          minHeight: 48,
          background: isOver ? 'var(--accent-bg)' : 'transparent',
          backgroundImage: `repeating-linear-gradient(90deg, var(--bd-1) 0 1px, transparent 1px ${100 / (DAY_END_HOUR - DAY_START_HOUR)}%)`,
        }}
      >
        {bars.map((bar) => (
          <OpBarView
            key={bar.op.operation_id}
            bar={bar}
            fromPhase={phase}
            onSelectOp={onSelectOp}
          />
        ))}
      </div>
    </div>
  );
}

function OpBarView({
  bar,
  fromPhase,
  onSelectOp,
}: {
  bar: OpBar;
  fromPhase: string;
  onSelectOp: (op: CpoOperation) => void;
}): ReactNode {
  const { dragProps, dragging, wasDragging } = useDraggable<DragData>({
    kind: 'boat',
    data: { operationId: bar.op.operation_id, fromPhase },
  });

  const leftPct = (bar.startSlot / TOTAL_SLOTS) * 100;
  const widthPct = (bar.spanSlots / TOTAL_SLOTS) * 100;
  const workersLabel =
    bar.op.workers.length > 0 ? bar.op.workers.join(' + ') : 'sem operador';

  return (
    <div
      {...dragProps}
      role="button"
      tabIndex={0}
      // Clicar abre o detalhe do barco; arrastar move a operação. O `click`
      // sintético que se segue a um `dragend` é filtrado por `wasDragging()`
      // (Q.54.K) — não fica refém do estado `dragging`, que podia ficar
      // preso a `true` se a barra fosse remontada durante o arrasto.
      onClick={() => {
        if (!wasDragging()) onSelectOp(bar.op);
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelectOp(bar.op);
        }
      }}
      title={`${bar.op.order_id} · ${workersLabel} · clica para ver o barco`}
      style={{
        position: 'absolute',
        top: 8,
        height: 32,
        left: `${leftPct}%`,
        width: `calc(${widthPct}% - 4px)`,
        background: 'var(--accent-bg)',
        border: '1px solid var(--accent-bd)',
        borderLeft: '3px solid var(--accent)',
        borderRadius: 5,
        fontSize: 10.5,
        color: 'var(--fg-1)',
        padding: '0 8px',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        cursor: 'pointer',
        opacity: dragging ? 0.4 : 1,
        overflow: 'hidden',
      }}
    >
      <GripVertical size={11} color="var(--fg-3)" />
      <span
        style={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {bar.op.order_id}
        {bar.op.mold_id ? ` · ${bar.op.mold_id}` : ''}
      </span>
    </div>
  );
}

/** Sugestão CPO fantasma — alternativa do MAP-Elites do último commit. */
export function CpoGhostSuggestion({ commit }: { commit: CpoCommit | undefined }): ReactNode {
  const alts = (commit?.alternatives as Array<Record<string, unknown>> | undefined) ?? [];
  if (!commit || alts.length === 0) return null;
  const first = alts[0];
  const narrative =
    typeof first.trade_off_narrative === 'string'
      ? first.trade_off_narrative
      : typeof first.message === 'string'
        ? first.message
        : 'O CPO tem uma alternativa de plano com trade-off diferente.';

  return (
    <div
      style={{
        marginTop: 14,
        padding: '12px 14px',
        background: 'var(--accent-bg)',
        border: '1px dashed var(--accent-bd)',
        borderRadius: 'var(--r-md)',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
      }}
    >
      <Sparkles size={14} color="var(--accent)" />
      <div>
        <div style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}>
          Alternativa do CPO (MAP-Elites)
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-2)' }}>{narrative}</div>
      </div>
    </div>
  );
}

const btnPrimary: React.CSSProperties = {
  padding: '6px 14px',
  fontSize: 12,
  fontWeight: 500,
  borderRadius: 'var(--r-sm)',
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  cursor: 'pointer',
};
