/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      fontSize: {
        // 04 §2.2 — metadatos / UUID / RFC.
        '2xs': ['11px', '14px'],
      },
      colors: {
        // Alias semántico de la marca; los matices vienen de la paleta Indigo.
        brand: {
          50: '#EEF2FF',
          200: '#C7D2FE',
          600: '#4F46E5',
          700: '#4338CA',
          900: '#312E81',
          950: '#1E1B4B',
        },
      },
    },
  },
  plugins: [],
}
