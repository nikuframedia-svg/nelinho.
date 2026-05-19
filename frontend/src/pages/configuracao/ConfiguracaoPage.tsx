/**
 * ConfiguracaoPage — Configuração (shell · Q.60.U).
 *
 * As 4 tabs (Aprendizagem/Custos/Cura/Trust) foram decompostas para ./tabs/.
 * O painel genérico ConfigKeysPanel e os helpers partilhados em
 * ./configuracaoShared. O componente da página e as constantes ConfigKeyRow[]
 * das tabs de chaves mantêm-se aqui.
 */
import { useSearchParams } from 'react-router-dom';
import { Settings, Brain, Euro, CalendarClock, Route, Beaker, Hammer, Bell, ShieldCheck, Globe, TriangleAlert, Scale, PackageSearch, Coins } from 'lucide-react';
import { PageHeader, Tabs } from '../../components/dark';
import { type ConfigKeyRow, ConfigKeysPanel } from './configuracaoShared';
import { AprendizagemTab } from './tabs/AprendizagemTab';
import { CustosTab } from './tabs/CustosTab';
import { CuraTab } from './tabs/CuraTab';
import { TrustTab } from './tabs/TrustTab';

const TAB_IDS = [
  'aprendizagem',
  'custos',
  'scheduling',
  'routing',
  'cura',
  'moldes',
  'alertas',
  'trust',
  'sistema',
  // Q.53.J — categorias de config que já existem no backend mas não tinham aba.
  'governanca',
  'aprovisionamento',
  'custos-metas',
] as const;
type TabId = (typeof TAB_IDS)[number];

function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

const TABS = [
  { id: 'aprendizagem', label: 'Aprendizagem', icon: <Brain size={13} /> },
  { id: 'custos', label: 'Custos', icon: <Euro size={13} /> },
  { id: 'scheduling', label: 'Scheduling', icon: <CalendarClock size={13} /> },
  { id: 'routing', label: 'Routing', icon: <Route size={13} /> },
  { id: 'cura', label: 'Cura/Secagem', icon: <Beaker size={13} /> },
  { id: 'moldes', label: 'Moldes', icon: <Hammer size={13} /> },
  { id: 'alertas', label: 'Alertas', icon: <Bell size={13} /> },
  { id: 'trust', label: 'Trust', icon: <ShieldCheck size={13} /> },
  { id: 'sistema', label: 'Sistema', icon: <Globe size={13} /> },
  { id: 'governanca', label: 'Governança', icon: <Scale size={13} /> },
  {
    id: 'aprovisionamento',
    label: 'Aprovisionamento',
    icon: <PackageSearch size={13} />,
  },
  { id: 'custos-metas', label: 'Metas de custo', icon: <Coins size={13} /> },
];

// ─── Card / SectionHeader (geometria do design NELO) ─────────────────────────

const SCHEDULING_KEYS: ConfigKeyRow[] = [
  {
    key: 'fitness.weight.makespan',
    label: 'Peso fitness — makespan',
    hint: 'Default 0.20 — mede o tempo total do horizonte',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.tardiness_transport',
    label: 'Peso fitness — tardiness transporte',
    hint: 'Default 0.25 — datas de transporte são king (PL14)',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.idle_operators',
    label: 'Peso fitness — idle operadores',
    hint: 'Default 0.15 — penaliza operadores parados',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.setup_time',
    label: 'Peso fitness — setup time',
    hint: 'Default 0.15 — tempo de troca de molde/cor',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.quality_risk',
    label: 'Peso fitness — quality risk',
    hint: 'Default 0.10 — mean P(erro) das operações',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.throughput_eur_day',
    label: 'Peso fitness — throughput €/dia',
    hint: 'Default 0.15 — negativado internamente',
    dataType: 'float',
  },
  {
    key: 'cpo.total_budget_s',
    label: 'CPO budget total (s)',
    hint: 'Tempo end-to-end do cascade (Blueprint §5.5: 60s alvo)',
    dataType: 'float',
  },
  {
    key: 'cpo.gen_count',
    label: 'GA gerações',
    hint: 'Blueprint v2.0 exige 200',
    dataType: 'int',
  },
];

