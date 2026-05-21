/**
 * PageHelpButton — botão "?" no canto superior direito do PageHeader.
 *
 * Onda fix-pagehelp — Luis: "ponha um ? em cada canto superior direito de
 * cada página, quando a pessoa clica tem um resumo e um exemplo de como
 * funcionar com a página em questão".
 *
 * Hover → tooltip "Ajuda da página". Click → Modal com 4 secções fixas
 * (Para que serve · O que vês · Como usar · Ver também) lidas do dicionário
 * estático em data/pageHelp.ts. Conteúdo instantâneo (sem LLM).
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HelpCircle, Lightbulb, ListOrdered, Sparkles, ArrowRight } from 'lucide-react';
import { Modal } from '../dark/Modal';
import { PAGE_HELP, type PageHelpId } from '../../data/pageHelp';

interface Props {
  helpId: PageHelpId;
}

export function PageHelpButton({ helpId }: Props) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const entry = PAGE_HELP[helpId];

  if (!entry) return null;

  function go(id: PageHelpId) {
    setOpen(false);
    // O `PageHelpId` é o próprio segmento de rota — navega directo.
    navigate(`/${id}`);
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="Ajuda da página"
        aria-label="Ajuda da página"
        className="inline-flex items-center justify-center transition-colors"
        style={{
          width: 32,
          height: 32,
          background: 'var(--bg-2)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-md)',
          color: 'var(--fg-2)',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = 'var(--blue)';
          e.currentTarget.style.borderColor = 'var(--blue)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = 'var(--fg-2)';
          e.currentTarget.style.borderColor = 'var(--bd-1)';
        }}
      >
        <HelpCircle size={15} />
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title={entry.title} size="lg">
        <div className="space-y-5 text-sm" style={{ color: 'var(--fg-1)' }}>
          {/* Para que serve */}
          <section>
            <div
              className="text-[10px] uppercase tracking-wider mb-1.5 flex items-center gap-1.5"
              style={{ color: 'var(--fg-3)' }}
            >
              <Sparkles size={11} />
              Para que serve
            </div>
            <p style={{ color: 'var(--fg-1)', lineHeight: 1.55 }}>{entry.purpose}</p>
          </section>

          {/* O que vês */}
          <section>
            <div
              className="text-[10px] uppercase tracking-wider mb-2 flex items-center gap-1.5"
              style={{ color: 'var(--fg-3)' }}
            >
              <ListOrdered size={11} />
              O que vês aqui
            </div>
            <ul className="space-y-1.5">
              {entry.whatYouSee.map((item, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2"
                  style={{ color: 'var(--fg-2)' }}
                >
                  <span
                    className="mt-1.5"
                    style={{
                      flexShrink: 0,
                      width: 4,
                      height: 4,
                      borderRadius: '50%',
                      background: 'var(--blue)',
                    }}
                  />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>

          {/* Como usar */}
          <section>
            <div
              className="text-[10px] uppercase tracking-wider mb-2 flex items-center gap-1.5"
              style={{ color: 'var(--fg-3)' }}
            >
              <Lightbulb size={11} />
              {entry.howToUse.title}
            </div>
            <ol className="space-y-2">
              {entry.howToUse.steps.map((step, i) => (
                <li key={i} className="flex items-start gap-3" style={{ color: 'var(--fg-1)' }}>
                  <span
                    className="inline-flex items-center justify-center text-[10px] font-semibold tabular-nums shrink-0"
                    style={{
                      width: 20,
                      height: 20,
                      borderRadius: '50%',
                      background: 'var(--blue-bg)',
                      color: 'var(--blue)',
                    }}
                  >
                    {i + 1}
                  </span>
                  <span style={{ lineHeight: 1.5 }}>{step}</span>
                </li>
              ))}
            </ol>
          </section>

          {/* Dicas */}
          {entry.tips && entry.tips.length > 0 && (
            <section
              className="rounded-md border p-3"
              style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}
            >
              <div
                className="text-[10px] uppercase tracking-wider mb-1.5"
                style={{ color: 'var(--yellow)' }}
              >
                Dicas
              </div>
              <ul className="space-y-1 text-xs">
                {entry.tips.map((tip, i) => (
                  <li key={i} style={{ color: 'var(--fg-2)' }}>
                    • {tip}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Ver também */}
          {entry.relatedPages && entry.relatedPages.length > 0 && (
            <section>
              <div
                className="text-[10px] uppercase tracking-wider mb-2"
                style={{ color: 'var(--fg-3)' }}
              >
                Ver também
              </div>
              <div className="space-y-1">
                {entry.relatedPages.map((rp) => (
                  <button
                    key={rp.id}
                    type="button"
                    onClick={() => go(rp.id)}
                    className="w-full text-left rounded-md border px-3 py-2 transition-colors flex items-center justify-between"
                    style={{
                      background: 'var(--bg-2)',
                      borderColor: 'var(--bd-1)',
                      color: 'var(--fg-1)',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--blue)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--bd-1)';
                    }}
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium" style={{ color: 'var(--fg-1)' }}>
                        {PAGE_HELP[rp.id]?.title ?? rp.id}
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--fg-3)' }}>
                        {rp.reason}
                      </div>
                    </div>
                    <ArrowRight size={14} style={{ color: 'var(--fg-3)' }} />
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      </Modal>
    </>
  );
}
