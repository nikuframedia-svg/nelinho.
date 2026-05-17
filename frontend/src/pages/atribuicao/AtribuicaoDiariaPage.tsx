/**
 * AtribuicaoDiariaPage — wrapper que delega para EquipaPage com tab=alocacoes.
 *
 * URL canónica zip: /atribuicao. Conteúdo da AlocacoesTab existing (2-col
 * Operadores 320px + Atribuições com WorkerRow + DispatchRow).
 *
 * Sprint Q.18.ZIP.shell.
 */

import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import EquipaPage from '../equipa/EquipaPage';

export default function AtribuicaoDiariaPage() {
  const [, setSearchParams] = useSearchParams();
  useEffect(() => {
    setSearchParams({ tab: 'alocacoes' }, { replace: true });
  }, [setSearchParams]);
  return <EquipaPage />;
}
