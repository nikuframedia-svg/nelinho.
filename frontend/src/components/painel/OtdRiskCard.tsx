/**
 * OtdRiskCard — cartão "Encomendas em risco de atraso" (Q.54.L).
 *
 * Liga ao endpoint REAL `/v1/plan/orders/otd-risk` (Q.54.F): o
 * `OTDRiskModel` activo dá a P(atraso) de cada encomenda aberta. Barcos
 * de risco alto destacados a vermelho.
 *
 * ZERO MOCKS: quando ainda não há modelo treinado o backend devolve
 * `model_available=false` com uma `reason` honesta — mostramos essa
 * razão, nunca inventamos um número. Reutilizável no Painel e na Direção.
 */

import type { ReactNode } from 'react';
import { Clock, TimerOff } from 'lucide-react';
import { DarkBadge, DarkButton, EmptyState } from '../dark';
import type {
  OtdRiskBand,
  OtdRiskOrder,
  OtdRiskResponse,
} from '../../pages/painel/painelApi';

type BadgeVariant = 'danger' | 'warning' | 'success' | 'neutral';

const BAND_BADGE: Record<string, { variant: BadgeVariant; label: string }> = {
  alto: { variant: 'danger', label: 'Risco alto' },
  medio: { variant: 'warning', label: 'Risco médio' },
  baixo: { variant: 'success', label: 'Risco baixo' },
};

function bandBadge(band: OtdRiskBand): { variant: BadgeVariant; label: string } {
  return BAND_BADGE[band] ?? { variant: 'neutral', label: String(band) };
}

function fmtDate(iso: string | null): string {
  if (!iso) return 'sem data';
  return new Date(iso).toLocaleDateString('pt-PT', {
    day: '2-digit',
    month: '2-digit',
  });
}

export interface OtdRiskCardProps {
  query: {
    data: OtdRiskResponse | null;
    isLoading: boolean;
    isError: boolean;
  };
  onRetry: () => void;
  /** Limita as linhas mostradas (o resto fica num "+N"). */
  maxRows?: number;
}

export function OtdRiskCard({
  query,
  onRetry,
  maxRows = 8,
}: OtdRiskCardProps): ReactNode {
  const { data, isLoading, isError } = query;

  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding: 18,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 14,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Clock size={14} color="var(--fg-2)" />
          <div>
            <div
              style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}
            >
              Encomendas em risco de atraso
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              P(atraso) por encomenda — modelo OTD-risk
            </div>
          </div>
        </div>
        {data?.model_available &&
          typeof data.high_risk_count === 'number' && (
            <DarkBadge
              variant={data.high_risk_count > 0 ? 'danger' : 'success'}
              size="sm"
            >
              {data.high_risk_count} de risco alto
            </DarkBadge>
          )}
      </div>

      {isLoading ? (
        <div
          style={{
            fontSize: 12,
            color: 'var(--fg-3)',
            padding: '18px 0',
            textAlign: 'center',
          }}
        >
          A calcular o risco de atraso…
        </div>
      ) : isError ? (
        <EmptyState
          mascot={false}
          size="sm"
          title="Risco de atraso indisponível"
          hint="O serviço de risco de atraso não respondeu."
          action={
            <DarkButton size="sm" onClick={onRetry}>
              Tentar novamente
            </DarkButton>
          }
        />
      ) : !data || !data.model_available ? (
        <EmptyState
          mascot={false}
          size="sm"
          icon={<TimerOff size={24} />}
          title="Modelo de risco de atraso ainda não treinado"
          hint={
            data?.reason ??
            'Ainda não há histórico de entregas suficiente para treinar o modelo.'
          }
        />
      ) : data.orders.length === 0 ? (
        <EmptyState
          mascot={false}
          size="sm"
          title="Nenhuma encomenda em risco"
          hint="Todas as encomendas abertas estão dentro do prazo previsto."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          {data.orders.slice(0, maxRows).map((o) => (
            <OtdRiskRow key={o.of_id} order={o} />
          ))}
          {data.orders.length > maxRows && (
            <div
              style={{
                fontSize: 11,
                color: 'var(--fg-3)',
                textAlign: 'center',
                paddingTop: 4,
              }}
            >
              + {data.orders.length - maxRows} encomendas com risco mais baixo
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OtdRiskRow({ order }: { order: OtdRiskOrder }): ReactNode {
  const badge = bandBadge(order.risk_band);
  const isHigh = order.risk_band === 'alto';
  const pct = Math.round(order.late_probability * 100);
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 110px 96px 84px',
        alignItems: 'center',
        gap: 10,
        padding: '9px 11px',
        background: isHigh ? 'var(--bg-2)' : 'transparent',
        border: `1px solid ${isHigh ? 'var(--red)' : 'var(--bd-1)'}`,
        borderRadius: 'var(--r-md)',
        fontSize: 12,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            color: 'var(--fg-0)',
            fontWeight: 500,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={order.product_name ?? order.of_id}
        >
          {order.product_name ?? `Ordem ${order.of_id}`}
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>
          {order.current_phase_name ?? 'fase desconhecida'}
        </div>
      </div>
      <div style={{ justifySelf: 'start' }}>
        <DarkBadge variant={badge.variant} size="sm">
          {badge.label}
        </DarkBadge>
      </div>
      <span
        className="tabular"
        style={{
          textAlign: 'right',
          color: isHigh ? 'var(--red)' : 'var(--fg-1)',
          fontWeight: 600,
        }}
      >
        {pct}%
      </span>
      <span
        className="tabular"
        style={{ textAlign: 'right', color: 'var(--fg-2)', fontSize: 11 }}
      >
        {fmtDate(order.transport_date)}
      </span>
    </div>
  );
}

export default OtdRiskCard;
