/**
 * SyncStatusBadge — testes (Q.117.A).
 *
 * A lógica de cor/label do frescor ERP é pura (`resolve`) → testada
 * directamente. Smoke render confirma que o badge monta sem servidor
 * (estado loading → "ERP …"). ZERO MOCKS.
 */
import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { SyncStatusBadge, resolve } from './SyncStatusBadge';
import type { ErpConnectionResponse } from '../../lib/api';

function base(over: Partial<ErpConnectionResponse>): ErpConnectionResponse {
  return {
    enabled: true,
    url_masked: 'mssql://***@fabrica.nelo.eu/MAR-KAYAKS',
    connected: true,
    detail: null,
    latency_ms: 12,
    mirrors: [],
    last_sync_at: '2026-05-29T10:00:00Z',
    lag_seconds: 120,
    lag_human: '2m',
    total_rows_last_sync: 10,
    sync_history_error: null,
    sampled_at: '2026-05-29T10:02:00Z',
    ...over,
  };
}

describe('SyncStatusBadge.resolve', () => {
  it('verde quando ligado e lag < 10 min', () => {
    const r = resolve(base({ lag_seconds: 120, lag_human: '2m' }));
    expect(r.color).toBe('green');
    expect(r.label).toBe('ERP há 2m');
  });

  it('âmbar quando lag entre 10 e 30 min', () => {
    const r = resolve(base({ lag_seconds: 15 * 60, lag_human: '15m' }));
    expect(r.color).toBe('amber');
  });

  it('vermelho quando lag > 30 min', () => {
    const r = resolve(base({ lag_seconds: 45 * 60, lag_human: '45m' }));
    expect(r.color).toBe('red');
  });

  it('vermelho quando offline', () => {
    const r = resolve(base({ connected: false }));
    expect(r.color).toBe('red');
    expect(r.label).toBe('ERP offline');
  });

  it('cinza quando ERP desligado por config', () => {
    const r = resolve(base({ enabled: false }));
    expect(r.color).toBe('gray');
    expect(r.label).toBe('ERP desligado');
  });

  it('âmbar a sincronizar quando ainda não há sync', () => {
    const r = resolve(base({ last_sync_at: null, lag_seconds: null, lag_human: null }));
    expect(r.color).toBe('amber');
    expect(r.label).toBe('ERP a sincronizar…');
  });
});

describe('SyncStatusBadge render', () => {
  it('monta com estado loading sem servidor', () => {
    renderWithProviders(<SyncStatusBadge />);
    expect(screen.getByTestId('sync-status-badge')).toBeInTheDocument();
  });
});
