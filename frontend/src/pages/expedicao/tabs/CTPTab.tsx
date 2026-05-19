// ExpedicaoPage · CTPTab (Q.60.S). ZERO MOCKS — endpoints reais.
import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Target, CalendarClock, PackageCheck, AlertTriangle, CircleSlash } from 'lucide-react';
import { EmptyState } from '../../../components/dark';
import { type TransportBatch } from '../../../lib/api';
import { expedicaoCtpApi, type CtpBoat, type CtpResponse } from '../expedicaoCtpApi';
import { shortDate, todayIso } from '../expedicaoShared';

export function CTPTab({
  batches,
  batchesLoading,
}: {
  batches: TransportBatch[];
  batchesLoading: boolean;
}) {
  // Pré-preenche com o camião aberto mais próximo, se houver.
  const openBatches = useMemo(
    () =>
      [...batches]
        .filter((b) => b.status === 'OPEN')
        .sort(
          (a, b) =>
            new Date(a.transport_date).getTime() -
            new Date(b.transport_date).getTime(),
        ),
    [batches],
  );

  const [truckDate, setTruckDate] = useState('');
  const [capacity, setCapacity] = useState('6');
  const [startFrom, setStartFrom] = useState('');

  // Resultado da última avaliação — mutation porque o CTP só *computa*
  // a pedido (não é uma query reactiva a parâmetros de URL).
  const ctpMutation = useMutation({
    mutationFn: (vars: {
      truck_date: string;
      truck_capacity: number;
      start_from?: string;
    }) => expedicaoCtpApi.evaluate(vars),
  });

  const result = ctpMutation.data ?? null;

  const capacityNum = Number(capacity);
  const dateValid = truckDate.length === 10;
  const capacityValid =
    Number.isFinite(capacityNum) && capacityNum >= 1 && capacityNum <= 100;
  const canSubmit = dateValid && capacityValid && !ctpMutation.isPending;

  const applyBatch = (b: TransportBatch) => {
    setTruckDate(b.transport_date.slice(0, 10));
    setCapacity(String(b.truck_capacity_units));
  };

  const runCtp = () => {
    if (!canSubmit) return;
    ctpMutation.mutate({
      truck_date: truckDate,
      truck_capacity: capacityNum,
      start_from: startFrom || undefined,
    });
  };

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '320px 1fr',
        gap: 14,
        alignItems: 'start',
      }}
    >
      {/* ─── Esquerda — formulário do pedido ─────────────────────────── */}
      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--bd-1)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 7,
              background: 'var(--bg-3)',
              border: '1px solid var(--bd-2)',
              display: 'grid',
              placeItems: 'center',
              color: 'var(--accent)',
            }}
          >
            <Target size={14} />
          </div>
          <div>
            <div className="display" style={{ fontSize: 14, fontWeight: 500 }}>
              CTP · Capable to Promise
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>
              Que barcos encaixam num camião/data
            </div>
          </div>
        </div>

        <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Atalhos — camiões abertos */}
          {batchesLoading ? (
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              A carregar camiões…
            </div>
          ) : openBatches.length > 0 ? (
            <div>
              <FieldLabel>Usar camião aberto</FieldLabel>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {openBatches.slice(0, 6).map((b) => (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => applyBatch(b)}
                    style={{
                      fontSize: 10.5,
                      padding: '3px 9px',
                      borderRadius: 999,
                      background:
                        truckDate === b.transport_date.slice(0, 10)
                          ? 'var(--accent-bg)'
                          : 'var(--bg-3)',
                      border: `1px solid ${
                        truckDate === b.transport_date.slice(0, 10)
                          ? 'var(--accent-bd)'
                          : 'var(--bd-1)'
                      }`,
                      color: 'var(--fg-1)',
                      cursor: 'pointer',
                    }}
                  >
                    {shortDate(b.transport_date)} · {b.code}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div>
            <FieldLabel>Data de partida do camião</FieldLabel>
            <input
              type="date"
              value={truckDate}
              min={todayIso()}
              onChange={(e) => setTruckDate(e.target.value)}
              className="text-slate-900"
              style={ctpInputStyle}
            />
          </div>

          <div>
            <FieldLabel>Capacidade (slots)</FieldLabel>
            <input
              type="number"
              min={1}
              max={100}
              value={capacity}
              onChange={(e) => setCapacity(e.target.value)}
              className="text-slate-900 placeholder:text-slate-400"
              style={ctpInputStyle}
            />
            {!capacityValid && capacity !== '' ? (
              <div style={{ fontSize: 10, color: 'var(--red)', marginTop: 3 }}>
                Capacidade entre 1 e 100.
              </div>
            ) : null}
          </div>

          <div>
            <FieldLabel>Produção pode começar (opcional)</FieldLabel>
            <input
              type="date"
              value={startFrom}
              onChange={(e) => setStartFrom(e.target.value)}
              className="text-slate-900"
              style={ctpInputStyle}
            />
            <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 3 }}>
              Vazio → assume hoje.
            </div>
          </div>

          <button
            type="button"
            onClick={runCtp}
            disabled={!canSubmit}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-xs font-semibold text-white transition-colors disabled:opacity-50"
            style={{ background: 'var(--accent)' }}
          >
            <Target size={12} />
            {ctpMutation.isPending ? 'A calcular…' : 'Calcular encaixe'}
          </button>

          {ctpMutation.isError ? (
            <div
              style={{
                fontSize: 11,
                color: 'var(--red)',
                background: 'var(--red-bg)',
                border: '1px solid var(--red-bd)',
                borderRadius: 6,
                padding: '6px 9px',
              }}
            >
              Não foi possível calcular o CTP. Confirma a data e tenta outra
              vez.
            </div>
          ) : null}
        </div>
      </div>

      {/* ─── Direita — painel de sugestão ────────────────────────────── */}
      <div>
        {ctpMutation.isPending ? (
          <div
            style={{
              padding: 48,
              textAlign: 'center',
              color: 'var(--fg-3)',
              fontSize: 12,
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-lg)',
            }}
          >
            A avaliar barcos contra a data do camião…
          </div>
        ) : result ? (
          <CTPResultPanel result={result} />
        ) : (
          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-lg)',
              padding: 8,
            }}
          >
            <EmptyState
              title="Escolhe um camião e uma data"
              hint="Indica a data de partida e a capacidade do camião — o CTP avalia cada barco em curso (data viável, capacidade, materiais, molde) e diz quais podes prometer."
              icon={<Target size={32} />}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export const ctpInputStyle: React.CSSProperties = {
  width: '100%',
  padding: '6px 10px',
  background: 'white',
  border: '1px solid var(--bd-2)',
  borderRadius: 6,
  fontSize: 12,
  outline: 'none',
};

