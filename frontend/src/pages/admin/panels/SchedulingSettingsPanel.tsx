// SettingsPage · SchedulingSettingsPanel (Q.60.R).
import { useEffect, useState } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { Loader2, Save } from 'lucide-react';
import { configApi } from '../../../lib/api';
import { useToastContext } from '../../../components/ToastProvider';
import { DarkButton, DarkCard, DarkInput } from '../../../components/dark';

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

export function SchedulingSettingsPanel() {
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
