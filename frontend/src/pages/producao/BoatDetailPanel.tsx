/**
 * BoatDetailPanel — detalhe inline do barco + operadores recomendados
 * para a tarefa (Q.54.N).
 *
 * Substitui o `BoatDetailSheet` modal no caminho de clique da Fábrica.
 * O modal abria via o componente `Sheet`, que aplica um `backdrop-filter`
 * de ecrã inteiro — esse snapshot desfocado da página toda no primeiro
 * frame era o micro-congelamento ao clicar num barco. Inline não há
 * blur de ecrã inteiro → sem congelamento.
 *
 * Além do detalhe (estado/fase/expedição/plano CPO), responde "quem ponho
 * nesta tarefa?": lista os operadores DISPONÍVEIS (não atribuídos) para a
 * FASE do barco, ranqueados por adequação, com o NÍVEL rotulado, a
 * recomendação (o melhor leva badge RECOMENDADO) e o PORQUÊ — as razões
 * legíveis do fit-scoring.
 *
 * Os perfis (`WorkerProfile[]`) chegam já carregados pela página (a
 * chamada batch que a `FabricaPage` faz) — este painel é presentacional,
 * não busca dados. ZERO MOCKS — sem perfis, o scoring degrada com razão
 * explícita; nunca inventa.
 */

import { useMemo } from 'react';
import type { ReactNode } from 'react';
import { X, Sparkles, Users } from 'lucide-react';
import { DarkBadge, NeloWorkerAvatar } from '../../components/dark';
import { fmtEuro } from '../painel/painelHelpers';
import { fitTone, scoreFor } from './fabricaScoring';
import type { WorkerProfile } from './fabricaScoring';
import type { ActiveOrderCard, OptimizedOrderCard } from './fabricaApi';

type BadgeTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

interface LevelLabel {
  text: string;
  tone: BadgeTone;
}

/** Quantos operadores mostrar antes do "+N". */
const VISIBLE_CAP = 12;

function deriveInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '—';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/**
 * Nível do operador NESTA fase, lido da skill-matrix — mesma
 * correspondência difusa de fase que `scoreFor` usa (mantém os dois
 * coerentes).
 */
function levelLabelFor(
  worker: WorkerProfile,
  phaseName: string | null,
): LevelLabel {
  if (!worker.skills) return { text: 'Sem matriz de skills', tone: 'neutral' };
  if (!phaseName) return { text: 'Fase indefinida', tone: 'neutral' };
  const phaseLc = phaseName.toLowerCase();
  const row = worker.skills.phases.find((p) => {
    const name = (p.phase_name ?? p.phase_id).toLowerCase();
    return name.includes(phaseLc) || phaseLc.includes(name);
  });
  if (!row || !row.can_do) {
    return { text: 'Sem skill nesta fase', tone: 'danger' };
  }
  const nivel = row.nivel ?? 1;
  if (nivel >= 3 || row.ops_count >= 50) {
    return { text: `Especialista · ${row.ops_count} ops`, tone: 'success' };
  }
  if (nivel === 2) {
    return { text: `Nível 2 · ${row.ops_count} ops`, tone: 'info' };
  }
  return { text: `Nível 1 · ${row.ops_count} ops`, tone: 'warning' };
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}): ReactNode {
  return (
    <div>
      <div
        style={{
          fontSize: 10,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 13, color: 'var(--fg-0)', marginTop: 3 }}>
        {children}
      </div>
    </div>
  );
}

export interface BoatDetailPanelProps {
  boat: ActiveOrderCard;
  /** Perfis de operador já carregados pela página (fit-scoring). */
  workers: WorkerProfile[];
  /** Ids de operadores já atribuídos a este barco. */
  assignedIds: string[];
  /** Fase a usar para pontuar a adequação (actual ou optimizada). */
  phaseName: string | null;
  /** True enquanto os perfis de qualidade/skill ainda carregam. */
  loadingProfiles?: boolean;
  /**
   * Atribuir um operador ao barco — chamado ao clicar numa linha da
   * lista. Quando ausente (ex: vista "plano", só leitura), as linhas
   * não são clicáveis.
   */
  onAssign?: (workerId: string) => void;
  onClose: () => void;
}

