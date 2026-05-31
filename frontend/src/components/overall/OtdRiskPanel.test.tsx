/**
 * OtdRiskPanel — testes (Q.118.H).
 * Mostra ordens em risco; esconde-se sem modelo (degradação honesta).
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { OtdRiskPanel } from './OtdRiskPanel';
import { otdRiskApi, type OtdRiskResponse } from '../../lib/api';

afterEach(() => vi.restoreAllMocks());

function resp(over: Partial<OtdRiskResponse>): OtdRiskResponse {
  return { model_available: true, orders: [], ...over };
}

describe('OtdRiskPanel', () => {
  it('mostra as ordens em risco alto/médio', async () => {
    vi.spyOn(otdRiskApi, 'list').mockResolvedValue(
      resp({
        orders: [
          { of_id: 'OF-9', product_name: 'K1', product_type: 'K', current_phase_name: 'LAM', transport_date: null, late_probability: 0.8, risk_band: 'alto' },
          { of_id: 'OF-3', product_name: 'C2', product_type: 'C', current_phase_name: 'PIN', transport_date: null, late_probability: 0.1, risk_band: 'baixo' },
        ],
      }),
    );
    renderWithProviders(<OtdRiskPanel />, { withEntitySheets: true });
    await waitFor(() => expect(screen.getByTestId('otd-risk-panel')).toBeInTheDocument());
    // só a de risco alto entra
    expect(screen.getByText('#OF-9')).toBeInTheDocument();
    expect(screen.queryByText('#OF-3')).not.toBeInTheDocument();
  });

  it('esconde-se quando não há modelo (degradação honesta)', async () => {
    vi.spyOn(otdRiskApi, 'list').mockResolvedValue(resp({ model_available: false }));
    const { container } = renderWithProviders(<OtdRiskPanel />, { withEntitySheets: true });
    await waitFor(() => expect(otdRiskApi.list).toHaveBeenCalled());
    expect(screen.queryByTestId('otd-risk-panel')).not.toBeInTheDocument();
    expect(container.textContent).toBe('');
  });
});
