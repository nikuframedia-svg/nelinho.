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

interface ComparisonRow {
  label: string;
  baseline: string;
  simulated: string;
}

/** Aplaina o resultado da simulação numa tabela legível. */
function buildComparisonRows(
  simResult: Record<string, unknown> | null,
): ComparisonRow[] {
  if (!simResult) return [];
  const rows: ComparisonRow[] = [];
  const kpis = simResult.kpis;
  const comparison = simResult.comparison;

  if (comparison && typeof comparison === 'object') {
    for (const [key, value] of Object.entries(
      comparison as Record<string, unknown>,
    )) {
      if (value && typeof value === 'object') {
        const v = value as Record<string, unknown>;
        rows.push({
          label: key,
          baseline: String(v.baseline ?? v.before ?? '—'),
          simulated: String(v.scenario ?? v.after ?? v.value ?? '—'),
        });
      }
    }
  }
  if (rows.length === 0 && kpis && typeof kpis === 'object') {
    for (const [key, value] of Object.entries(
      kpis as Record<string, unknown>,
    )) {
      if (key.startsWith('_')) continue;
      const display =
        value && typeof value === 'object'
          ? String((value as Record<string, unknown>).value ?? '—')
          : String(value);
      rows.push({ label: key, baseline: '—', simulated: display });
    }
  }
  return rows;
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
                          i < rows.length - 1
                            ? '1px solid var(--bd-1)'
                            : 'none',
                        alignItems: 'center',
                        fontSize: 12,
                      }}
                    >
                      <span style={{ color: 'var(--fg-1)' }}>
                        {r.label}
                      </span>
                      <span
                        className="tabular"
                        style={{
                          color: 'var(--fg-2)',
                          textAlign: 'right',
                        }}
                      >
                        {r.baseline}
                      </span>
                      <span
                        className="tabular"
                        style={{
                          color: 'var(--fg-0)',
                          fontWeight: 500,
                          textAlign: 'right',
                        }}
                      >
                        {r.simulated}
                      </span>
                    </div>
                  ))}
                </div>
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
