// QualidadePage · tab MapaTab (Q.60.Q). ZERO MOCKS — liga a endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { Layers } from 'lucide-react';
import { EmptyState } from '../../../components/dark';
import { Card, SectionHeader, MiniBar, HullHeatmap, type HullZone } from '../../../components/qualidade/QualidadeBits';
import { fetchDefectZones, type DefectZone } from '../../../components/qualidade/qualidadeApi';
import { LoadingLine, ZONE_GEOMETRY } from '../qualidadeShared';

export function MapaTab() {
  // Q.53.H — GET /v1/quality/defect-zones: agregação de retrabalho por
  // zona do casco. Sempre devolve as 8 zonas canónicas (count 0 quando
  // limpa), por isso o SVG renderiza o casco completo.
  const zonesQuery = useQuery({
    queryKey: ['qualidade', 'defect-zones'],
    queryFn: () => fetchDefectZones(),
    staleTime: 60_000,
    retry: 0,
  });

  const header = (
    <SectionHeader
      icon={<Layers size={14} />}
      title="Mapa de defeitos por zona do casco"
      subtitle="DefectZoneService · onde o defeito ocorre, não só quanto"
    />
  );

  if (zonesQuery.isLoading) {
    return (
      <Card padding={20}>
        {header}
        <LoadingLine />
      </Card>
    );
  }

  if (zonesQuery.isError || !zonesQuery.data) {
    return (
      <Card padding={20}>
        {header}
        <EmptyState
          title="Mapa do casco indisponível"
          hint="O endpoint /v1/quality/defect-zones não respondeu. Tenta atualizar dentro de momentos."
        />
      </Card>
    );
  }

  const data = zonesQuery.data;
  // O HullHeatmap só desenha as zonas com geometria posicionável; a zona
  // "outro" (sem localização no casco) é listada à parte na tabela.
  const heatmapZones: HullZone[] = data.zones
    .filter((z): z is DefectZone => z.zone in ZONE_GEOMETRY && z.zone !== 'outro')
    .map((z) => {
      const g = ZONE_GEOMETRY[z.zone];
      return {
        id: z.zone,
        label: g.label,
        x: g.x,
        y: g.y,
        w: g.w,
        h: g.h,
        count: z.events,
      };
    });

  const ranked = [...data.zones].sort((a, b) => b.events - a.events);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card padding={20}>
        {header}
        {data.total_events === 0 ? (
          <EmptyState
            size="sm"
            title="Sem defeitos registados na janela"
            hint="Não há eventos de retrabalho nos últimos 90 dias para mapear no casco."
          />
        ) : (
          <HullHeatmap zones={heatmapZones} />
        )}
      </Card>

      <Card padding={18}>
        <SectionHeader
          title="Defeitos por zona"
          subtitle={`${data.total_events} eventos · janela de ${new Date(
            data.window.from,
          ).toLocaleDateString('pt-PT')} a ${new Date(
            data.window.to,
          ).toLocaleDateString('pt-PT')}`}
        />
        {ranked.map((z, i, arr) => {
          const tone =
            z.share_pct > 30
              ? 'red'
              : z.share_pct > 15
                ? 'orange'
                : z.share_pct > 5
                  ? 'yellow'
                  : 'green';
          return (
            <div
              key={z.zone}
              style={{
                display: 'grid',
                gridTemplateColumns: '130px 1fr 70px 80px 70px',
                alignItems: 'center',
                gap: 14,
                padding: '9px 0',
                borderBottom:
                  i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
                fontSize: 12,
              }}
            >
              <span style={{ color: 'var(--fg-0)', fontWeight: 500 }}>
                {ZONE_GEOMETRY[z.zone]?.label ?? z.zone}
              </span>
              <MiniBar
                value={z.share_pct}
                max={60}
                color={`var(--${tone})`}
                height={5}
              />
              <span
                className="tabular"
                style={{ color: `var(--${tone})`, fontWeight: 600 }}
              >
                {z.share_pct.toFixed(1)}%
              </span>
              <span
                className="tabular"
                style={{ color: 'var(--red)', textAlign: 'right' }}
              >
                {z.cost_eur > 0 ? `−€${Math.round(z.cost_eur)}` : '—'}
              </span>
              <span
                className="tabular"
                style={{ color: 'var(--fg-2)', textAlign: 'right' }}
              >
                {z.events} ev.
              </span>
            </div>
          );
        })}
      </Card>
    </div>
  );
}

// ─── ErrosTab ────────────────────────────────────────────────────────────
