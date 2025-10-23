module.exports = {
  content: [
    '/templates/*.{html,js}',
  ],
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
    './templates/**/*.{html,js}',
    './components/**/*.{html,js}',
  ],
  // ...
}