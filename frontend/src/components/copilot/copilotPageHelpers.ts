/**
 * copilotPageHelpers — modos e tipos da página /copilot (Q.52.N).
 *
 * Os "modos" são o enquadramento que o protótipo NELO dá à conversa
 * (factual / cenário / diagnóstico / CTP / relatório). Não há enum de
 * modo no backend — o `POST /api/copilot/ask` decide o `intent`
 * server-side. O modo aqui é só um prefixo de contexto que ajuda o
 * utilizador a saber o que esperar e que afina o placeholder do input.
 */

import type { ReactNode } from 'react';
import { Info, FlaskConical, Brain, Target, Download } from 'lucide-react';
import { createElement } from 'react';

export type CopilotMode = 'factual' | 'scenario' | 'diagnostic' | 'ctp' | 'report';

export interface CopilotModeDef {
  id: CopilotMode;
  label: string;
  hint: string;
  icon: ReactNode;
}

export const COPILOT_MODES: CopilotModeDef[] = [
  {
    id: 'factual',
    label: 'Factuais',
    hint: 'Pergunta sobre o estado actual',
    icon: createElement(Info, { size: 12 }),
  },
  {
    id: 'scenario',
    label: 'Cenários',
    hint: '"E se…" — corre uma simulação',
    icon: createElement(FlaskConical, { size: 12 }),
  },
  {
    id: 'diagnostic',
    label: 'Diagnóstico',
    hint: 'Causa raiz de um problema',
    icon: createElement(Brain, { size: 12 }),
  },
  {
    id: 'ctp',
    label: 'CTP',
    hint: 'Capable to Promise — data viável de entrega',
    icon: createElement(Target, { size: 12 }),
  },
  {
    id: 'report',
    label: 'Relatórios',
    hint: 'Exporta um resumo PDF/CSV',
    icon: createElement(Download, { size: 12 }),
  },
];

/**
 * `CopilotResponseWithCharts` — Q.53.L.
 *
 * O backend (Q.53.F) acrescentou `charts: ChartSpec[]` à `CopilotResponse`
 * mas o tipo partilhado em `lib/copilot-types.ts` (off-limits neste
 * sub-sprint) ainda não o declara. Estendemo-lo localmente para a UI do
 * copiloto poder ler os gráficos com type-safety, sem `any`.
 */
export type CopilotResponseWithCharts =
  import('../../lib/copilot-types').CopilotResponse & {
    charts?: import('./CopilotChart').ChartSpec[];
  };

/** Mensagem de UI — `user` é o que foi escrito; `copilot` carrega a resposta rica. */
export interface ChatMessage {
  id: string;
  role: 'user' | 'copilot';
  text: string;
  when: string;
  /** Resposta estruturada do copiloto (factos/citações/acções/avisos/gráficos). */
  response?: CopilotResponseWithCharts;
  /** True enquanto o copiloto "escreve" (pré-resposta). */
  typing?: boolean;
}

export const WARNING_LABELS: Record<string, string> = {
  INSUFFICIENT_EVIDENCE: 'Evidência insuficiente',
  SECURITY_FLAG: 'Sinal de segurança',
  LOW_TRUST_INDEX: 'Índice de confiança baixo',
  MODEL_OFFLINE: 'Modelo offline',
  VALIDATION_FAILED: 'Validação falhou',
  SERVICE_ERROR: 'Erro de serviço',
};

export function nowLabel(): string {
  return new Date().toLocaleTimeString('pt-PT', {
    hour: '2-digit',
    minute: '2-digit',
  });
}
