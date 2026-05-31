/**
 * OtdHeatmap — testes (Q.118.K).
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { OtdHeatmap } from './OtdHeatmap';
import { kpisApi } from '../../lib/api';

afterEach(() => vi.restoreAllMocks());

describe('OtdHeatmap', () => {
  it('renderiza a matriz produto × semana', async () => {
    vi.spyOn(kpisApi, 'getOtdHeatmap').mockResolvedValue({
      product_types: ['K1', 'C2'],
      weeks: ['2026-05-01', '2026-05-08'],
      heatmap: {
        K1: { '2026-05-01': 95, '2026-05-08': 60 },
        C2: { '2026-05-01': null, '2026-05-08': 80 },
      },
    });
    renderWithProviders(<OtdHeatmap />);
    await waitFor(() => expect(screen.getByText(/Entregas a tempo/)).toBeInTheDocument());
    expect(screen.getByText('K1')).toBeInTheDocument();
    expect(screen.getByText('C2')).toBeInTheDocument();
  });

  it('esconde-se sem dados', async () => {
    vi.spyOn(kpisApi, 'getOtdHeatmap').mockResolvedValue({ product_types: [], weeks: [], heatmap: {} });
    const { container } = renderWithProviders(<OtdHeatmap />);
    await waitFor(() => expect(kpisApi.getOtdHeatmap).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });
});
