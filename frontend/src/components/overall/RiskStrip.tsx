/**
 * RiskStrip — faixa colapsável com os 4 risk panels (C3).
 *
 * Os painéis ficam SEMPRE montados (mantém data-testid intactos e evita
 * re-fetch ao expandir). Quando colapsada, apenas o resumo fica visível.
 */

import { useState, memo } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { OtdRiskPanel } from './OtdRiskPanel';
import { MoldHealthPanel } from './MoldHealthPanel';
import { ShortageRiskPanel } from './ShortageRiskPanel';

export const RiskStrip = memo(function RiskStrip() {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="rounded-xl border overflow-hidden"
      style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)' }}
    >
      {/* Cabeçalho colapsável */}
      <button
        className="flex items-center gap-2 w-full px-3 py-2 text-left transition-colors hover:opacity-80"
        style={{ background: 'var(--bg-3)' }}
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        {expanded ? (
          <ChevronDown size={13} style={{ color: 'var(--fg-3)' }} />
        ) : (
          <ChevronRight size={13} style={{ color: 'var(--fg-3)' }} />
        )}
        <span className="text-xs font-semibold" style={{ color: 'var(--fg-2)' }}>
          Riscos operacionais
        </span>
        {!expanded && (
          <span className="text-[10px]" style={{ color: 'var(--fg-4)' }}>
            OTD · Moldes · Stocks
          </span>
        )}
      </button>

      {/* Painéis — sempre montados, visibilidade controlada por CSS */}
      <div className={expanded ? 'block p-3 space-y-2' : 'hidden'}>
        <OtdRiskPanel />
        <MoldHealthPanel />
        <ShortageRiskPanel />
      </div>
    </div>
  );
});
