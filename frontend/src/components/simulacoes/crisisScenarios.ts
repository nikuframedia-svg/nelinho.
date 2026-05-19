/**
 * Cenários de crise pré-definidos da tab "Crise · agora".
 * =======================================================
 *
 * Isto é CONFIGURAÇÃO, não dados mock: cada cenário descreve um
 * problema de produção e o(s) delta(s) a aplicar no digital twin.
 * Quando o utilizador corre um cenário, o frontend cria um
 * `twin/scenario` real (`POST /v1/twin/scenarios`), aplica os deltas
 * (`POST .../apply-delta`) e simula (`POST .../simulate`). O resultado
 * (€, dias, cascata, axiomas) vem do backend — nada é inventado.
 *
 * Os `deltas` seguem o contrato `DeltaApplyRequest` do twin:
 *   { entity_type, entity_key, patch, description }
 *
 * Sprint Q.52.M.
 */

import type { Tone } from './atoms';

export interface CrisisDelta {
  entity_type: string;
  entity_key: string;
  patch: Record<string, unknown>;
  description: string;
}

export interface CrisisCascadeStep {
  /** Momento relativo (ex: "+30min", "+1 dia"). */
  t: string;
  /** O que acontece nesse momento. */
  what: string;
  /** Tom de severidade do passo. */
  tone: Tone;
}

export interface CrisisOption {
  letter: 'A' | 'B' | 'C';
  label: string;
  detail: string;
  /** Custo legível (ex: "+€480", "€0", "−€4.500"). */
  cost: string;
  tone: Tone;
  recommended: boolean;
}

export interface CrisisScenario {
  id: string;
  /** Nome do ícone lucide-react a usar. */
  icon:
    | 'Box'
    | 'User'
    | 'Boxes'
    | 'AlertTriangle'
    | 'Zap'
    | 'Truck';
  label: string;
  severity: 'critical' | 'high' | 'medium';
  detail: string;
  /** Título do twin scenario criado. */
  scenarioTitle: string;
  /** Deltas aplicados ao twin (contrato DeltaApplyRequest). */
  deltas: CrisisDelta[];
  cascade: CrisisCascadeStep[];
  /** Custo de não fazer nada (€, negativo). */
  deltaEur: number;
  /** Atraso em dias se nada for feito. */
  deltaDays: number;
  options: CrisisOption[];
}

