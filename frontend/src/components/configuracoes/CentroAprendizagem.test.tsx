/**
 * CentroAprendizagem — testes (Q.118.M).
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { CentroAprendizagem } from './CentroAprendizagem';
import { learningApi } from '../../lib/api/governanceApi';

afterEach(() => vi.restoreAllMocks());

describe('CentroAprendizagem', () => {
  it('mostra camadas 2/3 + pares com dados reais', async () => {
    vi.spyOn(learningApi, 'weights').mockResolvedValue({
      status: 'ok', current_weights: {}, default_weights: {}, multipliers: {},
      pairs_used: 42, commits_scanned: 100, trained_at: '2026-05-20T00:00:00Z',
      blend_learned_pct: 70, min_pairs_threshold: 5, reason: null,
    });
    vi.spyOn(learningApi, 'adapter').mockResolvedValue({
      active_version: 'v3', promoted_at: null, promoted_by: null, reason: null,
      intent_match_rate: 0.92, safety_violations_count: 0, has_previous: true,
    });
    vi.spyOn(learningApi, 'pairs').mockResolvedValue({
      total_commits_with_rejection: 10, total_pairs: 30, eligible_for_dpo: 12,
      by_category: {}, by_weekday: {}, last_30d: { commits: 5, pairs: 8, eligible: 3 },
      last_90d: { commits: 10, pairs: 30, eligible: 12 }, abl_pairs_today: 1, min_reason_len: 10,
    });

    renderWithProviders(<CentroAprendizagem />, { withToast: true });
    expect(screen.getByText('Centro de aprendizagem')).toBeInTheDocument();
    // espera a query do adapter resolver
    await waitFor(() => expect(screen.getByText('v3')).toBeInTheDocument());
    // botão reverter aparece (has_previous=true)
    expect(screen.getByRole('button', { name: /reverter/i })).toBeInTheDocument();
  });

  it('degrada com "Indisponível" quando uma query falha', async () => {
    vi.spyOn(learningApi, 'weights').mockRejectedValue(new Error('x'));
    vi.spyOn(learningApi, 'adapter').mockRejectedValue(new Error('x'));
    vi.spyOn(learningApi, 'pairs').mockRejectedValue(new Error('x'));
    renderWithProviders(<CentroAprendizagem />, { withToast: true });
    await waitFor(() => expect(screen.getAllByText('Indisponível.').length).toBeGreaterThan(0));
  });
});
