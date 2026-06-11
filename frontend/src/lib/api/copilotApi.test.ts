/**
 * Q.173.AL — testes para cubeToCopilotResponse:
 * verifica que o campo explicacao é preservado (ou ausente) corretamente.
 */
import { describe, expect, it } from 'vitest';
import { cubeToCopilotResponse } from './copilotApi';

// Resposta Cube mínima com status ok e explicacao completa
const EXPLICACAO_FULL = {
  tabela: 'mart_qualidade',
  measures: [
    { nome: 'qualidade.taxa_defeitos', formula_sql: 'COUNT(CASE WHEN defeito THEN 1 END)::float / COUNT(*)' },
  ],
  filtros: ['qualidade.fase equals 40'],
  periodo: '2026-05-01 a 2026-05-31',
  fonte: 'Cube',
};

describe('cubeToCopilotResponse', () => {
  it('preserva explicacao quando presente em status=ok', () => {
    const r = cubeToCopilotResponse({
      status: 'ok',
      narration: 'Taxa de defeitos na fase 40 é 3,2%.',
      data: [{ 'qualidade.taxa_defeitos': 0.032 }],
      explicacao: EXPLICACAO_FULL,
    });
    expect(r.explicacao).toBeDefined();
    expect(r.explicacao!.tabela).toBe('mart_qualidade');
    expect(r.explicacao!.measures).toHaveLength(1);
    expect(r.explicacao!.measures[0].formula_sql).toContain('COUNT');
    expect(r.explicacao!.filtros).toContain('qualidade.fase equals 40');
    expect(r.explicacao!.periodo).toBe('2026-05-01 a 2026-05-31');
    expect(r.explicacao!.fonte).toBe('Cube');
  });

  it('explicacao fica null quando o backend não a envia (status no_data)', () => {
    const r = cubeToCopilotResponse({
      status: 'no_data',
      narration: 'Não há dados para esses filtros.',
      data: [],
    });
    expect(r.explicacao).toBeNull();
  });

  it('explicacao fica null quando o backend não a envia (status guard_failed)', () => {
    const r = cubeToCopilotResponse({
      status: 'guard_failed',
      data: [{ 'qualidade.taxa_defeitos': 99 }],
      warnings: ['guard rejeitou número inventado'],
    });
    expect(r.explicacao).toBeNull();
  });

  it('explicacao nula explícita é preservada como null', () => {
    const r = cubeToCopilotResponse({
      status: 'ok',
      narration: 'Resposta sem explicacao explícita.',
      data: [{ 'producao_ofs_em_curso.total': 42 }],
      explicacao: null,
    });
    expect(r.explicacao).toBeNull();
  });

  it('narration é mapeada para summary', () => {
    const r = cubeToCopilotResponse({
      status: 'ok',
      narration: 'Há 42 OFs em curso.',
      data: [{ 'producao_ofs_em_curso.total': 42 }],
      explicacao: EXPLICACAO_FULL,
    });
    expect(r.summary).toBe('Há 42 OFs em curso.');
  });

  it('status=ok produz validation_passed=true no meta', () => {
    const r = cubeToCopilotResponse({
      status: 'ok',
      narration: 'ok',
      data: [{ m: 1 }],
    });
    expect(r.meta.validation_passed).toBe(true);
  });

  it('status=no_data produz warning INSUFFICIENT_EVIDENCE', () => {
    const r = cubeToCopilotResponse({
      status: 'no_data',
      data: [],
    });
    expect(r.warnings.some((w) => w.code === 'INSUFFICIENT_EVIDENCE')).toBe(true);
  });

  it('explicacao com measures vazia é preservada', () => {
    const r = cubeToCopilotResponse({
      status: 'ok',
      narration: 'Resultado.',
      data: [{ m: 1 }],
      explicacao: { ...EXPLICACAO_FULL, measures: [] },
    });
    expect(r.explicacao!.measures).toHaveLength(0);
  });
});
