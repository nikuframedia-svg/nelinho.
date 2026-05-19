/**
 * MaterialDetailSheet — painel lateral de detalhe de um material (Q.52.K).
 *
 * Mostra a posição (on-hand + in-transit) e o histórico de movimentos.
 * Ambos os endpoints são PARTIAL — quando degradam, o painel mostra um
 * empty state honesto com a razão (nunca placeholder).
 *
 * Acções: ajustar stock (POST .../adjust) e editar mínimo
 * (PATCH .../min-stock). Mutações invalidam as queries da página.
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDownLeft, ArrowUpRight, SlidersHorizontal } from 'lucide-react';
import { Sheet } from '../dark/Sheet';
import { EmptyState } from '../dark/EmptyState';
import { useHonestEmptyState } from '../../hooks/useHonestEmptyState';
import { materiaisApi, type Material } from './materiaisApi';

interface Props {
  material: Material | null;
  onClose: () => void;
}

export function MaterialDetailSheet({ material, onClose }: Props): ReactNode {
  const queryClient = useQueryClient();
  const skuId = material?.sku_id ?? '';
  const [delta, setDelta] = useState('');
  const [reason, setReason] = useState('');
  const [minStock, setMinStock] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const positionQuery = useQuery({
    queryKey: ['materiais', 'position', skuId],
    queryFn: () => materiaisApi.getPosition(skuId),
    enabled: material !== null,
    retry: 0,
  });

  const movementsQuery = useQuery({
    queryKey: ['materiais', 'movements', skuId],
    queryFn: () => materiaisApi.getMovements(skuId, 50),
    enabled: material !== null,
    retry: 0,
  });

  const honest = useHonestEmptyState(positionQuery.data);

  const invalidate = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['materiais'] });
  };

  const adjustMutation = useMutation({
    mutationFn: () =>
      materiaisApi.adjustStock(skuId, {
        qty_delta: Number(delta),
        reason: reason.trim(),
      }),
    onSuccess: () => {
      setDelta('');
      setReason('');
      setActionError(null);
      invalidate();
    },
    onError: (e: unknown) => {
      setActionError(e instanceof Error ? e.message : 'Falha no ajuste de stock.');
    },
  });

  const minStockMutation = useMutation({
    mutationFn: () => materiaisApi.patchMinStock(skuId, Number(minStock)),
    onSuccess: () => {
      setMinStock('');
      setActionError(null);
      invalidate();
    },
    onError: (e: unknown) => {
      setActionError(
        e instanceof Error ? e.message : 'Falha a actualizar o mínimo.',
      );
    },
  });

  const pos = positionQuery.data;
  const movements = movementsQuery.data ?? [];

  const inputCls = 'text-slate-900 placeholder:text-slate-400';
  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '7px 10px',
    background: 'var(--bg-0)',
    border: '1px solid var(--bd-1)',
    borderRadius: 'var(--r-sm)',
    outline: 'none',
    fontSize: 12,
    height: 32,
  };

  return (
    <Sheet
      open={material !== null}
      onClose={onClose}
      title={material?.name ?? 'Material'}
      subtitle={
        material
          ? `${material.sku_id} · ${material.unit_of_measure}${material.category ? ` · ${material.category}` : ''}`
          : ''
      }
      width={520}
    >
      {material === null ? null : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {/* ── Posição ─────────────────────────────────────────────── */}
          <section>
            <h3
              style={{
                fontSize: 11,
                textTransform: 'uppercase',
                letterSpacing: 0.5,
                color: 'var(--fg-3)',
                fontWeight: 600,
                marginBottom: 8,
              }}
            >
              Posição actual
            </h3>
            {positionQuery.isLoading ? (
              <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>A carregar…</div>
            ) : positionQuery.isError ? (
              <EmptyState
                title="Não foi possível ler a posição"
                hint="O endpoint /v1/supply/materials/{sku}/position falhou. Tenta recarregar."
                icon={<SlidersHorizontal size={20} />}
                size="sm"
              />
            ) : honest.degraded ? (
              <EmptyState
                title="Posição indisponível"
                hint={honest.reason}
                icon={<SlidersHorizontal size={20} />}
                size="sm"
              />
            ) : pos ? (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: 8,
                }}
              >
                <Metric label="On-hand" value={`${pos.on_hand} ${material.unit_of_measure}`} />
                <Metric
                  label="Em trânsito"
                  value={`${pos.in_transit.qty} ${material.unit_of_measure}`}
                />
                <Metric
                  label="Projetado (14d)"
                  value={`${pos.projected_stock_horizon} ${material.unit_of_measure}`}
                />
                <Metric
                  label="Mínimo efetivo"
                  value={`${pos.min_stock} ${material.unit_of_measure}`}
                />
                <Metric
                  label="ROP"
                  value={pos.rop !== null ? `${pos.rop}` : '—'}
                />
                <Metric
                  label="Acaba em"
                  value={
                    pos.days_to_stockout !== null
                      ? `~${Math.round(pos.days_to_stockout)}d`
                      : '—'
                  }
                  tone={pos.below_min ? 'red' : 'green'}
                />
              </div>
            ) : null}

            {pos && pos.in_transit.entries.length > 0 && (
              <div style={{ marginTop: 10 }}>
                {pos.in_transit.entries.map((e, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: 11.5,
                      color: 'var(--fg-2)',
                      padding: '6px 0',
                      borderBottom: '1px solid var(--bd-1)',
                    }}
                  >
                    <span>Entrega · {e.eta}</span>
                    <span className="tabular">
                      {e.qty} {material.unit_of_measure}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* ── Movimentos ──────────────────────────────────────────── */}
          <section>
            <h3
              style={{
                fontSize: 11,
                textTransform: 'uppercase',
                letterSpacing: 0.5,
                color: 'var(--fg-3)',
                fontWeight: 600,
                marginBottom: 8,
              }}
            >
              Movimentos recentes
            </h3>
            {movementsQuery.isLoading ? (
              <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>A carregar…</div>
            ) : movementsQuery.isError ? (
              <EmptyState
                title="Histórico indisponível"
                hint="O endpoint /v1/supply/materials/{sku}/movements falhou."
                size="sm"
              />
            ) : movements.length === 0 ? (
              <EmptyState
                title="Sem movimentos"
                hint="Ainda não há consumos, receções ou ajustes registados para este SKU."
                size="sm"
              />
            ) : (
              <div>
                {movements.map((m, i) => {
                  const positive = m.qty_change >= 0;
                  return (
                    <div
                      key={i}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        fontSize: 11.5,
                        padding: '6px 0',
                        borderBottom: '1px solid var(--bd-1)',
                      }}
                    >
                      {positive ? (
                        <ArrowDownLeft size={13} color="var(--green)" />
                      ) : (
                        <ArrowUpRight size={13} color="var(--red)" />
                      )}
                      <span style={{ flex: 1, color: 'var(--fg-1)' }}>
                        {m.transaction_type}
                        {m.occurred_at
                          ? ` · ${new Date(m.occurred_at).toLocaleDateString('pt-PT')}`
                          : ''}
                      </span>
                      <span
                        className="tabular"
                        style={{ color: positive ? 'var(--green)' : 'var(--red)' }}
                      >
                        {positive ? '+' : ''}
                        {m.qty_change}
                      </span>
                      <span
                        className="tabular"
                        style={{ color: 'var(--fg-3)', width: 60, textAlign: 'right' }}
                      >
                        {m.on_hand_after}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* ── Acções ──────────────────────────────────────────────── */}
          <section
            style={{
              borderTop: '1px solid var(--bd-1)',
              paddingTop: 14,
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            {actionError && (
              <div
                style={{
                  fontSize: 11.5,
                  color: 'var(--red)',
                  background: 'var(--red-bg)',
                  border: '1px solid var(--red-bd)',
                  borderRadius: 'var(--r-sm)',
                  padding: '6px 10px',
                }}
              >
                {actionError}
              </div>
            )}

            <div>
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--fg-2)',
                  marginBottom: 6,
                  fontWeight: 500,
                }}
              >
                Ajustar stock (manual)
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <input
                  className={inputCls}
                  style={{ ...inputStyle, width: 90 }}
                  type="number"
                  placeholder="±qtd"
                  value={delta}
                  onChange={(e) => setDelta(e.target.value)}
                />
                <input
                  className={inputCls}
                  style={inputStyle}
                  placeholder="Motivo do ajuste"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
                <button
                  type="button"
                  disabled={
                    delta.trim() === '' ||
                    reason.trim() === '' ||
                    adjustMutation.isPending
                  }
                  onClick={() => adjustMutation.mutate()}
                  style={actionBtnStyle(
                    delta.trim() === '' || reason.trim() === '',
                  )}
                >
                  {adjustMutation.isPending ? '…' : 'Aplicar'}
                </button>
              </div>
            </div>

            <div>
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--fg-2)',
                  marginBottom: 6,
                  fontWeight: 500,
                }}
              >
                Editar stock mínimo (actual: {material.min_stock_qty})
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <input
                  className={inputCls}
                  style={inputStyle}
                  type="number"
                  placeholder="Novo mínimo"
                  value={minStock}
                  onChange={(e) => setMinStock(e.target.value)}
                />
                <button
                  type="button"
                  disabled={minStock.trim() === '' || minStockMutation.isPending}
                  onClick={() => minStockMutation.mutate()}
                  style={actionBtnStyle(minStock.trim() === '')}
                >
                  {minStockMutation.isPending ? '…' : 'Guardar'}
                </button>
              </div>
            </div>
          </section>
        </div>
      )}
    </Sheet>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: 'red' | 'green';
}): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-sm)',
        padding: '8px 10px',
      }}
    >
      <div style={{ fontSize: 10, color: 'var(--fg-3)', textTransform: 'uppercase' }}>
        {label}
      </div>
      <div
        className="tabular"
        style={{
          fontSize: 14,
          fontWeight: 600,
          marginTop: 3,
          color: tone ? `var(--${tone})` : 'var(--fg-0)',
        }}
      >
        {value}
      </div>
    </div>
  );
}

function actionBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    padding: '0 12px',
    height: 32,
    fontSize: 11.5,
    fontWeight: 500,
    borderRadius: 'var(--r-sm)',
    border: '1px solid transparent',
    background: disabled ? 'var(--bg-3)' : 'var(--accent)',
    color: disabled ? 'var(--fg-3)' : '#fff',
    cursor: disabled ? 'not-allowed' : 'pointer',
    whiteSpace: 'nowrap',
  };
}
