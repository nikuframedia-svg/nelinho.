/**
 * ComplexityBadge — Q.155.E. Mostra o ICB (0–100) do barco com cor por nível.
 * >=75 vermelho (muito complexo), 45–74 âmbar, <45 cinza. null → não renderiza.
 */
export function ComplexityBadge({ score, rank }: { score?: number; rank?: number }) {
  if (score == null) return null;
  const tone =
    score >= 75
      ? { bg: 'rgba(239,68,68,0.15)', fg: '#fca5a5' }
      : score >= 45
        ? { bg: 'rgba(245,158,11,0.15)', fg: '#fcd34d' }
        : { bg: 'rgba(100,116,139,0.18)', fg: '#cbd5e1' };
  return (
    <span
      title={`Complexidade ${score}/100${rank ? ` · #${rank} mais complexo` : ''}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 3,
        padding: '1px 6px',
        borderRadius: 999,
        fontSize: 10.5,
        fontWeight: 600,
        fontVariantNumeric: 'tabular-nums',
        background: tone.bg,
        color: tone.fg,
        whiteSpace: 'nowrap',
      }}
    >
      ⬢ {score}
    </span>
  );
}
