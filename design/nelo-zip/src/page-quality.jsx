/* ─── Página: Qualidade ──────────────────────────────────────────── */

const PageQuality = () => (
  <UI.Page
    icon={<I.Shield size={20} />}
    title="Qualidade & Defeitos"
    subtitle="Erros recentes · estado dos moldes · padrões aprendidos"
  >
    {/* KPI strip */}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 22 }}>
      <UI.KPICard label="Taxa de defeito" value="2,1" unit="%" context="48 erros em 2.270 operações esta semana" target="2,0%" trend={-0.4} status="green" />
      <UI.KPICard label="Retrabalho" value="49" unit="%" context="Lixagem água · 88% dos retrabalhos" target="35%" trend={2.1} status="red" />
      <UI.KPICard label="Custo retrabalho" value={PP.fmtEuro(680)} context="Esta semana · sobretudo Lixagem" status="yellow" />
      <UI.KPICard label="CQ Final — pass" value="99,1" unit="%" context="2 barcos para revisão ligeira" target="99%" status="green" />
    </div>

    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 22 }}>
      {/* Erros recentes */}
      <UI.Card padding={0}>
        <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--bd-1)' }}>
          <UI.CardHeader icon={<I.Alert size={16} />} accent="orange" title="Erros recentes" subtitle="Últimas 24h · ordenados por gravidade" />
        </div>
        <div>
          {PP.RECENT_ERRORS.map((e, i) => (
            <div key={i} style={{
              padding: '12px 22px',
              borderBottom: i < PP.RECENT_ERRORS.length - 1 ? '1px solid var(--bd-1)' : 'none',
              display: 'flex', alignItems: 'center', gap: 14,
            }}>
              <UI.SevBadge severity={e.severity} size="sm" />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, color: 'var(--fg-0)', fontWeight: 500 }}>{e.boat} · {e.defect}</div>
                <div style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 2 }}>{e.phase} · {e.worker}</div>
              </div>
              <UI.Button variant="ghost" size="sm" icon={<I.Eye size={12} />}>Ver</UI.Button>
            </div>
          ))}
        </div>
      </UI.Card>

      {/* Moldes */}
      <UI.Card padding={0}>
        <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--bd-1)' }}>
          <UI.CardHeader icon={<I.Boxes size={16} />} accent="blue" title="Estado dos moldes" subtitle="Usos vs limite recomendado · 800 ciclos" />
        </div>
        <div>
          {PP.MOLDS.map((m, i) => {
            const pct = (m.uses / m.max) * 100;
            const tone = pct >= 100 ? 'red' : pct >= 80 ? 'yellow' : 'green';
            return (
              <div key={m.id} style={{
                padding: '12px 22px',
                borderBottom: i < PP.MOLDS.length - 1 ? '1px solid var(--bd-1)' : 'none',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-0)' }}>{m.name}</span>
                  <span className="tabular" style={{ fontSize: 12, color: UI.colorVar(tone) }}>
                    {m.uses}/{m.max}
                  </span>
                </div>
                <div style={{ height: 4, background: 'var(--bg-3)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', background: UI.colorVar(tone) }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--fg-2)', marginTop: 5 }}>
                  <span>Erro: <span className="tabular" style={{ color: UI.colorVar(tone), fontWeight: 600 }}>{(m.err_week*100).toFixed(0)}%</span> esta semana <span style={{ color: 'var(--fg-3)' }}>(normal {(m.err_normal*100).toFixed(0)}%)</span></span>
                  {m.status === 'critical' && <span style={{ color: 'var(--red)' }}>● Manutenção</span>}
                </div>
              </div>
            );
          })}
        </div>
      </UI.Card>
    </div>
  </UI.Page>
);

window.PageQuality = PageQuality;
