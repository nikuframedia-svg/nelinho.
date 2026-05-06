/* ─── Página: OEE ────────────────────────────────────────────────── */

const PageOEE = () => {
  return (
    <UI.Page
      icon={<I.Trending size={20} />}
      title="OEE — Eficácia da fábrica"
      subtitle="Disponibilidade × Performance × Qualidade · 14 dias"
      actions={<UI.Button variant="secondary" size="sm">Exportar</UI.Button>}
    >
      {/* What is OEE — explainer */}
      <div style={{
        padding: '14px 18px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        marginBottom: 22,
        fontSize: 13, color: 'var(--fg-1)', lineHeight: 1.6,
      }}>
        <strong style={{ color: 'var(--fg-0)' }}>O que é OEE?</strong> Mede que percentagem do tempo a fábrica está realmente a produzir bem. <strong>78%</strong> significa que de cada 8h de trabalho, 6h15 produzem barcos sem defeito.
        <span style={{ color: 'var(--fg-2)' }}> Meta NELO: 80%.</span>
      </div>

      {/* OEE breakdown — 3 grandes números */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr', gap: 14, marginBottom: 22 }}>
        <UI.Card>
          <UI.CardHeader title="OEE Global" subtitle="Hoje" />
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span className="tabular" style={{ fontSize: 56, fontWeight: 700, color: 'var(--yellow)', lineHeight: 1 }}>78,4</span>
            <span style={{ fontSize: 18, color: 'var(--fg-2)' }}>%</span>
            <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--green)' }}>↑ 2,3% vs ontem</span>
          </div>
          <div style={{ marginTop: 12, height: 60 }}>
            <UI.Sparkline data={PP.THROUGHPUT_14D.map(v => 70 + v / 5)} color="var(--yellow)" height={60} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
            <span>14 dias atrás</span>
            <span>Hoje</span>
          </div>
        </UI.Card>

        <OEEBlock label="Disponibilidade" value="92" target="95" tone="yellow" detail="Tempo a produzir vs tempo planeado" loss="32min de paragem não planeada (molde K1 7 ML)" />
        <OEEBlock label="Performance" value="86" target="90" tone="yellow" detail="Velocidade real vs velocidade ideal" loss="Lixagem mais lenta — fila de 22 barcos" />
        <OEEBlock label="Qualidade" value="99,1" target="99" tone="green" detail="Barcos bons vs total produzido" loss="2 barcos para retrabalho ligeiro" />
      </div>

      {/* Throughput chart + financial impact */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 22 }}>
        <UI.Card>
          <UI.CardHeader title="Throughput diário" subtitle="Barcos completados por dia · últimos 14 dias" />
          <ThroughputChart data={PP.THROUGHPUT_14D} target={30} />
        </UI.Card>

        <UI.Card>
          <UI.CardHeader title="Impacto financeiro" subtitle="Custo das perdas de OEE" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[
              { label: 'Paragem por molde',   value: 1280, color: 'red' },
              { label: 'Lentidão Lixagem',    value: 2400, color: 'yellow' },
              { label: 'Retrabalho qualidade',value: 680,  color: 'yellow' },
              { label: 'Setup excessivo',     value: 420,  color: 'blue' },
            ].map(r => (
              <div key={r.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--fg-1)', marginBottom: 4 }}>
                  <span>{r.label}</span>
                  <span className="tabular" style={{ fontWeight: 600 }}>{PP.fmtEuro(r.value)}</span>
                </div>
                <div style={{ height: 4, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: `${(r.value / 2400) * 100}%`, height: '100%', background: UI.colorVar(r.color) }} />
                </div>
              </div>
            ))}
            <div style={{ marginTop: 6, paddingTop: 12, borderTop: '1px solid var(--bd-1)', display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 12, color: 'var(--fg-1)', fontWeight: 600 }}>Total perdido / semana</span>
              <span className="tabular" style={{ fontSize: 14, color: 'var(--red)', fontWeight: 700 }}>{PP.fmtEuro(4780)}</span>
            </div>
          </div>
        </UI.Card>
      </div>
    </UI.Page>
  );
};

const OEEBlock = ({ label, value, target, tone, detail, loss }) => (
  <UI.Card>
    <div style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: 0.4, fontWeight: 600 }}>{label}</div>
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginTop: 8 }}>
      <span className="tabular" style={{ fontSize: 32, fontWeight: 700, color: UI.colorVar(tone), lineHeight: 1 }}>{value}</span>
      <span style={{ fontSize: 14, color: 'var(--fg-2)' }}>%</span>
    </div>
    <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>Meta: {target}%</div>
    <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 10, lineHeight: 1.4 }}>{detail}</div>
    {loss && (
      <div style={{
        marginTop: 10, padding: '8px 10px',
        background: 'var(--bg-2)', borderRadius: 'var(--r-sm)',
        fontSize: 11, color: 'var(--fg-1)',
        borderLeft: `2px solid ${UI.colorVar(tone)}`,
      }}>
        <strong style={{ color: 'var(--fg-2)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.4 }}>Maior perda:</strong>
        <div style={{ marginTop: 2 }}>{loss}</div>
      </div>
    )}
  </UI.Card>
);

const ThroughputChart = ({ data, target }) => {
  const w = 600, h = 200, pad = { l: 32, r: 12, t: 12, b: 28 };
  const cw = w - pad.l - pad.r, ch = h - pad.t - pad.b;
  const max = Math.max(...data, target) * 1.1;
  const dx = cw / (data.length - 1);
  return (
    <div style={{ marginTop: 6 }}>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 200 }}>
        {/* grid */}
        {[0, 0.25, 0.5, 0.75, 1].map(t => (
          <line key={t} x1={pad.l} x2={w - pad.r} y1={pad.t + ch * (1 - t)} y2={pad.t + ch * (1 - t)}
                stroke="var(--bd-1)" strokeDasharray={t === 0 ? '0' : '2 3'} />
        ))}
        {[0, 0.25, 0.5, 0.75, 1].map(t => (
          <text key={t} x={pad.l - 6} y={pad.t + ch * (1 - t) + 3} fontSize="9" fill="var(--fg-3)" textAnchor="end">
            {Math.round(max * t)}
          </text>
        ))}
        {/* target line */}
        <line x1={pad.l} x2={w - pad.r} y1={pad.t + ch * (1 - target / max)} y2={pad.t + ch * (1 - target / max)}
              stroke="var(--green)" strokeWidth="1.2" strokeDasharray="3 3" />
        <text x={w - pad.r - 4} y={pad.t + ch * (1 - target / max) - 4} fontSize="9" fill="var(--green)" textAnchor="end">Meta {target}</text>
        {/* line */}
        <path
          d={data.map((v, i) => `${i === 0 ? 'M' : 'L'} ${pad.l + i * dx} ${pad.t + ch * (1 - v / max)}`).join(' ')}
          fill="none" stroke="var(--blue)" strokeWidth="2"
        />
        {/* dots */}
        {data.map((v, i) => (
          <circle key={i} cx={pad.l + i * dx} cy={pad.t + ch * (1 - v / max)} r="3" fill="var(--blue)" />
        ))}
        {/* x-axis */}
        {data.map((_, i) => i % 2 === 0 && (
          <text key={i} x={pad.l + i * dx} y={h - 8} fontSize="9" fill="var(--fg-3)" textAnchor="middle">D−{data.length - 1 - i}</text>
        ))}
      </svg>
    </div>
  );
};

window.PageOEE = PageOEE;
