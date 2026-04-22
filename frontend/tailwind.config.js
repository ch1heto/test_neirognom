/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        panel: 'rgba(20, 30, 54, 0.52)',
        stroke: 'rgba(255,255,255,0.14)',
        soft: 'rgba(255,255,255,0.08)',
      },
      boxShadow: {
        glow: '0 20px 80px rgba(112, 87, 255, 0.18)',
        glass: '0 12px 40px rgba(7, 14, 27, 0.35)',
      },
      backdropBlur: {
        xs: '2px',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        pulseSoft: {
          '0%, 100%': { opacity: '0.75', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.04)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        pulseSoft: 'pulseSoft 2.4s ease-in-out infinite',
        slideUp: 'slideUp 0.4s ease-out',
        shimmer: 'shimmer 3s linear infinite',
      },
    },
  },
  plugins: [],
}
