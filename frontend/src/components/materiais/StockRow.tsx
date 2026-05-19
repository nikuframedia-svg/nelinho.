/**
 * StockRow — linha da tabela de stock (Q.52.K).
 *
 * Port fiel da `StockRow` de design/nelo/page-materiais.jsx. Grelha de 6
 * colunas, barra mini de cobertura, tom por estado. Dados sempre por
 * props — o caller funde `Material` (master) + `MaterialPosition`
 * (on-hand real, PARTIAL).
 */

import type { ReactNode } from 'react';
import type { Material, MaterialPosition } from './materiaisApi';

export type StockState = 'ok' | 'low' | 'critical' | 'out' | 'unknown';

export interface StockRowData {
  material: Material;
  position: MaterialPosition | null;
}

const STATE_TONE: Record<StockState, string> = {
  ok: 'green',
  low: 'yellow',
  critical: 'red',
  out: 'red',
  unknown: 'gray',
};

const STATE_LABEL: Record<StockState, string> = {
  ok: 'OK',
  low: 'Baixo',
  critical: 'Crítico',
  out: 'Esgotado',
  unknown: 'Sem leitura',
};

export function stateFor(d: StockRowData): StockState {
  if (d.position === null) return 'unknown';
  const { on_hand, min_stock, critical } = d.position;
  if (on_hand <= 0) return 'out';
  if (critical) return 'critical';
  if (min_stock > 0 && on_hand < min_stock) return 'low';
  return 'ok';
}

const GRID = '2fr 120px 110px 110px 130px 100px';

export function StockRowHeader(): ReactNode {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: GRID,
        alignItems: 'center',
        gap: 14,
        padding: '12px 16px',
        borderBottom: '1px solid var(--bd-1)',
        background: 'var(--bg-2)',
        fontSize: 10.5,
        color: 'var(--fg-3)',
        textTransform: 'uppercase',
        letterSpacing: 0.4,
        fontWeight: 600,
      }}
    >
      <div>Material</div>
      <div>On-hand</div>
      <div>Mínimo</div>
      <div>Estado</div>
      <div>Acaba em</div>
      <div />
    </div>
  );
}

export interface StockRowProps {
  data: StockRowData;
  onSelect: (skuId: string) => void;
  onOrder: (skuId: string) => void;
}

export function StockRow({ data, onSelect, onOrder }: StockRowProps): ReactNode {
  const { material, position } = data;
  const state = stateFor(data);
  const tone = STATE_TONE[state];
  const onHand = position?.on_hand;
  const minStock = position?.min_stock ?? material.min_stock_qty;
  const unit = material.unit_of_measure;
  const pct =
    position && minStock > 0
      ? Math.min(150, (position.on_hand / minStock) * 100)
      : 0;
  const days = position?.days_to_stockout;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(material.sku_id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(material.sku_id);
        }
      }}
      style={{
        display: 'grid',
        gridTemplateColumns: GRID,
        alignItems: 'center',
        gap: 14,
        padding: '12px 16px',
        borderBottom: '1px solid var(--bd-1)',
        background: state === 'out' ? 'var(--red-bg)' : 'transparent',
        cursor: 'pointer',
      }}
    >
      <div>
        <div style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}>
          {material.name}
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--fg-3)', marginTop: 3 }}>
          {material.sku_id}
          {material.category ? ` · ${material.category}` : ''}
          {material.critical_flag ? ' · crítico' : ''}
        </div>
      </div>
      <div
        className="tabular"
        style={{ fontSize: 13, color: 'var(--fg-0)', fontWeight: 600 }}
      >
        {onHand === undefined ? (
          <span style={{ color: 'var(--fg-3)', fontWeight: 400 }}>—</span>
        ) : (
          <>
            {onHand.toLocaleString('pt-PT')}{' '}
            <span style={{ fontSize: 10, color: 'var(--fg-3)', fontWeight: 400 }}>
              {unit}
            </span>
          </>
        )}
      </div>
      <div className="tabular" style={{ fontSize: 12, color: 'var(--fg-2)' }}>
        {minStock.toLocaleString('pt-PT')} {unit}
      </div>
      <div>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '2px 8px',
            borderRadius: 5,
            fontSize: 10.5,
            fontWeight: 600,
            color: tone === 'gray' ? 'var(--fg-2)' : `var(--${tone})`,
            background:
              tone === 'gray' ? 'var(--bg-3)' : `var(--${tone}-bg)`,
            border: `1px solid ${tone === 'gray' ? 'var(--bd-1)' : `var(--${tone}-bd)`}`,
          }}
        >
          {STATE_LABEL[state]}
        </span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        {days === undefined || days === null ? (
          <span style={{ color: 'var(--fg-3)' }}>—</span>
        ) : (
          <>
            <span
              className="tabular"
              style={{ color: tone === 'gray' ? 'var(--fg-2)' : `var(--${tone})` }}
            >
              {days <= 0 ? 'esgotado' : `~${Math.round(days)}d`}
            </span>
            {days > 0 && (
              <div
                style={{
                  marginTop: 4,
                  height: 3,
                  background: 'var(--bg-3)',
                  borderRadius: 2,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(100, (pct / 150) * 100)}%`,
                    background:
                      tone === 'gray' ? 'var(--fg-3)' : `var(--${tone})`,
                  }}
                />
              </div>
            )}
          </>
        )}
      </div>
      <div>
        {(state === 'out' || state === 'critical' || state === 'low') && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onOrder(material.sku_id);
            }}
            style={{
              padding: '4px 10px',
              height: 26,
              fontSize: 11,
              fontWeight: 500,
              borderRadius: 6,
              cursor: 'pointer',
              border: '1px solid transparent',
              background:
                state === 'low' ? 'var(--bg-2)' : 'var(--orange)',
              color: state === 'low' ? 'var(--fg-0)' : '#fff',
              borderColor: state === 'low' ? 'var(--bd-2)' : 'transparent',
            }}
          >
            Encomendar
          </button>
        )}
      </div>
    </div>
  );
}
