/**
 * SimDetail — painel de detalhe de uma simulação do histórico.
 *
 * Mostra os deltas aplicados e o resultado da simulação (baseline vs
 * simulação) de um twin scenario real. Tudo vem da API — quando o
 * cenário ainda não foi simulado, mostra um estado honesto a dizê-lo.
 *
 * Sprint Q.52.M.
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Sparkles } from 'lucide-react';
import type { ReactNode } from 'react';
import { twinApi } from '../../lib/api';
import { Tag } from './atoms';
import type { TwinScenario } from './types';

export interface ComparisonRow {
  label: string;
  baseline: string;
  simulated: string;
}

/** Formata uma célula de KPI `{value, unit, status}` para texto legível. */
function kpiCell(kpi: unknown): string {
  if (!kpi || typeof kpi !== 'object') return '—';
  const k = kpi as Record<string, unknown>;
  const value = k.value;
  if (value === null || value === undefined) {
    // KPI sem valor — mostra o estado honesto (BLOCKED / NO_DATA).
    return typeof k.status === 'string' ? k.status : '—';
  }
  if (typeof value === 'number') {
    const unit = typeof k.unit === 'string' ? ` ${k.unit}` : '';
    return `${value.toLocaleString('pt-PT')}${unit}`;
  }
  return String(value);
}

/**
 * Aplaina o `simulation_result` numa tabela baseline↔simulação.
 *
 * Q.56.C — o backend (`twin/service.simulate`) guarda o resultado como
 * `{ before, after, delta_summary, mode }`. Antes esta função procurava
 * `kpis`/`comparison` (a forma da RESPOSTA do endpoint `/simulate`, não a
 * guardada) → a tabela vinha sempre vazia. Agora emparelha `before` e
 * `after` por chave de KPI.
 */
export function buildComparisonRows(
  simResult: Record<string, unknown> | null | undefined,
): ComparisonRow[] {
  if (!simResult || typeof simResult !== 'object') return [];
  const before = simResult.before;
  const after = simResult.after;
  if (
    !before || typeof before !== 'object' ||
    !after || typeof after !== 'object'
  ) {
    return [];
  }
  const b = before as Record<string, unknown>;
  const a = after as Record<string, unknown>;
  const keys = [...new Set([...Object.keys(b), ...Object.keys(a)])].filter(
    (k) => !k.startsWith('_'),
  );
  const rows: ComparisonRow[] = [];
  for (const key of keys) {
    const src = (a[key] ?? b[key]) as Record<string, unknown> | undefined;
    const label =
      src && typeof src.semantic_label === 'string'
        ? src.semantic_label
        : key;
    rows.push({
      label,
      baseline: kpiCell(b[key]),
      simulated: kpiCell(a[key]),
    });
  }
  return rows;
}

/** Tabela baseline↔simulação reutilizável (SimDetail + CrisisSimulator). */
export function ComparisonTable({ rows }: { rows: ComparisonRow[] }): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-sm)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.5fr 1fr 1fr',
          padding: '8px 14px',
          background: 'var(--bg-2)',
          borderBottom: '1px solid var(--bd-1)',
          fontSize: 10,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
        }}
      >
        <span>Métrica</span>
        <span style={{ textAlign: 'right' }}>Baseline</span>
        <span style={{ textAlign: 'right' }}>Simulação</span>
      </div>
      {rows.map((r, i) => (
        <div
          key={r.label}
          style={{
            display: 'grid',
            gridTemplateColumns: '1.5fr 1fr 1fr',
            padding: '10px 14px',
            borderBottom:
              i < rows.length - 1 ? '1px solid var(--bd-1)' : 'none',
            alignItems: 'center',
            fontSize: 12,
          }}
        >
          <span style={{ color: 'var(--fg-1)' }}>{r.label}</span>
          <span
            className="tabular"
            style={{ color: 'var(--fg-2)', textAlign: 'right' }}
          >
            {r.baseline}
          </span>
          <span
            className="tabular"
            style={{ color: 'var(--fg-0)', fontWeight: 500, textAlign: 'right' }}
          >
            {r.simulated}
          </span>
        </div>
      ))}
    </div>
  );
}

