/* ─── Páginas: Expedição, Aprendizagem, Definições ───────────────── */

/* ─── Expedições ─────────────────────────────────────────────── */
const PageShipments = () => (
  <UI.Page
    icon={<I.Truck size={20} />}
    title="Expedições"
    subtitle="Calendário de saídas · estado dos camiões"
    actions={<UI.Button variant="primary" tone="blue" size="sm" icon={<I.Plus size={13} />}>Nova expedição</UI.Button>}
  >
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 22 }}>
      <UI.KPICard label="Próxima expedição" value="3" unit="dias" context="Sexta-feira · 50 barcos para FR + PT" status="yellow" />
      <UI.KPICard label="Prontos em armazém" value="48" context="42 sexta · 4 quarta · 2 já entregues" status="green" />
      <UI.KPICard label="Em risco" value="2" context="K1 #4275 (Lixagem) · K4 #6002 (Pintura)" status="yellow" />
    </div>

    <UI.SectionHeader title="Calendário das próximas 4 semanas" subtitle="Cada cartão é uma expedição agendada com cliente" />
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {PP.SHIPMENTS.map(s => <ShipmentDetail key={s.date} shipment={s} />)}
    </div>
  </UI.Page>
);

const ShipmentDetail = ({ shipment: s }) => {
  const pct = (s.ready / s.total) * 100;
  const tone = s.at_risk > 0 ? 'yellow' : pct === 100 ? 'green' : 'blue';
  return (
    <UI.Card>
      <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr 220px', gap: 22, alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: 0.4 }}>{s.day}</div>
          <div className="tabular" style={{ fontSize: 22, fontWeight: 700, color: 'var(--fg-0)', marginTop: 2 }}>
            {s.date.slice(8,10)}/{s.date.slice(5,7)}
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-1)', marginTop: 4 }}>{s.client}</div>
        </div>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-0)' }}>Estado dos {s.total} barcos</span>
            <span className="tabular" style={{ fontSize: 14, color: UI.colorVar(tone), fontWeight: 700 }}>
              {s.ready}/{s.total} prontos
            </span>
          </div>
          <div style={{ height: 6, background: 'var(--bg-3)', borderRadius: 3, overflow: 'hidden', display: 'flex' }}>
            <div style={{ width: `${pct}%`, background: 'var(--green)' }} />
            {s.in_prod > 0 && <div style={{ width: `${(s.in_prod/s.total)*100}%`, background: 'var(--blue)' }} />}
            {s.at_risk > 0 && <div style={{ width: `${(s.at_risk/s.total)*100}%`, background: 'var(--yellow)' }} />}
          </div>
          <div style={{ display: 'flex', gap: 14, marginTop: 8, fontSize: 11, color: 'var(--fg-2)' }}>
            <span>● <span style={{ color: 'var(--green)' }}>{s.ready} prontos</span></span>
            {s.in_prod > 0 && <span>● <span style={{ color: 'var(--blue)' }}>{s.in_prod} em produção</span></span>}
            {s.at_risk > 0 && <span>● <span style={{ color: 'var(--yellow)' }}>{s.at_risk} em risco</span></span>}
          </div>
          {s.suggestion && (
            <div style={{
              marginTop: 12, padding: '10px 12px',
              background: 'var(--blue-bg)', border: '1px solid var(--blue-bd)',
              borderRadius: 'var(--r-md)',
              fontSize: 12, color: 'var(--fg-1)',
              display: 'flex', gap: 8, alignItems: 'flex-start',
            }}>
              <I.Sparkles size={14} color="var(--blue)" style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{s.suggestion}</span>
            </div>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <UI.Button variant="secondary" size="sm" fullWidth>Ver barcos</UI.Button>
          <UI.Button variant="ghost" size="sm" fullWidth>Documentos</UI.Button>
        </div>
      </div>
    </UI.Card>
  );
};

