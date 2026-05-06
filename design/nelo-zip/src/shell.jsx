/* ─── Shell: sidebar + topbar ────────────────────────────────────── */
const { useState: useStateS } = React;

const NAV_GROUPS = [
  {
    label: 'Operação',
    items: [
      { id: 'ceo',        label: 'Direção',          icon: <I.Building size={16} />, badge: null },
      { id: 'inbox',      label: 'Inbox de decisões', icon: <I.Inbox size={16} />,    badge: 3 },
      { id: 'scheduling', label: 'Plano de produção',icon: <I.Calendar size={16} />, badge: null },
      { id: 'dispatch',   label: 'Atribuição diária',icon: <I.Activity size={16} />, badge: 1 },
    ],
  },
  {
    label: 'Análise',
    items: [
      { id: 'oee',        label: 'OEE',              icon: <I.Trending size={16} />, badge: null },
      { id: 'quality',    label: 'Qualidade',        icon: <I.Shield size={16} />,   badge: null },
      { id: 'workforce',  label: 'Operadores',       icon: <I.Workers size={16} />,  badge: null },
      { id: 'shipments',  label: 'Expedição',        icon: <I.Truck size={16} />,    badge: null },
    ],
  },
  {
    label: 'Sistema',
    items: [
      { id: 'learning',   label: 'O que aprendi',    icon: <I.Brain size={16} />,    badge: null },
      { id: 'settings',   label: 'Definições',       icon: <I.Settings size={16} />, badge: null },
    ],
  },
];

const Sidebar = ({ active, onNavigate }) => (
  <aside style={{
    width: 240, flexShrink: 0,
    background: 'var(--bg-1)',
    borderRight: '1px solid var(--bd-1)',
    display: 'flex', flexDirection: 'column',
    height: '100vh', position: 'sticky', top: 0,
  }}>
    {/* Logo */}
    <div style={{
      padding: '18px 20px',
      borderBottom: '1px solid var(--bd-1)',
      display: 'flex', alignItems: 'center', gap: 10,
    }}>
      <div style={{
        width: 30, height: 30,
        background: 'var(--blue)',
        borderRadius: 'var(--r-md)',
        display: 'grid', placeItems: 'center',
        color: '#fff',
        fontWeight: 700, fontSize: 14,
      }}>N</div>
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-0)', letterSpacing: -0.1 }}>NELO</div>
        <div style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: 0.4, textTransform: 'uppercase' }}>ProdPlan ONE</div>
      </div>
    </div>

    {/* Nav */}
    <nav style={{ flex: 1, overflowY: 'auto', padding: '12px 10px' }}>
      {NAV_GROUPS.map(g => (
        <div key={g.label} style={{ marginBottom: 18 }}>
          <div style={{
            fontSize: 10, color: 'var(--fg-3)',
            textTransform: 'uppercase', letterSpacing: 0.6,
            padding: '6px 12px 8px 12px',
            fontWeight: 600,
          }}>{g.label}</div>
          {g.items.map(item => {
            const isActive = active === item.id;
            return (
              <button key={item.id} onClick={() => onNavigate(item.id)} style={{
                display: 'flex', alignItems: 'center',
                width: '100%',
                padding: '8px 12px',
                background: isActive ? 'var(--bg-3)' : 'transparent',
                border: 'none',
                borderRadius: 'var(--r-md)',
                color: isActive ? 'var(--fg-0)' : 'var(--fg-1)',
                fontSize: 13,
                fontWeight: isActive ? 500 : 400,
                cursor: 'pointer',
                textAlign: 'left',
                gap: 11,
                transition: 'background 0.12s, color 0.12s',
                position: 'relative',
              }}
              onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--bg-2)'; }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
              >
                {isActive && <div style={{
                  position: 'absolute', left: -10, top: 8, bottom: 8, width: 2,
                  background: 'var(--blue)', borderRadius: 2,
                }} />}
                <span style={{ color: isActive ? 'var(--fg-0)' : 'var(--fg-2)' }}>{item.icon}</span>
                <span style={{ flex: 1 }}>{item.label}</span>
                {item.badge && (
                  <span style={{
                    background: 'var(--orange)', color: '#fff',
                    fontSize: 10, fontWeight: 600,
                    padding: '1px 6px', borderRadius: 999,
                    minWidth: 18, textAlign: 'center',
                  }}>{item.badge}</span>
                )}
              </button>
            );
          })}
        </div>
      ))}
    </nav>

    {/* User */}
    <div style={{
      padding: '14px 16px',
      borderTop: '1px solid var(--bd-1)',
      display: 'flex', alignItems: 'center', gap: 10,
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: '50%',
        background: 'var(--bg-3)', border: '1px solid var(--bd-2)',
        display: 'grid', placeItems: 'center',
        fontSize: 12, fontWeight: 600, color: 'var(--fg-1)',
      }}>NF</div>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <div style={{ fontSize: 12, color: 'var(--fg-0)', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Nuno Ferreira</div>
        <div style={{ fontSize: 10, color: 'var(--fg-3)' }}>Direção · NELO</div>
      </div>
    </div>
  </aside>
);

const Topbar = ({ onCopilot, copilotOpen }) => {
  const d = PP.TODAY;
  const dateStr = d.toLocaleDateString('pt-PT', { weekday: 'long', day: 'numeric', month: 'long' });
  const timeStr = d.toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' });
  return (
    <div style={{
      height: 52, flexShrink: 0,
      borderBottom: '1px solid var(--bd-1)',
      background: 'var(--bg-0)',
      display: 'flex', alignItems: 'center',
      padding: '0 24px',
      gap: 16,
      position: 'sticky', top: 0, zIndex: 20,
    }}>
      {/* Search */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        padding: '6px 12px',
        width: 320,
      }}>
        <I.Search size={14} color="var(--fg-3)" />
        <input
          placeholder="Procurar barco, operador, fase..."
          style={{
            flex: 1, background: 'transparent', border: 'none', outline: 'none',
            color: 'var(--fg-0)', fontSize: 13,
          }}
        />
        <span style={{ fontSize: 10, color: 'var(--fg-3)', padding: '1px 6px', border: '1px solid var(--bd-1)', borderRadius: 4 }}>⌘K</span>
      </div>

      <div style={{ flex: 1 }} />

      <UI.LiveBadge />
      <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>
        {dateStr} · <span className="tabular">{timeStr}</span>
      </span>

      <button onClick={onCopilot} style={{
        display: 'inline-flex', alignItems: 'center', gap: 7,
        padding: '6px 12px', height: 32,
        background: copilotOpen ? 'var(--blue)' : 'var(--bg-2)',
        color: copilotOpen ? '#fff' : 'var(--fg-1)',
        border: `1px solid ${copilotOpen ? 'var(--blue)' : 'var(--bd-2)'}`,
        borderRadius: 'var(--r-md)',
        fontSize: 12, fontWeight: 500,
        cursor: 'pointer',
        transition: 'background 0.12s',
      }}>
        <I.Sparkles size={14} />
        Assistente
      </button>
    </div>
  );
};

window.Shell = { Sidebar, Topbar };
