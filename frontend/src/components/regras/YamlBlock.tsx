/**
 * YamlBlock — visor YAML colorizado (Q.52.L).
 *
 * Port fiel do `YamlBlock` do protótipo NELO (page-regras.jsx): chaves
 * em accent, strings/números em amarelo, resto em fg-1. Tokenizador
 * linha-a-linha, zero dependências — chega para o DSL fechado e pequeno
 * do Q.17. Distinto do `YamlHighlight` legacy: geometria bate certo com
 * o protótipo (fundo bg-0, mono 11.5px, max-height 320px).
 */

import type { ReactNode } from 'react';

export interface YamlBlockProps {
  text: string;
  /** Altura máxima antes de scroll (default 320). */
  maxHeight?: number;
}

export function YamlBlock({ text, maxHeight = 320 }: YamlBlockProps): ReactNode {
  const lines = text.split('\n');
  return (
    <pre
      style={{
        margin: 0,
        padding: 14,
        background: 'var(--bg-0)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-sm)',
        fontFamily: 'Geist Mono, ui-monospace, monospace',
        fontSize: 11.5,
        lineHeight: 1.7,
        color: 'var(--fg-1)',
        overflow: 'auto',
        maxHeight,
      }}
    >
      {lines.map((line, i) => {
        const m = line.match(/^(\s*)([\w.-]+:)(.*)$/);
        if (!m) {
          return (
            <div key={i} style={{ color: 'var(--fg-3)' }}>
              {line || ' '}
            </div>
          );
        }
        const valueIsScalar = m[3].includes("'") || m[3].includes('"') || /\d/.test(m[3]);
        return (
          <div key={i}>
            <span>{m[1]}</span>
            <span style={{ color: 'var(--accent)' }}>{m[2]}</span>
            <span style={{ color: valueIsScalar ? 'var(--yellow)' : 'var(--fg-1)' }}>
              {m[3]}
            </span>
          </div>
        );
      })}
    </pre>
  );
}
