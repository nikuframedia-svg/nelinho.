/**
 * MasterDataBrowser — testes (Q.118.P).
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { MasterDataBrowser } from './MasterDataBrowser';
import { productsApi } from '../../lib/api';

afterEach(() => vi.restoreAllMocks());

describe('MasterDataBrowser', () => {
  it('lista produtos com nome clicável', async () => {
    vi.spyOn(productsApi, 'list').mockResolvedValue([
      { id: '1', product_code: 'K1V', product_name: 'K1 Vanquish', product_type: 'K', category: 'race', status: 'active' },
    ]);
    renderWithProviders(<MasterDataBrowser />, { withEntitySheets: true });
    await waitFor(() => expect(screen.getByText('K1 Vanquish')).toBeInTheDocument());
    expect(screen.getByText('K1V')).toBeInTheDocument();
    // os 4 segmentos de entidade existem
    expect(screen.getByText('Produtos')).toBeInTheDocument();
    expect(screen.getByText('Máquinas')).toBeInTheDocument();
  });

  it('empty state honesto sem registos', async () => {
    vi.spyOn(productsApi, 'list').mockResolvedValue([]);
    renderWithProviders(<MasterDataBrowser />, { withEntitySheets: true });
    await waitFor(() => expect(screen.getByText('Sem registos')).toBeInTheDocument());
  });
});
