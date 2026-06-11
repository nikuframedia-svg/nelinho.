// ExpedicaoPage · listaComponents (Q.60.S). ZERO MOCKS — endpoints reais.
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Truck, GripVertical, Check, X, Snowflake, Send } from 'lucide-react';
import { useDraggable, useDropZone } from '../../../components/dark';
import { TruckGrid } from '../../../components/expedicao/TruckGrid';
import { transportApi, type TransportBatch, type TransportManifestBoat } from '../../../lib/api';
import { transportKeys } from '../../../lib/api/keys';
import { dayLabel, shortDate, daysUntil, classifyBoat, type BatchCounts, countManifest } from '../expedicaoShared';

export interface BoatDragData {
  boat: TransportManifestBoat;
  batchId: string;
}

export function ShipmentRow({
  batch,
  counts,
  active,
  onClick,
  onDropBoat,
}: {
  batch: TransportBatch;
  counts: BatchCounts;
  active: boolean;
  onClick: () => void;
  onDropBoat: (payload: BoatDragData) => void;
}) {
  const { dropProps, isOver } = useDropZone<BoatDragData>({
    accept: 'boat',
    onDrop: (p) => onDropBoat(p.data),
  });

  const assigned = batch.assigned_orders_count ?? counts.ready + counts.inProd;
  const truckPct = assigned / batch.truck_capacity_units;
  const dx = daysUntil(batch.transport_date);

  return (
    <div
      {...dropProps}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onClick();
      }}
      style={{
        padding: '14px 16px',
        background: isOver
          ? 'var(--accent-bg)'
          : active
            ? 'var(--bg-3)'
            : 'var(--bg-1)',
        border: `1px solid ${
          isOver ? 'var(--accent-bd)' : active ? 'var(--bd-3)' : 'var(--bd-1)'
        }`,
        boxShadow: isOver ? '0 0 0 2px var(--accent-bd) inset' : 'none',
        borderRadius: 'var(--r-md)',
        cursor: 'pointer',
        transition: 'background 0.15s, border-color 0.15s',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 10,
          gap: 12,
        }}
      >
        <div>
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}
          >
            <span
              className="tabular display"
              style={{
                fontSize: 18,
                fontWeight: 500,
                color: 'var(--fg-0)',
                letterSpacing: -0.2,
              }}
            >
              {shortDate(batch.transport_date)}
            </span>
            <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              {dayLabel(batch.transport_date)}
            </span>
            {dx >= 0 && dx <= 7 ? (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: dx <= 1 ? 'var(--red)' : dx <= 3 ? 'var(--yellow)' : 'var(--green)',
                }}
              >
                D−{dx}
              </span>
            ) : null}
            {counts.atRisk > 0 ? <RowTag tone="yellow">{counts.atRisk} em risco</RowTag> : null}
            {truckPct > 0 && truckPct < 1 ? (
              <RowTag tone="blue">incompleto</RowTag>
            ) : null}
            <RowTag tone={batch.status === 'OPEN' ? 'neutral' : 'green'}>
              {batch.status === 'OPEN'
                ? 'aberto'
                : batch.status === 'FROZEN'
                  ? 'congelado'
                  : 'expedido'}
            </RowTag>
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--fg-1)' }}>{batch.code}</div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>
            → {batch.destination ?? 'destino por definir'}
          </div>
        </div>
        <TruckGrid
          ready={counts.ready}
          inProd={counts.inProd}
          atRisk={counts.atRisk}
          total={batch.truck_capacity_units}
        />
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'baseline',
          gap: 12,
          fontSize: 11,
        }}
      >
        <span>
          <span style={{ color: 'var(--fg-3)' }}>prontos </span>
          <span className="tabular" style={{ color: 'var(--green)', fontWeight: 600 }}>
            {counts.ready}
          </span>
        </span>
        <span>
          <span style={{ color: 'var(--fg-3)' }}>produção </span>
          <span className="tabular" style={{ color: 'var(--fg-1)', fontWeight: 600 }}>
            {counts.inProd}
          </span>
        </span>
        <span>
          <span style={{ color: 'var(--fg-3)' }}>camião </span>
          <span
            className="tabular"
            style={{
              color: truckPct < 0.5 ? 'var(--yellow)' : 'var(--accent)',
              fontWeight: 600,
            }}
          >
            {assigned}/{batch.truck_capacity_units}
          </span>
        </span>
      </div>
    </div>
  );
}

export function RowTag({
  tone,
  children,
}: {
  tone: 'yellow' | 'blue' | 'green' | 'neutral';
  children: React.ReactNode;
}) {
  const bg = tone === 'neutral' ? 'var(--bg-3)' : `var(--${tone}-bg)`;
  const bd = tone === 'neutral' ? 'var(--bd-1)' : `var(--${tone}-bd)`;
  const fg = tone === 'neutral' ? 'var(--fg-2)' : `var(--${tone})`;
  return (
    <span
      style={{
        fontSize: 9.5,
        padding: '1px 6px',
        background: bg,
        border: `1px solid ${bd}`,
        borderRadius: 4,
        color: fg,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: 0.3,
      }}
    >
      {children}
    </span>
  );
}