export const CRISIS_SCENARIOS: CrisisScenario[] = [
  {
    id: 'mold_break',
    icon: 'Box',
    label: 'Molde parte',
    severity: 'critical',
    detail:
      'Molde K1 7 ML (03) parte durante laminagem · indisponível 7 dias',
    scenarioTitle: 'Crise · molde K1 7 ML (03) parte',
    deltas: [
      {
        entity_type: 'mold',
        entity_key: 'K1-7ML-03',
        patch: { available: false, unavailable_days: 7 },
        description: 'Molde indisponível 7 dias (rotura em laminagem)',
      },
    ],
    cascade: [
      { t: '+0min', what: 'Laminagem #4274 interrompida', tone: 'red' },
      {
        t: '+30min',
        what: 'Limpeza de emergência · barco para retrabalho',
        tone: 'red',
      },
      { t: '+2h', what: '6 K1 em fila perdem slot', tone: 'orange' },
      {
        t: '+1 dia',
        what: 'K1 7 ML (02) em sobrecarga · fila +2 dias',
        tone: 'orange',
      },
      {
        t: '+3 dias',
        what: 'Fed. Francesa 15/06 em risco crítico',
        tone: 'red',
      },
    ],
    deltaEur: -3200,
    deltaDays: 4,
    options: [
      {
        letter: 'A',
        label: 'Reroute 6 K1 para molde 7 ML (02)',
        detail: '+2h por barco · fila cresce 12h',
        cost: '+€480',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'B',
        label: 'Subcontratar reparação 24h',
        detail: 'Especialista externo · molde volta em 18h',
        cost: '+€1.200',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'C',
        label: 'Aceitar atraso de 7d na Fed. Francesa',
        detail: 'Comunicar agora · penalização €4.500',
        cost: '−€4.500',
        tone: 'red',
        recommended: false,
      },
    ],
  },
  {
    id: 'worker_out',
    icon: 'User',
    label: 'Falta operador',
    severity: 'high',
    detail:
      'Operador principal de Laminagem K1 doente · 3 dias de ausência',
    scenarioTitle: 'Crise · ausência de laminador K1',
    deltas: [
      {
        entity_type: 'employee',
        entity_key: 'laminador-k1-principal',
        patch: { available: false, absent_days: 3, phase: 'Laminagem' },
        description: 'Laminador K1 ausente 3 dias (baixa médica)',
      },
    ],
    cascade: [
      {
        t: 'agora',
        what: 'Par de laminagem quebrado · K1 sem operador master',
        tone: 'red',
      },
      {
        t: '+1 dia',
        what: 'Substituto tier <5m · risco de erro +14pp',
        tone: 'orange',
      },
      {
        t: '+2 dias',
        what: '2 K1 com retrabalho previsto',
        tone: 'yellow',
      },
      {
        t: '+3 dias',
        what: 'Operador regressa · normal restabelecido',
        tone: 'green',
      },
    ],
    deltaEur: -480,
    deltaDays: 0.5,
    options: [
      {
        letter: 'A',
        label: 'Substituto sob supervisão de operadora sénior',
        detail: 'Mais lento mas seguro · sem retrabalho extra',
        cost: '+€140',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'B',
        label: 'Concentrar séniores só nos K1 críticos',
        detail: 'K2 atrasa mas o crítico fica coberto',
        cost: '€0',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'C',
        label: 'Convocar operador da Colagem',
        detail: 'Skill transferível · Colagem fica curta',
        cost: '+€60',
        tone: 'yellow',
        recommended: false,
      },
    ],
  },
  {
    id: 'material_out',
    icon: 'Boxes',
    label: 'Material esgota',
    severity: 'high',
    detail: 'Gelcoat branco esgotou · próxima entrega só daqui a 3 dias',
    scenarioTitle: 'Crise · rotura de gelcoat branco',
    deltas: [
      {
        entity_type: 'material',
        entity_key: 'gelcoat-branco',
        patch: { stock_qty: 0, next_delivery_days: 3 },
        description: 'Gelcoat branco em rotura · entrega em 3 dias',
      },
    ],
    cascade: [
      { t: 'agora', what: '8L disponíveis · acaba em ~12h', tone: 'red' },
      {
        t: '+12h',
        what: 'K1 #4271 e K2 #5103 param antes da Pintura',
        tone: 'red',
      },
      {
        t: '+1 dia',
        what: '2 barcos sem gelcoat · backlog 36h',
        tone: 'orange',
      },
      {
        t: '+3 dias',
        what: 'Entrega do fornecedor · recuperação 24h',
        tone: 'green',
      },
    ],
    deltaEur: -540,
    deltaDays: 1.5,
    options: [
      {
        letter: 'A',
        label: 'Encomenda urgente · fornecedor em 24h',
        detail: '€240 de sobretaxa · chega amanhã às 12h',
        cost: '+€240',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'B',
        label: 'Avançar lixagem antes da pintura',
        detail: 'Reordenar fases · poupa tempo morto',
        cost: '€0',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'C',
        label: 'Substituir por gelcoat off-white',
        detail: 'Cliente privado pode aceitar a variação',
        cost: '€0',
        tone: 'orange',
        recommended: false,
      },
    ],
  },
  {
    id: 'defect_spike',
    icon: 'AlertTriangle',
    label: 'Pico de defeitos',
    severity: 'critical',
    detail: 'Lote de resina com 8 defeitos em 5 dias (baseline: 2)',
    scenarioTitle: 'Crise · pico de defeitos no lote de resina',
    deltas: [
      {
        entity_type: 'material_lot',
        entity_key: 'resina-lote-suspeito',
        patch: { defect_rate: 0.23, baseline_defect_rate: 0.06 },
        description: 'Lote de resina com taxa de defeito 23% (3.8× baseline)',
      },
    ],
    cascade: [
      {
        t: 'agora',
        what: '3 fases afectadas: Laminagem, Gelcoat, Pintura',
        tone: 'red',
      },
      {
        t: '+2h',
        what: 'QualityRiskModel a re-pontuar · risco médio +12pp',
        tone: 'orange',
      },
      {
        t: '+6h',
        what: '14 barcos com risco preditivo >25%',
        tone: 'red',
      },
      {
        t: '+1 dia',
        what: 'Se mantido · €2.400 de retrabalho por dia',
        tone: 'red',
      },
    ],
    deltaEur: -1620,
    deltaDays: 2,
    options: [
      {
        letter: 'A',
        label: 'Bloquear lote · usar lote anterior em stock',
        detail: 'Stock chega para 3 dias · zero defeito esperado',
        cost: '€0',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'B',
        label: 'Contactar fornecedor · análise do lote',
        detail: 'Suspende encomendas até resposta · 48h',
        cost: '€0',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'C',
        label: 'Aceitar retrabalho · ajustar parâmetros',
        detail: '+15min de cura · 8% mais resina',
        cost: '+€180',
        tone: 'orange',
        recommended: false,
      },
    ],
  },
  {
    id: 'power_out',
    icon: 'Zap',
    label: 'Falha eléctrica',
    severity: 'critical',
    detail: 'Falha geral · estufas de cura desligadas · 12 barcos em cura',
    scenarioTitle: 'Crise · falha eléctrica nas estufas de cura',
    deltas: [
      {
        entity_type: 'facility',
        entity_key: 'estufas-cura',
        patch: { powered: false, boats_in_curing: 12 },
        description: 'Estufas de cura sem energia · 12 barcos em cura activa',
      },
    ],
    cascade: [
      {
        t: '+0min',
        what: 'Temperatura cai 0.8°C/h · 16 transições químicas em risco',
        tone: 'red',
      },
      {
        t: '+30min',
        what: 'Gerador entra · estufa 1 e 2 OK',
        tone: 'orange',
      },
      {
        t: '+1h',
        what: 'Sem energia, todos os 12 barcos ficam invalidados',
        tone: 'red',
      },
      {
        t: '+2h',
        what: 'Restauro de energia · análise lote-a-lote',
        tone: 'yellow',
      },
    ],
    deltaEur: -8400,
    deltaDays: 2,
    options: [
      {
        letter: 'A',
        label: 'Gerador imediato · prioridade às estufas',
        detail: 'Combustível para 8h · cobre todos os barcos',
        cost: '+€420',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'B',
        label: 'Reagendar cura para mais tarde',
        detail: 'Só viável se a falha durar <30min',
        cost: '+€140',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'C',
        label: 'Aceitar perda · 12 barcos para retrabalho',
        detail: '€8.4K em material + 2 dias',
        cost: '−€8.400',
        tone: 'red',
        recommended: false,
      },
    ],
  },
  {
    id: 'shipment_delay',
    icon: 'Truck',
    label: 'Camião atrasa',
    severity: 'medium',
    detail: 'Camião da Fed. Italiana · transportadora avariou · +2 dias',
    scenarioTitle: 'Crise · atraso do camião de expedição',
    deltas: [
      {
        entity_type: 'transport_batch',
        entity_key: 'camiao-fed-italiana',
        patch: { delayed_days: 2, boats_ready: 16 },
        description: 'Camião de expedição atrasa 2 dias (avaria da transportadora)',
      },
    ],
    cascade: [
      {
        t: 'agora',
        what: '16 barcos prontos · armazém ocupado',
        tone: 'yellow',
      },
      {
        t: '+1 dia',
        what: 'Outras expedições disputam espaço de armazém',
        tone: 'orange',
      },
      {
        t: '+2 dias',
        what: 'Camião alternativo encontrado',
        tone: 'green',
      },
    ],
    deltaEur: -680,
    deltaDays: 2,
    options: [
      {
        letter: 'A',
        label: 'Camião alternativo · transportadora B',
        detail: 'Disponível em 4h · €120 de sobretaxa',
        cost: '+€120',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'B',
        label: 'Dividir em 2 camiões parciais',
        detail: 'Armazém alivia mais cedo',
        cost: '+€800',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'C',
        label: 'Aguardar · cliente aceita +2d',
        detail: 'Relação OK · risco de repetir',
        cost: '€0',
        tone: 'gray',
        recommended: false,
      },
    ],
  },
];
