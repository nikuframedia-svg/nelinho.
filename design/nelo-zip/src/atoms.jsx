/* ─── PP1-NELO atoms & shared components ─────────────────────────── */
const { useState, useEffect, useRef, useMemo } = React;

/* ─── Status colour map (NEVER colour-only — always icon + label) ── */
const STATUS = {
  on_time:    { color: 'green',  label: 'No prazo',     glyph: '●'  },
  at_risk:    { color: 'yellow', label: 'Em risco',     glyph: '◆'  },
  late:       { color: 'red',    label: 'Atrasado',     glyph: '▲'  },
  curing:     { color: 'gray',   label: 'Em cura',      glyph: '◐'  },
  completed:  { color: 'blue',   label: 'Concluído',    glyph: '■'  },
};
const SEV = {
  critical: { color: 'red',    label: 'Crítico',  glyph: '▲' },
  high:     { color: 'orange', label: 'Alto',     glyph: '▲' },
  medium:   { color: 'yellow', label: 'Médio',    glyph: '◆' },
  low:      { color: 'blue',   label: 'Baixo',    glyph: '●' },
};
const colorVar = (c) => `var(--${c})`;
const colorBg  = (c) => `var(--${c}-bg)`;
const colorBd  = (c) => `var(--${c}-bd)`;

/* ─── Badge — icon + label pair ──────────────────────────────────── */
const Badge = ({ tone = 'gray', children, glyph, size = 'md' }) => {
  const sz = size === 'sm' ? { padding: '1px 7px', fontSize: 11, height: 20 }
                            : { padding: '3px 10px', fontSize: 12, height: 24 };
  const isToken = ['green','yellow','red','blue','orange','purple','gray'].includes(tone);
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      ...sz,
      borderRadius: 999, fontWeight: 500,
      letterSpacing: 0.1,
      color: isToken && tone !== 'gray' ? colorVar(tone) : 'var(--fg-1)',
      background: isToken && tone !== 'gray' ? colorBg(tone) : 'var(--bg-3)',
      border: `1px solid ${isToken && tone !== 'gray' ? colorBd(tone) : 'var(--bd-1)'}`,
    }}>
      {glyph && <span style={{ fontSize: 9, lineHeight: 1 }}>{glyph}</span>}
      {children}
    </span>
  );
};

const StatusBadge = ({ status, size = 'md' }) => {
  const s = STATUS[status] || STATUS.on_time;
  return <Badge tone={s.color} glyph={s.glyph} size={size}>{s.label}</Badge>;
};

const SevBadge = ({ severity, size = 'md' }) => {
  const s = SEV[severity] || SEV.low;
  return <Badge tone={s.color} glyph={s.glyph} size={size}>{s.label}</Badge>;
};

/* ─── Card — base container ─────────────────────────────────────── */
const Card = ({ children, style = {}, padding = 20, ...rest }) => (
  <div style={{
    background: 'var(--bg-1)',
    border: '1px solid var(--bd-1)',
    borderRadius: 'var(--r-lg)',
    padding,
    ...style,
  }} {...rest}>{children}</div>
);

const CardHeader = ({ icon, title, subtitle, actions, accent }) => (
  <div style={{
    display: 'flex', alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 14,
    gap: 12,
  }}>
    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      {icon && (
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: accent ? colorBg(accent) : 'var(--bg-3)',
          color: accent ? colorVar(accent) : 'var(--fg-1)',
          display: 'grid', placeItems: 'center',
          border: `1px solid ${accent ? colorBd(accent) : 'var(--bd-1)'}`,
          flexShrink: 0,
        }}>{icon}</div>
      )}
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-0)', lineHeight: 1.3 }}>{title}</div>
        {subtitle && <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 2 }}>{subtitle}</div>}
      </div>
    </div>
    {actions && <div style={{ display: 'flex', gap: 6 }}>{actions}</div>}
  </div>
);

