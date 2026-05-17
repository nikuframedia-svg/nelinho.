/**
 * PlanoProducaoPage — wrapper que delega para ProducaoPage existing.
 *
 * URL canónica do zip: /plano-producao (era /producao no frontend antigo).
 * Conteúdo: 3 vistas (Por fase / Gantt / Calendário) + legenda + 11 colunas.
 *
 * Sprint Q.18.ZIP.shell.
 */

import ProducaoPage from '../producao/ProducaoPage';

export default function PlanoProducaoPage() {
  return <ProducaoPage />;
}
