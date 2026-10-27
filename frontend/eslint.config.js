import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'node_modules'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommendedTypeChecked,
      reactHooks.configs.flat.recommended,
      jsxA11y.flatCategories?.recommended ?? jsxA11y.flatConfigs.recommended,
      prettier,
    ],
    plugins: { 'react-refresh': reactRefresh },
    languageOptions: {
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/consistent-type-imports': 'error',
      // Scrollable regions must be focusable so keyboard users can scroll them.
      'jsx-a11y/no-noninteractive-tabindex': ['error', { tags: [], roles: ['tabpanel', 'region'] }],
      'react-refresh/only-export-components': ['error', { allowConstantExport: true }],
    },
  },
  {
    // CLAUDE.md: components under 200 lines.
    files: ['src/**/*.tsx'],
    ignores: ['src/**/*.test.tsx'],
    rules: { 'max-lines': ['error', { max: 200, skipBlankLines: true, skipComments: true }] },
  },
  {
    files: ['eslint.config.js'],
    languageOptions: { globals: globals.node },
    ...tseslint.configs.disableTypeChecked,
  },
);
