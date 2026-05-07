import { useEffect, useMemo, useState } from 'react';
import { useQueries, useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import {
  Settings, Users, Key, Bell, Plug, Loader2, Save, RotateCcw, Truck, HardHat,
  CalendarClock, Hammer, Box, ShieldCheck, Globe, Brain, Beaker,
} from 'lucide-react';
import { configApi, tenantsApi, learningApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';
import { DarkPageLayout } from '../../layouts';
import {
  AuditTrailRow,
  DarkBadge,
  DarkButton,
  DarkCard,
  DarkInput,
  DarkSelect,
} from '../../components/dark';

type TabType =
  | 'general'
  | 'tenant'
  | 'api'
  | 'notifications'
  | 'integrations'
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
    { id: 'api' as TabType, label: 'API', icon: Key },
    { id: 'notifications' as TabType, label: 'Notifications', icon: Bell },
    { id: 'integrations' as TabType, label: 'Integrations', icon: Plug },
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

          {activeTab === 'api' && (
            <DarkCard title="API Configuration" subtitle="Manage API keys and access">
              <div className="text-center py-12">
                <Key size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                <p className="text-text-secondary font-medium">Coming Soon</p>
                <p className="text-text-tertiary text-sm mt-1">API configuration functionality is in development.</p>
              </div>
            </DarkCard>
          )}

          {activeTab === 'notifications' && (
            <DarkCard title="Notifications" subtitle="Configure notification preferences">
              <div className="text-center py-12">
                <Bell size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                <p className="text-text-secondary font-medium">Coming Soon</p>
                <p className="text-text-tertiary text-sm mt-1">Notification settings are in development.</p>
              </div>
            </DarkCard>
          )}

          {activeTab === 'integrations' && (
            <DarkCard title="Integrations" subtitle="Connect with external services">
              <div className="text-center py-12">
                <Plug size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                <p className="text-text-secondary font-medium">Coming Soon</p>
                <p className="text-text-tertiary text-sm mt-1">Integration with external services is in development.</p>
              </div>
            </DarkCard>
          )}

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

const TRANSPORT_KEYS = [
  {
    key: 'transport.default_batch_size',
    label: 'Capacidade do camião (barcos)',
    hint: 'CG11 — moda histórica = 26, CEO disse 50/camião.',
    dataType: 'int' as const,
    parse: (v: string) => Number.parseInt(v, 10),
  },
  {
    key: 'transport.delivery_buffer_h',
    label: 'Buffer antes da expedição (horas)',
    hint: 'Quantas horas antes da transport_date a OF tem de estar pronta.',
    dataType: 'float' as const,
    parse: (v: string) => Number.parseFloat(v),
  },
];

function TransportSettingsPanel() {
  const queryClient = useQueryClient();
  const toast = useToastContext();
  const { data, isLoading, error } = useQuery({
    queryKey: ['config', 'planning'],
    queryFn: () => configApi.listCategory('planning'),
    staleTime: 60_000,
  });

  // Local edit buffer keyed by config-key.
  const [edits, setEdits] = useState<Record<string, string>>({});

  // Hydrate edit buffer from server values whenever they refetch.
  useEffect(() => {
    if (!data) return;
    const next: Record<string, string> = {};
    for (const row of TRANSPORT_KEYS) {
      const raw = data.values[row.key];
      next[row.key] = raw == null ? '' : String(raw);
    }
    setEdits((prev) => ({ ...next, ...prev }));
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: async (changes: { key: string; value: unknown; dataType: 'int' | 'float' }[]) =>
      configApi.bulkSet(
        changes.map((c) => ({
          category: 'planning',
          key: c.key,
          value: c.value,
          data_type: c.dataType,
        })),
      ),
    onSuccess: () => {
      toast.success('Configuração guardada.');
      queryClient.invalidateQueries({ queryKey: ['config', 'planning'] });
    },
    onError: (err) => {
      toast.error(`Erro ao guardar: ${(err as Error).message}`);
    },
  });

  const handleSave = () => {
    const changes = TRANSPORT_KEYS.flatMap((row) => {
      const raw = edits[row.key] ?? '';
      if (raw === '') return [];
      const parsed = row.parse(raw);
      if (Number.isNaN(parsed)) return [];
      const current = data?.values[row.key];
      if (current === parsed) return [];
      return [{ key: row.key, value: parsed, dataType: row.dataType }];
    });
    if (changes.length === 0) {
      toast.info('Nada para guardar.');
      return;
    }
    saveMutation.mutate(changes);
  };

  return (
    <DarkCard title="Transporte / Despacho" subtitle="Plan v4 §11.1 · ConfigStore">
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={24} className="text-accent animate-spin" />
        </div>
      ) : error ? (
        <p className="text-sm text-red-400 py-4">
          Falha ao carregar configuração: {(error as Error).message}
        </p>
      ) : (
        <div className="space-y-4 mt-4">
          {TRANSPORT_KEYS.map((row) => (
            <DarkInput
              key={row.key}
              label={row.label}
              hint={row.hint}
              type="number"
              value={edits[row.key] ?? ''}
              onChange={(e) => setEdits((s) => ({ ...s, [row.key]: e.target.value }))}
            />
          ))}
          <div className="flex justify-end gap-2 pt-2">
            <DarkButton
              variant="primary"
              icon={saveMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              onClick={handleSave}
              disabled={saveMutation.isPending}
            >
              Guardar
            </DarkButton>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Cada alteração escreve em <code>tenant_configuration.planning.*</code> com audit
            (utilizador + timestamp + valor anterior). Ver histórico em DQA → Audit Trail.
          </p>
        </div>
      )}
    </DarkCard>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Sprint Q.3 — Workforce panel (consumes ConfigStore via configApi)
// ───────────────────────────────────────────────────────────────────────────

const WORKFORCE_KEYS: Array<{
  category: 'workforce' | 'planning';
  key: string;
  label: string;
  hint: string;
  dataType: 'int' | 'bool';
  parse: (v: string) => number | boolean;
}> = [
  {
    category: 'workforce',
    key: 'skill_tier.junior_max_months',
    label: 'Tier junior — meses máx',
    hint: 'WF05 — abaixo deste número de meses, tier=junior. Default 5.',
    dataType: 'int',
    parse: (v) => Number.parseInt(v, 10),
  },
  {
    category: 'workforce',
    key: 'skill_tier.mid_max_months',
    label: 'Tier mid — meses máx',
    hint: 'WF05 — entre junior_max e mid_max, tier=mid. Default 12.',
    dataType: 'int',
    parse: (v) => Number.parseInt(v, 10),
  },
  {
    category: 'planning',
    key: 'laminagem.require_pair',
    label: 'Laminagem exige par (boolean)',
    hint: 'WF11 — historical 88.5% pair. true=obrigatório, false=desligado.',
    dataType: 'bool',
    parse: (v) => v === 'true' || v === '1',
  },
  {
    category: 'planning',
    key: 'laminagem.require_chefe',
    label: 'Par obrigatoriamente com chefe',
    hint: 'true=par tem de incluir um senior; false=permite par junior+junior.',
    dataType: 'bool',
    parse: (v) => v === 'true' || v === '1',
  },
];

function WorkforceSettingsPanel() {
  const queryClient = useQueryClient();
  const toast = useToastContext();

  const workforceConfig = useQuery({
    queryKey: ['config', 'workforce'],
    queryFn: () => configApi.listCategory('workforce'),
    staleTime: 60_000,
  });
  const planningConfig = useQuery({
    queryKey: ['config', 'planning'],
    queryFn: () => configApi.listCategory('planning'),
    staleTime: 60_000,
  });

  const [edits, setEdits] = useState<Record<string, string>>({});

  useEffect(() => {
    const next: Record<string, string> = {};
    for (const row of WORKFORCE_KEYS) {
      const src =
        row.category === 'workforce' ? workforceConfig.data : planningConfig.data;
      const raw = src?.values?.[row.key];
      next[row.key] = raw == null ? '' : String(raw);
    }
    setEdits((prev) => ({ ...next, ...prev }));
  }, [workforceConfig.data, planningConfig.data]);

  const saveMutation = useMutation({
    mutationFn: async (
      changes: Array<{ category: string; key: string; value: unknown; dataType: 'int' | 'bool' }>,
    ) =>
      configApi.bulkSet(
        changes.map((c) => ({
          category: c.category,
          key: c.key,
          value: c.value,
          data_type: c.dataType,
        })),
      ),
    onSuccess: () => {
      toast.success('Workforce config gravado.');
      queryClient.invalidateQueries({ queryKey: ['config'] });
    },
    onError: (err) => {
      toast.error(`Erro ao guardar: ${(err as Error).message}`);
    },
  });

  const handleSave = () => {
    const changes = WORKFORCE_KEYS.flatMap((row) => {
      const raw = edits[row.key] ?? '';
      if (raw === '') return [];
      const parsed = row.parse(raw);
      const src =
        row.category === 'workforce' ? workforceConfig.data : planningConfig.data;
      const current = src?.values?.[row.key];
      if (current === parsed) return [];
      return [
        { category: row.category, key: row.key, value: parsed, dataType: row.dataType },
      ];
    });
    if (changes.length === 0) {
      toast.info('Nada para guardar.');
      return;
    }
    saveMutation.mutate(changes);
  };

  const isLoading = workforceConfig.isLoading || planningConfig.isLoading;
  const error = workforceConfig.error ?? planningConfig.error;

  return (
    <DarkCard title="Workforce" subtitle="Plan v4 §5 / WF05 / WF11 · ConfigStore">
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={24} className="text-accent animate-spin" />
        </div>
      ) : error ? (
        <p className="text-sm text-red-400 py-4">
          Falha ao carregar configuração: {(error as Error).message}
        </p>
      ) : (
        <div className="space-y-4 mt-4">
          {WORKFORCE_KEYS.map((row) => (
            <DarkInput
              key={row.key}
              label={row.label}
              hint={row.hint}
              type={row.dataType === 'bool' ? 'text' : 'number'}
              placeholder={row.dataType === 'bool' ? 'true | false' : ''}
              value={edits[row.key] ?? ''}
              onChange={(e) => setEdits((s) => ({ ...s, [row.key]: e.target.value }))}
            />
          ))}
          <div className="flex justify-end gap-2 pt-2">
            <DarkButton
              variant="primary"
              icon={saveMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              onClick={handleSave}
              disabled={saveMutation.isPending}
            >
              Guardar
            </DarkButton>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Tudo editável via <code>tenant_configuration</code>. Cada override grava
            audit (quem/quando/valor anterior). O override do gestor SEMPRE ganha sobre
            regras automáticas (Plan v4 §11.3 hierarquia).
          </p>
        </div>
      )}
    </DarkCard>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Sprint Q.4 — Scheduling panel (CPO fitness + budgets + MAP-Elites)
// ───────────────────────────────────────────────────────────────────────────

const SCHEDULING_KEYS: Array<{
  key: string;
  label: string;
  hint: string;
  dataType: 'int' | 'float';
}> = [
  {
    key: 'fitness.weight.makespan',
    label: 'Peso fitness — makespan',
    hint: 'Default 0.20. Mede o tempo total do horizonte.',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.tardiness_transport',
    label: 'Peso fitness — tardiness transporte',
    hint: 'Default 0.25. Datas de transporte são king (PL14).',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.idle_operators',
    label: 'Peso fitness — idle operadores',
    hint: 'Default 0.15. Penaliza operadores parados.',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.setup_time',
    label: 'Peso fitness — setup time',
    hint: 'Default 0.15. Tempo de troca de molde/cor.',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.quality_risk',
    label: 'Peso fitness — quality risk',
    hint: 'Default 0.10. Mean P(erro) das ops.',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.throughput_eur_day',
    label: 'Peso fitness — throughput €/dia',
    hint: 'Default 0.15. Negativado internamente (mais €/dia → fitness menor).',
    dataType: 'float',
  },
  {
    key: 'cpo.total_budget_s',
    label: 'CPO budget total (s)',
    hint: 'Tempo end-to-end do cascade (Blueprint §5.5: 60s alvo).',
    dataType: 'float',
  },
  {
    key: 'cpo.gen_count',
    label: 'GA gerações',
    hint: 'Blueprint v2.0 exige 200; default era 50 em Sprint E.',
    dataType: 'int',
  },
  {
    key: 'queue_time.median_h',
    label: 'Mediana queue inter-fase (h)',
    hint: 'PL22 — 5.2h mediana entre fases consecutivas.',
    dataType: 'float',
  },
];

function SchedulingSettingsPanel() {
  const queryClient = useQueryClient();
  const toast = useToastContext();

  const { data, isLoading, error } = useQuery({
    queryKey: ['config', 'planning'],
    queryFn: () => configApi.listCategory('planning'),
    staleTime: 60_000,
  });
  const [edits, setEdits] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!data) return;
    const next: Record<string, string> = {};
    for (const row of SCHEDULING_KEYS) {
      const raw = data.values[row.key];
      next[row.key] = raw == null ? '' : String(raw);
    }
    setEdits((prev) => ({ ...next, ...prev }));
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: async (
      changes: Array<{ key: string; value: number; dataType: 'int' | 'float' }>,
    ) =>
      configApi.bulkSet(
        changes.map((c) => ({
          category: 'planning',
          key: c.key,
          value: c.value,
          data_type: c.dataType,
        })),
      ),
    onSuccess: () => {
      toast.success('Scheduling config gravado.');
      queryClient.invalidateQueries({ queryKey: ['config', 'planning'] });
    },
    onError: (err) => toast.error(`Erro: ${(err as Error).message}`),
  });

  const handleSave = () => {
    const changes = SCHEDULING_KEYS.flatMap((row) => {
      const raw = edits[row.key] ?? '';
      if (raw === '') return [];
      const parsed =
        row.dataType === 'int' ? Number.parseInt(raw, 10) : Number.parseFloat(raw);
      if (Number.isNaN(parsed)) return [];
      const current = data?.values[row.key];
      if (current === parsed) return [];
      return [{ key: row.key, value: parsed, dataType: row.dataType }];
    });
    if (changes.length === 0) {
      toast.info('Nada para guardar.');
      return;
    }
    saveMutation.mutate(changes);
  };

  const weightSum = SCHEDULING_KEYS.filter((r) => r.key.startsWith('fitness.weight.'))
    .map((r) => Number.parseFloat(edits[r.key] ?? '0'))
    .filter((v) => !Number.isNaN(v))
    .reduce((acc, v) => acc + v, 0);

  return (
    <DarkCard title="Scheduling / CPO" subtitle="Plan v4 §11.1 / Blueprint v2.0 §5.5">
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={24} className="text-accent animate-spin" />
        </div>
      ) : error ? (
        <p className="text-sm text-red-400 py-4">
          Falha ao carregar: {(error as Error).message}
        </p>
      ) : (
        <div className="space-y-4 mt-4">
          {SCHEDULING_KEYS.map((row) => (
            <DarkInput
              key={row.key}
              label={row.label}
              hint={row.hint}
              type="number"
              value={edits[row.key] ?? ''}
              onChange={(e) => setEdits((s) => ({ ...s, [row.key]: e.target.value }))}
            />
          ))}

          <div
            className={`p-2 rounded text-xs ${
              Math.abs(weightSum - 1.0) < 0.005
                ? 'bg-emerald-500/10 text-emerald-300'
                : 'bg-amber-500/10 text-amber-300'
            }`}
          >
            Soma dos pesos fitness: {weightSum.toFixed(3)}{' '}
            {Math.abs(weightSum - 1.0) < 0.005
              ? '✓ normalizado'
              : '⚠ deveria ser ≈ 1.000 — o motor renormaliza defensivamente'}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <DarkButton
              variant="primary"
              icon={
                saveMutation.isPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Save size={14} />
                )
              }
              onClick={handleSave}
              disabled={saveMutation.isPending}
            >
              Guardar
            </DarkButton>
          </div>

          <p className="text-xs text-slate-500 mt-2">
            Os pesos definem como o CPO compara alternativas. Plan v4 §11.3
            hierarquia: override do gestor SEMPRE ganha sobre regras aprendidas.
          </p>
        </div>
      )}
    </DarkCard>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Sprint Q.6 — Generic ConfigKeysPanel (powers Cura/Moldes/Quality/Trust)
