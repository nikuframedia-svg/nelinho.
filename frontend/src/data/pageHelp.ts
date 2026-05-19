/**
 * pageHelp.ts — conteúdo do botão "?" em cada página (Q.56).
 *
 * Luis: "uma ? em cada página com uma explicação em linguagem simples mas
 * bastante explicativa da página e do que faz." PT-PT informal, concreto,
 * sem jargão. Conteúdo instantâneo (sem LLM).
 *
 * As chaves são os NOMES DE ROTA actuais (ex: `fabrica`, `planeamento`) —
 * o `DarkPageLayout` deriva o `helpId` do URL, por isso a chave tem de
 * bater certo com o segmento da rota. Adicionar página nova → entrada no
 * union `PageHelpId` + no dicionário.
 */

export type PageHelpId =
  | 'painel'
  | 'planeamento'
  | 'fabrica'
  | 'expedicao'
  | 'equipa'
  | 'qualidade'
  | 'materiais'
  | 'simulacoes'
  | 'custos'
  | 'regras'
  | 'aprendi'
  | 'copilot'
  | 'configuracao'
  | 'direcao'
  | 'inbox'
  | 'relatorios'
  | 'saude'
  | 'rbac'
  | 'conexao-erp'
  | 'ligacoes';

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
  /** Páginas relacionadas com razão. */
  relatedPages?: { id: PageHelpId; reason: string }[];
}

/**
 * Deriva o `PageHelpId` do primeiro segmento do URL (ex: `/qualidade?tab=oee`
 * → `qualidade`). Devolve `undefined` se o segmento não tiver entrada de
 * ajuda. Usado pelo `DarkPageLayout` e pelo `PageHeader` para mostrar o "?"
 * em todas as páginas sem cada uma ter de declarar o `helpId`. Q.56.
 */
export function helpIdFromPath(pathname: string): PageHelpId | undefined {
  const seg = pathname.split('/').filter(Boolean)[0];
  if (seg && seg in PAGE_HELP) return seg as PageHelpId;
  return undefined;
}

