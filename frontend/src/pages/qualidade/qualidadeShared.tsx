// QualidadePage — hooks de dados, primitivas e constantes partilhadas (Q.60.Q).
import { useQuery } from '@tanstack/react-query';
import { Euro } from 'lucide-react';
import { EmptyState } from '../../components/dark';
import { Card, SectionHeader } from '../../components/qualidade/QualidadeBits';
import { fetchRoiActions, type HullZoneId } from '../../components/qualidade/qualidadeApi';
import { apiFetch, moldsApi, type Mold } from '../../lib/api';
import { type ReworkRow, type MoldQuality } from './qualidadeTypes';

export function useFpy() {
  return useQuery({
    queryKey: ['qualidade', 'fpy'],
    queryFn: () =>
      apiFetch<{
        window_days: number;
        orders_total: number;
        orders_with_rework: number;
        first_pass_yield_pct: number;
      }>('/v1/quality/first-pass-yield?window_days=30'),
    staleTime: 60_000,
    retry: 0,
  });
}

export function useReworkList() {
  return useQuery<ReworkRow[]>({
    queryKey: ['qualidade', 'rework'],
    queryFn: () => apiFetch<ReworkRow[]>('/v1/quality/rework?limit=100'),
    staleTime: 60_000,
    retry: 0,
  });
}

export function useMolds() {
  return useQuery<Mold[]>({
    queryKey: ['qualidade', 'molds-health'],
    queryFn: () => moldsApi.healthReport({ limit: 30 }),
    staleTime: 60_000,
    retry: 0,
  });
}

/**
 * Q.54.S — moldes reais (factory_curated.mold) cruzados com os eventos de
 * qualidade. Distinto de `useMolds`, que serve o catálogo de planeamento
 * (`plan.mold`) cujo espaço de IDs não casa com os dados de defeitos.
 */
export function useMoldQuality() {
  return useQuery<MoldQuality[]>({
    queryKey: ['qualidade', 'mold-quality'],
    queryFn: () => apiFetch<MoldQuality[]>('/v1/quality/molds?limit=60'),
    staleTime: 60_000,
    retry: 0,
  });
}

export function RoiCard() {
  // Q.53.H — GET /v1/quality/roi-actions: € poupado vs investido por
  // acção, ordenado por retorno líquido.
  const roiQuery = useQuery({
    queryKey: ['qualidade', 'roi-actions'],
    queryFn: () => fetchRoiActions(25),
    staleTime: 60_000,
    retry: 0,
  });

  const header = (
    <SectionHeader
      icon={<Euro size={14} />}
      title="ROI de acções de qualidade"
      subtitle="ROIService · investido vs poupado por código de erro"
    />
  );

  if (roiQuery.isLoading) {
    return (
      <Card padding={20}>
        {header}
        <LoadingLine />
      </Card>
    );
  }

  if (roiQuery.isError || !roiQuery.data) {
    return (
      <Card padding={20}>
        {header}
        <EmptyState
          title="ROI de qualidade indisponível"
          hint="O endpoint /v1/quality/roi-actions não respondeu. O custo de retrabalho real está no cartão acima."
        />
      </Card>
    );
  }

  const data = roiQuery.data;
  const actions = data.actions;

  if (actions.length === 0) {
    return (
      <Card padding={20}>
        {header}
        <EmptyState
          size="sm"
          title="Sem acções de qualidade para avaliar"
          hint="Não há registos de retrabalho na janela para calcular retorno."
        />
      </Card>
    );
  }

  const netTotal = data.total_saved_eur - data.total_invested_eur;

  return (
    <Card padding={20}>
      {header}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 12,
          marginBottom: 14,
        }}
      >
        <KpiTile
          label="Poupado (total)"
          value={`€${Math.round(data.total_saved_eur).toLocaleString('pt-PT')}`}
          tone="green"
        />
        <KpiTile
          label="Investido (total)"
          value={`€${Math.round(data.total_invested_eur).toLocaleString('pt-PT')}`}
          tone="red"
        />
        <KpiTile
          label="Retorno líquido"
          value={`€${Math.round(netTotal).toLocaleString('pt-PT')}`}
          tone={netTotal >= 0 ? 'green' : 'red'}
        />
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.4fr 90px 110px 110px 90px',
          padding: '10px 6px',
          borderBottom: '1px solid var(--bd-1)',
          background: 'var(--bg-2)',
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
        }}
      >
        <div>Código de erro</div>
        <div style={{ textAlign: 'right' }}>Eventos</div>
        <div style={{ textAlign: 'right' }}>Poupado</div>
        <div style={{ textAlign: 'right' }}>Investido</div>
        <div style={{ textAlign: 'right' }}>ROI</div>
      </div>
      {actions.map((a, i, arr) => {
        const tone =
          a.net_eur > 0 ? 'green' : a.net_eur < 0 ? 'red' : 'fg-2';
        return (
          <div
            key={a.error_code}
            style={{
              display: 'grid',
              gridTemplateColumns: '1.4fr 90px 110px 110px 90px',
              alignItems: 'center',
              padding: '11px 6px',
              borderBottom:
                i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
              fontSize: 12,
            }}
          >
            <span style={{ color: 'var(--fg-0)' }}>
              <span style={{ fontWeight: 500 }}>{a.error_code}</span>
              <span
                style={{
                  fontSize: 10.5,
                  color: 'var(--fg-3)',
                  marginLeft: 8,
                }}
              >
                {a.action_basis === 'fixed_corrective_action'
                  ? 'acção correctiva'
                  : 'esforço de reacção'}
              </span>
            </span>
            <span
              className="tabular"
              style={{ color: 'var(--fg-2)', textAlign: 'right' }}
            >
              {a.events}
            </span>
            <span
              className="tabular"
              style={{ color: 'var(--green)', textAlign: 'right' }}
            >
              €{Math.round(a.saved_eur).toLocaleString('pt-PT')}
            </span>
            <span
              className="tabular"
              style={{ color: 'var(--red)', textAlign: 'right' }}
            >
              €{Math.round(a.invested_eur).toLocaleString('pt-PT')}
            </span>
            <span
              className="tabular"
              style={{
                color: `var(--${tone})`,
                fontWeight: 600,
                textAlign: 'right',
              }}
            >
              {a.roi_ratio !== null ? `${a.roi_ratio.toFixed(1)}×` : '—'}
            </span>
          </div>
        );
      })}
    </Card>
  );
}

