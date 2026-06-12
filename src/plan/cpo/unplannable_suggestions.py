"""Q.174.F5 — sugestões ACIONÁVEIS para a secção "não planeável".

Decisão do dono: «declarar inviável + porquê + recurso em falta + sugerir
alternativas». Cada template é CALCULÁVEL hoje com dados reais — nada de
"considere rever a capacidade" genérico (auditoria 2026-06-11 apanhou os
alertas sem remédio). Função pura sobre o state já carregado; corre 1× por
run, fora do hot-path.

Templates:
* BLOCKED_OPERADORES → operadores com HISTÓRICO da fase fora do pool atual
  (filtrados pelos gates de certificação/ativos — candidatos reais a
  qualificar/reativar), ou pool global vazio = formar alguém.
* BLOCKED_MOLDE     → moldes do modelo em manutenção (concluir reparação)
  ou nenhum molde registado para o modelo.
* BLOCKED_HORIZONTE → atrasar a OF n dias (excesso medido) ou alargar o
  horizonte de planeamento.
* SEM_ROTA          → definir rota/template para o modelo.
* BLOCKED_PRECEDENCIA → rota com dependências impossíveis (dados a corrigir).
* BLOCKED_COMPONENTE → acelerar a OF da peça (Q.174.F7).
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List

from src.plan.cpo import op_status


def _sugestao_operadores(entry: Dict[str, Any], state: Any) -> str:
    fase = str(entry.get("phase_id") or "")
    missing = entry.get("missing") or {}
    needed = int(missing.get("needed") or 1)
    pool_n = int(missing.get("pool_size") or 0)
    history = getattr(state, "skill_matrix_history", None) or {}
    pool = set()
    wf = getattr(state, "workers_for", None)
    if wf is not None and fase:
        try:
            pool = set(wf(fase) or ())
        except Exception:  # pragma: no cover — defensivo
            pool = set()
    fora = sorted(set(history.get(fase, set())) - pool)
    if fora:
        top = ", ".join(fora[:3])
        return (
            f"Faltam operadores (pool {pool_n}, precisos {needed}). "
            f"Com histórico real da fase mas fora do pool atual "
            f"(certificação/ativos): {top} — qualificar/reativar um deles."
        )
    return (
        f"Faltam operadores (pool {pool_n}, precisos {needed}) e ninguém "
        f"tem histórico da fase {fase} — formar um operador nesta fase."
    )


def _sugestao_molde(entry: Dict[str, Any], state: Any) -> str:
    model_id = str((entry.get("missing") or {}).get("model_id") or "")
    by_model = getattr(state, "molds_by_model", None) or {}
    candidatos = by_model.get(model_id, [])
    em_rep = [m.molde_id for m in candidatos if getattr(m, "em_manutencao", False)]
    if em_rep:
        return (
            f"Sem molde livre para o modelo {model_id}: "
            f"{len(em_rep)} em reparação ({', '.join(em_rep[:3])}) — "
            "concluir a manutenção liberta a laminação."
        )
    return (
        f"Nenhum molde registado para o modelo {model_id} — registar o molde "
        "no ERP (OF 70000-79999) ou confirmar a assinatura (np/modelo/tamanho)."
    )


def _sugestao_horizonte(entry: Dict[str, Any]) -> str:
    missing = entry.get("missing") or {}
    try:
        end = datetime.fromisoformat(str(missing.get("end_estimado")))
        hor = datetime.fromisoformat(str(missing.get("horizon_end")))
        dias = max(1, math.ceil((end - hor).total_seconds() / 86400.0))
        return (
            f"Não cabe no horizonte por ~{dias} dia(s) — atrasar a OF "
            f"{entry.get('order_id')} {dias}d, ou alargar o horizonte de "
            "planeamento."
        )
    except (ValueError, TypeError):
        return "Não cabe no horizonte — atrasar a OF ou alargar o horizonte."


_STATIC = {
    op_status.SEM_ROTA: (
        "Sem rota de produção (sem histórico nem template) — definir a rota "
        "do modelo no editor de fases ou confirmar o catálogo do produto."
    ),
    op_status.BLOCKED_PRECEDENCIA: (
        "Dependências de rota impossíveis (deadlock) — rever a sequência de "
        "fases/predecessores alternativos do modelo."
    ),
    op_status.BLOCKED_COMPONENTE: (
        "Componente em atraso — acelerar a OF da peça ou confirmar a ETA."
    ),
}


def enrich_unplannable(
    unplannable: List[Dict[str, Any]], state: Any,
) -> List[Dict[str, Any]]:
    """Acrescenta ``label_pt`` + ``suggestion_pt`` a cada entrada (in-place,
    devolve a lista). Entrada desconhecida fica sem sugestão (honesto)."""
    for entry in unplannable:
        status = str(entry.get("status") or "")
        entry.setdefault("label_pt", op_status.label_pt(status))
        if "suggestion_pt" in entry:
            continue
        if status == op_status.BLOCKED_OPERADORES:
            entry["suggestion_pt"] = _sugestao_operadores(entry, state)
        elif status == op_status.BLOCKED_MOLDE:
            entry["suggestion_pt"] = _sugestao_molde(entry, state)
        elif status == op_status.BLOCKED_HORIZONTE:
            entry["suggestion_pt"] = _sugestao_horizonte(entry)
        elif status in _STATIC:
            entry["suggestion_pt"] = _STATIC[status]
    return unplannable
