/**
 * WorkerProfile — perfil enriquecido do operador num Sheet, 5 sub-tabs.
 *
 * Port fiel do `WorkerProfile` do protótipo NELO (page-equipa.jsx) ligado
 * a endpoints reais:
 *   • Perfil    — quality-score (ML vs override) + skills aptas
 *   • Skills    — skill-matrix por fase, toggle real via PATCH .../skills
 *   • Histórico — operações recentes (/history)
 *   • Nível     — level-summary por grupo de área (escala 3=melhor) +
 *     barcos recomendados (Q.53.L)
 *   • Notas     — campo livre (não persiste — não há endpoint de notas)
 *
 * ZERO MOCKS — secções sem dados mostram empty state honesto.
 *
 * Sprints Q.52.H · Q.53.L.
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { GitBranch, Save } from 'lucide-react';
import { Sheet } from '../dark';
import {
  workforceEmployeesApi,
  type QualityScoreResult,
  type SkillMatrixResult,
  type OperationHistoryResult,
} from '../../lib/api';
import { equipaApi, type LevelSummary } from './equipaApi';
import { LevelGauge, levelTone } from './LevelScale';

export interface WorkerProfileEmployee {
  id: string;
  name: string;
  tier: '>12m' | '<12m' | '<5m';
}

interface ProfileTab {
  id: 'perfil' | 'skills' | 'historico' | 'nivel' | 'notas';
  label: string;
}

export function WorkerProfile({
  employee,
  onClose,
  onCompare,
}: {
  employee: WorkerProfileEmployee | null;
  onClose: () => void;
  onCompare: (id: string) => void;
}): ReactNode {
  const [tab, setTab] = useState<ProfileTab['id']>('perfil');
  const [notes, setNotes] = useState('');

  const id = employee?.id ?? '';

  const qualityQuery = useQuery({
    queryKey: ['equipa', 'profile', 'quality', id],
    queryFn: () => workforceEmployeesApi.qualityScore(id),
    enabled: !!employee,
    retry: 0,
  });
  const skillsQuery = useQuery({
    queryKey: ['equipa', 'profile', 'skills', id],
    queryFn: () => workforceEmployeesApi.skillMatrix(id),
    enabled: !!employee,
    retry: 0,
  });
  const historyQuery = useQuery({
    queryKey: ['equipa', 'profile', 'history', id],
    queryFn: () => workforceEmployeesApi.history(id, { limit: 20 }),
    enabled: !!employee && tab === 'historico',
    retry: 0,
  });
  const levelQuery = useQuery({
    queryKey: ['equipa', 'profile', 'level', id],
    queryFn: () => equipaApi.levelSummary(id),
    enabled: !!employee && tab === 'nivel',
    retry: 0,
  });

  if (!employee) return null;

  const quality = qualityQuery.data;
  const subtitle = quality
    ? `★ ${quality.score.toFixed(1)} · ${employee.tier} · ${quality.operations.toLocaleString('pt-PT')} ops · ${(quality.defect_rate * 100).toFixed(1)}% erro`
    : employee.tier;

  const tabs: ProfileTab[] = [
    { id: 'perfil', label: 'Perfil' },
    { id: 'skills', label: 'Skills' },
    { id: 'historico', label: 'Histórico' },
    { id: 'nivel', label: 'Nível' },
    { id: 'notas', label: 'Notas' },
  ];

  return (
    <Sheet
      open={!!employee}
      onClose={onClose}
      title={employee.name}
      subtitle={subtitle}
      width={720}
      footer={
        <>
          <button
            type="button"
            onClick={() => onCompare(employee.id)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors"
            style={{
              background: 'var(--bg-2)',
              color: 'var(--fg-0)',
              border: '1px solid var(--bd-2)',
            }}
          >
            <GitBranch size={13} />
            Comparar
          </button>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-white transition-colors"
            style={{ background: 'var(--blue)' }}
          >
            <Save size={13} />
            Fechar
          </button>
        </>
      }
    >
      {/* Sub-tabs */}
      <div
        style={{
          display: 'flex',
          borderBottom: '1px solid var(--bd-1)',
          marginBottom: 14,
          marginTop: -6,
          gap: 2,
        }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            style={{
              padding: '7px 12px',
              background: 'transparent',
              border: 'none',
              borderBottom: `1.5px solid ${tab === t.id ? 'var(--fg-0)' : 'transparent'}`,
              color: tab === t.id ? 'var(--fg-0)' : 'var(--fg-2)',
              fontSize: 12,
              fontWeight: tab === t.id ? 600 : 500,
              cursor: 'pointer',
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'perfil' && (
        <PerfilTab quality={quality} loading={qualityQuery.isLoading} skills={skillsQuery.data} />
      )}
      {tab === 'skills' && (
        <SkillsTab
          employeeId={employee.id}
          skills={skillsQuery.data}
          loading={skillsQuery.isLoading}
          isError={skillsQuery.isError}
        />
      )}
      {tab === 'historico' && (
        <HistoricoTab
          data={historyQuery.data}
          loading={historyQuery.isLoading}
          isError={historyQuery.isError}
        />
      )}
      {tab === 'nivel' && (
        <NivelTab
          data={levelQuery.data}
          loading={levelQuery.isLoading}
          isError={levelQuery.isError}
        />
      )}
      {tab === 'notas' && (
        <div>
          <SectionLabel>Notas do gestor</SectionLabel>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notas internas sobre o operador…"
            className="text-slate-900 placeholder:text-slate-400"
            style={{
              width: '100%',
              minHeight: 140,
              padding: 12,
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-2)',
              borderRadius: 'var(--r-md)',
              color: 'var(--fg-0)',
              outline: 'none',
              fontSize: 12.5,
              fontFamily: 'inherit',
              resize: 'vertical',
              lineHeight: 1.5,
            }}
          />
          <div style={{ marginTop: 8, fontSize: 10.5, color: 'var(--fg-3)' }}>
            As notas não são guardadas — ainda não há endpoint de notas de
            operador no backend.
          </div>
        </div>
      )}
    </Sheet>
  );
}

