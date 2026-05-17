/**
 * OEEPage — standalone OEE page (port literal de page-oee.jsx).
 *
 * URL canónica zip: /oee. Conteúdo: Explainer "O que é OEE?" + OEE Global
 * 78,4% + sparkline 14d + 3 breakdown cards (Disp/Perf/Qual) + Throughput
 * SVG line chart + Impacto financeiro 4 rows.
 *
 * Wraps QualidadePage com tab=oee selecionada.
 *
 * Sprint Q.18.ZIP.shell.
 */

import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import QualidadePage from '../qualidade/QualidadePage';

export default function OEEPage() {
  const [, setSearchParams] = useSearchParams();
  useEffect(() => {
    setSearchParams({ tab: 'oee' }, { replace: true });
  }, [setSearchParams]);
  return <QualidadePage />;
}