// ───────────────────────────────────────────────────────────────────────────

interface ConfigKeyRow {
  key: string;
  label: string;
  hint: string;
  dataType: 'int' | 'float' | 'bool' | 'string';
}

function ConfigKeysPanel({
  title,
  subtitle,
  category,
  rows,
  hint,
}: {
  title: string;
  subtitle: string;
  category: string;
  rows: ConfigKeyRow[];
  hint?: string;
}) {
  const queryClient = useQueryClient();
  const toast = useToastContext();

  const { data, isLoading, error } = useQuery({
    queryKey: ['config', category],
    queryFn: () => configApi.listCategory(category),
    staleTime: 60_000,
  });

  // Sprint Q.9 Onda 3.7 — fetch the per-key ConfigEntry so we can show
  // who changed it / when / why. listCategory only returns the value;
  // get() returns the full audit metadata (id, last_modified_by/at).
  // Each panel has ≤ ~12 rows so the round-trips are cheap.
  const entryQueries = useQueries({
    queries: rows.map((row) => ({
      queryKey: ['config', category, row.key, 'entry'],
      queryFn: async () => {
        try {
          return await configApi.get(category, row.key);
        } catch (err) {
          // 404 = key never set on this tenant. Return null so the row
          // can render the default + "por definir" affordance.
          if (err instanceof Error && err.message.includes('404')) {
            return null;
          }
          throw err;
        }
      },
      staleTime: 60_000,
    })),
  });
  const entriesByKey = useMemo(() => {
    const m: Record<string, NonNullable<typeof entryQueries[number]['data']>> = {};
    rows.forEach((row, idx) => {
      const e = entryQueries[idx]?.data;
      if (e) m[row.key] = e;
    });
    return m;
  }, [rows, entryQueries]);

  const [edits, setEdits] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!data) return;
    const next: Record<string, string> = {};
    for (const row of rows) {
      const raw = data.values[row.key];
      next[row.key] = raw == null ? '' : String(raw);
    }
    setEdits((prev) => ({ ...next, ...prev }));
  }, [data, rows]);

  const saveMutation = useMutation({
    mutationFn: async (
      changes: Array<{ key: string; value: unknown; dataType: ConfigKeyRow['dataType'] }>,
    ) =>
      configApi.bulkSet(
        changes.map((c) => ({
          category,
          key: c.key,
          value: c.value,
          data_type:
            c.dataType === 'bool'
              ? 'bool'
              : c.dataType === 'int'
              ? 'int'
              : c.dataType === 'string'
              ? 'string'
              : 'float',
        })),
      ),
    onSuccess: () => {
      toast.success('Config gravada.');
      queryClient.invalidateQueries({ queryKey: ['config', category] });
    },
    onError: (err) => toast.error(`Erro: ${(err as Error).message}`),
  });

  const resetMutation = useMutation({
    mutationFn: (key: string) => configApi.resetToDefault(category, key),
    onSuccess: () => {
      toast.success('Reset ao default aplicado.');
      queryClient.invalidateQueries({ queryKey: ['config', category] });
    },
    onError: (err) => toast.error(`Reset falhou: ${(err as Error).message}`),
  });

  const parseValue = (row: ConfigKeyRow, raw: string): unknown => {
    if (raw === '') return null;
    switch (row.dataType) {
      case 'int':
        return Number.parseInt(raw, 10);
      case 'float':
        return Number.parseFloat(raw);
      case 'bool':
        return raw === 'true' || raw === '1';
      default:
        return raw;
    }
  };

  const handleSave = () => {
    const changes = rows.flatMap((row) => {
      const raw = edits[row.key] ?? '';
      if (raw === '') return [];
      const parsed = parseValue(row, raw);
      if (parsed === null) return [];
      if (typeof parsed === 'number' && Number.isNaN(parsed)) return [];
      const current = data?.values[row.key];
      if (current === parsed) return [];
      return [{ key: row.key, value: parsed, dataType: row.dataType }];
    });
    if (changes.length === 0) {
      toast.info('Nada para guardar.');
      return;
    }
    saveMutation.mutate(changes);
  };

  return (
    <DarkCard title={title} subtitle={subtitle}>
      {hint && (
        <p className="text-xs text-slate-500 mb-3 px-1 italic">{hint}</p>
      )}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={24} className="text-accent animate-spin" />
        </div>
      ) : error ? (
        <p className="text-sm text-red-400 py-4">
          Falha: {(error as Error).message}
        </p>
      ) : (
        <div className="space-y-4 mt-2">
          {rows.map((row) => {
            const entry = entriesByKey[row.key] ?? null;
            const currentValue = data?.values[row.key];
            const editedValue = edits[row.key] ?? '';
            // The displayed "default" value in the AuditTrailRow is the
            // current backend value cast to string — that's the value
            // a "reset" would target. (The seeded default ships in
            // `default_configs.py` and the backend's
            // `configApi.resetToDefault` knows the canonical default.)
            const defaultRender =
              currentValue === undefined || currentValue === null
                ? null
                : String(currentValue);
            return (
              <div key={row.key} className="space-y-1">
                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <DarkInput
                      label={row.label}
                      hint={row.hint}
                      type={
                        row.dataType === 'bool' || row.dataType === 'string'
                          ? 'text'
                          : 'number'
                      }
                      placeholder={
                        row.dataType === 'bool'
                          ? 'true | false'
                          : row.dataType === 'string'
                          ? '—'
                          : ''
                      }
                      value={editedValue}
                      onChange={(e) =>
                        setEdits((s) => ({ ...s, [row.key]: e.target.value }))
                      }
                    />
                  </div>
                </div>
                {/* Sprint Q.9 Onda 3.7 — show last_changed_by/at + reset
                    button via the shared AuditTrailRow component. The
                    audit trail comes from configApi.get(category, key)
                    fetched in entryQueries above. */}
                <AuditTrailRow
                  lastChangedBy={entry?.last_modified_by ?? null}
                  lastChangedAt={entry?.last_modified_at ?? null}
                  defaultValue={defaultRender}
                  isOverridden={editedValue !== '' && editedValue !== defaultRender}
                  onReset={
                    entry
                      ? () => resetMutation.mutate(row.key)
                      : undefined
                  }
                  className="px-1"
                />
              </div>
            );
          })}
          <div className="flex justify-end gap-2 pt-2">
            <DarkButton
              variant="primary"
              icon={
                saveMutation.isPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Save size={14} />
                )
              }
              onClick={handleSave}
              disabled={saveMutation.isPending}
            >
              Guardar
            </DarkButton>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Cada chave grava um audit row em <code>tenant_configuration.{category}.*</code>.
            O botão <RotateCcw size={10} className="inline" /> repõe o default seeded.
          </p>
        </div>
      )}
    </DarkCard>
  );
}

