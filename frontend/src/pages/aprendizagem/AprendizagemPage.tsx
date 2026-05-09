/**
 * AprendizagemPage — "O que aprendi" do zip page-extra.jsx PageLearning.
 *
 * URL canónica zip: /aprendizagem. Conteúdo: regras aprendidas + pesos
 * fitness side-by-side. Sub-tabs Regras Q.17 NL→DSL + Aprendidas Camada 1
 * preservadas como sub-tabs avançadas.
 *
 * Wraps ConfiguracaoPage com tab=aprendizagem selecionada.
 *
 * Sprint Q.18.ZIP.shell.
 */

import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import ConfiguracaoPage from '../configuracao/ConfiguracaoPage';

export default function AprendizagemPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    if (!searchParams.get('tab')) {
      setSearchParams({ tab: 'aprendizagem' }, { replace: true });
    }
  }, [searchParams, setSearchParams]);
  return <ConfiguracaoPage />;
}
