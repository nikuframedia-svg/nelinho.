/**
 * ConsequenceBox — coração do modo consultivo: o sistema mostra o que
 * acontece se aceitar vs se rejeitar uma sugestão.
 *
 * Port fiel do atom `ConsequenceBox` do design NELO.html (atoms.jsx).
 * Grelha 2 colunas (Se aceitar / Se rejeitar), bloco de alternativa
 * opcional, campo de razão livre (alimenta a aprendizagem) e a fila de
 * ações Aceitar / Rejeitar / Alternativa.
 *
 * Distinto do `ConsequenceBlock` legacy — este bate certo com a
 * geometria do protótipo NELO. Dados sempre por props (ZERO MOCKS).
 *
 * Sprint Q.52.B.
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { Check, X, Sparkles } from 'lucide-react';
import { formatCurrency } from '../../lib/utils';

export interface ConsequenceAlternative {
  label: string;
  detail: string;
}

export interface ConsequenceBoxProps {
  /** Consequências de aceitar — string única ou lista. */
  ifAccept: string | string[];
  /** Consequências de rejeitar — string única ou lista. */
  ifReject: string | string[];
  /** Sugestão alternativa opcional. */
  alternative?: ConsequenceAlternative;
  /** Fonte da sugestão (ex: "CPO · MAP-Elites"). */
  source?: string;
  /** Confiança 0-100. */
  confidence?: number;
  /** Impacto em € (mostrado se > 0). */
  impact?: number;
  /** Callback ao aceitar — recebe a razão escrita pelo utilizador. */
  onAccept?: (reason: string) => void;
  /** Callback ao rejeitar. */
  onReject?: (reason: string) => void;
  /** Callback ao escolher a alternativa. */
  onAlternative?: (reason: string) => void;
}

function asList(v: string | string[]): string[] {
  return Array.isArray(v) ? v : [v];
}

export function ConsequenceBox({
  ifAccept,
  ifReject,
  alternative,
  source,
  confidence,
  impact,
  onAccept,
  onReject,
  onAlternative,
}: ConsequenceBoxProps): ReactNode {
  const [reason, setReason] = useState('');
  const accList = asList(ifAccept);
  const rejList = asList(ifReject);

  return (
    <div
      style={{
        border: '1px solid var(--bd-2)',
        borderRadius: 'var(--r-lg)',
        background: 'var(--bg-1)',
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
        {/* Se aceitar */}
        <div
          style={{
            padding: 14,
            borderRight: '1px solid var(--bd-1)',
            background: 'var(--green-bg)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 8,
            }}
          >
            <Check size={13} color="var(--green)" />
            <span
              style={{
                fontSize: 10.5,
                textTransform: 'uppercase',
                letterSpacing: 0.6,
                fontWeight: 600,
                color: 'var(--green)',
              }}
            >
              Se aceitar
            </span>
          </div>
          <ul
            style={{
              margin: 0,
              paddingLeft: 16,
              color: 'var(--fg-1)',
              fontSize: 12.5,
              lineHeight: 1.6,
            }}
          >
            {accList.map((s, i) => (
              <li key={i} style={{ marginBottom: 3 }}>
                {s}
              </li>
            ))}
          </ul>
        </div>

        {/* Se rejeitar */}
        <div style={{ padding: 14, background: 'var(--red-bg)' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 8,
            }}
          >
            <X size={13} color="var(--red)" />
            <span
              style={{
                fontSize: 10.5,
                textTransform: 'uppercase',
                letterSpacing: 0.6,
                fontWeight: 600,
                color: 'var(--red)',
              }}
            >
              Se rejeitar
            </span>
          </div>
          <ul
            style={{
              margin: 0,
              paddingLeft: 16,
              color: 'var(--fg-1)',
              fontSize: 12.5,
              lineHeight: 1.6,
            }}
          >
            {rejList.map((s, i) => (
              <li key={i} style={{ marginBottom: 3 }}>
                {s}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {alternative ? (
        <div
          style={{
            padding: '11px 14px',
            background: 'var(--blue-bg)',
            borderTop: '1px solid var(--bd-1)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 4,
            }}
          >
            <Sparkles size={12} color="var(--blue)" />
            <span
              style={{
                fontSize: 10.5,
                textTransform: 'uppercase',
                letterSpacing: 0.6,
                fontWeight: 600,
                color: 'var(--blue)',
              }}
            >
              Alternativa
            </span>
          </div>
          <div
            style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}
          >
            {alternative.label}
          </div>
          <div
            style={{ fontSize: 11.5, color: 'var(--fg-2)', marginTop: 2 }}
          >
            {alternative.detail}
          </div>
        </div>
      ) : null}

      <div
        style={{
          padding: '12px 14px',
          background: 'var(--bg-2)',
          borderTop: '1px solid var(--bd-1)',
        }}
      >
        <div style={{ marginBottom: 10 }}>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Porquê esta decisão? (ajuda o sistema a aprender)"
            className="text-slate-900 placeholder:text-slate-400"
            style={{
              width: '100%',
              padding: '7px 10px',
              background: 'var(--bg-0)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-sm)',
              color: 'var(--fg-0)',
              outline: 'none',
              fontSize: 12,
              transition: 'border-color 0.15s',
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = 'var(--accent)';
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = 'var(--bd-1)';
            }}
          />
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 10,
            flexWrap: 'wrap',
          }}
        >
          <div
            style={{
              fontSize: 10.5,
              color: 'var(--fg-3)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              flexWrap: 'wrap',
            }}
          >
            {source ? <span>{source}</span> : null}
            {confidence !== undefined ? (
              <>
                <span style={{ color: 'var(--fg-4)' }}>·</span>
                <span>
                  Confiança{' '}
                  <span style={{ color: 'var(--fg-1)' }}>{confidence}%</span>
                </span>
              </>
            ) : null}
            {impact !== undefined && impact > 0 ? (
              <>
                <span style={{ color: 'var(--fg-4)' }}>·</span>
                <span style={{ color: 'var(--green)' }}>
                  Impacto {formatCurrency(impact)}
                </span>
              </>
            ) : null}
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {alternative && onAlternative ? (
              <button
                type="button"
                onClick={() => onAlternative(reason)}
                style={btnStyle('tonal-blue')}
              >
                Alternativa
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => onReject?.(reason)}
              style={btnStyle('secondary')}
            >
              <X size={12} />
              Rejeitar
            </button>
            <button
              type="button"
              onClick={() => onAccept?.(reason)}
              style={btnStyle('primary-green')}
            >
              <Check size={12} />
              Aceitar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

type BtnKind = 'tonal-blue' | 'secondary' | 'primary-green';

function btnStyle(kind: BtnKind): React.CSSProperties {
  const base: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    padding: '4px 9px',
    height: 26,
    fontSize: 11.5,
    fontWeight: 500,
    borderRadius: 7,
    cursor: 'pointer',
    border: '1px solid transparent',
    whiteSpace: 'nowrap',
  };
  if (kind === 'tonal-blue') {
    return {
      ...base,
      background: 'var(--blue-bg)',
      color: 'var(--blue)',
      borderColor: 'var(--blue-bd)',
    };
  }
  if (kind === 'primary-green') {
    return {
      ...base,
      background: 'var(--green)',
      color: '#fff',
    };
  }
  return {
    ...base,
    background: 'var(--bg-2)',
    color: 'var(--fg-0)',
    borderColor: 'var(--bd-2)',
  };
}
