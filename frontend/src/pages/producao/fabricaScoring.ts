/**
 * fabricaScoring — adequação operador ↔ barco (Q.52.F · Q.53.I).
 *
 * Port do `scoreFor` do design NELO, religado a dados REAIS:
 *   - quality-score  → score 0-10 base + penalização por defect_rate
 *   - skill-matrix   → match de fase (can_do / nivel / ops_count)
 *   - qualification  → Q.53.I: recência, versatilidade e produtividade,
 *                      os 3 sinais novos que o workforce passou a expor
 *                      (`/qualification-metrics`).
 *
 * Função pura: recebe os dados já carregados e devolve `{ fit, reasons,
 * impact }`. ZERO MOCKS — se um operador não tem dados de qualidade,
 * skills ou métricas, o fit degrada com honestidade (razão "sem
 * histórico"), nunca inventa.
 */

import type {
  QualityScoreResult,
  SkillMatrixResult,
} from '../../lib/api';
import type { QualificationMetrics } from './fabricaApi';

export interface FitReason {
  /** Texto curto da razão. */
  text: string;
  /** Tom — mapeia a variantes do DarkBadge. */
  tone: 'success' | 'info' | 'danger' | 'warning';
}

export interface FitResult {
  /** Adequação 0-10. */
  fit: number;
  /** Até 3 razões legíveis. */
  reasons: FitReason[];
  /** Impacto € estimado se atribuído (positivo = bom). */
  impact: number;
}

/** Perfil de operador agregado para o fit-scoring. */
export interface WorkerProfile {
  id: string;
  name: string;
  /** Resultado de quality-score (pode faltar → sem histórico). */
  quality?: QualityScoreResult;
  /** Matriz de skills (pode faltar → sem histórico). */
  skills?: SkillMatrixResult;
  /**
   * Q.53.I — métricas de qualificação (recência/versatilidade/
   * produtividade). Pode faltar → o scoring ignora esse eixo.
   */
  metrics?: QualificationMetrics;
}

/**
 * Calcula a adequação de um operador a um barco numa dada fase.
 *
 * @param worker  perfil agregado do operador
 * @param phaseName nome da fase actual do barco (current_phase_name)
 */
export function scoreFor(
  worker: WorkerProfile,
  phaseName: string | null,
): FitResult {
  const reasons: FitReason[] = [];
  let impact = 0;

  // ── Base: quality-score 0-1 → 0-10 ──────────────────────────────────────
  // Sem quality-score → base neutra 5.0 + razão honesta.
  const q = worker.quality;
  let fit = q ? Math.max(0, Math.min(10, q.score * 10)) : 5;
  if (!q || q.method === 'default_no_history') {
    reasons.push({
      text: 'Sem histórico de qualidade',
      tone: 'warning',
    });
  }

  // ── Match de fase via skill-matrix ──────────────────────────────────────
  if (phaseName) {
    const phaseLc = phaseName.toLowerCase();
    const row = worker.skills?.phases.find((p) => {
      const name = (p.phase_name ?? p.phase_id).toLowerCase();
      return name.includes(phaseLc) || phaseLc.includes(name);
    });
    if (row && row.can_do) {
      const nivel = row.nivel ?? 1;
      if (nivel >= 3 || row.ops_count >= 50) {
        fit += 1.4;
        impact += 280;
        reasons.push({
          text: `Especialista · ${row.ops_count} ops em ${phaseName}`,
          tone: 'success',
        });
      } else {
        fit += 0.6;
        impact += 120;
        reasons.push({
          text: `Tem skill ${phaseName} (nível ${nivel})`,
          tone: 'info',
        });
      }
    } else if (worker.skills) {
      fit -= 2.2;
      impact -= 320;
      reasons.push({
        text: `Sem experiência em ${phaseName}`,
        tone: 'danger',
      });
    }
  }

  // ── Penalização por taxa de defeito ─────────────────────────────────────
  if (q) {
    if (q.defect_rate < 0.05 && q.operations >= 10) {
      fit += 0.8;
      impact += 180;
      reasons.push({
        text: `Taxa de erro ${(q.defect_rate * 100).toFixed(1)}%`,
        tone: 'success',
      });
    } else if (q.defect_rate > 0.12) {
      fit -= 1.5;
      impact -= 240;
      reasons.push({
        text: `Erro alto ${(q.defect_rate * 100).toFixed(0)}%`,
        tone: 'danger',
      });
    }
  }

  // ── Q.53.I — 3 sinais de qualificação: recência / versatilidade /
  //    produtividade. Cada eixo ajusta o fit; sem dados, é ignorado
  //    (nunca inventa). Os pesos são menores que o da fase para não
  //    afogar o match de skill, que continua a ser o eixo dominante.
  const m = worker.metrics;
  if (m) {
    // Recência — operador "fresco" na fábrica vale mais; "frio" penaliza.
    if (m.recency_days !== null) {
      if (m.recency_days <= 14) {
        fit += 0.7;
        impact += 90;
        reasons.push({
          text: `Activo há ${m.recency_days}d`,
          tone: 'success',
        });
      } else if (m.recency_days > 90) {
        fit -= 1.0;
        impact -= 130;
        reasons.push({
          text: `Sem operações há ${m.recency_days}d`,
          tone: 'warning',
        });
      }
    }

    // Versatilidade — quantas fases distintas domina (flexibilidade).
    if (m.versatility >= 8) {
      fit += 0.6;
      impact += 100;
      reasons.push({
        text: `Polivalente · ${m.versatility} fases`,
        tone: 'info',
      });
    } else if (m.versatility > 0 && m.versatility <= 2) {
      fit -= 0.5;
      reasons.push({
        text: `Pouca polivalência · ${m.versatility} fase(s)`,
        tone: 'warning',
      });
    }

    // Produtividade — operações por dia ao longo do histórico.
    if (m.productivity !== null) {
      if (m.productivity >= 3) {
        fit += 0.7;
        impact += 120;
        reasons.push({
          text: `Ritmo ${m.productivity.toFixed(1)} ops/dia`,
          tone: 'success',
        });
      } else if (m.productivity > 0 && m.productivity < 1) {
        fit -= 0.6;
        impact -= 90;
        reasons.push({
          text: `Ritmo baixo ${m.productivity.toFixed(1)} ops/dia`,
          tone: 'warning',
        });
      }
    }
  }

  return {
    fit: Math.max(0, Math.min(10, fit)),
    reasons: reasons.slice(0, 3),
    impact,
  };
}

/** Tom do número de fit consoante o valor. */
export function fitTone(fit: number): 'green' | 'yellow' | 'red' {
  if (fit > 7) return 'green';
  if (fit > 5) return 'yellow';
  return 'red';
}
