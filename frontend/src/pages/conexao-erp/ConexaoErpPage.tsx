/**
 * ConexaoErpPage — /conexao-erp · estado vivo da integração com a ERP NELO.
 *
 * Q.53.L. Responde "a ERP MAR-KAYAKS está ligada e os dados frescos?":
 *   - URL de ligação mascarado + flag enabled;
 *   - ligado / offline (round-trip real quando a ERP está activa);
 *   - última sync por mirror (core.etl_run) com contagem de linhas;
 *   - lag desde a última sync com sucesso.
 *
 * Fonte: `GET /v1/diagnostics/erp-connection` (Q.53.F). ZERO MOCKS — uma
 * ERP desligada ou sem histórico mostra um estado degradado honesto.
 *
 * A rota desta página é registada à parte (App.tsx, fora deste território).
 */

import { useQuery } from '@tanstack/react-query';
import {
  Database,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkBadge, EmptyState } from '../../components/dark';
import { conexaoErpApi, type ErpMirror } from './conexaoErpApi';

// ─── Helpers ────────────────────────────────────────────────────────────────

function mirrorBadgeVariant(
  status: string,
): 'success' | 'danger' | 'warning' | 'neutral' {
  if (status === 'ok') return 'success';
  if (status === 'error') return 'danger';
  if (status === 'never_synced') return 'neutral';
  return 'warning';
}

function mirrorStatusLabel(status: string): string {
  switch (status) {
    case 'ok':
      return 'Sincronizada';
    case 'error':
      return 'Erro';
    case 'never_synced':
      return 'Nunca sincronizada';
    default:
      return status;
  }
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('pt-PT', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ConexaoErpPage() {
  const query = useQuery({
    queryKey: ['conexao-erp', 'connection'],
    queryFn: () => conexaoErpApi.connection(),
    refetchInterval: 30_000,
    retry: 0,
  });

  const data = query.data;

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Sistema' }, { label: 'Conexão ERP' }]}
      title="Conexão ERP"
      subtitle="Estado vivo da integração com a ERP NELO MAR-KAYAKS"
      icon={<Database className="h-6 w-6" />}
      actions={
        <button
          type="button"
          onClick={() => query.refetch()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-fg-2 hover:bg-white/5 hover:text-fg-0 border border-bd-1 text-xs font-medium transition-colors"
        >
          <RefreshCw size={13} />
          Atualizar
        </button>
      }
    >
      {query.isLoading ? (
        <div className="py-16 text-center text-sm text-fg-3">
          A consultar o estado da ERP…
        </div>
      ) : query.isError || !data ? (
        <EmptyState
          title="Não foi possível consultar a ERP"
          hint="O endpoint /v1/diagnostics/erp-connection não respondeu."
          icon={<XCircle size={32} />}
        />
      ) : (
        <div className="flex flex-col gap-3.5">
          {/* Estado da ligação */}
          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-lg)',
              padding: 18,
            }}
          >
            <div className="flex items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2.5">
                {data.connected ? (
                  <CheckCircle2 size={18} className="text-green" />
                ) : (
                  <XCircle size={18} className="text-red" />
                )}
                <span
                  style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-0)' }}
                >
                  {data.connected ? 'ERP ligada' : 'ERP offline'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <DarkBadge variant={data.enabled ? 'info' : 'neutral'}>
                  {data.enabled ? 'integração activa' : 'integração desligada'}
                </DarkBadge>
                {data.latency_ms !== null && (
                  <DarkBadge variant="neutral">
                    {data.latency_ms} ms
                  </DarkBadge>
                )}
              </div>
            </div>

            <InfoRow label="URL de ligação">
              <span
                className="font-mono"
                style={{ fontSize: 11.5, color: 'var(--fg-1)' }}
              >
                {data.url_masked ?? 'não configurado'}
              </span>
            </InfoRow>
            {data.detail && (
              <InfoRow label="Detalhe">
                <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                  {data.detail}
                </span>
              </InfoRow>
            )}
            <InfoRow label="Última sync com sucesso">
              <span style={{ fontSize: 11.5, color: 'var(--fg-1)' }}>
                {fmtDate(data.last_sync_at)}
              </span>
            </InfoRow>
            <InfoRow label="Lag desde a última sync">
              <span className="flex items-center gap-1.5">
                <Clock size={11} className="text-fg-3" />
                <span style={{ fontSize: 11.5, color: 'var(--fg-1)' }}>
                  {data.lag_human ?? '—'}
                </span>
              </span>
            </InfoRow>
            <InfoRow label="Linhas lidas na última sync">
              <span
                className="tabular"
                style={{ fontSize: 11.5, color: 'var(--fg-1)' }}
              >
                {data.total_rows_last_sync.toLocaleString('pt-PT')}
              </span>
            </InfoRow>
          </div>

          {/* Aviso de histórico em falta */}
          {data.sync_history_error && (
            <div
              className="flex items-start gap-2 rounded-md px-3 py-2.5"
              style={{
                background: 'var(--yellow-bg)',
                border: '1px solid var(--yellow-bd)',
              }}
            >
              <AlertTriangle size={13} className="text-yellow mt-0.5 shrink-0" />
              <span style={{ fontSize: 11.5, color: 'var(--fg-1)' }}>
                Não foi possível ler o histórico de sincronização
                (core.etl_run): {data.sync_history_error}.
              </span>
            </div>
          )}

          {/* Mirrors */}
          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-lg)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid var(--bd-1)',
                fontSize: 13,
                fontWeight: 600,
                color: 'var(--fg-0)',
              }}
            >
              Mirrors · última sync por tabela espelhada
            </div>
            {data.mirrors.length === 0 ? (
              <div className="py-8 text-center text-xs text-fg-3">
                Sem mirrors configuradas.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table
                  style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    minWidth: 720,
                  }}
                >
                  <thead>
                    <tr style={{ background: 'var(--bg-2)' }}>
                      <Th>Mirror</Th>
                      <Th>Estado</Th>
                      <Th align="right">Última sync</Th>
                      <Th align="right">Lidas</Th>
                      <Th align="right">Inseridas</Th>
                      <Th align="right">Atualizadas</Th>
                      <Th align="right">Ignoradas</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.mirrors.map((m) => (
                      <MirrorRow key={m.source} mirror={m} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <p className="text-[10px] text-fg-4">
            Amostrado em {fmtDate(data.sampled_at)} · atualização automática a
            cada 30 s.
          </p>
        </div>
      )}
    </DarkPageLayout>
  );
}

