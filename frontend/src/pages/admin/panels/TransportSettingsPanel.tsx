// SettingsPage · TransportSettingsPanel (Q.60.R).
import { useEffect, useState } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { Loader2, Save } from 'lucide-react';
import { configApi } from '../../../lib/api';
import { useToastContext } from '../../../components/ToastProvider';
import { DarkButton, DarkCard, DarkInput } from '../../../components/dark';

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

export function TransportSettingsPanel() {
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
