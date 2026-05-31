/**
 * DecisionCard — um cartão de decisão (Q.121.C).
 * ================================================
 *
 * Extraído do DecidirTab (era um hub Tinder de 1 cartão) para se poder
 * renderizar VÁRIAS decisões ao mesmo tempo numa grelha. Estética idêntica:
 * badges de metadata, título, porquê, entidades clicáveis, cartão-hub,
 * consequências (Se aceitar / Se rejeitar) e botões Sim · Não por cartão.
 *
 * As mutações são por-id (o pai passa onApprove/onReject(decision.id)).
 */
import { Check, X } from 'lucide-react';
import type { DecisionRun } from '../../lib/api';
import { DecisionEntities } from './decisionEntities';
import { DecisionHubActions } from './DecisionHubActions';

function sourceLabel(source: string | undefined): string {
  if (!source) return '';
  const map: Record<string, string> = {
    auto: 'Auto-proposto',
    manual: 'Manual',
    cpo: 'CPO',
    copilot: 'Copilot',
  };
  return map[source.toLowerCase()] ?? source;
}

const BADGE: React.CSSProperties = {
  fontSize: 11,
  padding: '2px 8px',
  borderRadius: 99,
  fontWeight: 500,
};

export function DecisionCard({
  decision,
  onApprove,
  onReject,
  isPending,
  canWrite = true,
}: {
  decision: DecisionRun;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  isPending: boolean;
  /** false quando o utilizador está em modo read-only (ex: vista CEO). */
  canWrite?: boolean;
}) {
  const sb = (decision.sandbox_result ?? {}) as {
    confidence?: number;
    source?: string;
    if_accept?: string[];
    if_reject?: string[];
    why?: string;
    quality_risk?: string | null;
    cost_delta?: number | null;
  };
  const confidence = sb.confidence;
  // Q.121.5 — só mostrar a fonte quando há um rótulo real (auto/cpo/manual/…);
  // a lista slim não traz sandbox_result, e cair para proposed_by mostrava um
  // UUID cru no badge. Sem source → sem badge (o action_type já dá o contexto).
  const source = sb.source;
  const ifAccept = sb.if_accept;
  const ifReject = sb.if_reject;
  const why = sb.why;
  const qualityRisk = sb.quality_risk ?? null;
  const costDelta = sb.cost_delta ?? null;

  return (
    <div
      style={{
        width: '100%',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-xl)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div style={{ padding: '20px 20px 16px' }}>
        {/* badges de metadata */}
        <div className="flex flex-wrap gap-2 mb-3">
          {confidence != null ? (
            <span style={{ ...BADGE, background: 'var(--blue-bg)', color: 'var(--blue)', border: '1px solid var(--blue-bd)' }}>
              Confiança {confidence}%
            </span>
          ) : null}
          {source ? (
            <span style={{ ...BADGE, background: 'var(--bg-2)', color: 'var(--fg-2)', border: '1px solid var(--bd-2)' }}>
              {sourceLabel(source)}
            </span>
          ) : null}
          {qualityRisk != null ? (
            <span style={{ ...BADGE, background: 'var(--red-bg)', color: 'var(--red)', border: '1px solid var(--red-bd)' }}>
              Risco qualidade: {qualityRisk}
            </span>
          ) : null}
          {costDelta != null ? (
            <span
              style={{
                ...BADGE,
                background: costDelta >= 0 ? 'var(--green-bg)' : 'var(--red-bg)',
                color: costDelta >= 0 ? 'var(--green)' : 'var(--red)',
                border: `1px solid ${costDelta >= 0 ? 'var(--green-bd)' : 'var(--red-bd)'}`,
              }}
            >
              {costDelta >= 0 ? '+' : ''}
              {costDelta.toFixed(0)} €
            </span>
          ) : null}
        </div>

        {/* título */}
        <h2 className="text-text-dark-primary font-bold" style={{ fontSize: 20, lineHeight: 1.3 }}>
          {decision.title ?? '(Sem título)'}
        </h2>

        {/* porquê */}
        {why ? (
          <p className="text-text-dark-secondary mt-2" style={{ fontSize: 13, lineHeight: 1.5 }}>
            {why}
          </p>
        ) : null}

        {/* entidades clicáveis (encomenda/fase/operador) */}
        <DecisionEntities decision={decision} />

        {/* cartão-hub: ligações a plano/€/explicar */}
        <DecisionHubActions decision={decision} />
      </div>

      {/* consequências (Se aceitar / Se rejeitar) */}
      {(ifAccept && ifAccept.length > 0) || (ifReject && ifReject.length > 0) ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderTop: '1px solid var(--bd-1)' }}>
          {ifAccept && ifAccept.length > 0 ? (
            <div style={{ padding: '12px 16px', background: 'var(--green-bg)', borderRight: '1px solid var(--bd-1)' }}>
              <div className="uppercase font-semibold mb-2" style={{ fontSize: 10, letterSpacing: '0.5px', color: 'var(--green)' }}>
                Se aceitar
              </div>
              <ul style={{ margin: 0, paddingLeft: 14, color: 'var(--fg-1)', fontSize: 12, lineHeight: 1.6 }}>
                {ifAccept.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            </div>
          ) : (
            <div />
          )}
          {ifReject && ifReject.length > 0 ? (
            <div style={{ padding: '12px 16px', background: 'var(--red-bg)' }}>
              <div className="uppercase font-semibold mb-2" style={{ fontSize: 10, letterSpacing: '0.5px', color: 'var(--red)' }}>
                Se rejeitar
              </div>
              <ul style={{ margin: 0, paddingLeft: 14, color: 'var(--fg-1)', fontSize: 12, lineHeight: 1.6 }}>
                {ifReject.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            </div>
          ) : (
            <div />
          )}
        </div>
      ) : null}

      {/* botões Sim / Não (por-cartão) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderTop: '1px solid var(--bd-1)', minHeight: 56, marginTop: 'auto' }}>
        <button
          type="button"
          onClick={() => canWrite && onReject(decision.id)}
          disabled={isPending || !canWrite}
          aria-label={`Rejeitar decisão: ${decision.title ?? ''}`}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, minHeight: 56,
            background: 'var(--red-bg)', color: 'var(--red)', border: 'none', borderRight: '1px solid var(--bd-1)',
            cursor: (isPending || !canWrite) ? 'not-allowed' : 'pointer', opacity: (isPending || !canWrite) ? 0.4 : 1,
            fontSize: 15, fontWeight: 600, transition: 'background 0.12s',
          }}
          onMouseEnter={(e) => { if (!isPending && canWrite) e.currentTarget.style.background = 'var(--red)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--red-bg)'; }}
        >
          <X size={18} />
          Não
        </button>
        <button
          type="button"
          onClick={() => canWrite && onApprove(decision.id)}
          disabled={isPending || !canWrite}
          aria-label={`Aprovar decisão: ${decision.title ?? ''}`}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, minHeight: 56,
            background: 'var(--green-bg)', color: 'var(--green)', border: 'none',
            cursor: (isPending || !canWrite) ? 'not-allowed' : 'pointer', opacity: (isPending || !canWrite) ? 0.4 : 1,
            fontSize: 15, fontWeight: 600, transition: 'background 0.12s',
          }}
          onMouseEnter={(e) => { if (!isPending && canWrite) e.currentTarget.style.background = 'var(--green)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--green-bg)'; }}
        >
          <Check size={18} />
          Sim
        </button>
      </div>
    </div>
  );
}
