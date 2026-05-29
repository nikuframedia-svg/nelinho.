/**
 * SyncStatusBadge — frescor do sync ERP no TopBar global (Q.117.A).
 * ==================================================================
 *
 * O sync incremental ERP→Postgres corre de 5/5 min (job
 * `nelo_erp_incremental_sync`). Este badge dá ao utilizador visibilidade
 * directa do frescor: "ERP há Xm" + dot de estado, lido de
 * GET /v1/diagnostics/erp-connection (campo `lag_human` / `lag_seconds`).
 *
 * Estados (dot):
 *   • verde   — ligado e lag < 10 min (sync de 5 min saudável)
 *   • âmbar   — ligado mas lag 10–30 min (a atrasar)
 *   • vermelho— offline, erro, ou lag > 30 min
 *   • cinza   — sqlserver_enabled=False (ERP desligado por config)
 *
 * ZERO MOCKS: erro/loading têm estado explícito, nunca dados inventados.
 * Tooltip lista o frescor por mirror (stock/calendar/quality).
 */

import { useQuery } from '@tanstack/react-query';
import { diagnosticsApi } from '../../lib/api';
import { diagnosticsKeys } from '../../lib/api/keys';
import type { ErpConnectionResponse, ErpMirrorStatus } from '../../lib/api';

type DotColor = 'green' | 'amber' | 'red' | 'gray';

const DOT_VAR: Record<DotColor, string> = {
  green: 'var(--green)',
  amber: 'var(--amber, #f59e0b)',
  red: 'var(--red, #ef4444)',
  gray: 'var(--fg-3)',
};

const HEALTHY_LAG_S = 10 * 60; // 5 min de cadência → < 10 min é saudável
const STALE_LAG_S = 30 * 60;

export function resolve(data: ErpConnectionResponse): { color: DotColor; label: string } {
  if (!data.enabled) return { color: 'gray', label: 'ERP desligado' };
  if (!data.connected) return { color: 'red', label: 'ERP offline' };
  if (data.lag_seconds == null || data.last_sync_at == null) {
    return { color: 'amber', label: 'ERP a sincronizar…' };
  }
  const color: DotColor =
    data.lag_seconds < HEALTHY_LAG_S ? 'green' : data.lag_seconds < STALE_LAG_S ? 'amber' : 'red';
  return { color, label: `ERP há ${data.lag_human}` };
}

function mirrorTooltip(mirrors: ErpMirrorStatus[]): string {
  if (mirrors.length === 0) return 'Sem histórico de sync.';
  return mirrors
    .map((m) => {
      if (m.status === 'never_synced') return `${m.source}: nunca`;
      if (m.status === 'error') return `${m.source}: erro`;
      const when = m.finished_at
        ? new Date(m.finished_at).toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' })
        : '—';
      return `${m.source}: ${when} (+${m.rows_inserted}/~${m.rows_updated})`;
    })
    .join(' · ');
}

export function SyncStatusBadge() {
  const { data, isLoading, isError } = useQuery({
    queryKey: diagnosticsKeys.erpConnection(),
    queryFn: () => diagnosticsApi.erpConnection(),
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
  });

  let color: DotColor = 'gray';
  let label = 'ERP …';
  let title = 'Estado do sync ERP';

  if (isLoading) {
    color = 'gray';
    label = 'ERP …';
  } else if (isError || !data) {
    color = 'red';
    label = 'ERP sem estado';
    title = 'Não foi possível ler o estado do sync ERP.';
  } else {
    const r = resolve(data);
    color = r.color;
    label = r.label;
    title = `${data.url_masked ?? 'ERP'} · ${mirrorTooltip(data.mirrors)}`;
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 text-text-dark-tertiary cursor-default"
      style={{
        padding: '4px 10px',
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: 999,
        fontSize: 11,
      }}
      title={title}
      aria-label={label}
      data-testid="sync-status-badge"
    >
      <span
        className={color === 'green' ? 'rounded-full animate-pulse' : 'rounded-full'}
        style={{ width: 6, height: 6, background: DOT_VAR[color] }}
      />
      {label}
    </span>
  );
}
