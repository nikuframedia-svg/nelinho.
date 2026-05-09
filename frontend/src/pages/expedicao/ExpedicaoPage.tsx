/**
 * ExpedicaoPage — porto do nelo (1).zip pages-1.jsx:ExpedicaoPage.
 *
 * Pelo brief PROMPT_CLAUDE_CODE.md §3.4 ("não tocar — DispatchPage Q.2
 * está bem como está"), esta página apenas:
 *   1. Adiciona PageHeader PT-PT com Atualizar/Pedir-ao-Copilot
 *   2. Embebe o DispatchPage Q.2 existing (que já tem drag-drop entre
 *      expedições + RejectionDialog com categoria obrigatória)
 *   3. Migra a rota canónica de `/plan/dispatch` → `/expedicao`
 *
 * O zip mostra "3 rails verticais (Hoje/Amanhã/Semana)" mas o
 * DispatchPage actual já organiza expedições por data via
 * `transportApi.list({ horizon_days: 14 })`. O port preserva esse
 * comportamento — substituir o layout interno seria perder Q.2 work.
 *
 * Sprint Q.18.ZIP.E.
 */

import { lazy, Suspense } from 'react';
import { RefreshCw, Sparkles } from 'lucide-react';
import { PageHeader } from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';

const DispatchPage = lazy(() => import('../dispatch/DispatchPage'));

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

export default function ExpedicaoPage() {
  return (
    <div>
      <PageHeader
        title="Expedição"
        subtitle="LOTES DE TRANSPORTE · DRAG-DROP · CONFIRMAÇÃO COM IMPACTO"
        actions={
          <>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
            >
              <RefreshCw size={13} />
              Atualizar
            </button>
            <button
              type="button"
              onClick={() =>
                askCopilot('Como otimizar as expedições da próxima semana?')
              }
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-xs font-medium transition-colors"
            >
              <Sparkles size={13} />
              Pedir ao Copilot
            </button>
          </>
        }
      />
      <Suspense
        fallback={
          <div className="p-8">
            <SkeletonLoader count={5} />
          </div>
        }
      >
        <DispatchPage />
      </Suspense>
    </div>
  );
}
