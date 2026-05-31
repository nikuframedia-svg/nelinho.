// PlaneamentoPage — teste de cobertura do fluxo async de replaneamento
// (Q.62.E.5b).
//
// Q.62.E.5 migrou a página de `runSchedule` síncrono (bloqueia ate 30s) para
// `runScheduleAsync` + polling em `pollScheduleJob` + promoção via
// `approveScheduleJob`. Este teste guarda o contrato visível dos 7 estados:
//   1. initial render (botão "Replanear")
//   2. enqueue success → badge "A processar..."
//   3. polling in_progress (badge azul persiste)
//   4. polling complete → banner verde + botão "Aprovar"
//   5. approve success → banner "Plano aprovado"
//   6. polling failed → banner vermelho
//   7. enqueue error → banner "Falha a enfileirar replano"
//
// Os mocks isolam a página dos endpoints reais — `cpoCommitsApi` e
// `materiaisApi` são mockados a devolver listas vazias, e `BarcosTimeline`
// é mockado para um stub leve (o componente real corre `useDragDrop` +
// muitas queries que poluiriam o teste).
//
// `vi.useFakeTimers()` controla o `refetchInterval` de 2s da TanStack
// Query — sem isso o test esperaria ate 2s reais por cada poll.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test/renderWithProviders';

// ─── Mocks ───────────────────────────────────────────────────────────────
//
// `vi.mock` é hoisted, por isso a factory tem de ser self-contained — não
// pode capturar variáveis de cima. Usamos `vi.hoisted` para partilhar as
// instâncias dos `vi.fn()` com o resto do ficheiro.
const planeamentoMocks = vi.hoisted(() => ({
  runScheduleAsync: vi.fn(),
  pollScheduleJob: vi.fn(),
  approveScheduleJob: vi.fn(),
  priorityReport: vi.fn(),
  runSchedule: vi.fn(),
  calendar: vi.fn(),
  startBy: vi.fn(),
  suggestShipment: vi.fn(),
  adherence: vi.fn(),
}));

vi.mock('../../components/planeamento/planeamentoApi', () => ({
  planeamentoApi: planeamentoMocks,
}));

// `cpoCommitsApi` e `materiaisApi` são consumidos pelas tabs Pessoas /
// Materiais — só precisamos que devolvam vazio para o render não rebentar.
vi.mock('../../lib/api', () => ({
  cpoCommitsApi: {
    list: vi.fn().mockResolvedValue([]),
    get: vi.fn().mockResolvedValue({ operations: [] }),
  },
}));

vi.mock('../../components/materiais/materiaisApi', () => ({
  materiaisApi: {
    listMaterialsFromBom: vi
      .fn()
      .mockResolvedValue({ items: [], stock_available: false }),
  },
}));

// `BarcosTimeline` puxa muitas queries (commits, ghost suggestion, drag/drop)
// — substituímo-lo por um stub para o teste só medir a shell da PlaneamentoPage.
vi.mock('../../components/planeamento/BarcosTimeline', () => ({
  BarcosTimeline: () => <div data-testid="barcos-timeline-stub" />,
  CpoGhostSuggestion: () => <div data-testid="cpo-ghost-stub" />,
}));

import PlaneamentoPage from './PlaneamentoPage';
import type {
  CpoJobStatusResponse,
  CpoScheduleResult,
} from '../../components/planeamento/planeamentoApi';

// ─── Fixtures ────────────────────────────────────────────────────────────
const JOB_ID = 'job-abc-12345678';

const enqueueResponse = {
  job_id: JOB_ID,
  status_url: `/v1/plan/cpo/schedule/job/${JOB_ID}`,
  enqueued_at: '2026-05-20T10:00:00Z',
};

function makeResult(opCount: number): CpoScheduleResult {
  return {
    tenant_id: '00000000-0000-0000-0000-000000000001',
    engine_used: 'cpo-v4',
    status: 'success',
    solve_time_sec: 12.3,
    makespan_hours: 8.5,
    num_late_orders: 0,
    setups: 5,
    degraded: false,
    fallback_reason: null,
    operations: Array.from({ length: opCount }, (_, i) => ({
      operation_id: `op-${i}`,
      order_id: `ord-${i}`,
      phase_id: 'F01',
      machine_id: null,
      workers: ['w1'],
      mold_id: null,
      mold_batch_id: null,
      start_time: '2026-05-20T07:00:00Z',
      end_time: '2026-05-20T08:00:00Z',
      duration_minutes: 60,
      setup_family: null,
    })),
    warnings: [],
    unplanned_orders: [],
    orders_coverage: 1,
    commit_sha256: 'commit-sha-aaaa1111',
  };
}

