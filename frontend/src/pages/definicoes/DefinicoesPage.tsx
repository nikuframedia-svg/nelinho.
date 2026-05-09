/**
 * DefinicoesPage — "Definições" do zip page-extra.jsx PageSettings.
 *
 * URL canónica zip: /definicoes. Conteúdo: Geral wrap SettingsPage + sub-tabs
 * preservadas (Trust/Acessos/Auditoria/Sistema/Dados Mestre — killer).
 *
 * Wraps ConfiguracaoPage com tab=geral selecionada.
 *
 * Sprint Q.18.ZIP.shell.
 */

import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import ConfiguracaoPage from '../configuracao/ConfiguracaoPage';

export default function DefinicoesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    if (!searchParams.get('tab')) {
      setSearchParams({ tab: 'geral' }, { replace: true });
    }
  }, [searchParams, setSearchParams]);
  return <ConfiguracaoPage />;
}