const ROUTING_KEYS: ConfigKeyRow[] = [
  {
    key: 'queue_time.median_h',
    label: 'Mediana queue inter-fase (h)',
    hint: 'PL22 — 5.2h mediana entre fases consecutivas',
    dataType: 'float',
  },
  {
    key: 'queue_time.p90_h',
    label: 'P90 queue inter-fase (h)',
    hint: 'PL22 — 69.2h, buffer maior quando TI < 0.60',
    dataType: 'float',
  },
  {
    key: 'buffer.post_desmolde_h',
    label: 'Buffer pós-Desmolde (h)',
    hint: 'PL21 — 4h, Desmolde é o ponto QC de facto',
    dataType: 'float',
  },
  {
    key: 'laminagem.require_pair',
    label: 'Laminagem exige par',
    hint: 'WF11 — 88.5% histórico. true=obrigatório',
    dataType: 'bool',
  },
  {
    key: 'laminagem.require_chefe',
    label: 'Par obrigatoriamente com chefe',
    hint: 'true=par tem de incluir um senior',
    dataType: 'bool',
  },
];

const MOLD_KEYS: ConfigKeyRow[] = [
  {
    key: 'maintenance_threshold_cycles',
    label: 'Threshold manutenção (ciclos)',
    hint: 'H2 — pending CEO. ≤0 desliga MOLD_MAINT_DUE',
    dataType: 'int',
  },
  {
    key: 'health_weight.cycles',
    label: 'Peso health — ciclos',
    hint: 'Default 0.40 — soma com os outros pesos = 1.0',
    dataType: 'float',
  },
  {
    key: 'health_weight.defects_90d',
    label: 'Peso health — defeitos 90d',
    hint: 'Default 0.20',
    dataType: 'float',
  },
  {
    key: 'health_weight.days_since_maint',
    label: 'Peso health — dias desde manutenção',
    hint: 'Default 0.20',
    dataType: 'float',
  },
  {
    key: 'health_weight.rework_rate',
    label: 'Peso health — taxa de retrabalho',
    hint: 'Default 0.20',
    dataType: 'float',
  },
  {
    key: 'health.red_threshold',
    label: 'Health score → vermelho',
    hint: 'Default 40 — abaixo bloqueia uso do molde',
    dataType: 'int',
  },
  {
    key: 'health.yellow_threshold',
    label: 'Health score → amarelo',
    hint: 'Default 70',
    dataType: 'int',
  },
];

const ALERTAS_KEYS: ConfigKeyRow[] = [
  {
    key: 'risk_alert_threshold',
    label: 'Threshold P(erro) para alerta',
    hint: 'QA07 — alerta preventivo quando P(erro) > threshold. Default 0.40',
    dataType: 'float',
  },
  {
    key: 'rework_buffer_pct.sanding_water',
    label: 'Buffer Lixagem água (%)',
    hint: 'QA11 — 20% (taxa real 49.2%)',
    dataType: 'float',
  },
  {
    key: 'rework_buffer_pct.sanding_polish',
    label: 'Buffer Lixagem polimento (%)',
    hint: 'QA11 — 20% (taxa real 41.3%)',
    dataType: 'float',
  },
  {
    key: 'rework_buffer_pct.painting_finishing',
    label: 'Buffer Pintura Acabamento (%)',
    hint: 'QA11 — 18% (taxa real 42.4%)',
    dataType: 'float',
  },
  {
    key: 'skill_bottleneck_threshold',
    label: 'Skill bottleneck (workers aptos)',
    hint: 'WF12 — fases com < N workers aptos viram bottleneck',
    dataType: 'int',
  },
];

const SYSTEM_KEYS: ConfigKeyRow[] = [
  {
    key: 'language',
    label: 'Idioma da interface',
    hint: 'pt-PT canónico. en-US/de-DE diferidos',
    dataType: 'string',
  },
  {
    key: 'format.currency',
    label: 'Moeda de apresentação',
    hint: 'EUR — afecta a formatação de valores',
    dataType: 'string',
  },
  {
    key: 'theme',
    label: 'Tema visual',
    hint: 'dark — tema único de produção',
    dataType: 'string',
  },
];

// ═══ Q.53.J — categorias de config governance / supply / cost ════════════════
// As linhas mapeiam 1:1 os seeds de src/core/services/default_configs.py.