// ─── Sub-tab: Perfil ────────────────────────────────────────────────────────

function PerfilTab({
  quality,
  loading,
  skills,
}: {
  quality: QualityScoreResult | undefined;
  loading: boolean;
  skills: SkillMatrixResult | undefined;
}) {
  if (loading) return <Loading />;
  if (!quality) {
    return <EmptyHint text="Sem quality-score registado para este operador." />;
  }
  const aptPhases = (skills?.phases ?? []).filter((p) => p.can_do);
  return (
    <div className="space-y-3">
      <Card>
        <SectionLabel>Score de qualidade</SectionLabel>
        <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
          <span
            className="display tabular"
            style={{ fontSize: 28, color: 'var(--fg-0)', fontWeight: 500 }}
          >
            ★ {quality.score.toFixed(1)}
          </span>
          <span style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>
            {quality.method === 'laplace_smoothed'
              ? `Derivado de ${quality.operations.toLocaleString('pt-PT')} operações · ${quality.defects} defeitos`
              : 'Score por defeito — sem histórico de operações ainda'}
          </span>
        </div>
      </Card>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Card>
          <SectionLabel>Taxa de erro</SectionLabel>
          <span
            className="tabular"
            style={{
              fontSize: 20,
              fontWeight: 600,
              color:
                quality.defect_rate > 0.1 ? 'var(--red)' : 'var(--green)',
            }}
          >
            {(quality.defect_rate * 100).toFixed(1)}%
          </span>
        </Card>
        <Card>
          <SectionLabel>Operações</SectionLabel>
          <span
            className="tabular"
            style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-0)' }}
          >
            {quality.operations.toLocaleString('pt-PT')}
          </span>
        </Card>
      </div>
      <Card>
        <SectionLabel>Fases aptas ({aptPhases.length})</SectionLabel>
        {aptPhases.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
            Sem fases aptas registadas.
          </div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {aptPhases.map((p) => (
              <span
                key={p.phase_id}
                style={{
                  fontSize: 11,
                  padding: '3px 9px',
                  background: 'var(--accent-bg)',
                  border: '1px solid var(--accent-bd)',
                  borderRadius: 999,
                  color: 'var(--accent)',
                }}
              >
                {p.phase_name ?? p.phase_id}
              </span>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

// ─── Sub-tab: Skills ────────────────────────────────────────────────────────

const LEVEL_STEPS = [1.0, 1.5, 2.0, 2.5, 3.0];

function SkillsTab({
  employeeId,
  skills,
  loading,
  isError,
}: {
  employeeId: string;
  skills: SkillMatrixResult | undefined;
  loading: boolean;
  isError: boolean;
}) {
  const queryClient = useQueryClient();
  const toggleMutation = useMutation({
    mutationFn: (payload: {
      phase_id: string;
      can_do: boolean;
      nivel?: number;
    }) => equipaApi.toggleSkill(employeeId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['equipa', 'profile', 'skills', employeeId],
      });
      queryClient.invalidateQueries({
        queryKey: ['equipa', 'profile', 'level', employeeId],
      });
    },
  });

  if (loading) return <Loading />;
  if (isError) return <EmptyHint text="Erro a carregar a skill-matrix." />;
  if (!skills || skills.phases.length === 0) {
    return <EmptyHint text="Sem matriz de skills para este operador." />;
  }

  return (
    <div>
      <SectionLabel>
        Skills por fase · clica na caixa para alternar a aptidão · ajusta o
        nível (escala 1.0–3.0, 3.0 = melhor)
      </SectionLabel>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {skills.phases.map((p) => {
          // O nível curado vem na escala ERP (1-5, 1=melhor); na UI
          // mostramos a escala invertida. O backend faz a conversão e
          // clamp — aqui só precisamos do valor a propor.
          const currentLevel =
            p.nivel !== null && p.nivel >= 1 && p.nivel <= 3
              ? p.nivel
              : null;
          return (
            <div
              key={p.phase_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 11px',
                background: p.can_do ? 'var(--accent-bg)' : 'var(--bg-2)',
                border: `1px solid ${p.can_do ? 'var(--accent-bd)' : 'var(--bd-1)'}`,
                borderRadius: 6,
                fontSize: 12,
                color: 'var(--fg-1)',
              }}
            >
              <button
                type="button"
                onClick={() =>
                  toggleMutation.mutate({
                    phase_id: p.phase_id,
                    can_do: !p.can_do,
                  })
                }
                disabled={toggleMutation.isPending}
                aria-label={`Alternar aptidão de ${p.phase_name ?? p.phase_id}`}
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: 4,
                  border: `1px solid ${p.can_do ? 'var(--accent)' : 'var(--bd-2)'}`,
                  background: p.can_do ? 'var(--accent)' : 'transparent',
                  flexShrink: 0,
                  cursor: 'pointer',
                  padding: 0,
                }}
              />
              <span style={{ flex: 1 }}>{p.phase_name ?? p.phase_id}</span>
              {p.ops_count > 0 ? (
                <span
                  className="tabular"
                  style={{ fontSize: 10, color: 'var(--fg-3)' }}
                >
                  {p.ops_count} ops
                </span>
              ) : null}
              {/* Selector de nível — só faz sentido quando o operador é apto */}
              {p.can_do ? (
                <select
                  value={currentLevel ?? ''}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (!v) return;
                    toggleMutation.mutate({
                      phase_id: p.phase_id,
                      can_do: true,
                      nivel: Number(v),
                    });
                  }}
                  disabled={toggleMutation.isPending}
                  aria-label={`Nível em ${p.phase_name ?? p.phase_id}`}
                  className="text-slate-900"
                  style={{
                    fontSize: 11,
                    padding: '2px 4px',
                    background: '#fff',
                    border: '1px solid var(--bd-2)',
                    borderRadius: 4,
                    outline: 'none',
                  }}
                >
                  <option value="">nível…</option>
                  {LEVEL_STEPS.map((s) => (
                    <option key={s} value={s}>
                      {s.toFixed(1)}
                    </option>
                  ))}
                </select>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Sub-tab: Histórico ─────────────────────────────────────────────────────

function HistoricoTab({
  data,
  loading,
  isError,
}: {
  data: OperationHistoryResult | undefined;
  loading: boolean;
  isError: boolean;
}) {
  if (loading) return <Loading />;
  if (isError) return <EmptyHint text="Erro a carregar o histórico." />;
  if (!data || data.operations.length === 0) {
    return <EmptyHint text="Sem operações registadas para este operador." />;
  }
  return (
    <div>
      <SectionLabel>Operações recentes ({data.returned})</SectionLabel>
      <div className="flex flex-col gap-2">
        {data.operations.map((op) => (
          <div
            key={op.schedule_id}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '9px 12px',
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-sm)',
            }}
          >
            <div>
              <div style={{ fontSize: 12, color: 'var(--fg-0)', fontWeight: 500 }}>
                Ordem {op.order_id} · seq {op.operation_sequence}
              </div>
              <div className="tabular" style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>
                {op.scheduled_start_date?.slice(0, 10)} →{' '}
                {op.scheduled_end_date?.slice(0, 10)}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: 11, color: 'var(--fg-2)' }}>{op.status}</span>
              {op.actual_duration_hours !== null ? (
                <div className="tabular" style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>
                  {op.actual_duration_hours.toFixed(1)} h
                </div>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Sub-tab: Nível ─────────────────────────────────────────────────────────

function NivelTab({
  data,
  loading,
  isError,
}: {
  data: LevelSummary | undefined;
  loading: boolean;
  isError: boolean;
}) {
  if (loading) return <Loading />;
  if (isError) return <EmptyHint text="Erro a carregar o nível derivado." />;
  if (!data) return <EmptyHint text="Sem nível derivado para este operador." />;

  const tone = levelTone(data.derived_level);
  const metrics = data.qualification_metrics;

  return (
    <div className="space-y-3">
      <Card>
        <SectionLabel>Nível global · escala 1.0–3.0 (3.0 = melhor)</SectionLabel>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span
            className="display tabular"
            style={{ fontSize: 30, fontWeight: 600, color: `var(--${tone})` }}
          >
            {data.derived_level.toFixed(1)}
          </span>
          <span style={{ fontSize: 13, color: 'var(--fg-1)', fontWeight: 500 }}>
            {data.level_label}
          </span>
        </div>
        <div style={{ marginTop: 10 }}>
          <LevelGauge level={data.derived_level} />
        </div>
        <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 8, lineHeight: 1.5 }}>
          {data.level_description}
        </div>
      </Card>

      {/* Nível por grupo de área — o coração da escala nova */}
      <Card>
        <SectionLabel>
          Nível por grupo de área ({data.per_area_levels.length})
        </SectionLabel>
        {data.per_area_levels.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
            Sem fases aptas — nenhum grupo de área avaliado ainda.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {data.per_area_levels.map((area) => (
              <div key={area.area_group}>
                <LevelGauge level={area.level} label={area.area_group} />
                <div
                  style={{
                    fontSize: 9.5,
                    color: 'var(--fg-4)',
                    marginLeft: 106,
                    marginTop: 1,
                  }}
                >
                  {area.phases_apt} fase{area.phases_apt === 1 ? '' : 's'} apta
                  {area.phases_apt === 1 ? '' : 's'}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Sinais de qualificação (Q.53.E) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        <Card>
          <SectionLabel>Recência</SectionLabel>
          <span
            className="tabular"
            style={{ fontSize: 17, fontWeight: 600, color: 'var(--fg-0)' }}
          >
            {metrics.recency_days !== null ? `${metrics.recency_days}d` : '—'}
          </span>
        </Card>
        <Card>
          <SectionLabel>Versatilidade</SectionLabel>
          <span
            className="tabular"
            style={{ fontSize: 17, fontWeight: 600, color: 'var(--fg-0)' }}
          >
            {metrics.versatility} fases
          </span>
        </Card>
        <Card>
          <SectionLabel>Produtividade</SectionLabel>
          <span
            className="tabular"
            style={{ fontSize: 17, fontWeight: 600, color: 'var(--fg-0)' }}
          >
            {metrics.productivity !== null
              ? `${metrics.productivity.toFixed(1)}/d`
              : '—'}
          </span>
        </Card>
      </div>

      {data.recommended_boats.length > 0 ? (
        <Card>
          <SectionLabel>Barcos recomendados</SectionLabel>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {data.recommended_boats.map((b) => (
              <span
                key={b}
                style={{
                  fontSize: 11,
                  padding: '3px 9px',
                  background: 'var(--bg-3)',
                  border: '1px solid var(--bd-1)',
                  borderRadius: 999,
                  color: 'var(--fg-1)',
                }}
              >
                {b}
              </span>
            ))}
          </div>
        </Card>
      ) : null}
    </div>
  );
}

// ─── Bits visuais ───────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10.5,
        color: 'var(--fg-3)',
        textTransform: 'uppercase',
        letterSpacing: 0.4,
        fontWeight: 600,
        marginBottom: 10,
      }}
    >
      {children}
    </div>
  );
}

function Card({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        padding: 14,
      }}
    >
      {children}
    </div>
  );
}

function Loading() {
  return (
    <div style={{ padding: 24, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
      A carregar…
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div
      style={{
        padding: 20,
        textAlign: 'center',
        color: 'var(--fg-3)',
        fontSize: 12,
        background: 'var(--bg-2)',
        borderRadius: 8,
      }}
    >
      {text}
    </div>
  );
}