/* ─── O que aprendi ──────────────────────────────────────────── */
const PageLearning = () => (
  <UI.Page
    icon={<I.Brain size={20} />}
    title="O que aprendi"
    subtitle="Padrões, regras e pesos que o sistema descobriu observando-o decidir"
  >
    <div style={{
      padding: '14px 18px',
      background: 'var(--bg-1)',
      border: '1px solid var(--bd-1)',
      borderRadius: 'var(--r-lg)',
      marginBottom: 22,
      fontSize: 13, color: 'var(--fg-1)', lineHeight: 1.6,
    }}>
      <strong style={{ color: 'var(--fg-0)' }}>Transparência total.</strong> Tudo o que o sistema aprendeu está aqui. Pode <strong>aprovar</strong>, <strong>rejeitar</strong>, ou <strong>pausar</strong> qualquer regra. Nada é mágico, nada é caixa-preta.
    </div>

    <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 22 }}>
      {/* Regras */}
      <UI.Card padding={0}>
        <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--bd-1)' }}>
          <UI.CardHeader title="Regras aprendidas" subtitle="Padrões observados nas suas decisões" />
        </div>
        <div>
          {PP.LEARNED_RULES.map((r, i) => (
            <div key={r.id} style={{
              padding: '16px 22px',
              borderBottom: i < PP.LEARNED_RULES.length - 1 ? '1px solid var(--bd-1)' : 'none',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                    <UI.Badge tone={r.status === 'active' ? 'green' : 'yellow'} size="sm" glyph={r.status === 'active' ? '●' : '◆'}>
                      {r.status === 'active' ? 'Activa' : 'Sugerida'}
                    </UI.Badge>
                    <span className="tabular" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
                      Confiança {(r.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div style={{ fontSize: 14, color: 'var(--fg-0)', fontWeight: 500, lineHeight: 1.4 }}>{r.text}</div>
                  <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 4 }}>Base: {r.basis}</div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  {r.status === 'suggested' ? (
                    <>
                      <UI.Button variant="primary" tone="green" size="sm" icon={<I.Check size={12} />}>Aprovar</UI.Button>
                      <UI.Button variant="ghost" size="sm" icon={<I.X size={12} />}>Recusar</UI.Button>
                    </>
                  ) : (
                    <UI.Button variant="ghost" size="sm" icon={<I.Pause size={12} />}>Pausar</UI.Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </UI.Card>

      {/* Pesos */}
      <UI.Card>
        <UI.CardHeader title="Pesos da fitness" subtitle="Como o sistema pondera cada objectivo" />
        <div style={{ fontSize: 11, color: 'var(--fg-2)', marginBottom: 14, lineHeight: 1.5 }}>
          <strong style={{ color: 'var(--fg-1)' }}>Default</strong> = padrão NELO. <strong style={{ color: 'var(--blue)' }}>Aprendido</strong> = ajustado pelas suas decisões.
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {PP.FITNESS_WEIGHTS.map(w => (
            <div key={w.key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 5 }}>
                <span style={{ color: 'var(--fg-1)' }}>{w.key}</span>
                <span className="tabular" style={{ color: 'var(--fg-2)' }}>
                  {(w.default * 100).toFixed(0)} → <span style={{ color: 'var(--blue)', fontWeight: 600 }}>{(w.learned * 100).toFixed(0)}%</span>
                </span>
              </div>
              <div style={{ position: 'relative', height: 6, background: 'var(--bg-3)', borderRadius: 3 }}>
                <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${w.default * 100 * 2.5}%`, background: 'var(--bd-2)', borderRadius: 3 }} />
                <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${w.learned * 100 * 2.5}%`, background: 'var(--blue)', borderRadius: 3 }} />
              </div>
            </div>
          ))}
        </div>
      </UI.Card>
    </div>
  </UI.Page>
);

/* ─── Definições ──────────────────────────────────────────────── */
const PageSettings = () => (
  <UI.Page icon={<I.Settings size={20} />} title="Definições" subtitle="Sistema, segurança, integrações">
    <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 22 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {[
          { id: 'profile', label: 'Perfil', icon: <I.User size={14} /> },
          { id: 'security', label: 'Segurança', icon: <I.Lock size={14} /> },
          { id: 'data', label: 'Dados & ingestão', icon: <I.Database size={14} /> },
          { id: 'audit', label: 'Auditoria', icon: <I.Shield size={14} /> },
          { id: 'integrations', label: 'Integrações', icon: <I.Zap size={14} /> },
        ].map((it, i) => (
          <button key={it.id} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 14px',
            background: i === 0 ? 'var(--bg-2)' : 'transparent',
            border: i === 0 ? '1px solid var(--bd-1)' : '1px solid transparent',
            borderRadius: 'var(--r-md)',
            color: i === 0 ? 'var(--fg-0)' : 'var(--fg-1)',
            cursor: 'pointer', textAlign: 'left',
            fontSize: 13,
          }}>
            <span style={{ color: 'var(--fg-2)' }}>{it.icon}</span>
            {it.label}
          </button>
        ))}
      </div>
      <UI.Card>
        <UI.SectionHeader title="Perfil" subtitle="Os seus dados e preferências" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 420 }}>
          <Field label="Nome" value="Nuno Ferreira" />
          <Field label="Email" value="nuno@nelo.pt" />
          <Field label="Função" value="Direção" />
          <Field label="Idioma" value="Português" />
          <div style={{ marginTop: 8 }}>
            <UI.Button variant="primary" tone="blue" size="md">Guardar alterações</UI.Button>
          </div>
        </div>
      </UI.Card>
    </div>
  </UI.Page>
);

const Field = ({ label, value }) => (
  <div>
    <div style={{ fontSize: 11, color: 'var(--fg-2)', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6 }}>{label}</div>
    <input defaultValue={value} style={{
      width: '100%',
      padding: '9px 12px',
      background: 'var(--bg-2)',
      border: '1px solid var(--bd-1)',
      borderRadius: 'var(--r-md)',
      color: 'var(--fg-0)',
      fontSize: 13,
      outline: 'none',
    }} />
  </div>
);

window.PageShipments = PageShipments;
window.PageLearning = PageLearning;
window.PageSettings = PageSettings;
