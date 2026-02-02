/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        reader: {
          bg: '#faf9f6',
          text: '#2d2d2d',
          highlight: '#fef08a',
          muted: '#6b7280',
        }
      },
      fontFamily: {
        reader: ['Georgia', 'Cambria', 'Times New Roman', 'serif'],
      },
    }
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}

