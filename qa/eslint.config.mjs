import eslint from '@eslint/js';

export default [
  {
    files: ['**/*.mjs'],
    rules: {
      ...eslint.configs.recommended.rules,
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: Object.fromEntries(
        [
          'process',
          'console',
          'URL',
          'Buffer',
          'fetch',
          'AbortSignal',
          'setTimeout',
          'globalThis',
          'document',
          'location',
          'innerWidth',
          'innerHeight',
          'window',
          'getComputedStyle',
        ].map((name) => [name, 'readonly']),
      ),
    },
  },
];