export function SimDetail({
  scenario,
}: {
  scenario: TwinScenario | null;
}): ReactNode {
  const { data: detail, isLoading } = useQuery({
    queryKey: ['twin', 'scenario', scenario?.id],
    queryFn: () => twinApi.getScenario(scenario!.id),
    enabled: !!scenario,
  });

  const rows = useMemo(
    () => buildComparisonRows(detail?.simulation_result ?? null),
    [detail],
  );

  if (!scenario) {
    return (
      <div
        style={{
          padding: 40,
          textAlign: 'center',
          color: 'var(--fg-3)',
          fontSize: 13,
        }}
      >
        Selecciona uma simulação
      </div>
    );
  }

  const deltas: Array<Record<string, unknown>> = Array.isArray(
    detail?.deltas,
  )
    ? (detail!.deltas as Array<Record<string, unknown>>)
    : [];

  return (
    <div
      style={{ display: 'flex', flexDirection: 'column', height: '100%' }}
    >
      <div
        style={{
          padding: '14px 18px',
          borderBottom: '1px solid var(--bd-1)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 8,
          }}
        >
          <Tag
            tone={
              scenario.status === 'SOLVED'
                ? 'green'
                : scenario.status === 'SIMULATED'
                  ? 'blue'
                  : 'yellow'
            }
            size="sm"
          >
            {scenario.status ?? 'DRAFT'}
          </Tag>
          <span
            className="mono"
            style={{ fontSize: 11, color: 'var(--fg-3)' }}
          >
            {scenario.id.slice(0, 8)}
          </span>
        </div>
        <div
          style={{ fontSize: 15, color: 'var(--fg-0)', fontWeight: 500 }}
        >
          {scenario.title}
        </div>
        {scenario.description ? (
          <div
            style={{
              fontSize: 12,
              color: 'var(--fg-2)',
              marginTop: 4,
            }}
          >
            {scenario.description}
          </div>
        ) : null}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 18 }}>
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: 32 }}>
            <Loader2
              size={24}
              className="animate-spin"
              style={{ color: 'var(--accent)' }}
            />
          </div>
        ) : (
          <>
            {/* Deltas aplicados */}
            <div style={{ marginBottom: 18 }}>
              <div
                style={{
                  fontSize: 10.5,
                  color: 'var(--fg-3)',
                  textTransform: 'uppercase',
                  letterSpacing: 0.4,
                  fontWeight: 600,
                  marginBottom: 8,
                }}
              >
                Deltas aplicados · {deltas.length}
              </div>
              {deltas.length === 0 ? (
                <div
                  style={{
                    padding: 14,
                    background: 'var(--bg-2)',
                    borderRadius: 'var(--r-sm)',
                    fontSize: 12,
                    color: 'var(--fg-2)',
                  }}
                >
                  Este cenário ainda não tem deltas aplicados.
                </div>
              ) : (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                  }}
                >
                  {deltas.map((d, i) => (
                    <div
                      key={i}
                      style={{
                        padding: '8px 11px',
                        background: 'var(--bg-2)',
                        border: '1px solid var(--bd-1)',
                        borderRadius: 'var(--r-sm)',
                        fontSize: 11.5,
                        color: 'var(--fg-1)',
                      }}
                    >
                      <span
                        className="mono"
                        style={{ color: 'var(--fg-3)' }}
                      >
                        {String(d.entity_type ?? '?')}·
                        {String(d.entity_key ?? '?')}
                      </span>{' '}
                      {String(d.description ?? '')}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Baseline vs simulação */}
            <div style={{ marginBottom: 18 }}>
              <div
                style={{
                  fontSize: 10.5,
                  color: 'var(--fg-3)',
                  textTransform: 'uppercase',
                  letterSpacing: 0.4,
                  fontWeight: 600,
                  marginBottom: 8,
                }}
              >
                Baseline vs simulação
              </div>
              {rows.length === 0 ? (
                <div
                  style={{
                    padding: 14,
                    background: 'var(--bg-2)',
                    borderRadius: 'var(--r-sm)',
                    fontSize: 12,
                    color: 'var(--fg-2)',
                  }}
                >
                  Este cenário ainda não foi simulado. Corre a simulação
                  para ver o impacto.
                </div>
              ) : (
                <ComparisonTable rows={rows} />
              )}
            </div>

            {/* Reprodutibilidade */}
            {detail?.scenario_hash ? (
              <div
                style={{
                  padding: 14,
                  background: 'var(--accent-bg)',
                  border: '1px solid var(--accent-bd)',
                  borderRadius: 'var(--r-md)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    marginBottom: 6,
                  }}
                >
                  <Sparkles size={13} color="var(--accent)" />
                  <span
                    style={{
                      fontSize: 11,
                      color: 'var(--accent)',
                      textTransform: 'uppercase',
                      letterSpacing: 0.4,
                      fontWeight: 600,
                    }}
                  >
                    Reprodutível
                  </span>
                </div>
                <div
                  className="mono"
                  style={{
                    fontSize: 11.5,
                    color: 'var(--fg-1)',
                    wordBreak: 'break-all',
                  }}
                >
                  {detail.scenario_hash}
                </div>
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