export const PAGE_HELP: Record<PageHelpId, PageHelpEntry> = {
  painel: {
    title: 'Painel diário',
    purpose:
      'A vista de 5 segundos: olhas para aqui e sabes se a fábrica está bem ou se há fogo para apagar. É o sítio por onde começas o dia.',
    whatYouSee: [
      'KPIs do dia — barcos em produção, throughput, gargalos',
      'Gargalo por fase — qual a fase que está a travar a fábrica',
      'Alertas activos — o que o sistema detectou e precisa de atenção',
      'Aprovações pendentes — decisões à espera de um sim/não teu',
    ],
    howToUse: {
      title: 'Cenário: começar o dia',
      steps: [
        'Abre o Painel logo de manhã',
        'Lê os KPIs no topo — se está tudo verde, segue para o teu trabalho',
        'Se há um gargalo destacado, clica para perceber que fase está a travar',
        'Vê os alertas e as aprovações — trata primeiro os de severidade alta',
      ],
    },
    tips: [
      'O painel não actualiza sozinho — usa o botão actualizar quando quiseres dados frescos',
    ],
    relatedPages: [
      { id: 'inbox', reason: 'Tratar as decisões que aguardam aprovação' },
      { id: 'fabrica', reason: 'Ver o chão de fábrica fase a fase' },
    ],
  },

  planeamento: {
    title: 'Planeamento',
    purpose:
      'O plano da fábrica nos próximos dias: que barco faz o quê, quando, e com quem. Mexes no plano e vês logo a consequência antes de a aplicar.',
    whatYouSee: [
      'Barcos — timeline (Gantt) das operações do último plano do CPO',
      'Pessoas — cobertura de operadores por fase',
      'Materiais — se o stock actual chega para o plano',
      'Botão Replanear — corre o optimizador (CPO) outra vez',
    ],
    howToUse: {
      title: 'Cenário: mudar uma operação de fase',
      steps: [
        'Abre a aba Barcos',
        'Arrasta uma barra da timeline para outra fase',
        'O sistema mostra a consequência (fitness, throughput) — sem aplicar nada ainda',
        'Clica numa barra para ver o barco e os operadores recomendados para essa tarefa',
        'Se quiseres regenerar o plano todo, usa Replanear',
      ],
    },
    tips: [
      'Arrastar nunca aplica às cegas — passa sempre pela pré-visualização da consequência',
    ],
    relatedPages: [
      { id: 'fabrica', reason: 'Executar o plano no chão de fábrica' },
      { id: 'materiais', reason: 'Detalhe do stock que sustenta o plano' },
    ],
  },

  fabrica: {
    title: 'Fábrica',
    purpose:
      'A war room do chão de fábrica: cada coluna é uma fase, cada cartão um barco. Arrastas barcos entre fases e atribuis operadores ao trabalho do dia.',
    whatYouSee: [
      'Colunas Kanban — uma por fase, ordenadas pela sequência real de fabrico',
      'Cartões de barco dentro de cada fase',
      'Ao clicar num barco — painel com o detalhe e os operadores recomendados',
      'Toggle Estado actual ↔ Plano sugerido pelo CPO',
    ],
    howToUse: {
      title: 'Cenário: pôr um operador num barco',
      steps: [
        'Clica no cartão do barco que está na fase que te interessa',
        'Abre um painel com a info do barco e a lista de operadores',
        'A lista vem ordenada por adequação — o melhor leva o selo RECOMENDADO',
        'Cada operador mostra o nível na fase e o porquê (experiência, taxa de erro)',
        'Clica no operador que queres — fica atribuído ao barco na hora',
      ],
    },
    tips: [
      'Arrastar um barco para outra coluna mostra primeiro a consequência',
      'A vista Plano sugerido é só leitura — é a proposta do optimizador',
    ],
    relatedPages: [
      { id: 'planeamento', reason: 'Ver a timeline completa do plano' },
      { id: 'equipa', reason: 'Detalhe de cada operador e das suas skills' },
    ],
  },

  expedicao: {
    title: 'Expedições',
    purpose:
      'O calendário de saídas: que barcos vão em que camião, quando e para onde. Inclui também o lado do aprovisionamento (forecast de procura, stock).',
    whatYouSee: [
      'Lista de camiões/expedições com o manifesto de cada um',
      'Estado de cada barco do manifesto (pronto / em produção / em risco)',
      'Aba Supply / Forecast — previsão de procura e níveis de stock',
    ],
    howToUse: {
      title: 'Cenário: ver o risco do próximo camião',
      steps: [
        'Abre a aba Expedições e escolhe o próximo camião na lista',
        'Vê o manifesto à direita — barras a amarelo são barcos em risco',
        'Se houver risco elevado, vai ao Planeamento ver que barcos estão atrasados',
        'Arrasta um barco para outra expedição se precisares de remarcar',
      ],
    },
    relatedPages: [
      { id: 'planeamento', reason: 'Ver o detalhe dos barcos do camião' },
      { id: 'painel', reason: 'Próximas expedições no resumo do dia' },
    ],
  },

  equipa: {
    title: 'Equipa',
    purpose:
      'A casa das pessoas: a lista de operadores, o que cada um sabe fazer e quão bem, onde há risco de depender de uma só pessoa, e que formação falta.',
    whatYouSee: [
      'Operadores — tabela com nível, taxa de erro, operações e skills',
      'Pares & Cobertura — quem pode substituir quem na Laminagem',
      'SPOFs — fases que dependem de uma única pessoa (risco)',
      'Perfil de cada operador — histórico, skills por fase, recomendações',
    ],
    howToUse: {
      title: 'Cenário: ver se a equipa cobre uma falta',
      steps: [
        'Abre a aba Pares & Cobertura',
        'Vê os SPOFs — fases marcadas a vermelho dependem de uma só pessoa',
        'Clica num operador para abrir o perfil com as skills por fase',
        'Se houver um buraco, vê as recomendações de formação',
      ],
    },
    tips: [
      'Nível: 3 é o melhor, 1 o pior — e é por fase (alguém pode ser 3 em laminagem e 1 em pintura)',
      'Os dados de qualidade e skills vêm do histórico real do ERP',
    ],
    relatedPages: [
      { id: 'fabrica', reason: 'Atribuir o operador ao trabalho do dia' },
      { id: 'qualidade', reason: 'Ver quem causa mais defeitos e onde' },
    ],
  },

  qualidade: {
    title: 'Qualidade & Defeitos',
    purpose:
      'Onde investigas porque é que saem peças defeituosas: erros recentes, defeitos por molde, retrabalho, diagnóstico de causa-raiz e a eficácia da fábrica (OEE).',
    whatYouSee: [
      'Resumo — KPIs de qualidade + erros recentes',
      'Moldes — defeitos reais por molde, pior primeiro',
      'Retrabalho — a fila de peças a refazer',
      'Diagnóstico — análise de causa-raiz dos defeitos',
      'OEE — disponibilidade × performance × qualidade',
    ],
    howToUse: {
      title: 'Cenário: um molde anda a dar defeitos',
      steps: [
        'Abre a aba Moldes — vêm ordenados pelos que mais defeitos causam',
        'Vê o número de defeitos e a data do último em cada cartão',
        'Para perceber o padrão, vai à aba Diagnóstico',
        'Cruza com a aba Inteligência para ver o erro por tipo e por fase',
      ],
    },
    relatedPages: [
      { id: 'equipa', reason: 'Quem causa mais defeitos e em que fase' },
      { id: 'aprendi', reason: 'Painéis causais e de explicação' },
    ],
  },

  materiais: {
    title: 'Materiais',
    purpose:
      'O que a fábrica consome: o catálogo de materiais (os componentes das BOMs dos barcos), o stock que existe e os fornecedores.',
    whatYouSee: [
      'Catálogo — materiais com nome, unidade, custo padrão e em quantas BOMs entram',
      'Prospeção / Entregas — o lado de compra e recepção',
      'Fornecedores — quem fornece o quê',
      'Stock real do ERP cruzado com o catálogo',
    ],
    howToUse: {
      title: 'Cenário: ver se um material está a faltar',
      steps: [
        'Abre a aba Catálogo',
        'Procura o material pelo nome',
        'Vê o stock actual e se há rutura prevista',
        'Materiais em risco aparecem destacados',
      ],
    },
    tips: [
      'Os materiais reais da NELO são os componentes-folha das BOMs — não há uma tabela de "material" separada',
    ],
    relatedPages: [
      { id: 'planeamento', reason: 'Ver se o stock chega para o plano' },
      { id: 'expedicao', reason: 'Forecast de procura e níveis de stock' },
    ],
  },

  simulacoes: {
    title: 'Simulações',
    purpose:
      'O gémeo digital da fábrica: testas um "e se…?" sem mexer na produção real. Vês o resultado lado a lado com o baseline antes de decidires.',
    whatYouSee: [
      'Histórico — cenários já simulados, baseline vs simulação',
      'Crise · agora — cenários de crise pré-definidos prontos a correr',
      'Botão Nova simulação — cria um cenário do zero',
    ],
    howToUse: {
      title: 'Cenário: testar o impacto de uma avaria',
      steps: [
        'Abre a aba Crise · agora',
        'Escolhe um cenário pré-definido (ex: máquina parada)',
        'Corre a simulação — o twin calcula o impacto',
        'Compara baseline vs simulação para decidir o que fazer',
      ],
    },
    tips: [
      'Nada do que fazes aqui afecta a produção real — é uma cópia segura',
    ],
    relatedPages: [
      { id: 'planeamento', reason: 'Aplicar no plano real o que a simulação validou' },
    ],
  },

  custos: {
    title: 'Custos',
    purpose:
      'A casa do dinheiro: quanto custa cada barco (COGS), a margem por produto, o que mais pesa nos custos, e um simulador de cenários de preço.',
    whatYouSee: [
      'Custo por barco — material, mão-de-obra, máquina, energia',
      'Margem por produto — quanto se ganha em cada modelo',
      'Ranking de drivers de custo — o que mais pesa',
      'Simulador what-if — mexe num preço e vê o efeito na margem',
    ],
    howToUse: {
      title: 'Cenário: perceber a margem de um modelo',
      steps: [
        'Abre Custos e escolhe o modelo de barco',
        'Vê o COGS decomposto — onde está o grosso do custo',
        'Vê a margem face ao preço de venda',
        'Usa o simulador para testar um preço diferente',
      ],
    },
    tips: [
      'O CoeficienteX é sempre dinheiro (€), nunca tempo',
    ],
    relatedPages: [
      { id: 'direcao', reason: 'Visão financeira de topo para o CEO' },
      { id: 'relatorios', reason: 'Drill-down de lucro barco a barco' },
    ],
  },

  regras: {
    title: 'Regras Q.17',
    purpose:
      'O editor das regras do sistema em linguagem-como-dados. Defines "quando acontece X, faz Y" — e o sistema passa a segui-las. Uma pessoa aprova sempre.',
    whatYouSee: [
      'Lista de regras à esquerda, editor à direita',
      'Pré-visualização da consequência antes de aplicar (sandbox)',
      'Verificação dos 7 axiomas — garante que a regra não parte nada',
      'Modal de diff ao aprovar uma mudança',
    ],
    howToUse: {
      title: 'Cenário: criar uma regra de alerta',
      steps: [
        'Clica em Nova regra e escreve o que queres em português',
        'O sistema propõe a regra estruturada',
        'Vê a pré-visualização — corre numa cópia, não afecta produção',
        'Aprova — a mudança fica registada com o seu histórico',
      ],
    },
    tips: [
      'Toda a regra exige aprovação humana — o sistema nunca a salta',
    ],
    relatedPages: [
      { id: 'inbox', reason: 'As decisões que as regras propõem aparecem aqui' },
      { id: 'aprendi', reason: 'Ver o histórico de quando as regras dispararam' },
    ],
  },

  aprendi: {
    title: 'O que aprendi',
    purpose:
      'O sítio onde vês tudo o que o sistema aprendeu e como se governa: regras, camadas de aprendizagem, modelos de ML, análise causal e a trilha de auditoria.',
    whatYouSee: [
      'Resumo do que o sistema aprendeu',
      'Regras aprendidas a partir das tuas correcções',
      'Modelos de ML — versões, promover, reverter',
      'Painéis causais e de explicação',
      'Governança e auditoria — quem fez o quê, quando',
    ],
    howToUse: {
      title: 'Cenário: ver porque o sistema sugeriu algo',
      steps: [
        'Abre a aba de auditoria / disparos de regras',
        'Procura a decisão ou regra que te interessa',
        'Vê o evento que a despoletou e o resultado',
        'Para análise causal, usa os painéis de explicação',
      ],
    },
    relatedPages: [
      { id: 'regras', reason: 'Editar as regras que originam as decisões' },
      { id: 'inbox', reason: 'Aprovar decisões propostas' },
    ],
  },

  copilot: {
    title: 'Copilot',
    purpose:
      'Conversa com o sistema em linguagem natural. Perguntas o que quiseres sobre a fábrica e o copiloto responde com dados ao vivo e fontes citáveis.',
    whatYouSee: [
      'Coluna esquerda — histórico das tuas conversas',
      'Coluna do meio — o chat, com modos de resposta',
      'Coluna direita — fontes e acções da última resposta',
    ],
    howToUse: {
      title: 'Cenário: perguntar algo ao sistema',
      steps: [
        'Escreve a pergunta na caixa em baixo e envia',
        'O copiloto consulta os dados ao vivo e responde',
        'Vê as fontes citadas na coluna direita',
        'Se a resposta sugerir uma acção, podes executá-la dali',
      ],
    },
    tips: [
      'Escolhe o modo de resposta nas pílulas por cima do chat',
    ],
    relatedPages: [
      { id: 'painel', reason: 'A vista rápida do estado da fábrica' },
    ],
  },

  configuracao: {
    title: 'Configuração',
    purpose:
      'Onde se afina o sistema: parâmetros de scheduling, custos, cura, moldes, alertas — e os dados mestre (produtos, BOMs, tarifas, fornecedores).',
    whatYouSee: [
      'Abas de parâmetros por área — cada valor mostra quem o definiu e quando',
      'Dados mestre — os CRUDs de produtos, BOM, operações, tarifas',
      'Sistema — saúde, ingestão, relatórios agendados',
      'Botão de repor o valor por defeito em cada parâmetro',
    ],
    howToUse: {
      title: 'Cenário: mudar um parâmetro',
      steps: [
        'Abre a aba da área que queres afinar',
        'Encontra o parâmetro — vê o valor actual e o histórico',
        'Muda o valor e guarda',
        'Se te arrependeres, usa repor ao default',
      ],
    },
    relatedPages: [
      { id: 'aprendi', reason: 'Governança, auditoria e permissões' },
      { id: 'conexao-erp', reason: 'Estado da ligação ao ERP' },
    ],
  },

  direcao: {
    title: 'Direção',
    purpose:
      'A vista do CEO: o estado da NELO em 30 segundos. KPIs grandes, objectivos, gráfico de €/dia e a margem por país/agente.',
    whatYouSee: [
      '4 KPIs grandes do negócio',
      'Banda de objectivos — onde estamos face às metas',
      'Gráfico de €/dia com a banda-alvo',
      'Margem por país/agente e encomendas activas',
    ],
    howToUse: {
      title: 'Cenário: ponto de situação da semana',
      steps: [
        'Abre Direção',
        'Lê os 4 KPIs e a banda de objectivos',
        'Vê o gráfico de €/dia — estamos dentro da banda-alvo?',
        'Para o detalhe financeiro, salta para Custos',
      ],
    },
    relatedPages: [
      { id: 'custos', reason: 'Detalhe de COGS, margem e cenários' },
      { id: 'painel', reason: 'O estado operacional do dia' },
    ],
  },

  inbox: {
    title: 'Inbox de decisões',
    purpose:
      'Onde o sistema te pede aprovação antes de fazer mudanças que mexem com o plano. Tu decides: aceitar, rejeitar ou modificar.',
    whatYouSee: [
      'Lista de decisões pendentes, por urgência',
      'Cada cartão: o que muda, porquê, e a consequência de aceitar ou rejeitar',
      'Botões Aceitar / Rejeitar / Modificar',
      'Filtros por estado (pendentes, aceites, rejeitadas)',
    ],
    howToUse: {
      title: 'Cenário: aprovar uma sugestão',
      steps: [
        'Abre o Inbox na aba Pendentes',
        'Lê uma sugestão — o que muda, porquê, e o que acontece se aceitares',
        'Se concordas, Aceitar; se não, Rejeitar com uma razão curta',
        'A tua razão alimenta a aprendizagem do sistema',
      ],
    },
    tips: [
      'Toda a decisão fica registada na trilha de auditoria — dá para voltar atrás',
    ],
    relatedPages: [
      { id: 'regras', reason: 'Editar as regras que originam estas decisões' },
      { id: 'aprendi', reason: 'Auditoria e reversão de decisões' },
    ],
  },

  relatorios: {
    title: 'Relatórios',
    purpose:
      'Os relatórios da fábrica: KPIs, o lucro barco a barco, e a exportação de relatórios para ficheiro.',
    whatYouSee: [
      'KPIs — indicadores agregados',
      'Lucro — drill-down de margem por barco',
      'Exportar — gerar e descarregar relatórios por template',
    ],
    howToUse: {
      title: 'Cenário: exportar um relatório',
      steps: [
        'Abre a aba Exportar',
        'Escolhe o template que queres',
        'Gera — o ficheiro é descarregado',
      ],
    },
    relatedPages: [
      { id: 'custos', reason: 'Análise de custos e margem' },
      { id: 'direcao', reason: 'Visão de topo do negócio' },
    ],
  },

  saude: {
    title: 'Saúde do sistema',
    purpose:
      'Responde a uma pergunta: a fábrica está segura para operar agora? Mostra o estado de cada módulo do sistema — verde, amarelo ou vermelho.',
    whatYouSee: [
      'Estado de cada módulo (verde / amarelo / vermelho)',
      'O que está degradado e porquê',
      'Sinais de diagnóstico do sistema',
    ],
    howToUse: {
      title: 'Cenário: algo parece estranho no software',
      steps: [
        'Abre Saúde do sistema',
        'Procura módulos a amarelo ou vermelho',
        'Lê o motivo indicado para esse módulo',
        'Usa isso para reportar ou investigar o problema',
      ],
    },
    relatedPages: [
      { id: 'conexao-erp', reason: 'Estado específico da ligação ao ERP' },
      { id: 'ligacoes', reason: 'Estado das ligações em tempo real' },
    ],
  },

  rbac: {
    title: 'Acessos',
    purpose:
      'Quem pode fazer o quê no sistema. Mostra os papéis (roles) e as permissões de cada um.',
    whatYouSee: [
      'Lista de papéis do sistema',
      'As permissões associadas a cada papel',
    ],
    howToUse: {
      title: 'Cenário: confirmar o que um papel pode fazer',
      steps: [
        'Abre Acessos',
        'Escolhe o papel que te interessa',
        'Vê a lista de permissões desse papel',
      ],
    },
    relatedPages: [
      { id: 'configuracao', reason: 'Configuração geral do sistema' },
    ],
  },

  'conexao-erp': {
    title: 'Conexão ERP',
    purpose:
      'O estado vivo da ligação ao ERP da NELO (MAR-KAYAKS): está ligado? Os dados estão frescos? Quando foi a última sincronização?',
    whatYouSee: [
      'Ligado / offline — com teste real à ERP',
      'Última sincronização por tipo de dados, com o nº de linhas',
      'O atraso desde a última sync com sucesso',
    ],
    howToUse: {
      title: 'Cenário: os dados parecem desactualizados',
      steps: [
        'Abre Conexão ERP',
        'Confirma se está Ligado',
        'Vê a última sync — se o atraso é grande, os dados estão velhos',
        'Reporta se a ligação estiver offline',
      ],
    },
    relatedPages: [
      { id: 'saude', reason: 'Saúde geral do sistema' },
      { id: 'ligacoes', reason: 'Estado das ligações em tempo real' },
    ],
  },

  ligacoes: {
    title: 'Ligações em tempo real',
    purpose:
      'O estado das ligações ao vivo do sistema: o canal de eventos em tempo real está a funcionar e a receber acontecimentos da fábrica?',
    whatYouSee: [
      'Saúde do canal de tempo real',
      'Canais disponíveis e os respectivos tópicos',
      'Stream ao vivo dos eventos à medida que acontecem',
    ],
    howToUse: {
      title: 'Cenário: confirmar que os eventos ao vivo chegam',
      steps: [
        'Abre Ligações',
        'Escolhe os canais que queres subscrever',
        'A stream liga-se e os eventos aparecem em tempo real',
      ],
    },
    relatedPages: [
      { id: 'saude', reason: 'Saúde geral do sistema' },
      { id: 'conexao-erp', reason: 'Estado da ligação ao ERP' },
    ],
  },
};
