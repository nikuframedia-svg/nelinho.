/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Fonte-de-verdade da paleta = index.css @theme (OKLCH). Os HEX aqui
        // são equivalentes aproximados — Tailwind não lê OKLCH nativo. Ao mudar
        // uma cor, mudar primeiro no @theme e refletir o HEX aqui (Q.23.A).
        // Dark theme backgrounds — Q.18.ZIP.design2 OKLCH (HEX equivalents)
        // hue 250 = cool blue-gray neutral (Palantir-like)
        dark: {
          900: '#1d2025',   // matches --bg-0 oklch(0.158 0.008 250)
          800: '#252830',   // matches --bg-1 oklch(0.195 0.008 250)
          700: '#2c2f37',   // matches --bg-2 oklch(0.225 0.009 250)
          600: '#373a43',   // matches --bg-3 oklch(0.265 0.010 250)
          500: '#42454f',   // matches --bg-4 oklch(0.305 0.011 250)
        },
        // Accent - Teal
        accent: {
          50: '#f0fdfa',
          100: '#ccfbf1',
          200: '#99f6e4',
          300: '#5eead4',
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488',
          700: '#0f766e',
          800: '#115e59',
          900: '#134e4a',
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
        // Text colors — Q.18.ZIP.design2 OKLCH (HEX equivalents)
        'text-dark': {
          primary:   '#f0f1f3',  // matches --fg-0 oklch(0.96 0.005 250)
          secondary: '#c8cbd0',  // matches --fg-1 oklch(0.82 0.008 250)
          tertiary:  '#888d96',  // matches --fg-2 oklch(0.62 0.012 250)
          muted:     '#5a5f68',  // matches --fg-3 oklch(0.45 0.015 250)
        },
        // Border tokens (--bd-N) accessible as Tailwind utility classes
        'bd-1': '#3b3e47',  // matches --bd-1 oklch(0.295 0.011 250)
        'bd-2': '#494d58',  // matches --bd-2 oklch(0.355 0.013 250)
        'bd-3': '#5a5f68',  // matches --bd-3 oklch(0.420 0.014 250)
        // Status colors (design2 desaturated calm — HEX approximations)
        green:  { DEFAULT: '#5fc77e' },  // oklch(0.78 0.14 155)
        yellow: { DEFAULT: '#d6b146' },  // oklch(0.82 0.14 90)
        red:    { DEFAULT: '#e76060' },  // oklch(0.72 0.18 25)
        blue:   { DEFAULT: '#7aa3d8' },  // oklch(0.72 0.14 245)
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
        // Q.18.ZIP.design2 — refinado, mais pequeno (matching design package)
        sm: '4px',    // era 6px
        md: '6px',    // era 8px
        lg: '10px',   // era 12px (matching --r-lg do design package)
        xl: '14px',   // era 16px
        '2xl': '1rem',
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
