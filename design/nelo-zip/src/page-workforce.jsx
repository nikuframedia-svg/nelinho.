/* ─── Página: Operadores (Workforce) ─────────────────────────────── */

const PageWorkforce = () => (
  <UI.Page
    icon={<I.Workers size={20} />}
    title="Operadores"
    subtitle="Score, skills e taxa de erro · 8 operadores activos"
    actions={<UI.Button variant="secondary" size="sm" icon={<I.Plus size={13} />}>Adicionar operador</UI.Button>}
  >
    {/* Explainer */}
    <div style={{
      padding: '14px 18px',
      background: 'var(--bg-1)',
      border: '1px solid var(--bd-1)',
      borderRadius: 'var(--r-lg)',
      marginBottom: 22,
      fontSize: 13, color: 'var(--fg-1)', lineHeight: 1.6,
    }}>
      <strong style={{ color: 'var(--fg-0)' }}>Como o sistema mede operadores:</strong> O score 0–10 vem do histórico — taxa de erro, qualidade, tempo médio. <strong style={{ color: 'var(--fg-1)' }}>Não é uma avaliação humana</strong>, é o que ajuda o sistema a sugerir a melhor pessoa para cada barco. Operadores podem sempre ver e corrigir o seu próprio perfil.
    </div>

    {/* Strip */}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 22 }}>
      <UI.KPICard label="Operadores hoje" value="7/8" context="António P. de férias" status="green" />
      <UI.KPICard label="Score médio" value="7,2" context="Subiu 0,3 nos últimos 30 dias" trend={4.3} status="green" />
      <UI.KPICard label="Taxa de erro média" value="8,5" unit="%" context="Tier >12m: 4,8% · Tier <5m: 22,1%" status="yellow" />
      <UI.KPICard label="Cobertura crítica" value="2" context="Lixagem só tem Helena tier >12m" status="yellow" />
    </div>

    {/* Table */}
    <UI.Card padding={0}>
      <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--bd-1)' }}>
        <UI.SectionHeader title="Equipa" subtitle="Clique num operador para ver o detalhe completo" />
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: 'var(--bg-2)' }}>
            {['Operador', 'Tier', 'Score', 'Taxa erro', 'Operações', 'Skill principal', 'Estado', ''].map(h => (
              <th key={h} style={{
                padding: '10px 16px',
                textAlign: 'left',
                fontSize: 11, color: 'var(--fg-2)',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: 0.4,
                borderBottom: '1px solid var(--bd-1)',
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {PP.WORKERS.map((w, i) => {
            const tone = w.score >= 8 ? 'green' : w.score >= 6 ? 'blue' : w.score >= 4 ? 'yellow' : 'red';
            const errTone = w.err < 0.05 ? 'green' : w.err < 0.10 ? 'blue' : w.err < 0.18 ? 'yellow' : 'red';
            return (
              <tr key={w.id} style={{
                cursor: 'pointer',
                borderBottom: i < PP.WORKERS.length - 1 ? '1px solid var(--bd-1)' : 'none',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-2)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <td style={{ padding: '12px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <UI.WorkerAvatar worker={w} size={30} />
                    <span style={{ fontWeight: 500, color: 'var(--fg-0)' }}>{w.name}</span>
                  </div>
                </td>
                <td style={{ padding: '12px 16px', color: 'var(--fg-1)' }}>
                  <UI.Badge tone={w.tier === '>12m' ? 'green' : w.tier === '<12m' ? 'blue' : 'yellow'} size="sm">{w.tier}</UI.Badge>
                </td>
                <td style={{ padding: '12px 16px' }} className="tabular">
                  <span style={{ color: UI.colorVar(tone), fontWeight: 600 }}>★ {w.score.toFixed(1)}</span>
                </td>
                <td style={{ padding: '12px 16px' }} className="tabular">
                  <span style={{ color: UI.colorVar(errTone), fontWeight: 600 }}>{(w.err * 100).toFixed(1)}%</span>
                </td>
                <td style={{ padding: '12px 16px', color: 'var(--fg-1)' }} className="tabular">{w.ops.toLocaleString('pt-PT')}</td>
                <td style={{ padding: '12px 16px', color: 'var(--fg-1)' }}>{w.main}</td>
                <td style={{ padding: '12px 16px' }}>
                  {w.status === 'active' ? (
                    <span style={{ fontSize: 12, color: 'var(--green)' }}>● Activo</span>
                  ) : (
                    <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>○ Férias</span>
                  )}
                </td>
                <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                  <I.Chevron size={14} color="var(--fg-3)" />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </UI.Card>
  </UI.Page>
);

window.PageWorkforce = PageWorkforce;
