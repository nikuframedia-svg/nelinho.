/* ─── PP1-NELO mock data ─────────────────────────────────────────── */

const TODAY = new Date('2026-05-12T10:30:00');
const fmtEuro = (n) => '€' + Math.round(n).toLocaleString('pt-PT');
const fmtEuroK = (n) => '€' + (n/1000).toFixed(1).replace('.', ',') + 'K';

/* 41 fases — mostramos as principais no mapa de produção */
const PHASES = [
  { id: 1,  name: 'Prep. Molde',       short: 'Prep.',      cap: 4,  cure: 0 },
  { id: 2,  name: 'Pintura gelcoat',   short: 'Gelcoat',    cap: 6,  cure: 0 },
  { id: 3,  name: 'Laminagem',         short: 'Laminagem',  cap: 16, cure: 0 },
  { id: 4,  name: 'Cura',              short: 'Cura',       cap: 20, cure: 15 },
  { id: 5,  name: 'Desmolde',          short: 'Desmolde',   cap: 6,  cure: 0 },
  { id: 6,  name: 'Corte',             short: 'Corte',      cap: 8,  cure: 0 },
  { id: 7,  name: 'Colagem Peças',     short: 'Colagem',    cap: 10, cure: 0 },
  { id: 8,  name: 'Pintura Acabam.',   short: 'Pint. Ac.',  cap: 12, cure: 0 },
  { id: 9,  name: 'Lixagem água',      short: 'Lixagem',    cap: 25, cure: 0 },
  { id: 10, name: 'Montagem',          short: 'Montagem',   cap: 8,  cure: 0 },
  { id: 11, name: 'CQ Final',          short: 'CQ',         cap: 4,  cure: 0 },
  { id: 12, name: 'Armazém',           short: 'Armazém',    cap: 30, cure: 0 },
];

const CLIENTS = {
  FR: { code: 'FR', name: 'Federação Francesa',     flag: '🇫🇷' },
  DE: { code: 'DE', name: 'Cliente Privado DE',     flag: '🇩🇪' },
  PT: { code: 'PT', name: 'Federação Portuguesa',   flag: '🇵🇹' },
  IT: { code: 'IT', name: 'Federação Italiana',     flag: '🇮🇹' },
  SE: { code: 'SE', name: 'Equipa Sueca',           flag: '🇸🇪' },
  NO: { code: 'NO', name: 'Clube Noruega',          flag: '🇳🇴' },
  AT: { code: 'AT', name: 'Federação Áustria',      flag: '🇦🇹' },
};

/* operadores — score, taxa erro, tier, skills */
const WORKERS = [
  { id: 'W01', name: 'Paulo Gomes Faria',  initials: 'PG', score_ml: 8.7, score: 8.9, err: 0.031, tier: '>12m', status: 'active',   ops: 14195, cost: 12.50, skills: ['Laminagem','Colagem Peças','Desmolde','Corte','Reparação'], main: 'Laminagem' },
  { id: 'W02', name: 'Maria Silva',        initials: 'MS', score_ml: 8.2, score: 8.2, err: 0.048, tier: '>12m', status: 'active',   ops: 9120,  cost: 11.80, skills: ['Laminagem','Laminagem Infusão','Colagem Barcos'], main: 'Laminagem' },
  { id: 'W03', name: 'João Costa',         initials: 'JC', score_ml: 7.2, score: 7.2, err: 0.079, tier: '>12m', status: 'vacation', ops: 8210,  cost: 11.20, skills: ['Colagem Peças','Corte','Montagem'], main: 'Colagem Peças' },
  { id: 'W04', name: 'Ana Reis',           initials: 'AR', score_ml: 6.2, score: 6.2, err: 0.150, tier: '<12m', status: 'active',   ops: 4220,  cost: 10.50, skills: ['Pintura Acabamento','Pintura gelcoat'], main: 'Pintura Acabamento' },
  { id: 'W05', name: 'António Pereira',    initials: 'AP', score_ml: 4.2, score: 4.2, err: 0.221, tier: '<5m',  status: 'active',   ops: 612,   cost: 9.00,  skills: ['Laminagem'], main: 'Laminagem' },
  { id: 'W06', name: 'Carlos Santos',      initials: 'CS', score_ml: 8.1, score: 8.1, err: 0.041, tier: '>12m', status: 'active',   ops: 11400, cost: 12.00, skills: ['Pintura Acabamento','Lixagem','Montagem'], main: 'Pintura Acabamento' },
  { id: 'W07', name: 'Helena Marques',     initials: 'HM', score_ml: 7.8, score: 7.8, err: 0.052, tier: '>12m', status: 'active',   ops: 9870,  cost: 11.50, skills: ['Lixagem','Pintura gelcoat','Pintura Acabamento'], main: 'Lixagem água' },
  { id: 'W08', name: 'Tiago Lopes',        initials: 'TL', score_ml: 7.5, score: 7.5, err: 0.062, tier: '>12m', status: 'active',   ops: 7320,  cost: 11.20, skills: ['Corte','Montagem','CQ Final'], main: 'Montagem' },
];

