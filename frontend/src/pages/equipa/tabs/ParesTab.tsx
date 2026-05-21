// EquipaPage · ParesTab (Q.60.T). ZERO MOCKS — endpoints reais.
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { GitBranch, Shield, Sparkles } from 'lucide-react';
import { workforceEmployeesApi, type SkillMatrixResult } from '../../../lib/api';
import { equipaApi } from '../../../components/equipa/equipaApi';
import { type TrainingRecommendation } from '../../../components/workforce/types';
import { type EnrichedEmployee, SectionHeader } from '../equipaShared';

export function ParesTab({ employees }: { employees: EnrichedEmployee[] }) {
  // Skill-matrix de cada operador → quem está apto a Laminagem.
  const matricesQuery = useQuery({
    queryKey: ['equipa', 'pares', 'matrices', employees.map((e) => e.id).join(',')],
    queryFn: async () => {
      const entries = await Promise.all(
        employees.map(async (e) => {
          try {
            return [e.id, await workforceEmployeesApi.skillMatrix(e.id)] as const;
          } catch {
            return [e.id, null] as const;
          }
        }),
      );
      return new Map<string, SkillMatrixResult | null>(entries);
    },
    enabled: employees.length > 0,
    staleTime: 120_000,
    retry: 0,
  });

  const spofQuery = useQuery({
    queryKey: ['equipa', 'pares', 'spof'],
    queryFn: () => equipaApi.spofs(8),
    staleTime: 120_000,
    retry: 0,
  });

  // Laminadores = operadores aptos a uma fase cujo nome contém "lamina".
  const laminadores = useMemo(() => {
    const data = matricesQuery.data;
    if (!data) return [];
    return employees.filter((e) => {
      const m = data.get(e.id);
      return (
        m?.phases.some(
          (p) =>
            p.can_do &&
            (p.phase_name ?? '').toLowerCase().includes('lamina'),
        ) ?? false
      );
    });
  }, [employees, matricesQuery.data]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 14 }}>
      {/* Matriz de co-aptidão */}
      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionHeader
          icon={<GitBranch size={14} />}
          title="Pares de Laminagem · co-aptidão"
          subtitle="Operadores aptos à mesma fase de Laminagem podem formar par — verde = ambos séniores"
        />
        {matricesQuery.isLoading ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            A carregar skill-matrix…
          </div>
        ) : laminadores.length < 2 ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            Sem laminadores suficientes para uma matriz de pares.
          </div>
        ) : (
          <PairMatrix laminadores={laminadores} />
        )}
      </div>

      {/* SPOFs + formação */}
      <div className="space-y-3">
        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-lg)',
            padding: 18,
          }}
        >
          <SectionHeader
            icon={<Shield size={14} />}
            title="Single Points of Failure"
            subtitle="Fases que dependem de um só operador apto"
          />
          {spofQuery.isLoading ? (
            <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
              A carregar SPOFs…
            </div>
          ) : spofQuery.isError ? (
            <div style={{ padding: 16, textAlign: 'center', color: 'var(--danger)', fontSize: 12 }}>
              Erro a carregar /v1/workforce/risks/spof.
            </div>
          ) : !spofQuery.data || spofQuery.data.length === 0 ? (
            <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
              Sem SPOFs detectados — cobertura suficiente.
            </div>
          ) : (
            spofQuery.data.map((rec) => <SpofCard key={rec.id} rec={rec} />)
          )}
        </div>
      </div>
    </div>
  );
}

