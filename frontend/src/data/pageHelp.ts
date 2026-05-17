/**
 * pageHelp.ts — conteúdo estático do botão "?" em cada page do shell.
 *
 * Luis: "quando a pessoa clica nesse ? tem um resumo e um exemplo de como
 * funcionar com a página em questão". PT-PT informal, concreto, sem jargão.
 *
 * Adicionar entry para nova page → `PageHelpId` union + dicionário abaixo.
 */

export type PageHelpId =
  | 'direcao'
  | 'inbox'
  | 'plano-producao'
  | 'atribuicao'
  | 'oee'
  | 'qualidade'
  | 'operadores'
  | 'expedicao'
  | 'aprendizagem'
  | 'regras'
  | 'definicoes';

export interface PageHelpEntry {
  /** Título humano (não a URL). */
  title: string;
  /** 1-2 frases — para que serve esta página. */
  purpose: string;
  /** Bullets curtos do que o utilizador vê. */
  whatYouSee: string[];
  /** Cenário concreto + passos numerados. */
  howToUse: { title: string; steps: string[] };
  /** Dicas opcionais. */
  tips?: string[];
  /** Pages relacionadas com razão. */
  relatedPages?: { id: PageHelpId; reason: string }[];
}

export const PAGE_HELP: Record<PageHelpId, PageHelpEntry> = {
  direcao: {
    title: 'Direção — Resumo do dia',
    purpose:
      'Visão de 10 segundos para CEO/gestor: a fábrica está no plano, em risco ou em atraso? Quantos barcos? Que decisões aguardam aprovação?',
    whatYouSee: [
      'Hero "A fábrica está NO PLANO / EM RISCO / EM ATRASO" com cor por estado',
      '4 KPIs hero (throughput €/dia, OTD, em curso, atrasos)',
      'Atenção necessária — alertas pendentes ordenados por severidade',
      'Próximas expedições — o que sai esta semana',
      'Tab "Profit Intelligence" — pricing, COGS, what-if scenarios, margem',
    ],
    howToUse: {
      title: 'Cenário: começar o dia',
      steps: [
        'Abre /direcao logo de manhã',
        'Lê o hero: se diz "no plano" e KPIs verdes → focar noutras coisas',
        'Se "em risco/atraso" → click "Sugestões" canto superior direito → vai para /inbox',
        'Para análise financeira → click tab "Profit Intelligence"',
        'Para exportar relatório → click "Exportar Produção" e escolhe template',
      ],
    },
    tips: [
      'O hero refresca quando clicas Actualizar (não há refresh automático)',
      'Vista CEO read-only (TopBar) esconde botões de escrita — útil para mostrar',
    ],
    relatedPages: [
      { id: 'inbox', reason: 'Aprovar/rejeitar decisões propostas' },
      { id: 'plano-producao', reason: 'Detalhe do que cada barco está a fazer' },
      { id: 'expedicao', reason: 'Calendário completo de expedições' },
    ],
  },

  inbox: {
    title: 'Inbox de decisões',
    purpose:
      'Onde o sistema te pede aprovação humana antes de fazer mudanças que mexem com o plano (ex: alterar atribuição, mover barco entre semanas, ajustar pricing).',
    whatYouSee: [
      'Lista de decisões pendentes ordenadas por urgência',
      'Cada cartão mostra: o que muda, porquê, se aceitar/rejeitar consequências, alternativa',
      'Botões Aceitar / Rejeitar (com razão) / Modificar',
      'Filtros por tipo de decisão e estado',
    ],
    howToUse: {
      title: 'Cenário: aprovar uma sugestão de re-atribuição',
      steps: [
        'Abre /inbox — lista as decisões em "Pendentes"',
        'Lê uma sugestão: "O que muda" + "Porquê" + "Se aceitar"',
        'Se concordas → Aceitar (escreve razão curta opcional para alimentar Camada 3 DPO)',
        'Se discordas → Rejeitar com razão obrigatória (≥10 chars) — alimenta aprendizagem',
        'O sistema regista hash da decisão na audit trail — podes voltar atrás em /aprendizagem > Governance',
      ],
    },
    tips: [
      'Toda decisão Q.17 requer aprovação humana — kill_switch é admin-SQL-only',
      'Para bulk approve/reject vai a /definicoes > Sistema > Operations',
    ],
    relatedPages: [
      { id: 'aprendizagem', reason: 'Ver activity outbox + audit + rollback decisões' },
      { id: 'regras', reason: 'Editar as regras Q.17 que originam estas decisões' },
    ],
  },

  'plano-producao': {
    title: 'Plano de produção',
    purpose:
      'Vista detalhada do que cada barco está a fazer agora e nas próximas semanas. 4 vistas: por fase, Gantt, calendário, ou CPO (optimização).',
    whatYouSee: [
      'Por fase — barcos agrupados pela fase actual (laminagem, cura, pintura...)',
      'Gantt — timeline horizontal por barco × dias',
      'Calendário — vista mensal',
      'CPO — re-optimizer + alternativas MAP-Elites + commits SHA',
    ],
    howToUse: {
      title: 'Cenário: ver o que falta para um barco K1',
      steps: [
        'Abre /plano-producao — vista "Por fase" por defeito',
        'Encontra o barco pela fase actual ou usa Ctrl+K para procurar',
        'Click no barco → drawer com timeline detalhada',
        'Para optimizar plano → muda para vista "CPO" → ajusta horizon_days → "Re-optimizar"',
        'Cada commit fica registado com SHA + axiom violations (devem ser 0)',
      ],
    },
    tips: [
      'Os 7 axiomas Spelke são imovíveis — qualquer plano que viole capacity ≥0, mold exclusivo, etc., é rejeitado pelo CPO',
      'Ver alternativas MAP-Elites (3D archive 10×10×5) na vista CPO > Timeline',
    ],
    relatedPages: [
      { id: 'atribuicao', reason: 'Quem faz o quê hoje' },
      { id: 'inbox', reason: 'Aprovar mudanças propostas pelo CPO' },
    ],
  },

  atribuicao: {
    title: 'Atribuição diária',
    purpose:
      'Quem faz o quê hoje. Vista 2-col operador × OF para o gestor confirmar/ajustar antes do início do dia.',
    whatYouSee: [
      'Coluna esquerda: lista de operadores activos hoje (com nivel + skills)',
      'Coluna direita: OFs do dia agrupadas por turno',
      'Drag-drop visual (preview-delta) antes de commit',
      'Botão "Sugerir atribuição" → CPO recomenda matching óptimo',
    ],
    howToUse: {
      title: 'Cenário: ajustar atribuição depois de uma falta',
      steps: [
        'Operador faltou → marca status em /operadores > Lista',
        'Volta a /atribuicao — operador desaparece do disponível',
        'Click "Sugerir atribuição" → CPO devolve novo matching com axiom check',
        'Confirma drag-drop manual se queres ajustar — ConsequenceBlock mostra o impacto',
        'Click "Imprimir folha" para deixar no chão de fábrica',
      ],
    },
    relatedPages: [
      { id: 'operadores', reason: 'Editar nível, marcar férias, ver skill matrix' },
      { id: 'plano-producao', reason: 'Vista Gantt do plano completo' },
    ],
  },

  oee: {
    title: 'OEE — Eficácia da fábrica',
    purpose:
      'Disponibilidade × Performance × Qualidade nos últimos 14 dias. Indicador clássico de manufacturing — sai abaixo de 75% e há problema.',
    whatYouSee: [
      'OEE Global — gauge com cor por nível (>85% verde, 75-85% amarelo, <75% vermelho)',
      '3 breakdown cards (Disponibilidade / Performance / Qualidade)',
      'Throughput chart 14 dias',
      'Impacto financeiro 4 rows (custo por hora parada, etc.)',
    ],
    howToUse: {
      title: 'Cenário: investigar drop no OEE',
      steps: [
        'Vê o gauge global. Se vermelho → qual dos 3 breakdowns está pior?',
        'Disponibilidade baixa → /qualidade > Moldes (ver health report)',
        'Performance baixa → /atribuicao (skill mismatch?)',
        'Qualidade baixa → /qualidade > Inteligência > Root-cause',
        'Para diagnóstico causal completo → tab Diagnóstico em /qualidade',
      ],
    },
    relatedPages: [
      { id: 'qualidade', reason: 'Drill-down em defeitos + diagnóstico causal' },
      { id: 'plano-producao', reason: 'Ver throughput vs alvo €/dia' },
    ],
  },

  qualidade: {
    title: 'Qualidade & Defeitos',
    purpose:
      'Onde investigas porque é que peças saem defeituosas. Erros recentes, estado de moldes, retrabalho, diagnóstico causal, OEE, Trust+DQA, Inteligência (root-cause/impact).',
    whatYouSee: [
      'Resumo — 4 KPIs + 2-col (erros recentes / estado moldes)',
      'Erros — lista de retrabalhos abertos',
      'Moldes — health report grid (click molde → drawer com histórico defeitos)',
      'Retrabalho — fila de retrabalho activa',
      'Diagnóstico — ERRO-TREE + Reichenbach + Mill (causal Q.15.D)',
      'OEE — embed da page OEE',
      'Trust + DQA — heatmap, blocked metrics, coverage, ingestão, drift, quarentena',
      'Inteligência — root-cause/impact por error_code, by-supplier, by-lot, worker ranking, multidim',
    ],
    howToUse: {
      title: 'Cenário: defeito repetido num molde K2',
      steps: [
        'Tab Moldes → encontra o molde com pior score (red/yellow)',
        'Click no card → drawer com últimos 50 defeitos + custo total',
        'Ver padrão? → tab Inteligência > Root-cause analyzer com error_code',
        'Causa-raiz noutra fase? → tab Diagnóstico > Reichenbach (common-cause)',
        'Pedir manutenção preventiva → drawer molde > "Propor manutenção"',
      ],
    },
    relatedPages: [
      { id: 'aprendizagem', reason: 'Ver causal/explain panels (NELO_DAG, attribution)' },
      { id: 'operadores', reason: 'Worker quality ranking — quem causa mais defeitos' },
    ],
  },

  operadores: {
    title: 'Operadores',
    purpose:
      'Lista da equipa, score derivado dos defeitos, polivalência por fase. Adicionar/editar operadores, ver skill history, simular ausências.',
    whatYouSee: [
      'Lista — 9 cols (avatar, tier, nível 1-3, score, taxa erro, ops, skill, estado, chevron)',
      'Alocações — atribuição diária (mesmo que /atribuicao)',
      'Produtividade — KPIs operacionais',
      'Risco — RiskHeatmap + SPOFAlertPanel + DependencyGraph + CascadeImpact',
      'Simulador — what-if "se este operador falta, qual o impacto?"',
      'Formação — TrainingRecommendation por skill gap',
      'Skills history — recency 12m + drawer matriz per-fase',
    ],
    howToUse: {
      title: 'Cenário: adicionar operador novo Junior',
      steps: [
        'Click "Adicionar operador" canto superior direito',
        'Preenche código, nome, departamento, função',
        'No campo "Nível" escolhe "3 — Em formação" (vai gravar quality_score=3.0 inicial)',
        'Guardar → operador aparece na lista com badge nível 3 vermelho',
        'Click no row → drawer detail com nível explicado + barcos recomendados (recreio supervisionado)',
        'Para perguntar ao Copilot que barcos lhe podem dar → "Pedir ao Copilot" no drawer',
      ],
    },
    tips: [
      'Nível 1=melhor, 3=pior. Derivado do quality score Laplace (defeitos/operações)',
      'Polivalência: mesmo operador pode ser nível 1 em laminagem e 3 em pintura (per-fase)',
      'Soft-delete preserva histórico (status TERMINATED, não apaga)',
    ],
    relatedPages: [
      { id: 'atribuicao', reason: 'Atribuir o operador ao dia' },
      { id: 'qualidade', reason: 'Worker quality ranking + by-worker errors' },
    ],
  },

  expedicao: {
    title: 'Expedições',
    purpose:
      'Calendário de saídas — que barcos saem em que camião, quando, para onde. Plus dashboard de Supply/Forecast (Prophet, ROP, ABC, shortage alerts).',
    whatYouSee: [
      'Tab Expedições — 3 KPIs strip + lista de batches com progress (ready/in_prod/at_risk)',
      'Tab Supply / Forecast — Prophet 30/90d, ROP per SKU, ABC analysis, shortage alerts, sazonalidade (stub)',
    ],
    howToUse: {
      title: 'Cenário: ver risco do próximo camião',
      steps: [
        'Tab Expedições mostra os 3 próximos batches',
        'Cada batch tem barra com green=ready, blue=in_prod, yellow=at_risk',
        'Se yellow elevado → drill /plano-producao para ver quais barcos atrasados',
        'Para forecast de procura SKU → tab Supply > Forecast → input sku_id + horizon',
        'ROP — Reorder Point por SKU com nível de serviço 90/95/99%',
      ],
    },
    relatedPages: [
      { id: 'plano-producao', reason: 'Ver detalhe dos barcos do próximo batch' },
      { id: 'direcao', reason: 'Próximas expedições no resumo do dia' },
    ],
  },

  aprendizagem: {
    title: 'O que aprendi',
    purpose:
      'Hub de tudo o que o sistema aprendeu/governa: regras Q.17, 4 camadas aprendizagem, causal/explain, ML registry, Twin sandbox, governance/audit, factory data product, Copilot extras, showcase de componentes.',
    whatYouSee: [
      'Resumo — vista zip page-extra (PageLearning)',
      'Regras (NL→DSL Q.17) — split-pane editor de regras YAML',
      'Regras aprendidas (Camada 1) — PreferenceRules de overrides',
      'Q.17 Avançado — 5 painéis (audit firings, impact, schema explorer, conflict, axioms)',
      '4 Camadas Aprendizagem — preference rule, adaptive weights, DPO counter, ABL',
      'Causal/Explain — ERRO-TREE, Reichenbach, Mill, NELO_DAG, attribution, POETIQ',
      'Copilot extras — feedback collector, RAG ingest, mascot',
      'Governance/Audit — event-outbox, RBAC matrix, decision rollback',
      'Factory data product — 7 semantic views allow-listed',
      'ML registry — list/promote/rollback versões de modelos',
      'Twin sandbox — scenarios CRUD + simulate + solve',
      'Showcase — demos de componentes design system',
    ],
    howToUse: {
      title: 'Cenário: ver porque é que uma regra disparou',
      steps: [
        'Tab Q.17 Avançado → painel Audit firings',
        'Lista todas as vezes que regras Q.17 dispararam (rule_id, evento, outcome)',
        'Para impacto adoption → painel Impact dashboard',
        'Para vocabulário fechado (12 events × 9 actions × 8 ops × 7 axioms) → Schema explorer',
        'Para rollback de decisão → tab Governance/Audit > Decision rollback',
      ],
    },
    relatedPages: [
      { id: 'regras', reason: 'Editor split-pane standalone das regras YAML' },
      { id: 'inbox', reason: 'Aprovar decisões originadas pelas regras' },
    ],
  },

  regras: {
    title: 'Regras Q.17 (YAML)',
    purpose:
      'Editor split-pane das regras logic-as-data. Vocabulário fechado: 12 events × 9 actions × 8 condition ops × 7 Spelke axioms. LLM pode propor regra a partir de NL, humano sempre aprova.',
    whatYouSee: [
      'Split-pane: lista de regras YAML à esquerda, editor à direita',
      'Sandbox dry-run banner — explica que mudanças correm em DB copy primeiro',
      'ACTION_WIRING badges — indica quais actions estão wired (alert/block/modify_fitness/set_config) vs stubbed',
      'Diff modal approve/reject quando aplicas mudanças',
      'Axiom checklist visual no preview — garante 7 Spelke preservados',
    ],
    howToUse: {
      title: 'Cenário: criar regra "alertar quando mold > 800 usos"',
      steps: [
        'Click "+ Nova regra" → modal NL→DSL',
        'Escreves "Alertar quando mold use count > 800"',
        'LLM propõe DSL YAML estruturado (event=mold_use_count_threshold, action=alert)',
        'Validas axioms — sandbox dry-run mostra impacto sem afectar prod',
        'Click "Approve" → diff modal mostra estado before/after, hash chain regista decisão',
        'Regra fica activa, dispara quando trigger condition passa',
      ],
    },
    tips: [
      'safety.requires_human_approval=True é Literal — LLM nunca pode opt-out',
      'kill_switch é admin-SQL-only — não há botão UI para activar/desactivar regras crít.',
      '4 dispatchers stubbed (reassign_worker, propose_maintenance, notify, create_decision, pause_writes) — flipados True quando sub-sprint chegar',
    ],
    relatedPages: [
      { id: 'aprendizagem', reason: 'Q.17 Avançado — audit firings + impact dashboard' },
      { id: 'inbox', reason: 'Decisões propostas por regras aparecem aqui' },
    ],
  },

  definicoes: {
    title: 'Definições',
    purpose:
      'Configuração geral do sistema: dados mestre (clientes/fornecedores/máquinas/produtos/BOM/operações/tarifas/tenants), saúde do sistema, ingestão, RAG, tools, Reports schedule + GDPR, Operations dashboard.',
    whatYouSee: [
      'Geral — settings core',
      'Dados Mestre — 8 sub-CRUDs (Customers/Suppliers/Machines/Products/BOM/Operations/Rates/Tenants)',
      'Sistema — Saúde + Ingestão + RAG + Tools + Reports schedule + Operations',
      'Trust — DQA Page (Trust Index v2 + 5 gates)',
      'Acessos — RBAC matrix viewer',
      'Auditoria — audit trail per user',
    ],
    howToUse: {
      title: 'Cenário: agendar relatório semanal de produção',
      steps: [
        'Tab Sistema > Reports schedule',
        'Painel Schedule auto: escolhe template "producao", cron "0 8 * * MON" (Seg 8h)',
        'Click Agendar — fica registado (stub, persistência em sub-sprint)',
        'Painel Email delivery: adiciona luis@nikufra.ai para receber CSV',
        'Painel GDPR retention: define 365 dias (1 ano)',
      ],
    },
    relatedPages: [
      { id: 'aprendizagem', reason: 'Governance + audit + RBAC viewer' },
      { id: 'direcao', reason: 'Botão Exportar Produção usa o mesmo template' },
    ],
  },
};
