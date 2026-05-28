/**
 * FaseSheet — sheet contextual de fase de produção (Q.116.A, read-only).
 *
 * Tabs: Operadores · Barcos exigentes · Cura
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Sheet } from '../../dark/Sheet';
import { Tabs } from '../../dark/Tabs';
import { EmptyState } from '../../dark/EmptyState';
import { entityKeys } from '../../../lib/api/keys';
import { entityApi, type OperatorScore, type BoatScore, type CuringGap } from '../../../lib/api/entityApi';

export interface FaseSheetProps {
  phaseId: string;
  onClose: () => void;
}

const TABS = [
  { id: 'operadores', label: 'Operadores' },
  { id: 'barcos', label: 'Barcos exigentes' },
  { id: 'cura', label: 'Cura' },
];

export default function FaseSheet({ phaseId, onClose }: FaseSheetProps) {
  const [tab, setTab] = useState('operadores');

  const { data, isLoading, error } = useQuery({
    queryKey: entityKeys.fase(phaseId),
    queryFn: () => entityApi.fase(phaseId),
  });

  if (isLoading) {
    return (
      <Sheet open={true} onClose={onClose} title="A carregar..." width={720}>
        <div style={{ color: 'var(--fg-2)', fontSize: 14 }}>
          A carregar dados da fase...
        </div>
      </Sheet>
    );
  }

  if (error || !data) {
    return (
      <Sheet open={true} onClose={onClose} title="Erro" width={720}>
        <div style={{ color: 'var(--danger, #ef4444)', fontSize: 14 }}>
          Erro ao carregar dados:{' '}
          {error instanceof Error ? error.message : 'Erro desconhecido'}
        </div>
      </Sheet>
    );
  }

  return (
    <Sheet
      open={true}
      onClose={onClose}
      title={data.phase_name ?? phaseId}
      subtitle="Fase de produção"
      width={720}
    >
      <div style={{ borderBottom: '1px solid var(--bd-1)', marginBottom: 16 }}>
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === 'operadores' && (
        <TabOperadores operators={data.top_operators} />
      )}

      {tab === 'barcos' && (
        <TabBarcos boats={data.difficult_boats} />
      )}

      {tab === 'cura' && (
        <TabCura
          gapsIn={data.curing_gaps_in}
          gapsOut={data.curing_gaps_out}
        />
      )}
    </Sheet>
  );
}

function TabOperadores({ operators }: { operators: OperatorScore[] }) {
  if (operators.length === 0) {
    return (
      <EmptyState
        title="Sem dados"
        hint="O job de afinidades ainda não correu para esta fase."
        size="sm"
      />
    );
  }

  return (
    <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid var(--bd-1)', color: 'var(--fg-2)' }}>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>
            Operador
          </th>
          <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 500 }}>
            Score (0-1)
          </th>
          <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 500 }}>
            Amostras
          </th>
        </tr>
      </thead>
      <tbody>
        {operators.map((op) => (
          <tr
            key={op.operator_id}
            style={{ borderBottom: '1px solid var(--bd-1)' }}
          >
            <td style={{ padding: '8px 8px' }}>
              {op.operator_name ?? op.operator_id}
            </td>
            <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {op.score.toFixed(3)}
            </td>
            <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--fg-2)' }}>
              {op.sample_count}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TabBarcos({ boats }: { boats: BoatScore[] }) {
  if (boats.length === 0) {
    return (
      <EmptyState
        title="Sem dados"
        hint="Sem registos de barcos para esta fase ainda."
        size="sm"
      />
    );
  }

  return (
    <div>
      <div
        style={{
          fontSize: 12,
          color: 'var(--fg-2)',
          marginBottom: 12,
          padding: '6px 8px',
          background: 'var(--bg-2)',
          borderRadius: 6,
        }}
      >
        Score mais baixo = barco mais exigente nesta fase.
      </div>
      <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--bd-1)', color: 'var(--fg-2)' }}>
            <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>
              Barco
            </th>
            <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 500 }}>
              Score (0-1)
            </th>
            <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 500 }}>
              Amostras
            </th>
          </tr>
        </thead>
        <tbody>
          {boats.map((b) => (
            <tr
              key={b.boat_id}
              style={{ borderBottom: '1px solid var(--bd-1)' }}
            >
              <td style={{ padding: '8px 8px' }}>
                {b.boat_id}
              </td>
              <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                {b.score.toFixed(3)}
              </td>
              <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--fg-2)' }}>
                {b.sample_count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TabCura({
  gapsIn,
  gapsOut,
}: {
  gapsIn: CuringGap[];
  gapsOut: CuringGap[];
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--fg-2)',
            marginBottom: 8,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          Gaps de entrada
        </div>
        {gapsIn.length === 0 ? (
          <EmptyState title="Sem gaps de entrada" size="sm" mascot={false} />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {gapsIn.map((g, i) => (
              <div
                key={i}
                style={{
                  fontSize: 13,
                  padding: '6px 10px',
                  background: 'var(--bg-2)',
                  borderRadius: 6,
                  display: 'flex',
                  gap: 8,
                  alignItems: 'center',
                }}
              >
                <span style={{ color: 'var(--fg-2)' }}>{g.from_phase ?? '—'}</span>
                <span style={{ color: 'var(--fg-3)' }}>→ esta fase:</span>
                <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {g.hours}h
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--fg-2)',
            marginBottom: 8,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          Gaps de saída
        </div>
        {gapsOut.length === 0 ? (
          <EmptyState title="Sem gaps de saída" size="sm" mascot={false} />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {gapsOut.map((g, i) => (
              <div
                key={i}
                style={{
                  fontSize: 13,
                  padding: '6px 10px',
                  background: 'var(--bg-2)',
                  borderRadius: 6,
                  display: 'flex',
                  gap: 8,
                  alignItems: 'center',
                }}
              >
                <span style={{ color: 'var(--fg-3)' }}>esta fase →</span>
                <span style={{ color: 'var(--fg-2)' }}>{g.to_phase ?? '—'}:</span>
                <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {g.hours}h
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
