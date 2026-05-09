/**
 * OperadoresPage — wrap EquipaPage com tab=lista (port literal page-workforce.jsx).
 *
 * URL canónica zip: /operadores. Conteúdo: explainer + 4 KPI strip + tabela
 * 8 cols (Avatar+name/Tier/Score/Err%/Ops/Skill/Estado/Chevron). Sub-tabs
 * Risco/Simulador/Formação preservadas (killer features).
 *
 * Sprint Q.18.ZIP.shell.
 */

import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import EquipaPage from '../equipa/EquipaPage';

export default function OperadoresPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    if (!searchParams.get('tab')) {
      setSearchParams({ tab: 'lista' }, { replace: true });
    }
  }, [searchParams, setSearchParams]);
  return <EquipaPage />;
}
