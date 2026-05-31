/**
 * OperadorSheet — sheet contextual de operador (Q.116.E, read-only).
 *
 * Tabs: Top fases · Atividade hoje · Histórico
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Sheet } from '../../dark/Sheet';
import { Tabs } from '../../dark/Tabs';
import { EmptyState } from '../../dark/EmptyState';
import { entityKeys } from '../../../lib/api/keys';
import { entityApi, type TopPhaseForOperator } from '../../../lib/api/entityApi';

export interface OperadorSheetProps {
  operatorId: string;
  onClose: () => void;
}

const TABS = [
  { id: 'top-fases', label: 'Top fases' },
  { id: 'atividade', label: 'Atividade hoje' },
  { id: 'historico', label: 'Histórico' },
];

export default function OperadorSheet({ operatorId, onClose }: OperadorSheetProps) {
  const [tab, setTab] = useState('top-fases');

  const { data, isLoading, error } = useQuery({
    queryKey: entityKeys.operador(operatorId),
    queryFn: () => entityApi.operador(operatorId),
  });

  if (isLoading) {
    return (
      <Sheet open={true} onClose={onClose} title="A carregar..." width={720}>
        <div style={{ color: 'var(--fg-2)', fontSize: 14 }}>
          A carregar dados do operador...
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

  const subtitle = `${data.role ?? '—'} · ${data.active ? 'Activo' : 'Inactivo'} · ${data.total_phases_with_data} fases com dados`;

  return (
    <Sheet
      open={true}
      onClose={onClose}
      title={data.operator_name ?? operatorId}
      subtitle={subtitle}
      width={720}
    >
      <div style={{ borderBottom: '1px solid var(--bd-1)', marginBottom: 16 }}>
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === 'top-fases' && (
        <TabTopFases phases={data.top_phases} />
      )}

      {tab === 'atividade' && (
        <EmptyState
          title="Sem dados de atividade"
          hint="Q.116.F vai mostrar tarefas do dia."
          size="sm"
        />
      )}

      {tab === 'historico' && (
        <EmptyState
          title="Sem histórico"
          hint="Q.116.F vai mostrar histórico de fases."
          size="sm"
        />
      )}
    </Sheet>
  );
}

function TabTopFases({ phases }: { phases: TopPhaseForOperator[] }) {
  if (phases.length === 0) {
    return (
      <EmptyState
        title="Sem dados de afinidade"
        hint="O job ainda não correu para este operador."
        size="sm"
      />
    );
  }

  return (
    <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid var(--bd-1)', color: 'var(--fg-2)' }}>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>
            Fase
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
        {phases.map((p) => (
          <tr
            key={p.phase_id}
            style={{ borderBottom: '1px solid var(--bd-1)' }}
          >
            <td style={{ padding: '8px 8px' }}>
              {p.phase_name ?? p.phase_id}
            </td>
            <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {p.score.toFixed(3)}
            </td>
            <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--fg-2)' }}>
              {p.sample_count}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
