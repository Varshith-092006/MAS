/** @type {import('tailwindcss').Config} */
import colors from 'tailwindcss/colors';

// Professional light theme (DEC-051).
// The components were written for a dark theme (e.g. bg-slate-900 cards, text-slate-400 body
// text, text-cyan-400 accents). Instead of rewriting ~1,300 class names, the palette is remapped
// here: dark shades become light surfaces, light shades become dark text, and the neon accents
// (cyan / violet / purple) collapse into one calm blue + indigo pair.

// Neutral scale: low numbers = dark text, high numbers = light surfaces.
const neutral = {
  50: '#0f172a',
  100: '#0f172a',
  200: '#1e293b',
  300: '#334155',
  400: '#475569',
  500: '#64748b',
  600: '#94a3b8',
  700: '#cbd5e1',
  800: '#e2e8f0',
  850: '#eef2f6',
  900: '#ffffff',
  925: '#f8fafc',
  950: '#f3f5f8',
};

// Hue scale for a light background: text shades get darker, tint shades get lighter,
// and 500/600 stay solid enough for buttons with white text.
const lightHue = (s) => ({
  50: s[900],
  100: s[900],
  200: s[800],
  300: s[700],
  400: s[700],
  500: s[700],
  600: s[600],
  700: s[700],
  800: s[200],
  900: s[100],
  950: s[50],
});

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'Cascadia Code', 'Consolas', 'monospace'],
      },
      colors: {
        slate: neutral,
        cyan: lightHue(colors.blue),
        indigo: lightHue(colors.indigo),
        violet: lightHue(colors.indigo),
        purple: lightHue(colors.indigo),
        teal: lightHue(colors.teal),
        amber: lightHue(colors.amber),
        emerald: lightHue(colors.emerald),
        rose: lightHue(colors.rose),
      },
      animation: {
        'fade-in': 'fade-in 0.2s ease-out forwards',
        'slide-in': 'slide-in 0.2s ease-out forwards',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: 0, transform: 'translateY(2px)' },
          to: { opacity: 1, transform: 'translateY(0)' },
        },
        'slide-in': {
          from: { opacity: 0, transform: 'translateX(-4px)' },
          to: { opacity: 1, transform: 'translateX(0)' },
        },
      },
      boxShadow: {
        'glow-cyan': '0 1px 2px rgba(15,23,42,0.06)',
        'glow-indigo': '0 1px 2px rgba(15,23,42,0.06)',
      },
    },
  },
  plugins: [],
};
