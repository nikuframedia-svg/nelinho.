/* ─── Página: Inbox de decisões ──────────────────────────────────── */
const PageInbox = ({ onNavigate }) => {
  const [filter, setFilter] = React.useState('pending');

  return (
    <UI.Page
      icon={<I.Inbox size={20} />}
      title="Inbox de decisões"
      subtitle="Sugestões à espera da sua decisão. Tudo o que aceitar ou rejeitar ensina o sistema."
      actions={<UI.Button variant="secondary" size="sm" icon={<I.Filter size={13} />}>Filtros</UI.Button>}
    >
      {/* Explainer banner — só na 1ª utilização ou sempre? Por agora, sempre. */}
      <div style={{
        padding: '14px 18px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        marginBottom: 22,
        display: 'flex', gap: 14, alignItems: 'flex-start',
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 'var(--r-md)',
          background: 'var(--blue-bg)', border: '1px solid var(--blue-bd)',
          display: 'grid', placeItems: 'center', flexShrink: 0,
        }}>
          <I.Info size={16} color="var(--blue)" />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--fg-0)', marginBottom: 4 }}>
            Como funciona a inbox
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-2)', lineHeight: 1.6 }}>
            Cada cartão é uma <strong style={{ color: 'var(--fg-1)' }}>proposta</strong>, não uma ordem. Vê <strong style={{ color: 'var(--fg-1)' }}>o que muda se aceitar</strong>, <strong style={{ color: 'var(--fg-1)' }}>o que muda se rejeitar</strong>, e (quando há) uma <strong style={{ color: 'var(--fg-1)' }}>alternativa</strong>. Rejeitar exige sempre um motivo curto — é assim que o sistema aprende a sua forma de decidir.
          </div>
        </div>
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 18 }}>
        {[
          { id: 'pending',  label: 'Pendentes',  count: 3 },
          { id: 'accepted', label: 'Aceites hoje', count: 12 },
          { id: 'rejected', label: 'Rejeitadas hoje', count: 4 },
          { id: 'all',      label: 'Tudo',       count: 47 },
        ].map(t => (
          <button key={t.id} onClick={() => setFilter(t.id)} style={{
            padding: '7px 14px',
            background: filter === t.id ? 'var(--bg-3)' : 'var(--bg-1)',
            border: `1px solid ${filter === t.id ? 'var(--bd-2)' : 'var(--bd-1)'}`,
            borderRadius: 'var(--r-md)',
            color: filter === t.id ? 'var(--fg-0)' : 'var(--fg-2)',
            fontSize: 12, fontWeight: 500,
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 7,
          }}>
            {t.label}
            <span style={{
              fontSize: 10, padding: '1px 6px',
              background: filter === t.id ? 'var(--bg-1)' : 'var(--bg-3)',
              borderRadius: 999, color: 'var(--fg-1)',
            }}>{t.count}</span>
          </button>
        ))}
      </div>

      {/* List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {PP.SUGGESTIONS.map(s => <SuggestionCard key={s.id} suggestion={s} />)}
      </div>
    </UI.Page>
  );
};

const SuggestionCard = ({ suggestion: s }) => (
  <UI.Card padding={0}>
    <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--bd-1)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14, marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <UI.SevBadge severity={s.priority === 'critical' ? 'critical' : s.priority === 'high' ? 'high' : 'medium'} />
          <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>Sugestão #{s.id}</span>
        </div>
      </div>
      <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--fg-0)', lineHeight: 1.4 }}>{s.title}</h3>
      <div style={{ marginTop: 10, fontSize: 13, color: 'var(--fg-1)', lineHeight: 1.6, paddingLeft: 14, borderLeft: '2px solid var(--bd-2)' }}>
        <strong style={{ color: 'var(--fg-0)' }}>Porquê:</strong> {s.why}
      </div>
    </div>
    <div style={{ padding: 22 }}>
      <UI.ConsequenceBox
        if_accept={s.if_accept}
        if_reject={s.if_reject}
        alternative={s.alternative}
        confidence={s.confidence}
        source={s.source}
        onAccept={() => alert(`Sugestão #${s.id} aceite.`)}
        onReject={(r) => alert(`Sugestão #${s.id} rejeitada. Motivo: ${r}`)}
        onAlternative={() => alert(`Alternativa aplicada à #${s.id}.`)}
      />
    </div>
  </UI.Card>
);

window.PageInbox = PageInbox;