const GOVERNANCA_KEYS: ConfigKeyRow[] = [
  {
    key: 'auto_approval.reschedule_order.enabled',
    label: 'Auto-aprovar reagendamentos',
    hint: 'WG07 — auto-aprova mudanças de plano baratas de risco baixo',
    dataType: 'bool',
  },
  {
    key: 'auto_approval.reschedule_order.risk_ceiling',
    label: 'Tecto de risco — reagendamento',
    hint: 'Só decisões até este nível auto-aprovam (LOW/MEDIUM/HIGH)',
    dataType: 'string',
  },
  {
    key: 'auto_approval.stock_adjustment.enabled',
    label: 'Auto-aprovar ajustes de stock',
    hint: 'Auto-aprova ajustes de stock dentro do tecto de risco',
    dataType: 'bool',
  },
  {
    key: 'auto_approval.stock_adjustment.risk_ceiling',
    label: 'Tecto de risco — ajuste de stock',
    hint: 'Nível máximo que auto-aprova ajustes de stock',
    dataType: 'string',
  },
  {
    key: 'auto_approval.model_promotion.enabled',
    label: 'Auto-aprovar promoção de modelos ML',
    hint: 'Auto-aprova a promoção de modelos ML de risco baixo',
    dataType: 'bool',
  },
  {
    key: 'auto_approval.model_promotion.risk_ceiling',
    label: 'Tecto de risco — promoção de modelos',
    hint: 'Nível máximo que auto-aprova promoção de modelos',
    dataType: 'string',
  },
  {
    key: 'timeline.hide_low_risk_default',
    label: 'Esconder risco baixo por defeito',
    hint: 'WG08 — anti-fadiga: esconde decisões LOW na timeline',
    dataType: 'bool',
  },
  {
    key: 'timeline.max_per_user_shown',
    label: 'Máx. itens por revisor',
    hint: 'WG08 — limita itens visíveis por revisor para evitar sobrecarga',
    dataType: 'int',
  },
];

const APROVISIONAMENTO_KEYS: ConfigKeyRow[] = [
  {
    key: 'safety_multiplier',
    label: 'Multiplicador de segurança',
    hint: 'MR05 — multiplicador sobre os pontos de encomenda calculados',
    dataType: 'float',
  },
  {
    key: 'stockout_critical_days',
    label: 'Dias críticos até rutura',
    hint: 'Abaixo deste nº de dias dispara MATERIAL_STOCKOUT_IMMINENT',
    dataType: 'int',
  },
  {
    key: 'adjust.auto_approve_threshold_qty',
    label: 'Limite de ajuste sem aprovação',
    hint: '|qty_delta| acima exige aprovação de governança (MR06/ST01)',
    dataType: 'float',
  },
];

const CUSTOS_METAS_KEYS: ConfigKeyRow[] = [
  {
    key: 'target.throughput_eur_day_min',
    label: 'Meta mínima de throughput/dia',
    hint: 'CS05 — Blueprint v2.0 §2.8 alvo €30K/dia',
    dataType: 'currency',
  },
  {
    key: 'target.throughput_eur_day_max',
    label: 'Meta máxima de throughput/dia',
    hint: 'Topo da banda de meta diária (€35K/dia)',
    dataType: 'currency',
  },
  {
    key: 'margin_default',
    label: 'Margem por defeito',
    hint: 'Margem fallback quando ProductPricing.sale_value falta (ex: 1.40)',
    dataType: 'float',
  },
  {
    key: 'target.unit_value_eur',
    label: 'Valor por encomenda',
    hint: 'Q.8 — €/encomenda para estimativas de backlog (€35K ÷ 14.9 barcos)',
    dataType: 'currency',
  },
];

// ═══ Página ══════════════════════════════════════════════════════════════════