function jobStatus(
  state: CpoJobStatusResponse['state'],
  overrides: Partial<CpoJobStatusResponse> = {},
): CpoJobStatusResponse {
  return {
    job_id: JOB_ID,
    state,
    result: null,
    error: null,
    enqueued_at: '2026-05-20T10:00:00Z',
    started_at: null,
    completed_at: null,
    ...overrides,
  };
}

// ─── Setup ───────────────────────────────────────────────────────────────
beforeEach(() => {
  Object.values(planeamentoMocks).forEach((m) => m.mockReset());
  // Default: priorityReport rejeita (tab Pessoas só carrega quando
  // navegamos lá; mantemos a rejeição para evitar warnings).
  planeamentoMocks.priorityReport.mockRejectedValue(new Error('no commit'));
});

afterEach(() => {
  vi.useRealTimers();
});

// ─── Tests ───────────────────────────────────────────────────────────────
describe('PlaneamentoPage — replanear async (Q.62.E.5)', () => {
  it('1. initial render: botão "Replanear" presente, sem badge de progresso', () => {
    renderWithProviders(<PlaneamentoPage />, { route: '/planeamento' });

    expect(
      screen.getByRole('button', { name: /Replanear/i }),
    ).toBeInTheDocument();
    // Sem job activo: nem badge de progresso, nem botão Aprovar.
    expect(screen.queryByText(/A processar plano/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Aprovar/i }),
    ).not.toBeInTheDocument();
  });

  it('2. enqueue success: click no botão chama runScheduleAsync e mostra "A processar"', async () => {
    planeamentoMocks.runScheduleAsync.mockResolvedValue(enqueueResponse);
    // Polling devolve "deferred" para o badge se manter visível.
    planeamentoMocks.pollScheduleJob.mockResolvedValue(jobStatus('deferred'));

    const user = userEvent.setup();
    renderWithProviders(<PlaneamentoPage />, { route: '/planeamento' });

    await user.click(screen.getByRole('button', { name: /Replanear/i }));

    await waitFor(() => {
      expect(planeamentoMocks.runScheduleAsync).toHaveBeenCalledWith({
        horizon_days: 7,
      });
    });
    await waitFor(() => {
      expect(screen.getByText(/A processar plano/i)).toBeInTheDocument();
    });
  });

  it('3. polling in_progress: UI continua a mostrar badge azul', async () => {
    planeamentoMocks.runScheduleAsync.mockResolvedValue(enqueueResponse);
    planeamentoMocks.pollScheduleJob.mockResolvedValue(
      jobStatus('in_progress', { started_at: '2026-05-20T10:00:05Z' }),
    );

    const user = userEvent.setup();
    renderWithProviders(<PlaneamentoPage />, { route: '/planeamento' });

    await user.click(screen.getByRole('button', { name: /Replanear/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/estado:\s*in_progress/i),
      ).toBeInTheDocument();
    });
    // Botão Replanear continua disabled enquanto o job vai.
    expect(screen.getByRole('button', { name: /A replanear/i })).toBeDisabled();
  });

  it('4. polling complete: banner verde + botão "Aprovar (LIVE)"', async () => {
    planeamentoMocks.runScheduleAsync.mockResolvedValue(enqueueResponse);
    // Primeira resposta é "in_progress", segunda é "complete" — usamos
    // fake timers para avançar o refetchInterval da TanStack Query (2s).
    planeamentoMocks.pollScheduleJob
      .mockResolvedValueOnce(jobStatus('in_progress'))
      .mockResolvedValue(
        jobStatus('complete', {
          result: makeResult(10),
          completed_at: '2026-05-20T10:00:30Z',
        }),
      );

    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithProviders(<PlaneamentoPage />, { route: '/planeamento' });

    await user.click(screen.getByRole('button', { name: /Replanear/i }));

    // Espera pelo primeiro poll (in_progress).
    await waitFor(() => {
      expect(planeamentoMocks.pollScheduleJob).toHaveBeenCalled();
    });

    // Avança o tempo 2.1s para disparar o refetch — o `shouldAdvanceTime`
    // mantém os micro-ticks a correr para o React processar os updates.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });

    await waitFor(() => {
      expect(screen.getByText(/Plano pronto \(DRAFT\)/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/10\s*operações/i)).toBeInTheDocument();
    expect(screen.getByText(/makespan\s*8\.5h/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Aprovar \(LIVE\)/i }),
    ).toBeInTheDocument();
  });

  it('4b. Q.131.H honestidade: banner de ordens sem rota não planeadas', async () => {
    planeamentoMocks.runScheduleAsync.mockResolvedValue(enqueueResponse);
    const result = makeResult(6);
    result.unplanned_orders = ['OF-AAA', 'OF-BBB'];
    result.orders_coverage = 0.75;
    planeamentoMocks.pollScheduleJob
      .mockResolvedValueOnce(jobStatus('in_progress'))
      .mockResolvedValue(jobStatus('complete', { result }));

    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithProviders(<PlaneamentoPage />, { route: '/planeamento' });
    await user.click(screen.getByRole('button', { name: /Replanear/i }));
    await waitFor(() => {
      expect(planeamentoMocks.pollScheduleJob).toHaveBeenCalled();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });

    // As ordens órfãs são MOSTRADAS (nunca saltadas em silêncio).
    await waitFor(() => {
      expect(
        screen.getByText(/ordens sem rota conhecida/i),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/OF-AAA, OF-BBB/)).toBeInTheDocument();
  });

  it('5. approve success: banner "Plano aprovado · commit ... → LIVE"', async () => {
    planeamentoMocks.runScheduleAsync.mockResolvedValue(enqueueResponse);
    planeamentoMocks.pollScheduleJob.mockResolvedValue(
      jobStatus('complete', { result: makeResult(3) }),
    );
    planeamentoMocks.approveScheduleJob.mockResolvedValue({
      job_id: JOB_ID,
      commit_sha256: 'abc12345deadbeef',
      previous_status: 'DRAFT',
      new_status: 'LIVE',
      approved_at: '2026-05-20T10:01:00Z',
    });

    const user = userEvent.setup();
    renderWithProviders(<PlaneamentoPage />, { route: '/planeamento' });

    await user.click(screen.getByRole('button', { name: /Replanear/i }));

    // Espera que o botão Aprovar apareça (job já complete na primeira poll).
    const approveBtn = await screen.findByRole('button', {
      name: /Aprovar \(LIVE\)/i,
    });
    await user.click(approveBtn);

    await waitFor(() => {
      expect(planeamentoMocks.approveScheduleJob).toHaveBeenCalledWith(JOB_ID);
    });
    await waitFor(() => {
      expect(screen.getByText(/Plano aprovado/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/commit\s*abc12345/i)).toBeInTheDocument();
    expect(screen.getByText(/→\s*LIVE/i)).toBeInTheDocument();
  });

  it('6. polling failed: banner vermelho com a mensagem de erro', async () => {
    planeamentoMocks.runScheduleAsync.mockResolvedValue(enqueueResponse);
    planeamentoMocks.pollScheduleJob.mockResolvedValue(
      jobStatus('failed', { error: 'OOM' }),
    );

    const user = userEvent.setup();
    renderWithProviders(<PlaneamentoPage />, { route: '/planeamento' });

    await user.click(screen.getByRole('button', { name: /Replanear/i }));

    await waitFor(() => {
      expect(screen.getByText(/falhou/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/OOM/)).toBeInTheDocument();
    // Sem botão Aprovar num job falhado.
    expect(
      screen.queryByRole('button', { name: /Aprovar/i }),
    ).not.toBeInTheDocument();
  });

  it('7. enqueue error: banner "Falha a enfileirar replano: <mensagem>"', async () => {
    planeamentoMocks.runScheduleAsync.mockRejectedValue(new Error('network'));

    const user = userEvent.setup();
    renderWithProviders(<PlaneamentoPage />, { route: '/planeamento' });

    await user.click(screen.getByRole('button', { name: /Replanear/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Falha a enfileirar replano/i),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/network/)).toBeInTheDocument();
    // pollScheduleJob não é chamado se o enqueue falhou (sem job_id).
    expect(planeamentoMocks.pollScheduleJob).not.toHaveBeenCalled();
  });
});
