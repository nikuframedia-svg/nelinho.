// SettingsPage · ConfigKeysPanel (Q.60.R).
import { useEffect, useMemo, useState } from 'react';
import { useQueries, useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { Loader2, Save, RotateCcw } from 'lucide-react';
import { configApi } from '../../../lib/api';
import { useToastContext } from '../../../components/ToastProvider';
import { AuditTrailRow, DarkButton, DarkCard, DarkInput } from '../../../components/dark';
import { type ConfigKeyRow } from '../settingsTypes';

export function ConfigKeysPanel({
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