// ─── Bits visuais ────────────────────────────────────────────────────────────

function InfoRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="flex items-center justify-between gap-3 py-1.5"
      style={{ borderTop: '1px solid var(--bd-1)' }}
    >
      <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{label}</span>
      {children}
    </div>
  );
}

function Th({
  children,
  align = 'left',
}: {
  children: React.ReactNode;
  align?: 'left' | 'right';
}) {
  return (
    <th
      style={{
        padding: '9px 14px',
        textAlign: align,
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: 0.4,
        textTransform: 'uppercase',
        color: 'var(--fg-3)',
        borderBottom: '1px solid var(--bd-1)',
      }}
    >
      {children}
    </th>
  );
}

function MirrorRow({ mirror }: { mirror: ErpMirror }) {
  return (
    <tr style={{ borderBottom: '1px solid var(--bd-1)' }}>
      <td style={{ padding: '9px 14px' }}>
        <span
          className="font-mono"
          style={{ fontSize: 11.5, color: 'var(--fg-0)' }}
        >
          {mirror.source}
        </span>
        {mirror.error && (
          <div style={{ fontSize: 10, color: 'var(--red)', marginTop: 2 }}>
            {mirror.error}
          </div>
        )}
      </td>
      <td style={{ padding: '9px 14px' }}>
        <DarkBadge variant={mirrorBadgeVariant(mirror.status)}>
          {mirrorStatusLabel(mirror.status)}
        </DarkBadge>
      </td>
      <td
        className="tabular"
        style={{
          padding: '9px 14px',
          textAlign: 'right',
          fontSize: 11,
          color: 'var(--fg-2)',
        }}
      >
        {fmtDate(mirror.finished_at ?? mirror.last_run_at)}
      </td>
      {[
        mirror.rows_read,
        mirror.rows_inserted,
        mirror.rows_updated,
        mirror.rows_skipped,
      ].map((n, i) => (
        <td
          key={i}
          className="tabular"
          style={{
            padding: '9px 14px',
            textAlign: 'right',
            fontSize: 11.5,
            color: 'var(--fg-1)',
          }}
        >
          {n.toLocaleString('pt-PT')}
        </td>
      ))}
    </tr>
  );
}
