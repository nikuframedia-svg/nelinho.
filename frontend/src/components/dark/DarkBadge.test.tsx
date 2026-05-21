// Testes da primitiva DarkBadge (Q.60.G).
//
// DarkBadge é um componente de apresentação puro — sem rede, sem providers.
// Guarda as 8 variantes (conjunto fechado: CLAUDE.md proíbe inventar
// green/yellow/red) e o mapa status→variante do StatusBadge.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DarkBadge, StatusBadge } from './DarkBadge';

describe('DarkBadge', () => {
  it('renderiza o conteúdo', () => {
    render(<DarkBadge>12 barcos</DarkBadge>);
    expect(screen.getByText('12 barcos')).toBeInTheDocument();
  });

  it.each([
    ['success', 'badge-success'],
    ['warning', 'badge-warning'],
    ['danger', 'badge-danger'],
    ['info', 'badge-primary'],
    ['neutral', 'badge-neutral'],
    ['accent', 'badge-accent'],
    ['primary', 'badge-primary'],
    ['teal', 'badge-teal'],
  ] as const)('variant "%s" aplica a classe .%s', (variant, cls) => {
    render(<DarkBadge variant={variant}>x</DarkBadge>);
    expect(screen.getByText('x')).toHaveClass('badge-dark', cls);
  });

  it('dot=true renderiza o ponto de estado', () => {
    const { container } = render(<DarkBadge dot>online</DarkBadge>);
    expect(container.querySelector('.status-dot')).not.toBeNull();
  });

  it('sem dot não renderiza o ponto', () => {
    const { container } = render(<DarkBadge>offline</DarkBadge>);
    expect(container.querySelector('.status-dot')).toBeNull();
  });

  it('pulse adiciona animate-pulse e respeita prefers-reduced-motion', () => {
    render(<DarkBadge pulse>novo</DarkBadge>);
    expect(screen.getByText('novo')).toHaveClass(
      'animate-pulse',
      'motion-reduce:animate-none',
    );
  });
});

describe('StatusBadge', () => {
  it('mapeia status "active" para variante success', () => {
    render(<StatusBadge status="active" />);
    expect(screen.getByText('Active')).toHaveClass('badge-success');
  });

  it('mapeia status "error" para variante danger', () => {
    render(<StatusBadge status="error" />);
    expect(screen.getByText('Error')).toHaveClass('badge-danger');
  });

  it('status fora do conjunto cai em "inactive"', () => {
    // @ts-expect-error — robustez ao caso defensivo `|| statusConfig.inactive`
    render(<StatusBadge status="desconhecido" />);
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });
});
