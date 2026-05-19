// Gate ZERO MOCKS (Q.60.A) — regra anti-MOCK isolada da dívida de lint.
//
// `eslint .` no projecto tem ~665 erros pré-existentes (no-explicit-any, etc.),
// por isso não serve de guardrail. Este config corre SÓ a regra anti-MOCK:
// `npm run lint:mocks` → exit≠0 apenas quando aparece um mock no frontend.
//
// O invariante: frontend/src/ nunca tem `const MOCK_X = [...]` nem fallbacks
// placeholder `data ?? [{...}]` / `data || [{...}]` (CLAUDE.md, Luis 2026-05-06).
import { defineConfig } from 'eslint/config'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

// Exportada também para o eslint.config.js principal (feedback no editor).
export const zeroMocksRestrictedSyntax = [
  'error',
  {
    selector: 'VariableDeclarator[id.name=/^MOCK_/]',
    message:
      'ZERO MOCKS (CLAUDE.md): proibida constante MOCK_ no frontend. Liga à API real e mostra <EmptyState>.',
  },
  {
    selector: "LogicalExpression[operator='??'] > ArrayExpression.right > ObjectExpression",
    message:
      'ZERO MOCKS (CLAUDE.md): proibido fallback placeholder `?? [{...}]`. Usa empty/error state explícito.',
  },
  {
    selector: "LogicalExpression[operator='||'] > ArrayExpression.right > ObjectExpression",
    message:
      'ZERO MOCKS (CLAUDE.md): proibido fallback placeholder `|| [{...}]`. Usa empty/error state explícito.',
  },
]

export default defineConfig([
  { ignores: ['dist'] },
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: { parser: tseslint.parser },
    // Os `eslint-disable` do código referem regras que este gate não activa;
    // não é trabalho deste config avaliá-los.
    linterOptions: { reportUnusedDisableDirectives: 'off' },
    // Plugins registados só para os comentários `eslint-disable` espalhados
    // pelo código resolverem o nome da regra — nenhuma destas regras é activada.
    plugins: {
      '@typescript-eslint': tseslint.plugin,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: { 'no-restricted-syntax': zeroMocksRestrictedSyntax },
  },
])
