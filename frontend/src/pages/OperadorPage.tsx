/**
 * OperadorPage (Sprint H.2)
 * ===========================
 *
 * `/operador` — tablet-first work surface for a line operator. Two
 * bands on one vertical screen:
 *
 *  1. **A minha fila** — assigned operations for today, ordered by
 *     start time. First row is always "A próxima".
 *  2. **Reportar problema** — a four-field form that POSTs to
 *     ``/v1/quality/rework``. No modal — the form lives on the page
 *     so a gloved hand can tap + type without juggling overlays.
 *
 * UX constraints (Blueprint v2.0 §7.3):
 * * All interactive controls ≥ 56px tall.
 * * At most one primary action per band (the big "Gravar" button).
 * * Strong visual hierarchy so "próxima op" reads at arm's length.
 *
 * Offline story (MVP): the *read* path is cached by TanStack Query;
 * stale data is served when the network drops. The *write* path
 * (issue reporting) queues to ``localStorage`` and flushes when the
 * mutation succeeds on the next visit. Dexie is the upgrade path
 * once `npm install dexie` lands — see the ``OFFLINE_QUEUE_KEY``
 * helper below for the migration point.
 *
 * The worker id is read from ``localStorage.getItem('employee_id')``
 * or the `?worker=<uuid>` query param; no auth. Sprint K hooks in
 * the real JWT and replaces this with ``useCurrentUser()``.
 */

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  useSearchParams,
} from 'react-router-dom';
import {
  Hammer,
  ClipboardList,
  AlertCircle,
  CheckCircle2,
  PlayCircle,
  WifiOff,
  Clock,
  Cpu,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { pt } from 'date-fns/locale';
import { DarkPageLayout } from '../layouts';
import { DarkCard, DarkBadge, DarkButton } from '../components/dark';
import { LiveBadge } from '../components/dashboard/LiveBadge';
import { useRealtime } from '../providers/RealtimeProvider';
import {
  qualityReworkApi,
  workerOperationsApi,
  type ReworkCreatePayload,
  type WorkerOperation,
} from '../lib/api';

// ─── Offline write queue (localStorage MVP) ──────────────────────────────

const OFFLINE_QUEUE_KEY = 'operador.offline_rework_queue';
const WORKER_ID_KEY = 'employee_id';

interface QueuedReport extends ReworkCreatePayload {
  queued_at: string;
  attempts: number;
}

function loadQueue(): QueuedReport[] {
  try {
    const raw = localStorage.getItem(OFFLINE_QUEUE_KEY);
    return raw ? (JSON.parse(raw) as QueuedReport[]) : [];
  } catch {
    return [];
  }
}

function saveQueue(q: QueuedReport[]): void {
  try {
    localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(q));
  } catch {
    // storage full / private mode — drop silently, user keeps the form
  }
}

// ─── Operation card ──────────────────────────────────────────────────────

interface OperationCardProps {
  op: WorkerOperation;
  highlight?: boolean;
}

