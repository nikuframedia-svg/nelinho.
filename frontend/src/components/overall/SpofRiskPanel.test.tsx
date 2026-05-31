/**
 * SpofRiskPanel — testes (Q.118.Q).
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { SpofRiskPanel } from './SpofRiskPanel';
import { workforceRisksApi, type SpofRecommendation } from '../../lib/api';

afterEach(() => vi.restoreAllMocks());

function spof(over: Partial<SpofRecommendation>): SpofRecommendation {
  return {
    id: 's1', priority: 'high', employee_id: 'E1', employee_name: 'Ana',
    employee_current_phases: [], target_phase_id: 'LAM', target_phase_name: 'Laminagem',
    reasoning: [], expected_impact: {}, estimated_cost: {}, trust_index: 0.8, ...over,
  };
}

describe('SpofRiskPanel', () => {
  it('mostra fase + operador clicáveis', async () => {
    vi.spyOn(workforceRisksApi, 'spof').mockResolvedValue([spof({})]);
    renderWithProviders(<SpofRiskPanel />, { withEntitySheets: true });
    await waitFor(() => expect(screen.getByTestId('spof-risk-panel')).toBeInTheDocument());
    expect(screen.getByText('Laminagem')).toBeInTheDocument();
    expect(screen.getByText('Ana')).toBeInTheDocument();
  });

  it('esconde-se sem SPOFs', async () => {
    vi.spyOn(workforceRisksApi, 'spof').mockResolvedValue([]);
    const { container } = renderWithProviders(<SpofRiskPanel />, { withEntitySheets: true });
    await waitFor(() => expect(workforceRisksApi.spof).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });
});
