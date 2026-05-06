/* ─── Página: Direção (CEO Dashboard) ────────────────────────────── */

const PageCEO = ({ onNavigate, onOpenCopilot }) => {
  const onTime = PP.BOATS.filter(b => b.status === 'on_time').length;
  const atRisk = PP.BOATS.filter(b => b.status === 'at_risk').length;
  const late   = PP.BOATS.filter(b => b.status === 'late').length;
  const totalActive = PP.BOATS.length;

  return (
    <UI.Page
      icon={<I.Building size={20} />}
      title="Bom dia, Nuno."
      subtitle="Resumo do dia · Quarta, 12 de Maio"
      actions={
        <>
          <UI.Button variant="secondary" size="sm" icon={<I.Refresh size={13} />}>Actualizar</UI.Button>
          <UI.Button variant="primary" tone="blue" size="sm" icon={<I.Sparkles size={13} />} onClick={onOpenCopilot}>
            3 sugestões
          </UI.Button>
        </>
      }
    >
      {/* Hero — 1 frase em destaque */}
      <div style={{
        padding: '22px 26px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        marginBottom: 22,
        display: 'flex', alignItems: 'center', gap: 18,
      }}>
        <div style={{
          width: 44, height: 44, borderRadius: 'var(--r-md)',
          background: 'var(--green-bg)', border: '1px solid var(--green-bd)',
          color: 'var(--green)',
          display: 'grid', placeItems: 'center', flexShrink: 0,
        }}>
          <I.Check size={22} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 18, fontWeight: 500, color: 'var(--fg-0)', lineHeight: 1.4 }}>
            A fábrica está <span style={{ color: 'var(--green)' }}>no plano</span>. Vamos cumprir a expedição de sexta com <span style={{ color: 'var(--fg-0)', fontWeight: 600 }}>2 barcos em risco</span>.
          </div>
          <div style={{ fontSize: 13, color: 'var(--fg-2)', marginTop: 6 }}>
            48 dos 50 barcos prontos. K1 #4275 (Lixagem) está atrasado 7 dias e K4 #6002 (Pintura) está em risco. Há 3 sugestões a aguardar a sua decisão.
          </div>
        </div>
        <UI.Button variant="tonal" tone="blue" onClick={onOpenCopilot} icon={<I.ArrowRight size={14} />}>
          Ver detalhe
        </UI.Button>
      </div>

      {/* KPIs — só 4, com contexto */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 14,
        marginBottom: 24,
      }}>
        <UI.KPICard
          label="Barcos em produção"
          value={totalActive}
          context={`${onTime} no prazo · ${atRisk} em risco · ${late} atrasados`}
          status={late > 0 ? 'yellow' : 'green'}
          onClick={() => onNavigate('scheduling')}
        />
        <UI.KPICard
          label="OEE da fábrica"
          value="78,4"
          unit="%"
          context="Disponibilidade 92% · Performance 86% · Qualidade 99%"
          target="80%"
          trend={2.3}
          status="yellow"
          sparkline={PP.THROUGHPUT_14D.map(v => v / 33)}
          onClick={() => onNavigate('oee')}
        />
        <UI.KPICard
          label="Throughput hoje"
          value="32"
          unit="barcos/dia"
          context="Média 14 dias: 29,4 barcos/dia · +9% acima"
          target="30"
          trend={5.1}
          status="green"
          sparkline={PP.THROUGHPUT_14D}
          onClick={() => onNavigate('oee')}
        />
        <UI.KPICard
          label="Margem por barco"
          value={PP.fmtEuroK(2400)}
          context="Custo médio €18,2K · Preço médio €20,6K"
          target="€2,5K"
          trend={-1.4}
          status="yellow"
          onClick={() => onNavigate('oee')}
        />
      </div>

      {/* Two-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 22 }}>
        {/* Left: alertas */}
        <UI.Card>
          <UI.CardHeader
            icon={<I.Alert size={16} />}
            accent="orange"
            title="Atenção necessária"
            subtitle="3 alertas activos · ordenados por urgência"
            actions={
              <UI.Button variant="ghost" size="sm" onClick={() => onNavigate('inbox')} icon={<I.ArrowRight size={13} />}>Ver inbox</UI.Button>
            }
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {PP.ALERTS.map(a => (
              <AlertCard key={a.id} alert={a} />
            ))}
          </div>
        </UI.Card>

        {/* Right: expedição */}
        <UI.Card>
          <UI.CardHeader
            icon={<I.Truck size={16} />}
            accent="blue"
            title="Próximas expedições"
            subtitle="Estado dos próximos camiões"
            actions={
              <UI.Button variant="ghost" size="sm" onClick={() => onNavigate('shipments')} icon={<I.ArrowRight size={13} />}>Ver tudo</UI.Button>
            }
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {PP.SHIPMENTS.map(s => <ShipmentRow key={s.date} shipment={s} />)}
          </div>
        </UI.Card>
      </div>

      {/* Bottom: how the system is helping */}
      <div style={{ marginTop: 22 }}>
        <UI.Card padding={0}>
          <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--bd-1)' }}>
            <UI.CardHeader
              icon={<I.Brain size={16} />}
              accent="purple"
              title="O que o sistema fez por si esta semana"
              subtitle="O assistente é uma proposta — você decide sempre"
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)' }}>
            {[
              { value: '47', label: 'Sugestões geradas', sub: 'Plano, atribuição, qualidade' },
              { value: '38', label: 'Aceites por si', sub: '81% — boa concordância' },
              { value: '9',  label: 'Rejeitadas',     sub: 'O sistema aprendeu com cada uma' },
              { value: '€18,2K', label: 'Poupança estimada', sub: 'Menos retrabalho + setup' },
            ].map((s, i) => (
              <div key={i} style={{
                padding: '20px 22px',
                borderRight: i < 3 ? '1px solid var(--bd-1)' : 'none',
              }}>
                <div className="tabular" style={{ fontSize: 28, fontWeight: 700, color: 'var(--fg-0)', lineHeight: 1 }}>{s.value}</div>
                <div style={{ fontSize: 12, color: 'var(--fg-1)', marginTop: 6, fontWeight: 500 }}>{s.label}</div>
                <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 3 }}>{s.sub}</div>
              </div>
            ))}
          </div>
        </UI.Card>
      </div>
    </UI.Page>
  );
};

