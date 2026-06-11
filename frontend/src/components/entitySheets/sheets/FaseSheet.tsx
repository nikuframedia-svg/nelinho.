/**
 * FaseSheet — sheet contextual de fase de produção (Q.116.A, read-only).
 *
 * Tabs: Operadores · Barcos exigentes · Cura · Configuração
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Sheet } from '../../dark/Sheet';
import { SheetError } from '../SheetError';
import { Tabs } from '../../dark/Tabs';
import { EmptyState } from '../../dark/EmptyState';
import { DarkBadge } from '../../dark/DarkBadge';
import { DarkButton } from '../../dark/DarkButton';
import { entityKeys, phaseGapsKeys } from '../../../lib/api/keys';
import {
  entityApi,
  type OperatorScore,
  type BoatScore,
} from '../../../lib/api/entityApi';
import { phaseGapsApi, type PhaseGap } from '../../../lib/api/governanceApi';
import { useToastContext } from '../../ToastProvider';
import { useEmployeeNamesByCode } from '../../../hooks/useEmployeeNamesByCode';
import { useBoatComplexity } from '../../../hooks/useBoatComplexity';
import { ComplexityBadge } from '../../overall/ComplexityBadge';

export interface FaseSheetProps {
  phaseId: string;
  onClose: () => void;
}

const TABS = [
  { id: 'operadores', label: 'Operadores' },
  { id: 'barcos', label: 'Barcos exigentes' },
  { id: 'cura', label: 'Cura' },
  { id: 'kpis', label: 'KPIs' },
  { id: 'configuracao', label: 'Configuração' },
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
    return <SheetError error={error} onClose={onClose} kind="fase" />;
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
        <TabCura phaseId={phaseId} />
      )}

      {tab === 'kpis' && (
        <TabKpis summary={data} />
      )}

      {tab === 'configuracao' && (
        <TabConfiguracao phaseId={phaseId} />
      )}
    </Sheet>
  );
}

function TabOperadores({ operators }: { operators: OperatorScore[] }) {
  const empNameByCode = useEmployeeNamesByCode();
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
              {op.operator_name ?? empNameByCode.get(op.operator_id) ?? op.operator_id}
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
  const { byName } = useBoatComplexity();
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
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  {b.boat_id}
                  <ComplexityBadge
                    score={byName.get(String(b.boat_id))?.score}
                    rank={byName.get(String(b.boat_id))?.rank}
                  />
                </span>
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

// ─── TabCura editável (Q.173.O) ─────────────────────────────────────────────
//
// Usa phaseGapsApi (GET /v1/plan/phase-gaps) e filtra pela fase corrente.
// Edição inline: horas (0-72) + razão ≥10 chars → PATCH.
// Badge source: 'seed' = "padrão NELO" (neutral), 'db' = "editado" (accent).

interface EditState {
  hours: string;
  reason: string;
}

function GapRow({
  gap,
  label,
}: {
  gap: PhaseGap;
  label: string;
}) {
  const toast = useToastContext();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<EditState>({ hours: String(gap.min_gap_hours), reason: gap.reason ?? '' });

  const mut = useMutation({
    mutationFn: () =>
      phaseGapsApi.update(gap.from_phase_code, gap.to_phase_code, {
        min_gap_hours: parseFloat(form.hours),
        reason: form.reason.trim(),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: phaseGapsKeys.all });
      toast.success('Transição de cura actualizada');
      setEditing(false);
    },
    onError: () => {
      toast.error('Erro ao actualizar transição de cura');
    },
  });

  const hoursNum = parseFloat(form.hours);
  const hoursValid = Number.isFinite(hoursNum) && hoursNum > 0 && hoursNum <= 72;
  const reasonValid = form.reason.trim().length >= 10;
  const canSave = hoursValid && reasonValid && !mut.isPending;

  return (
    <div
      style={{
        fontSize: 13,
        padding: '8px 10px',
        background: 'var(--bg-2)',
        borderRadius: 6,
      }}
    >
      {/* cabeçalho da linha */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--fg-3)', fontSize: 12 }}>{label}</span>
        {!editing && (
          <>
            <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
              {gap.min_gap_hours}h
            </span>
            <DarkBadge variant={gap.source === 'db' ? 'accent' : 'neutral'} size="sm">
              {gap.source === 'db' ? 'editado' : 'padrão NELO'}
            </DarkBadge>
            {gap.reason && (
              <span style={{ color: 'var(--fg-3)', fontSize: 11, fontStyle: 'italic' }}>
                {gap.reason}
              </span>
            )}
            <DarkButton size="sm" variant="ghost" onClick={() => {
              setForm({ hours: String(gap.min_gap_hours), reason: gap.reason ?? '' });
              setEditing(true);
            }}>
              Editar
            </DarkButton>
          </>
        )}
      </div>

      {/* form de edição inline */}
      {editing && (
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <label style={{ fontSize: 11, color: 'var(--fg-2)', minWidth: 48 }}>Horas</label>
            <input
              type="number"
              min={0.1}
              max={72}
              step={0.5}
              className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-2 py-1 text-xs w-20"
              value={form.hours}
              onChange={(e) => setForm((f) => ({ ...f, hours: e.target.value }))}
            />
            {!hoursValid && form.hours !== '' && (
              <span style={{ fontSize: 11, color: 'var(--danger)' }}>0–72h</span>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <label style={{ fontSize: 11, color: 'var(--fg-2)' }}>Razão (obrigatória)</label>
              <span style={{ fontSize: 11, color: form.reason.trim().length >= 10 ? 'var(--fg-3)' : 'var(--danger)' }}>
                {form.reason.trim().length}/10 mín.
              </span>
            </div>
            <textarea
              rows={2}
              className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-2 py-1 text-xs resize-none w-full"
              placeholder="Explica a razão (química real, não ajuste de fila)"
              value={form.reason}
              onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
            />
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <DarkButton size="sm" disabled={!canSave} onClick={() => mut.mutate()}>
              {mut.isPending ? 'A guardar…' : 'Guardar'}
            </DarkButton>
            <DarkButton size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancelar
            </DarkButton>
          </div>
        </div>
      )}
    </div>
  );
}