// ── Cura/Secagem (Plan v4 §3.8 — 16 transições) ─────────────────────────
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
function SystemSettingsPanel() {
  const toast = useToastContext();
  const [language, setLanguage] = useState<'pt-PT' | 'en-US' | 'de-DE'>('pt-PT');

  return (
    <DarkCard title="Sistema" subtitle="Idioma · tema · formatos (Plan v4 §11.1)">
      <div className="space-y-4 mt-4">
        <DarkSelect
          label="Idioma da UI"
          options={[
            { value: 'pt-PT', label: 'Português (Portugal)' },
            { value: 'en-US', label: 'English (US) — coming soon' },
            { value: 'de-DE', label: 'Deutsch — coming soon' },
          ]}
          value={language}
          onChange={(e) => setLanguage(e.target.value as 'pt-PT' | 'en-US' | 'de-DE')}
        />
        <p className="text-xs text-slate-500">
          O frontend Q.6 usa apenas PT-PT directamente nos componentes. Suporte
          completo i18n (en-US, de-DE) está diferido — chega quando a base de
          strings for grande o suficiente para justificar o overhead i18next.
        </p>
        <DarkButton
          variant="secondary"
          size="sm"
          onClick={() => toast.info('i18n completo está diferido para a Fase 5.')}
        >
          Aplicar idioma
        </DarkButton>
      </div>
    </DarkCard>
  );
}

