/**
 * PainelAlertCard — cartão de alerta com barra lateral por severidade
 * + acções Confirmar / Resolver (Q.52.D).
 *
 * Reconstrói o `AlertCard` do protótipo NELO ligado ao endpoint real
 * `/v1/copilot/alerts`. As acções fazem mutate e o caller invalida a
 * query. Impacto € só aparece quando o `context` do alerta o traz.
 */

import type { ReactNode } from 'react';
import { Check, X } from 'lucide-react';
import { DarkBadge } from '../../components/dark';
import type { CopilotAlert } from './painelApi';
import { fmtEuro, severityLabel, severityTone } from './painelHelpers';

const TONE_VAR: Record<'danger' | 'warning' | 'info', string> = {
  danger: 'var(--red)',
  warning: 'var(--orange)',
  info: 'var(--blue)',
};

export interface PainelAlertCardProps {
  alert: CopilotAlert;
  /** Confirmar o alerta (active → acknowledged). */
  onAcknowledge: (id: string) => void;
  /** Resolver o alerta. */
  onResolve: (id: string) => void;
  /** True enquanto uma mutação deste alerta está em curso. */
  busy?: boolean;
}

function relativeWhen(iso: string | null): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return '—';
  const diffMin = Math.round((Date.now() - then) / 60000);
  if (diffMin < 1) return 'agora';
  if (diffMin < 60) return `há ${diffMin} min`;
  const h = Math.round(diffMin / 60);
  if (h < 24) return `há ${h}h`;
  return `há ${Math.round(h / 24)}d`;
}

function readImpact(context: Record<string, unknown>): number | null {
  for (const key of ['impact_eur', 'impacto_eur', 'cost_eur', 'impact']) {
    const v = context[key];
    if (typeof v === 'number' && v > 0) return v;
  }
  return null;
}

export function PainelAlertCard({
  alert,
  onAcknowledge,
  onResolve,
  busy = false,
}: PainelAlertCardProps): ReactNode {
  const tone = severityTone(alert.severity);
  const impact = readImpact(alert.context);
  const cause =
    typeof alert.context['cause'] === 'string'
      ? (alert.context['cause'] as string)
      : null;

  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderLeft: `3px solid ${TONE_VAR[tone]}`,
        borderRadius: 'var(--r-md)',
        padding: 14,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 6,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <DarkBadge variant={tone} size="sm">
            {severityLabel(alert.severity)}
          </DarkBadge>
          <span style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>
            {relativeWhen(alert.created_at)}
          </span>
        </div>
        {impact !== null && (
          <span style={{ fontSize: 11, color: 'var(--fg-2)' }}>
            Impacto{' '}
            <span style={{ color: 'var(--red)', fontWeight: 600 }}>
              −{fmtEuro(impact)}
            </span>
          </span>
        )}
      </div>

      <div
        style={{
          fontSize: 13,
          fontWeight: 500,
          color: 'var(--fg-0)',
          marginBottom: 3,
        }}
      >
        {alert.title}
      </div>
      <div style={{ fontSize: 12, color: 'var(--fg-2)', marginBottom: 6 }}>
        {alert.message_pt}
      </div>
      {cause && (
        <div
          style={{ fontSize: 11.5, color: 'var(--fg-3)', marginBottom: 10 }}
        >
          Causa: {cause}
        </div>
      )}

      <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
        <button
          type="button"
          disabled={busy}
          onClick={() => onAcknowledge(alert.id)}
          style={actionStyle('primary', busy)}
        >
          <Check size={12} />
          Confirmar
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onResolve(alert.id)}
          style={actionStyle('ghost', busy)}
        >
          <X size={12} />
          Resolver
        </button>
      </div>
    </div>
  );
}

function actionStyle(
  kind: 'primary' | 'ghost',
  disabled: boolean,
): React.CSSProperties {
  const base: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    padding: '4px 10px',
    height: 26,
    fontSize: 11.5,
    fontWeight: 500,
    borderRadius: 7,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    border: '1px solid transparent',
  };
  if (kind === 'primary') {
    return {
      ...base,
      background: 'var(--accent-bg)',
      color: 'var(--accent)',
      borderColor: 'var(--accent-bd)',
    };
  }
  return {
    ...base,
    background: 'var(--bg-2)',
    color: 'var(--fg-1)',
    borderColor: 'var(--bd-2)',
  };
}