/* ─── Button ─────────────────────────────────────────────────────── */
const Button = ({ variant = 'secondary', tone, size = 'md', icon, children, fullWidth, ...rest }) => {
  const sizes = {
    sm: { padding: '5px 10px', fontSize: 12, height: 28, gap: 6 },
    md: { padding: '7px 14px', fontSize: 13, height: 34, gap: 7 },
    lg: { padding: '12px 20px', fontSize: 15, height: 48, gap: 9 },
    xl: { padding: '16px 24px', fontSize: 18, height: 64, gap: 10 },
  };
  let style = {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    fontWeight: 500, borderRadius: 'var(--r-md)',
    border: '1px solid transparent',
    transition: 'background 0.12s, border-color 0.12s, color 0.12s',
    whiteSpace: 'nowrap',
    width: fullWidth ? '100%' : 'auto',
    ...sizes[size],
  };
  if (variant === 'primary') {
    const t = tone || 'blue';
    style = { ...style,
      background: colorVar(t), color: '#fff',
      borderColor: colorVar(t),
    };
  } else if (variant === 'tonal') {
    const t = tone || 'blue';
    style = { ...style,
      background: colorBg(t), color: colorVar(t),
      borderColor: colorBd(t),
    };
  } else if (variant === 'ghost') {
    style = { ...style, background: 'transparent', color: 'var(--fg-1)' };
  } else {
    style = { ...style,
      background: 'var(--bg-2)', color: 'var(--fg-0)',
      borderColor: 'var(--bd-2)',
    };
  }
  return (
    <button style={style} {...rest}>
      {icon}{children}
    </button>
  );
};

/* ─── KPICard — number + context (NEVER % alone) ─────────────────── */
const KPICard = ({ label, value, unit, context, target, trend, status, sparkline, onClick, accent = 'gray' }) => {
  const tone = status === 'green' ? 'green'
            : status === 'yellow' ? 'yellow'
            : status === 'red'    ? 'red'
            : 'gray';
  return (
    <div onClick={onClick} style={{
      background: 'var(--bg-1)',
      border: `1px solid var(--bd-1)`,
      borderLeft: `3px solid ${colorVar(tone)}`,
      borderRadius: 'var(--r-lg)',
      padding: 18,
      cursor: onClick ? 'pointer' : 'default',
      transition: 'border-color 0.15s, background 0.15s',
    }}
    onMouseEnter={e => { if (onClick) e.currentTarget.style.background = 'var(--bg-2)'; }}
    onMouseLeave={e => { if (onClick) e.currentTarget.style.background = 'var(--bg-1)'; }}
    >
      <div style={{ fontSize: 12, color: 'var(--fg-2)', textTransform: 'uppercase', letterSpacing: 0.4, fontWeight: 500 }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 8 }}>
        <span className="tabular" style={{ fontSize: 32, fontWeight: 700, color: 'var(--fg-0)', lineHeight: 1 }}>
          {value}
        </span>
        {unit && <span style={{ fontSize: 14, color: 'var(--fg-2)' }}>{unit}</span>}
      </div>
      {context && (
        <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 8, lineHeight: 1.4 }}>
          {context}
        </div>
      )}
      {(target !== undefined || trend !== undefined) && (
        <div style={{ display: 'flex', gap: 10, marginTop: 10, fontSize: 11, color: 'var(--fg-3)' }}>
          {target !== undefined && (
            <span>Meta: <span className="tabular" style={{ color: 'var(--fg-1)' }}>{target}</span></span>
          )}
          {trend !== undefined && (
            <span style={{ color: trend >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {trend >= 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}% vs ontem
            </span>
          )}
        </div>
      )}
      {sparkline && (
        <div style={{ marginTop: 12, height: 32 }}>
          <Sparkline data={sparkline} color={colorVar(tone)} />
        </div>
      )}
    </div>
  );
};

/* ─── Sparkline (SVG) ────────────────────────────────────────────── */
const Sparkline = ({ data, color = 'var(--blue)', height = 32 }) => {
  if (!data || data.length === 0) return null;
  const w = 200, h = height;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => [
    (i / (data.length - 1)) * w,
    h - ((v - min) / range) * (h - 4) - 2
  ]);
  const d = pts.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(' ');
  const dArea = d + ` L${w},${h} L0,${h} Z`;
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <path d={dArea} fill={color} fillOpacity={0.10} />
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
};

