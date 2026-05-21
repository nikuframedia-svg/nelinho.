// EquipaPage · AmanhaTab (Q.60.T). ZERO MOCKS — endpoints reais.
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CalendarRange, Sparkles } from 'lucide-react';
import { workforceApi } from '../../../lib/workforceApi';
import { equipaApi } from '../../../components/equipa/equipaApi';
import { type SimulationResult } from '../../../components/workforce/types';
import { type EnrichedEmployee, Tag, SectionHeader } from '../equipaShared';

export function AmanhaTab({ employees }: { employees: EnrichedEmployee[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const trainingQuery = useQuery({
    queryKey: ['equipa', 'amanha', 'training'],
    queryFn: () => workforceApi.getTrainingRecommendations(8),
    staleTime: 120_000,
    retry: 0,
  });

  const simQuery = useQuery({
    queryKey: ['equipa', 'amanha', 'simulate', selectedId],
    queryFn: () => equipaApi.simulateAbsence(selectedId as string),
    enabled: !!selectedId,
    retry: 0,
  });

  const activeEmployees = employees.filter((e) => e.status === 'ACTIVE');

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
      {/* Simulador de ausência */}
      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionHeader
          icon={<CalendarRange size={14} />}
          title="E se faltar amanhã?"
          subtitle="Escolhe um operador para simular a ausência"
        />
        <div style={{ marginBottom: 12 }}>
          <select
            value={selectedId ?? ''}
            onChange={(e) => setSelectedId(e.target.value || null)}
            style={{
              width: '100%',
              padding: '8px 10px',
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-2)',
              borderRadius: 'var(--r-sm)',
              color: 'var(--fg-0)',
              fontSize: 12.5,
              outline: 'none',
            }}
          >
            <option value="">Selecciona um operador…</option>
            {activeEmployees.map((e) => (
              <option key={e.id} value={e.id}>
                {e.employee_name} · {e.tier}
              </option>
            ))}
          </select>
        </div>
        {!selectedId ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            Escolhe um operador acima para ver o impacto da ausência.
          </div>
        ) : simQuery.isLoading ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            A simular…
          </div>
        ) : simQuery.isError ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--danger)', fontSize: 12 }}>
            Erro a simular a ausência.
          </div>
        ) : simQuery.data ? (
          <AbsenceImpact sim={simQuery.data} />
        ) : null}
      </div>

      {/* Recomendações de formação */}
      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionHeader
          icon={<Sparkles size={14} />}
          title="Recomendações de formação"
          subtitle="Ordenadas por impacto na redução de risco"
        />
        {trainingQuery.isLoading ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            A carregar recomendações…
          </div>
        ) : trainingQuery.isError ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--danger)', fontSize: 12 }}>
            Erro a carregar /v1/workforce/training-recommendations.
          </div>
        ) : !trainingQuery.data || trainingQuery.data.length === 0 ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            Sem recomendações de formação de momento.
          </div>
        ) : (
          trainingQuery.data.map((rec) => (
            <div
              key={rec.id}
              style={{
                padding: 11,
                background: 'var(--bg-2)',
                border: '1px solid var(--bd-1)',
                borderRadius: 'var(--r-sm)',
                marginBottom: 8,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                }}
              >
                <span style={{ fontSize: 12, color: 'var(--fg-0)', fontWeight: 500 }}>
                  {rec.employee.name} → {rec.targetPhase.name}
                </span>
                <Tag
                  tone={
                    rec.priority === 'critical'
                      ? 'red'
                      : rec.priority === 'high'
                        ? 'orange'
                        : 'yellow'
                  }
                >
                  {rec.priority}
                </Tag>
              </div>
              <div style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 4 }}>
                {rec.reasoning[0] ?? '—'} · {rec.estimatedCost.hours}h estimadas
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export function AbsenceImpact({ sim }: { sim: SimulationResult }) {
  const metrics: Array<{ label: string; baseline: number; simulated: number; worseUp: boolean }> = [
    {
      label: 'SPOFs',
      baseline: sim.baseline.spofCount,
      simulated: sim.simulated.spofCount,
      worseUp: true,
    },
    {
      label: 'Fases em risco',
      baseline: sim.baseline.phasesAtRisk,
      simulated: sim.simulated.phasesAtRisk,
      worseUp: true,
    },
    {
      label: 'Score de risco médio',
      baseline: Math.round(sim.baseline.avgRiskScore),
      simulated: Math.round(sim.simulated.avgRiskScore),
      worseUp: true,
    },
  ];
  return (
    <div className="space-y-3">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {metrics.map((m) => {
          const delta = m.simulated - m.baseline;
          const worse = m.worseUp ? delta > 0 : delta < 0;
          return (
            <div
              key={m.label}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '9px 12px',
                background: 'var(--bg-2)',
                borderRadius: 'var(--r-sm)',
              }}
            >
              <span style={{ fontSize: 12, color: 'var(--fg-1)' }}>{m.label}</span>
              <span className="tabular" style={{ fontSize: 12.5 }}>
                <span style={{ color: 'var(--fg-3)' }}>{m.baseline}</span>
                <span style={{ color: 'var(--fg-4)', margin: '0 6px' }}>→</span>
                <span
                  style={{
                    color: delta === 0 ? 'var(--fg-1)' : worse ? 'var(--red)' : 'var(--green)',
                    fontWeight: 600,
                  }}
                >
                  {m.simulated}
                </span>
                {delta !== 0 ? (
                  <span
                    style={{
                      color: worse ? 'var(--red)' : 'var(--green)',
                      fontSize: 10.5,
                      marginLeft: 6,
                    }}
                  >
                    ({delta > 0 ? '+' : ''}
                    {delta})
                  </span>
                ) : null}
              </span>
            </div>
          );
        })}
      </div>
      {sim.recommendations.length > 0 ? (
        <div
          style={{
            padding: 11,
            background: 'var(--accent-bg)',
            border: '1px solid var(--accent-bd)',
            borderRadius: 'var(--r-sm)',
            fontSize: 11.5,
            color: 'var(--fg-1)',
          }}
        >
          <Sparkles
            size={11}
            color="var(--accent)"
            style={{ verticalAlign: 'middle', marginRight: 6 }}
          />
          {sim.recommendations[0]}
        </div>
      ) : null}
    </div>
  );
}
