/**
 * SettingsPage — Configuração (shell · Q.60.R).
 *
 * Os 6 painéis foram decompostos para ./panels/. Tipos partilhados em
 * ./settingsTypes. O componente da página mantém-se aqui (routing de tabs +
 * separadores General/Tenant) com as constantes ConfigKeyRow[] das tabs
 * cura/molds/quality/trust.
 */
import { useEffect, useState } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { Settings, Users, Loader2, Save, RotateCcw, Truck, HardHat, CalendarClock, Hammer, Box, ShieldCheck, Globe, Brain, Beaker } from 'lucide-react';
import { configApi, tenantsApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';
import { DarkPageLayout } from '../../layouts';
import { DarkButton, DarkCard, DarkInput, DarkSelect } from '../../components/dark';
import { type ConfigKeyRow } from './settingsTypes';
import { TransportSettingsPanel } from './panels/TransportSettingsPanel';
import { WorkforceSettingsPanel } from './panels/WorkforceSettingsPanel';
import { SchedulingSettingsPanel } from './panels/SchedulingSettingsPanel';
import { ConfigKeysPanel } from './panels/ConfigKeysPanel';
import { SystemSettingsPanel } from './panels/SystemSettingsPanel';
import { LearningSettingsPanel } from './panels/LearningSettingsPanel';

// Q.21.E — os separadores 'api', 'notifications' e 'integrations' foram
// removidos: eram só painéis "Coming Soon" sem funcionalidade. Voltam
// quando o backend os servir.
type TabType =
  | 'general'
  | 'tenant'
  | 'transport'
  | 'workforce'
  | 'scheduling'
  | 'cura'
  | 'molds'
  | 'quality'
  | 'trust'
  | 'system'
  | 'learning';

interface Tenant {
  id: string;
  name: string;
  status: string;
  created_at: string;
  contact_email?: string;
  contact_phone?: string;
  subscription_level?: string;
}

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabType>('general');
  const toast = useToastContext();
  const queryClient = useQueryClient();

  // Fetch tenant data
  const { data: tenants, isLoading: tenantsLoading } = useQuery<Tenant[]>({
    queryKey: ['tenants', 'current'],
    queryFn: () => tenantsApi.list(),
    retry: false,
  });

  // Sprint Q.13.A — A1: load system.* values from ConfigStore so the
  // General tab reflects what's actually persisted (not just the
  // hardcoded defaults useState picks up). Falls back silently when
  // the backend doesn't have the keys yet.
  const { data: systemConfig } = useQuery({
    queryKey: ['config', 'system'],
    queryFn: () => configApi.listCategory('system'),
    staleTime: 30_000,
  });
  
  const currentTenant = tenants && tenants.length > 0 ? tenants[0] : null;

  // Form states
  const [timezone, setTimezone] = useState('Europe/Lisbon');
  const [currency, setCurrency] = useState('EUR');
  const [language, setLanguage] = useState('pt-PT');
  const [contactEmail, setContactEmail] = useState(currentTenant?.contact_email || '');
  const [contactPhone, setContactPhone] = useState(currentTenant?.contact_phone || '');

  // Sprint Q.13.A — A1: hydrate the General tab from ConfigStore once
  // the system category arrives. Without this, the page shows the
  // hardcoded defaults forever even when the operator already saved
  // a different value last week.
  useEffect(() => {
    if (!systemConfig?.values) return;
    const v = systemConfig.values;
    if (typeof v['language'] === 'string') setLanguage(v['language'] as string);
    if (typeof v['format.currency'] === 'string') {
      setCurrency(v['format.currency'] as string);
    }
    // timezone left out — `system.timezone` not in default_configs yet
    // (deferred to a follow-up seed).
  }, [systemConfig]);

  // Sprint Q.13.A — A1: hydrate the Tenant tab when tenant arrives.
  // Without this, opening the page resets contact fields to '' even
  // when the tenant has them populated.
  useEffect(() => {
    if (!currentTenant) return;
    if (currentTenant.contact_email) setContactEmail(currentTenant.contact_email);
    if (currentTenant.contact_phone) setContactPhone(currentTenant.contact_phone);
  }, [currentTenant]);

  // Sprint Q.13.A — A1: real persistence (was 500ms mock).
  //
  // Two writes happen on Save:
  //   1. system category in ConfigStore: `system.language`, `system.theme`,
  //      `system.format.currency` — seeded in Q.11 Onda 3.6 follow-up
  //      so the keys already exist with defaults.
  //   2. Tenant row update (contact_email, contact_phone) via
  //      `tenantsApi.update(tenantId, ...)`.
  //
  // We bulk-write the ConfigStore keys atomically and then PATCH the
  // tenant row. Either side can fail independently; the Toast reports
  // which write failed so the operator knows what got saved.
  //
  // Note: timezone is currently UI-only (no backend storage); we keep
  // the form state but don't persist it until a `system.timezone` seed
  // lands. Same for general → currency vs system.format.currency
  // (system carries the canonical value).
  const saveMutation = useMutation({
    mutationFn: async (data: {
      timezone: string;
      currency: string;
      language: string;
      contact_email: string;
      contact_phone: string;
    }) => {
      const errors: string[] = [];

      // Step 1: ConfigStore system.* writes.
      try {
        await configApi.bulkSet([
          { category: 'system', key: 'language', value: data.language, data_type: 'string' },
          { category: 'system', key: 'format.currency', value: data.currency, data_type: 'string' },
        ]);
      } catch (err) {
        errors.push(
          `ConfigStore: ${err instanceof Error ? err.message : String(err)}`,
        );
      }

      // Step 2: Tenant row patch (only when we have a tenant + something
      // to write; skip silently when contact fields are empty so a user
      // landing on the page doesn't accidentally null out the tenant
      // record).
      if (currentTenant && (data.contact_email || data.contact_phone)) {
        try {
          await tenantsApi.update(currentTenant.id, {
            contact_email: data.contact_email,
            contact_phone: data.contact_phone,
          });
        } catch (err) {
          errors.push(
            `Tenant: ${err instanceof Error ? err.message : String(err)}`,
          );
        }
      }

      if (errors.length > 0) {
        throw new Error(errors.join(' · '));
      }
      return data;
    },
    onSuccess: () => {
      // Invalidate so the next render picks up persisted values + audit.
      queryClient.invalidateQueries({ queryKey: ['config', 'system'] });
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
      toast.success('Settings saved successfully!');
    },
    onError: (err) => {
      const msg = err instanceof Error ? err.message : 'Error saving settings.';
      toast.error(msg);
    },
  });

  const tabs = [
    { id: 'general' as TabType, label: 'General', icon: Settings },
    { id: 'tenant' as TabType, label: 'Tenant', icon: Users },
    { id: 'scheduling' as TabType, label: 'Scheduling', icon: CalendarClock },
    { id: 'transport' as TabType, label: 'Transporte', icon: Truck },
    { id: 'workforce' as TabType, label: 'Workforce', icon: HardHat },
    { id: 'cura' as TabType, label: 'Cura/Secagem', icon: Beaker },
    { id: 'molds' as TabType, label: 'Moldes', icon: Hammer },
    { id: 'quality' as TabType, label: 'Qualidade', icon: Box },
    { id: 'trust' as TabType, label: 'Trust Index', icon: ShieldCheck },
    { id: 'learning' as TabType, label: 'Aprendizagem', icon: Brain },
    { id: 'system' as TabType, label: 'Sistema', icon: Globe },
  ];

  const handleSave = () => {
    saveMutation.mutate({
      timezone,
      currency,
      language,
      contact_email: contactEmail,
      contact_phone: contactPhone,
    });
  };

  const handleReset = () => {
    setTimezone('Europe/Lisbon');
    setCurrency('EUR');
    setLanguage('pt-PT');
    setContactEmail(currentTenant?.contact_email || '');
    setContactPhone(currentTenant?.contact_phone || '');
    saveMutation.reset();
  };

  const timezoneOptions = [
    { value: 'Europe/Lisbon', label: 'Europe/Lisbon (UTC+0)' },
    { value: 'Europe/London', label: 'Europe/London (UTC+0)' },
    { value: 'America/New_York', label: 'America/New York (UTC-5)' },
    { value: 'America/Sao_Paulo', label: 'America/São Paulo (UTC-3)' },
    { value: 'Asia/Tokyo', label: 'Asia/Tokyo (UTC+9)' },
  ];

  const currencyOptions = [
    { value: 'EUR', label: 'EUR (€)' },
    { value: 'USD', label: 'USD ($)' },
    { value: 'GBP', label: 'GBP (£)' },
    { value: 'BRL', label: 'BRL (R$)' },
    { value: 'JPY', label: 'JPY (¥)' },
  ];

  const languageOptions = [
    { value: 'pt-PT', label: 'Português (PT)' },
    { value: 'pt-BR', label: 'Português (BR)' },
    { value: 'en-US', label: 'English (US)' },
    { value: 'es-ES', label: 'Español' },
  ];

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Sistema' }, { label: 'Definições' }]}
      title="Settings"
      subtitle="Manage system and tenant settings"
      icon={<Settings size={20} />}
      actions={
        <div className="flex items-center gap-2">
          <DarkButton
            variant="secondary"
            icon={<RotateCcw size={16} />}
            onClick={handleReset}
            disabled={saveMutation.isPending}
          >
            Reset
          </DarkButton>
          <DarkButton
            icon={saveMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            onClick={handleSave}
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
          </DarkButton>
        </div>
      }
    >
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Sidebar Tabs */}
        <div className="lg:w-56 flex-shrink-0">
          <DarkCard padding="sm">
            <nav className="space-y-1">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${
                      activeTab === tab.id
                        ? 'bg-accent/15 text-accent font-medium border border-accent/30'
                        : 'text-text-secondary hover:bg-bg-elevated hover:text-text-white'
                    }`}
                  >
                    <Icon size={18} />
                    <span className="text-sm">{tab.label}</span>
                  </button>
                );
              })}
            </nav>
          </DarkCard>
        </div>

        {/* Content */}
        <div className="flex-1">
          {activeTab === 'general' && (
            <DarkCard title="General Settings" subtitle="Configure timezone, currency, and language">
              <div className="space-y-5 mt-4">
                <DarkSelect
                  label="Timezone"
                  options={timezoneOptions}
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  icon={<Settings size={16} />}
                />

                <DarkSelect
                  label="Currency"
                  options={currencyOptions}
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                />

                <DarkSelect
                  label="Language"
                  options={languageOptions}
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                />
              </div>
            </DarkCard>
          )}

          {activeTab === 'tenant' && (
            <DarkCard title="Tenant Information" subtitle="View and edit tenant details">
              {tenantsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 size={24} className="text-accent animate-spin" />
                </div>
              ) : currentTenant ? (
                <div className="space-y-5 mt-4">
                  <DarkInput
                    label="Tenant Name"
                    value={currentTenant.name}
                    disabled
                    hint="Name cannot be changed"
                  />

                  <DarkInput
                    label="Tenant ID"
                    value={currentTenant.id}
                    disabled
                    className="font-mono text-sm"
                  />

                  <DarkInput
                    label="Status"
                    value={currentTenant.status}
                    disabled
                  />

                  <DarkInput
                    label="Contact Email"
                    type="email"
                    value={contactEmail}
                    onChange={(e) => setContactEmail(e.target.value)}
                    placeholder="contact@example.com"
                  />

                  <DarkInput
                    label="Contact Phone"
                    type="tel"
                    value={contactPhone}
                    onChange={(e) => setContactPhone(e.target.value)}
                    placeholder="+351 123 456 789"
                  />

                  {currentTenant.subscription_level && (
                    <DarkInput
                      label="Subscription Level"
                      value={currentTenant.subscription_level}
                      disabled
                    />
                  )}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Users size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                  <p className="text-text-secondary">No tenant information available.</p>
                </div>
              )}
            </DarkCard>
          )}

          {/* Q.21.E — painéis "Coming Soon" (api/notifications/
              integrations) removidos com os respectivos separadores. */}

          {activeTab === 'transport' && <TransportSettingsPanel />}

          {activeTab === 'workforce' && <WorkforceSettingsPanel />}

          {activeTab === 'scheduling' && <SchedulingSettingsPanel />}

          {activeTab === 'cura' && (
            <ConfigKeysPanel
              title="Cura / Secagem"
              subtitle="Plan v4 §3.8 · 16 transições obrigatórias (min_gap_hours)"
              category="planning"
              rows={CURA_KEYS}
              hint="Os 16 pares fase-a-fase têm tempos mínimos físicos (cura de resina, secagem de tinta). Estão hardcoded no seed FactoryState — esta tab edita os overrides via tenant_configuration. As transições não listadas têm gap=0 (filas minimizáveis)."
            />
          )}
          {activeTab === 'molds' && (
            <ConfigKeysPanel
              title="Moldes"
              subtitle="Plan v4 §3.5 · QA10/CG12/AL08"
              category="mold"
              rows={MOLD_KEYS}
              hint="O threshold de manutenção é H2 do plano (placeholder pending CEO). Pesos health_weight.* devem somar 1.0."
            />
          )}
          {activeTab === 'quality' && (
            <ConfigKeysPanel
              title="Qualidade"
              subtitle="Plan v4 §3.3 · QA01-QA11"
              category="quality"
              rows={QUALITY_KEYS}
              hint="Factor de capacidade 1.5× nas lixagens espelha a taxa real de retrabalho (Lixagem água 49.2%, Pintura Acab 42.4%, Lixagem polim 41.3%)."
            />
          )}
          {activeTab === 'trust' && (
            <ConfigKeysPanel
              title="Trust Index v2"
              subtitle="Blueprint v2.0 §4.5 · 7 componentes + 5 gates"
              category="trust"
              rows={TRUST_KEYS}
              hint="Componentes (peso): C/V/F/K/P/A/E. Gates: 0.50 (solver-only), 0.60 (P90), 0.70 (auto-reorder), 0.75 (auto-commit), 0.80 (quality disposition)."
            />
          )}
          {activeTab === 'system' && <SystemSettingsPanel />}
          {activeTab === 'learning' && <LearningSettingsPanel />}
        </div>
      </div>
    </DarkPageLayout>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Sprint Q.2 — Transporte panel (consumes ConfigStore via configApi)
// ───────────────────────────────────────────────────────────────────────────

const CURA_KEYS: ConfigKeyRow[] = [
  // Currently the gaps live in the Python seed (state.py NELO_CURING_GAPS_SEED);
  // tenant_configuration only carries the buffer factor + queue defaults.
  {
    key: 'queue_time.median_h',
    label: 'Mediana queue inter-fase (h)',
    hint: 'PL22 — 5.2h mediana. Aplica-se a todas as transições não listadas no seed de cura.',
    dataType: 'float',
  },
  {
    key: 'queue_time.p90_h',
    label: 'P90 queue inter-fase (h)',
    hint: 'PL22 — 69.2h. Buffer maior usado quando TI < 0.60.',
    dataType: 'float',
  },
  {
    key: 'buffer.post_desmolde_h',
    label: 'Buffer pós-Desmolde (h)',
    hint: 'PL21 — 4h. Desmolde é o ponto QC de facto (96.4% erros detectados).',
    dataType: 'float',
  },
];

// ── Moldes (Plan v4 §3.5) ────────────────────────────────────────────────
const MOLD_KEYS: ConfigKeyRow[] = [
  {
    key: 'maintenance_threshold_cycles',
    label: 'Threshold manutenção (ciclos)',
    hint: 'H2 PLACEHOLDER — pending CEO. ≤0 desliga MOLD_MAINT_DUE alerts.',
    dataType: 'int',
  },
  {
    key: 'health_weight.cycles',
    label: 'Peso health: ciclos',
    hint: 'Default 0.40. Soma com defects_90d + days_since_maint + rework_rate = 1.0.',
    dataType: 'float',
  },
  {
    key: 'health_weight.defects_90d',
    label: 'Peso health: defeitos 90d',
    hint: 'Default 0.20.',
    dataType: 'float',
  },
  {
    key: 'health_weight.days_since_maint',
    label: 'Peso health: dias desde manut',
    hint: 'Default 0.20.',
    dataType: 'float',
  },
  {
    key: 'health_weight.rework_rate',
    label: 'Peso health: taxa retrabalho',
    hint: 'Default 0.20.',
    dataType: 'float',
  },
  {
    key: 'health.red_threshold',
    label: 'Health score → vermelho',
    hint: 'Default 40. Score abaixo bloqueia uso do molde.',
    dataType: 'int',
  },
  {
    key: 'health.yellow_threshold',
    label: 'Health score → amarelo',
    hint: 'Default 70.',
    dataType: 'int',
  },
];

// ── Qualidade (Plan v4 §3.3 + QA07/QA11) ────────────────────────────────
const QUALITY_KEYS: ConfigKeyRow[] = [
  {
    key: 'risk_alert_threshold',
    label: 'Threshold P(erro) alerta',
    hint: 'QA07 — emit preventive alert quando P(erro) > threshold. Default 0.40.',
    dataType: 'float',
  },
  {
    key: 'rework_buffer_pct.sanding_water',
    label: 'Buffer Lixagem água (%)',
    hint: 'QA11 — 20% (19,149 retornos histórico, 49.2% taxa real).',
    dataType: 'float',
  },
  {
    key: 'rework_buffer_pct.sanding_polish',
    label: 'Buffer Lixagem polim. (%)',
    hint: 'QA11 — 20% (16,221 retornos, 41.3% taxa real).',
    dataType: 'float',
  },
  {
    key: 'rework_buffer_pct.painting_finishing',
    label: 'Buffer Pintura Acab. (%)',
    hint: 'QA11 — 18% (12,826 retornos, 42.4% taxa real).',
    dataType: 'float',
  },
  {
    key: 'skill_bottleneck_threshold',
    label: 'Skill bottleneck (workers aptos)',
    hint: 'WF12 — fases com < N workers aptos viram skill bottleneck (Pintura=22, Colagem=13).',
    dataType: 'int',
  },
];

// ── Trust Index (Blueprint §4.5) ─────────────────────────────────────────
const TRUST_KEYS: ConfigKeyRow[] = [
  { key: 'weights.completeness', label: 'Peso C — Completeness', hint: 'Default 0.15.', dataType: 'float' },
  { key: 'weights.validity', label: 'Peso V — Validity', hint: 'Default 0.20.', dataType: 'float' },
  { key: 'weights.freshness', label: 'Peso F — Freshness', hint: 'Default 0.15. exp(-age/tau).', dataType: 'float' },
  { key: 'weights.consistency', label: 'Peso K — Consistency', hint: 'Default 0.20. exp(-|z|/kappa).', dataType: 'float' },
  { key: 'weights.provenance', label: 'Peso P — Provenance', hint: 'Default 0.15. sensor>historian>erp>manual.', dataType: 'float' },
  { key: 'weights.anomaly', label: 'Peso A — Anomaly', hint: 'Default 0.10. 1 - p(anomaly).', dataType: 'float' },
  { key: 'weights.evidence', label: 'Peso E — Evidence', hint: 'Default 0.05.', dataType: 'float' },
  { key: 'gates.solver_suggestion_only', label: 'Gate 1: solver suggestion-only', hint: 'TI<0.50 → solver não compromete.', dataType: 'float' },
  { key: 'gates.use_p90_durations', label: 'Gate 2: P90 durations', hint: 'TI<0.60 → buffer maior nas durações.', dataType: 'float' },
  { key: 'gates.auto_reorder', label: 'Gate 3: auto-reorder', hint: 'TI<0.70 → reorder bloqueado.', dataType: 'float' },
  { key: 'gates.auto_commit', label: 'Gate 4: auto-commit', hint: 'TI<0.75 → human approval obrigatório.', dataType: 'float' },
  { key: 'gates.quality_disposition', label: 'Gate 5: quality disposition', hint: 'TI<0.80 → quality moves bloqueados.', dataType: 'float' },
  { key: 'freshness.tau_seconds_curated', label: 'Freshness tau (segundos)', hint: 'Default 86400 (1 dia).', dataType: 'float' },
  { key: 'consistency.kappa', label: 'Consistency kappa', hint: 'Default 2.0. softening do z-score.', dataType: 'float' },
];

// ── Sistema panel (idioma + tema stub) ───────────────────────────────────
