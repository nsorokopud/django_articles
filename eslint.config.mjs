import globals from 'globals';
import pluginJs from '@eslint/js';

/** @type {import('eslint').Linter.Config[]} */
export default [
  { languageOptions: { globals: globals.browser } },
  {
    files: ['**/*.js'],
    ignores: ['static/js/notifications/**/*.js'],
    languageOptions: { sourceType: 'script' },
  },
  {
    files: ['static/js/notifications/**/*.js'],
    languageOptions: {
      sourceType: 'module',
      globals: {
        bootstrap: 'readonly',
        luxon: 'readonly',
        Cookies: 'readonly',
      },
    },
  },
  pluginJs.configs.recommended,
  {
    files: ['static/js/**/*.js'],
    rules: {
      'no-undef': 'off',
      'no-unused-vars': 'off',
    },
  },
  {
    ignores: ['npm_modules/', 'staticfiles/', '*env/'],
  },
];