export function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10,
        color: 'var(--fg-3)',
        textTransform: 'uppercase',
        letterSpacing: 0.4,
        fontWeight: 600,
        marginBottom: 5,
      }}
    >
      {children}
    </div>
  );
}

// ─── CTPResultPanel — sugestão do CTP ───────────────────────────────────────

export function CTPResultPanel({ result }: { result: CtpResponse }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Resumo */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 8,
        }}
      >
        <CTPSummaryCell
          label="Slots usados"
          value={`${result.slots_used}/${result.truck_capacity}`}
          tone="accent"
        />
        <CTPSummaryCell
          label="Encaixam"
          value={result.summary.n_committable}
          tone="green"
        />
        <CTPSummaryCell
          label="Em risco"
          value={result.summary.n_at_risk}
          tone={result.summary.n_at_risk > 0 ? 'yellow' : 'fg-2'}
        />
        <CTPSummaryCell
          label="Não chegam"
          value={result.summary.n_rejected}
          tone={result.summary.n_rejected > 0 ? 'red' : 'fg-2'}
        />
      </div>

      <CTPBoatGroup
        icon={<PackageCheck size={13} color="var(--green)" />}
        title="Encaixam no camião"
        subtitle={`Data viável, capacidade e materiais OK · partida ${shortDate(result.truck_date)}`}
        boats={result.committable}
        tone="green"
        emptyHint="Nenhum barco encaixa neste camião com estes parâmetros. Tenta uma data mais tarde ou outra capacidade."
      />

      {result.at_risk.length > 0 ? (
        <CTPBoatGroup
          icon={<AlertTriangle size={13} color="var(--yellow)" />}
          title="Encaixam mas com risco"
          subtitle="Data viável, mas falta material — decisão do planeador"
          boats={result.at_risk}
          tone="yellow"
        />
      ) : null}

      {result.rejected.length > 0 ? (
        <CTPBoatGroup
          icon={<CircleSlash size={13} color="var(--fg-3)" />}
          title="Não chegam a tempo"
          subtitle="A data sugerida de expedição é depois da partida do camião"
          boats={result.rejected}
          tone="neutral"
        />
      ) : null}
    </div>
  );
}

