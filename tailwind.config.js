module.exports = {
  content: [
    '/kkoala/templates/*.{html,js}',
  ],
  darkMode: 'class',
  theme: {
    extend: {},
  },
  variants: {
    extend: {},
  },
  plugins: [
    'postcss',
  ],
  
}

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './kkoala/templates/**/*.{html,js}',
    './kkoala/components/**/*.{html,js}',
  ],
  darkMode: 'class',
  theme: {
    extend: {},
  },
  variants: {
    extend: {},
  },
  plugins: [
    'postcss',
  ],
  // ...
}