/**
 * SimulacoesTab — aba Simulações das Decisões (Q.118.B base; enriquecida em Q.118.E).
 * ====================================================================================
 *
 * Q.118.B: reutiliza directamente a SimulacoesPage existente (Histórico de
 * cenários twin + "Crise · agora"), já 100% funcional e ligada ao digital twin.
 * Q.118.E acrescenta a secção "Esta decisão" (what-if da decisão seleccionada:
 * sandbox_result + margin preview + "Simular no twin").
 *
 * ZERO MOCKS — toda a simulação corre no twin real.
 */

import SimulacoesPage from '../simulacoes/SimulacoesPage';

export default function SimulacoesTab() {
  return <SimulacoesPage />;
}