function TabCura({ phaseId }: { phaseId: string }) {
  const q = useQuery({
    queryKey: phaseGapsKeys.list(),
    queryFn: () => phaseGapsApi.list(),
  });

  if (q.isLoading) {
    return <div style={{ color: 'var(--fg-3)', fontSize: 13 }}>A carregar transições de cura…</div>;
  }
  if (q.isError) {
    return (
      <EmptyState
        title="Erro ao carregar transições de cura"
        hint="Verifica a ligação ao backend."
        size="sm"
        action={<DarkButton size="sm" onClick={() => q.refetch()}>Tentar novamente</DarkButton>}
      />
    );
  }

  const all = q.data?.items ?? [];
  const gapsIn = all.filter((g) => g.to_phase_code === phaseId && g.active);
  const gapsOut = all.filter((g) => g.from_phase_code === phaseId && g.active);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* aviso: cura é química real */}
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-3)',
          padding: '6px 10px',
          background: 'var(--bg-1)',
          borderRadius: 4,
          borderLeft: '3px solid var(--warning)',
        }}
      >
        Cura é química real (NELO_CURING_GAPS_SEED) — não confundir com tempo de fila de espera.
        Alterações afectam o próximo plano do CPO.
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
          Gaps de entrada
        </div>
        {gapsIn.length === 0 ? (
          <EmptyState title="Sem gaps de entrada para esta fase" size="sm" mascot={false} />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {gapsIn.map((g) => (
              <GapRow
                key={`${g.from_phase_code}-${g.to_phase_code}`}
                gap={g}
                label={`${g.from_phase_code} → esta fase:`}
              />
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
          <EmptyState title="Sem gaps de saída para esta fase" size="sm" mascot={false} />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {gapsOut.map((g) => (
              <GapRow
                key={`${g.from_phase_code}-${g.to_phase_code}`}
                gap={g}
                label={`esta fase → ${g.to_phase_code}:`}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Tab KPIs (Q.173.AH) ────────────────────────────────────────────────────
//
// Mostra os campos REAIS do FaseSummary que não são expostos nas outras tabs:
// fila_mediana_h (Q.160), nº de operadores qualificados, top boats count.

function TabKpis({ summary }: { summary: import('../../../lib/api/entityApi').FaseSummary }) {
  const nOps = summary.top_operators.length;
  const nBoats = summary.difficult_boats.length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Fila inter-fase */}
      <KpiCard
        label="Fila inter-fase mediana"
        hint="Mediana real de of_fp — tempo entre a fase anterior e esta. Fila = desperdício (gargalo). Cura = química (ver aba Cura)."
      >
        {summary.fila_mediana_h != null ? (
          <span style={{ fontSize: 22, fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
            {summary.fila_mediana_h.toFixed(1)}
            <span style={{ fontSize: 13, fontWeight: 400, color: 'var(--fg-2)', marginLeft: 4 }}>h</span>
          </span>
        ) : (
          <span style={{ fontSize: 13, color: 'var(--fg-3)' }}>
            Sem dados (menos de 5 observações reais)
          </span>
        )}
      </KpiCard>

      {/* Operadores qualificados */}
      <KpiCard
        label="Operadores qualificados (top afinidade)"
        hint="Número de operadores com registo de afinidade nesta fase (score calculado de of_fp)."
      >
        {nOps > 0 ? (
          <span style={{ fontSize: 22, fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
            {nOps}
          </span>
        ) : (
          <span style={{ fontSize: 13, color: 'var(--fg-3)' }}>
            Sem dados de afinidade calculados ainda
          </span>
        )}
      </KpiCard>

      {/* Barcos exigentes */}
      <KpiCard
        label="Barcos exigentes registados"
        hint="Modelos de barco com score baixo nesta fase (score calculado de of_fp — mais baixo = mais exigente)."
      >
        {nBoats > 0 ? (
          <span style={{ fontSize: 22, fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
            {nBoats}
          </span>
        ) : (
          <span style={{ fontSize: 13, color: 'var(--fg-3)' }}>
            Sem dados de dificuldade calculados ainda
          </span>
        )}
      </KpiCard>

      {/* Cura (read-only count) */}
      {(summary.curing_gaps_in.length > 0 || summary.curing_gaps_out.length > 0) && (
        <KpiCard
          label="Transições de cura"
          hint="Total de transições de cura (entrada + saída). Detalhes na aba Cura."
        >
          <span style={{ fontSize: 22, fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
            {summary.curing_gaps_in.length + summary.curing_gaps_out.length}
          </span>
        </KpiCard>
      )}
    </div>
  );
}

function KpiCard({
  label,
  hint,
  children,
}: {
  label: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        padding: '12px 16px',
        background: 'var(--bg-2)',
        borderRadius: 8,
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
    >
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--fg-2)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </div>
      <div>{children}</div>
      <div style={{ fontSize: 11, color: 'var(--fg-3)', fontStyle: 'italic' }}>{hint}</div>
    </div>
  );
}

// ─── Tab Configuração (Q.135.3.4) ───────────────────────────────────────────

function TabConfiguracao({ phaseId }: { phaseId: string }) {
  const toast = useToastContext();
  const queryClient = useQueryClient();
  const empNameByCode = useEmployeeNamesByCode();

  const { data, isLoading, error } = useQuery({
    queryKey: entityKeys.faseConfig(phaseId),
    queryFn: () => entityApi.phaseConfig.get(phaseId),
  });

  // Estado local do formulário — sincronizado com data quando carrega
  const [selectedWorkers, setSelectedWorkers] = useState<string[] | null>(null);
  const [teamSize, setTeamSize] = useState<string>('');
  const [numStations, setNumStations] = useState<string>('');
  const [note, setNote] = useState<string>('');
  const [initialised, setInitialised] = useState(false);

  // Sincroniza estado local quando os dados chegam (uma só vez)
  if (data && !initialised) {
    setSelectedWorkers(data.overrides.allowed_worker_ids ?? null);
    setTeamSize(data.overrides.team_size_override != null ? String(data.overrides.team_size_override) : '');
    setNumStations(data.overrides.num_stations_override != null ? String(data.overrides.num_stations_override) : '');
    setNote(data.overrides.note ?? '');
    setInitialised(true);
  }

  const mutation = useMutation({
    mutationFn: (body: Parameters<typeof entityApi.phaseConfig.put>[1]) =>
      entityApi.phaseConfig.put(phaseId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: entityKeys.faseConfig(phaseId) });
      toast.success('Configuração guardada.');
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Erro desconhecido';
      toast.error(msg);
    },
  });

  if (isLoading) {
    return (
      <div style={{ color: 'var(--fg-2)', fontSize: 14, padding: '16px 0' }}>
        A carregar configuração...
      </div>
    );
  }

  if (error || !data) {
    return (
      <EmptyState
        title="Erro ao carregar configuração"
        hint={error instanceof Error ? error.message : 'Tenta novamente.'}
        size="sm"
      />
    );
  }

  const { baselines, overrides } = data;
  const hasOverride =
    overrides.team_size_override != null ||
    overrides.num_stations_override != null ||
    (overrides.allowed_worker_ids != null && overrides.allowed_worker_ids.length > 0) ||
    !!overrides.note;

  function toggleWorker(id: string) {
    setSelectedWorkers((prev) => {
      const current = prev ?? [];
      if (current.includes(id)) {
        const next = current.filter((w) => w !== id);
        return next.length === 0 ? null : next;
      }
      return [...current, id];
    });
  }

  function handleGuardar() {
    const body: Parameters<typeof entityApi.phaseConfig.put>[1] = {
      team_size_override: teamSize !== '' ? parseInt(teamSize, 10) : null,
      num_stations_override: numStations !== '' ? parseInt(numStations, 10) : null,
      allowed_worker_ids: selectedWorkers && selectedWorkers.length > 0 ? selectedWorkers : null,
      note: note.trim() !== '' ? note.trim() : null,
    };
    mutation.mutate(body);
  }

  const effectiveAllowed = selectedWorkers ?? [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Badge override ativo */}
      {hasOverride && (
        <div>
          <DarkBadge variant="warning">Override ativo</DarkBadge>
        </div>
      )}

      {/* ── Secção: Operadores ── */}
      <section>
        <SectionTitle>Operadores qualificados</SectionTitle>
        <div style={{ fontSize: 12, color: 'var(--fg-2)', marginBottom: 8 }}>
          Seleciona os operadores permitidos para esta fase. Sem seleção = todos os qualificados.
        </div>
        {baselines.capable_worker_ids.length === 0 ? (
          <EmptyState
            title="Sem operadores qualificados registados"
            hint="Os dados de competências ainda não foram calculados para esta fase."
            size="sm"
            mascot={false}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {baselines.capable_worker_ids.map((wid) => {
              const isAffinity = baselines.affinity_worker_ids.includes(wid);
              const isChecked = effectiveAllowed.length === 0 || effectiveAllowed.includes(wid);
              const isExplicitlySet = (selectedWorkers ?? []).length > 0;
              const isCheckedExplicit = isExplicitlySet ? (selectedWorkers ?? []).includes(wid) : false;
              return (
                <label
                  key={wid}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '6px 10px',
                    background: 'var(--bg-2)',
                    borderRadius: 6,
                    cursor: 'pointer',
                    fontSize: 13,
                    opacity: isChecked ? 1 : 0.5,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={isExplicitlySet ? isCheckedExplicit : true}
                    onChange={() => toggleWorker(wid)}
                    style={{ accentColor: 'var(--accent)', width: 15, height: 15 }}
                  />
                  <WorkerLabel code={wid} name={empNameByCode.get(wid)} />
                  {isAffinity && (
                    <span style={{ color: '#f59e0b', fontSize: 12 }}>★ afinidade</span>
                  )}
                </label>
              );
            })}
          </div>
        )}
        {(selectedWorkers ?? []).length > 0 && (
          <button
            onClick={() => setSelectedWorkers(null)}
            style={{
              marginTop: 8,
              fontSize: 12,
              color: 'var(--fg-2)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              textDecoration: 'underline',
            }}
          >
            Limpar seleção (usar todos os qualificados)
          </button>
        )}
      </section>

      {/* ── Secção: Nº colaboradores / estações ── */}
      <section>
        <SectionTitle>Dimensionamento</SectionTitle>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--fg-2)', marginBottom: 4 }}>
              Nº de colaboradores
            </label>
            <input
              type="number"
              min={1}
              value={teamSize}
              onChange={(e) => setTeamSize(e.target.value)}
              placeholder={`default: ${baselines.team_size_default}`}
              style={{
                width: '100%',
                padding: '6px 10px',
                borderRadius: 6,
                border: '1px solid var(--bd-2)',
                fontSize: 13,
                boxSizing: 'border-box',
                background: 'var(--bg-3)',
                color: 'var(--fg-0)',
                colorScheme: 'dark',
              }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--fg-2)', marginBottom: 4 }}>
              Nº de estações
            </label>
            <input
              type="number"
              min={1}
              value={numStations}
              onChange={(e) => setNumStations(e.target.value)}
              placeholder={`sugerido: ${baselines.suggested_stations}`}
              style={{
                width: '100%',
                padding: '6px 10px',
                borderRadius: 6,
                border: '1px solid var(--bd-2)',
                fontSize: 13,
                boxSizing: 'border-box',
                background: 'var(--bg-3)',
                color: 'var(--fg-0)',
                colorScheme: 'dark',
              }}
            />
          </div>
        </div>
      </section>

      {/* ── Secção: Nota ── */}
      <section>
        <SectionTitle>Nota</SectionTitle>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Nota opcional sobre esta configuração..."
          rows={2}
          style={{
            width: '100%',
            padding: '6px 10px',
            borderRadius: 6,
            border: '1px solid var(--bd-2)',
            fontSize: 13,
            resize: 'vertical',
            boxSizing: 'border-box',
            background: 'var(--bg-3)',
            color: 'var(--fg-0)',
            colorScheme: 'dark',
          }}
        />
      </section>

      {/* ── Secção: Ordem normal (read-only) ── */}
      <section>
        <SectionTitle>Ordem normal</SectionTitle>
        <div
          style={{
            fontSize: 13,
            padding: '8px 12px',
            background: 'var(--bg-2)',
            borderRadius: 6,
            display: 'flex',
            gap: 8,
            alignItems: 'center',
            flexWrap: 'wrap',
          }}
        >
          <span style={{ color: 'var(--fg-2)' }}>
            {baselines.typical_prev_phase ?? '—'}
          </span>
          <span style={{ color: 'var(--fg-3)' }}>→</span>
          <span style={{ fontWeight: 600 }}>esta fase</span>
          {baselines.canonical_rank != null && (
            <DarkBadge variant="neutral">#{baselines.canonical_rank}</DarkBadge>
          )}
          <span style={{ color: 'var(--fg-3)' }}>→</span>
          <span style={{ color: 'var(--fg-2)' }}>
            {baselines.typical_next_phase ?? '—'}
          </span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
          Para alterar a sequência, edita o modelo de routing no detalhe do modelo.
        </div>
      </section>

      {/* ── Secção: Duração esperada (read-only) ── */}
      <section>
        <SectionTitle>Duração esperada</SectionTitle>
        <div
          style={{
            fontSize: 13,
            padding: '8px 12px',
            background: 'var(--bg-2)',
            borderRadius: 6,
          }}
        >
          {baselines.expected_duration_h != null ? (
            <span>
              O sistema diz:{' '}
              <strong style={{ fontVariantNumeric: 'tabular-nums' }}>
                ~{baselines.expected_duration_h.toFixed(1)}h
              </strong>{' '}
              <span style={{ color: 'var(--fg-2)' }}>(do histórico)</span>
            </span>
          ) : (
            <span style={{ color: 'var(--fg-2)' }}>— sem dados históricos suficientes</span>
          )}
        </div>
      </section>

      {/* ── Botão Guardar ── */}
      <div style={{ paddingTop: 4 }}>
        <button
          onClick={handleGuardar}
          disabled={mutation.isPending}
          style={{
            padding: '8px 20px',
            borderRadius: 6,
            background: mutation.isPending ? 'var(--bg-3)' : 'var(--accent)',
            color: '#fff',
            border: 'none',
            cursor: mutation.isPending ? 'not-allowed' : 'pointer',
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          {mutation.isPending ? 'A guardar...' : 'Guardar'}
        </button>
      </div>
    </div>
  );
}

/**
 * WorkerLabel (Q.154.A) — mostra o NOME do colaborador com o código pequeno ao
 * lado (referência cruzada com o ERP e com o whitelist guardado). Sem nome
 * resolvido (ex. operador histórico fora do core), mostra só o código cru.
 */
function WorkerLabel({ code, name }: { code: string; name?: string }) {
  if (!name) {
    return <span style={{ flex: 1, fontVariantNumeric: 'tabular-nums' }}>{code}</span>;
  }
  return (
    <span style={{ flex: 1, display: 'flex', alignItems: 'baseline', gap: 8, minWidth: 0 }}>
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {name}
      </span>
      <span style={{ color: 'var(--fg-3)', fontSize: 11, fontVariantNumeric: 'tabular-nums' }}>
        {code}
      </span>
    </span>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
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
      {children}
    </div>
  );
}
