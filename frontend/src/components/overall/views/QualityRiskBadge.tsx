/**
 * QualityRiskBadge — badge defensivo de risco de defeito (Q.115.L / Q.115.E).
 *
 * Faz fetch de GET /v1/quality/risk-preview.
 * Se o endpoint não existir (404) ou retornar null → não mostra nada.
 * Só aparece quando p_defect > 0.15.
 *
 * Q.144.E — fetch LAZY (só quando o badge entra no viewport). Sem isto, a
 * /overall renderiza ~1473 OpCards e dispara ~1473 pedidos `risk-preview` de uma
 * vez → o Chrome esgota sockets (`ERR_INSUFFICIENT_RESOURCES`) e essas falhas
 * abriam o circuit breaker GLOBAL, bloqueando a query crítica do plano →
 * "Erro ao carregar plano". Lazy-load corta para as ~poucas dezenas visíveis.
 */

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { qualityRiskApi } from '../../../lib/api/qualityApi';
import { qualityRiskKeys } from '../../../lib/api/keys';

interface Props {
  operatorId: string;
  boatId: string;
  phaseId: string;
}

export function QualityRiskBadge({ operatorId, boatId, phaseId }: Props): ReactNode {
  const anchorRef = useRef<HTMLSpanElement | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    if (inView) return;
    const el = anchorRef.current;
    // Sem IntersectionObserver (ex. jsdom/tests) → comporta-se como antes.
    if (!el || typeof IntersectionObserver === 'undefined') {
      setInView(true);
      return;
    }
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setInView(true);
          obs.disconnect();
        }
      },
      { rootMargin: '150px' },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [inView]);

  const { data } = useQuery({
    queryKey: qualityRiskKeys.preview(operatorId, boatId, phaseId),
    queryFn: () => qualityRiskApi.riskPreview({ operator_id: operatorId, boat_id: boatId, phase_id: phaseId }),
    enabled: inView && !!operatorId && !!boatId && !!phaseId,
    retry: false,
    staleTime: 60_000,
  });

  // Âncora sempre no DOM para o observer ter o que vigiar; 1px (não 0×0, que
  // não interseta) e invisível. Quando há risco real, o badge substitui-a.
  if (!data || data.p_defect <= 0.15) {
    return <span ref={anchorRef} aria-hidden className="inline-block w-px h-px opacity-0" />;
  }

  const pct = Math.round(data.p_defect * 100);

  return (
    <span
      ref={anchorRef}
      className="ml-1 text-[9px] font-semibold text-amber-400 flex-shrink-0"
      title={`Risco de defeito: ${pct}%`}
    >
      ⚠ {pct}%
    </span>
  );
}