function OperationCard({ op, highlight = false }: OperationCardProps) {
  const scheduledStart = new Date(op.scheduled_start);
  const scheduledEnd = new Date(op.scheduled_end);
  const when = Number.isFinite(scheduledStart.getTime())
    ? scheduledStart.toLocaleTimeString('pt-PT', {
        hour: '2-digit',
        minute: '2-digit',
      })
    : '—';

  const statusVariant: 'success' | 'info' | 'neutral' | 'warning' =
    op.status === 'IN_PROGRESS'
      ? 'info'
      : op.status === 'COMPLETED'
      ? 'success'
      : op.status === 'CANCELLED'
      ? 'warning'
      : 'neutral';

  return (
    <div
      className={`rounded-xl border p-5 ${
        highlight
          ? 'bg-accent/10 border-accent/40 shadow-lg'
          : 'bg-bg-elevated border-border-subtle'
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Hammer
            size={22}
            className={highlight ? 'text-accent' : 'text-text-tertiary'}
          />
          <span className="text-2xl font-semibold text-text-white tabular-nums">
            {when}
          </span>
          <span className="text-text-tertiary text-sm">
            ({op.scheduled_duration_hours
              ? `${op.scheduled_duration_hours.toFixed(1)}h`
              : '—'})
          </span>
        </div>
        <DarkBadge variant={statusVariant}>{op.status}</DarkBadge>
      </div>
      <div className="text-xl font-medium text-text-white">
        {op.order_id}{' '}
        <span className="text-text-tertiary text-base">
          · op {op.operation_sequence}
        </span>
      </div>
      <div className="flex items-center gap-4 mt-2 text-sm text-text-secondary">
        <span className="flex items-center gap-1">
          <Clock size={14} />
          até{' '}
          {Number.isFinite(scheduledEnd.getTime())
            ? scheduledEnd.toLocaleTimeString('pt-PT', {
                hour: '2-digit',
                minute: '2-digit',
              })
            : '—'}
        </span>
        <span className="flex items-center gap-1">
          <Cpu size={14} />
          {op.machine_id ? op.machine_id.slice(0, 8) : 'sem máquina'}
        </span>
        <span>
          qt <b className="text-text-white">{op.quantity}</b>
        </span>
      </div>
    </div>
  );
}

// ─── Issue form ──────────────────────────────────────────────────────────

interface IssueFormProps {
  defaultOrderId?: string;
  workerId: string | null;
  onSuccess: () => void;
}

const ERROR_CODES: Array<{ code: string; label: string }> = [
  { code: 'RESIN_BUBBLE', label: 'Bolha na resina' },
  { code: 'PAINT_SCRATCH', label: 'Risco na pintura' },
  { code: 'COLAGEM_FAIL', label: 'Falha na colagem' },
  { code: 'DIMENSION_OFF', label: 'Dimensão fora de tolerância' },
  { code: 'OTHER', label: 'Outro' },
];

function IssueForm({ defaultOrderId, workerId, onSuccess }: IssueFormProps) {
  const queryClient = useQueryClient();
  const [orderId, setOrderId] = useState(defaultOrderId ?? '');
  const [errorCode, setErrorCode] = useState('');
  const [description, setDescription] = useState('');
  const [savedBanner, setSavedBanner] = useState(false);
  const [offlineBanner, setOfflineBanner] = useState(false);

  useEffect(() => {
    if (defaultOrderId && !orderId) setOrderId(defaultOrderId);
  }, [defaultOrderId, orderId]);

  const mutation = useMutation({
    mutationFn: (payload: ReworkCreatePayload) =>
      qualityReworkApi.create(payload),
    onSuccess: () => {
      setSavedBanner(true);
      setTimeout(() => setSavedBanner(false), 3_000);
      setOrderId(defaultOrderId ?? '');
      setErrorCode('');
      setDescription('');
      queryClient.invalidateQueries({
        queryKey: ['worker-operations-today'],
      });
      onSuccess();
    },
  });

  // On mount, flush anything queued from a previous offline session.
  useEffect(() => {
    const queue = loadQueue();
    if (queue.length === 0) return;
    (async () => {
      const remaining: QueuedReport[] = [];
      for (const item of queue) {
        try {
          await qualityReworkApi.create(item);
        } catch {
          remaining.push({ ...item, attempts: item.attempts + 1 });
        }
      }
      saveQueue(remaining);
    })();
  }, []);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!orderId || !errorCode) return;
    const payload: ReworkCreatePayload = {
      of_id: orderId,
      error_code: errorCode,
      detected_at: new Date().toISOString(),
      error_description: description || undefined,
      causer_employee_id: workerId ?? undefined,
    };
    // Offline-safe: optimistic queue + try the network.
    try {
      mutation.mutate(payload);
    } catch {
      const queue = loadQueue();
      queue.push({ ...payload, queued_at: new Date().toISOString(), attempts: 0 });
      saveQueue(queue);
      setOfflineBanner(true);
      setTimeout(() => setOfflineBanner(false), 4_000);
    }
    // Also queue when the mutation itself errors (real network drop).
    if (mutation.isError) {
      const queue = loadQueue();
      queue.push({ ...payload, queued_at: new Date().toISOString(), attempts: 0 });
      saveQueue(queue);
      setOfflineBanner(true);
    }
  }

  const disabled = !orderId || !errorCode || mutation.isPending;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <label className="block">
          <span className="text-sm text-text-secondary">Ordem</span>
          <input
            type="text"
            value={orderId}
            onChange={(e) => setOrderId(e.target.value.toUpperCase())}
            placeholder="OF-12345"
            className="mt-1 w-full h-14 rounded-xl bg-bg-elevated border border-border-subtle px-4 text-lg text-text-white focus:outline-none focus:border-accent"
            required
          />
        </label>
        <label className="block">
          <span className="text-sm text-text-secondary">Tipo de defeito</span>
          <select
            value={errorCode}
            onChange={(e) => setErrorCode(e.target.value)}
            className="mt-1 w-full h-14 rounded-xl bg-bg-elevated border border-border-subtle px-4 text-lg text-text-white focus:outline-none focus:border-accent"
            required
          >
            <option value="">Escolher…</option>
            {ERROR_CODES.map((e) => (
              <option key={e.code} value={e.code}>
                {e.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="block">
        <span className="text-sm text-text-secondary">
          Descrição (opcional)
        </span>
        <textarea
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Ex: bolha de 3 mm no pavilhão lateral direito"
          className="mt-1 w-full rounded-xl bg-bg-elevated border border-border-subtle px-4 py-3 text-base text-text-white focus:outline-none focus:border-accent"
        />
      </label>

      {savedBanner && (
        <div className="flex items-center gap-2 text-sm text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-4 py-3">
          <CheckCircle2 size={16} /> Problema registado.
        </div>
      )}
      {offlineBanner && (
        <div className="flex items-center gap-2 text-sm text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-xl px-4 py-3">
          <WifiOff size={16} /> Guardado localmente — envio quando voltar
          a rede.
        </div>
      )}

      <DarkButton
        type="submit"
        variant="primary"
        size="lg"
        disabled={disabled}
        fullWidth
      >
        <AlertCircle size={18} className="mr-2" />
        {mutation.isPending ? 'A enviar…' : 'Registar problema'}
      </DarkButton>
    </form>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────

export function OperadorPage() {
  const [searchParams] = useSearchParams();
  const realtime = useRealtime();
  const queryClient = useQueryClient();

  const workerId = useMemo(
    () =>
      searchParams.get('worker')
      ?? (typeof window !== 'undefined'
        ? window.localStorage.getItem(WORKER_ID_KEY)
        : null),
    [searchParams],
  );

  const [manualWorkerId, setManualWorkerId] = useState('');

  const activeWorkerId = workerId ?? (manualWorkerId.trim() || null);
  const todayIso = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const { data: operations, isLoading, isError } = useQuery({
    queryKey: ['worker-operations-today', activeWorkerId, todayIso],
    queryFn: () =>
      activeWorkerId
        ? workerOperationsApi.today(activeWorkerId, { as_of: todayIso })
        : Promise.resolve([]),
    enabled: !!activeWorkerId,
    staleTime: 30_000,
  });

  // SSE: invalidate when the scheduler publishes a new or updated
  // schedule — the operator sees the new assignment without reloading.
  useEffect(() => {
    if (!realtime || !activeWorkerId) return;
    const total = realtime.events.length;
    const fresh = realtime.events.slice(Math.max(0, total - 1));
    for (const ev of fresh) {
      if (
        ev.event_type === 'SCHEDULE_CREATED' ||
        ev.event_type === 'SCHEDULE_UPDATED'
      ) {
        queryClient.invalidateQueries({
          queryKey: ['worker-operations-today', activeWorkerId],
        });
      }
    }
  }, [realtime?.events.length, realtime, activeWorkerId, queryClient]);

  function saveManualWorkerId() {
    const next = manualWorkerId.trim();
    if (!next) return;
    localStorage.setItem(WORKER_ID_KEY, next);
    window.location.reload();
  }

  if (!activeWorkerId) {
    return (
      <DarkPageLayout
        title="Operador"
        subtitle="Identifica-te para carregar a tua fila"
        icon={<Hammer size={20} />}
      >
        <DarkCard>
          <p className="text-sm text-text-secondary mb-4">
            Ainda não tens um ID guardado. Introduz o teu UUID de
            empregado — ficará no browser e não será pedido novamente.
          </p>
          <input
            type="text"
            value={manualWorkerId}
            onChange={(e) => setManualWorkerId(e.target.value)}
            placeholder="8d1f0c6a-..."
            className="w-full h-14 rounded-xl bg-bg-elevated border border-border-subtle px-4 text-lg text-text-white focus:outline-none focus:border-accent mb-4"
          />
          <DarkButton
            variant="primary"
            size="lg"
            fullWidth
            onClick={saveManualWorkerId}
            disabled={!manualWorkerId.trim()}
          >
            Guardar
          </DarkButton>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  const next = operations && operations.length > 0 ? operations[0] : null;
  const rest = operations && operations.length > 1 ? operations.slice(1) : [];

  const handleNewReport = () => {
    queryClient.invalidateQueries({
      queryKey: ['worker-operations-today', activeWorkerId],
    });
  };

  return (
    <DarkPageLayout
      title="Operador"
      subtitle="A minha fila de trabalho · tablet"
      icon={<Hammer size={20} />}
      actions={<LiveBadge />}
    >
      {/* Next-up hero */}
      <DarkCard className="mb-6 p-0">
        <div className="px-5 py-4 border-b border-border-subtle bg-bg-secondary/40 flex items-center gap-2">
          <PlayCircle className="text-accent" size={22} />
          <h2 className="text-lg font-semibold text-text-white">
            A próxima operação
          </h2>
        </div>
        <div className="p-5">
          {isLoading ? (
            <p className="text-sm text-text-tertiary text-center py-6">
              A carregar…
            </p>
          ) : isError ? (
            <p className="text-sm text-amber-300 text-center py-6">
              Rede indisponível. A mostrar últimos dados vistos.
            </p>
          ) : !next ? (
            <p className="text-sm text-text-tertiary text-center py-6">
              Sem operações atribuídas para hoje.
            </p>
          ) : (
            <OperationCard op={next} highlight />
          )}
        </div>
      </DarkCard>

      {/* Remaining queue */}
      {rest.length > 0 && (
        <DarkCard className="mb-6 p-0">
          <div className="px-5 py-4 border-b border-border-subtle bg-bg-secondary/40 flex items-center gap-2">
            <ClipboardList className="text-text-tertiary" size={20} />
            <h2 className="text-base font-semibold text-text-white">
              Resto da fila ({rest.length})
            </h2>
          </div>
          <div className="p-5 space-y-3">
            {rest.map((op) => (
              <OperationCard key={op.id} op={op} />
            ))}
          </div>
        </DarkCard>
      )}

      {/* Issue report */}
      <DarkCard className="p-0">
        <div className="px-5 py-4 border-b border-border-subtle bg-bg-secondary/40 flex items-center gap-2">
          <AlertCircle className="text-red-400" size={20} />
          <h2 className="text-base font-semibold text-text-white">
            Reportar problema
          </h2>
        </div>
        <div className="p-5">
          <IssueForm
            defaultOrderId={next?.order_id}
            workerId={activeWorkerId}
            onSuccess={handleNewReport}
          />
        </div>
      </DarkCard>
    </DarkPageLayout>
  );
}

export default OperadorPage;
