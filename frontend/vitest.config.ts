import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

// Vitest — runner de testes unitários do frontend.
//
// Q.60.F: `environment: 'jsdom'` — a app é React e os testes de componente
// (React Testing Library) precisam de DOM. As poucas suites de função pura
// (`fabricaScoring`, `crisisScenarios`, `SimDetail`) correm na mesma; o custo
// do jsdom à escala destas suites é negligível.
//
// `setupFiles` regista os matchers do jest-dom e faz cleanup entre testes.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
});
