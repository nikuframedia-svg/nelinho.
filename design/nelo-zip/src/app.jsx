/* ─── App root ───────────────────────────────────────────────────── */
const { useState: useStateA } = React;

const App = () => {
  const [page, setPage] = useStateA('ceo');
  const [copilotOpen, setCopilotOpen] = useStateA(false);

  /* keyboard shortcut: cmd/ctrl + j */
  React.useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'j') {
        e.preventDefault();
        setCopilotOpen(o => !o);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const onNavigate = (id) => setPage(id);

  let pageEl;
  switch (page) {
    case 'ceo':        pageEl = <PageCEO onNavigate={onNavigate} onOpenCopilot={() => setCopilotOpen(true)} />; break;
    case 'inbox':      pageEl = <PageInbox onNavigate={onNavigate} />; break;
    case 'scheduling': pageEl = <PageScheduling />; break;
    case 'dispatch':   pageEl = <PageDispatch />; break;
    case 'oee':        pageEl = <PageOEE />; break;
    case 'quality':    pageEl = <PageQuality />; break;
    case 'workforce':  pageEl = <PageWorkforce />; break;
    case 'shipments':  pageEl = <PageShipments />; break;
    case 'learning':   pageEl = <PageLearning />; break;
    case 'settings':   pageEl = <PageSettings />; break;
    default:           pageEl = <PageCEO onNavigate={onNavigate} onOpenCopilot={() => setCopilotOpen(true)} />;
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-0)' }}>
      <Shell.Sidebar active={page} onNavigate={onNavigate} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Shell.Topbar onCopilot={() => setCopilotOpen(o => !o)} copilotOpen={copilotOpen} />
        <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>{pageEl}</main>
      </div>
      <CopilotDrawer open={copilotOpen} onClose={() => setCopilotOpen(false)} />
    </div>
  );
};

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