export default function ConfiguracaoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'aprendizagem';

  const handleTabChange = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', id);
    setSearchParams(next, { replace: true });
  };

  return (
    <div>
      <PageHeader
        title="Configuração"
        subtitle="Parâmetros, regras e aprendizagem — cada valor com quem definiu, quando e botão reset"
        icon={<Settings size={18} />}
      />

      <div className="px-6 pt-3">
        <Tabs
          tabs={TABS}
          value={activeTab}
          onChange={handleTabChange}
          sticky
        />
      </div>

      <div className="px-6 py-5 page-enter">
        {activeTab === 'aprendizagem' && <AprendizagemTab />}

        {activeTab === 'custos' && <CustosTab />}

        {activeTab === 'scheduling' && (
          <ConfigKeysPanel
            title="Scheduling / CPO"
            subtitle="Pesos da fitness do solver · Blueprint v2.0 §5.5"
            icon={<CalendarClock size={14} />}
            category="planning"
            rows={SCHEDULING_KEYS}
            hint="Os pesos definem como o CPO compara alternativas. Devem somar ≈1.0 — o motor renormaliza defensivamente. Override do gestor SEMPRE ganha sobre regras aprendidas."
          />
        )}

        {activeTab === 'routing' && (
          <ConfigKeysPanel
            title="Routing"
            subtitle="Filas inter-fase e regras de par · Plan v4 §3"
            icon={<Route size={14} />}
            category="planning"
            rows={ROUTING_KEYS}
            hint="Os tempos de fila vêm do histórico real (PL22). O par obrigatório na Laminagem é o axioma dual-resource (88.5%)."
          />
        )}

        {activeTab === 'cura' && <CuraTab />}

        {activeTab === 'moldes' && (
          <ConfigKeysPanel
            title="Moldes"
            subtitle="Health score e manutenção · Plan v4 §3.5"
            icon={<Hammer size={14} />}
            category="mold"
            rows={MOLD_KEYS}
            hint="Os pesos health_weight.* devem somar 1.0. O threshold de manutenção é H2 do plano (placeholder pending CEO)."
          />
        )}

        {activeTab === 'alertas' && (
          <ConfigKeysPanel
            title="Alertas"
            subtitle="Thresholds de risco e buffers de retrabalho · QA07/QA11"
            icon={<Bell size={14} />}
            category="quality"
            rows={ALERTAS_KEYS}
            hint="Os buffers de retrabalho espelham as taxas reais (Lixagem água 49.2%, Pintura Acab. 42.4%, Lixagem polimento 41.3%)."
          />
        )}

        {activeTab === 'trust' && <TrustTab />}

        {activeTab === 'sistema' && (
          <ConfigKeysPanel
            title="Sistema"
            subtitle="Idioma, moeda e formatos · Plan v4 §11.1"
            icon={<Globe size={14} />}
            category="system"
            rows={SYSTEM_KEYS}
            hint="O frontend usa PT-PT directamente nos componentes. Suporte i18n completo (en-US, de-DE) está diferido."
          />
        )}

        {activeTab === 'governanca' && (
          <ConfigKeysPanel
            title="Governança & auto-aprovação"
            subtitle="Quando o sistema decide sozinho vs quando pede aprovação humana"
            icon={<Scale size={14} />}
            category="governance"
            rows={GOVERNANCA_KEYS}
            hint="Os axiomas Spelke e o write-gate continuam a aplicar-se: estas chaves só controlam o que auto-aprova dentro do tecto de risco, nunca contornam o gate de aprovação humana."
          />
        )}

        {activeTab === 'aprovisionamento' && (
          <ConfigKeysPanel
            title="Aprovisionamento"
            subtitle="Pontos de encomenda, alertas de rutura e limites de ajuste de stock"
            icon={<PackageSearch size={14} />}
            category="supply"
            rows={APROVISIONAMENTO_KEYS}
            hint="Afetam o detetor de rutura e o cálculo de ROP — não tocam no stock real do ERP NELO."
          />
        )}

        {activeTab === 'custos-metas' && (
          <ConfigKeysPanel
            title="Metas de custo"
            subtitle="Metas de throughput diário, margem e valor por encomenda"
            icon={<Coins size={14} />}
            category="cost"
            rows={CUSTOS_METAS_KEYS}
            hint="A CoeficienteX é dinheiro (€) — estas metas alimentam o módulo de lucro, nunca o scheduler."
          />
        )}

        {(activeTab === 'scheduling' ||
          activeTab === 'routing' ||
          activeTab === 'moldes' ||
          activeTab === 'alertas') && (
          <div className="mt-3 flex items-start gap-2 px-1">
            <TriangleAlert size={13} className="text-status-yellow mt-0.5" />
            <p className="text-[11px] text-text-dark-tertiary leading-relaxed">
              Alterações de parâmetros do solver só entram em vigor no próximo
              ciclo de scheduling. Os 7 axiomas Spelke são imovíveis e não são
              editáveis por aqui.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
