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
 * Vive em `components/dark/` para a Onda 1 não partilhar ficheiros.
 *
 * Sprint Q.52.B.
 */

import type { ReactNode } from 'react';

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

  return (
    <div
      style={{
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        background: 'var(--bg-1)',
        overflow: 'auto',
      }}
    >
      {/* Cabeçalho de colunas */}
      <div style={{ display: 'flex', minWidth: labelWidth + gridWidth }}>
        <div
          style={{
            width: labelWidth,
            flexShrink: 0,
            borderRight: '1px solid var(--bd-1)',
            borderBottom: '1px solid var(--bd-1)',
            background: 'var(--bg-2)',
          }}
        />
        <div style={{ display: 'flex' }}>
          {slots.map((s) => (
            <div
              key={s.id}
              style={{
                width: slotWidth,
                flexShrink: 0,
                padding: '6px 4px',
                textAlign: 'center',
                fontSize: 10,
                color: s.highlight ? 'var(--fg-1)' : 'var(--fg-3)',
                borderRight: '1px solid var(--bd-1)',
                borderBottom: '1px solid var(--bd-1)',
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
      </div>

      {/* Raias */}
      {lanes.map((lane) => {
        const laneItems = items.filter((it) => it.laneId === lane.id);
        return (
          <div
            key={lane.id}
            style={{ display: 'flex', minWidth: labelWidth + gridWidth }}
          >
            {/* Etiqueta fixa */}
            <div
              style={{
                width: labelWidth,
                flexShrink: 0,
                height: laneHeight,
                padding: '0 10px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                borderRight: '1px solid var(--bd-1)',
                borderBottom: '1px solid var(--bd-1)',
                background: 'var(--bg-2)',
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
  );
}
