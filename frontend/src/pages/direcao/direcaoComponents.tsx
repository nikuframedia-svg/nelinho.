// DirecaoPage — componentes e helpers (Q.60.W).
import { useMemo } from 'react';
import { ObjectiveBar, EmptyState } from '../../components/dark';
import { MarginRow } from '../../components/ceo/CeoBits';
import { type ObjectiveBand, type Pp1Impact, type MarginBySegmentResponse } from './direcaoApi';
import { type LiveKpis } from './direcaoTypes';

export const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  draft: { label: 'Rascunho', tone: 'neutral' },
  planned: { label: 'Planeado', tone: 'info' },
  frozen: { label: 'Congelado', tone: 'warning' },
  dispatched: { label: 'Expedido', tone: 'success' },
};

export function fmtDate(iso?: string | null): string {
  if (!iso) return '—';
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

// ─── Página ─────────────────────────────────────────────────────────────

export function realisedForKpi(kpi: string, live: LiveKpis): number | null {
  switch (kpi) {
    case 'throughput_eur_day':
      return live.throughputToday !== null
        ? Number((live.throughputToday / 1000).toFixed(1))
        : null;
    case 'otd_pct':
      return live.otdPct !== null ? Number(live.otdPct.toFixed(1)) : null;
    case 'fpy_pct':
      return live.fpyPct !== null ? Number(live.fpyPct.toFixed(1)) : null;
    case 'rework_pct':
      return live.reworkRate !== null
        ? Number((live.reworkRate * 100).toFixed(1))
        : null;
    default:
      return null;
  }
}

// ─── ObjectiveCell ───────────────────────────────────────────────────────

export function ObjectiveCell({
  band,
  realised,
}: {
  band: ObjectiveBand;
  realised: number | null;
}) {
  // A banda do backend `throughput_eur_day` vem em € — a ObjectiveBar
  // mostra-a em K para casar com o realizado. Os restantes KPIs (%) já
  // estão na escala certa.
  const isThroughput = band.kpi === 'throughput_eur_day';
  const scale = isThroughput ? 1000 : 1;
  const unit = isThroughput ? 'K' : band.unit;
  return (
    <div>
      <div
        style={{
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        {band.label}
      </div>
      {realised !== null ? (
        <ObjectiveBar
          value={realised}
          low={band.low / scale}
          high={band.high / scale}
          unit={unit}
        />
      ) : (
        <div
          style={{
            fontSize: 11,
            color: 'var(--fg-3)',
            padding: '6px 0',
          }}
        >
          alvo {(band.target / scale).toLocaleString('pt-PT')}
          {unit} · sem realizado
        </div>
      )}
      <div
        style={{
          fontSize: 9.5,
          color: 'var(--fg-3)',
          marginTop: 2,
        }}
      >
        alvo {(band.target / scale).toLocaleString('pt-PT')}
        {unit}
        {band.source === 'tenant_config' ? ' · configurado' : ''}
      </div>
    </div>
  );
}

// ─── SummaryStat ─────────────────────────────────────────────────────────

export function SummaryStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'green' | 'red' | 'neutral';
}) {
  const color =
    tone === 'green'
      ? 'var(--green)'
      : tone === 'red'
        ? 'var(--red)'
        : 'var(--fg-0)';
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        padding: '8px 0',
        borderBottom: '1px solid var(--bd-1)',
        fontSize: 12,
      }}
    >
      <span style={{ color: 'var(--fg-2)' }}>{label}</span>
      <span className="tabular" style={{ color, fontWeight: 600 }}>
        {value}
      </span>
    </div>
  );
}

// ─── CountryMargins — margem agregada por país do ERP NELO ───────────────

export function CountryMargins({ data }: { data: MarginBySegmentResponse | null }) {
  const rows = useMemo(() => {
    const segments = data?.segments ?? [];
    // margin_pct vem 0–1 no backend → ×100 para a percentagem que a
    // MarginRow espera. Ordena por margem € decrescente (já vem assim,
    // mas garantimos para não depender da ordem do backend).
    return segments
      .map((s) => ({
        label: s.segment,
        margin: s.margin_pct !== null ? s.margin_pct * 100 : 0,
        revenue: s.revenue_eur,
        marginEur: s.margin_eur,
      }))
      .sort((a, b) => b.marginEur - a.marginEur);
  }, [data]);

  if (rows.length === 0) {
    return (
      <EmptyState
        size="sm"
        title="Sem margem por país"
        hint="O ERP respondeu, mas nenhuma ordem tem país atribuído para segmentar."
      />
    );
  }
  return (
    <div>
      {rows.map((r, i) => (
        <MarginRow
          key={r.label}
          label={r.label}
          margin={r.margin}
          revenue={r.revenue}
          asPill
          last={i === rows.length - 1}
        />
      ))}
    </div>
  );
}

// ─── ImpactPP1 — € poupado por sugestões aceites (decisões executadas) ───

export function ImpactPP1({
  impact,
  isLoading,
  isError,
}: {
  impact: Pp1Impact | null;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) {
    return (
      <div
        style={{
          padding: 12,
          textAlign: 'center',
          color: 'var(--fg-3)',
          fontSize: 12,
        }}
      >
        A carregar impacto PP1…
      </div>
    );
  }
  if (isError || !impact) {
    return (
      <div style={{ marginTop: 4 }}>
        <EmptyState
          size="sm"
          title="Impacto PP1 indisponível"
          hint="Não foi possível ler o sinal de impacto-PP1. Tenta recarregar a página."
        />
      </div>
    );
  }
  // Sem decisões aceites na janela — mostra a razão honesta do backend.
  if (impact.accepted_decisions === 0) {
    return (
      <div style={{ marginTop: 4 }}>
        <EmptyState
          size="sm"
          title="Impacto PP1 ainda não quantificado"
          hint={
            impact.reason ||
            'A poupança começa a contar quando as sugestões do sistema forem aceites e executadas.'
          }
        />
      </div>
    );
  }
  return (
    <div style={{ marginTop: 4 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 6,
          marginBottom: 4,
        }}
      >
        <span
          className="display tabular"
          style={{
            fontSize: 26,
            fontWeight: 500,
            color: impact.eur_saved > 0 ? 'var(--green)' : 'var(--fg-0)',
            letterSpacing: -0.4,
          }}
        >
          €{Math.round(impact.eur_saved).toLocaleString('pt-PT')}
        </span>
        <span style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>
          poupado · {impact.window_days} dias
        </span>
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
        {impact.accepted_decisions} decis
        {impact.accepted_decisions === 1 ? 'ão' : 'ões'} aceite
        {impact.accepted_decisions === 1 ? '' : 's'}
        {impact.decisions_with_eur < impact.accepted_decisions
          ? ` · ${impact.decisions_with_eur} com € medido`
          : ''}
      </div>
      {impact.decisions_with_eur < impact.accepted_decisions ? (
        <div
          style={{
            fontSize: 10.5,
            color: 'var(--fg-3)',
            marginTop: 6,
            lineHeight: 1.5,
          }}
        >
          As restantes decisões ainda não têm impacto € registado — o
          valor mostrado é só o que foi medido.
        </div>
      ) : null}
    </div>
  );
}
