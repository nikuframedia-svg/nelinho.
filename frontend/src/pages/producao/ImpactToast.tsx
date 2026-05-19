/**
 * ImpactToast — toast efémero de impacto de uma acção (Q.52.F).
 *
 * Port fiel do `ImpactToast` do design NELO: surge no fundo ao centro,
 * mostra título + detalhe e o impacto € (verde/vermelho). Auto-fecha
 * em ~3,2 s. Dados por props — ZERO MOCKS.
 */

import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle, Check } from 'lucide-react';
import { fmtEuro } from '../painel/painelHelpers';

export interface ImpactToastData {
  title: string;
  detail: string;
  /** Impacto € — positivo verde, negativo vermelho, 0 neutro. */
  impact: number;
}

export interface ImpactToastProps {
  toast: ImpactToastData | null;
  onClose: () => void;
}

export function ImpactToast({ toast, onClose }: ImpactToastProps): ReactNode {
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(onClose, 3200);
    return () => clearTimeout(t);
  }, [toast, onClose]);

  if (!toast) return null;
  const isGood = toast.impact >= 0;

  return (
    <div
      role="status"
      style={{
        position: 'fixed',
        bottom: 24,
        left: '50%',
        transform: 'translateX(-50%)',
        padding: '12px 18px',
        background: 'rgba(18,18,22,0.96)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: `1px solid ${
          isGood ? 'var(--green-bd)' : 'var(--red-bd)'
        }`,
        borderRadius: 'var(--r-lg)',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        boxShadow: 'var(--shadow-3)',
        zIndex: 200,
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          background: isGood ? 'var(--green-bg)' : 'var(--red-bg)',
          display: 'grid',
          placeItems: 'center',
        }}
      >
        {isGood ? (
          <Check size={16} color="var(--green)" />
        ) : (
          <AlertTriangle size={16} color="var(--red)" />
        )}
      </div>
      <div>
        <div
          style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}
        >
          {toast.title}
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 2 }}>
          {toast.detail}
        </div>
      </div>
      {toast.impact !== 0 && (
        <div
          className="display tabular"
          style={{
            fontSize: 18,
            color: isGood ? 'var(--green)' : 'var(--red)',
            fontWeight: 600,
          }}
        >
          {toast.impact > 0 ? '+' : ''}
          {fmtEuro(toast.impact)}
        </div>
      )}
    </div>
  );
}
