/* ─── Icons — minimal Feather-style 1.6px stroke ─────────────────── */
const ic = (paths, vb = '0 0 24 24') => ({ size = 16, color = 'currentColor', style = {}, ...rest }) => (
  <svg width={size} height={size} viewBox={vb} fill="none" stroke={color}
       strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
       style={{ flexShrink: 0, ...style }} {...rest}>
    {paths}
  </svg>
);

const I = {
  /* nav */
  Layout:    ic(<><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></>),
  Inbox:     ic(<><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z"/></>),
  Calendar:  ic(<><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></>),
  Workers:   ic(<><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>),
  Activity:  ic(<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>),
  Shield:    ic(<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>),
  Boxes:     ic(<><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="m3.3 7 8.7 5 8.7-5M12 22V12"/></>),
  Truck:     ic(<><path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/><path d="M14 9h4l4 4v5h-2"/></>),
  Building:  ic(<><rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4M8 6h.01M16 6h.01M12 6h.01M12 10h.01M12 14h.01M16 10h.01M16 14h.01M8 10h.01M8 14h.01"/></>),
  Sparkles:  ic(<><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/><path d="M5 3v4M3 5h4M19 17v4M17 19h4"/></>),
  Settings:  ic(<><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/></>),
  /* small */
  Check:     ic(<path d="M20 6 9 17l-5-5"/>),
  X:         ic(<path d="M18 6 6 18M6 6l12 12"/>),
  Chevron:   ic(<path d="m9 18 6-6-6-6"/>),
  ChevronDown: ic(<path d="m6 9 6 6 6-6"/>),
  ChevronUp: ic(<path d="m18 15-6-6-6 6"/>),
  ArrowRight:ic(<path d="M5 12h14M13 5l7 7-7 7"/>),
  Plus:      ic(<path d="M12 5v14M5 12h14"/>),
  Search:    ic(<><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></>),
  Bell:      ic(<><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></>),
  Filter:    ic(<path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/>),
  Info:      ic(<><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></>),
  Alert:     ic(<><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4M12 17h.01"/></>),
  Clock:     ic(<><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></>),
  Brain:     ic(<><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></>),
  Send:      ic(<path d="m22 2-7 20-4-9-9-4 20-7Z"/>),
  Menu:      ic(<path d="M3 12h18M3 6h18M3 18h18"/>),
  Eye:       ic(<><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></>),
  Trending:  ic(<path d="m22 7-8.5 8.5-5-5L2 17"/>),
  TrendDown: ic(<path d="m22 17-8.5-8.5-5 5L2 7"/>),
  Minus:     ic(<path d="M5 12h14"/>),
  Refresh:   ic(<><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/></>),
  Lock:      ic(<><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></>),
  User:      ic(<><circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 0 0-16 0"/></>),
  Database:  ic(<><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></>),
  GripVert:  ic(<><circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/></>),
  MoreH:     ic(<><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></>),
  Zap:       ic(<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>),
  Pause:     ic(<><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></>),
  Play:      ic(<polygon points="5 3 19 12 5 21 5 3"/>),
  Logo:      ic(<><path d="M3 17 12 3l9 14"/><path d="M3 17h18"/><path d="m7 17 5-8 5 8"/></>, '0 0 24 24'),
};

window.I = I;