/* barcos em produção */
const BOATS = [
  { id: 4271, model: 'K1 Vanquish L SCS', short: 'K1', client: 'FR', phase: 3, status: 'on_time', dx: 4, transport: '2026-05-16', workers: ['W01','W02'], mold: 'K1 7 ML (02)', risk: 0.08 },
  { id: 4272, model: 'K1 Quattro L SCS',  short: 'K1', client: 'PT', phase: 8, status: 'at_risk', dx: 5, transport: '2026-05-16', workers: ['W04'],       mold: null, risk: 0.18 },
  { id: 4273, model: 'K1 Vanquish M',     short: 'K1', client: 'FR', phase: 10, status: 'at_risk', dx: 2, transport: '2026-05-16', workers: ['W08'],     mold: null, risk: 0.12 },
  { id: 4274, model: 'K1 Vanquish L',     short: 'K1', client: 'PT', phase: 3, status: 'on_time', dx: 1, transport: '2026-05-20', workers: ['W05'],     mold: 'K1 7 ML (03)', risk: 0.23 },
  { id: 4275, model: 'K1 Vanquish M',     short: 'K1', client: 'PT', phase: 9, status: 'late',    dx: 7, transport: '2026-05-16', workers: ['W07'],     mold: null, risk: 0.31 },
  { id: 5103, model: 'K2 Hybrid',         short: 'K2', client: 'DE', phase: 7, status: 'on_time', dx: 3, transport: '2026-05-20', workers: ['W03'],     mold: null, risk: 0.06 },
  { id: 5104, model: 'K2 Pro',            short: 'K2', client: 'IT', phase: 3, status: 'on_time', dx: 2, transport: '2026-05-22', workers: ['W01'],     mold: 'K2 7 L (02)', risk: 0.10 },
  { id: 5105, model: 'K2 Sprint',         short: 'K2', client: 'DE', phase: 8, status: 'on_time', dx: 1, transport: '2026-05-22', workers: ['W06'],     mold: null, risk: 0.07 },
  { id: 6001, model: 'K4 Multisport',     short: 'K4', client: 'PT', phase: 4, status: 'curing',  dx: 0, transport: '2026-05-22', workers: [],          mold: null, risk: 0.05 },
  { id: 6002, model: 'K4 Cluster',        short: 'K4', client: 'PT', phase: 8, status: 'at_risk', dx: 6, transport: '2026-05-16', workers: ['W04'],     mold: null, risk: 0.22 },
  { id: 6003, model: 'K4 Multisport',     short: 'K4', client: 'NO', phase: 5, status: 'late',    dx: 4, transport: '2026-05-16', workers: [],          mold: null, risk: 0.28 },
  { id: 6004, model: 'K4 Cluster',        short: 'K4', client: 'SE', phase: 7, status: 'on_time', dx: 1, transport: '2026-05-22', workers: ['W08'],     mold: null, risk: 0.09 },
];

