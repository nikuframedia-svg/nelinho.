/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Fonte-de-verdade da paleta = index.css :root + @theme. Os HEX aqui
        // espelham esses tokens — ao mudar uma cor, mudar primeiro no index.css
        // e refletir o HEX aqui (Q.52.A).
        // Dark theme backgrounds — Q.52.A preto-puro NELO.html (--bg-N)
        dark: {
          900: '#000000',   // matches --bg-0
          800: '#0a0a0c',   // matches --bg-1
          700: '#111114',   // matches --bg-2
          600: '#18181c',   // matches --bg-3
          500: '#222227',   // matches --bg-4
        },
        // Accent — Q.52.A azul NELO.html (#2876e5, era teal)
        accent: {
          50: '#eef4fd',
          100: '#d4e3fa',
          200: '#a9c7f5',
          300: '#7eaaef',
          400: '#4f93ec',
          500: '#2876e5',
          600: '#1f5cb8',
          700: '#17468b',
          800: '#0f2f5d',
          900: '#081930',
        },
        // Primary (Blue)
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
        // Text colors — Q.52.A soft-white NELO.html (--fg-N)
        'text-dark': {
          primary:   '#f5f5f7',  // matches --fg-0
          secondary: '#c7c7cc',  // matches --fg-1
          tertiary:  '#8e8e93',  // matches --fg-2
          muted:     '#636366',  // matches --fg-3
        },
        // Border tokens (--bd-N) — translucent white (NELO.html).
        // HEX-on-black equivalents para utilitários Tailwind sólidos.
        'bd-1': 'rgba(255,255,255,0.06)',  // matches --bd-1
        'bd-2': 'rgba(255,255,255,0.10)',  // matches --bd-2
        'bd-3': 'rgba(255,255,255,0.16)',  // matches --bd-3
        // Status colors — Q.52.A sober-on-black NELO.html
        green:  { DEFAULT: '#2da14b' },
        yellow: { DEFAULT: '#c9a72a' },
        red:    { DEFAULT: '#d6453a' },
        blue:   { DEFAULT: '#2876e5' },
        // Status colors
        success: {
          DEFAULT: '#10b981',
          light: '#34d399',
          dark: '#059669',
        },
        warning: {
          DEFAULT: '#f59e0b',
          light: '#fbbf24',
          dark: '#d97706',
        },
        danger: {
          DEFAULT: '#ef4444',
          light: '#f87171',
          dark: '#dc2626',
        },
        // Q.18.ZIP.A — Palantir industrial accent (additive, não substitui o teal)
        'accent-orange': {
          DEFAULT: '#f97316',
          light: '#fb923c',
          soft: 'rgba(249, 115, 22, 0.12)',
          bd: 'rgba(249, 115, 22, 0.35)',
        },
        purple: {
          DEFAULT: '#b780ff',
          light: '#c89eff',
          soft: 'rgba(183, 128, 255, 0.12)',
        },
      },
      fontFamily: {
        // Q.23.A — só Geist + Geist Mono (fontes legacy Inter/JetBrains/DM Sans/
        // Space Grotesk removidas; nenhum .tsx as referenciava).
        sans: ['Geist', 'system-ui', 'sans-serif'],
        mono: ['Geist Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        // Q.18.ZIP.design2 — base 13px (era 14px Tailwind default)
        base: ['13px', { lineHeight: '1.45' }],
      },
      boxShadow: {
        'card': '0 4px 16px rgba(0, 0, 0, 0.3), 0 2px 8px rgba(0, 0, 0, 0.2)',
        'card-hover': '0 8px 24px rgba(0, 0, 0, 0.4), 0 4px 12px rgba(0, 0, 0, 0.3)',
        'elevated': '0 12px 40px rgba(0, 0, 0, 0.5), 0 6px 20px rgba(0, 0, 0, 0.4)',
        'glow-teal': '0 0 24px rgba(20, 184, 166, 0.4)',
        'glow-blue': '0 0 24px rgba(59, 130, 246, 0.4)',
        'glow-green': '0 0 24px rgba(16, 185, 129, 0.4)',
        'glow-amber': '0 0 24px rgba(245, 158, 11, 0.4)',
        'glow-red': '0 0 24px rgba(239, 68, 68, 0.4)',
        'inner-glow': 'inset 0 0 20px rgba(20, 184, 166, 0.1)',
      },
      borderRadius: {
        // Q.52.A — raios generosos Apple-style (matching --r-* do NELO.html)
        xs: '6px',    // matches --r-xs
        sm: '8px',    // matches --r-sm
        md: '10px',   // matches --r-md
        lg: '14px',   // matches --r-lg
        xl: '18px',   // matches --r-xl
        '2xl': '22px',// matches --r-2xl
        '3xl': '1.5rem',
      },
      backgroundImage: {
        'gradient-dark': 'linear-gradient(135deg, #0a0f1a 0%, #111827 50%, #0f172a 100%)',
        'gradient-card': 'linear-gradient(135deg, rgba(20, 184, 166, 0.1) 0%, rgba(17, 24, 39, 0.8) 100%)',
        'gradient-accent': 'linear-gradient(135deg, #0d9488 0%, #14b8a6 50%, #2dd4bf 100%)',
        'gradient-blue': 'linear-gradient(135deg, #2563eb 0%, #3b82f6 50%, #60a5fa 100%)',
        'gradient-glow': 'radial-gradient(ellipse at center, rgba(20, 184, 166, 0.15) 0%, transparent 70%)',
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'shimmer': 'shimmer 1.5s infinite',
        'float': 'float 3s ease-in-out infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(20, 184, 166, 0.3)' },
          '50%': { boxShadow: '0 0 30px rgba(20, 184, 166, 0.5)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
