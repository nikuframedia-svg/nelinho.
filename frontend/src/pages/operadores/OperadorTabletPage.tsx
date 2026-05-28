import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { AlertTriangle, Check, Hammer, Play } from 'lucide-react';
import { DarkButton, EmptyState, LiveBadge, NeloWorkerAvatar } from '../../components/dark';
import { Clickable } from '../../components/entitySheets';
import { authApi, employeesApi, qualityReworkApi, workerOperationsApi, type ReworkCreatePayload, type WorkerOperation } from '../../lib/api';
import { WORKER_ID_KEY, PROBLEM_KINDS, fmtClock, fmtTimeOfDay, ContextCard, bigButton, problemButton } from './operadorTabletBits';

export function OperadorTabletPage(): ReactNode {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();

  // ─── Identidade ─────────────────────────────────────────────────────────
  const meQuery = useQuery({
    queryKey: ['operador', 'me'],
    queryFn: () => authApi.me(),
    refetchOnWindowFocus: false,
    retry: false,
  });

  // worker id: ?worker= → auth/me → localStorage
  const workerId = useMemo(() => {
    const fromParam = searchParams.get('worker');
    if (fromParam) return fromParam;
    if (meQuery.data?.user_id) return meQuery.data.user_id;
    if (typeof window !== 'undefined') {
      return window.localStorage.getItem(WORKER_ID_KEY);
    }
    return null;
  }, [searchParams, meQuery.data]);

  // Nome do operador — auth/me, ou employees como fallback.
  const employeeQuery = useQuery({
    queryKey: ['operador', 'employee', workerId],
    queryFn: () => employeesApi.list({ limit: 300 }),
    enabled: !!workerId && !meQuery.data?.name,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const workerName = useMemo(() => {
    if (meQuery.data?.name) return meQuery.data.name;
    const raw =
      (employeeQuery.data as { data?: unknown[] } | undefined)?.data ??
      employeeQuery.data;
    if (Array.isArray(raw) && workerId) {
      const match = raw.find(
        (e) =>
          String((e as { id?: string }).id) === workerId ||
          String((e as { employee_id?: string }).employee_id) === workerId,
      ) as Record<string, unknown> | undefined;
      if (match) {
        const parts = [match.first_name, match.last_name].filter(Boolean);
        return (
          (parts.join(' ') as string) ||
          (match.full_name as string) ||
          (match.name as string) ||
          'Operador'
        );
      }
    }
    return 'Operador';
  }, [meQuery.data, employeeQuery.data, workerId]);

  // ─── Relógio de parede ──────────────────────────────────────────────────
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  // ─── Fila de operações de hoje ──────────────────────────────────────────
  const todayIso = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const opsQuery = useQuery({
    queryKey: ['operador', 'ops', workerId, todayIso],
    queryFn: () =>
      workerId
        ? workerOperationsApi.today(workerId, { as_of: todayIso })
        : Promise.resolve([] as WorkerOperation[]),
    enabled: !!workerId,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
  });

  // A operação "actual" = primeira não-concluída.
  const operations = opsQuery.data ?? [];
  const currentOp = useMemo(
    () =>
      operations.find(
        (o) => o.status === 'SCHEDULED' || o.status === 'IN_PROGRESS',
      ) ?? null,
    [operations],
  );

  // ─── Timer (deriva do actual_start real) ────────────────────────────────
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (currentOp?.status !== 'IN_PROGRESS' || !currentOp.actual_start) {
      setElapsed(0);
      return;
    }
    const startMs = new Date(currentOp.actual_start).getTime();
    const tick = () => {
      if (Number.isFinite(startMs)) {
        setElapsed(Math.max(0, Math.round((Date.now() - startMs) / 1000)));
      }
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [currentOp?.status, currentOp?.actual_start]);

  // ─── Mutações COMECEI / ACABEI ──────────────────────────────────────────
  const [actionError, setActionError] = useState<string | null>(null);
  const invalidateOps = () =>
    queryClient.invalidateQueries({
      queryKey: ['operador', 'ops', workerId],
    });

  const startMutation = useMutation({
    mutationFn: (id: string) => workerOperationsApi.start(id),
    onSuccess: () => {
      setActionError(null);
      invalidateOps();
    },
    onError: () =>
      setActionError('Não foi possível iniciar a fase. Tenta outra vez.'),
  });

  const completeMutation = useMutation({
    mutationFn: (id: string) => workerOperationsApi.complete(id, {}),
    onSuccess: () => {
      setActionError(null);
      invalidateOps();
    },
    onError: () =>
      setActionError('Não foi possível concluir a fase. Tenta outra vez.'),
  });

  // ─── Fluxo PROBLEMA ─────────────────────────────────────────────────────
  const [problemMode, setProblemMode] = useState(false);
  const reworkMutation = useMutation({
    mutationFn: (payload: ReworkCreatePayload) =>
      qualityReworkApi.create(payload),
    onSuccess: () => {
      setProblemMode(false);
      setActionError(null);
      invalidateOps();
    },
    onError: () =>
      setActionError(
        'Não foi possível registar o problema. Tenta outra vez.',
      ),
  });

  function reportProblem(errorCode: string): void {
    if (!currentOp) return;
    reworkMutation.mutate({
      of_id: currentOp.order_id,
      error_code: errorCode,
      detected_at: new Date().toISOString(),
      causer_employee_id: workerId ?? undefined,
    });
  }

  // ─── Render ─────────────────────────────────────────────────────────────

  if (!workerId) {
    return (
      <div
        style={{
          height: '100%',
          background: 'var(--bg-0)',
          display: 'grid',
          placeItems: 'center',
          padding: 48,
        }}
      >
        <EmptyState
          mascot={false}
          icon={<Hammer size={32} />}
          title="Identifica-te para carregar a tua fila"
          hint="Esta vista abre num tablet com ?worker=<id> ou depois de iniciar sessão. Sem identificação não há operações para mostrar."
        />
      </div>
    );
  }

  const busy =
    startMutation.isPending ||
    completeMutation.isPending ||
    reworkMutation.isPending;

  const machineState: 'ready' | 'running' | 'idle' = currentOp
    ? currentOp.status === 'IN_PROGRESS'
      ? 'running'
      : 'ready'
    : 'idle';

  return (
    <div
      style={{
        height: '100%',
        background: 'var(--bg-0)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* ─── Topo: avatar / turno / relógio ──────────────────────────── */}
      <div
        style={{
          padding: '20px 32px',
          borderBottom: '1px solid var(--bd-1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <NeloWorkerAvatar worker={{ name: workerName }} size={44} />
          <div>
            <div
              style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-0)' }}
            >
              {workerName}
            </div>
            <div style={{ fontSize: 13, color: 'var(--fg-2)' }}>
              {meQuery.data?.role
                ? `${meQuery.data.role} · operador`
                : 'Vista de operador · tablet'}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <LiveBadge label="Sincronizado" />
          <div className="tabular" style={{ fontSize: 14, color: 'var(--fg-2)' }}>
            {fmtTimeOfDay(now)}
          </div>
        </div>
      </div>

      {/* ─── Corpo ───────────────────────────────────────────────────── */}
      <div
        style={{
          flex: 1,
          padding: '32px 48px',
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
        }}
      >
        {opsQuery.isLoading ? (
          <div
            style={{
              flex: 1,
              display: 'grid',
              placeItems: 'center',
              color: 'var(--fg-3)',
              fontSize: 15,
            }}
          >
            A carregar a tua fila…
          </div>
        ) : opsQuery.isError ? (
          <EmptyState
            mascot={false}
            icon={<AlertTriangle size={32} />}
            title="Não foi possível carregar a fila"
            hint="A rede não respondeu. Tenta recarregar quando voltar a ligação."
            action={
              <DarkButton size="md" onClick={() => opsQuery.refetch()}>
                Recarregar
              </DarkButton>
            }
          />
        ) : !currentOp ? (
          <EmptyState
            mascot={false}
            icon={<Check size={32} />}
            title="Fila concluída"
            hint={
              operations.length > 0
                ? 'Terminaste todas as operações de hoje. Bom trabalho.'
                : 'Sem operações atribuídas para hoje.'
            }
          />
        ) : (
          <>
            {/* Número do barco gigante */}
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 14,
                marginBottom: 6,
                flexWrap: 'wrap',
              }}
            >
              <span
                className="display tabular"
                style={{
                  fontSize: 54,
                  fontWeight: 600,
                  color: 'var(--fg-0)',
                  letterSpacing: '-0.04em',
                }}
              >
                <Clickable kind="encomenda" id={currentOp.order_id}>
                  {currentOp.order_id}
                </Clickable>
              </span>
              <span
                style={{
                  fontSize: 13,
                  color: 'var(--fg-2)',
                  padding: '3px 10px',
                  background: 'var(--bg-2)',
                  border: '1px solid var(--bd-1)',
                  borderRadius: 999,
                }}
              >
                Operação {currentOp.operation_sequence}
              </span>
              {((currentOp as WorkerOperation & { effective_boost?: number }).effective_boost ?? 0) > 50 && (
                <span
                  style={{
                    fontSize: 13,
                    padding: '3px 10px',
                    background: 'var(--amber-bg, #78350f22)',
                    border: '1px solid #f59e0b66',
                    borderRadius: 999,
                    color: '#fbbf24',
                    fontWeight: 600,
                  }}
                  title={`Acelerada (boost ${(currentOp as WorkerOperation & { effective_boost?: number }).effective_boost})`}
                >
                  ⚡ Acelerada
                </span>
              )}
            </div>
            <div
              style={{
                fontSize: 18,
                color: 'var(--fg-1)',
                marginBottom: 24,
              }}
            >
              {operations.length} operação(ões) hoje ·{' '}
              {operations.filter((o) => o.status === 'COMPLETED').length}{' '}
              concluída(s)
            </div>

            {/* 4 cartões de contexto */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 14,
                marginBottom: 28,
              }}
            >
              <ContextCard
                label="Início previsto"
                value={
                  Number.isFinite(
                    new Date(currentOp.scheduled_start).getTime(),
                  )
                    ? fmtTimeOfDay(new Date(currentOp.scheduled_start))
                    : '—'
                }
              />
              <ContextCard
                label="Fim previsto"
                value={
                  Number.isFinite(
                    new Date(currentOp.scheduled_end).getTime(),
                  )
                    ? fmtTimeOfDay(new Date(currentOp.scheduled_end))
                    : '—'
                }
              />
              <ContextCard
                label="Máquina"
                value={
                  currentOp.machine_id
                    ? currentOp.machine_id.slice(0, 8)
                    : 'sem máquina'
                }
              />
              <ContextCard
                label="Estimado"
                value={
                  currentOp.scheduled_duration_hours
                    ? `${currentOp.scheduled_duration_hours.toFixed(1)}h`
                    : '—'
                }
                accent
              />
            </div>

            {/* Timer */}
            {machineState === 'running' && (
              <div
                style={{
                  padding: 24,
                  background: 'var(--bg-1)',
                  border: '1px solid var(--bd-2)',
                  borderRadius: 14,
                  marginBottom: 24,
                  textAlign: 'center',
                }}
              >
                <div
                  style={{
                    fontSize: 13,
                    color: 'var(--fg-2)',
                    marginBottom: 8,
                  }}
                >
                  Tempo decorrido
                </div>
                <div
                  className="display tabular"
                  style={{
                    fontSize: 72,
                    fontWeight: 600,
                    color: 'var(--accent)',
                    letterSpacing: '-0.04em',
                    lineHeight: 1,
                  }}
                >
                  {fmtClock(elapsed)}
                </div>
              </div>
            )}

            {/* Quantidade */}
            <div
              style={{
                padding: 18,
                background: 'var(--bg-1)',
                border: '1px solid var(--bd-1)',
                borderRadius: 14,
                marginBottom: 24,
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--fg-3)',
                  textTransform: 'uppercase',
                  letterSpacing: 0.4,
                  marginBottom: 8,
                }}
              >
                Instrução
              </div>
              <div
                style={{
                  fontSize: 16,
                  color: 'var(--fg-0)',
                  lineHeight: 1.5,
                }}
              >
                Quantidade a produzir:{' '}
                <strong>{currentOp.quantity}</strong>. Confirma o molde e o
                parceiro antes de começar. Se algo estiver errado, usa o
                botão PROBLEMA — o registo vai directo para a qualidade.
              </div>
            </div>

            {actionError && (
              <div
                style={{
                  marginBottom: 16,
                  padding: '10px 14px',
                  background: 'var(--red-bg)',
                  border: '1px solid var(--red-bd)',
                  borderRadius: 10,
                  color: 'var(--red)',
                  fontSize: 14,
                }}
              >
                {actionError}
              </div>
            )}

            {/* Botões de acção — alvos ≥100px */}
            <div style={{ display: 'flex', gap: 14, marginTop: 'auto' }}>
              {!problemMode && machineState === 'ready' && (
                <>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => startMutation.mutate(currentOp.id)}
                    style={bigButton('green', busy)}
                  >
                    <Play size={28} />
                    {startMutation.isPending ? 'A INICIAR…' : 'COMECEI'}
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => setProblemMode(true)}
                    style={problemButton(busy)}
                  >
                    <AlertTriangle size={22} />
                    PROBLEMA
                  </button>
                </>
              )}
              {!problemMode && machineState === 'running' && (
                <>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => completeMutation.mutate(currentOp.id)}
                    style={bigButton('green', busy)}
                  >
                    <Check size={28} />
                    {completeMutation.isPending ? 'A CONCLUIR…' : 'ACABEI'}
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => setProblemMode(true)}
                    style={problemButton(busy)}
                  >
                    <AlertTriangle size={22} />
                    PROBLEMA
                  </button>
                </>
              )}
              {problemMode && (
                <div
                  style={{
                    flex: 1,
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: 12,
                  }}
                >
                  {PROBLEM_KINDS.map((p) => (
                    <button
                      key={p.errorCode}
                      type="button"
                      disabled={busy}
                      onClick={() => reportProblem(p.errorCode)}
                      style={{
                        height: 100,
                        background: 'var(--bg-2)',
                        border: '1px solid var(--bd-2)',
                        borderRadius: 14,
                        color: 'var(--fg-0)',
                        fontSize: 18,
                        fontWeight: 500,
                        cursor: busy ? 'not-allowed' : 'pointer',
                        opacity: busy ? 0.6 : 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 12,
                      }}
                    >
                      {p.icon}
                      {p.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setProblemMode(false)}
                    style={{
                      gridColumn: '1 / -1',
                      height: 56,
                      background: 'transparent',
                      border: '1px solid var(--bd-1)',
                      borderRadius: 12,
                      color: 'var(--fg-2)',
                      fontSize: 15,
                      fontWeight: 500,
                      cursor: 'pointer',
                    }}
                  >
                    Cancelar
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default OperadorTabletPage;