/* ─── AlertCard — used in CEO dashboard ────────────────────────── */
const AlertCard = ({ alert }) => {
  const sev = UI.SEV[alert.severity] || UI.SEV.low;
  return (
    <div style={{
      padding: '14px 16px',
      background: 'var(--bg-2)',
      border: '1px solid var(--bd-1)',
      borderLeft: `3px solid ${UI.colorVar(sev.color)}`,
      borderRadius: 'var(--r-md)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <UI.SevBadge severity={alert.severity} size="sm" />
          <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>{alert.when}</span>
        </div>
      </div>
      <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--fg-0)' }}>{alert.title}</div>
      <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 4 }}>{alert.detail}</div>
      {alert.cause && (
        <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 6, paddingLeft: 12, borderLeft: '2px solid var(--bd-2)' }}>
          <strong style={{ color: 'var(--fg-1)' }}>Causa:</strong> {alert.cause}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        {alert.primary && (
          <UI.Button variant="tonal" tone={sev.color === 'red' ? 'red' : 'blue'} size="sm">
            {alert.primary.label}
          </UI.Button>
        )}
        {alert.secondary && (
          <UI.Button variant="ghost" size="sm">{alert.secondary.label}</UI.Button>
        )}
      </div>
    </div>
  );
};

/* ─── ShipmentRow ──────────────────────────────────────────────── */
const ShipmentRow = ({ shipment }) => {
  const pct = Math.round((shipment.ready / shipment.total) * 100);
  const tone = shipment.at_risk > 0 ? 'yellow' : pct === 100 ? 'green' : 'blue';
  return (
    <div style={{
      padding: '12px 14px',
      background: 'var(--bg-2)',
      border: '1px solid var(--bd-1)',
      borderRadius: 'var(--r-md)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>{shipment.day}</span>
          <span className="tabular" style={{ fontSize: 11, color: 'var(--fg-3)' }}>{shipment.date.slice(8,10)}/{shipment.date.slice(5,7)}</span>
        </div>
        <span className="tabular" style={{ fontSize: 13, fontWeight: 600, color: UI.colorVar(tone) }}>
          {shipment.ready}/{shipment.total}
        </span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--fg-2)', marginBottom: 8 }}>{shipment.client}</div>
      <div style={{ height: 5, background: 'var(--bg-3)', borderRadius: 3, overflow: 'hidden', display: 'flex' }}>
        <div style={{ width: `${pct}%`, background: UI.colorVar(tone) }} />
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11, color: 'var(--fg-2)' }}>
        <span>✓ {shipment.ready} prontos</span>
        {shipment.in_prod > 0 && <span>◐ {shipment.in_prod} em produção</span>}
        {shipment.at_risk > 0 && <span style={{ color: 'var(--yellow)' }}>◆ {shipment.at_risk} em risco</span>}
      </div>
      {shipment.suggestion && (
        <div style={{
          marginTop: 10, padding: '8px 10px',
          background: 'var(--blue-bg)',
          border: '1px solid var(--blue-bd)',
          borderRadius: 'var(--r-sm)',
          fontSize: 11, color: 'var(--fg-1)',
          display: 'flex', gap: 7, alignItems: 'flex-start',
        }}>
          <I.Sparkles size={12} color="var(--blue)" style={{ marginTop: 1, flexShrink: 0 }} />
          <span>{shipment.suggestion}</span>
        </div>
      )}
    </div>
  );
};

window.PageCEO = PageCEO;
