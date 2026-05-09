/**
 * LiveBadge — port literal de design/nelo-zip/src/atoms.jsx LiveBadge.
 *
 * Pequeno badge pill com dot verde pulsante + label "Em direto".
 * Usado no TopBar (zip shell.jsx) para indicar que dados são live.
 *
 * Sprint Q.18.ZIP.shell.
 */

export function LiveBadge({ label = 'Em direto' }: { label?: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 text-text-dark-tertiary"
      style={{
        padding: '4px 10px',
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: 999,
        fontSize: 11,
      }}
    >
      <span
        className="rounded-full animate-pulse"
        style={{
          width: 6,
          height: 6,
          background: 'var(--green)',
        }}
      />
      {label}
    </span>
  );
}
