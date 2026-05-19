// Setup global das suites Vitest (Q.60.F) — corre antes de cada ficheiro
// de teste (registado em vitest.config.ts `setupFiles`).
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Desmonta a árvore React e limpa o DOM entre testes — sem isto, queries
// como `getByText` veriam restos do teste anterior.
afterEach(() => {
  cleanup();
});

// Seed de localStorage de dev: o `lib/api.ts` lê tenant/user/role daqui para
// montar os headers. Tenant de dev é `...001` — o zero-UUID é rejeitado por
// design (CLAUDE.md, Q.12 Onda 0.1). Limpo antes de cada teste para que um
// teste que mexa no localStorage não contamine o seguinte.
beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('tenant_id', '00000000-0000-0000-0000-000000000001');
  localStorage.setItem('user_id', '00000000-0000-0000-0000-000000000001');
  localStorage.setItem('user_role', 'admin');
  localStorage.setItem('auth_token', 'dev-test-token');
});
