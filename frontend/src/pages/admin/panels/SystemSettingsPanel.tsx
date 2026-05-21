// SettingsPage · SystemSettingsPanel (Q.60.R).
import { useState } from 'react';
import { useToastContext } from '../../../components/ToastProvider';
import { DarkButton, DarkCard, DarkSelect } from '../../../components/dark';

export function SystemSettingsPanel() {
  const toast = useToastContext();
  const [language, setLanguage] = useState<'pt-PT' | 'en-US' | 'de-DE'>('pt-PT');

  return (
    <DarkCard title="Sistema" subtitle="Idioma · tema · formatos (Plan v4 §11.1)">
      <div className="space-y-4 mt-4">
        <DarkSelect
          label="Idioma da UI"
          options={[
            { value: 'pt-PT', label: 'Português (Portugal)' },
            { value: 'en-US', label: 'English (US) — diferido' },
            { value: 'de-DE', label: 'Deutsch — diferido' },
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
