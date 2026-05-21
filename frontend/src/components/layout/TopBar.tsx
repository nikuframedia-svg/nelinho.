/**
 * TopBar — port literal de design/nelo-zip/src/shell.jsx Topbar.
 *
 * Layout: search 360px (bg-2) + flex-1 spacer + LiveBadge + date longo +
 * botão "Assistente" (Sparkles icon, azul quando aberto).
 *
 * Q.52.S — a caixa de pesquisa é um <input> real: Enter navega para
 * `/pesquisa?q=…` (SearchResultsPage, GET /v1/search). ⌘K continua a abrir
 * a paleta de comandos para navegação rápida.
 *
 * Sem UmweltSwitcher / Notifications / Breadcrumbs (zip não tem).
 * User chip vive na Sidebar footer (zip pattern).
 *
 * Sprint Q.18.ZIP.shell · Q.52.S.
 */

import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Sparkles } from 'lucide-react';
import { LiveBadge } from '../dark/LiveBadge';
import { UmweltPills } from './UmweltPills';

function nowLabels(): { compact: string; full: string } {
  const d = new Date();
  const compact = d.toLocaleTimeString('pt-PT', {
    hour: '2-digit',
    minute: '2-digit',
  });
  const full = `${d.toLocaleDateString('pt-PT', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })} · ${d.toLocaleTimeString('pt-PT', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })}`;
  return { compact, full };
}

function openCopilot() {
  window.dispatchEvent(new CustomEvent('copilot:open'));
}

export function TopBar() {
  const navigate = useNavigate();
  const [now, setNow] = useState(nowLabels());
  const [term, setTerm] = useState('');

  useEffect(() => {
    const id = window.setInterval(() => setNow(nowLabels()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  function onSearchSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const q = term.trim();
    if (q.length === 0) return;
    navigate(`/pesquisa?q=${encodeURIComponent(q)}`);
  }

  return (
    <header
      className="flex items-center sticky top-0 z-20"
      style={{
        height: 52,
        flexShrink: 0,
        background: 'rgba(0,0,0,0.6)',
        backdropFilter: 'saturate(180%) blur(20px)',
        WebkitBackdropFilter: 'saturate(180%) blur(20px)',
        borderBottom: '1px solid var(--bd-1)',
        padding: '0 16px',
        gap: 14,
      }}
    >
      {/* Search — Enter navega para /pesquisa */}
      <form
        onSubmit={onSearchSubmit}
        className="flex items-center gap-2"
        role="search"
        style={{
          width: 360,
          height: 32,
          background: 'var(--bg-2)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-md)',
          padding: '5px 11px',
        }}
      >
        <Search size={13} className="shrink-0 text-text-dark-tertiary" />
        <input
          type="search"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="Procurar barco, operador, fase…"
          aria-label="Pesquisar"
          className="flex-1 bg-transparent outline-none border-none text-text-dark-primary placeholder:text-text-dark-tertiary"
          style={{ fontSize: 12 }}
        />
        <span
          className="mono text-text-dark-tertiary shrink-0"
          style={{
            fontSize: 10,
            padding: '1px 5px',
            background: 'var(--bg-3)',
            border: '1px solid var(--bd-1)',
            borderRadius: 4,
          }}
        >
          ⌘K
        </span>
      </form>

      <div className="flex-1" />

      {/* Umwelt switcher (Onda 12 L) */}
      <UmweltPills />

      {/* Live indicator */}
      <LiveBadge />

      {/* Hora compacta — tooltip com data completa */}
      <span
        className="text-text-dark-secondary tabular-nums hidden lg:inline cursor-default"
        style={{ fontSize: 12 }}
        aria-label={`Data e hora actual: ${now.full}`}
        title={now.full}
      >
        {now.compact}
      </span>

      {/* Assistente button */}
      <button
        type="button"
        onClick={openCopilot}
        className="inline-flex items-center gap-1.5 font-medium transition-colors"
        style={{
          padding: '0 11px',
          height: 32,
          background: 'var(--bg-2)',
          color: 'var(--fg-0)',
          border: '1px solid var(--bd-2)',
          borderRadius: 'var(--r-md)',
          fontSize: 12,
        }}
      >
        <Sparkles size={13} />
        Assistente
      </button>
    </header>
  );
}