// ── Aprendizagem panel (Sprint R.1 — números reais; R.4 — history modal) ─
function LearningSettingsPanel() {
  const STALE = 5 * 60 * 1000; // 5min
  const [showHistory, setShowHistory] = useState(false);
  const pairsQ = useQuery({
    queryKey: ['learning', 'pairs'],
    queryFn: () => learningApi.pairs({ window_days: 90, min_reason_len: 10 }),
    staleTime: STALE,
    retry: false,
  });
  const rulesQ = useQuery({
    queryKey: ['learning', 'rules'],
    queryFn: () => learningApi.rules(),
    staleTime: STALE,
    retry: false,
  });
  const weightsQ = useQuery({
    queryKey: ['learning', 'weights'],
    queryFn: () => learningApi.weights(),
    staleTime: STALE,
    retry: false,
  });
  const historyQ = useQuery({
    queryKey: ['learning', 'weights', 'history'],
    queryFn: () => learningApi.weightHistory(12),
    staleTime: STALE,
    retry: false,
    enabled: showHistory,
  });
  const adapterQ = useQuery({
    queryKey: ['learning', 'adapter'],
    queryFn: () => learningApi.adapter(),
    staleTime: STALE,
    retry: false,
  });
  const queryClient = useQueryClient();
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [promoteVersion, setPromoteVersion] = useState('');
  const [promoteReason, setPromoteReason] = useState('');
  const [promoteBy, setPromoteBy] = useState('');
  const [rollbackOpen, setRollbackOpen] = useState(false);
  const [rollbackReason, setRollbackReason] = useState('');
  const [rollbackBy, setRollbackBy] = useState('');
  const promoteMut = useMutation({
    mutationFn: () =>
      learningApi.promoteAdapter(promoteVersion.trim(), {
        reason: promoteReason.trim(),
        decided_by: promoteBy.trim() || 'unknown',
      }),
    onSuccess: () => {
      setPromoteOpen(false);
      setPromoteReason('');
      setPromoteVersion('');
      setPromoteBy('');
      queryClient.invalidateQueries({ queryKey: ['learning', 'adapter'] });
    },
  });
  const rollbackMut = useMutation({
    mutationFn: () =>
      learningApi.rollbackAdapter({
        reason: rollbackReason.trim(),
        decided_by: rollbackBy.trim() || 'unknown',
      }),
    onSuccess: () => {
      setRollbackOpen(false);
      setRollbackReason('');
      setRollbackBy('');
      queryClient.invalidateQueries({ queryKey: ['learning', 'adapter'] });
    },
  });
  const adapter = adapterQ.data;

  const pairs = pairsQ.data;
  const rules = rulesQ.data;
  const weights = weightsQ.data;

  const ruleConfirmed = rules?.by_status?.confirmed ?? 0;
  const ruleDetected = rules?.by_status?.detected ?? 0;
  const ruleRejected = rules?.by_status?.rejected ?? 0;
  const reEmit = rules?.rules_re_emitted_count ?? 0;

  const eligible = pairs?.eligible_for_dpo ?? 0;
  const ablToday = pairs?.abl_pairs_today ?? 0;
  const dpoBadge: { variant: 'success' | 'warning' | 'neutral'; label: string } =
    eligible >= 500
      ? { variant: 'success', label: 'PRONTO' }
      : eligible >= 100
        ? { variant: 'warning', label: 'A ACUMULAR' }
        : { variant: 'neutral', label: 'BOOTSTRAP' };

  const weightsTrained = weights?.status === 'trained';
  const weightsBadge: { variant: 'success' | 'warning' | 'neutral'; label: string } =
    weightsTrained
      ? { variant: 'success', label: 'TREINADOS' }
      : weights?.status === 'never_trained'
        ? { variant: 'neutral', label: 'DEFAULTS' }
        : { variant: 'warning', label: weights?.status?.toUpperCase() ?? 'DESCONHECIDO' };

  const trainedAt = weights?.trained_at
    ? new Date(weights.trained_at).toLocaleString('pt-PT')
    : '—';
  const detectorAt = rules?.last_detector_run_at
    ? new Date(rules.last_detector_run_at).toLocaleString('pt-PT')
    : '—';

  return (
    <DarkCard title="Aprendizagem" subtitle="Plan v4 §22-§27 · Camadas 1-4 · Sprint R.1 (visibilidade)">
      <div className="space-y-3 mt-4">

        {/* Camada 1 */}
        <div className="bg-slate-800/40 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-slate-200 font-medium">Camada 1 — Regras explícitas</p>
            {rulesQ.isLoading ? (
              <DarkBadge variant="neutral" size="sm">A carregar…</DarkBadge>
            ) : reEmit > 0 ? (
              <DarkBadge variant="warning" size="sm" dot>{reEmit} re-emitidas</DarkBadge>
            ) : (
              <DarkBadge variant="success" size="sm" dot>OK</DarkBadge>
            )}
          </div>
          <div className="grid grid-cols-3 gap-3 mt-2">
            <div>
              <p className="text-2xl font-bold text-slate-100">{ruleConfirmed}</p>
              <p className="text-xs text-slate-400">Confirmadas</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-400">{ruleDetected}</p>
              <p className="text-xs text-slate-400">Em revisão</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-500">{ruleRejected}</p>
              <p className="text-xs text-slate-400">Rejeitadas</p>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            Última passagem do detector: <span className="text-slate-300">{detectorAt}</span>
          </p>
          <a
            href="/admin/learned-rules"
            className="text-xs text-accent underline mt-2 inline-block"
          >
            Ver e aprovar regras aprendidas →
          </a>
        </div>

        {/* Camada 2 */}
        <div className="bg-slate-800/40 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-slate-200 font-medium">Camada 2 — Pesos adaptativos</p>
            {weightsQ.isLoading ? (
              <DarkBadge variant="neutral" size="sm">A carregar…</DarkBadge>
            ) : (
              <DarkBadge variant={weightsBadge.variant} size="sm" dot>{weightsBadge.label}</DarkBadge>
            )}
          </div>
          <div className="grid grid-cols-4 gap-2 mt-2 text-xs">
            {weights && Object.entries(weights.current_weights).map(([key, value]) => {
              const def = weights.default_weights[key] ?? 0;
              const mult = weights.multipliers[key] ?? 1;
              const arrow = mult > 1.05 ? '↑' : mult < 0.95 ? '↓' : '→';
              const colour = mult > 1.05 ? 'text-emerald-400' : mult < 0.95 ? 'text-rose-400' : 'text-slate-300';
              return (
                <div key={key}>
                  <p className="text-slate-400">{key.replace('w_', '')}</p>
                  <p className={`font-mono ${colour}`}>
                    {value.toFixed(2)} {arrow} ({mult.toFixed(2)}×)
                  </p>
                  <p className="text-slate-600">def {def.toFixed(2)}</p>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-slate-500 mt-3">
            Treinado com <span className="text-slate-300">{weights?.pairs_used ?? 0}</span> pares ·
            blend {((weights?.blend_learned_pct ?? 0.7) * 100).toFixed(0)}% aprendido /
            {(100 - (weights?.blend_learned_pct ?? 0.7) * 100).toFixed(0)}% default ·
            min pares: {weights?.min_pairs_threshold ?? 50} ·
            último retrain: <span className="text-slate-300">{trainedAt}</span>
          </p>
          <button
            type="button"
            className="text-xs text-accent underline mt-2"
            onClick={() => setShowHistory(true)}
          >
            Ver histórico (12 retrains) →
          </button>
        </div>

        {/* Camada 3 */}
        <div className="bg-slate-800/40 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-slate-200 font-medium">Camada 3 — DPO no LLM (fine-tune)</p>
            {pairsQ.isLoading ? (
              <DarkBadge variant="neutral" size="sm">A carregar…</DarkBadge>
            ) : (
              <DarkBadge variant={dpoBadge.variant} size="sm" dot>{dpoBadge.label}</DarkBadge>
            )}
          </div>
          <div className="grid grid-cols-3 gap-3 mt-2">
            <div>
              <p className="text-2xl font-bold text-slate-100">{eligible}</p>
              <p className="text-xs text-slate-400">Pares elegíveis (≥{pairs?.min_reason_len ?? 10} chars)</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-300">{pairs?.total_pairs ?? 0}</p>
              <p className="text-xs text-slate-400">Total de pares</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-300">{pairs?.last_30d?.eligible ?? 0}</p>
              <p className="text-xs text-slate-400">Elegíveis últimos 30d</p>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            Bootstrap: precisa de ≥500 pares elegíveis para fine-tune QLoRA on-prem (Sprint R.5).
            Pares vêm de <code>rejected_alternatives</code> nos commits CPO + ABL (Sprint R.3).
          </p>
          <div className="mt-3 pt-3 border-t border-slate-700 text-xs">
            {adapter?.active_version ? (
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-slate-300">
                    Adapter activo: <code className="text-accent">{adapter.active_version}</code>
                  </p>
                  <p className="text-slate-500 mt-1">
                    Promovido por <span className="text-slate-300">{adapter.promoted_by ?? '—'}</span>
                    {' '}em{' '}
                    <span className="text-slate-300">
                      {adapter.promoted_at ? new Date(adapter.promoted_at).toLocaleString('pt-PT') : '—'}
                    </span>
                  </p>
                  {adapter.intent_match_rate !== null && (
                    <p className="text-slate-500 mt-1">
                      intent_match: <span className="text-slate-300">{((adapter.intent_match_rate ?? 0) * 100).toFixed(1)}%</span>
                      {' · safety: '}
                      <span className="text-slate-300">{adapter.safety_violations_count ?? 0}</span>
                    </p>
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  <button
                    type="button"
                    className="text-xs text-accent underline"
                    onClick={() => setPromoteOpen(true)}
                  >
                    Promover novo →
                  </button>
                  {adapter.has_previous && (
                    <button
                      type="button"
                      className="text-xs text-rose-400 underline"
                      onClick={() => setRollbackOpen(true)}
                    >
                      Rollback ↩
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <p className="text-slate-500">Sem adapter activo — base model em uso.</p>
                <button
                  type="button"
                  className="text-xs text-accent underline"
                  onClick={() => setPromoteOpen(true)}
                >
                  Promover candidato →
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Camada 4 */}
        <div className="bg-slate-800/40 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-slate-200 font-medium">Camada 4 — ABLkit (loop contínuo)</p>
            {pairsQ.isLoading ? (
              <DarkBadge variant="neutral" size="sm">A carregar…</DarkBadge>
            ) : ablToday > 0 ? (
              <DarkBadge variant="success" size="sm" dot>ACTIVA</DarkBadge>
            ) : (
              <DarkBadge variant="warning" size="sm" dot>STUB (R.3 pendente)</DarkBadge>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 mt-2">
            <div>
              <p className="text-2xl font-bold text-slate-100">{ablToday}</p>
              <p className="text-xs text-slate-400">Divergências hoje</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-300">—</p>
              <p className="text-xs text-slate-400">Acumuladas (Sprint R.3)</p>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            Cada divergência kernel-vs-LLM produz um triplet <code>{`{prompt, chosen, rejected}`}</code>
            alimentado à Camada 3. Activado pelo job <code>_abl_feedback_job</code> (Sprint R.3).
          </p>
        </div>

        <p className="text-xs text-slate-500 mt-2">
          Override do gestor SEMPRE ganha (Plan v4 §11.3).
          Endpoints expostos: <code>/v1/governance/learning/{`{pairs,rules,weights}`}</code>.
        </p>
      </div>

      {showHistory && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setShowHistory(false)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl max-w-5xl w-full max-h-[85vh] overflow-y-auto p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">
                  Histórico de pesos adaptativos (Camada 2)
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Últimos 12 retrains com explicação determinística por KPI (Sprint R.4).
                </p>
              </div>
              <button
                type="button"
                className="text-slate-400 hover:text-slate-100"
                onClick={() => setShowHistory(false)}
              >
                Fechar ✕
              </button>
            </div>

            {historyQ.isLoading && (
              <p className="text-sm text-slate-400">A carregar histórico…</p>
            )}
            {historyQ.isError && (
              <p className="text-sm text-rose-400">
                Erro a carregar histórico. Tente outra vez.
              </p>
            )}
            {historyQ.data && historyQ.data.entries.length === 0 && (
              <p className="text-sm text-slate-400">
                Sem retrains gravados ainda. O job corre domingos 02:00 UTC.
              </p>
            )}
            {historyQ.data && historyQ.data.entries.length > 0 && (
              <div className="space-y-3">
                {historyQ.data.entries.map((entry, idx) => {
                  const dt = entry.trained_at
                    ? new Date(entry.trained_at).toLocaleString('pt-PT')
                    : entry.valid_from
                      ? new Date(entry.valid_from).toLocaleString('pt-PT')
                      : '—';
                  return (
                    <div
                      key={`${entry.trained_at}-${idx}`}
                      className="bg-slate-800/40 rounded-lg p-3"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-medium text-slate-200">
                          {dt}
                        </p>
                        <DarkBadge
                          variant={entry.status === 'trained' ? 'success' : 'neutral'}
                          size="sm"
                          dot
                        >
                          {entry.status ?? 'unknown'} · {entry.pairs_used} pares
                        </DarkBadge>
                      </div>
                      {entry.explanations && entry.explanations.length > 0 ? (
                        <ul className="space-y-1">
                          {entry.explanations.map((ex) => (
                            <li key={ex.kpi} className="text-xs text-slate-300">
                              {/* ZERO XSS: render as plain text. The previous
                                  implementation used dangerouslySetInnerHTML
                                  with a regex that left ex.human_text exposed
                                  to attacker-controlled HTML. */}
                              {ex.human_text.replace(/\*\*([^*]+)\*\*/g, '$1')}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-slate-500 italic">
                          Sem explicações neste retrain (anterior a R.4).
                        </p>
                      )}
                      {entry.warnings && entry.warnings.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-slate-700">
                          <p className="text-xs text-amber-400 font-medium">
                            ⚠ {entry.warnings.length} contradição{entry.warnings.length > 1 ? 'ões' : ''} com regras confirmadas
                          </p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {promoteOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setPromoteOpen(false)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold text-slate-100 mb-1">
              Promover candidato LoRA
            </h2>
            <p className="text-xs text-slate-400 mb-4">
              Sprint R.5.3 — promove um adapter como activo. Razão obrigatória ≥20 chars (audit).
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-300">Versão do candidato</label>
                <DarkInput
                  value={promoteVersion}
                  onChange={(e) => setPromoteVersion(e.target.value)}
                  placeholder="gemma4-8b-nelo-2026-04-25"
                />
              </div>
              <div>
                <label className="text-xs text-slate-300">Decidido por</label>
                <DarkInput
                  value={promoteBy}
                  onChange={(e) => setPromoteBy(e.target.value)}
                  placeholder="luis"
                />
              </div>
              <div>
                <label className="text-xs text-slate-300">Razão (≥20 chars)</label>
                <DarkInput
                  value={promoteReason}
                  onChange={(e) => setPromoteReason(e.target.value)}
                  placeholder="ex: candidato passou eval +5pp, sem violações"
                />
                <p className="text-xs text-slate-500 mt-1">
                  {promoteReason.trim().length}/20 chars mínimos
                </p>
              </div>
              {promoteMut.isError && (
                <p className="text-xs text-rose-400">
                  {(promoteMut.error as Error)?.message ?? 'Erro a promover.'}
                </p>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <DarkButton
                  variant="secondary"
                  onClick={() => setPromoteOpen(false)}
                >
                  Cancelar
                </DarkButton>
                <DarkButton
                  variant="primary"
                  disabled={
                    !promoteVersion.trim()
                    || promoteReason.trim().length < 20
                    || promoteMut.isPending
                  }
                  onClick={() => promoteMut.mutate()}
                >
                  {promoteMut.isPending ? 'A promover…' : 'Promover'}
                </DarkButton>
              </div>
            </div>
          </div>
        </div>
      )}

      {rollbackOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setRollbackOpen(false)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold text-slate-100 mb-1">
              Rollback do adapter activo
            </h2>
            <p className="text-xs text-slate-400 mb-4">
              Restaura a versão anterior. Razão obrigatória ≥20 chars.
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-300">Decidido por</label>
                <DarkInput
                  value={rollbackBy}
                  onChange={(e) => setRollbackBy(e.target.value)}
                  placeholder="luis"
                />
              </div>
              <div>
                <label className="text-xs text-slate-300">Razão (≥20 chars)</label>
                <DarkInput
                  value={rollbackReason}
                  onChange={(e) => setRollbackReason(e.target.value)}
                  placeholder="ex: regressão de OTD após promote"
                />
                <p className="text-xs text-slate-500 mt-1">
                  {rollbackReason.trim().length}/20 chars mínimos
                </p>
              </div>
              {rollbackMut.isError && (
                <p className="text-xs text-rose-400">
                  {(rollbackMut.error as Error)?.message ?? 'Erro a fazer rollback.'}
                </p>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <DarkButton
                  variant="secondary"
                  onClick={() => setRollbackOpen(false)}
                >
                  Cancelar
                </DarkButton>
                <DarkButton
                  variant="primary"
                  disabled={
                    rollbackReason.trim().length < 20
                    || rollbackMut.isPending
                  }
                  onClick={() => rollbackMut.mutate()}
                >
                  {rollbackMut.isPending ? 'A reverter…' : 'Rollback'}
                </DarkButton>
              </div>
            </div>
          </div>
        </div>
      )}
    </DarkCard>
  );
}
