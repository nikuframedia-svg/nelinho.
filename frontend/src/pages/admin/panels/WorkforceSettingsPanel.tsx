// SettingsPage · WorkforceSettingsPanel (Q.60.R).
import { useEffect, useState } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { Loader2, Save } from 'lucide-react';
import { configApi } from '../../../lib/api';
import { useToastContext } from '../../../components/ToastProvider';
import { DarkButton, DarkCard, DarkInput } from '../../../components/dark';

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

export function WorkforceSettingsPanel() {
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
