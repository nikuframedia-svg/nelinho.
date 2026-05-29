/**
 * Playwright E2E (Q.118.U) — smoke de browser das 4 páginas.
 * ===========================================================
 *
 * Arranca o vite dev (npm run dev :5173) e corre os specs em e2e/. O backend
 * pode estar em baixo: os specs verificam que a SHELL renderiza (abas, headers,
 * navegação por ?tab=) e que não há erros JS não-tratados — os estados vazios
 * por falta de dados são esperados (ZERO MOCKS). Com o stack a correr (/nitro),
 * os mesmos specs validam dados reais.
 */
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 7_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
