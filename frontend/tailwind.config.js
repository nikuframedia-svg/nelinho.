/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark theme backgrounds — aligned com nelo.html zip --bg-N
        dark: {
          900: '#0A0A0A',   // matches --bg-0 (page bg)
          800: '#111113',   // matches --bg-1 (card bg)
          700: '#16171A',   // matches --bg-2 (nested)
          600: '#1E1F23',   // matches --bg-3 (track / hover)
          500: '#2A2B30',   // matches --bg-4 (elevated)
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
        // Text colors for dark theme — aligned com nelo.html zip --fg-N
        'text-dark': {
          primary:   '#FAFAFA',  // matches --fg-0
          secondary: '#D4D4D8',  // matches --fg-1
          tertiary:  '#A1A1AA',  // matches --fg-2
          muted:     '#71717A',  // matches --fg-3
        },
        // Border tokens (zip --bd-N) accessible as Tailwind utility classes
        'bd-1': '#25262B',
        'bd-2': '#34353B',
        'bd-3': '#4A4C54',
        // Status colors (zip-aligned, used inline)
        green:  { DEFAULT: '#22C55E' },
        yellow: { DEFAULT: '#EAB308' },
        red:    { DEFAULT: '#EF4444' },
        blue:   { DEFAULT: '#3B82F6' },
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
        // Q.18.ZIP.tokens — Inter primária matching nelo.html zip body
        sans: ['Inter', 'Geist', 'Space Grotesk', 'DM Sans', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Geist Mono', 'Fira Code', 'monospace'],
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
        // Q.18.ZIP.tokens — alinhar com zip --r-{sm,md,lg,xl}
        sm: '6px',
        md: '8px',
        lg: '12px',   // era 0.5rem (8px) Tailwind default
        xl: '16px',   // era 0.75rem (12px) Tailwind default
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
