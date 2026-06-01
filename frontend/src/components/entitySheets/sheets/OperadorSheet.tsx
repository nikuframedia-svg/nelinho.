/**
 * OperadorSheet — sheet contextual de operador (Q.116.E/F, read-only).
 *
 * Tabs: Top fases · Atividade hoje · Histórico
 * Q.116.F: Atividade hoje (tarefas do plano) + Histórico (fases do ERP)
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Sheet } from '../../dark/Sheet';
import { SheetError } from '../SheetError';
import { Tabs } from '../../dark/Tabs';
import { EmptyState } from '../../dark/EmptyState';
import { entityKeys } from '../../../lib/api/keys';
import {
  entityApi,
  type TopPhaseForOperator,
  type OperatorTask,
  type OperatorPhaseHistory,
} from '../../../lib/api/entityApi';
import { Clickable } from '../Clickable';

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
    return <SheetError error={error} onClose={onClose} kind="operador" />;
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
        <TabAtividade tasks={data.today_tasks} />
      )}

      {tab === 'historico' && (
        <TabHistorico history={data.phase_history} />
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

// ─── Tab Atividade hoje (Q.116.F) ────────────────────────────────────────────

function fmtTime(iso: string | null): string {
  if (!iso) return '—';
  const m = iso.match(/T(\d{2}:\d{2})/);
  return m ? m[1] : iso;
}

function TabAtividade({ tasks }: { tasks: OperatorTask[] }) {
  if (tasks.length === 0) {
    return (
      <EmptyState
        title="Sem tarefas para hoje"
        hint="Este operador não tem operações atribuídas no plano de hoje (ou ainda não há plano)."
        size="sm"
      />
    );
  }
  return (
    <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid var(--bd-1)', color: 'var(--fg-2)' }}>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>#</th>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>Fase</th>
          <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 500 }}>Início</th>
          <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 500 }}>Fim</th>
        </tr>
      </thead>
      <tbody>
        {tasks.map((t) => (
          <tr key={t.operation_id} style={{ borderBottom: '1px solid var(--bd-1)' }}>
            <td style={{ padding: '8px 8px' }}>
              {t.order_legacy_id != null ? (
                <Clickable kind="encomenda" id={t.order_legacy_id}>
                  #{t.order_legacy_id}
                </Clickable>
              ) : (
                '—'
              )}
            </td>
            <td style={{ padding: '8px 8px' }}>{t.phase_name}</td>
            <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {fmtTime(t.start_time)}
            </td>
            <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--fg-2)' }}>
              {fmtTime(t.end_time)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ─── Tab Histórico de fases (Q.116.F) ────────────────────────────────────────

function TabHistorico({ history }: { history: OperatorPhaseHistory[] }) {
  if (history.length === 0) {
    return (
      <EmptyState
        title="Sem histórico no ERP"
        hint="Ainda não há registo de fases trabalhadas (factory_raw.of_fp) para este operador."
        size="sm"
      />
    );
  }
  return (
    <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid var(--bd-1)', color: 'var(--fg-2)' }}>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>#</th>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>Fase</th>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>Início</th>
          <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 500 }}>Horas</th>
        </tr>
      </thead>
      <tbody>
        {history.map((h, i) => (
          <tr key={`${h.of_legacy_id ?? 'x'}-${h.phase_id}-${i}`} style={{ borderBottom: '1px solid var(--bd-1)' }}>
            <td style={{ padding: '8px 8px' }}>
              {h.of_legacy_id != null ? (
                <Clickable kind="encomenda" id={h.of_legacy_id}>
                  #{h.of_legacy_id}
                </Clickable>
              ) : (
                '—'
              )}
            </td>
            <td style={{ padding: '8px 8px' }}>{h.phase_name ?? h.phase_id}</td>
            <td style={{ padding: '8px 8px', color: 'var(--fg-2)', fontVariantNumeric: 'tabular-nums' }}>
              {h.started_at ? h.started_at.slice(0, 16).replace('T', ' ') : '—'}
            </td>
            <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--fg-2)' }}>
              {h.hours != null ? h.hours.toFixed(1) : '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
