// ConfiguracaoPage · CustosTab (Q.60.U). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { Euro, Loader2, Zap } from 'lucide-react';
import { EmptyState } from '../../../components/dark';
import { ratesApi } from '../../../lib/api';
import { ConfigCard, SectionHeader, type RateRow, rateValue, unwrapList } from '../configuracaoShared';

export function CustosTab() {
  const laborQ = useQuery({
    queryKey: ['rates', 'labor'],
    queryFn: () => ratesApi.laborRates.list(),
    staleTime: 60_000,
    retry: false,
  });
  const machineQ = useQuery({
    queryKey: ['rates', 'machine'],
    queryFn: () => ratesApi.machineRates.list(),
    staleTime: 60_000,
    retry: false,
  });
  const overheadQ = useQuery({
    queryKey: ['rates', 'overhead'],
    queryFn: () => ratesApi.overheadRates.list(),
    staleTime: 60_000,
    retry: false,
  });
  const labor = unwrapList<RateRow>(laborQ.data);
  const machine = unwrapList<RateRow>(machineQ.data);
  const overhead = unwrapList<RateRow>(overheadQ.data);

  const rateGroups: Array<{ title: string; rows: RateRow[]; loading: boolean }> = [
    { title: 'Mão de obra (€/hora)', rows: labor, loading: laborQ.isLoading },
    { title: 'Máquina (€/hora)', rows: machine, loading: machineQ.isLoading },
    { title: 'Overhead', rows: overhead, loading: overheadQ.isLoading },
  ];

  return (
    <div className="space-y-3.5">
      {rateGroups.map((g) => (
        <ConfigCard key={g.title}>
          <div
            style={{
              padding: '14px 18px',
              borderBottom: '1px solid var(--bd-1)',
            }}
          >
            <SectionHeader
              icon={<Euro size={14} />}
              title={g.title}
              subtitle="core.*_rates · cada valor com data efectiva"
            />
          </div>
          <div className="p-[18px]">
            {g.loading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 size={20} className="text-accent-500 animate-spin" />
              </div>
            ) : g.rows.length === 0 ? (
              <EmptyState
                  title="Sem tarifas registadas"
                hint="Adiciona tarifas em Configuração → Dados-mestre. As tarifas alimentam o cálculo de COGS por barco."
              />
            ) : (
              <div className="space-y-1">
                {g.rows.map((r, i) => {
                  const v = rateValue(r);
                  return (
                    <div
                      key={r.id ?? i}
                      className="grid grid-cols-[1fr_120px_120px] items-center gap-3 py-2 text-[12px]"
                      style={{
                        borderBottom:
                          i < g.rows.length - 1
                            ? '1px solid var(--bd-1)'
                            : 'none',
                      }}
                    >
                      <span className="text-text-dark-secondary">
                        {r.phase ??
                          r.phase_code ??
                          r.machine_code ??
                          r.category ??
                          '—'}
                      </span>
                      <span className="tabular-nums text-text-dark-primary font-semibold text-right">
                        {v !== null ? `€${v.toFixed(2)}` : '—'}
                      </span>
                      <span className="text-text-dark-tertiary text-[10.5px] text-right">
                        {r.effective_date ?? r.updated_at ?? ''}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </ConfigCard>
      ))}

      <ConfigCard>
        <div
          style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}
        >
          <SectionHeader
            icon={<Zap size={14} />}
            title="Energia real vs standard"
            subtitle="IOT_SENSOR_DATA · potência trifásica por fase"
          />
        </div>
        <div className="p-[18px]">
          {/* Q.58.A — não há endpoint nem fonte de dados de energia (o
              backend nunca expôs `/v1/profit/energy/real`). Em vez de uma
              `useQuery` que batia sempre num 404, mostramos o estado
              honesto directamente. Quando a NELO ligar sensores IOT de
              potência, religa-se aqui a query ao endpoint real. */}
          <EmptyState
            title="Medição de energia não disponível"
            hint="A NELO ainda não tem sensores IOT de potência trifásica ligados. Quando houver leituras por fase, o consumo real vs standard aparece aqui."
          />
        </div>
      </ConfigCard>
    </div>
  );
}

// ═══ Tab Cura/Secagem ════════════════════════════════════════════════════════
