/**
 * Cenários de crise pré-definidos da tab "Crise · agora".
 * =======================================================
 *
 * Isto é CONFIGURAÇÃO, não dados mock: cada cenário descreve um
 * problema de produção e o(s) delta(s) a aplicar no digital twin.
 * Quando o utilizador corre um cenário, o frontend cria um
 * `twin/scenario` real (`POST /v1/twin/scenarios`), aplica os deltas
 * (`POST .../apply-delta`) e simula (`POST .../simulate`).
 *
 * O resultado computado pelo twin (real) são os deltas de KPIs agregados
 * (`backlog_horas_theoretical`, `quality_errors_total`) em
 * `simulation_result.before/after` + o `scenario_hash` reprodutível.
 * É isso que a card "Resultado real da simulação" mostra. Não há €
 * autorais neste ficheiro — os cenários são apenas parametrizações.
 *
 * Os `deltas` seguem o contrato `DeltaApplyRequest` do twin:
 *   { entity_type, entity_key, patch, description }
 *
 * O `entity_type` TEM de ser um dos tipos que o backend Twin sabe aplicar
 * (`SUPPORTED_DELTA_ENTITY_TYPES` em `src/twin/service.py`) — senão o
 * `apply-delta` devolve 422. O Twin modela a fábrica em KPIs agregados, por
 * isso cada crise entra como um choque de capacidade (`capacity_adjustment`,
 * `capacity_increase_pct` negativo = perda) ou de qualidade
 * (`quality_improvement`, `error_reduction_pct` negativo = degradação).
 *
 * Sprint Q.52.M · Q.56.A.
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
        entity_type: 'capacity_adjustment',
        entity_key: 'molde-k1-7ml-03',
        patch: { capacity_increase_pct: -30 },
        description:
          'Molde K1 7 ML (03) fora 7 dias — perda de capacidade de laminagem',
      },
    ],
    cascade: [
      {
        t: '+0min',
        what: 'Laminagem interrompida · barco para retrabalho',
        tone: 'red',
      },
      { t: '+2h', what: 'K1 em fila perdem slot', tone: 'orange' },
      {
        t: '+1 dia',
        what: 'K1 7 ML (02) em sobrecarga · fila cresce',
        tone: 'orange',
      },
      {
        t: '+3 dias',
        what: 'Encomendas de exportação em risco crítico',
        tone: 'red',
      },
    ],
    options: [
      {
        letter: 'A',
        label: 'Reroute K1 para molde 7 ML (02)',
        detail: '+2h por barco · fila cresce',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'B',
        label: 'Subcontratar reparação 24h',
        detail: 'Especialista externo · molde volta em 18h',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'C',
        label: 'Aceitar atraso de 7d e comunicar ao cliente',
        detail: 'Comunicar agora · evita surpresas de última hora',
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
        entity_type: 'capacity_adjustment',
        entity_key: 'laminador-k1-principal',
        patch: { capacity_increase_pct: -15 },
        description:
          'Laminador K1 ausente 3 dias — par de laminagem quebrado, capacidade abaixo',
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
    options: [
      {
        letter: 'A',
        label: 'Substituto sob supervisão de operadora sénior',
        detail: 'Mais lento mas seguro · sem retrabalho extra',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'B',
        label: 'Concentrar séniores só nos K1 críticos',
        detail: 'K2 atrasa mas o crítico fica coberto',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'C',
        label: 'Convocar operador da Colagem',
        detail: 'Skill transferível · Colagem fica curta',
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
        entity_type: 'capacity_adjustment',
        entity_key: 'gelcoat-branco',
        patch: { capacity_increase_pct: -20 },
        description:
          'Gelcoat branco em rotura 3 dias — barcos param antes da pintura',
      },
    ],
    cascade: [
      { t: 'agora', what: 'Stock crítico · acaba em ~12h', tone: 'red' },
      {
        t: '+12h',
        what: 'Barcos param antes da Pintura',
        tone: 'red',
      },
      {
        t: '+1 dia',
        what: 'Backlog cresce · capacidade bloqueada',
        tone: 'orange',
      },
      {
        t: '+3 dias',
        what: 'Entrega do fornecedor · recuperação 24h',
        tone: 'green',
      },
    ],
    options: [
      {
        letter: 'A',
        label: 'Encomenda urgente · fornecedor em 24h',
        detail: 'Sobretaxa de entrega urgente · chega amanhã',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'B',
        label: 'Avançar lixagem antes da pintura',
        detail: 'Reordenar fases · poupa tempo morto',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'C',
        label: 'Substituir por gelcoat off-white',
        detail: 'Cliente privado pode aceitar a variação',
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
        entity_type: 'quality_improvement',
        entity_key: 'resina-lote-suspeito',
        // `error_reduction_pct` negativo = degradação. -100 (erros duplicam)
        // é o limite da validação [-100,100]; o lote real é 3.8× baseline,
        // mas o choque máximo modelável é a duplicação.
        patch: { error_reduction_pct: -100 },
        description:
          'Lote de resina com taxa de defeito 23% (3.8× baseline) — erros disparam',
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
        what: 'Se mantido · retrabalho acumula por dia',
        tone: 'red',
      },
    ],
    options: [
      {
        letter: 'A',
        label: 'Bloquear lote · usar lote anterior em stock',
        detail: 'Stock chega para 3 dias · zero defeito esperado',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'B',
        label: 'Contactar fornecedor · análise do lote',
        detail: 'Suspende encomendas até resposta · 48h',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'C',
        label: 'Aceitar retrabalho · ajustar parâmetros',
        detail: '+15min de cura · 8% mais resina',
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
        entity_type: 'capacity_adjustment',
        entity_key: 'estufas-cura',
        patch: { capacity_increase_pct: -55 },
        description:
          'Estufas de cura sem energia — 12 barcos em cura activa em risco',
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
    options: [
      {
        letter: 'A',
        label: 'Gerador imediato · prioridade às estufas',
        detail: 'Combustível para 8h · cobre todos os barcos',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'B',
        label: 'Reagendar cura para mais tarde',
        detail: 'Só viável se a falha durar <30min',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'C',
        label: 'Aceitar perda · barcos para retrabalho',
        detail: 'Perda de material e atraso na produção',
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
        entity_type: 'capacity_adjustment',
        entity_key: 'camiao-fed-italiana',
        patch: { capacity_increase_pct: -10 },
        description:
          'Camião de expedição atrasa 2 dias — 16 barcos prontos ocupam armazém',
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
    options: [
      {
        letter: 'A',
        label: 'Camião alternativo · transportadora B',
        detail: 'Disponível em 4h · sobretaxa de urgência',
        tone: 'green',
        recommended: true,
      },
      {
        letter: 'B',
        label: 'Dividir em 2 camiões parciais',
        detail: 'Armazém alivia mais cedo',
        tone: 'yellow',
        recommended: false,
      },
      {
        letter: 'C',
        label: 'Aguardar · cliente aceita +2d',
        detail: 'Relação OK · risco de repetir',
        tone: 'gray',
        recommended: false,
      },
    ],
  },
];
