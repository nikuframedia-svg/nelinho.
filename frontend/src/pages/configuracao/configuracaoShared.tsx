// ConfiguracaoPage — painel genérico, helpers e tipos partilhados (Q.60.U).
import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, Save, RotateCcw } from 'lucide-react';
import { configApi, type ConfigDataType, type ConfigCategoryValues } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';

export function ConfigCard({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={className}
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 14,
        overflow: 'hidden',
      }}
    >
      {children}
    </div>
  );
}

export function SectionHeader({
  icon,
  title,
  subtitle,
}: {
  icon?: React.ReactNode;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="flex items-center gap-2.5">
      {icon ? <span style={{ color: 'var(--fg-3)' }}>{icon}</span> : null}
      <div>
        <div className="text-[13px] font-semibold text-text-dark-primary">
          {title}
        </div>
        {subtitle ? (
          <div className="text-[11px] text-text-dark-tertiary mt-0.5">
            {subtitle}
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ─── Painel genérico de chaves de configuração (ConfigStore) ─────────────────
// Cada chave: valor editável + proveniência (quem/quando) + reset ao default.

export interface ConfigKeyRow {
  key: string;
  label: string;
  hint: string;
  // Q.53.J — `currency` adicionado para a aba Custos (metas em €).
  dataType: Extract<ConfigDataType, 'int' | 'float' | 'bool' | 'string' | 'currency'>;
}

export function parseConfigValue(row: ConfigKeyRow, raw: string): unknown {
  if (raw === '') return null;
  switch (row.dataType) {
    case 'int':
      return Number.parseInt(raw, 10);
    case 'float':
    case 'currency':
      return Number.parseFloat(raw);
    case 'bool':
      return raw === 'true' || raw === '1';
    default:
      return raw;
  }
}

export function ConfigKeysPanel({
  title,
  subtitle,
  icon,
  category,
  rows,
  hint,
}: {
  title: string;
  subtitle: string;
  icon?: React.ReactNode;
  category: string;
  rows: ConfigKeyRow[];
  hint?: string;
}) {
  const queryClient = useQueryClient();
  const toast = useToastContext();

  const { data, isLoading, error } = useQuery<ConfigCategoryValues>({
    queryKey: ['config', category],
    queryFn: () => configApi.listCategory(category),
    staleTime: 60_000,
  });

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
    mutationFn: (
      changes: Array<{ key: string; value: unknown; dataType: ConfigKeyRow['dataType'] }>,
    ) =>
      configApi.bulkSet(
        changes.map((c) => ({
          category,
          key: c.key,
          value: c.value,
          data_type: c.dataType,
        })),
      ),
    onSuccess: () => {
      toast.success('Configuração gravada.');
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

  const handleSave = () => {
    const changes = rows.flatMap((row) => {
      const raw = edits[row.key] ?? '';
      if (raw === '') return [];
      const parsed = parseConfigValue(row, raw);
      if (parsed === null) return [];
      if (typeof parsed === 'number' && Number.isNaN(parsed)) return [];
      if (data?.values[row.key] === parsed) return [];
      return [{ key: row.key, value: parsed, dataType: row.dataType }];
    });
    if (changes.length === 0) {
      toast.info('Nada para guardar.');
      return;
    }
    saveMutation.mutate(changes);
  };

  return (
    <ConfigCard>
      <div
        style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}
      >
        <SectionHeader icon={icon} title={title} subtitle={subtitle} />
      </div>
      <div className="p-[18px]">
        {hint ? (
          <p className="text-[11px] text-text-dark-tertiary mb-4 italic leading-relaxed">
            {hint}
          </p>
        ) : null}
        {isLoading ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 size={22} className="text-accent-500 animate-spin" />
          </div>
        ) : error ? (
          <p className="text-sm text-status-red py-3">
            Falha ao carregar: {(error as Error).message}
          </p>
        ) : (
          <>
            <div className="space-y-3.5">
              {rows.map((row) => {
                const current = data?.values[row.key];
                const defaultRender =
                  current === undefined || current === null
                    ? '—'
                    : String(current);
                return (
                  <div
                    key={row.key}
                    className="grid grid-cols-[1fr_140px_90px] items-center gap-3 py-1"
                  >
                    <div>
                      <div className="text-[12.5px] text-text-dark-primary">
                        {row.label}
                      </div>
                      <div className="text-[10.5px] text-text-dark-tertiary mt-0.5">
                        {row.hint} · actual{' '}
                        <span className="tabular-nums text-text-dark-secondary">
                          {defaultRender}
                        </span>
                      </div>
                    </div>
                    <input
                      type={
                        row.dataType === 'bool' || row.dataType === 'string'
                          ? 'text'
                          : 'number'
                      }
                      value={edits[row.key] ?? ''}
                      placeholder={
                        row.dataType === 'bool' ? 'true | false' : '—'
                      }
                      onChange={(e) =>
                        setEdits((s) => ({ ...s, [row.key]: e.target.value }))
                      }
                      className="w-full px-2.5 py-1.5 rounded-md text-[12px] tabular-nums bg-white text-slate-900 placeholder:text-slate-400 border border-bd-2 focus:outline-none focus:border-accent-500"
                    />
                    <button
                      type="button"
                      onClick={() => resetMutation.mutate(row.key)}
                      disabled={resetMutation.isPending}
                      className="inline-flex items-center justify-center gap-1 px-2 py-1.5 rounded-md text-[11px] text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary disabled:opacity-50 transition-colors"
                    >
                      <RotateCcw size={11} />
                      Reset
                    </button>
                  </div>
                );
              })}
            </div>
            <div className="flex justify-end pt-4">
              <button
                type="button"
                onClick={handleSave}
                disabled={saveMutation.isPending}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-[12px] font-medium disabled:opacity-50 transition-colors"
              >
                {saveMutation.isPending ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <Save size={13} />
                )}
                Guardar
              </button>
            </div>
            <p className="text-[10.5px] text-text-dark-tertiary mt-3">
              Cada chave grava um audit row em{' '}
              <code>tenant_configuration.{category}.*</code> (quem · quando ·
              valor anterior). O Reset repõe o default seeded.
            </p>
          </>
        )}
      </div>
    </ConfigCard>
  );
}

// ═══ Tab Aprendizagem ════════════════════════════════════════════════════════

export interface RateRow {
  id?: string;
  phase_code?: string;
  phase?: string;
  machine_code?: string;
  category?: string;
  rate_per_hour?: number;
  cost_per_hour?: number;
  hourly_rate?: number;
  amount?: number;
  effective_date?: string;
  updated_at?: string;
}

export function rateValue(r: RateRow): number | null {
  const v = r.rate_per_hour ?? r.cost_per_hour ?? r.hourly_rate ?? r.amount;
  return typeof v === 'number' ? v : null;
}

export function unwrapList<T>(d: unknown): T[] {
  if (Array.isArray(d)) return d as T[];
  if (d && typeof d === 'object') {
    const o = d as Record<string, unknown>;
    if (Array.isArray(o.items)) return o.items as T[];
    if (Array.isArray(o.data)) return o.data as T[];
    if (Array.isArray(o.rates)) return o.rates as T[];
  }
  return [];
}
