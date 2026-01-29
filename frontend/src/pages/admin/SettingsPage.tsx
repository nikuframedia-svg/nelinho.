import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Settings, Users, Key, Bell, Plug, Loader2, Save, RotateCcw } from 'lucide-react';
import { tenantsApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkButton, DarkSelect, DarkInput } from '../../components/dark';

type TabType = 'general' | 'tenant' | 'api' | 'notifications' | 'integrations';

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
  
  // Fetch tenant data
  const { data: tenants, isLoading: tenantsLoading } = useQuery<Tenant[]>({
    queryKey: ['tenants', 'current'],
    queryFn: () => tenantsApi.list(),
    retry: false,
  });
  
  const currentTenant = tenants && tenants.length > 0 ? tenants[0] : null;

  // Form states
  const [timezone, setTimezone] = useState('Europe/Lisbon');
  const [currency, setCurrency] = useState('EUR');
  const [language, setLanguage] = useState('pt-PT');
  const [contactEmail, setContactEmail] = useState(currentTenant?.contact_email || '');
  const [contactPhone, setContactPhone] = useState(currentTenant?.contact_phone || '');

  // Save mutation (placeholder - would need backend endpoint)
  const saveMutation = useMutation({
    mutationFn: async (data: Record<string, any>) => {
      // Placeholder - would need actual endpoint
      await new Promise((resolve) => setTimeout(resolve, 500));
      return data;
    },
    onSuccess: () => {
      toast.success('Settings saved successfully!');
    },
    onError: () => {
      toast.error('Error saving settings.');
    },
  });

  const tabs = [
    { id: 'general' as TabType, label: 'General', icon: Settings },
    { id: 'tenant' as TabType, label: 'Tenant', icon: Users },
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
        </div>
      </div>
    </DarkPageLayout>
  );
}