export function PairMatrix({ laminadores }: { laminadores: EnrichedEmployee[] }) {
  // Score de par derivado dos dados reais: tier + taxa de erro.
  const pairScore = (a: EnrichedEmployee, b: EnrichedEmployee): number | null => {
    if (a.id === b.id) return null;
    let s = 5;
    if (a.tier === '>12m' && b.tier === '>12m') s += 2.5;
    else if (a.tier === '<5m' || b.tier === '<5m') s -= 1.8;
    else s += 0.8;
    if (a.err !== null && b.err !== null) {
      const diff = Math.abs(a.err - b.err);
      if (diff < 0.02) s += 0.7;
      if (diff > 0.1) s -= 0.9;
    }
    return Math.max(0, Math.min(10, s));
  };
  const tone = (s: number) => (s >= 7.5 ? 'green' : s >= 6 ? 'yellow' : 'red');

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th />
            {laminadores.map((w) => (
              <th
                key={w.id}
                style={{
                  padding: '4px 3px',
                  fontSize: 9.5,
                  color: 'var(--fg-3)',
                  fontWeight: 500,
                  whiteSpace: 'nowrap',
                  height: 56,
                }}
              >
                <span style={{ display: 'inline-block', transform: 'rotate(-40deg)' }}>
                  {w.employee_name.split(/\s+/)[0]}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {laminadores.map((a) => (
            <tr key={a.id}>
              <td
                style={{
                  padding: '3px 8px',
                  fontSize: 10.5,
                  color: 'var(--fg-1)',
                  whiteSpace: 'nowrap',
                  textAlign: 'right',
                }}
              >
                {a.employee_name.split(/\s+/)[0]}
              </td>
              {laminadores.map((b) => {
                const s = pairScore(a, b);
                if (s === null) {
                  return (
                    <td
                      key={b.id}
                      style={{ width: 30, height: 30, background: 'var(--bg-3)' }}
                    />
                  );
                }
                const t = tone(s);
                return (
                  <td
                    key={b.id}
                    title={`${a.employee_name} + ${b.employee_name}: ${s.toFixed(1)}/10`}
                    style={{
                      width: 30,
                      height: 30,
                      textAlign: 'center',
                      background: `var(--${t}-bg)`,
                      border: `1px solid var(--${t}-bd)`,
                      fontSize: 10,
                      fontWeight: 600,
                      color: `var(--${t})`,
                      fontFamily: 'monospace',
                    }}
                  >
                    {s.toFixed(1)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div
        style={{
          marginTop: 12,
          display: 'flex',
          gap: 14,
          fontSize: 10.5,
          color: 'var(--fg-3)',
        }}
      >
        <LegendDot tone="green" label="Excelente par (>7.5)" />
        <LegendDot tone="yellow" label="OK (6-7.5)" />
        <LegendDot tone="red" label="Evitar (<6)" />
      </div>
    </div>
  );
}

export function LegendDot({ tone, label }: { tone: string; label: string }) {
  return (
    <span>
      <span
        style={{
          display: 'inline-block',
          width: 10,
          height: 10,
          background: `var(--${tone})`,
          borderRadius: 2,
          marginRight: 5,
          verticalAlign: 'middle',
        }}
      />
      {label}
    </span>
  );
}

export function SpofCard({ rec }: { rec: TrainingRecommendation }) {
  return (
    <div
      style={{
        padding: 11,
        background: 'var(--red-bg)',
        border: '1px solid var(--red-bd)',
        borderRadius: 'var(--r-sm)',
        marginBottom: 8,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 4,
        }}
      >
        <span style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}>
          {rec.targetPhase.name}
        </span>
        <span style={{ fontSize: 10.5, color: 'var(--red)' }}>
          ⚠ -{rec.expectedImpact.riskReduction.toFixed(0)}pp risco
        </span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--fg-2)', marginBottom: 6 }}>
        Formar <strong>{rec.employee.name}</strong> elimina o ponto único de falha
      </div>
      {rec.reasoning.length > 0 ? (
        <div
          style={{
            fontSize: 11,
            color: 'var(--fg-1)',
            padding: '5px 9px',
            background: 'var(--bg-1)',
            borderRadius: 4,
            display: 'flex',
            alignItems: 'center',
            gap: 5,
          }}
        >
          <Sparkles size={10} color="var(--accent)" />
          {rec.reasoning[0]}
        </div>
      ) : null}
    </div>
  );
}