/* ─── ConsequenceBox — the heart of advisory mode ────────────────── */
/*  ALWAYS appears before any irreversible action.                    */
const ConsequenceBox = ({ if_accept, if_reject, alternative, source, confidence, onAccept, onReject, onAlternative, requireReason = 'on_reject' }) => {
  const [reason, setReason] = useState('');
  const [showReason, setShowReason] = useState(false);
  const ifA = Array.isArray(if_accept) ? if_accept : [if_accept];
  const ifR = Array.isArray(if_reject) ? if_reject : [if_reject];

  const handleReject = () => {
    if (requireReason === 'always' || requireReason === 'on_reject') {
      if (!reason.trim()) { setShowReason(true); return; }
    }
    onReject?.(reason);
  };
  const handleAccept = () => {
    onAccept?.(reason);
  };

  return (
    <div style={{
      border: '1px solid var(--bd-2)',
      borderRadius: 'var(--r-lg)',
      background: 'var(--bg-1)',
      overflow: 'hidden',
    }}>
      {/* Two columns: aceitar / rejeitar */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
        <div style={{
          padding: 14,
          borderRight: '1px solid var(--bd-1)',
          background: 'var(--green-bg)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
            <I.Check size={14} />
            <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 600, color: 'var(--green)' }}>Se aceitar</span>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--fg-1)', fontSize: 13, lineHeight: 1.6 }}>
            {ifA.map((s, i) => <li key={i} style={{ marginBottom: 4 }}>{s}</li>)}
          </ul>
        </div>
        <div style={{
          padding: 14,
          background: 'var(--red-bg)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
            <I.X size={14} />
            <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 600, color: 'var(--red)' }}>Se rejeitar</span>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--fg-1)', fontSize: 13, lineHeight: 1.6 }}>
            {ifR.map((s, i) => <li key={i} style={{ marginBottom: 4 }}>{s}</li>)}
          </ul>
        </div>
      </div>

      {/* Alternativa */}
      {alternative && (
        <div style={{
          padding: '12px 14px',
          background: 'var(--blue-bg)',
          borderTop: '1px solid var(--bd-1)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <I.Sparkles size={14} />
            <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 600, color: 'var(--blue)' }}>Alternativa</span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--fg-0)', fontWeight: 500 }}>{alternative.label}</div>
          <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 2 }}>{alternative.detail}</div>
        </div>
      )}

      {/* Footer: source + actions */}
      <div style={{
        padding: 14,
        background: 'var(--bg-2)',
        borderTop: '1px solid var(--bd-1)',
      }}>
        {/* Reason field — sempre visível em rejeição (regra #5) */}
        {(showReason || requireReason === 'always') && (
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', fontSize: 11, color: 'var(--fg-2)', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6 }}>
              Porquê esta decisão? <span style={{ color: 'var(--fg-3)', textTransform: 'none', letterSpacing: 0 }}>(ajuda o sistema a aprender)</span>
            </label>
            <input
              autoFocus={showReason}
              value={reason}
              onChange={e => setReason(e.target.value)}
              placeholder="Ex: o gestor da fase decidiu manter o plano original"
              style={{
                width: '100%',
                padding: '9px 12px',
                background: 'var(--bg-0)',
                border: '1px solid var(--bd-2)',
                borderRadius: 'var(--r-md)',
                color: 'var(--fg-0)',
                outline: 'none',
              }}
              onFocus={e => e.target.style.borderColor = 'var(--blue)'}
              onBlur={e => e.target.style.borderColor = 'var(--bd-2)'}
            />
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {source && <span>Fonte: {source}</span>}
            {confidence !== undefined && (
              <>
                {source && <span style={{ color: 'var(--bd-2)' }}>·</span>}
                <span>Confiança: <span style={{ color: 'var(--fg-1)' }}>{confidence}%</span></span>
              </>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {alternative && onAlternative && (
              <Button variant="tonal" tone="blue" size="sm" onClick={() => onAlternative(reason)}>
                Aplicar alternativa
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={handleReject} icon={<I.X size={13} />}>
              Rejeitar
            </Button>
            <Button variant="primary" tone="green" size="sm" onClick={handleAccept} icon={<I.Check size={13} />}>
              Aceitar
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ─── BoatCard — small, clickable, drag-able ─────────────────────── */
const BoatCard = ({ boat, onClick, compact = false }) => {
  const c = PP.CLIENTS[boat.client] || { code: boat.client, flag: '' };
  const s = STATUS[boat.status] || STATUS.on_time;
  return (
    <div onClick={onClick} style={{
      background: 'var(--bg-2)',
      border: `1px solid var(--bd-1)`,
      borderLeft: `3px solid ${colorVar(s.color)}`,
      borderRadius: 'var(--r-md)',
      padding: compact ? '7px 9px' : '9px 11px',
      cursor: onClick ? 'pointer' : 'grab',
      transition: 'background 0.12s',
      fontSize: 12,
    }}
    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-3)'}
    onMouseLeave={e => e.currentTarget.style.background = 'var(--bg-2)'}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span style={{ fontWeight: 600, color: 'var(--fg-0)' }}>{boat.short} #{boat.id}</span>
        <span style={{ fontSize: 10, color: 'var(--fg-3)' }}>{c.flag}</span>
      </div>
      {!compact && (
        <div style={{ marginTop: 3, fontSize: 11, color: 'var(--fg-2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 80 }}>{c.code}</span>
          <span style={{ color: colorVar(s.color), fontSize: 10 }}>{s.glyph} {s.label}</span>
        </div>
      )}
    </div>
  );
};

/* ─── WorkerAvatar ──────────────────────────────────────────────── */
const WorkerAvatar = ({ worker, size = 32, showScore = false }) => (
  <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: 'var(--bg-3)',
      border: '1px solid var(--bd-2)',
      display: 'grid', placeItems: 'center',
      fontSize: size * 0.36, fontWeight: 600,
      color: 'var(--fg-1)',
      flexShrink: 0,
    }}>{worker.initials}</div>
    {showScore && (
      <span style={{ fontSize: 11, color: 'var(--fg-2)' }}>
        ★ <span className="tabular" style={{ color: 'var(--fg-0)' }}>{worker.score.toFixed(1)}</span>
      </span>
    )}
  </div>
);

/* ─── Section header (page-internal) ────────────────────────────── */
const SectionHeader = ({ icon, title, subtitle, action }) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      {icon && <span style={{ color: 'var(--fg-2)' }}>{icon}</span>}
      <div>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--fg-0)' }}>{title}</h2>
        {subtitle && <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 2 }}>{subtitle}</div>}
      </div>
    </div>
    {action}
  </div>
);

/* ─── Page header ───────────────────────────────────────────────── */
const PageHeader = ({ icon, title, subtitle, actions }) => (
  <div style={{
    padding: '20px 28px 16px 28px',
    borderBottom: '1px solid var(--bd-1)',
    display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
    gap: 16,
    background: 'var(--bg-0)',
    position: 'sticky', top: 0, zIndex: 10,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      {icon && (
        <div style={{
          width: 38, height: 38, borderRadius: 'var(--r-md)',
          background: 'var(--bg-2)', color: 'var(--fg-1)',
          display: 'grid', placeItems: 'center',
          border: '1px solid var(--bd-1)',
        }}>{icon}</div>
      )}
      <div>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: 'var(--fg-0)', letterSpacing: -0.2 }}>{title}</h1>
        {subtitle && <div style={{ fontSize: 13, color: 'var(--fg-2)', marginTop: 3 }}>{subtitle}</div>}
      </div>
    </div>
    {actions && <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>{actions}</div>}
  </div>
);

const Page = ({ icon, title, subtitle, actions, children }) => (
  <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100%', flex: 1 }}>
    <PageHeader icon={icon} title={title} subtitle={subtitle} actions={actions} />
    <div style={{ padding: '24px 28px', flex: 1 }}>{children}</div>
  </div>
);

/* ─── Live badge ─────────────────────────────────────────────────── */
const LiveBadge = ({ label = 'Em direto' }) => (
  <div style={{
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '4px 10px',
    background: 'var(--bg-2)',
    border: '1px solid var(--bd-1)',
    borderRadius: 999,
    fontSize: 11,
    color: 'var(--fg-2)',
  }}>
    <span className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)' }} />
    {label}
  </div>
);

/* ─── exports ─── */
window.UI = {
  Badge, StatusBadge, SevBadge,
  Card, CardHeader, Button,
  KPICard, Sparkline,
  ConsequenceBox,
  BoatCard, WorkerAvatar,
  SectionHeader, PageHeader, Page, LiveBadge,
  STATUS, SEV, colorVar, colorBg, colorBd,
};