// ─── Helpers de UI ───────────────────────────────────────────────────────

export function LoadingLine() {
  return (
    <div
      style={{
        padding: '20px 0',
        textAlign: 'center',
        color: 'var(--fg-3)',
        fontSize: 12,
      }}
    >
      A carregar…
    </div>
  );
}

export function KpiTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'red' | 'green' | 'neutral';
}) {
  const color =
    tone === 'red'
      ? 'var(--red)'
      : tone === 'green'
        ? 'var(--green)'
        : 'var(--fg-0)';
  return (
    <div
      style={{
        padding: 14,
        background: 'var(--bg-2)',
        borderRadius: 'var(--r-md)',
        border: '1px solid var(--bd-1)',
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
        }}
      >
        {label}
      </div>
      <div
        className="tabular display"
        style={{
          fontSize: 22,
          color,
          fontWeight: 600,
          marginTop: 6,
        }}
      >
        {value}
      </div>
    </div>
  );
}

export const ZONE_GEOMETRY: Record<
  HullZoneId,
  { label: string; x: number; y: number; w: number; h: number }
> = {
  casco: { label: 'Casco', x: 70, y: 30, w: 78, h: 26 },
  conves: { label: 'Convés', x: 152, y: 30, w: 70, h: 11 },
  cockpit: { label: 'Cockpit', x: 152, y: 44, w: 70, h: 12 },
  interior: { label: 'Interior', x: 226, y: 30, w: 64, h: 26 },
  acabamento: { label: 'Acabamento', x: 294, y: 30, w: 56, h: 26 },
  molde: { label: 'Molde', x: 28, y: 30, w: 38, h: 26 },
  montagem: { label: 'Montagem', x: 354, y: 32, w: 30, h: 22 },
  outro: { label: 'Outro', x: 152, y: 58, w: 70, h: 0 },
};

export const REWORK_ERROR_CODES = [
  { code: 'RESIN_BUBBLE', label: 'Bolha na resina' },
  { code: 'PAINT_SCRATCH', label: 'Risco na pintura' },
  { code: 'COLAGEM_FAIL', label: 'Falha na colagem' },
  { code: 'LAMINATE_DEFECT', label: 'Defeito de laminagem' },
  { code: 'DIMENSION_OFF', label: 'Dimensão fora de tolerância' },
  { code: 'OTHER', label: 'Outro' },
];

export const ROOT_CAUSE_CATEGORIES = [
  'Erro de operador',
  'Molde danificado',
  'Material defeituoso',
  'Procedimento incorreto',
  'Equipamento',
  'Outro',
];

export const FIELD_CLASS =
  'mt-1 w-full px-3 py-2 rounded-md text-sm outline-none ' +
  'text-slate-900 placeholder:text-slate-400';

export const FIELD_STYLE = {
  background: '#f1f5f9',
  border: '1px solid var(--bd-2)',
} as const;
