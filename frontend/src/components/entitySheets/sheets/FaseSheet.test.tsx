/**
 * FaseSheet — testes (Q.154.A).
 *
 * A aba "Configuração" mostrava o código cru do colaborador (employee_code)
 * nos checkboxes de "Operadores qualificados". Agora resolve para o NOME, com
 * o código pequeno ao lado, e cai no código quando o nome não resolve.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../../test/renderWithProviders';
import FaseSheet from './FaseSheet';
import {
  entityApi,
  employeesApi,
  type FaseSummary,
  type PhaseConfigOut,
} from '../../../lib/api';

afterEach(() => vi.restoreAllMocks());

const FASE: FaseSummary = {
  phase_id: 'LAM',
  phase_name: 'Laminagem',
  top_operators: [],
  difficult_boats: [],
  curing_gaps_in: [],
  curing_gaps_out: [],
  fila_mediana_h: null,
};

const CONFIG: PhaseConfigOut = {
  phase_id: 'LAM',
  overrides: {
    team_size_override: null,
    num_stations_override: null,
    allowed_worker_ids: null,
    note: null,
  },
  baselines: {
    capable_worker_ids: ['21564', '99999'], // 21564 resolve; 99999 não (histórico)
    affinity_worker_ids: ['21564'],
    suggested_stations: 2,
    team_size_default: 2,
    expected_duration_h: 3.2,
    canonical_rank: 1,
    typical_prev_phase: 'CORTE',
    typical_next_phase: 'PINTURA',
  },
};

describe('FaseSheet — Configuração (Q.154.A)', () => {
  it('mostra nome do colaborador com o código ao lado; cai no código quando não resolve', async () => {
    vi.spyOn(entityApi, 'fase').mockResolvedValue(FASE);
    vi.spyOn(entityApi.phaseConfig, 'get').mockResolvedValue(CONFIG);
    vi.spyOn(employeesApi, 'list').mockResolvedValue([
      { employee_code: '21564', employee_name: 'Maria Silva' },
    ]);

    renderWithProviders(<FaseSheet phaseId="LAM" onClose={() => {}} />, {
      withToast: true,
    });

    // Sheet abre com o nome da fase.
    await waitFor(() => expect(screen.getByText('Laminagem')).toBeInTheDocument());

    // Muda para a aba "Configuração".
    fireEvent.click(screen.getByText('Configuração'));

    // Código resolvido → mostra o NOME...
    expect(await screen.findByText('Maria Silva')).toBeInTheDocument();
    // ...com o código pequeno ao lado (referência cruzada mantida).
    expect(screen.getByText('21564')).toBeInTheDocument();
    // Código sem nome no core → mostra o código cru (fallback honesto).
    expect(screen.getByText('99999')).toBeInTheDocument();
  });
});
