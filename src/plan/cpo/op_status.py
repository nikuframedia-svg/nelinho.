"""Q.174.F5 — vocabulário de estado de planeabilidade por operação.

Decisão do dono (2026-06-12): «plano parcial + secção inviável» — o plano
publica o que é exequível e lista À PARTE o que NÃO foi planeável, por
op/barco, com o RECURSO em falta e sugestões acionáveis. Nunca silêncio,
nunca plano falso (invariante #8).

Este módulo é só o vocabulário (strings estáveis, viajam em JSON para o
commit/API/FE) + helpers puros. A captura das razões vive no decoder
(`SchedulingLoopResult.blocked`) e no orquestrador (`run_cpo_schedule`
monta a secção `unplannable` — o caminho CP-SAT agenda tudo no post-pass,
pelo que as suas entradas vêm do resolver/anotações).
"""
from __future__ import annotations

# Op planeada normalmente.
VIAVEL = "VIAVEL"
#: Op agendada mas com risco de material (Q.174.F6 — constraint soft).
RISCO_MATERIAL = "RISCO_MATERIAL"
#: Sem operadores suficientes (pool fino em fase pair-REQUIRED).
BLOCKED_OPERADORES = "BLOCKED_OPERADORES"
#: Fase exige molde e não há molde conhecido para o modelo.
BLOCKED_MOLDE = "BLOCKED_MOLDE"
#: Deadlock de precedência (dados de rota inconsistentes).
BLOCKED_PRECEDENCIA = "BLOCKED_PRECEDENCIA"
#: A op não cabe no horizonte de planeamento.
BLOCKED_HORIZONTE = "BLOCKED_HORIZONTE"
#: A dependência de componente (peça) não chega a tempo (Q.174.F7).
BLOCKED_COMPONENTE = "BLOCKED_COMPONENTE"
#: A ordem não tem rota nenhuma (sem histórico, sem template, sem canónica).
SEM_ROTA = "SEM_ROTA"

#: Razões consideradas BLOQUEIO (entram na secção unplannable).
BLOCKED_STATUSES = frozenset({
    BLOCKED_OPERADORES,
    BLOCKED_MOLDE,
    BLOCKED_PRECEDENCIA,
    BLOCKED_HORIZONTE,
    BLOCKED_COMPONENTE,
    SEM_ROTA,
})

_LABEL_PT = {
    VIAVEL: "Planeável",
    RISCO_MATERIAL: "Risco de material",
    BLOCKED_OPERADORES: "Sem operadores suficientes",
    BLOCKED_MOLDE: "Sem molde disponível",
    BLOCKED_PRECEDENCIA: "Precedência impossível",
    BLOCKED_HORIZONTE: "Não cabe no horizonte",
    BLOCKED_COMPONENTE: "Componente em atraso",
    SEM_ROTA: "Sem rota de produção",
}


def label_pt(status: str) -> str:
    """Etiqueta PT-PT para UI/alertas (passthrough para desconhecidos)."""
    return _LABEL_PT.get(status, status)