export function CTPSummaryCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone: 'accent' | 'green' | 'yellow' | 'red' | 'fg-2';
}) {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        padding: '10px 12px',
      }}
    >
      <div
        style={{
          fontSize: 9.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        className="tabular display"
        style={{ fontSize: 20, fontWeight: 500, color: `var(--${tone})` }}
      >
        {value}
      </div>
    </div>
  );
}

export function CTPBoatGroup({
  icon,
  title,
  subtitle,
  boats,
  tone,
  emptyHint,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  boats: CtpBoat[];
  tone: 'green' | 'yellow' | 'neutral';
  emptyHint?: string;
}) {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--bd-1)',
          display: 'flex',
          alignItems: 'center',
          gap: 9,
        }}
      >
        {icon}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
            {title}{' '}
            <span
              className="tabular"
              style={{ color: 'var(--fg-3)', fontWeight: 400 }}
            >
              ({boats.length})
            </span>
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>{subtitle}</div>
        </div>
      </div>
      {boats.length === 0 ? (
        <div
          style={{
            padding: 16,
            fontSize: 11.5,
            color: 'var(--fg-3)',
            textAlign: 'center',
          }}
        >
          {emptyHint ?? 'Sem barcos neste grupo.'}
        </div>
      ) : (
        <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {boats.map((b) => (
            <CTPBoatRow key={b.order_id} boat={b} tone={tone} />
          ))}
        </div>
      )}
    </div>
  );
}

export function CTPBoatRow({
  boat,
  tone,
}: {
  boat: CtpBoat;
  tone: 'green' | 'yellow' | 'neutral';
}) {
  const stripe =
    tone === 'green' ? 'green' : tone === 'yellow' ? 'yellow' : 'fg-3';
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 11px',
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-sm)',
      }}
    >
      <span
        style={{
          width: 3,
          height: 28,
          background: `var(--${stripe})`,
          borderRadius: 2,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--fg-0)', fontWeight: 500 }}>
            {boat.hull ? `#${boat.hull}` : 'Ordem'}{' '}
            <span style={{ color: 'var(--fg-3)', fontWeight: 400 }}>
              {boat.product_type ?? ''}
            </span>
          </span>
          <span
            className="tabular"
            style={{
              fontSize: 10.5,
              color: 'var(--fg-2)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <CalendarClock size={10} color="var(--fg-3)" />
            {boat.suggested_shipment
              ? shortDate(boat.suggested_shipment)
              : 'sem data'}
          </span>
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--fg-2)', marginTop: 2 }}>
          {boat.product_name ?? 'produto por definir'}
          {boat.lead_time !== null ? ` · lead-time ${boat.lead_time}` : ''}
        </div>
        {/* Razões — porque é que o barco está neste grupo */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 5,
            marginTop: 5,
          }}
        >
          <CTPReason ok={boat.date_feasible}>
            {boat.date_feasible ? 'data viável' : 'data inviável'}
          </CTPReason>
          <CTPReason ok={boat.materials_ok}>
            {boat.materials_ok
              ? 'materiais OK'
              : `falta material${
                  boat.missing_materials.length > 0
                    ? ` (${boat.missing_materials.length})`
                    : ''
                }`}
          </CTPReason>
          {boat.risk ? <CTPReason ok={false}>{boat.risk}</CTPReason> : null}
        </div>
      </div>
    </div>
  );
}

export function CTPReason({
  ok,
  children,
}: {
  ok: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      style={{
        fontSize: 9.5,
        padding: '1px 6px',
        borderRadius: 4,
        background: ok ? 'var(--green-bg)' : 'var(--red-bg)',
        border: `1px solid ${ok ? 'var(--green-bd)' : 'var(--red-bd)'}`,
        color: ok ? 'var(--green)' : 'var(--red)',
        fontWeight: 600,
      }}
    >
      {children}
    </span>
  );
}
