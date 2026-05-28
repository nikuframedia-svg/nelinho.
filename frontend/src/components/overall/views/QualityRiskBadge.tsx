/**
 * QualityRiskBadge — badge defensivo de risco de defeito (Q.115.L / Q.115.E).
 *
 * Faz fetch de GET /v1/quality/risk-preview.
 * Se o endpoint não existir (404) ou retornar null → não mostra nada.
 * Só aparece quando p_defect > 0.15.
 */

import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { qualityRiskApi } from '../../../lib/api/qualityApi';
import { qualityRiskKeys } from '../../../lib/api/keys';

interface Props {
  operatorId: string;
  boatId: string;
  phaseId: string;
}

export function QualityRiskBadge({ operatorId, boatId, phaseId }: Props): ReactNode {
  const { data } = useQuery({
    queryKey: qualityRiskKeys.preview(operatorId, boatId, phaseId),
    queryFn: () => qualityRiskApi.riskPreview({ operator_id: operatorId, boat_id: boatId, phase_id: phaseId }),
    enabled: !!operatorId && !!boatId && !!phaseId,
    retry: false,
    staleTime: 60_000,
  });

  if (!data || data.p_defect <= 0.15) return null;

  const pct = Math.round(data.p_defect * 100);

  return (
    <span
      className="ml-1 text-[9px] font-semibold text-amber-400 flex-shrink-0"
      title={`Risco de defeito: ${pct}%`}
    >
      ⚠ {pct}%
    </span>
  );
}