/* sugestões na timeline de aprovação */
const SUGGESTIONS = [
  {
    id: 847,
    priority: 'critical',
    title: 'Mover 3 barcos K2 de terça para quarta',
    why: 'Molde K2 7 L (02) em manutenção preventiva terça-feira (847 usos, atinge ciclo de 800). Sem molde, 3 barcos ficam parados.',
    if_accept: [
      'Barcos atrasam 1 dia (entregues quarta às 18h)',
      'Expedição sexta sem impacto — margem de 2 dias',
      'Throughput terça: −€7.200, quarta: +€7.200 (zero impacto líquido)',
    ],
    if_reject: [
      '3 barcos parados terça-feira inteira (sem molde)',
      '2 laminadores idle 8h — custo €240 em mão-de-obra parada',
      'Molde força paragem na mesma terça à tarde — barcos acabam quarta',
    ],
    alternative: {
      label: 'Usar molde K2 7 L (01) — versão de 2 poços',
      detail: '+2h por barco (4 poços vs 2), sem atraso de calendário. Custo: ~€80 em horas extra.',
    },
    confidence: 91,
    source: 'CPO Scheduler · regra MOLD_PREVENTIVE',
  },
  {
    id: 846,
    priority: 'high',
    title: 'Trocar Ana Reis por Carlos Santos no K1 #4272 Pintura',
    why: 'Ana tem score 6.2 em Pintura Acabamento (taxa erro 18% nos últimos 90 dias). Carlos tem score 8.1 (taxa 4%). #4272 é prioridade alta — Federação Portuguesa, expedição sexta.',
    if_accept: [
      'Risco de erro desce de 18% para 4%',
      'Tempo estimado: +30min (Carlos é mais metódico)',
      'Ana fica livre 09:00–13:00 — pode ir para Lixagem (3 barcos em fila)',
    ],
    if_reject: [
      'Risco de retrabalho sobe — 1 em 5 barcos K1 da Ana volta à Pintura',
      'Se #4272 vier para retrabalho, perde-se a expedição de sexta',
    ],
    alternative: null,
    confidence: 84,
    source: 'CPO Scheduler · skill matching',
  },
  {
    id: 845,
    priority: 'medium',
    title: 'Antecipar K1 #4271 para expedição de quinta',
    why: '#4271 acaba quarta às 16h. Próxima expedição é sexta. Há um camião de quinta com 4 lugares vazios para Federação Francesa.',
    if_accept: [
      'Cliente FR recebe 1 dia mais cedo (boa relação comercial)',
      'Liberta espaço de armazém quinta-feira',
      'Custo: €0 (camião já agendado)',
    ],
    if_reject: [
      'Sem impacto operacional — expedição sexta corre normal',
      'Barco fica 1 dia parado em armazém',
    ],
    alternative: null,
    confidence: 76,
    source: 'CPO Dispatcher · transport_optimizer',
  },
];

/* alertas do painel */
const ALERTS = [
  {
    id: 'A01',
    severity: 'critical',
    title: 'Molde K1 7 ML (03) — taxa erro a subir',
    detail: '23% esta semana vs 12% normal',
    cause: '847 usos desde última manutenção (limite recomendado: 800)',
    primary: { label: 'Propor manutenção',     action: 'mold_maintenance' },
    secondary:{ label: 'Ver detalhe',          action: 'mold_detail' },
    when: 'há 23 min',
  },
  {
    id: 'A02',
    severity: 'high',
    title: 'Expedição sexta — 2 barcos em risco',
    detail: 'K1 #4275 (Lixagem, atrasado 7 dias) e K4 #6002 (Pintura, em risco)',
    cause: null,
    primary: { label: 'Ver expedição',         action: 'shipment_friday' },
    secondary:null,
    when: 'há 1h',
  },
  {
    id: 'A03',
    severity: 'medium',
    title: 'Lixagem água — fila de 22 barcos',
    detail: 'Capacidade da fase: 25. Carga: 88%. Retrabalho a aumentar (49%)',
    cause: 'Falta de operadores — Helena Marques é a única tier >12m',
    primary: { label: 'Ver fase',              action: 'phase_detail' },
    secondary:{ label: 'Sugerir reforço',      action: 'staffing' },
    when: 'há 2h',
  },
];

