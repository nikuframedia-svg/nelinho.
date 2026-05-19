import { defineConfig } from 'vitest/config';
import path from 'path';

// Vitest — runner de testes unitários do frontend (Q.55.A).
// Mínimo de propósito: a maioria da lógica testável são funções puras
// (ex: `fabricaScoring`). Ambiente `node` chega; quem precisar de DOM
// declara `// @vitest-environment jsdom` no topo do ficheiro de teste.
export default defineConfig({
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
});