export function BoatDetailPanel({
  boat,
  workers,
  assignedIds,
  phaseName,
  loadingProfiles = false,
  onAssign,
  onClose,
}: BoatDetailPanelProps): ReactNode {
  const opt = boat as OptimizedOrderCard;
  const optimizedPhase = opt.optimized_phase ?? null;
  const optimizedWorker = opt.assigned_employee_name ?? null;
  const hull = boat.hull ?? boat.id.slice(0, 6);

  const assigned = useMemo(() => new Set(assignedIds), [assignedIds]);

  // Operadores DISPONÍVEIS (não atribuídos a este barco), ranqueados por
  // adequação à fase. `scoreFor` penaliza quem não tem skill na fase, por
  // isso os aptos sobem naturalmente.
  const ranked = useMemo(() => {
    return workers
      .filter((w) => !assigned.has(w.id))
      .map((w) => {
        const score = scoreFor(w, phaseName);
        const level = levelLabelFor(w, phaseName);
        return { worker: w, ...score, level };
      })
      .sort((a, b) => b.fit - a.fit);
  }, [workers, assigned, phaseName]);

  const visible = ranked.slice(0, VISIBLE_CAP);
  const hiddenCount = ranked.length - visible.length;
  const best = ranked[0] ?? null;

  // Operadores já neste barco — listados à parte (não são "disponíveis").
  const assignedNames = useMemo(
    () =>
      workers.filter((w) => assigned.has(w.id)).map((w) => w.name),
    [workers, assigned],
  );

  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--accent-bd)',
        borderRadius: 'var(--r-lg)',
        padding: 16,
      }}
    >
      {/* ── Cabeçalho ──────────────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 14,
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-0)' }}>
            {boat.product_name ?? `Barco #${hull}`}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--fg-3)', marginTop: 2 }}>
            Barco #{hull} · {boat.product_type ?? 'modelo —'}
            {boat.customer_name ? ` · ${boat.customer_name}` : ''}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar detalhe"
          style={{
            width: 26,
            height: 26,
            borderRadius: '50%',
            background: 'var(--bg-3)',
            border: '1px solid var(--bd-2)',
            color: 'var(--fg-1)',
            display: 'grid',
            placeItems: 'center',
            cursor: 'pointer',
            flexShrink: 0,
          }}
        >
          <X size={13} />
        </button>
      </div>

      {/* ── Detalhe do barco ───────────────────────────────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 12,
        }}
      >
        <Field label="Estado">
          <span style={{ fontWeight: 600 }}>{boat.status}</span>
        </Field>
        <Field label="Fase actual">
          <span style={{ fontWeight: 600 }}>{boat.phase ?? 'sem fase'}</span>
        </Field>
        <Field label="Expedição prevista">
          {boat.transport_date
            ? new Date(boat.transport_date).toLocaleDateString('pt-PT')
            : '—'}
        </Field>
      </div>

      {(optimizedPhase || optimizedWorker) && (
        <div
          style={{
            marginTop: 12,
            padding: '8px 12px',
            background: 'var(--accent-bg)',
            border: '1px dashed var(--accent-bd)',
            borderRadius: 'var(--r-md)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 11.5,
            color: 'var(--fg-2)',
          }}
        >
          <Sparkles size={13} color="var(--accent)" style={{ flexShrink: 0 }} />
          <span>
            Plano CPO:
            {optimizedPhase && (
              <>
                {' '}fase{' '}
                <span style={{ color: 'var(--fg-0)', fontWeight: 600 }}>
                  {optimizedPhase}
                </span>
              </>
            )}
            {optimizedWorker && (
              <>
                {optimizedPhase ? ' ·' : ''} operador{' '}
                <span style={{ color: 'var(--accent)', fontWeight: 600 }}>
                  {optimizedWorker}
                </span>
              </>
            )}
          </span>
        </div>
      )}

      {/* ── Operadores recomendados para a tarefa ──────────────────────── */}
      <div
        style={{
          marginTop: 16,
          paddingTop: 14,
          borderTop: '1px solid var(--bd-1)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            marginBottom: 4,
          }}
        >
          <Users size={14} color="var(--fg-2)" />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
            Operadores para esta tarefa
          </span>
        </div>
        <div style={{ fontSize: 11.5, color: 'var(--fg-3)', marginBottom: 12 }}>
          Fase{' '}
          <span style={{ color: 'var(--accent)', fontWeight: 500 }}>
            {phaseName ?? 'sem fase'}
          </span>{' '}
          · disponíveis, ordenados por adequação
          {onAssign ? ' · clica num operador para o atribuir' : ''}
        </div>

        {assignedNames.length > 0 && (
          <div style={{ fontSize: 11, color: 'var(--fg-2)', marginBottom: 10 }}>
            Já neste barco: {assignedNames.join(', ')}.
          </div>
        )}

        {loadingProfiles && ranked.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
            A carregar perfis de operador…
          </div>
        ) : ranked.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
            Sem operadores disponíveis. Confirma se a tabela de empregados foi
            sincronizada do ERP.
          </div>
        ) : (
          <>
            {/* Recomendação + porquê */}
            {best && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                  padding: '10px 12px',
                  marginBottom: 12,
                  background: 'var(--accent-bg)',
                  border: '1px dashed var(--accent-bd)',
                  borderRadius: 'var(--r-md)',
                }}
              >
                <Sparkles
                  size={14}
                  color="var(--accent)"
                  style={{ flexShrink: 0, marginTop: 1 }}
                />
                <div>
                  <div style={{ fontSize: 12.5, color: 'var(--fg-0)' }}>
                    Recomendo{' '}
                    <span style={{ fontWeight: 600 }}>{best.worker.name}</span>{' '}
                    para esta fase
                    <span
                      className="tabular"
                      style={{
                        marginLeft: 6,
                        color: `var(--${fitTone(best.fit)})`,
                        fontWeight: 600,
                      }}
                    >
                      adequação {best.fit.toFixed(1)}/10
                    </span>
                  </div>
                  <div
                    style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 2 }}
                  >
                    {best.reasons.length > 0
                      ? `Porquê: ${best.reasons
                          .map((r) => r.text)
                          .join(' · ')}.`
                      : 'Melhor adequação disponível com os dados actuais.'}
                  </div>
                </div>
              </div>
            )}

            {loadingProfiles && (
              <div
                style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 10 }}
              >
                A afinar a pontuação com os perfis de skill e qualidade…
              </div>
            )}

            {/* Lista ranqueada */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {visible.map((entry, idx) => {
                const isTop = idx === 0;
                return (
                  <div
                    key={entry.worker.id}
                    role={onAssign ? 'button' : undefined}
                    tabIndex={onAssign ? 0 : undefined}
                    onClick={
                      onAssign
                        ? () => onAssign(entry.worker.id)
                        : undefined
                    }
                    onKeyDown={
                      onAssign
                        ? (e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              onAssign(entry.worker.id);
                            }
                          }
                        : undefined
                    }
                    title={
                      onAssign
                        ? `Clica para atribuir ${entry.worker.name} a este barco`
                        : undefined
                    }
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '8px 10px',
                      background: isTop
                        ? 'rgba(45,161,75,0.06)'
                        : 'var(--bg-2)',
                      border: `1px solid ${
                        isTop ? 'var(--green-bd)' : 'var(--bd-1)'
                      }`,
                      borderRadius: 'var(--r-md)',
                      cursor: onAssign ? 'pointer' : 'default',
                    }}
                  >
                    <span
                      className="tabular"
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: 'var(--fg-3)',
                        width: 18,
                        textAlign: 'center',
                        flexShrink: 0,
                      }}
                    >
                      {idx + 1}
                    </span>
                    <NeloWorkerAvatar
                      worker={{
                        name: entry.worker.name,
                        initials: deriveInitials(entry.worker.name),
                      }}
                      size={28}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          flexWrap: 'wrap',
                        }}
                      >
                        <span
                          style={{
                            fontSize: 12,
                            fontWeight: 500,
                            color: 'var(--fg-0)',
                          }}
                          title={entry.worker.name}
                        >
                          {entry.worker.name}
                        </span>
                        {isTop && (
                          <DarkBadge variant="success" size="sm">
                            RECOMENDADO
                          </DarkBadge>
                        )}
                        <DarkBadge variant={entry.level.tone} size="sm">
                          {entry.level.text}
                        </DarkBadge>
                      </div>
                      {entry.reasons.length > 0 && (
                        <div
                          style={{
                            marginTop: 4,
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: 3,
                          }}
                        >
                          {entry.reasons.map((r, i) => (
                            <DarkBadge key={i} variant={r.tone} size="sm">
                              {r.text}
                            </DarkBadge>
                          ))}
                        </div>
                      )}
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div
                        className="tabular"
                        style={{
                          fontSize: 14,
                          fontWeight: 600,
                          color: `var(--${fitTone(entry.fit)})`,
                        }}
                      >
                        {entry.fit.toFixed(1)}
                      </div>
                      {entry.impact !== 0 && (
                        <div
                          className="tabular"
                          style={{
                            fontSize: 10,
                            color:
                              entry.impact > 0
                                ? 'var(--green)'
                                : 'var(--red)',
                          }}
                        >
                          {entry.impact > 0 ? '+' : ''}
                          {fmtEuro(entry.impact)}
                        </div>
                      )}
                    </div>
                    {onAssign && (
                      <span
                        style={{
                          flexShrink: 0,
                          fontSize: 10,
                          fontWeight: 600,
                          color: '#fff',
                          background: 'var(--accent)',
                          borderRadius: 999,
                          padding: '3px 9px',
                        }}
                      >
                        Atribuir
                      </span>
                    )}
                  </div>
                );
              })}
            </div>

            {hiddenCount > 0 && (
              <div
                style={{
                  marginTop: 8,
                  fontSize: 10.5,
                  color: 'var(--fg-3)',
                  textAlign: 'center',
                }}
              >
                +{hiddenCount} operador(es) com adequação mais baixa a esta
                fase. Arrasta-os do rail em baixo se precisares.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
