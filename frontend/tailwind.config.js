/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        qualys: {
          red: '#e3001b',
          dark: '#1a1a2e',
          panel: '#16213e',
          card: '#0f3460',
        },
      },
      keyframes: {
        'zap-flash': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '20%': { opacity: '0.2', transform: 'scale(0.8)' },
          '40%': { opacity: '1', transform: 'scale(1.3)' },
          '60%': { opacity: '0.3', transform: 'scale(0.85)' },
          '80%': { opacity: '1', transform: 'scale(1.1)' },
        },
        'lightning-strike': {
          '0%':   { boxShadow: 'none', borderColor: 'rgba(234,88,12,0.4)' },
          '10%':  { boxShadow: '0 0 8px 2px rgba(251,146,60,0.8)', borderColor: 'rgba(251,146,60,1)' },
          '20%':  { boxShadow: 'none', borderColor: 'rgba(234,88,12,0.2)' },
          '30%':  { boxShadow: '0 0 16px 4px rgba(251,146,60,0.6)', borderColor: 'rgba(251,146,60,0.9)' },
          '50%':  { boxShadow: 'none', borderColor: 'rgba(234,88,12,0.4)' },
          '100%': { boxShadow: 'none', borderColor: 'rgba(234,88,12,0.4)' },
        },
        'zap-ripple': {
          '0%':   { transform: 'scale(0.6)', opacity: '0.8' },
          '100%': { transform: 'scale(2.4)', opacity: '0' },
        },
      },
      animation: {
        'zap-flash': 'zap-flash 1.8s ease-in-out infinite',
        'lightning-strike': 'lightning-strike 3s ease-in-out infinite',
        'zap-ripple': 'zap-ripple 1.8s ease-out infinite',
        'zap-ripple-delay': 'zap-ripple 1.8s ease-out 0.6s infinite',
      },
    },
  },
  plugins: [],
}
