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

// Q.61.07 — bloqueia `fetch(...)` directo em `src/pages/` e `src/components/`.
// `lib/api/` continua a ser o ÚNICO ponto que faz HTTP. Pages/components que
// queiram fazer um request novo: adicionam função em `lib/api/<domain>Api.ts`.
//
// **Severity = 'warn'** porque ha 50 sites pre-existentes (audit Q.61);
// o gate real de CI e `scripts/lint_drift_gate.py` (compara count vs
// baseline). Vaga 5 (Q.61.25) migra os 50; entao sobe para 'error'.
//
// Excepções permitidas:
//   * `src/lib/api/**`     — onde o `apiFetch` real vive.
//   * `src/test/**`        — testes podem fazer `fetch` para o MSW mock server.
//   * `src/mocks/**`       — MSW handlers.
export const noDirectFetchRestrictedSyntax = [
  'warn',
  {
    // CallExpression onde o callee é o identifier `fetch` (não membro,
    // ex: `apiFetch()` não bate; `window.fetch()` também não bate).
    selector: "CallExpression[callee.type='Identifier'][callee.name='fetch']",
    message:
      'Q.61.07: `fetch(...)` directo proibido em `src/pages/` e `src/components/`. ' +
      'Adiciona uma função em `src/lib/api/<domain>Api.ts` e usa-a aqui — fonte única + tracing.',
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
  // Q.61.07 — anti-fetch directo SÓ em pages/components.
  // `lib/api/`, testes e mocks ficam livres (vivem onde a chamada
  // tem de ser feita).
  {
    files: ['src/pages/**/*.{ts,tsx}', 'src/components/**/*.{ts,tsx}'],
    languageOptions: { parser: tseslint.parser },
    linterOptions: { reportUnusedDisableDirectives: 'off' },
    plugins: { '@typescript-eslint': tseslint.plugin },
    rules: { 'no-restricted-syntax': noDirectFetchRestrictedSyntax },
  },
])
