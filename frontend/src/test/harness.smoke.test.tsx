// Smoke do harness de testes do frontend (Q.60.F).
//
// Prova que jsdom + React Testing Library + os providers + os matchers do
// jest-dom estão de pé. Não testa domínio nenhum — é o teste que falha
// primeiro se a infra de testes partir.
import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from './renderWithProviders';

describe('harness de testes do frontend', () => {
  it('renderiza um componente dentro dos providers', () => {
    renderWithProviders(<p>olá fábrica</p>);
    expect(screen.getByText('olá fábrica')).toBeInTheDocument();
  });

  it('respeita a entrada inicial de rota do MemoryRouter', () => {
    renderWithProviders(<p>página</p>, { route: '/qualidade?tab=resumo' });
    expect(screen.getByText('página')).toBeInTheDocument();
  });

  it('o seed de localStorage do setup.ts está activo', () => {
    expect(localStorage.getItem('tenant_id')).toBe(
      '00000000-0000-0000-0000-000000000001',
    );
  });
});