// ─── ShipmentDetail — manifesto da expedição seleccionada ───────────────────

export function ShipmentDetail({ batch }: { batch: TransportBatch }) {
  const queryClient = useQueryClient();
  const manifestQuery = useQuery({
    queryKey: transportKeys.manifest(batch.id),
    queryFn: () => transportApi.manifest(batch.id),
    retry: 0,
  });
  const manifest = manifestQuery.data;
  const counts = manifest
    ? countManifest(manifest.boats)
    : { ready: 0, inProd: 0, atRisk: 0 };

  const freezeMutation = useMutation({
    mutationFn: () => transportApi.freeze(batch.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: transportKeys.all }),
  });
  const dispatchMutation = useMutation({
    mutationFn: () => transportApi.dispatch(batch.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: transportKeys.all }),
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            justifyContent: 'space-between',
            marginBottom: 6,
            gap: 12,
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span
                className="display tabular"
                style={{
                  fontSize: 22,
                  fontWeight: 500,
                  color: 'var(--fg-0)',
                  letterSpacing: -0.3,
                }}
              >
                {shortDate(batch.transport_date)}
              </span>
              <span style={{ fontSize: 13, color: 'var(--fg-2)' }}>
                {dayLabel(batch.transport_date)}
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--fg-1)', marginTop: 3 }}>
              {batch.code}
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              → {batch.destination ?? 'destino por definir'}
            </div>
          </div>
          <TruckGrid
            ready={counts.ready}
            inProd={counts.inProd}
            atRisk={counts.atRisk}
            total={batch.truck_capacity_units}
          />
        </div>
        <div
          style={{
            fontSize: 11,
            color: 'var(--fg-3)',
            marginTop: 4,
          }}
        >
          {manifest ? `${manifest.boat_count} barcos no manifesto` : '—'}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 14 }}>
        <div
          style={{
            fontSize: 10.5,
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
            letterSpacing: 0.4,
            fontWeight: 600,
            marginBottom: 8,
          }}
        >
          Barcos · arrasta para outra expedição
        </div>
        {manifestQuery.isLoading ? (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            A carregar manifesto…
          </div>
        ) : manifestQuery.isError ? (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--danger)', fontSize: 12 }}>
            Erro a carregar o manifesto.
          </div>
        ) : !manifest || manifest.boats.length === 0 ? (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            Sem barcos atribuídos a esta expedição.
          </div>
        ) : (
          manifest.boats.map((b) => (
            <BoatTile key={b.order_id} boat={b} batchId={batch.id} />
          ))
        )}
      </div>

      <div
        style={{
          padding: '12px 18px',
          borderTop: '1px solid var(--bd-1)',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 8,
        }}
      >
        {batch.status === 'OPEN' ? (
          <button
            type="button"
            onClick={() => freezeMutation.mutate()}
            disabled={freezeMutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors disabled:opacity-50"
            style={{
              background: 'var(--bg-2)',
              color: 'var(--fg-0)',
              border: '1px solid var(--bd-2)',
            }}
          >
            <Snowflake size={12} />
            {freezeMutation.isPending ? 'A congelar…' : 'Congelar manifesto'}
          </button>
        ) : null}
        {batch.status === 'FROZEN' ? (
          <button
            type="button"
            onClick={() => dispatchMutation.mutate()}
            disabled={dispatchMutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-white transition-colors disabled:opacity-50"
            style={{ background: 'var(--blue)', border: '1px solid var(--blue)' }}
          >
            <Send size={12} />
            {dispatchMutation.isPending ? 'A expedir…' : 'Expedir camião'}
          </button>
        ) : null}
        {batch.status === 'DISPATCHED' ? (
          <span style={{ fontSize: 12, color: 'var(--green)', fontWeight: 500 }}>
            ● Camião já expedido
          </span>
        ) : null}
      </div>
    </div>
  );
}

// ─── BoatTile — barco arrastável dentro do manifesto ────────────────────────

export function BoatTile({
  boat,
  batchId,
}: {
  boat: TransportManifestBoat;
  batchId: string;
}) {
  const { dragProps, dragging } = useDraggable<BoatDragData>({
    kind: 'boat',
    data: { boat, batchId },
  });
  const cls = classifyBoat(boat);
  const color =
    cls === 'ready' ? 'green' : cls === 'at_risk' ? 'yellow' : 'fg-3';

  return (
    <div
      {...dragProps}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 11px',
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-sm)',
        cursor: 'grab',
        marginBottom: 4,
        opacity: dragging ? 0.4 : 1,
        transition: 'opacity 0.12s',
      }}
    >
      <GripVertical size={12} color="var(--fg-3)" />
      <span
        style={{
          width: 3,
          height: 24,
          background: `var(--${color})`,
          borderRadius: 2,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--fg-0)', fontWeight: 500 }}>
            #{boat.hull}{' '}
            <span style={{ color: 'var(--fg-3)', fontWeight: 400 }}>
              {boat.product_type}
            </span>
          </span>
          <span style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>{boat.status}</span>
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--fg-2)', marginTop: 2 }}>
          {boat.product_name} · {boat.current_phase}
        </div>
      </div>
    </div>
  );
}

