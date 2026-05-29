/**
 * panel.spec.ts — smoke E2E das 4 páginas do painel (Q.118.U).
 *
 * Verifica que cada página renderiza a shell, as sub-abas navegam por ?tab=,
 * e que NÃO há erros JS não-tratados (page errors). Erros de rede (backend em
 * baixo) são esperados e ignorados — testa-se a integridade do React, não dados.
 */
import { test, expect, type Page } from '@playwright/test';

// Semear auth de dev antes de qualquer script da app correr (senão o lib/api
// não tem tenant/user e algumas páginas comportam-se como deslogado).
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('tenant_id', '00000000-0000-0000-0000-000000000001');
    localStorage.setItem('user_id', '00000000-0000-0000-0000-000000000001');
    localStorage.setItem('user_role', 'admin');
    localStorage.setItem('auth_token', 'dev-e2e-token');
  });
});

/** Captura erros JS não-tratados (não conta falhas de fetch/rede). */
function trackPageErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(String(err)));
  return errors;
}

test('Decisões — 3 sub-abas navegam e renderizam', async ({ page }) => {
  const errors = trackPageErrors(page);
  await page.goto('/decisoes');
  await expect(page.getByRole('tab', { name: /Decidir/ })).toBeVisible();
  await expect(page.getByRole('tab', { name: /Simulações/ })).toBeVisible();
  await expect(page.getByRole('tab', { name: /Histórico/ })).toBeVisible();

  await page.goto('/decisoes?tab=simulacoes');
  await expect(page.getByText('Esta decisão')).toBeVisible();

  await page.goto('/decisoes?tab=historico');
  await expect(page.getByText('Histórico de decisões')).toBeVisible();

  expect(errors, errors.join('\n')).toHaveLength(0);
});

test('Overall — carrega a vista de planeamento', async ({ page }) => {
  const errors = trackPageErrors(page);
  await page.goto('/overall');
  // o seletor de vistas (Por fase/barco/pessoa/expedição) está sempre presente
  await expect(page.getByText(/Por fase|Planeamento|fase/i).first()).toBeVisible();
  expect(errors, errors.join('\n')).toHaveLength(0);
});

test('LLM — 4 tabs incl. Alertas', async ({ page }) => {
  const errors = trackPageErrors(page);
  await page.goto('/llm');
  await expect(page.getByRole('tab', { name: /Chat/ })).toBeVisible();
  await expect(page.getByRole('tab', { name: /KPIs/ })).toBeVisible();
  await expect(page.getByRole('tab', { name: /Alertas/ })).toBeVisible();
  await expect(page.getByRole('tab', { name: /Regras/ })).toBeVisible();

  await page.goto('/llm?tab=alertas');
  await expect(page.getByText(/Alertas proativos/)).toBeVisible();
  expect(errors, errors.join('\n')).toHaveLength(0);
});

test('Configurações — carrega e tem aba Aprendizagem', async ({ page }) => {
  const errors = trackPageErrors(page);
  await page.goto('/configuracoes?tab=aprendizagem');
  await expect(page.getByText(/Aprendizagem|Centro de aprendizagem/i).first()).toBeVisible();
  expect(errors, errors.join('\n')).toHaveLength(0);
});
