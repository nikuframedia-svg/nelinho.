/**
 * TimelineLanes — grelha de raias temporais (timeline grid).
 *
 * Primitiva partilhada do design NELO: usada pela Fábrica (14 dias ×
 * 56px) e pelo Planeamento (07–18h, 44 slots de 15min). Desenha um
 * cabeçalho de colunas (slots) + uma raia por linha; cada item é
 * posicionado por `startSlot`/`spanSlots` e renderizado pelo caller.
 *
 * Genérica: ZERO conhecimento do domínio, ZERO dados hardcoded. O
 * caller passa `lanes`, `slots` e os `items` (cada um com a sua raia,
 * coluna de início e duração em colunas).
 *
 * Q.173.AE — virtualização de lanes (@tanstack/react-virtual) +
 * sticky header de datas + sticky coluna de etiquetas.
 *
 * Sprint Q.52.B.
 */

import { useRef, type ReactNode, type CSSProperties } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';

export interface TimelineSlot {
  /** Identificador único da coluna. */
  id: string;
  /** Etiqueta no cabeçalho (ex: "07:00", "Seg 12"). */
  label: string;
  /** Marca a coluna como destacada (ex: hoje, fim-de-semana). */
  highlight?: boolean;
}

export interface TimelineLane {
  /** Identificador único da raia. */
  id: string;
  /** Etiqueta na coluna fixa à esquerda. */
  label: string;
  /** Sub-etiqueta opcional. */
  sublabel?: string;
  /** Nó React opcional para substituir `label` (ex: Clickable). */
  labelNode?: ReactNode;
}

export interface TimelineItem {
  /** Identificador único do item. */
  id: string;
  /** Raia onde o item vive (`TimelineLane.id`). */
  laneId: string;
  /** Índice da coluna de início (0-based). */
  startSlot: number;
  /** Número de colunas que o item ocupa (≥ 1). */
  spanSlots: number;
}

export interface TimelineLanesProps {
  slots: TimelineSlot[];
  lanes: TimelineLane[];
  items: TimelineItem[];
  /** Largura de cada coluna em px. */
  slotWidth?: number;
  /** Altura de cada raia em px. */
  laneHeight?: number;
  /** Largura da coluna fixa de etiquetas das raias em px. */
  labelWidth?: number;
  /** Render-prop para o conteúdo de cada item posicionado. */
  renderItem: (item: TimelineItem) => ReactNode;
}

// Altura do cabeçalho de datas em px (para o sticky offset correto).
const HEADER_HEIGHT = 28;

export function TimelineLanes({
  slots,
  lanes,
  items,
  slotWidth = 56,
  laneHeight = 44,
  labelWidth = 140,
  renderItem,
}: TimelineLanesProps): ReactNode {
  const gridWidth = slots.length * slotWidth;
  const totalWidth = labelWidth + gridWidth;

  // ── Q.173.AE: virtualização das lanes ────────────────────────────────────
  // Contentor de scroll: o div exterior abaixo. O virtualizer só precisa de
  // saber quantas lanes existem e a altura fixa de cada uma.
  const scrollRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: lanes.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => laneHeight,
    overscan: 5,
  });

  const totalLanesHeight = rowVirtualizer.getTotalSize();

  // Mapa laneId → items para O(1) por raia virtualizada
  const itemsByLane = new Map<string, TimelineItem[]>();
  for (const item of items) {
    if (!itemsByLane.has(item.laneId)) itemsByLane.set(item.laneId, []);
    itemsByLane.get(item.laneId)!.push(item);
  }

  // ── Estilos CSS partilhados ───────────────────────────────────────────────

  const stickyLabelStyle: CSSProperties = {
    position: 'sticky',
    left: 0,
    zIndex: 2,
    width: labelWidth,
    flexShrink: 0,
    borderRight: '1px solid var(--bd-1)',
    background: 'var(--bg-2)',
  };

  return (
    <div
      ref={scrollRef}
      style={{
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        background: 'var(--bg-1)',
        overflow: 'auto',
        // Altura máxima para que o scroll seja interno (evita super-scroll de 124k px)
        maxHeight: '100%',
        position: 'relative',
      }}
    >
      {/* ── Cabeçalho sticky de datas ────────────────────────────────────── */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          display: 'flex',
          minWidth: totalWidth,
          background: 'var(--bg-2)',
          borderBottom: '1px solid var(--bd-1)',
        }}
      >
        {/* Canto vazio (interseção header × label col) */}
        <div
          style={{
            ...stickyLabelStyle,
            height: HEADER_HEIGHT,
            borderRight: '1px solid var(--bd-1)',
          }}
        />
        {/* Colunas de datas */}
        {slots.map((s) => (
          <div
            key={s.id}
            style={{
              width: slotWidth,
              flexShrink: 0,
              height: HEADER_HEIGHT,
              padding: '4px 4px',
              textAlign: 'center',
              fontSize: 10,
              color: s.highlight ? 'var(--fg-1)' : 'var(--fg-3)',
              borderRight: '1px solid var(--bd-1)',
              background: s.highlight ? 'var(--bg-3)' : 'var(--bg-2)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {s.label}
          </div>
        ))}
      </div>

      {/* ── Área virtualizada das lanes ───────────────────────────────────── */}
      <div
        style={{
          position: 'relative',
          height: totalLanesHeight,
          minWidth: totalWidth,
        }}
      >
        {rowVirtualizer.getVirtualItems().map((vRow) => {
          const lane = lanes[vRow.index];
          if (!lane) return null;
          const laneItems = itemsByLane.get(lane.id) ?? [];

          return (
            <div
              key={lane.id}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                transform: `translateY(${vRow.start}px)`,
                width: '100%',
                height: laneHeight,
                display: 'flex',
              }}
            >
              {/* Etiqueta sticky à esquerda */}
              <div
                style={{
                  ...stickyLabelStyle,
                  height: laneHeight,
                  padding: '0 10px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  borderBottom: '1px solid var(--bd-1)',
                }}
              >
                <span
                  style={{
                    fontSize: 11.5,
                    color: 'var(--fg-1)',
                    fontWeight: 500,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {lane.labelNode ?? lane.label}
                </span>
                {lane.sublabel ? (
                  <span style={{ fontSize: 9.5, color: 'var(--fg-3)' }}>
                    {lane.sublabel}
                  </span>
                ) : null}
              </div>

              {/* Pista com grelha + items posicionados */}
              <div
                style={{
                  position: 'relative',
                  height: laneHeight,
                  width: gridWidth,
                  flexShrink: 0,
                  borderBottom: '1px solid var(--bd-1)',
                  backgroundImage: `linear-gradient(90deg, var(--bd-1) 1px, transparent 1px)`,
                  backgroundSize: `${slotWidth}px 100%`,
                }}
              >
                {laneItems.map((it) => (
                  <div
                    key={it.id}
                    style={{
                      position: 'absolute',
                      top: 4,
                      bottom: 4,
                      left: it.startSlot * slotWidth + 2,
                      width: it.spanSlots * slotWidth - 4,
                    }}
                  >
                    {renderItem(it)}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
