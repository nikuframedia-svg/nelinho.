/**
 * MoldHealthPanel — testes (Q.118.I).
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { MoldHealthPanel } from './MoldHealthPanel';
import { moldsApi, type Mold } from '../../lib/api';

afterEach(() => vi.restoreAllMocks());

function mold(over: Partial<Mold>): Mold {
  return {
    id: 'm1',
    mold_code: 'MLD-1',
    model_id: 'K1',
    name: null,
    pocket_count: 1,
    expected_life_cycles: null,
    active: true,
    depreciated: false,
    ...over,
  };
}

describe('MoldHealthPanel', () => {
  it('mostra moldes vermelhos/amarelos com o modelo clicável', async () => {
    vi.spyOn(moldsApi, 'healthReport').mockResolvedValue([
      mold({ id: 'm1', mold_code: 'MLD-1', health: { score_0_100: 30, risk_category: 'red', assessed_at: null, components: {} } }),
      mold({ id: 'm2', mold_code: 'MLD-2', health: { score_0_100: 90, risk_category: 'green', assessed_at: null, components: {} } }),
    ]);
    renderWithProviders(<MoldHealthPanel />, { withEntitySheets: true });
    await waitFor(() => expect(screen.getByTestId('mold-health-panel')).toBeInTheDocument());
    expect(screen.getByText('MLD-1')).toBeInTheDocument();
    expect(screen.queryByText('MLD-2')).not.toBeInTheDocument(); // verde não entra
  });

  it('esconde-se sem moldes em risco', async () => {
    vi.spyOn(moldsApi, 'healthReport').mockResolvedValue([
      mold({ health: { score_0_100: 95, risk_category: 'green', assessed_at: null, components: {} } }),
    ]);
    renderWithProviders(<MoldHealthPanel />, { withEntitySheets: true });
    await waitFor(() => expect(moldsApi.healthReport).toHaveBeenCalled());
    expect(screen.queryByTestId('mold-health-panel')).not.toBeInTheDocument();
  });
});