/* expedições agendadas */
const SHIPMENTS = [
  { date: '2026-05-16', day: 'Sexta',  client: 'Fed. Francesa + Fed. Portuguesa', total: 50, ready: 42, in_prod: 4, at_risk: 2, suggestion: null },
  { date: '2026-05-20', day: 'Quarta', client: 'Cliente Privado DE',              total: 50, ready: 18, in_prod: 0, at_risk: 0, suggestion: '4 barcos prontos sem expedição — completar camião poupa €800' },
  { date: '2026-05-22', day: 'Sexta',  client: 'Fed. Italiana + Equipa Sueca',    total: 50, ready: 22, in_prod: 7, at_risk: 2, suggestion: null },
];

/* moldes */
const MOLDS = [
  { id: 'M-K1-03', name: 'K1 7 ML (03)', uses: 847, max: 800, err_week: 0.23, err_normal: 0.12, status: 'critical' },
  { id: 'M-K2-02', name: 'K2 7 L (02)',  uses: 642, max: 800, err_week: 0.14, err_normal: 0.10, status: 'warning' },
  { id: 'M-K4-01', name: 'K4 7 L (01)',  uses: 312, max: 800, err_week: 0.08, err_normal: 0.09, status: 'ok' },
  { id: 'M-K1-02', name: 'K1 7 ML (02)', uses: 521, max: 800, err_week: 0.09, err_normal: 0.10, status: 'ok' },
];

/* erros de qualidade recentes */
const RECENT_ERRORS = [
  { boat: 'K1 #4270', defect: 'Interior enrugado',   phase: 'Laminagem', worker: 'Paulo G.', severity: 'high'   },
  { boat: 'K2 #5098', defect: 'Pintura com fios',    phase: 'Pintura Acab.', worker: 'Ana R.',   severity: 'medium' },
  { boat: 'K1 #4268', defect: 'Bolha 3 mm pavilhão', phase: 'Laminagem', worker: 'A. Pereira', severity: 'medium' },
  { boat: 'K4 #5999', defect: 'Cola insuficiente',   phase: 'Colagem',   worker: 'João C.',  severity: 'low'    },
];

/* regras aprendidas */
const LEARNED_RULES = [
  { id: 1, status: 'active',    confidence: 0.92, text: 'Nunca propor alterações na Laminagem à sexta-feira', basis: '7 rejeições consecutivas' },
  { id: 2, status: 'active',    confidence: 0.85, text: 'Preferir menos setups a mais throughput (delta < 5%)', basis: '23 escolhas consistentes' },
  { id: 3, status: 'suggested', confidence: 0.68, text: 'Operadores tier <5m não devem fazer K1 competição', basis: '4 overrides manuais' },
];

/* pesos da fitness — defaults vs aprendidos */
const FITNESS_WEIGHTS = [
  { key: 'makespan',   default: 0.20, learned: 0.18 },
  { key: 'tardiness',  default: 0.25, learned: 0.30 },
  { key: 'setup',      default: 0.15, learned: 0.22 },
  { key: 'quality',    default: 0.10, learned: 0.18 },
  { key: 'throughput', default: 0.15, learned: 0.08 },
  { key: 'idle',       default: 0.15, learned: 0.04 },
];

/* KPI series — 14 dias */
const THROUGHPUT_14D = [28.4, 29.1, 27.8, 30.2, 31.5, 32.0, 30.9, 28.5, 24.1, 25.3, 27.2, 30.8, 32.1, 33.2];

/* ─── exports ─── */
window.PP = {
  TODAY, fmtEuro, fmtEuroK,
  PHASES, CLIENTS, WORKERS, BOATS,
  SUGGESTIONS, ALERTS, SHIPMENTS, MOLDS, RECENT_ERRORS,
  LEARNED_RULES, FITNESS_WEIGHTS, THROUGHPUT_14D,
};