// ─── MoveBoatConfirm — ConsequenceBox de arrasto ────────────────────────────

export function MoveBoatConfirm({
  pending,
  isPending,
  isError,
  onConfirm,
  onCancel,
}: {
  pending: { boat: TransportManifestBoat; from: TransportBatch; to: TransportBatch };
  isPending: boolean;
  isError: boolean;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState('');
  const earlier = pending.to.transport_date < pending.from.transport_date;
  const deltaDays = Math.abs(
    Math.round(
      (new Date(pending.to.transport_date).getTime() -
        new Date(pending.from.transport_date).getTime()) /
        86_400_000,
    ),
  );

  return (
    <div
      className="anim-up"
      style={{
        position: 'fixed',
        bottom: 20,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 200,
        width: 560,
        maxWidth: '92vw',
      }}
    >
      <div
        style={{
          background: 'rgba(18,18,22,0.98)',
          backdropFilter: 'blur(20px)',
          border: '1px solid var(--bd-3)',
          borderRadius: 'var(--r-lg)',
          boxShadow: 'var(--shadow-3)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--bd-1)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <Truck size={14} color="var(--accent)" />
          <span style={{ fontSize: 13, color: 'var(--fg-0)', fontWeight: 500 }}>
            Mover #{pending.boat.hull} · {pending.boat.product_type}
          </span>
          <span style={{ fontSize: 11.5, color: 'var(--fg-3)', marginLeft: 'auto' }}>
            {shortDate(pending.from.transport_date)} → {shortDate(pending.to.transport_date)}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
          <div
            style={{
              padding: 12,
              borderRight: '1px solid var(--bd-1)',
              background: 'var(--green-bg)',
            }}
          >
            <div
              style={{
                fontSize: 10.5,
                color: 'var(--green)',
                textTransform: 'uppercase',
                letterSpacing: 0.4,
                fontWeight: 600,
                marginBottom: 6,
              }}
            >
              Se mover
            </div>
            <ul
              style={{
                margin: 0,
                paddingLeft: 14,
                fontSize: 11.5,
                color: 'var(--fg-1)',
                lineHeight: 1.6,
              }}
            >
              <li>
                Cliente recebe {deltaDays} dia{deltaDays !== 1 ? 's' : ''}{' '}
                {earlier ? 'mais cedo' : 'mais tarde'}
              </li>
              <li>{pending.from.code}: liberta 1 lugar</li>
              <li>{pending.to.code}: ocupa mais 1 lugar</li>
            </ul>
          </div>
          <div style={{ padding: 12, background: 'var(--red-bg)' }}>
            <div
              style={{
                fontSize: 10.5,
                color: 'var(--red)',
                textTransform: 'uppercase',
                letterSpacing: 0.4,
                fontWeight: 600,
                marginBottom: 6,
              }}
            >
              Riscos
            </div>
            <ul
              style={{
                margin: 0,
                paddingLeft: 14,
                fontSize: 11.5,
                color: 'var(--fg-1)',
                lineHeight: 1.6,
              }}
            >
              {earlier ? (
                <li>Pode forçar horas extra para acabar a tempo</li>
              ) : (
                <li>Avisar o cliente da nova data</li>
              )}
              {(pending.to.assigned_orders_count ?? 0) + 1 >
              pending.to.truck_capacity_units ? (
                <li>Camião excede a capacidade · precisa de 2º</li>
              ) : null}
              <li>Reagendar a logística</li>
            </ul>
          </div>
        </div>

        <div
          style={{
            padding: '10px 14px',
            background: 'var(--bg-2)',
            borderTop: '1px solid var(--bd-1)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Porquê esta mudança? (opcional)"
            className="text-fg-0 placeholder:text-fg-3"
            style={{
              flex: 1,
              padding: '5px 10px',
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 6,
              color: 'var(--fg-0)',
              fontSize: 11.5,
              outline: 'none',
            }}
          />
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            style={{ background: 'transparent', color: 'var(--fg-2)' }}
          >
            <X size={11} />
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => onConfirm(reason)}
            disabled={isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-white transition-colors disabled:opacity-50"
            style={{ background: 'var(--green)' }}
          >
            <Check size={11} />
            {isPending ? 'A mover…' : 'Confirmar'}
          </button>
        </div>
        {isError ? (
          <div
            style={{
              padding: '6px 14px',
              background: 'var(--red-bg)',
              borderTop: '1px solid var(--red-bd)',
              fontSize: 11,
              color: 'var(--red)',
            }}
          >
            Não foi possível mover o barco. Tenta outra vez.
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CTPTab — Capable to Promise · POST /v1/plan/ctp (Q.53.B)
// ═══════════════════════════════════════════════════════════════════════════

/** ISO de hoje, YYYY-MM-DD — default do campo de data. */
