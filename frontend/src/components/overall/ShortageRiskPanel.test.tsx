/**
 * ShortageRiskPanel — testes (Q.118.N).
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { ShortageRiskPanel } from './ShortageRiskPanel';
import { shortageRisksApi, type ShortageRisksResponse } from '../../lib/api';

afterEach(() => vi.restoreAllMocks());

function resp(items: ShortageRisksResponse['items']): ShortageRisksResponse {
  return { horizon_days: 14, items, counts: { high: 0, med: 0, low: 0 } };
}

describe('ShortageRiskPanel', () => {
  it('mostra materiais HIGH/MED em risco', async () => {
    vi.spyOn(shortageRisksApi, 'get').mockResolvedValue(
      resp([
        { sku_id: 'RESINA-A', on_hand: 5, rop: 20, avg_daily_demand: 2, lead_time_days: 7, days_to_stockout: 2, severity: 'HIGH' },
        { sku_id: 'TINTA-X', on_hand: 100, rop: 10, avg_daily_demand: 1, lead_time_days: 3, days_to_stockout: 100, severity: 'LOW' },
      ]),
    );
    renderWithProviders(<ShortageRiskPanel />);
    await waitFor(() => expect(screen.getByTestId('shortage-risk-panel')).toBeInTheDocument());
    expect(screen.getByText('RESINA-A')).toBeInTheDocument();
    expect(screen.queryByText('TINTA-X')).not.toBeInTheDocument(); // LOW não entra
  });

  it('esconde-se sem faltas', async () => {
    vi.spyOn(shortageRisksApi, 'get').mockResolvedValue(resp([]));
    const { container } = renderWithProviders(<ShortageRiskPanel />);
    await waitFor(() => expect(shortageRisksApi.get).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });
});
