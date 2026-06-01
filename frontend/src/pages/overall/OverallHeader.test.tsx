// OverallPage — header Replanear/Aprovar (Q.153.D3).
//
// Migra a cobertura do fluxo async de replan/approve que vivia no antigo
// PlaneamentoPage.test.tsx (apagado no Q.153.D3 — a página era código morto). O
// /overall absorveu o "Replanear" (runScheduleAsync→poll) + "Aprovar plano"
// (approveCommit, DRAFT→LIVE, Q.153.B1/B2). Guardamos o contrato visível:
//   1. render inicial → botões "Replanear" + "Aprovar plano" presentes;
//   2. click Replanear → planeamentoApi.runScheduleAsync chamado (horizon 42);
//   3. click Aprovar plano → planeamentoApi.approveCommit chamado com o sha.
//
// As vistas pesadas (RiskStrip / Por*View / overlays) e os hooks de fetch são
// stubbed — o teste mede só a SHELL do header, como o teste antigo stubava o
// BarcosTimeline.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test/renderWithProviders';

const DRAFT_SHA = 'abc12345deadbeef';

const planeamentoMocks = vi.hoisted(() => ({
  runScheduleAsync: vi.fn(),
  pollScheduleJob: vi.fn(),
  approveCommit: vi.fn(),
}));

const apiMocks = vi.hoisted(() => ({
  cpoList: vi.fn(),
  cpoGet: vi.fn(),
  actualsList: vi.fn(),
  alertsList: vi.fn(),
  excludedList: vi.fn(),
}));

vi.mock('../../components/planeamento/planeamentoApi', () => ({
  planeamentoApi: planeamentoMocks,
}));

vi.mock('../../lib/api', () => ({
  cpoCommitsApi: { list: apiMocks.cpoList, get: apiMocks.cpoGet },
  planOperationsApi: { reorder: vi.fn() },
  timelineActualsApi: { list: apiMocks.actualsList },
  copilotAlertsApi: { list: apiMocks.alertsList },
  planExclusionApi: {
    excludeBoat: vi.fn(),
    reincludeBoat: vi.fn(),
    listExcludedBoats: apiMocks.excludedList,
  },
  schedulePreviewApi: { previewDelta: vi.fn() },
  // ToastProvider liga o toast ao retry/health do fetch layer via este export.
  setToastContext: vi.fn(),
}));

vi.mock('../../lib/api/masterDataApi', () => ({
  employeesApi: { list: vi.fn().mockResolvedValue([]) },
}));

vi.mock('../../hooks/usePendingDecisions', () => ({
  usePendingDecisions: () => ({ decisions: [] }),
}));

// Vistas pesadas / overlays → stubs (poluiriam o teste com queries próprias).
vi.mock('../../components/overall/RiskStrip', () => ({
  RiskStrip: () => <div data-testid="risk-strip-stub" />,
}));
vi.mock('../../components/overall/AutoProposeOverlay', () => ({
  AutoProposeOverlay: () => <div data-testid="autopropose-stub" />,
}));
vi.mock('../../components/overall/views/PorBarcoView', () => ({
  PorBarcoView: () => <div data-testid="porbarco-stub" />,
}));
vi.mock('../../components/overall/views/PorFaseView', () => ({
  PorFaseView: () => <div data-testid="porfase-stub" />,
}));
vi.mock('../../components/overall/views/PorPessoaView', () => ({
  PorPessoaView: () => <div data-testid="porpessoa-stub" />,
}));
vi.mock('../../components/overall/views/PorExpedicaoView', () => ({
  PorExpedicaoView: () => <div data-testid="porexpedicao-stub" />,
}));

import OverallPage from './OverallPage';

function draftCommit() {
  return {
    id: 'c1',
    commit_sha256: DRAFT_SHA,
    short_sha: DRAFT_SHA.slice(0, 12),
    status: 'DRAFT',
    operations_count: 0,
    safety_net_triggered: false,
  };
}

beforeEach(() => {
  Object.values(planeamentoMocks).forEach((m) => m.mockReset());
  apiMocks.cpoList.mockResolvedValue([draftCommit()]);
  apiMocks.cpoGet.mockResolvedValue({ ...draftCommit(), operations: [] });
  apiMocks.actualsList.mockResolvedValue({ items: [], expeditions: [], truncated: false });
  apiMocks.alertsList.mockResolvedValue([]);
  apiMocks.excludedList.mockResolvedValue([]);
});

describe('OverallPage — header Replanear/Aprovar (Q.153.D3)', () => {
  it('1. render inicial: botões "Replanear" + "Aprovar plano" presentes (commit DRAFT)', async () => {
    renderWithProviders(<OverallPage />, {
      route: '/overall',
      withToast: true,
      withEntitySheets: true,
    });

    expect(
      await screen.findByRole('button', { name: /Replanear/i }),
    ).toBeInTheDocument();
    // Aprovar só aparece quando há commit não-LIVE (DRAFT).
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /Aprovar plano/i }),
      ).toBeInTheDocument();
    });
  });

  it('2. click Replanear → runScheduleAsync(horizon_days 42)', async () => {
    planeamentoMocks.runScheduleAsync.mockResolvedValue({ job_id: 'job-1' });
    planeamentoMocks.pollScheduleJob.mockResolvedValue({ state: 'deferred' });

    const user = userEvent.setup();
    renderWithProviders(<OverallPage />, {
      route: '/overall',
      withToast: true,
      withEntitySheets: true,
    });

    await user.click(await screen.findByRole('button', { name: /Replanear/i }));

    await waitFor(() => {
      expect(planeamentoMocks.runScheduleAsync).toHaveBeenCalledWith(
        expect.objectContaining({ horizon_days: 42 }),
      );
    });
  });

  it('3. click Aprovar plano → approveCommit(sha do DRAFT)', async () => {
    planeamentoMocks.approveCommit.mockResolvedValue({ commit_sha256: DRAFT_SHA });

    const user = userEvent.setup();
    renderWithProviders(<OverallPage />, {
      route: '/overall',
      withToast: true,
      withEntitySheets: true,
    });

    const approveBtn = await screen.findByRole('button', { name: /Aprovar plano/i });
    await user.click(approveBtn);

    await waitFor(() => {
      expect(planeamentoMocks.approveCommit).toHaveBeenCalledWith(DRAFT_SHA);
    });
  });
});
