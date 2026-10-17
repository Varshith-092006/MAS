/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', 'monospace'],
      },
      colors: {
        // Extended research dashboard palette
        slate: {
          850: '#0f1729',
          925: '#080e1a',
          950: '#020617',
        },
      },
      animation: {
        'fade-in': 'fade-in 0.3s ease-out forwards',
        'slide-in': 'slide-in 0.2s ease-out forwards',
        'shimmer': 'shimmer 2s infinite',
        'glow-pulse': 'glow-pulse 2s ease-in-out infinite',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: 0, transform: 'translateY(4px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
        'slide-in': {
          from: { opacity: 0, transform: 'translateX(-8px)' },
          to:   { opacity: 1, transform: 'translateX(0)' },
        },
        shimmer: {
          from: { backgroundPosition: '-200% 0' },
          to:   { backgroundPosition: '200% 0' },
        },
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 12px rgba(6,182,212,0.15)' },
          '50%':       { boxShadow: '0 0 24px rgba(6,182,212,0.30)' },
        },
      },
      boxShadow: {
        'glow-cyan':   '0 0 20px rgba(6,182,212,0.15), 0 0 40px rgba(6,182,212,0.05)',
        'glow-indigo': '0 0 20px rgba(99,102,241,0.15), 0 0 40px rgba(99,102,241,0.05)',
      },
    },
  },
  plugins: [],
}
