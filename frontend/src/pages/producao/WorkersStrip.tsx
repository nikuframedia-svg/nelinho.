/**
 * WorkersStrip — rail horizontal de operadores com fit-scoring (Q.52.F).
 *
 * Port fiel do `WorkersStrip` do design NELO: lista horizontal de
 * operadores, ordenada por adequação ao barco seleccionado. Cada cartão
 * mostra avatar, fit, razões e impacto €; o melhor leva badge "MELHOR".
 * Cada cartão é arrastável (payload `worker`) para os cartões de barco.
 *
 * O fit-scoring vem de `scoreFor` ligado a quality-score + skill-matrix
 * REAIS. ZERO MOCKS — sem barco seleccionado, ordena pelo score global.
 */

import { useMemo } from 'react';
import type { DragEvent, ReactNode } from 'react';
import { Users } from 'lucide-react';
import { DarkBadge, NeloWorkerAvatar } from '../../components/dark';
import { fmtEuro } from '../painel/painelHelpers';
import { fitTone, scoreFor } from './fabricaScoring';
import type { WorkerProfile } from './fabricaScoring';
import type { ActiveOrderCard } from './fabricaApi';

const MIME = 'application/x-nelo-dnd';

export interface WorkersStripProps {
  workers: WorkerProfile[];
  /** Barco seleccionado — religa a ordenação por adequação. */
  activeBoat: ActiveOrderCard | null;
  /** Ids já atribuídos ao barco activo (escondidos do rail). */
  assignedToActive: string[];
  /** True enquanto os perfis de qualidade/skills carregam. */
  loadingProfiles?: boolean;
}

function deriveInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '—';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function WorkersStrip({
  workers,
  activeBoat,
  assignedToActive,
  loadingProfiles = false,
}: WorkersStripProps): ReactNode {
  // Limite do rail — com 122 operadores, renderizar todos os cartões
  // pesa o DOM sem ganho: mostramos os mais relevantes (já ordenados
  // por adequação/score) e o resto fica acessível por scroll/selecção.
  const RAIL_CAP = 40;

  const scoredAll = useMemo(() => {
    return workers
      .filter((w) => !assignedToActive.includes(w.id))
      .map((w) => {
        const fitResult = scoreFor(w, activeBoat?.phase ?? null);
        const globalScore = w.quality
          ? Math.max(0, Math.min(10, w.quality.score * 10))
          : 5;
        return { worker: w, ...fitResult, globalScore };
      })
      .sort((a, b) =>
        activeBoat ? b.fit - a.fit : b.globalScore - a.globalScore,
      );
  }, [workers, activeBoat, assignedToActive]);

  const scored = useMemo(
    () => scoredAll.slice(0, RAIL_CAP),
    [scoredAll],
  );
  const hiddenCount = scoredAll.length - scored.length;

  const recommendedCount = activeBoat
    ? scoredAll.filter((s) => s.fit > 7).length
    : 0;

  function onDragStartWorker(
    e: DragEvent<HTMLDivElement>,
    workerId: string,
  ): void {
    e.dataTransfer.setData(
      MIME,
      JSON.stringify({ kind: 'worker', data: { id: workerId } }),
    );
    e.dataTransfer.effectAllowed = 'copy';
  }

  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--bd-1)',
          background: 'var(--bg-2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Users size={14} color="var(--fg-2)" />
          <span
            style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--fg-0)' }}
          >
            Operadores disponíveis
          </span>
          <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
            · {scoredAll.length}
          </span>
          {activeBoat && recommendedCount > 0 && (
            <DarkBadge variant="info" size="sm">
              {recommendedCount} recomendado(s)
            </DarkBadge>
          )}
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-2)' }}>
          {activeBoat ? (
            <>
              Ordenados por adequação a{' '}
              <span style={{ color: 'var(--fg-0)', fontWeight: 500 }}>
                #{activeBoat.hull ?? activeBoat.id.slice(0, 6)}
              </span>{' '}
              ·{' '}
              <span style={{ color: 'var(--accent)' }}>
                {activeBoat.phase ?? 'sem fase'}
              </span>{' '}
              · arrasta para o cartão
            </>
          ) : (
            <>Clica num barco para ordenar por adequação à sua fase</>
          )}
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          gap: 8,
          padding: 10,
          overflowX: 'auto',
          minHeight: 130,
        }}
      >
        {loadingProfiles && scored.length === 0 ? (
          <div
            style={{
              display: 'grid',
              placeItems: 'center',
              width: '100%',
              fontSize: 12,
              color: 'var(--fg-3)',
            }}
          >
            A carregar operadores…
          </div>
        ) : scored.length === 0 ? (
          <div
            style={{
              display: 'grid',
              placeItems: 'center',
              width: '100%',
              fontSize: 12,
              color: 'var(--fg-3)',
            }}
          >
            Sem operadores disponíveis. Confirma se a tabela de empregados
            foi sincronizada.
          </div>
        ) : (
          scored.map((entry, idx) => {
            const { worker: w, fit, reasons, impact, globalScore } = entry;
            const isTopPick = activeBoat !== null && idx === 0 && fit > 7;
            return (
              <div
                key={w.id}
                draggable
                onDragStart={(e) => onDragStartWorker(e, w.id)}
                style={{
                  minWidth: 200,
                  maxWidth: 220,
                  flexShrink: 0,
                  padding: '10px 12px',
                  background: isTopPick
                    ? 'rgba(45,161,75,0.06)'
                    : 'var(--bg-1)',
                  border: `1px solid ${
                    isTopPick ? 'var(--green-bd)' : 'var(--bd-1)'
                  }`,
                  borderRadius: 'var(--r-md)',
                  cursor: 'grab',
                  position: 'relative',
                }}
              >
                {isTopPick && (
                  <div
                    style={{
                      position: 'absolute',
                      top: -6,
                      right: 8,
                      padding: '1px 6px',
                      background: 'var(--green)',
                      color: '#000',
                      fontSize: 9,
                      fontWeight: 700,
                      borderRadius: 999,
                      letterSpacing: 0.4,
                    }}
                  >
                    MELHOR
                  </div>
                )}
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: 8 }}
                >
                  <div style={{ position: 'relative' }}>
                    <NeloWorkerAvatar
                      worker={{
                        name: w.name,
                        initials: deriveInitials(w.name),
                      }}
                      size={28}
                    />
                    <span
                      className="tabular"
                      style={{
                        position: 'absolute',
                        bottom: -2,
                        right: -2,
                        fontSize: 8.5,
                        fontWeight: 700,
                        background: 'var(--bg-1)',
                        color: 'var(--fg-3)',
                        border: '1px solid var(--bd-2)',
                        borderRadius: 999,
                        padding: '0 4px',
                        minWidth: 14,
                        textAlign: 'center',
                      }}
                    >
                      {idx + 1}
                    </span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'baseline',
                        gap: 4,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 12,
                          color: 'var(--fg-0)',
                          fontWeight: 500,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                        title={w.name}
                      >
                        {w.name}
                      </span>
                      {activeBoat ? (
                        <span
                          className="tabular"
                          style={{
                            fontSize: 11.5,
                            color: `var(--${fitTone(fit)})`,
                            fontWeight: 600,
                          }}
                        >
                          {fit.toFixed(1)}
                        </span>
                      ) : (
                        <span
                          className="tabular"
                          style={{ fontSize: 11.5, color: 'var(--fg-2)' }}
                        >
                          ★{globalScore.toFixed(1)}
                        </span>
                      )}
                    </div>
                    <div
                      style={{
                        fontSize: 10,
                        color: 'var(--fg-3)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {w.quality
                        ? `${w.quality.operations} ops · ${(
                            w.quality.defect_rate * 100
                          ).toFixed(1)}% erro`
                        : 'sem histórico'}
                    </div>
                  </div>
                </div>

                {activeBoat && reasons.length > 0 && (
                  <div
                    style={{
                      marginTop: 6,
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 3,
                    }}
                  >
                    {reasons.slice(0, 2).map((r, i) => (
                      <DarkBadge key={i} variant={r.tone} size="sm">
                        {r.text}
                      </DarkBadge>
                    ))}
                  </div>
                )}

                {activeBoat && impact !== 0 && (
                  <div
                    style={{
                      marginTop: 6,
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      paddingTop: 6,
                      borderTop: '1px solid var(--bd-1)',
                    }}
                  >
                    <span
                      style={{
                        fontSize: 9.5,
                        color: 'var(--fg-3)',
                        textTransform: 'uppercase',
                        letterSpacing: 0.4,
                      }}
                    >
                      se atribuído
                    </span>
                    <span
                      className="tabular"
                      style={{
                        fontSize: 12,
                        color: impact > 0 ? 'var(--green)' : 'var(--red)',
                        fontWeight: 600,
                      }}
                    >
                      {impact > 0 ? '+' : ''}
                      {fmtEuro(impact)}
                    </span>
                  </div>
                )}
              </div>
            );
          })
        )}
        {hiddenCount > 0 && (
          <div
            style={{
              display: 'grid',
              placeItems: 'center',
              minWidth: 150,
              flexShrink: 0,
              fontSize: 10.5,
              color: 'var(--fg-3)',
              textAlign: 'center',
              padding: '0 12px',
            }}
          >
            +{hiddenCount} operador(es).
            {activeBoat
              ? ' Os mais adequados aparecem primeiro.'
              : ' Clica num barco para ordenar por adequação.'}
          </div>
        )}
      </div>
    </div>
  );
}
